import os
import sys
import time
import shutil
from datetime import datetime
from typing import Optional
from enum import IntEnum

import config
from src.feishu_client import FeishuClient
from src.converter import MarkdownToFeishu, FeishuToMarkdown

class SyncResult(IntEnum):
    SUCCESS = 0
    EMPTY_CLOUD = 1
    ERROR = 2

class SyncManager:
    """
    Handles synchronization of a single Markdown file with a Feishu Document.
    """
    def __init__(self, md_path: str, doc_token: str, force: bool = False, vault_root: str = None):
        self.md_path = md_path
        self.doc_token = doc_token
        self.force = force
        self.vault_root = vault_root or os.path.dirname(md_path)
        self.client = FeishuClient(
            config.FEISHU_APP_ID, 
            config.FEISHU_APP_SECRET
        )
        
    def run(self):
        """
        Main execution flow for file synchronization.
        """
        print(f"\n{'-'*30}")
        print(f"📄 任务: {os.path.basename(self.md_path)}")
        print(f"{'-'*30}")

        if not os.path.exists(self.md_path):
            print(f"❌ 错误: 未找到文件: {self.md_path}")
            sys.exit(1)
            
        print(f"📖 读取本地文件: {self.md_path}...")
        local_mtime = os.path.getmtime(self.md_path)
        print(f"🕒 本地文件修改时间: {datetime.fromtimestamp(local_mtime)}")
        
        # Check cloud status
        print(f"🔍 正在检查云端文档状态 ({self.doc_token})...")
        file_info = self.client.get_file_info(self.doc_token)
        
        should_upload = True
        
        if not file_info:
            print("❌ 错误: 无法获取云端文档元数据。")
            if not self.force:
                print("🚫 操作终止。请使用 --force 参数强制继续。")
                sys.exit(1)
        else:
            cloud_mtime = self._parse_cloud_time(file_info.latest_modify_time)
            print(f"☁️ 云端文档修改时间: {datetime.fromtimestamp(cloud_mtime)}")
            
            if cloud_mtime > local_mtime:
                print("\n⚠️ 警告: 云端版本 比 本地版本 新！")
                if self.force:
                    print("💪 已启用 --force 参数，将强制覆盖。")
                    should_upload = True
                else:
                    print("🔄 开始反向同步 (云端 -> 本地)...")
                    result = self._sync_cloud_to_local()
                    if result == SyncResult.SUCCESS:
                        print("✅ 反向同步完成。")
                        should_upload = False
                    elif result == SyncResult.EMPTY_CLOUD:
                        print("ℹ️ 云端文档为空，准备上传本地内容。")
                        should_upload = True
                    else:
                        print("❌ 反向同步失败，操作终止。")
                        sys.exit(1)
            else:
                print("✅ 本地版本较新或一致，准备同步到云端。")
                should_upload = True

        if should_upload:
            self._sync_local_to_cloud()

    def _parse_cloud_time(self, timestamp) -> float:
        """
        Heuristic to detect if timestamp is in milliseconds or seconds.
        """
        ts = int(timestamp)
        if ts > 10000000000:
            return ts / 1000.0
        return float(ts)

    def _sync_cloud_to_local(self) -> SyncResult:
        """
        Downloads cloud content and overwrites local file.
        Returns SyncResult enum.
        """
        print(f"📥 正在下载云端内容并覆盖本地文件: {self.md_path}...")
        
        try:
            blocks = self.client.get_all_blocks(self.doc_token)
            if not blocks:
                print("⚠️ 警告: 云端文档为空，无需下载。")
                return SyncResult.EMPTY_CLOUD
            
            # Define image downloader callback
            def image_downloader(token: str) -> Optional[str]:
                # Assets folder: ./assets
                assets_dir = os.path.join(os.path.dirname(self.md_path), "assets")
                filename = f"{token}.png" # Default to png
                save_path = os.path.join(assets_dir, filename)
                
                if self.client.download_image(token, save_path):
                    # Return relative path for markdown
                    return os.path.join("assets", filename)
                return None

            converter = FeishuToMarkdown(image_downloader=image_downloader)
            md_content = converter.convert(blocks)
            
            # Backup
            backup_path = f"{self.md_path}.bak.{int(time.time())}"
            shutil.copy2(self.md_path, backup_path)
            print(f"📦 已创建本地备份: {backup_path}")
            
            with open(self.md_path, "w", encoding="utf-8") as f:
                f.write(md_content)
                
            print(f"✅ 成功使用云端内容覆盖本地文件。")
            return SyncResult.SUCCESS
            
        except Exception as e:
            print(f"❌ 反向同步过程中发生错误: {e}")
            import traceback
            traceback.print_exc()
            return SyncResult.ERROR

    def _sync_local_to_cloud(self):
        """
        Reads local file, converts to blocks, and uploads to Feishu.
        Implements incremental sync (Diff) strategy.
        """
        import hashlib
        import difflib
        import json
        
        print("🔄 正在将 Markdown 转换为飞书文档块...")
        with open(self.md_path, "r", encoding="utf-8") as f:
            md_text = f.read()
            
        # Define image uploader callback
        def image_uploader(src: str) -> Optional[str]:
            # Resolve path strategies
            
            # 1. Check if it's already an absolute path and exists
            if os.path.isabs(src) and os.path.exists(src):
                return src
                
            # 2. Check relative to MD file (Standard Markdown)
            path_rel_md = os.path.join(os.path.dirname(self.md_path), src)
            if os.path.exists(path_rel_md):
                return path_rel_md
            
            # 3. Check relative to Vault Root (Obsidian Style)
            # If vault_root is set, try resolving from there
            if self.vault_root:
                path_rel_vault = os.path.join(self.vault_root, src)
                if os.path.exists(path_rel_vault):
                    return path_rel_vault
                
                # 4. Check in 'assets' folder in Vault Root (Common convention)
                path_assets = os.path.join(self.vault_root, "assets", os.path.basename(src))
                if os.path.exists(path_assets):
                    return path_assets
            
            print(f"❌ 图片未找到: {src}")
            return None

        converter = MarkdownToFeishu(image_uploader=image_uploader)
        local_blocks = converter.parse(md_text)
        print(f"✨ 本地已生成 {len(local_blocks)} 个文档块。")
        
        # --- Incremental Sync Logic ---
        
        # 1. Fetch Cloud Blocks
        print(f"🔍 获取云端现有内容以进行比对...")
        cloud_blocks_raw = self.client.get_all_blocks(self.doc_token)
        
        # 2. Hash Calculation Helper
        def get_block_hash(block_data, is_cloud_obj=False):
            """
            Compute a hash for block content to compare equality.
            Ignores IDs, revision info, and irrelevant styles.
            """
            # This is a simplified hashing strategy. 
            # Ideally we should canonicalize the content structure.
            # For now, we dump specific fields to JSON string and hash it.
            
            content_fingerprint = {}
            
            if is_cloud_obj:
                # Map Cloud Object to simplified dict
                b_type = block_data.block_type
                content_fingerprint["type"] = b_type
                
                # Extract content based on type
                # This mapping must match what MarkdownToFeishu produces
                attr_map = {
                    2: "text", 3: "heading1", 4: "heading2", 5: "heading3",
                    6: "heading4", 7: "heading5", 8: "heading6", 9: "heading7",
                    10: "heading8", 11: "heading9", 12: "bullet", 13: "ordered",
                    14: "code", 22: "todo", 23: "file", 27: "image"
                }
                
                attr_name = attr_map.get(b_type)
                if attr_name and hasattr(block_data, attr_name):
                    attr_obj = getattr(block_data, attr_name)
                    if attr_obj:
                        # Improved serialization for SDK objects
                        if hasattr(attr_obj, "to_dict"):
                             content_fingerprint["content"] = attr_obj.to_dict()
                        elif hasattr(attr_obj, "__dict__"):
                             # Some SDK objects might not have to_dict but have __dict__
                             # Filter private attributes
                             content_fingerprint["content"] = {k: v for k, v in attr_obj.__dict__.items() if not k.startswith('_')}
                        else:
                             # Fallback
                             content_fingerprint["content"] = str(attr_obj)
                
                # Special handling for Image Block to make it comparable
                # Cloud returns: {token: "...", width: ..., height: ...}
                # Local has: {token: "path/to/local/file", ...}
                # They will NEVER match if we compare token directly.
                if b_type == 27:
                    # We can't compare token. So we ignore token in hash?
                    # But if image CHANGED, we need to detect it.
                    # Since we can't map Cloud Token -> Local Path, we assume:
                    # If everything else matches (position in doc, maybe surrounding text?), it's the same?
                    # No, that's risky.
                    
                    # Alternative: We mark all Image blocks as "Same" (Equal) tentatively?
                    # No, then we never update images.
                    
                    # Current constraint: We CANNOT know if a cloud image matches a local image without extra metadata.
                    # Hack: For now, we EXCLUDE image token from hash. 
                    # This means: "If there is an image here, and there was an image here, we assume it's the same."
                    # This fixes the re-upload issue, BUT means changing the image file (keeping same name/location) won't trigger update.
                    # To fix THAT, user needs to delete the block or we need metadata.
                    # Let's try ignoring token for Image blocks.
                    
                    if isinstance(content_fingerprint.get("content"), dict):
                        content_fingerprint["content"].pop("token", None)
                        
            else:
                # Local Block Dict
                b_type = block_data.get("block_type")
                content_fingerprint["type"] = b_type
                
                # Extract content key
                # Keys in local_blocks are like "text", "heading1", etc.
                for k, v in block_data.items():
                    if k != "block_type" and k != "alt":
                        # Use deep copy to avoid modifying original data when popping token later
                        if isinstance(v, dict):
                            content_fingerprint["content"] = v.copy()
                        else:
                            content_fingerprint["content"] = v
                        break
                
                # Special handling for Image Block (Local)
                if b_type == 27:
                    # Remove token (path) from hash to match cloud behavior
                    if isinstance(content_fingerprint.get("content"), dict):
                        content_fingerprint["content"].pop("token", None)
            
            # Normalize: sort keys, remove None, handle objects, remove defaults
            def clean_dict(d, is_cloud=False):
                if hasattr(d, "to_dict"):
                    d = d.to_dict()
                elif hasattr(d, "__dict__"):
                    d = {k: v for k, v in d.__dict__.items() if not k.startswith('_')}

                if isinstance(d, dict):
                    new_d = {}
                    for k, v in d.items():
                        # 1. Ignore "style" field (block style, alignment, etc.)
                        if k == "style":
                            continue
                        
                        # 2. Ignore "text_element_style" if all values are false/None
                        # Or better: Recursively clean it.
                        
                        clean_v = clean_dict(v, is_cloud)
                        
                        # 3. Filter false/None values in text_element_style or general
                        if v is None:
                            continue
                        
                        # Specific logic for text_element_style to remove default false values
                        if k == "text_element_style" and isinstance(clean_v, dict):
                            # Remove keys with False values
                            clean_v = {sk: sv for sk, sv in clean_v.items() if sv}
                            if not clean_v:
                                continue # Skip empty style
                        
                        if clean_v == {} or clean_v == [] or clean_v is None:
                             # Skip empty dicts/lists? 
                             # Be careful. Local might have empty dict for some reason?
                             # Image content in local became empty dict after popping token.
                             pass

                        new_d[k] = clean_v
                    
                    # 4. Special handling for Code Block content merging
                    # Cloud splits code into lines in elements. Local has one text_run.
                    # We can't easily merge here without knowing parent type.
                    # But we can try to normalize "elements" if it's a list of text_runs.
                    
                    return new_d
                
                if isinstance(d, list):
                    return [clean_dict(x, is_cloud) for x in d]
                
                return d

            # Pre-process content to handle Code Block merging and Image emptying
            def preprocess_content(block_type, content_dict):
                # 1. Image / File: Empty it
                if block_type == 27 or block_type == 23:
                    return {}
                
                # 2. Code: Merge elements text
                if block_type == 14:
                    if "elements" in content_dict:
                        full_text = ""
                        for el in content_dict["elements"]:
                            if "text_run" in el and "content" in el["text_run"]:
                                full_text += el["text_run"]["content"]
                        return {"elements": [{"text_run": {"content": full_text}}]}
                        
                return content_dict

            clean_fp = clean_dict(content_fingerprint, is_cloud_obj)
            
            if isinstance(clean_fp.get("content"), dict):
                clean_fp["content"] = preprocess_content(clean_fp.get("type"), clean_fp["content"])
            
            # Remove empty fields from top level
            if isinstance(clean_fp, dict):
                 clean_fp = {k: v for k, v in clean_fp.items() if v}

            return hashlib.md5(json.dumps(clean_fp, sort_keys=True, default=lambda x: str(x)).encode('utf-8')).hexdigest()

        # 3. Compute Hashes
        cloud_hashes = [get_block_hash(b, is_cloud_obj=True) for b in cloud_blocks_raw]
        local_hashes = [get_block_hash(b, is_cloud_obj=False) for b in local_blocks]
        
        # 4. Calculate Diff
        sm = difflib.SequenceMatcher(None, cloud_hashes, local_hashes)
        opcodes = sm.get_opcodes()
        
        # Analysis of operations
        # opcodes: list of (tag, i1, i2, j1, j2)
        # tag: 'replace', 'delete', 'insert', 'equal'
        
        ops_count = 0
        diff_strategy_feasible = True
        
        for tag, i1, i2, j1, j2 in opcodes:
            if tag != 'equal':
                ops_count += 1
        
        # Threshold: If changes are too fragmented (> 10 chunks of changes), fallback to Full Sync
        # Because we don't have Batch Update, lots of small updates are slow.
        # Batch Insert/Delete are supported though.
        # But 'replace' = delete + insert.
        
        if ops_count == 0:
            print("✅ 文档内容一致，无需更新。")
            return

        print(f"📊 差异分析: 发现 {ops_count} 处变更。")
        
        if ops_count > 10 or len(cloud_blocks_raw) == 0:
            print("⚠️ 变更较多或为空文档，使用全量覆盖模式以确保速度...")
            self.client.clear_document(self.doc_token)
            self.client.add_blocks(self.doc_token, local_blocks)
        else:
            print("⚡️ 使用增量同步模式...")
            
            # Helper to pad string with display width awareness
            def pad_center(text, width):
                # Calculate display width: ASCII=1, Others(CJK)=2
                display_len = 0
                for char in text:
                    if ord(char) > 127:
                        display_len += 2
                    else:
                        display_len += 1
                
                padding = width - display_len
                if padding <= 0:
                    return text
                
                left = padding // 2
                right = padding - left
                return " " * left + text + " " * right

            # Table Header
            # Define column widths (Display Width)
            w_type = 8
            w_cloud = 12
            w_local = 12
            
            # 1. Print Diff Table (Plan)
            print(f"  ┌{'─'*w_type}┬{'─'*w_cloud}┬{'─'*w_local}┐")
            print(f"  │{pad_center('类型', w_type)}│{pad_center('云端块索引', w_cloud)}│{pad_center('本地块索引', w_local)}│")
            print(f"  ├{'─'*w_type}┼{'─'*w_cloud}┼{'─'*w_local}┤")
            
            # Collect operations to execute
            ops_to_exec = []
            
            for tag, i1, i2, j1, j2 in reversed(opcodes):
                if tag == 'equal':
                    continue
                
                # Print readable diff
                action_map = {'delete': '🔴 删除', 'insert': '🟢 插入', 'replace': '🟡 替换'}
                icon = action_map.get(tag, tag)
                
                # Format ranges
                c_range = f"{i1:02d}-{i2:02d}"
                l_range = f"{j1:02d}-{j2:02d}"
                
                # Print row
                print(f"  │{pad_center(icon, w_type)}│{pad_center(c_range, w_cloud)}│{pad_center(l_range, w_local)}│")
                
                ops_to_exec.append((tag, i1, i2, j1, j2))
            
            # Table Footer
            print(f"  └{'─'*w_type}┴{'─'*w_cloud}┴{'─'*w_local}┘")
            
            # 2. Execute Operations
            print("🚀 开始执行同步操作...")
            for tag, i1, i2, j1, j2 in ops_to_exec: # Order is already reversed
                if tag == 'delete':
                    # Cloud blocks [i1:i2] need to be deleted.
                    self.client.delete_blocks_by_index(self.doc_token, i1, i2)
                    
                elif tag == 'insert':
                    # Insert local blocks [j1:j2] at cloud index i1.
                    blocks_to_insert = local_blocks[j1:j2]
                    self.client.add_blocks(self.doc_token, blocks_to_insert, index=i1)
                    
                elif tag == 'replace':
                    # Replace = Delete + Insert
                    # 1. Delete old
                    self.client.delete_blocks_by_index(self.doc_token, i1, i2)
                    # 2. Insert new at i1
                    blocks_to_insert = local_blocks[j1:j2]
                    self.client.add_blocks(self.doc_token, blocks_to_insert, index=i1)

        doc_url = f"https://feishu.cn/docx/{self.doc_token}"
        print(f"✅ 同步完成！文档链接: {doc_url}")


