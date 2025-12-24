import argparse
import json
import os
from src.sync import SyncManager

def load_config(config_path):
    if not os.path.exists(config_path):
        return []
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def main():
    parser = argparse.ArgumentParser(description="Sync Obsidian Markdown to Feishu Doc")
    parser.add_argument("md_path", nargs='?', help="Path to the Obsidian Markdown file (Optional if using config)")
    parser.add_argument("doc_token", nargs='?', help="Feishu Document Token (Optional if using config)")
    parser.add_argument("--force", action="store_true", help="Force upload even if cloud version is newer")
    parser.add_argument("--config", default="sync_config.json", help="Path to sync config file (default: sync_config.json)")
    
    args = parser.parse_args()
    
    # Mode 1: Single file sync via CLI args
    if args.md_path and args.doc_token:
        print(f"--- Syncing Single File: {args.md_path} ---")
        manager = SyncManager(args.md_path, args.doc_token, args.force)
        manager.run()
        return

    # Mode 2: Batch sync via Config file
    print(f"No arguments provided. Loading config from {args.config}...")
    tasks = load_config(args.config)
    
    if not tasks:
        print(f"No tasks found in {args.config} or file does not exist.")
        print("Usage: python3 main.py <md_path> <doc_token> [--force]")
        print("   Or: python3 main.py (uses sync_config.json)")
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
            print(f"Skipping invalid task: {task}")
            continue
            
        total_count += 1
        print(f"\n=== Processing Task {total_count}: {note} ===")
        print(f"Local: {local_path}")
        print(f"Cloud: {cloud_token}")
        
        try:
            # Config file tasks default to non-force unless specified in json (optional feature)
            # or we can inherit the global --force flag
            force_sync = args.force or task.get("force", False)
            
            manager = SyncManager(local_path, cloud_token, force_sync)
            manager.run()
            success_count += 1
        except Exception as e:
            print(f"Task failed: {e}")
            
    print(f"\nBatch Sync Completed. Success: {success_count}/{total_count}")

if __name__ == "__main__":
    main()
