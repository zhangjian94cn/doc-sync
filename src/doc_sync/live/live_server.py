"""
Live Sync WebSocket Server

Provides real-time collaborative editing by:
1. Polling Feishu blocks periodically and broadcasting changes
2. Managing block-level locks
3. Proxying block updates to Feishu API
"""

import asyncio
import json
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
    """

    def __init__(self, client: FeishuClient, doc_token: str, 
                 host: str = "localhost", port: int = 8765,
                 poll_interval: float = 3.0):
        """Initialize the live sync server.
        
        Args:
            client: Authenticated FeishuClient instance.
            doc_token: Feishu document token to sync.
            host: WebSocket server host.
            port: WebSocket server port.
            poll_interval: Seconds between Feishu API polls.
        """
        if websockets is None:
            raise ImportError(
                "websockets package is required for live sync. "
                "Install it with: pip install websockets>=12.0"
            )
        
        self.client = client
        self.doc_token = doc_token
        self.host = host
        self.port = port
        self.poll_interval = poll_interval
        
        self.lock_manager = LockManager(lock_timeout=300.0)
        self._clients: Set = set()
        self._client_users: Dict[Any, str] = {}  # websocket -> user name
        self._last_blocks: Dict[str, Dict] = {}  # block_id -> block data
        self._running = False

    async def start(self):
        """Start the WebSocket server and block polling loop."""
        logger.info(f"启动 Live Sync 服务器: ws://{self.host}:{self.port}", icon="🚀")
        logger.info(f"文档 Token: {self.doc_token}", icon="📄")
        
        self._running = True
        
        async with serve(self._handle_client, self.host, self.port):
            # Start the polling task
            poll_task = asyncio.create_task(self._poll_loop())
            logger.info(f"Live Sync 服务器已启动，轮询间隔: {self.poll_interval}s", icon="✅")
            
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

    def stop(self):
        """Signal the server to stop."""
        self._running = False

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
            
            # Run the API call in a thread to avoid blocking the event loop
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(
                None,
                lambda: self.client.update_block_text(self.doc_token, block_id, elements)
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
                if self._clients:  # Only poll if there are connected clients
                    await self._poll_blocks()
            except Exception as e:
                logger.error(f"轮询出错: {e}")
            
            await asyncio.sleep(self.poll_interval)

    async def _poll_blocks(self):
        """Fetch all blocks from Feishu and broadcast any changes."""
        loop = asyncio.get_event_loop()
        
        try:
            blocks_raw = await loop.run_in_executor(
                None,
                lambda: self.client.list_document_blocks(self.doc_token)
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
        
        self._last_blocks = new_blocks
        
        # Broadcast changes
        if changed_blocks or removed_ids:
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
                    poll_interval: float = 3.0):
    """Convenience function to create and run a live sync server.
    
    Args:
        app_id: Feishu app ID.
        app_secret: Feishu app secret. 
        user_access_token: Feishu user access token.
        doc_token: Document token to sync.
        host: Server host.
        port: Server port.
        poll_interval: Polling interval in seconds.
    """
    client = FeishuClient(app_id, app_secret, user_access_token)
    server = LiveSyncServer(client, doc_token, host, port, poll_interval)
    
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("Live Sync 服务器已停止", icon="🛑")
