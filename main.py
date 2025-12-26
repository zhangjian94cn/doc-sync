import argparse
import json
import os
import traceback
import sys
import warnings
from typing import Optional

# Filter out deprecated pkg_resources warning from third-party libraries
warnings.filterwarnings("ignore", category=UserWarning, module='lark_oapi.ws.pb.google')

from src.sync import SyncManager, FolderSyncManager
from src.converter import MarkdownToFeishu
from src.feishu_client import FeishuClient
from config import FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_USER_ACCESS_TOKEN
import sys

def load_config(config_path):
    if not os.path.exists(config_path):
        return []
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def find_vault_root(path: str) -> Optional[str]:
    """
    Find the Obsidian vault root by looking for .obsidian folder upwards.
    """
    path = os.path.abspath(path)
    if os.path.isfile(path):
        path = os.path.dirname(path)
        
    current = path
    while True:
        if os.path.exists(os.path.join(current, ".obsidian")):
            return current
        parent = os.path.dirname(current)
        if parent == current: # Reached root
            return None
        current = parent

def run_single_task(local_path, cloud_token, force, note="", target_folder=None, vault_root=None):
    """
    Determines whether the task is a folder or file sync and runs the appropriate manager.
    """
    if note:
        print(f"\n=== 📌 处理任务: {note} ===")
    else:
        print(f"\n=== 📌 处理任务: {local_path} -> {cloud_token} ===")
        
    print(f"📍 本地路径: {local_path}")
    print(f"☁️  云端 Token: {cloud_token}")

    # Auto-detect Vault Root if not provided
    if not vault_root:
        vault_root = find_vault_root(local_path)
        if vault_root:
             print(f"🏠 自动检测到 Vault Root: {vault_root}")

    if os.path.isdir(local_path):
        print(f"📂 任务类型: 文件夹同步")
        manager = FolderSyncManager(local_path, cloud_token, force, vault_root=vault_root)
        manager.run()
    else:
        print(f"📄 任务类型: 单文件同步")
        if target_folder:
            print(f"📂 目标文件夹: {target_folder}")
        manager = SyncManager(local_path, cloud_token, force, vault_root=vault_root)
        manager.run()

def main():
    parser = argparse.ArgumentParser(description="Sync Obsidian Markdown to Feishu Doc")
    parser.add_argument("md_path", nargs='?', help="Path to the Obsidian Markdown file or folder")
    parser.add_argument("doc_token", nargs='?', help="Feishu Document/Folder Token")
    parser.add_argument("--force", action="store_true", help="Force upload even if cloud version is newer")
    parser.add_argument("--config", default="sync_config.json", help="Path to sync config file (default: sync_config.json)")
    parser.add_argument("--vault-root", help="Explicitly set the Obsidian Vault Root path (for resolving absolute resource links)")
    
    args = parser.parse_args()
    
    # Init Client
    # Pass USER_ACCESS_TOKEN if available, otherwise it defaults to Tenant Token
    client = FeishuClient(FEISHU_APP_ID, FEISHU_APP_SECRET, user_access_token=FEISHU_USER_ACCESS_TOKEN)
    
    # Mode 1: Single task via CLI args
    if args.md_path and args.doc_token:
        target_folder = None
        try:
            # Try to load default folder from config if available
            tasks = load_config(args.config)
            if tasks and tasks[0].get("cloud"):
                target_folder = tasks[0]["cloud"]
                print(f"⚙️  自动从配置中读取目标文件夹: {target_folder}")
        except:
            pass

        try:
            run_single_task(args.md_path, args.doc_token, args.force, note="CLI Task", target_folder=target_folder, vault_root=args.vault_root)
        except Exception as e:
            print(f"❌ 任务失败: {e}")
            traceback.print_exc()
        return

    # Mode 2: Batch sync via Config file
    print(f"⚙️  未提供参数，正在加载配置文件: {args.config}...")
    tasks = load_config(args.config)
    
    if not tasks:
        print(f"⚠️  未在配置文件中找到任务或文件不存在。")
        print("用法: python3 main.py <local_path> <cloud_token> [--force]")
        print("   或: python3 main.py (使用 sync_config.json)")
        return

    success_count = 0
    total_count = 0

    for task in tasks:
        if not task.get("enabled", True):
            continue
            
        local_path = task.get("local")
        cloud_token = task.get("cloud")
        note = task.get("note", "")
        
        if not local_path or not cloud_token:
            print(f"⚠️  跳过无效任务: {task}")
            continue
            
        total_count += 1
        
        try:
            # Config file tasks default to non-force unless specified in json
            force_sync = args.force or task.get("force", False)
            vault_root = task.get("vault_root") or args.vault_root
            run_single_task(local_path, cloud_token, force_sync, note, vault_root=vault_root)
            success_count += 1
        except Exception as e:
            print(f"❌ 任务失败: {e}")
            traceback.print_exc()
            
    print(f"\n🏁 批量同步完成。成功: {success_count}/{total_count}")

if __name__ == "__main__":
    main()
