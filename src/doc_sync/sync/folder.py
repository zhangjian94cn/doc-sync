"""
Folder Sync Manager Module

Provides folder-level synchronization with concurrent file processing.
"""

import os
from datetime import datetime
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from doc_sync import config
from doc_sync.feishu_client import FeishuClient
from doc_sync.logger import logger


from doc_sync.sync.state import SyncState

class FolderSyncManager:
    """Manages folder-level synchronization with concurrent file processing."""
    
    def __init__(self, local_root: str, cloud_root_token: str, force: bool = False, overwrite: bool = False,
                 vault_root: str = None, debug: bool = False, client: FeishuClient = None):
        self.local_root = local_root
        self.cloud_root_token = cloud_root_token
        self.force = force
        self.overwrite = overwrite
        self.vault_root = vault_root or local_root
        self.debug = debug
        self.batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        if client:
            self.client = client
        else:
            self.client = FeishuClient(
                config.FEISHU_APP_ID, 
                config.FEISHU_APP_SECRET, 
                user_access_token=config.FEISHU_USER_ACCESS_TOKEN
            )
        self.stats = {"created": 0, "updated": 0, "skipped": 0, "failed": 0, "deleted_cloud": 0, "deleted_local": 0}
        self._stats_lock = threading.Lock()  # Initialize early to ensure thread safety
        self.state = SyncState(self.vault_root)

    def run(self):
        """Run folder synchronization with concurrent file processing."""
        # Import here to avoid circular imports
        from doc_sync.sync.manager import SyncManager
        
        self._stats_lock = threading.Lock()
        
        logger.header(f"开始文件夹同步: {self.local_root} -> {self.cloud_root_token}", icon="🚀")
        
        sync_tasks = self._collect_sync_tasks(self.local_root, self.cloud_root_token)
        
        if not sync_tasks:
            logger.info("没有需要同步的文件。", icon="✓")
            return
        
        logger.info(f"发现 {len(sync_tasks)} 个任务，使用 {config.MAX_PARALLEL_WORKERS} 个并行工作线程...", icon="⚡")
        
        with ThreadPoolExecutor(max_workers=config.MAX_PARALLEL_WORKERS) as executor:
            futures = {executor.submit(self._execute_sync_task, task, SyncManager): task for task in sync_tasks}
            
            with logger.progress(len(sync_tasks), "🔄 同步进度") as update:
                for future in as_completed(futures):
                    task = futures[future]
                    try:
                        result = future.result()
                        with self._stats_lock:
                            if result == "created":
                                self.stats["created"] += 1
                            elif result == "updated":
                                self.stats["updated"] += 1
                            elif result == "deleted_cloud":
                                self.stats["deleted_cloud"] += 1
                            elif result == "failed":
                                self.stats["failed"] += 1
                    except Exception as e:
                        logger.error(f"同步任务失败: {task.get('local_path', 'unknown')}: {e}")
                        with self._stats_lock:
                            self.stats["failed"] += 1
                    finally:
                        update(1)
        
        logger.summary_table("📊 同步汇总", {
            "✅ 新增/下载": self.stats['created'],
            "🔄 更新": self.stats['updated'],
            "🗑️ 云端删除": self.stats['deleted_cloud'],
            "❌ 失败": self.stats['failed']
        })

    def _collect_sync_tasks(self, local_path: str, cloud_token: str) -> List[Dict[str, Any]]:
        """Recursively collect all sync tasks from folder."""
        tasks = []
        
        try:
            local_items = os.listdir(local_path)
        except OSError as e:
            logger.error(f"无法读取目录 {local_path}: {e}")
            return tasks
        
        cloud_files = self.client.list_folder_files(cloud_token)
        cloud_map = {f.name: f for f in cloud_files}
        used_cloud_tokens = set()

        for item in local_items:
            # Skip hidden files, attachment directories, and Obsidian-specific files
            if item.startswith('.'):
                continue
            if item in ("assets", "attachments", "_attachments"):
                continue
            # Skip Excalidraw files (they won't sync properly to Feishu)
            if item.endswith(".excalidraw") or item.endswith(".excalidraw.md"):
                continue
            # Skip canvas files
            if item.endswith(".canvas"):
                continue
            
            item_path = os.path.join(local_path, item)
            
            if os.path.isdir(item_path):
                if item in cloud_map and cloud_map[item].type == "folder":
                    used_cloud_tokens.add(cloud_map[item].token)
                    tasks.extend(self._collect_sync_tasks(item_path, cloud_map[item].token))
                else:
                    new_token = self.client.create_folder(cloud_token, item)
                    if new_token:
                        tasks.extend(self._collect_sync_tasks(item_path, new_token))
                        
            elif item.endswith(".md"):
                doc_name = item[:-3]
                if doc_name in cloud_map and cloud_map[doc_name].type == "docx":
                    token = cloud_map[doc_name].token
                    used_cloud_tokens.add(token)
                    tasks.append({
                        "type": "sync",
                        "local_path": item_path,
                        "doc_token": token,
                        "is_new": False
                    })
                    # Update state
                    self.state.update(item_path, token)
                else:
                    # Check if it was known before (Maybe deleted on Cloud?)
                    known_info = self.state.get_by_path(item_path)
                    if known_info:
                        # It was known, but now missing from Cloud.
                        # Decision: Re-upload (Union preference).
                        logger.info(f"文件 '{item}' 在云端丢失，重新上传...", icon="📤")
                        pass
                    
                    new_token = self.client.create_docx(cloud_token, doc_name)
                    if new_token:
                        tasks.append({
                            "type": "sync",
                            "local_path": item_path,
                            "doc_token": new_token,
                            "is_new": True
                        })
                        self.state.update(item_path, new_token)
                    else:
                        with self._stats_lock:
                            self.stats["failed"] += 1
        
        # Check cloud files
        for name, file in cloud_map.items():
            if file.token not in used_cloud_tokens:
                if name in ["DocSync_Assets", "assets", ".Trash"]:
                    continue
                
                # Check if this file was known in our state
                known_info = self.state.get_by_token(file.token)
                
                if known_info:
                    # It was in our state, but NOT found in local scan (otherwise it would be in used_cloud_tokens).
                    # This means user DELETED it locally.
                    # Action: Delete from Cloud.
                    logger.info(f"检测到本地删除: '{name}'，正在同步删除云端文件...", icon="🗑️")
                    tasks.append({
                        "type": "delete_cloud",
                        "doc_token": file.token,
                        "file_type": file.type,
                        "local_path": known_info.get("path", name) # Just for logging
                    })
                    continue
                
                # Not in state -> New on Cloud -> Download
                if file.type == "docx":
                    local_name = name + ".md" 
                    local_file_path = os.path.join(local_path, local_name)
                    
                    logger.info(f"发现云端新增文档: '{name}'，准备下载...", icon="📥")
                    tasks.append({
                        "type": "sync",
                        "local_path": local_file_path,
                        "doc_token": file.token,
                        "is_new": False 
                    })
                    # We will update state after successful download in execute

                elif file.type == "folder":
                    local_folder_path = os.path.join(local_path, name)
                    if not os.path.exists(local_folder_path):
                        os.makedirs(local_folder_path)
                        logger.info(f"发现云端新增文件夹: '{name}'，已创建本地目录", icon="📂")
                    
                    tasks.extend(self._collect_sync_tasks(local_folder_path, file.token))
                
                else:
                    logger.info(f"跳过云端非文档文件: '{name}' ({file.type})", icon="⏭️")

        return tasks

    def _execute_sync_task(self, task: Dict[str, Any], SyncManager) -> str:
        """Execute a single sync task."""
        try:
            task_type = task.get("type", "sync")
            
            if task_type == "delete_cloud":
                self.client.delete_file(task["doc_token"], file_type=task.get("file_type", "docx"))
                self.state.remove_by_token(task["doc_token"])
                return "deleted_cloud"
            
            # Normal Sync
            sync = SyncManager(
                task["local_path"], 
                task["doc_token"], 
                force=self.force or task.get("is_new", False),
                overwrite=self.overwrite,
                vault_root=self.vault_root, 
                client=self.client, 
                batch_id=self.batch_id
            )
            sync.run(debug=self.debug)
            
            # Update state on success
            self.state.update(task["local_path"], task["doc_token"])
            
            return "created" if task.get("is_new") else "updated"
        except Exception as e:
            logger.error(f"任务失败: {task.get('local_path', 'unknown')}: {e}")
            return "failed"
