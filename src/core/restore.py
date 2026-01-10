import os
import sys
import shutil
import glob
import difflib
from datetime import datetime
from src.logger import logger

def parse_backup_timestamp(filename):
    """
    Parses timestamp from backup filename.
    Supports format: YYYYMMDD_HHMMSS
    """
    parts = filename.split(".bak.")
    if len(parts) < 2: return None, None

    ts_str = parts[-1]

    # Try format: 20240107_123000
    if "_" in ts_str and len(ts_str) == 15:
        try:
            dt = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
            return ts_str, dt
        except:
            pass

    # Fallback: Try Unix timestamp (digits) for backward compatibility
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

def format_time_ago(dt):
    """Format time difference in human-readable format (like git)"""
    now = datetime.now()
    diff = now - dt

    seconds = diff.total_seconds()
    if seconds < 60:
        return f"{int(seconds)} 秒前"
    elif seconds < 3600:
        return f"{int(seconds / 60)} 分钟前"
    elif seconds < 86400:
        return f"{int(seconds / 3600)} 小时前"
    elif seconds < 604800:
        return f"{int(seconds / 86400)} 天前"
    elif seconds < 2592000:
        return f"{int(seconds / 604800)} 周前"
    else:
        return f"{int(seconds / 2592000)} 个月前"

def print_batch_log(batches):
    """Print batch log in git-log style"""
    sorted_batches = sorted(batches.values(), key=lambda x: x["time"], reverse=True)

    logger.header(f"发现 {len(sorted_batches)} 个备份版本", icon="📚")

    for i, batch in enumerate(sorted_batches):
        file_count = len(batch['files'])
        time_str = batch['time'].strftime('%Y-%m-%d %H:%M:%S')
        time_ago = format_time_ago(batch['time'])

        # Print commit-like header
        logger.info(f"[{i+1}] commit {batch['id']}", icon="📦")
        logger.info(f"    Date:  {time_str} ({time_ago})")
        logger.info(f"    Files: {file_count} 个文件")

        # Show first 3 files
        for f in batch['files'][:3]:
            size_kb = f['size'] / 1024
            logger.info(f"           - {f['rel_path']} ({size_kb:.1f} KB)")

        if file_count > 3:
            logger.info(f"           ... 还有 {file_count - 3} 个文件")

        print()  # Empty line between commits

    return sorted_batches

def show_batch_detail(batch):
    """Show detailed information of a batch (like git show)"""
    logger.header(f"批次详情: {batch['id']}", icon="🔍")
    logger.info(f"时间: {batch['time'].strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"共 {len(batch['files'])} 个文件:\n")

    for f in batch['files']:
        size_kb = f['size'] / 1024
        print(f"  📄 {f['rel_path']}")
        print(f"     大小: {size_kb:.1f} KB")
        print(f"     备份: {f['backup_path']}")
        print(f"     原始: {f['original_path']}")
        print()

def show_diff(backup_file, current_file):
    """Show diff between backup and current file"""
    if not os.path.exists(current_file):
        logger.warning(f"当前文件不存在: {current_file}")
        return

    try:
        with open(backup_file, 'r', encoding='utf-8') as f:
            backup_lines = f.readlines()
    except:
        logger.error("无法读取备份文件（可能不是文本文件）")
        return

    try:
        with open(current_file, 'r', encoding='utf-8') as f:
            current_lines = f.readlines()
    except:
        logger.error("无法读取当前文件（可能不是文本文件）")
        return

    diff = difflib.unified_diff(
        backup_lines,
        current_lines,
        fromfile=f'备份版本: {os.path.basename(backup_file)}',
        tofile=f'当前版本: {os.path.basename(current_file)}',
        lineterm=''
    )

    has_diff = False
    for line in diff:
        has_diff = True
        if line.startswith('+++') or line.startswith('---'):
            logger.info(line)
        elif line.startswith('+'):
            print(f"\033[32m{line}\033[0m")  # Green
        elif line.startswith('-'):
            print(f"\033[31m{line}\033[0m")  # Red
        elif line.startswith('@@'):
            print(f"\033[36m{line}\033[0m")  # Cyan
        else:
            print(line)

    if not has_diff:
        logger.success("文件内容相同，无差异")

def restore_batch(batch):
    """Restore a batch of files"""
    logger.header(f"准备恢复版本: {batch['id']}", icon="🚀")
    logger.info(f"时间: {batch['time'].strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"包含 {len(batch['files'])} 个文件:\n")

    for f in batch['files']:
        size_kb = f['size'] / 1024
        print(f"  - {f['rel_path']} ({size_kb:.1f} KB)")

    print()
    confirm = input("⚠️  确认还原吗？这将覆盖当前文件 (y/n): ").lower()
    if confirm != 'y':
        logger.info("操作取消")
        return

    success_count = 0
    for f in batch['files']:
        src = f['backup_path']
        dst = f['original_path']
        try:
            # Backup current state before overwrite (optional)
            shutil.copy(src, dst)
            success_count += 1
        except Exception as e:
            logger.error(f"还原失败 {os.path.basename(dst)}: {e}")

    logger.success(f"还原完成！成功: {success_count}/{len(batch['files'])}")

def print_help():
    """Print help message"""
    print("""
可用命令:
  <数字>       - 还原指定序号的版本
  show <数字>  - 显示指定版本的详细信息
  diff <数字>  - 显示指定版本与当前文件的差异
  log          - 重新显示版本列表
  help         - 显示此帮助信息
  q/quit       - 退出
""")

def run_restore_interactive(target_path):
    """Interactive restore interface (git-like)"""
    if not os.path.exists(target_path):
        logger.error(f"路径不存在: {target_path}")
        return

    logger.info(f"正在扫描备份: {os.path.abspath(target_path)} ...", icon="🔍")
    batches = scan_backups(target_path)

    if not batches:
        logger.warning("未找到任何备份文件")
        return

    sorted_batches = print_batch_log(batches)

    logger.info("提示: 输入 'help' 查看可用命令", icon="💡")

    while True:
        try:
            choice = input("\n>>> ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print()
            break

        if not choice:
            continue

        if choice in ('q', 'quit', 'exit'):
            break

        if choice == 'help':
            print_help()
            continue

        if choice == 'log':
            print()
            print_batch_log(batches)
            continue

        parts = choice.split()
        cmd = parts[0]

        # Parse index
        if cmd.isdigit():
            idx = int(cmd) - 1
            if 0 <= idx < len(sorted_batches):
                restore_batch(sorted_batches[idx])
                break
            else:
                logger.error("无效的序号")
            continue

        # show <index>
        if cmd == 'show' and len(parts) == 2 and parts[1].isdigit():
            idx = int(parts[1]) - 1
            if 0 <= idx < len(sorted_batches):
                show_batch_detail(sorted_batches[idx])
            else:
                logger.error("无效的序号")
            continue

        # diff <index>
        if cmd == 'diff' and len(parts) == 2 and parts[1].isdigit():
            idx = int(parts[1]) - 1
            if 0 <= idx < len(sorted_batches):
                batch = sorted_batches[idx]
                if len(batch['files']) == 1:
                    f = batch['files'][0]
                    logger.info(f"对比文件: {f['rel_path']}\n")
                    show_diff(f['backup_path'], f['original_path'])
                else:
                    logger.info("批次包含多个文件，显示第一个文件的差异:\n")
                    f = batch['files'][0]
                    logger.info(f"文件: {f['rel_path']}\n")
                    show_diff(f['backup_path'], f['original_path'])
            else:
                logger.error("无效的序号")
            continue

        logger.error("无效的命令，输入 'help' 查看帮助")