class FolderSyncManager:
    """
    Handles recursive synchronization of a local folder with a Feishu Cloud Folder.
    """
    def __init__(self, local_root: str, cloud_root_token: str, force: bool = False, vault_root: str = None):
        self.local_root = local_root
        self.cloud_root_token = cloud_root_token
        self.force = force
        self.vault_root = vault_root or local_root
        self.client = FeishuClient(
            config.FEISHU_APP_ID, 
            config.FEISHU_APP_SECRET
        )
        
        # Stats
        self.total_files = 0
        self.processed_files = 0

        if self.cloud_root_token == "root":
            print("🔍 正在解析根目录(我的空间) Token...")
            root_token = self.client.get_root_folder_token()
            if root_token:
                print(f"✅ 已解析根目录 Token: {root_token}")
                self.cloud_root_token = root_token
            else:
                print("❌ 错误: 无法解析根目录 Token。")
                sys.exit(1)

    def run(self):
        """
        Main execution flow for folder synchronization.
        """
        if not os.path.exists(self.local_root):
            print(f"❌ 错误: 未找到本地文件夹: {self.local_root}")
            sys.exit(1)
        
        print(f"📊 正在统计文件数量...")
        self.total_files = self._count_files(self.local_root)
        print(f"📦 发现 {self.total_files} 个 Markdown 文件。")

        print(f"🚀 开始文件夹同步: {self.local_root} -> {self.cloud_root_token}")
        self._sync_folder(self.local_root, self.cloud_root_token)
        print("\n" + "="*50)
        print(f"🎉 文件夹同步完成。共处理 {self.processed_files}/{self.total_files} 个文件。")

    def _count_files(self, path: str) -> int:
        count = 0
        for root, dirs, files in os.walk(path):
            # Skip hidden folders
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for file in files:
                if file.endswith(".md") and not file.startswith('.'):
                    count += 1
        return count

    def _sync_folder(self, local_path: str, cloud_token: str):
        """
        Recursively syncs files and subfolders.
        """
        # 1. List cloud files in this folder
        # Only print scanning log if it's the root or we want verbose logs
        # print(f"🔍 正在扫描云端文件夹: {cloud_token}...")
        cloud_files = self.client.list_folder_files(cloud_token)
        # Map: name -> (token, type)
        cloud_map = {f.name: f for f in cloud_files}

        # 2. Iterate local files
        items = sorted(os.listdir(local_path))
        for item in items:
            if item.startswith('.'): continue # Skip hidden
            
            item_path = os.path.join(local_path, item)
            
            if os.path.isdir(item_path):
                # Handle Folder
                if item in cloud_map:
                    # Check if it is a folder
                    if cloud_map[item].type == "folder":
                        # print(f"📂 进入子文件夹: {item}")
                        self._sync_folder(item_path, cloud_map[item].token)
                    else:
                        print(f"⚠️ 警告: 名称冲突。本地是文件夹，但云端是 {cloud_map[item].type}。跳过: {item}。")
                else:
                    # Create folder
                    print(f"📁 正在创建云端文件夹: {item}")
                    new_token = self.client.create_folder(cloud_token, item)
                    if new_token:
                        self._sync_folder(item_path, new_token)
            
            elif item.endswith(".md"):
                self.processed_files += 1
                doc_name = item[:-3] # Remove .md
                
                print(f"\n" + "="*50)
                print(f"📂 [{self.processed_files}/{self.total_files}] 处理文件: {item}")
                print("=" * 50)
                
                if doc_name in cloud_map:
                    # Sync
                    c_file = cloud_map[doc_name]
                    if c_file.type == "docx":
                        sync = SyncManager(item_path, c_file.token, self.force, vault_root=self.vault_root)
                        sync.run()
                    else:
                        print(f"⚠️ 警告: 名称冲突。本地是 .md 文件，但云端是 {c_file.type}。跳过。")
                else:
                    # Create Doc
                    print(f"📝 正在创建云端文档: {doc_name}")
                    new_token = self.client.create_docx(cloud_token, doc_name)
                    if new_token:
                        print(f"✨ 已创建文档 {doc_name} ({new_token}), 开始同步内容...")
                        
                        # Newly created doc needs force upload to bypass timestamp check
                        sync = SyncManager(item_path, new_token, force=True, vault_root=self.vault_root)
                        sync.run()
