import argparse
import json
import os
import traceback
import sys
import warnings
from typing import Optional

# Filter out deprecated pkg_resources warning from third-party libraries
warnings.filterwarnings("ignore", category=UserWarning, module='lark_oapi.ws.pb.google')

from doc_sync.sync import SyncManager, FolderSyncManager
from doc_sync.converter import MarkdownToFeishu
from doc_sync.feishu_client import FeishuClient
from doc_sync.logger import logger
from doc_sync.config import FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_USER_ACCESS_TOKEN


def _ensure_client(user_token=None):
    """Create an authenticated FeishuClient, handling token refresh as needed."""
    if not user_token:
        user_token = FEISHU_USER_ACCESS_TOKEN
    client = FeishuClient(FEISHU_APP_ID, FEISHU_APP_SECRET, user_access_token=user_token)
    return client, user_token

def load_config(config_path: str) -> list:
    """
    Load sync tasks from configuration file.
    
    Args:
        config_path: Path to the JSON configuration file
        
    Returns:
        List of task configurations, empty list if loading fails
    """
    if not os.path.exists(config_path):
        return []
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Support both new dict format and old list format
            if isinstance(data, dict):
                return data.get("tasks", [])
            elif isinstance(data, list):
                return data
            return []
    except json.JSONDecodeError as e:
        logger.error(f"配置文件 JSON 格式错误: {e}")
        return []
    except IOError as e:
        logger.error(f"读取配置文件失败: {e}")
        return []

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

def run_single_task(local_path, cloud_token, force, overwrite=False, note="", target_folder=None, vault_root=None, debug=False, client: FeishuClient = None):
    """
    Determines whether the task is a folder or file sync and runs the appropriate manager.
    """
    if note:
        logger.header(f"处理任务: {note}", icon="📌")
    else:
        logger.header(f"处理任务: {local_path} -> {cloud_token}", icon="📌")
        
    logger.info(f"本地路径: {local_path}", icon="📍")
    logger.info(f"云端 Token: {cloud_token}", icon="☁️ ")

    # Auto-detect Vault Root if not provided
    if not vault_root:
        vault_root = find_vault_root(local_path)
        if vault_root:
             logger.info(f"自动检测到 Vault Root: {vault_root}", icon="🏠")

    # Ensure client
    if not client:
        client = FeishuClient(FEISHU_APP_ID, FEISHU_APP_SECRET, user_access_token=FEISHU_USER_ACCESS_TOKEN)

    if os.path.isdir(local_path):
        logger.info(f"任务类型: 文件夹同步", icon="📂")
        manager = FolderSyncManager(local_path, cloud_token, force, overwrite=overwrite, vault_root=vault_root, debug=debug, client=client)
        manager.run()
    else:
        # Check if cloud_token is a folder or doc
        
        doc_token = cloud_token
        is_folder = False
        
        # Check type - Try folder first
        logger.debug(f"正在检测 Token 类型: {cloud_token}", icon="🔍")
        file_info = client.get_file_info(cloud_token, obj_type="folder")
        
        if file_info and file_info.doc_type == "folder":
            is_folder = True
            logger.success("识别为文件夹", icon="📂")
        else:
            # Fallback to check if it's a docx
            file_info_doc = client.get_file_info(cloud_token, obj_type="docx")
            if file_info_doc:
                logger.success(f"识别为文档 (Type: {file_info_doc.doc_type})", icon="📄")
                is_folder = False
            else:
                logger.warning("无法识别 Token 类型，将尝试作为文档处理...")
                is_folder = False
            
        if is_folder:
            logger.info(f"检测到目标 Token 是文件夹，正在查找/创建同名文档...", icon="📂")
            doc_name = os.path.basename(local_path)
            if doc_name.endswith(".md"): doc_name = doc_name[:-3]
            
            files = client.list_folder_files(cloud_token)
            target_doc = next((f for f in files if f.name == doc_name and f.type == "docx"), None)
            
            if target_doc:
                doc_token = target_doc.token
                logger.success(f"找到现有文档: {doc_name} ({doc_token})", icon="✅")
            else:
                logger.info(f"创建新文档: {doc_name}", icon="📝")
                new_token = client.create_docx(cloud_token, doc_name)
                if new_token:
                    doc_token = new_token
                    force = True # Force upload for new doc
                else:
                    logger.error("创建文档失败，中止。")
                    return

        logger.info(f"任务类型: 单文件同步", icon="📄")
        if target_folder:
            logger.info(f"目标文件夹: {target_folder}", icon="📂")
        manager = SyncManager(local_path, doc_token, force, overwrite=overwrite, vault_root=vault_root, client=client)
        manager.run(debug=debug)

