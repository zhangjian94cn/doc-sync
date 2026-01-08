import os
import sys
import hashlib
import json
import shutil
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import IntEnum
from urllib.parse import unquote
import difflib

import lark_oapi as lark

from src import config
from src.config import SYNC_DIFF_THRESHOLD
from src.feishu_client import FeishuClient
from src.converter import MarkdownToFeishu, FeishuToMarkdown
from src.utils import pad_center, parse_cloud_time
from src.logger import logger
from src.resource_index import ResourceIndex

class SyncResult(IntEnum):
    SUCCESS = 0
    EMPTY_CLOUD = 1
    ERROR = 2

class SyncManager:
    """Manages synchronization between local Markdown files and Feishu documents."""
    
    # Class-level resource index cache
    _resource_index: Optional[ResourceIndex] = None
    _resource_index_root: Optional[str] = None
    
    def __init__(self, md_path: str, doc_token: str, force: bool = False, 
                 vault_root: str = None, client: FeishuClient = None, batch_id: str = None):
        self.md_path = os.path.abspath(md_path)
        self.doc_token = doc_token
        self.force = force
        self.vault_root = vault_root or os.path.dirname(self.md_path)
        self.batch_id = batch_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Initialize or reuse resource index
        self._init_resource_index()
        
        if client:
            self.client = client
        else:
            self.client = FeishuClient(
                config.FEISHU_APP_ID, 
                config.FEISHU_APP_SECRET,
                user_access_token=config.FEISHU_USER_ACCESS_TOKEN
            )
    
    def _init_resource_index(self) -> None:
        """Initialize or reuse the resource index for the vault."""
        if (SyncManager._resource_index is None or 
            SyncManager._resource_index_root != self.vault_root):
            logger.debug(f"构建资源索引: {self.vault_root}")
            SyncManager._resource_index = ResourceIndex(
                self.vault_root,
                extensions={'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp',
                           'mp4', 'mov', 'avi', 'mkv', 'webm',
                           'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
                           'zip', 'rar', '7z', 'tar'}
            )
            SyncManager._resource_index_root = self.vault_root

    def run(self, debug=False):
        logger.header(f"任务: {os.path.basename(self.md_path)}", icon="📄")
        if not os.path.exists(self.md_path):
            logger.error(f"错误: 未找到文件: {self.md_path}")
            sys.exit(1)
            
        local_mtime = os.path.getmtime(self.md_path)
        logger.info(f"本地修改时间: {datetime.fromtimestamp(local_mtime)}", icon="🕒")
        
        logger.info(f"检查云端状态 ({self.doc_token})...", icon="🔍")
        try:
            file_info = self.client.get_file_info(self.doc_token, obj_type="docx")
        except Exception as e:
            logger.warning(f"无法获取文档元数据: {e}")
            file_info = None
        
        should_upload = True
        if not file_info:
            logger.warning("无法获取文档元数据 (可能是一个新文档或Token错误)。")
            should_upload = True
        else:
            if file_info.doc_type == "folder":
                logger.error(f"错误: 提供的 Token ({self.doc_token}) 是一个文件夹，SyncManager 只能处理文档。")
                sys.exit(1)
                
            cloud_mtime = parse_cloud_time(file_info.latest_modify_time)
            logger.info(f"云端修改时间: {datetime.fromtimestamp(cloud_mtime)}", icon="☁️ ")
            if cloud_mtime > local_mtime and not self.force:
                logger.info("开始反向同步 (云端 -> 本地)...", icon="🔄")
                result = self._sync_cloud_to_local()
                if result == SyncResult.SUCCESS: should_upload = False
                elif result == SyncResult.EMPTY_CLOUD: should_upload = True
                else: sys.exit(1)

        if should_upload: self._sync_local_to_cloud()
        if debug: self.verify_cloud_structure()

    def _calculate_tree_hash(self, block_dict: Dict[str, Any]) -> str:
        b_type = block_dict.get("block_type")
        content = ""
        mapping = {
            2: "text", 12: "bullet", 13: "ordered", 22: "todo", 14: "code",
            27: "image", 23: "file"
        }
        for i in range(1, 10): mapping[2+i] = f"heading{i}"
        
        field = mapping.get(b_type)
        if field and field in block_dict:
            obj = block_dict[field]
            if "elements" in obj:
                for el in obj["elements"]:
                    if "text_run" in el: content += el["text_run"].get("content", "")
            elif "image" in obj: content = obj["image"].get("token", "")
            elif "file" in obj: content = obj["file"].get("token", "")

        # Prioritize children_data (Cloud objects) or children (Local objects)
        # But filter out strings (Cloud IDs) to avoid AttributeError
        raw_children = block_dict.get("children_data")
        if not raw_children:
            raw_children = block_dict.get("children") or []
        
        children = [c for c in raw_children if isinstance(c, dict)]
        
        child_hashes = [self._calculate_tree_hash(c) for c in children]
        
        data_str = f"{b_type}:{content}:{','.join(child_hashes)}"
        return hashlib.md5(data_str.encode('utf-8')).hexdigest()

    def _sync_local_to_cloud(self):
        logger.info("正在将 Markdown 转换为飞书文档块...", icon="🔄")
        with open(self.md_path, 'r', encoding='utf-8') as f:
            md_content = f.read()
        
        converter = MarkdownToFeishu(image_uploader=lambda p: self._resource_uploader(p))
        local_blocks = converter.parse(md_content)
        logger.info(f"本地已生成 {len(local_blocks)} 个顶层文档块。", icon="✨")

        logger.info("获取云端现有内容以进行比对...", icon="🔍")
        cloud_blocks_flat = self.client.list_document_blocks(self.doc_token)
        
        cloud_dicts = []
        for b in cloud_blocks_flat:
            try: cloud_dicts.append(json.loads(lark.JSON.marshal(b)))
            except: pass
        
        cloud_map = {b["block_id"]: b for b in cloud_dicts}
        root_children = []
        for b in cloud_dicts:
            p_id = b.get("parent_id")
            if p_id == self.doc_token or not p_id:
                if b["block_type"] != 1: root_children.append(b)
            else:
                parent = cloud_map.get(p_id)
                if parent:
                    if "children_data" not in parent: parent["children_data"] = []
                    parent["children_data"].append(b)

        cloud_hashes = [self._calculate_tree_hash(b) for b in root_children]
        local_hashes = [self._calculate_tree_hash(b) for b in local_blocks]

        matcher = difflib.SequenceMatcher(None, cloud_hashes, local_hashes)
        opcodes = matcher.get_opcodes()
        ops_count = sum(1 for tag, i1, i2, j1, j2 in opcodes if tag != 'equal')

        if ops_count == 0:
            logger.success("内容已同步，无需更新。"); return

        if ops_count > SYNC_DIFF_THRESHOLD or not root_children:
            logger.warning("变更较多或为空文档，使用全量覆盖模式...")
            self.client.clear_document(self.doc_token)
            self.client.add_blocks(self.doc_token, local_blocks)
        else:
            logger.info(f"差异分析: 发现 {ops_count} 处变更。使用增量同步...", icon="📊")
            for tag, i1, i2, j1, j2 in reversed(opcodes):
                if tag == 'replace':
                    self.client.delete_blocks_by_index(self.doc_token, i1, i2)
                    self.client.add_blocks(self.doc_token, local_blocks[j1:j2], index=i1)
                elif tag == 'delete':
                    self.client.delete_blocks_by_index(self.doc_token, i1, i2)
                elif tag == 'insert':
                    self.client.add_blocks(self.doc_token, local_blocks[j1:j2], index=i1)
        logger.success(f"同步完成！文档链接: https://feishu.cn/docx/{self.doc_token}")

    def _resource_uploader(self, path: str) -> Optional[str]:
        """Resolve resource path using the cached index."""
        if not path or path.startswith("http"):
            return None
        
        # URL decode first (e.g., %E4%B8%AD%E6%96%87.png -> 中文.png)
        decoded_path = unquote(path)
        
        # Use ResourceIndex for efficient lookup
        if SyncManager._resource_index:
            real_path = SyncManager._resource_index.find(decoded_path)
            if real_path and os.path.exists(real_path):
                return real_path
        
        # Fallback: try path relative to current file
        md_dir = os.path.dirname(self.md_path)
        candidate = os.path.join(md_dir, decoded_path)
        if os.path.exists(candidate):
            return candidate
        
        logger.error(f"本地资源未找到: {path}")
        return None

    def _sync_cloud_to_local(self) -> SyncResult:
        try:
            blocks = self.client.list_document_blocks(self.doc_token)
            blocks = [b for b in blocks if b.block_type != 1]
            converter = FeishuToMarkdown(image_downloader=lambda t: self.client.download_image(t, os.path.join(os.path.dirname(self.md_path), "assets", f"{t}.png")))
            md_content = converter.convert(blocks)
            if os.path.exists(self.md_path):
                bak_path = f"{self.md_path}.bak.{self.batch_id}"
                shutil.copy(self.md_path, bak_path)
            with open(self.md_path, "w", encoding="utf-8") as f:
                f.write(md_content)
            return SyncResult.SUCCESS
        except Exception as e:
            logger.error(f"Download failed: {e}"); return SyncResult.ERROR

    def verify_cloud_structure(self):
        logger.debug(f"正在拉取云端结构进行验证 ({self.doc_token})...")
        try:
            blocks = self.client.list_document_blocks(self.doc_token)
            block_map = {b.block_id: b for b in blocks}
            def print_tree(block_id, depth=0):
                b = block_map.get(block_id)
                if not b: return
                indent = "  " * depth
                content = "???"
                try:
                    json_str = lark.JSON.marshal(b)
                    d = json.loads(json_str)
                    for k in ['text', 'heading1', 'heading2', 'heading3', 'heading4', 'heading5', 'heading6', 'heading7', 'heading8', 'heading9', 'bullet', 'ordered', 'todo', 'code']:
                        if k in d and d[k]:
                            els = d[k].get('elements', [])
                            content = "".join([e.get('text_run', {}).get('content', '') for e in els]).strip()
                            break
                except: pass
                logger.debug(f"{indent}- [{b.block_type}] {content}") 
            root = next((b for b in blocks if b.block_type == 1), None)
            if root and root.children:
                for child_id in root.children: print_tree(child_id, 1)
        except Exception as e:
            logger.error(f"Verification failed: {e}")

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
            self.client = FeishuClient(config.FEISHU_APP_ID, config.FEISHU_APP_SECRET, user_access_token=config.FEISHU_USER_ACCESS_TOKEN)
        self.stats = {"created": 0, "updated": 0, "skipped": 0, "failed": 0}
        self._stats_lock = None  # Will be initialized in run()

    def run(self):
        """Run folder synchronization with concurrent file processing."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading
        
        self._stats_lock = threading.Lock()
        
        logger.header(f"开始文件夹同步: {self.local_root} -> {self.cloud_root_token}", icon="🚀")
        
        # Collect all sync tasks first
        sync_tasks = self._collect_sync_tasks(self.local_root, self.cloud_root_token)
        
        if not sync_tasks:
            logger.info("没有需要同步的文件。", icon="✓")
            return
        
        logger.info(f"发现 {len(sync_tasks)} 个文件需要同步，使用 {config.MAX_PARALLEL_WORKERS} 个并行工作线程...", icon="⚡")
        
        # Process sync tasks in parallel
        with ThreadPoolExecutor(max_workers=config.MAX_PARALLEL_WORKERS) as executor:
            futures = {executor.submit(self._execute_sync_task, task): task for task in sync_tasks}
            
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
        
        logger.info(f"同步汇总: 新增 {self.stats['created']}, 更新 {self.stats['updated']}, 跳过 {self.stats['skipped']}, 失败 {self.stats['failed']}", icon="📊")

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
        
        for item in local_items:
            if item.startswith('.') or item == "assets":
                continue
            
            item_path = os.path.join(local_path, item)
            
            if os.path.isdir(item_path):
                # Handle subdirectories
                if item in cloud_map and cloud_map[item].type == "folder":
                    # Recursively collect from existing folder
                    tasks.extend(self._collect_sync_tasks(item_path, cloud_map[item].token))
                else:
                    # Create new folder and recurse
                    new_token = self.client.create_folder(cloud_token, item)
                    if new_token:
                        tasks.extend(self._collect_sync_tasks(item_path, new_token))
                        
            elif item.endswith(".md"):
                doc_name = item[:-3]
                if doc_name in cloud_map and cloud_map[doc_name].type == "docx":
                    tasks.append({
                        "local_path": item_path,
                        "doc_token": cloud_map[doc_name].token,
                        "is_new": False
                    })
                else:
                    # Create new document
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
        
        return tasks

    def _execute_sync_task(self, task: Dict[str, Any]) -> str:
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

