import os
import sys
import time
import shutil
from datetime import datetime
from typing import Optional
import config
from src.feishu_client import FeishuClient
from src.converter import MarkdownToFeishu, FeishuToMarkdown

class SyncManager:
    def __init__(self, md_path: str, doc_token: str, force: bool = False):
        self.md_path = md_path
        self.doc_token = doc_token
        self.force = force
        self.client = FeishuClient(
            config.FEISHU_APP_ID, 
            config.FEISHU_APP_SECRET
        )
        
    def run(self):
        if not os.path.exists(self.md_path):
            print(f"Error: File not found: {self.md_path}")
            sys.exit(1)
            
        print(f"Reading {self.md_path}...")
        local_mtime = os.path.getmtime(self.md_path)
        print(f"Local file modified: {datetime.fromtimestamp(local_mtime)}")
        
        # Check cloud status
        print(f"Checking access to document {self.doc_token}...")
        file_info = self.client.get_file_info(self.doc_token)
        
        should_upload = True
        
        if not file_info:
            print("Error: Cannot access document info (metadata).")
            if not self.force:
                print("Aborting. Use --force to proceed anyway.")
                sys.exit(1)
        else:
            cloud_mtime = self._parse_cloud_time(file_info.latest_modify_time)
            print(f"Cloud file modified: {datetime.fromtimestamp(cloud_mtime)}")
            
            if cloud_mtime > local_mtime:
                print("\nWARNING: Cloud version is NEWER than local file!")
                if self.force:
                    print("Proceeding with overwrite due to --force flag.")
                    should_upload = True
                else:
                    print("Initiating Reverse Sync (Cloud -> Local)...")
                    if self._sync_cloud_to_local():
                        print("Reverse sync completed.")
                        should_upload = False
                    else:
                        print("Reverse sync failed. Aborting.")
                        sys.exit(1)
            else:
                print("Local version is newer or equal. Proceeding with sync.")
                should_upload = True

        if should_upload:
            self._sync_local_to_cloud()

    def _parse_cloud_time(self, timestamp) -> float:
        # Heuristic to detect ms vs seconds
        ts = int(timestamp)
        if ts > 10000000000:
            return ts / 1000.0
        return float(ts)

    def _sync_cloud_to_local(self) -> bool:
        print(f"Downloading cloud content to overwrite {self.md_path}...")
        
        try:
            blocks = self.client.get_all_blocks(self.doc_token)
            if not blocks:
                print("Warning: Cloud document is empty. Nothing to download.")
                return False
                
            converter = FeishuToMarkdown()
            md_content = converter.convert(blocks)
            
            # Backup
            backup_path = f"{self.md_path}.bak.{int(time.time())}"
            shutil.copy2(self.md_path, backup_path)
            print(f"Backed up local file to {backup_path}")
            
            with open(self.md_path, "w", encoding="utf-8") as f:
                f.write(md_content)
                
            print(f"Successfully overwritten {self.md_path} with cloud content.")
            return True
            
        except Exception as e:
            print(f"Error during reverse sync: {e}")
            return False

    def _sync_local_to_cloud(self):
        print("Converting Markdown to Feishu Blocks...")
        with open(self.md_path, "r", encoding="utf-8") as f:
            md_text = f.read()
            
        converter = MarkdownToFeishu()
        blocks = converter.parse(md_text)
        print(f"Generated {len(blocks)} blocks.")
        
        print(f"Clearing existing content in document {self.doc_token}...")
        self.client.clear_document(self.doc_token)
        
        print("Uploading new content...")
        self.client.add_blocks(self.doc_token, blocks)
        
        print("Sync complete!")
