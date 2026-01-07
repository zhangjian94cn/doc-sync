import os
import sys
import shutil
import glob
from datetime import datetime

def parse_backup_timestamp(filename):
    """
    Parses timestamp from backup filename.
    Supports both new format (YYYYMMDD_HHMMSS) and old format (Unix timestamp).
    """
    parts = filename.split(".bak.")
    if len(parts) < 2: return None, None
    
    ts_str = parts[-1]
    
    # Try new format: 20240107_123000
    if "_" in ts_str and len(ts_str) == 15:
        try:
            dt = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
            return ts_str, dt
        except:
            pass
            
    # Try old format: Unix timestamp (digits)
    if ts_str.isdigit():
        try:
            ts = int(ts_str)
            dt = datetime.fromtimestamp(ts)
            return ts_str, dt
        except:
            pass
            
    return None, None

def scan_backups(target_path):
    """
    Scans for all .bak.* files in the target directory (recursive).
    Returns a dict grouped by batch_id/timestamp.
    """
    abs_target = os.path.abspath(target_path)
    
    # If target is a file, just look for its backups
    if os.path.isfile(abs_target):
        search_path = os.path.dirname(abs_target)
        target_file_name = os.path.basename(abs_target)
    else:
        search_path = abs_target
        target_file_name = None

    batches = {} # Key: timestamp_str, Value: {time: datetime, files: []}

    for root, dirs, files in os.walk(search_path):
        for file in files:
            if ".bak." in file:
                # Check if it's a backup of our target file (if specified)
                if target_file_name and not file.startswith(target_file_name + ".bak."):
                    continue
                
                full_path = os.path.join(root, file)
                batch_id, dt = parse_backup_timestamp(file)
                
                if batch_id and dt:
                    if batch_id not in batches:
                        batches[batch_id] = {"time": dt, "id": batch_id, "files": []}
                    
                    # Original file path (remove .bak.xxx)
                    original_path = full_path.rsplit(".bak.", 1)[0]
                    
                    # Calculate relative path for display if possible
                    try:
                        rel_path = os.path.relpath(original_path, search_path)
                    except:
                        rel_path = os.path.basename(original_path)

                    batches[batch_id]["files"].append({
                        "backup_path": full_path,
                        "original_path": original_path,
                        "rel_path": rel_path,
                        "size": os.path.getsize(full_path)
                    })

    return batches

def print_batch_log(batches):
    sorted_batches = sorted(batches.values(), key=lambda x: x["time"], reverse=True)
    
    print(f"\n📚 发现 {len(sorted_batches)} 个备份版本 (按时间倒序):\n")
    print(f"    {'序号':<4} {'备份时间':<22} {'批次ID':<20} {'文件内容'}")
    print("-" * 100)
    
    for i, batch in enumerate(sorted_batches):
        file_count = len(batch['files'])
        # Show first 2 files + etc
        display_files = [f['rel_path'] for f in batch['files'][:2]]
        files_str = ", ".join(display_files)
        if file_count > 2:
            files_str += f" 等 {file_count} 个文件"
        elif file_count == 0:
            files_str = "无文件"
            
        print(f"    [{i+1}]  {batch['time'].strftime('%Y-%m-%d %H:%M:%S')}   {batch['id']:<20} {files_str}")
        
    return sorted_batches

def restore_batch(batch):
    print(f"\n🚀 准备恢复版本: {batch['time']} (批次: {batch['id']})")
    print(f"📦 包含 {len(batch['files'])} 个文件:")
    
    for f in batch['files']:
        print(f"  - {f['rel_path']}")

    confirm = input("\n⚠️  确认还原吗？这将覆盖当前文件。(y/n): ").lower()
    if confirm != 'y':
        print("操作取消。")
        return

    success_count = 0
    for f in batch['files']:
        src = f['backup_path']
        dst = f['original_path']
        try:
            # Optional: Backup current state before overwrite?
            # Maybe too much noise for batch restore.
            shutil.copy(src, dst)
            # print(f"  ✅ 已还原: {os.path.basename(dst)}")
            success_count += 1
        except Exception as e:
            print(f"  ❌ 还原失败 {os.path.basename(dst)}: {e}")

    print(f"\n✨ 还原完成! 成功: {success_count}/{len(batch['files'])}")

def run_restore_interactive(target_path):
    if not os.path.exists(target_path):
        print(f"错误: 路径不存在 {target_path}")
        return

    print(f"🔍 正在扫描备份: {os.path.abspath(target_path)} ...")
    batches = scan_backups(target_path)
    
    if not batches:
        print("未找到任何备份文件。")
        return

    sorted_batches = print_batch_log(batches)
    
    print("-" * 60)
    print("    [q] 退出")
    
    while True:
        choice = input("\n请选择要还原的版本序号 (输入数字): ").strip().lower()
        if choice == 'q':
            break
            
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(sorted_batches):
                restore_batch(sorted_batches[idx])
                break
            else:
                print("❌ 无效的序号")
        else:
            print("❌ 请输入数字或 q")