def main():
    # Route to bitable subcommand if first arg is 'bitable'
    if len(sys.argv) > 1 and sys.argv[1] == "bitable":
        bitable_main()
        return
    
    # Route to live sync subcommand if first arg is 'live'
    if len(sys.argv) > 1 and sys.argv[1] == "live":
        live_main()
        return
    
    parser = argparse.ArgumentParser(
        description="DocSync: 双向同步 Obsidian (Markdown) 与 飞书云文档",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
示例:
  1. 单文件/文件夹同步:
     docsync /path/to/note.md <doc_token>
     docsync /path/to/folder <folder_token>

  2. 使用配置文件批量同步 (默认读取 sync_config.json):
     docsync

  3. 多维表格操作:
     docsync bitable push data.csv --app-token bascnXXX
     docsync bitable pull --app-token bascnXXX --table-id tblXXX -o output.csv

  4. 还原备份:
     docsync --restore /path/to/folder_or_file

  5. 清理旧备份:
     docsync --clean
"""
    )
    parser.add_argument("md_path", nargs='?', help="本地 Markdown 文件或文件夹路径")
    parser.add_argument("doc_token", nargs='?', help="飞书云文档或文件夹的 Token")
    parser.add_argument("--force", action="store_true", help="强制上传（即使云端更新，也会覆盖云端）")
    parser.add_argument("--overwrite", action="store_true", help="强制全量覆盖（不进行增量比对，直接清空云端文档并重新上传）")
    parser.add_argument("--config", default="sync_config.json", help="指定配置文件路径 (默认: sync_config.json)")
    parser.add_argument("--vault-root", help="显式指定 Obsidian 仓库根目录 (用于解析绝对路径的资源引用)")
    parser.add_argument("--clean", action="store_true", help="清理模式：递归删除所有备份文件 (*.bak.*)")
    parser.add_argument("--restore", help="还原模式：交互式选择并还原备份版本")
    parser.add_argument("--debug-dump", action="store_true", help="调试模式：同步后拉取并打印云端结构")
    
    args = parser.parse_args()
    
    # Show help if no args provided and not using config implicitly
    if len(sys.argv) == 1 and not os.path.exists(args.config):
        parser.print_help()
        return
    
    # Mode: Restore
    if args.restore:
        from doc_sync.core.restore import run_restore_interactive
        run_restore_interactive(args.restore)
        return

    # Mode: Clean Backups
    if args.clean:
        target_path = args.md_path or "."
        # If no path arg, try to use the first local path from config
        if not args.md_path and os.path.exists(args.config):
            try:
                tasks = load_config(args.config)
                if tasks and tasks[0].get("local"):
                    target_path = tasks[0]["local"]
            except Exception as e:
                logger.debug(f"加载配置失败: {e}")
                
        logger.info(f"正在扫描并清理备份文件: {os.path.abspath(target_path)}")
        count = 0
        total_size = 0
        
        for root, dirs, files in os.walk(target_path):
            for file in files:
                # Match pattern: *.bak.<digits> or just *.bak
                # Standardize to handle .bak and .bak.TIMESTAMP
                if ".bak" in file:
                    # Additional check to be safe
                    is_bak = False
                    if file.endswith(".bak"):
                        is_bak = True
                    elif ".bak." in file:
                        parts = file.rsplit(".bak.", 1)
                        if len(parts) == 2 and parts[1].isdigit():
                            is_bak = True
                        elif len(parts) == 2 and "_" in parts[1]: # Handle TIMESTAMP with underscore like 20260113_094716
                             # simple check if it looks like timestamp
                             is_bak = True
                    
                    if is_bak:
                        file_path = os.path.join(root, file)
                        try:
                            s = os.path.getsize(file_path)
                            os.remove(file_path)
                            logger.info(f"  删除: {file}")
                            count += 1
                            total_size += s
                        except Exception as e:
                            logger.error(f"  删除失败 {file}: {e}")
        
        logger.success(f"清理完成。共删除 {count} 个文件，释放 {total_size/1024:.2f} KB。")
        return

    # Check Auth and Login if needed
    user_token = FEISHU_USER_ACCESS_TOKEN
    
    # Init Client (Temporary for validation)
    client = FeishuClient(FEISHU_APP_ID, FEISHU_APP_SECRET, user_access_token=user_token)
    
    # Validate and Auto-Refresh Token
    if user_token:
        # logger.debug("检查 Token 有效性...")
        try:
            from lark_oapi.api.authen.v1.model import GetUserInfoRequest
            req = GetUserInfoRequest.builder().build()
            # We need to construct request option manually or use client's internal helper if exposed
            # FeishuClient._get_request_option is protected but accessible
            opt = client._get_request_option()
            
            resp = client.client.authen.v1.user_info.get(req, opt)
            if not resp.success():
                # 99991677: Token Expired
                # 20005: Invalid Access Token (e.g. revoked or malformed)
                if resp.code == 99991677 or resp.code == 20005: 
                    logger.warning(f"Token 失效 (Code: {resp.code})，尝试自动刷新...")
                    from doc_sync.core.auth import FeishuAuthenticator
                    auth = FeishuAuthenticator()
                    new_token = auth.refresh()
                    if new_token:
                        user_token = new_token
                        from doc_sync import config as src_config
                        src_config.FEISHU_USER_ACCESS_TOKEN = new_token
                        # Re-init Client with new token
                        client = FeishuClient(FEISHU_APP_ID, FEISHU_APP_SECRET, user_access_token=user_token)
                        logger.success("Token 自动刷新成功")
                    else:
                        logger.warning("Refresh Token 已过期，正在自动打开浏览器重新登录...")
                        new_token = auth.login()
                        if new_token:
                            user_token = new_token
                            from doc_sync import config as src_config
                            src_config.FEISHU_USER_ACCESS_TOKEN = new_token
                            client = FeishuClient(FEISHU_APP_ID, FEISHU_APP_SECRET, user_access_token=user_token)
                            logger.success("重新登录成功")
                        else:
                            logger.error("登录失败，请检查网络或手动重试。")
                            sys.exit(1)
                else:
                    # Other errors (e.g. permission denied for user_info) shouldn't block main flow if token is valid?
                    # But 99991677 is specific to expiry.
                    # Let's print warning but continue, maybe sync permissions are fine.
                    logger.warning(f"Token 校验警告: {resp.code} {resp.msg}")
        except Exception as e:
            logger.warning(f"Token 校验异常: {e}")
            import traceback
            traceback.print_exc()

    if not user_token and sys.stdin.isatty():
        logger.warning("未检测到 User Access Token (推荐用于解决权限问题)。")
        # Check if we should prompt
        # For simplicity, let's just hint user to use setup script or auto login here?
        # Let's try auto login integration.
        try:
            choice = input("是否立即登录飞书以获取用户权限? (y/n) [y]: ").lower()
            if choice in ('', 'y'):
                from doc_sync.core.auth import FeishuAuthenticator
                auth = FeishuAuthenticator()
                new_token = auth.login()
                if new_token:
                    user_token = new_token
                    # Update config module in memory is tricky if imported as from config import ...
                    # But we passed user_token to FeishuClient below, so it's fine for this run.
                    from doc_sync import config
                    config.FEISHU_USER_ACCESS_TOKEN = user_token # Update global config
        except KeyboardInterrupt:
            logger.info("\n操作取消")
            return

    # Init Client
    # Pass USER_ACCESS_TOKEN if available, otherwise it defaults to Tenant Token
    client = FeishuClient(FEISHU_APP_ID, FEISHU_APP_SECRET, user_access_token=user_token)

    # Note: We need to ensure SyncManager also uses this token.
    # SyncManager currently imports from doc_sync.config directly.
    # So we MUST update config module.
    from doc_sync import config as src_config
    src_config.FEISHU_USER_ACCESS_TOKEN = user_token
    
    # Mode 1: Single task via CLI args
    if args.md_path and args.doc_token:
        target_folder = None
        try:
            # Try to load default folder from config if available
            tasks = load_config(args.config)
            if tasks and tasks[0].get("cloud"):
                target_folder = tasks[0]["cloud"]
                logger.debug(f"自动从配置中读取目标文件夹: {target_folder}")
        except:
            pass

        try:
            run_single_task(args.md_path, args.doc_token, args.force, overwrite=args.overwrite, note="CLI Task", target_folder=target_folder, vault_root=args.vault_root, debug=args.debug_dump, client=client)
        except Exception as e:
            logger.error(f"任务失败: {e}")
            traceback.print_exc()
        return

    # Mode 2: Batch sync via Config file
    logger.info(f"未提供参数，正在加载配置文件: {args.config}...", icon="⚙️ ")
    tasks = load_config(args.config)
    
    if not tasks:
        logger.warning(f"未在配置文件中找到任务或文件不存在。")
        print("用法: docsync <local_path> <cloud_token> [--force]")
        print("   或: docsync (使用 sync_config.json)")
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
            logger.warning(f"跳过无效任务: {task}")
            continue
            
        total_count += 1
        
        try:
            # Config file tasks default to non-force unless specified in json
            force_sync = args.force or task.get("force", False)
            overwrite_sync = args.overwrite or task.get("overwrite", False)
            vault_root = task.get("vault_root") or args.vault_root
            run_single_task(local_path, cloud_token, force_sync, overwrite=overwrite_sync, note=note, target_folder=task.get("target_folder"), vault_root=vault_root, debug=args.debug_dump, client=client)
            success_count += 1
        except Exception as e:
            logger.error(f"任务失败: {e}")
            traceback.print_exc()
            
    logger.header(f"批量同步完成。成功: {success_count}/{total_count}", icon="🏁")


def bitable_main():
    """CLI entry point for Bitable (多维表格) operations."""
    parser = argparse.ArgumentParser(
        prog="docsync bitable",
        description="DocSync Bitable: 同步本地数据与飞书多维表格",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
示例:
  1. 上传 CSV 到多维表格:
     docsync bitable push data.csv --app-token bascnXXX

  2. 从多维表格下载到 CSV:
     docsync bitable pull --app-token bascnXXX --table-id tblXXX -o output.csv

  3. 增量同步 (默认):
     docsync bitable push data.csv --app-token bascnXXX --table-id tblXXX --key-field "名称"

  4. 全量覆盖同步:
     docsync bitable push data.csv --app-token bascnXXX --table-id tblXXX --overwrite

  5. 使用配置文件批量同步:
     docsync bitable sync
"""
    )
    
    subparsers = parser.add_subparsers(dest="action", help="操作类型")
    
    # Push: Local → Cloud
    push_parser = subparsers.add_parser("push", help="上传本地数据到飞书多维表格")
    push_parser.add_argument("source", help="本地数据文件路径 (CSV/JSON/Markdown)")
    push_parser.add_argument("--app-token", required=True, help="多维表格 App Token")
    push_parser.add_argument("--table-id", help="目标数据表 ID (留空则自动创建)")
    push_parser.add_argument("--table-name", help="数据表名称 (创建新表时使用)")
    push_parser.add_argument("--key-field", help="用于增量同步的唯一标识字段名")
    push_parser.add_argument("--overwrite", action="store_true", help="全量覆盖模式 (清空后重新上传)")
    
    # Pull: Cloud → Local  
    pull_parser = subparsers.add_parser("pull", help="从飞书多维表格下载数据到本地")
    pull_parser.add_argument("--app-token", required=True, help="多维表格 App Token")
    pull_parser.add_argument("--table-id", required=True, help="数据表 ID")
    pull_parser.add_argument("-o", "--output", required=True, help="输出文件路径 (CSV/JSON)")
    pull_parser.add_argument("--format", choices=["csv", "json"], help="输出格式 (默认根据扩展名)")
    
    # Sync: from config file
    sync_parser = subparsers.add_parser("sync", help="使用配置文件同步多维表格")
    sync_parser.add_argument("--config", default="sync_config.json", help="配置文件路径")
    
    # Info: show app info
    info_parser = subparsers.add_parser("info", help="查看多维表格信息")
    info_parser.add_argument("--app-token", required=True, help="多维表格 App Token")
    
    args = parser.parse_args(sys.argv[2:])  # Skip 'docsync bitable'
    
    if not args.action:
        parser.print_help()
        return
    
    from doc_sync.sync.bitable_sync import BitableSyncManager
    
    client, user_token = _ensure_client()
    
    if args.action == "push":
        logger.header("多维表格同步: 上传", icon="⬆️")
        logger.info(f"数据源: {args.source}", icon="📄")
        
        manager = BitableSyncManager(
            client=client,
            app_token=args.app_token,
            table_id=args.table_id,
            table_name=args.table_name,
            key_field=args.key_field,
            overwrite=args.overwrite,
        )
        result = manager.push(args.source)
        logger.info(str(result))
        
    elif args.action == "pull":
        logger.header("多维表格同步: 下载", icon="⬇️")
        
        manager = BitableSyncManager(
            client=client,
            app_token=args.app_token,
            table_id=args.table_id,
        )
        result = manager.pull(args.output, output_format=args.format)
        logger.info(str(result))
        
    elif args.action == "sync":
        logger.header("多维表格批量同步", icon="🔄")
        config_path = args.config
        tasks = load_config(config_path)
        bitable_tasks = [t for t in tasks if t.get("type") == "bitable" and t.get("enabled", True)]
        
        if not bitable_tasks:
            logger.warning("配置文件中没有启用的多维表格任务")
            return
        
        for task in bitable_tasks:
            note = task.get("note", task.get("local", "Unknown"))
            logger.header(f"处理任务: {note}", icon="📌")
            
            manager = BitableSyncManager(
                client=client,
                app_token=task["app_token"],
                table_id=task.get("table_id"),
                table_name=task.get("table_name"),
                key_field=task.get("key_field"),
                overwrite=task.get("overwrite", False),
            )
            
            direction = task.get("sync_direction", "local_to_cloud")
            if direction == "local_to_cloud":
                result = manager.push(task["local"])
            elif direction == "cloud_to_local":
                result = manager.pull(task["local"])
            else:
                logger.warning(f"不支持的同步方向: {direction}")
                continue
            
            logger.info(str(result))
        
    elif args.action == "info":
        info = client.bitable_get_app_info(args.app_token)
        if info:
            logger.info(f"多维表格: {info.get('name', 'Unknown')}")
            tables = client.bitable_list_tables(args.app_token)
            for t in tables:
                fields = client.bitable_list_fields(args.app_token, t['table_id'])
                records = client.bitable_list_records(args.app_token, t['table_id'], page_size=1)
                logger.info(f"  📋 {t['name']} ({t['table_id']}): {len(fields)} 字段")
        else:
            logger.error("获取多维表格信息失败")


