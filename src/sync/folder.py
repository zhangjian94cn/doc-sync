"""
Folder Sync Manager Module

Provides folder-level synchronization with concurrent file processing.
"""

import os
from datetime import datetime
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from src import config
from src.feishu_client import FeishuClient
from src.logger import logger


class FolderSyncManager:
    """Manages folder-level synchronization with concurrent file processing."""
    
    def __init__(self, local_root: str, cloud_root_token: str, force: bool = False, 
                 vault_root: str = None, debug: bool = False, client: FeishuClient = None):
        self.local_root = local_root
        self.cloud_root_token = cloud_root_token
        self.force = force
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
        self.stats = {"created": 0, "updated": 0, "skipped": 0, "failed": 0}
        self._stats_lock = None

    def run(self):
        """Run folder synchronization with concurrent file processing."""
        # Import here to avoid circular imports
        from src.sync.manager import SyncManager
        
        self._stats_lock = threading.Lock()
        
        logger.header(f"开始文件夹同步: {self.local_root} -> {self.cloud_root_token}", icon="🚀")
        
        sync_tasks = self._collect_sync_tasks(self.local_root, self.cloud_root_token)
        
        if not sync_tasks:
            logger.info("没有需要同步的文件。", icon="✓")
            return
        
        logger.info(f"发现 {len(sync_tasks)} 个文件需要同步，使用 {config.MAX_PARALLEL_WORKERS} 个并行工作线程...", icon="⚡")
        
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
                            elif result == "failed":
                                self.stats["failed"] += 1
                    except Exception as e:
                        logger.error(f"同步任务失败: {task['local_path']}: {e}")
                        with self._stats_lock:
                            self.stats["failed"] += 1
                    finally:
                        update(1)
        
        logger.summary_table("📊 同步汇总", {
            "✅ 新增": self.stats['created'],
            "🔄 更新": self.stats['updated'],
            "⏭️ 跳过": self.stats['skipped'],
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
                    used_cloud_tokens.add(cloud_map[doc_name].token)
                    tasks.append({
                        "local_path": item_path,
                        "doc_token": cloud_map[doc_name].token,
                        "is_new": False
                    })
                else:
                    new_token = self.client.create_docx(cloud_token, doc_name)
                    if new_token:
                        tasks.append({
                            "local_path": item_path,
                            "doc_token": new_token,
                            "is_new": True
                        })
                    else:
                        with self._stats_lock:
                            self.stats["failed"] += 1
        
        # Prune deleted files/folders
        for name, file in cloud_map.items():
            if file.token not in used_cloud_tokens:
                if name in ["DocSync_Assets", "assets", ".Trash"]:
                    continue
                
                logger.info(f"本地不存在 '{name}'，正在从云端删除...", icon="🗑️")
                delete_type = file.type if file.type in ["docx", "folder", "file", "sheet", "bitable"] else "docx"
                self.client.delete_file(file.token, file_type=delete_type)

        return tasks

    def _execute_sync_task(self, task: Dict[str, Any], SyncManager) -> str:
        """Execute a single sync task. Returns 'created', 'updated', or 'failed'."""
        try:
            sync = SyncManager(
                task["local_path"], 
                task["doc_token"], 
                force=self.force or task["is_new"],
                vault_root=self.vault_root, 
                client=self.client, 
                batch_id=self.batch_id
            )
            sync.run(debug=self.debug)
            return "created" if task["is_new"] else "updated"
        except Exception as e:
            logger.error(f"同步失败 {os.path.basename(task['local_path'])}: {e}")
            return "failed"
