import os
import sys
import time
import shutil
import json
import hashlib
import lark_oapi as lark
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import IntEnum
from urllib.parse import unquote
import difflib

import config
from src.feishu_client import FeishuClient
from src.converter import MarkdownToFeishu, FeishuToMarkdown
from src.utils import pad_center, parse_cloud_time
from src.logger import logger

class SyncResult(IntEnum):
    SUCCESS = 0
    EMPTY_CLOUD = 1
    ERROR = 2

class SyncManager:
    def __init__(self, md_path: str, doc_token: str, force: bool = False, vault_root: str = None, client: FeishuClient = None, batch_id: str = None):
        self.md_path = os.path.abspath(md_path)
        self.doc_token = doc_token
        self.force = force
        self.vault_root = vault_root or os.path.dirname(self.md_path)
        self.batch_id = batch_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if client:
            self.client = client
        else:
            self.client = FeishuClient(
                config.FEISHU_APP_ID, 
                config.FEISHU_APP_SECRET,
                user_access_token=config.FEISHU_USER_ACCESS_TOKEN
            )

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

        if ops_count > 15 or not root_children:
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
        if not path or path.startswith("http"): return None
        
        # URL decode first (e.g., %E4%B8%AD%E6%96%87.png -> 中文.png)
        decoded_path = unquote(path)
        
        real_path = decoded_path
        
        # List of potential base directories to search in
        search_dirs = [
            os.path.dirname(self.md_path),  # Current file directory
            self.vault_root,                # Vault root
            os.path.join(self.vault_root, "assets"), # Common assets folder
            os.path.join(self.vault_root, "attachments"), # Obsidian attachments
            os.path.join(self.vault_root, "resources"),
            os.path.join(self.vault_root, "image"),
            os.path.join(self.vault_root, "images")
        ]

        found = False
        
        # Strategy 1: Check exact path relative to search dirs
        if not os.path.isabs(decoded_path):
            for base_dir in search_dirs:
                candidate = os.path.join(base_dir, decoded_path)
                if os.path.exists(candidate):
                    real_path = candidate
                    found = True
                    break
        
        # Strategy 2: Recursive search in Vault if not found
        # This is expensive but necessary for "shortest path" links in Obsidian
        if not found and not os.path.exists(real_path):
            filename = os.path.basename(decoded_path)
            for root, dirs, files in os.walk(self.vault_root):
                if filename in files:
                    real_path = os.path.join(root, filename)
                    found = True
                    break

        if not os.path.exists(real_path):
            logger.error(f"本地资源未找到: {path} (尝试路径: {real_path})"); return None

        # Return the local path instead of uploading immediately
        # The upload will be handled by add_blocks method
        return real_path

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
    def __init__(self, local_root: str, cloud_root_token: str, force: bool = False, vault_root: str = None, debug: bool = False, client: FeishuClient = None):
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

    def run(self):
        logger.header(f"开始文件夹同步: {self.local_root} -> {self.cloud_root_token}", icon="🚀")
        self._sync_folder(self.local_root, self.cloud_root_token)
        logger.info(f"同步汇总: 新增 {self.stats['created']}, 更新 {self.stats['updated']}, 跳过 {self.stats['skipped']}, 失败 {self.stats['failed']}", icon="📊")

    def _sync_folder(self, local_path, cloud_token):
        try: local_items = os.listdir(local_path)
        except: return
        cloud_files = self.client.list_folder_files(cloud_token)
        cloud_map = {f.name: f for f in cloud_files}
        for item in local_items:
            if item.startswith('.') or item == "assets": continue
            item_path = os.path.join(local_path, item)
            if os.path.isdir(item_path):
                if item in cloud_map and cloud_map[item].type == "folder":
                    self._sync_folder(item_path, cloud_map[item].token)
                else:
                    new_token = self.client.create_folder(cloud_token, item)
                    if new_token: self._sync_folder(item_path, new_token)
            elif item.endswith(".md"):
                doc_name = item[:-3]
                if doc_name in cloud_map and cloud_map[doc_name].type == "docx":
                    sync = SyncManager(item_path, cloud_map[doc_name].token, self.force, vault_root=self.vault_root, client=self.client, batch_id=self.batch_id)
                    sync.run(debug=self.debug)
                    self.stats["updated"] += 1
                else:
                    new_token = self.client.create_docx(cloud_token, doc_name)
                    if new_token:
                        sync = SyncManager(item_path, new_token, force=True, vault_root=self.vault_root, client=self.client, batch_id=self.batch_id)
                        sync.run(debug=self.debug)
                        self.stats["created"] += 1
                    else: self.stats["failed"] += 1
