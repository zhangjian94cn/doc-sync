"""
Live Sync WebSocket Server

Provides real-time collaborative editing by:
1. Polling Feishu blocks periodically and broadcasting changes
2. Managing block-level locks
3. Proxying block updates to Feishu API
4. **Bidirectional file sync**: local .md ↔ Feishu cloud (when local_path provided)
   - Single file mode: watches one .md ↔ one doc
   - Folder mode: watches entire folder, dynamically resolves each changed file to its cloud doc
"""

import asyncio
import json
import os
import time
from typing import Dict, Set, Optional, Any

try:
    import websockets
    from websockets.server import serve
except ImportError:
    websockets = None

from doc_sync.feishu_client import FeishuClient
from doc_sync.live.lock_manager import LockManager
from doc_sync.logger import logger

import lark_oapi as lark


class LiveSyncServer:
    """WebSocket server for real-time block-level collaborative editing.
    
    Connects to a single Feishu document and allows multiple clients to:
    - View all blocks in real-time
    - Lock individual blocks for exclusive editing
    - Push block content updates
    
    When local_path is provided, also performs bidirectional file sync:
    - Local .md changes → automatically pushed to Feishu
    - Feishu changes → automatically written back to local .md
    
    Supports folder mode: watches an entire local folder and syncs each
    changed .md file to its corresponding cloud document.
    """

    def __init__(self, client: FeishuClient, doc_token: str, 
                 host: str = "localhost", port: int = 8765,
                 poll_interval: float = 3.0,
                 local_path: str = None, vault_root: str = None,
                 is_folder_mode: bool = False):
        """Initialize the live sync server.
        
        Args:
            client: Authenticated FeishuClient instance.
            doc_token: Feishu document token (or folder token in folder mode).
            host: WebSocket server host.
            port: WebSocket server port.
            poll_interval: Seconds between Feishu API polls.
            local_path: Optional local .md file/folder path for bidirectional sync.
            vault_root: Optional Obsidian vault root for resource resolution.
            is_folder_mode: If True, local_path is a directory and doc_token is a folder.
        """
        if websockets is None:
            raise ImportError(
                "websockets package is required for live sync. "
                "Install it with: pip install websockets>=12.0"
            )
        
        self.client = client
        self.doc_token = doc_token  # In folder mode, this is the cloud folder token
        self.host = host
        self.port = port
        self.poll_interval = poll_interval
        self.local_path = local_path
        self.vault_root = vault_root
        self.is_folder_mode = is_folder_mode
        
        # In single-file mode, doc_token is the actual doc to poll
        # In folder mode, we track the "active" doc being polled for WebSocket clients
        self._active_doc_token: Optional[str] = None if is_folder_mode else doc_token
        self._active_local_path: Optional[str] = None if is_folder_mode else local_path
        
        self.lock_manager = LockManager(lock_timeout=300.0)
        self._clients: Set = set()
        self._client_users: Dict[Any, str] = {}  # websocket -> user name
        self._last_blocks: Dict[str, Dict] = {}  # block_id -> block data
        self._running = False
        
        # File watcher for bidirectional sync
        self._file_watcher = None
        self._sync_loop: Optional[asyncio.AbstractEventLoop] = None
        # Guard against concurrent sync operations
        self._sync_in_progress = False
        # Content hash cache to skip no-op syncs
        self._last_synced_hashes: Dict[str, str] = {}

    async def start(self):
        """Start the WebSocket server and block polling loop."""
        logger.info(f"启动 Live Sync 服务器: ws://{self.host}:{self.port}", icon="🚀")
        if self.is_folder_mode:
            logger.info(f"文件夹 Token: {self.doc_token}", icon="📂")
            logger.info(f"本地文件夹: {self.local_path}", icon="📁")
        else:
            logger.info(f"文档 Token: {self.doc_token}", icon="📄")
            if self.local_path:
                logger.info(f"本地文件: {self.local_path}", icon="📝")
        
        self._running = True
        self._sync_loop = asyncio.get_event_loop()
        
        # Start file watcher if local_path is configured
        if self.local_path:
            self._start_file_watcher()
        
        async with serve(self._handle_client, self.host, self.port):
            # Start the polling task
            poll_task = asyncio.create_task(self._poll_loop())
            logger.info(f"Live Sync 服务器已启动，轮询间隔: {self.poll_interval}s", icon="✅")
            if self.local_path:
                if self.is_folder_mode:
                    logger.info("文件夹模式: 监听所有 .md 文件变更，自动同步", icon="🔄")
                else:
                    logger.info("双向同步已启用: 本地文件 ↔ 飞书云端", icon="🔄")
            
            try:
                # Keep running until stopped
                while self._running:
                    await asyncio.sleep(0.5)
            finally:
                poll_task.cancel()
                try:
                    await poll_task
                except asyncio.CancelledError:
                    pass
                self._stop_file_watcher()

    def stop(self):
        """Signal the server to stop."""
        self._running = False

    def _start_file_watcher(self):
        """Initialize and start the file watcher."""
        if not self.local_path or not os.path.exists(self.local_path):
            logger.warning(f"本地路径不存在，跳过文件监听: {self.local_path}")
            return
        
        from doc_sync.live.file_watcher import FileWatcher
        
        def on_local_change(changed_path: str):
            """Called from watchdog thread when local file changes."""
            if self._sync_loop and self._running:
                asyncio.run_coroutine_threadsafe(
                    self._on_local_file_changed(changed_path), self._sync_loop
                )
        
        self._file_watcher = FileWatcher(
            self.local_path, on_local_change, debounce=1.0
        )
        self._file_watcher.start()

    def _stop_file_watcher(self):
        """Stop the file watcher if running."""
        if self._file_watcher:
            self._file_watcher.stop()
            self._file_watcher = None

    def _resolve_cloud_doc_for_file(self, local_file_path: str) -> Optional[str]:
        """In folder mode, resolve which cloud doc corresponds to a local file.
        
        Walks the cloud folder structure to mirror the local relative path.
        Returns the doc_token or None if not found.
        """
        if not self.is_folder_mode:
            return self._active_doc_token
        
        rel_path = os.path.relpath(local_file_path, self.local_path)
        parts = rel_path.replace("\\", "/").split("/")
        doc_name = os.path.splitext(parts[-1])[0]  # filename without .md
        
        # Navigate cloud folder structure
        current_folder = self.doc_token
        for subfolder_name in parts[:-1]:
            try:
                sub_files = self.client.list_folder_files(current_folder)
                match = next((f for f in sub_files if f.name == subfolder_name and f.type == "folder"), None)
                if match:
                    current_folder = match.token
                else:
                    logger.warning(f"云端未找到文件夹: {subfolder_name}")
                    return None
            except Exception as e:
                logger.error(f"遍历云端文件夹失败: {e}")
                return None
        
        # Find the doc in the final folder
        try:
            files = self.client.list_folder_files(current_folder)
            doc = next((f for f in files if f.name == doc_name and f.type == "docx"), None)
            if doc:
                return doc.token
            else:
                logger.warning(f"云端未找到文档: {doc_name}")
                return None
        except Exception as e:
            logger.error(f"查找云端文档失败: {e}")
            return None

    async def _on_local_file_changed(self, changed_path: str):
        """Handle local file modification: push changes to Feishu cloud."""
        if self._sync_in_progress:
            return
        
        self._sync_in_progress = True
        try:
            rel = os.path.relpath(changed_path, self.local_path) if self.is_folder_mode else os.path.basename(changed_path)
            logger.info(f"检测到本地文件变更: {rel}，正在同步到云端...", icon="📤")
            
            loop = asyncio.get_event_loop()
            # Suppress watcher during sync to prevent re-triggering
            if self._file_watcher:
                with self._file_watcher.suppress():
                    success = await loop.run_in_executor(
                        None, lambda: self._sync_file_to_cloud(changed_path)
                    )
            else:
                success = await loop.run_in_executor(
                    None, lambda: self._sync_file_to_cloud(changed_path)
                )
            
            if success:
                logger.success(f"本地变更已同步到云端: {rel}", icon="✅")
                # In single-file mode, refresh block cache and broadcast
                if not self.is_folder_mode:
                    await self._poll_blocks()
            else:
                logger.error(f"本地变更同步到云端失败: {rel}")
        except Exception as e:
            logger.error(f"本地→云端同步出错: {e}")
        finally:
            self._sync_in_progress = False

    def _sync_file_to_cloud(self, local_file_path: str) -> bool:
        """Synchronous: sync a local .md to its Feishu doc using SyncManager (runs in executor).
        
        Uses content hash caching to skip syncs when file content hasn't changed.
        Falls back to SyncManager's diff logic which handles incremental or full overwrite.
        """
        try:
            import hashlib
            
            # Read file and compute hash
            with open(local_file_path, 'r', encoding='utf-8') as f:
                md_content = f.read()
            
            if not md_content.strip():
                return True  # Empty file, skip
            
            content_hash = hashlib.md5(md_content.encode('utf-8')).hexdigest()
            
            # Skip if content hasn't changed since last successful sync
            last_hash = self._last_synced_hashes.get(local_file_path)
            if last_hash == content_hash:
                logger.info("文件内容未变化，跳过同步", icon="⏭️")
                return True
            
            # Resolve cloud doc token
            doc_token = self._resolve_cloud_doc_for_file(local_file_path)
            if not doc_token:
                logger.warning(f"未找到对应的云端文档，跳过同步: {local_file_path}")
                return False
            
            from doc_sync.sync.manager import SyncManager
            
            manager = SyncManager(
                md_path=local_file_path,
                doc_token=doc_token,
                force=True,  # Always sync (skip mtime comparison)
                overwrite=False,  # Let SyncManager decide strategy
                vault_root=self.vault_root,
                client=self.client,
            )
            manager._sync_local_to_cloud()
            
            # Cache hash after successful sync
            self._last_synced_hashes[local_file_path] = content_hash
            return True
        except Exception as e:
            logger.error(f"本地→云端同步失败: {e}")
            return False

    async def _sync_cloud_to_local(self):
        """Write current cloud blocks back to local .md file (single-file mode only)."""
        if not self._active_local_path or self._sync_in_progress:
            return
        
        self._sync_in_progress = True
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._write_cloud_to_local)
        except Exception as e:
            logger.error(f"云端→本地同步出错: {e}")
        finally:
            self._sync_in_progress = False

    def _write_cloud_to_local(self):
        """Synchronous: fetch cloud blocks and write to local .md (runs in executor)."""
        try:
            from doc_sync.converter import FeishuToMarkdown
            
            doc_token = self._active_doc_token
            local_path = self._active_local_path
            if not doc_token or not local_path:
                return
            
            blocks = self.client.list_document_blocks(doc_token)
            if blocks is None:
                return
            
            # Filter out the document root block (type 1)
            blocks = [b for b in blocks if b.block_type != 1]
            
            if not blocks:
                return  # Empty doc, don't overwrite
            
            # Set up image downloader if vault_root is available
            image_downloader = None
            if self.vault_root:
                attachments_dir = os.path.join(self.vault_root, "attachments")
                os.makedirs(attachments_dir, exist_ok=True)
                
                def downloader(token: str):
                    dl_path = os.path.join(attachments_dir, f"{token}.png")
                    result = self.client.download_image(token, dl_path)
                    if result:
                        return f"attachments/{token}.png"
                    return None
                
                image_downloader = downloader
            
            converter = FeishuToMarkdown(image_downloader=image_downloader)
            md_content = converter.convert(blocks)
            
            # Suppress file watcher to avoid feedback loop
            if self._file_watcher:
                with self._file_watcher.suppress():
                    with open(local_path, 'w', encoding='utf-8') as f:
                        f.write(md_content)
            else:
                with open(local_path, 'w', encoding='utf-8') as f:
                    f.write(md_content)
            
            logger.info("云端变更已写入本地文件", icon="📥")
        except Exception as e:
            logger.error(f"云端→本地写入失败: {e}")

    async def _handle_client(self, websocket):
        """Handle a new WebSocket client connection."""
        self._clients.add(websocket)
        client_addr = websocket.remote_address
        logger.info(f"客户端已连接: {client_addr}", icon="🔗")
        
        try:
            async for raw_message in websocket:
                try:
                    message = json.loads(raw_message)
                    await self._process_message(websocket, message)
                except json.JSONDecodeError:
                    await self._send(websocket, {
                        "event": "error",
                        "message": "Invalid JSON"
                    })
                except Exception as e:
                    logger.error(f"处理消息出错: {e}")
                    await self._send(websocket, {
                        "event": "error",
                        "message": str(e)
                    })
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            # Clean up on disconnect
            user = self._client_users.pop(websocket, None)
            self._clients.discard(websocket)
            
            if user:
                released = self.lock_manager.release_all(user)
                if released > 0:
                    logger.info(f"用户 {user} 断开连接，释放 {released} 个锁", icon="🔓")
                    # Broadcast updated lock state
                    await self._broadcast_locks()
            
            logger.info(f"客户端已断开: {client_addr}", icon="🔌")

    async def _process_message(self, websocket, message: dict):
        """Process an incoming WebSocket message."""
        action = message.get("action")
        
        if action == "subscribe":
            user = message.get("user", "anonymous")
            self._client_users[websocket] = user
            logger.info(f"用户 {user} 已订阅文档", icon="👤")
            
            # Send current block snapshot
            await self._send(websocket, {
                "event": "blocks_snapshot",
                "blocks": list(self._last_blocks.values()),
                "locks": self.lock_manager.get_locks()
            })
        
        elif action == "lock":
            block_id = message.get("block_id")
            user = self._client_users.get(websocket, "anonymous")
            
            if not block_id:
                await self._send(websocket, {"event": "error", "message": "block_id required"})
                return
            
            success = self.lock_manager.acquire(block_id, user)
            if success:
                logger.debug(f"用户 {user} 锁定 block {block_id}")
                await self._broadcast({
                    "event": "lock_acquired",
                    "block_id": block_id,
                    "user": user
                })
            else:
                holder = self.lock_manager.get_holder(block_id)
                await self._send(websocket, {
                    "event": "lock_denied",
                    "block_id": block_id,
                    "held_by": holder
                })
        
        elif action == "unlock":
            block_id = message.get("block_id")
            user = self._client_users.get(websocket, "anonymous")
            
            if not block_id:
                await self._send(websocket, {"event": "error", "message": "block_id required"})
                return
            
            success = self.lock_manager.release(block_id, user)
            if success:
                logger.debug(f"用户 {user} 释放 block {block_id}")
                await self._broadcast({
                    "event": "lock_released",
                    "block_id": block_id
                })
        
        elif action == "update_block":
            block_id = message.get("block_id")
            content = message.get("content")
            user = self._client_users.get(websocket, "anonymous")
            
            if not block_id or content is None:
                await self._send(websocket, {
                    "event": "error",
                    "message": "block_id and content required"
                })
                return
            
            # Check lock
            holder = self.lock_manager.get_holder(block_id)
            if holder != user:
                await self._send(websocket, {
                    "event": "error",
                    "message": f"Block is locked by {holder}" if holder else "Block is not locked by you"
                })
                return
            
            # Push update to Feishu
            await self._update_block_on_feishu(block_id, content, websocket)
        
        elif action == "refresh":
            # Force a fresh poll
            await self._poll_blocks()
        
        else:
            await self._send(websocket, {
                "event": "error",
                "message": f"Unknown action: {action}"
            })

    async def _update_block_on_feishu(self, block_id: str, content: dict, websocket):
        """Push a block content update to Feishu API.
        
        Args:
            block_id: The block to update.
            content: Dict with "elements" list of text elements.
            websocket: The requesting client's websocket.
        """
        try:
            elements = content.get("elements", [])
            if not elements:
                await self._send(websocket, {
                    "event": "error",
                    "message": "content.elements is required and must be non-empty"
                })
                return
            
            doc_token = self._active_doc_token or self.doc_token
            
            # Run the API call in a thread to avoid blocking the event loop
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(
                None,
                lambda: self.client.update_block_text(doc_token, block_id, elements)
            )
            
            if success:
                await self._send(websocket, {
                    "event": "update_success",
                    "block_id": block_id
                })
                # Trigger a poll to broadcast the updated state
                await self._poll_blocks()
            else:
                await self._send(websocket, {
                    "event": "error",
                    "message": f"Failed to update block {block_id} on Feishu"
                })
        except Exception as e:
            logger.error(f"更新 block {block_id} 失败: {e}")
            await self._send(websocket, {
                "event": "error",
                "message": f"Update failed: {str(e)}"
            })

    async def _poll_loop(self):
        """Periodically poll Feishu for block changes."""
        while self._running:
            try:
                # Only poll if we have an active doc (not in folder-only mode)
                if self._active_doc_token:
                    await self._poll_blocks()
            except Exception as e:
                logger.error(f"轮询出错: {e}")
            
            await asyncio.sleep(self.poll_interval)

    async def _poll_blocks(self):
        """Fetch all blocks from Feishu and broadcast any changes."""
        doc_token = self._active_doc_token
        if not doc_token:
            return
        
        loop = asyncio.get_event_loop()
        
        try:
            blocks_raw = await loop.run_in_executor(
                None,
                lambda: self.client.list_document_blocks(doc_token)
            )
        except Exception as e:
            logger.error(f"获取文档块失败: {e}")
            return
        
        if blocks_raw is None:
            return
        
        # Convert to dicts
        new_blocks: Dict[str, Dict] = {}
        for b in blocks_raw:
            try:
                d = json.loads(lark.JSON.marshal(b))
                block_id = d.get("block_id")
                if block_id:
                    new_blocks[block_id] = d
            except Exception:
                pass
        
        # Find changes
        changed_blocks = []
        for bid, bdata in new_blocks.items():
            old = self._last_blocks.get(bid)
            if old is None or old != bdata:
                changed_blocks.append(bdata)
        
        # Find removed blocks
        removed_ids = set(self._last_blocks.keys()) - set(new_blocks.keys())
        
        has_changes = bool(changed_blocks or removed_ids)
        self._last_blocks = new_blocks
        
        # Broadcast changes to WebSocket clients
        if has_changes:
            if len(changed_blocks) > len(new_blocks) * 0.5 or not self._last_blocks:
                # Major change — send full snapshot
                await self._broadcast({
                    "event": "blocks_snapshot",
                    "blocks": list(new_blocks.values()),
                    "locks": self.lock_manager.get_locks()
                })
            else:
                # Incremental updates
                for block in changed_blocks:
                    await self._broadcast({
                        "event": "block_updated",
                        "block_id": block["block_id"],
                        "block": block
                    })
                for bid in removed_ids:
                    await self._broadcast({
                        "event": "block_removed",
                        "block_id": bid
                    })
            
            # Cloud → Local: write back changes to local file (single-file mode only)
            if self._active_local_path and not self._sync_in_progress:
                await self._sync_cloud_to_local()

    async def _broadcast_locks(self):
        """Broadcast current lock state to all clients."""
        await self._broadcast({
            "event": "locks_update",
            "locks": self.lock_manager.get_locks()
        })

    async def _broadcast(self, message: dict):
        """Send a message to all connected clients."""
        if not self._clients:
            return
        data = json.dumps(message, ensure_ascii=False)
        disconnected = set()
        for ws in self._clients:
            try:
                await ws.send(data)
            except Exception:
                disconnected.add(ws)
        # Clean up disconnected clients
        for ws in disconnected:
            self._clients.discard(ws)

    async def _send(self, websocket, message: dict):
        """Send a message to a single client."""
        try:
            await websocket.send(json.dumps(message, ensure_ascii=False))
        except Exception:
            pass


def run_live_server(app_id: str, app_secret: str, user_access_token: str,
                    doc_token: str, host: str = "localhost", port: int = 8765,
                    poll_interval: float = 3.0,
                    local_path: str = None, vault_root: str = None,
                    is_folder_mode: bool = False):
    """Convenience function to create and run a live sync server.
    
    Args:
        app_id: Feishu app ID.
        app_secret: Feishu app secret. 
        user_access_token: Feishu user access token.
        doc_token: Document token (or folder token in folder mode).
        host: Server host.
        port: Server port.
        poll_interval: Polling interval in seconds.
        local_path: Optional local .md file/folder for bidirectional sync.
        vault_root: Optional Obsidian vault root for resource resolution.
        is_folder_mode: Whether to run in folder sync mode.
    """
    client = FeishuClient(app_id, app_secret, user_access_token)
    server = LiveSyncServer(client, doc_token, host, port, poll_interval,
                            local_path=local_path, vault_root=vault_root,
                            is_folder_mode=is_folder_mode)
    
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("Live Sync 服务器已停止", icon="🛑")
