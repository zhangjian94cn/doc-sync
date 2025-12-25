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
    def __init__(self, md_path: str, doc_token: str, force: bool = False):
        self.md_path = md_path
        self.doc_token = doc_token
        self.force = force
        self.client = FeishuClient(
            config.FEISHU_APP_ID, 
            config.FEISHU_APP_SECRET
        )
        
    def run(self):
        """
        Main execution flow for file synchronization.
        """
        if not os.path.exists(self.md_path):
            print(f"❌ 错误: 未找到文件: {self.md_path}")
            sys.exit(1)
            
        print(f"📖 正在读取本地文件: {self.md_path}...")
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
        """
        print("🔄 正在将 Markdown 转换为飞书文档块...")
        with open(self.md_path, "r", encoding="utf-8") as f:
            md_text = f.read()
            
        # Define image uploader callback
        def image_uploader(src: str) -> Optional[str]:
            # Resolve path
            # If src is absolute, use it. If relative, join with md_path dir.
            if os.path.isabs(src):
                abs_path = src
            else:
                abs_path = os.path.join(os.path.dirname(self.md_path), src)
            
            if os.path.exists(abs_path):
                return abs_path
            
            print(f"❌ 图片未找到: {abs_path}")
            return None

        converter = MarkdownToFeishu(image_uploader=image_uploader)
        blocks = converter.parse(md_text)
        print(f"✨ 已生成 {len(blocks)} 个文档块。")
        
        print(f"🧹 正在清空云端文档原始内容 ({self.doc_token})...")
        self.client.clear_document(self.doc_token)
        
        print("📤 正在上传新内容...")
        self.client.add_blocks(self.doc_token, blocks)
        
        doc_url = f"https://feishu.cn/docx/{self.doc_token}"
        print(f"✅ 同步完成！文档链接: {doc_url}")


class FolderSyncManager:
    """
    Handles recursive synchronization of a local folder with a Feishu Cloud Folder.
    """
    def __init__(self, local_root: str, cloud_root_token: str, force: bool = False):
        self.local_root = local_root
        self.cloud_root_token = cloud_root_token
        self.force = force
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
                
                print(f"\n" + "-"*50)
                print(f"📄 [{self.processed_files}/{self.total_files}] 处理文件: {item}")
                print("-" * 50)
                
                if doc_name in cloud_map:
                    # Sync
                    c_file = cloud_map[doc_name]
                    if c_file.type == "docx":
                        sync = SyncManager(item_path, c_file.token, self.force)
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
                        sync = SyncManager(item_path, new_token, force=True)
                        sync.run()