def live_main():
    """CLI entry point for Live Sync (实时协同) mode."""
    parser = argparse.ArgumentParser(
        prog="docsync live",
        description="DocSync Live: 实时协同编辑飞书文档（双向同步 + Block 级别锁）",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
示例:
  使用配置文件中的默认文档 (自动双向同步):
    docsync live

  指定文档 Token 和本地文件:
    docsync live --doc-token doxcnXXXXXX --local /path/to/note.md

  指定端口和轮询间隔:
    docsync live --doc-token doxcnXXXXXX --port 9000 --poll-interval 5
"""
    )
    parser.add_argument("--doc-token", default=None, help="飞书文档 Token (不指定则从 sync_config.json 读取)")
    parser.add_argument("--local", default=None, help="本地 .md 文件路径 (启用双向实时同步，不指定则从 config 自动匹配)")
    parser.add_argument("--port", type=int, default=8765, help="WebSocket 服务器端口 (默认: 8765)")
    parser.add_argument("--host", default="localhost", help="WebSocket 服务器地址 (默认: localhost)")
    parser.add_argument("--poll-interval", type=float, default=3.0, help="飞书 API 轮询间隔秒数 (默认: 3.0)")
    parser.add_argument("--config", default="sync_config.json", help="配置文件路径 (默认: sync_config.json)")
    
    args = parser.parse_args(sys.argv[2:])  # Skip 'docsync live'
    
    # Resolve doc_token and local_path: CLI arg > config file
    doc_token = args.doc_token
    local_path = args.local
    vault_root = None
    
    if not doc_token:
        tasks = load_config(args.config)
        for task in tasks:
            if task.get("enabled", True) and task.get("cloud"):
                doc_token = task["cloud"]
                logger.info(f"从配置文件读取文档 Token: {doc_token}", icon="📄")
                # Also resolve local_path from the same task if not specified
                if not local_path and task.get("local"):
                    local_path = task["local"]
                    logger.info(f"从配置文件读取本地路径: {local_path}", icon="📝")
                break
        if not doc_token:
            logger.error("未指定 --doc-token，且配置文件中无可用任务。")
            parser.print_help()
            sys.exit(1)
    
    # Resolve vault_root for local_path
    if local_path:
        local_path = os.path.abspath(local_path)
        vault_root = find_vault_root(local_path)
        if vault_root:
            logger.info(f"Vault Root: {vault_root}", icon="🏠")
    
    # Ensure token
    user_token = FEISHU_USER_ACCESS_TOKEN
    if not user_token:
        logger.error("未找到 User Access Token，请先配置或登录。")
        logger.info("提示: 运行 docsync 主命令进行登录，或在 sync_config.json 中配置 Token。")
        sys.exit(1)
    
    # Validate token
    client = FeishuClient(FEISHU_APP_ID, FEISHU_APP_SECRET, user_access_token=user_token)
    try:
        from lark_oapi.api.authen.v1.model import GetUserInfoRequest
        req = GetUserInfoRequest.builder().build()
        opt = client._get_request_option()
        resp = client.client.authen.v1.user_info.get(req, opt)
        if not resp.success():
            if resp.code in (99991677, 20005):
                logger.warning(f"Token 失效 (Code: {resp.code})，尝试自动刷新...")
                from doc_sync.core.auth import FeishuAuthenticator
                auth = FeishuAuthenticator()
                new_token = auth.refresh()
                if new_token:
                    user_token = new_token
                    from doc_sync import config as src_config
                    src_config.FEISHU_USER_ACCESS_TOKEN = new_token
                    client = FeishuClient(FEISHU_APP_ID, FEISHU_APP_SECRET, user_access_token=user_token)
                    logger.success("Token 自动刷新成功")
                else:
                    logger.error("Token 刷新失败，请重新登录。")
                    sys.exit(1)
    except Exception as e:
        logger.warning(f"Token 校验异常: {e}")
    
    # Detect token type and determine sync mode
    logger.info(f"正在检测 Token 类型: {doc_token}", icon="🔍")
    file_info = client.get_file_info(doc_token, obj_type="folder")
    
    is_folder_mode = False
    folder_token = None
    
    if file_info and file_info.doc_type == "folder":
        logger.info("检测到文件夹 Token", icon="📂")
        
        # In folder mode: keep the folder token, watch the entire local folder
        is_folder_mode = True
        folder_token = doc_token
        
        # Ensure we have a local folder path for folder mode
        if not local_path:
            tasks = load_config(args.config)
            for task in tasks:
                if task.get("cloud") == doc_token and task.get("enabled", True):
                    local_path = task.get("local")
                    break
        
        if local_path and os.path.isdir(local_path):
            logger.info(f"文件夹模式: 监听 {local_path} 下所有 .md 文件变更", icon="📁")
        elif local_path and os.path.isfile(local_path):
            # local is a file but cloud is a folder — use single file mode
            is_folder_mode = False
            logger.info(f"本地路径是文件，使用单文件模式: {local_path}", icon="📄")
        else:
            logger.warning("未找到有效的本地文件夹路径，文件夹模式将仅监听变更")
    else:
        logger.info("检测为文档 Token，直接使用。", icon="📄")
    
    if not local_path:
        logger.warning("未指定本地路径，仅启用 WebSocket 服务（不启用双向文件同步）", icon="⚠️")
    
    # Start the live sync server
    from doc_sync.live.live_server import run_live_server
    run_live_server(
        app_id=FEISHU_APP_ID,
        app_secret=FEISHU_APP_SECRET,
        user_access_token=user_token,
        doc_token=doc_token,
        host=args.host,
        port=args.port,
        poll_interval=args.poll_interval,
        local_path=local_path,
        vault_root=vault_root,
        is_folder_mode=is_folder_mode,
    )


if __name__ == "__main__":
    main()
