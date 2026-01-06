import os
import sys
import time
import shutil
from datetime import datetime
from typing import Optional
from enum import IntEnum
from urllib.parse import unquote
import difflib

import config
from src.feishu_client import FeishuClient
from src.converter import MarkdownToFeishu, FeishuToMarkdown
from src.utils import calculate_block_hash, pad_center, parse_cloud_time

class SyncResult(IntEnum):
    SUCCESS = 0
    EMPTY_CLOUD = 1
    ERROR = 2

class SyncManager:
    """
    Handles synchronization of a single Markdown file with a Feishu Document.
    """
    # Cache for vault asset index: { vault_root: { filename: full_path } }
    _asset_index_cache = {}

    def __init__(self, md_path: str, doc_token: str, force: bool = False, vault_root: str = None):
        self.md_path = md_path
        self.doc_token = doc_token
        self.force = force
        self.vault_root = vault_root or os.path.dirname(md_path)
        self.client = FeishuClient(
            config.FEISHU_APP_ID, 
            config.FEISHU_APP_SECRET,
            user_access_token=config.FEISHU_USER_ACCESS_TOKEN
        )

    def _get_asset_path_from_index(self, filename: str) -> Optional[str]:
        """
        Look up file path in the vault-wide asset index.
        """
        if not self.vault_root:
            return None
            
        # Initialize cache if needed
        if self.vault_root not in SyncManager._asset_index_cache:
            print(f"🔍 正在建立 Vault 资源索引 (首次运行): {self.vault_root} ...")
            asset_map = {}
            for root, dirs, files in os.walk(self.vault_root):
                # Skip hidden folders
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                for f in files:
                    if f.startswith('.'): continue
                    # Index media and typical attachments
                    if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', 
                                         '.pdf', '.mp4', '.mov', '.avi', '.mkv', '.zip', '.docx', '.xlsx', '.pptx')):
                        asset_map[f] = os.path.join(root, f)
            
            print(f"📚 索引完成，共 {len(asset_map)} 个资源文件。")
            SyncManager._asset_index_cache[self.vault_root] = asset_map
            
        return SyncManager._asset_index_cache[self.vault_root].get(filename)
        
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
            cloud_mtime = parse_cloud_time(file_info.latest_modify_time)
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
                if not os.path.exists(assets_dir):
                    os.makedirs(assets_dir)
                    
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
        print("🔄 正在将 Markdown 转换为飞书文档块...")
        with open(self.md_path, "r", encoding="utf-8") as f:
            md_text = f.read()
            
        # Define image uploader callback
        def image_uploader(src: str) -> Optional[str]:
            # Decode URL encoded chars (e.g. %20 -> space)
            src = unquote(src)

            # Resolve path strategies
            
            # 1. Check if it's already an absolute path and exists
            if os.path.isabs(src) and os.path.exists(src):
                return src
                
            # 2. Check relative to MD file (Standard Markdown)
            path_rel_md = os.path.join(os.path.dirname(self.md_path), src)
            if os.path.exists(path_rel_md):
                return path_rel_md
            
            # 3. Check relative to Vault Root (Obsidian Style)
            if self.vault_root:
                path_rel_vault = os.path.join(self.vault_root, src)
                if os.path.exists(path_rel_vault):
                    return path_rel_vault
                
                # 4. Check in 'assets' folder in Vault Root (Common convention)
                path_assets = os.path.join(self.vault_root, "assets", os.path.basename(src))
                if os.path.exists(path_assets):
                    return path_assets

            # 5. Last Resort: Vault-wide search (Obsidian fuzzy link)
            filename = os.path.basename(src)
            path_from_index = self._get_asset_path_from_index(filename)
            if path_from_index and os.path.exists(path_from_index):
                 return path_from_index
            
            print(f"❌ 图片未找到: {src}")
            return None

        converter = MarkdownToFeishu(image_uploader=image_uploader)
        local_blocks = converter.parse(md_text)
        print(f"✨ 本地已生成 {len(local_blocks)} 个文档块。")
        
        # --- Incremental Sync Logic ---
        
        # 1. Fetch Cloud Blocks
        print(f"🔍 获取云端现有内容以进行比对...")
        cloud_blocks_raw = self.client.get_all_blocks(self.doc_token)
        
        # 2. Compute Hashes
        cloud_hashes = [calculate_block_hash(b, is_cloud_obj=True) for b in cloud_blocks_raw]
        local_hashes = [calculate_block_hash(b, is_cloud_obj=False) for b in local_blocks]
        
        # 3. Calculate Diff
        sm = difflib.SequenceMatcher(None, cloud_hashes, local_hashes)
        opcodes = sm.get_opcodes()
        
        ops_count = 0
        for tag, i1, i2, j1, j2 in opcodes:
            if tag != 'equal':
                ops_count += 1
        
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
            
            # Table Header
            w_type = 8
            w_cloud = 12
            w_local = 12
            
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
                
                c_range = f"{i1:02d}-{i2:02d}"
                l_range = f"{j1:02d}-{j2:02d}"
                
                print(f"  │{pad_center(icon, w_type)}│{pad_center(c_range, w_cloud)}│{pad_center(l_range, w_local)}│")
                
                ops_to_exec.append((tag, i1, i2, j1, j2))
            
            print(f"  └{'─'*w_type}┴{'─'*w_cloud}┴{'─'*w_local}┘")
            
            print("🚀 开始执行同步操作...")
            for tag, i1, i2, j1, j2 in ops_to_exec: # Order is already reversed
                if tag == 'delete':
                    self.client.delete_blocks_by_index(self.doc_token, i1, i2)
                elif tag == 'insert':
                    blocks_to_insert = local_blocks[j1:j2]
                    self.client.add_blocks(self.doc_token, blocks_to_insert, index=i1)
                elif tag == 'replace':
                    self.client.delete_blocks_by_index(self.doc_token, i1, i2)
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
            config.FEISHU_APP_SECRET,
            user_access_token=config.FEISHU_USER_ACCESS_TOKEN
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
        cloud_files = self.client.list_folder_files(cloud_token)
        # Map: name -> (token, type)
        cloud_map = {f.name: f for f in cloud_files}

        items = sorted(os.listdir(local_path))
        for item in items:
            if item.startswith('.'): continue # Skip hidden
            
            item_path = os.path.join(local_path, item)
            
            if os.path.isdir(item_path):
                # Handle Folder
                if item in cloud_map:
                    if cloud_map[item].type == "folder":
                        self._sync_folder(item_path, cloud_map[item].token)
                    else:
                        print(f"⚠️ 警告: 名称冲突。本地是文件夹，但云端是 {cloud_map[item].type}。跳过: {item}。")
                else:
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
