#!/usr/bin/env python3
"""
DocSync CLI - 统一命令行入口
整合配置向导、健康检查、同步执行等功能

用法:
    python scripts/cli.py setup      # 配置向导
    python scripts/cli.py check      # 健康检查
    python scripts/cli.py sync       # 执行同步
    python scripts/cli.py example    # 运行示例
"""

import os
import sys
import json
import argparse
import importlib.util

# 添加项目根目录到路径
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)


# ============================================================
# 通用工具函数
# ============================================================
class Colors:
    OK = '\033[92m'
    WARN = '\033[93m'
    FAIL = '\033[91m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_logo():
    """打印 Logo"""
    print(f"""
{Colors.CYAN}╔═══════════════════════════════════════════╗
║   {Colors.BOLD}DocSync{Colors.END}{Colors.CYAN} - Obsidian → Feishu 同步工具   ║
╚═══════════════════════════════════════════╝{Colors.END}
""")


def ok(msg): print(f"{Colors.OK}✓{Colors.END} {msg}")
def warn(msg): print(f"{Colors.WARN}⚠{Colors.END} {msg}")
def fail(msg): print(f"{Colors.FAIL}✗{Colors.END} {msg}")
def info(msg): print(f"{Colors.CYAN}→{Colors.END} {msg}")


def prompt(msg, default="", required=True):
    """获取用户输入"""
    suffix = f" [{default}]" if default else ""
    while True:
        value = input(f"{msg}{suffix}: ").strip()
        if value:
            return value
        if default:
            return default
        if not required:
            return ""
        warn("此项为必填")


def confirm(msg, default=True):
    """确认提示"""
    hint = "Y/n" if default else "y/N"
    response = input(f"{msg} ({hint}): ").strip().lower()
    if not response:
        return default
    return response in ('y', 'yes', '是')


# ============================================================
# 命令: setup - 快速配置向导
# ============================================================
def cmd_setup(args):
    """快速配置向导"""
    print_logo()
    print("📋 快速配置向导\n")
    
    config_file = "sync_config.json"
    config = {}
    
    # 加载已有配置
    if os.path.exists(config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        info(f"检测到已有配置: {config_file}")
        if not confirm("是否重新配置？", default=False):
            print("\n配置未更改。运行 `python main.py` 开始同步。")
            return 0
    
    print("\n" + "─" * 45)
    print(f" {Colors.BOLD}Step 1: 飞书应用配置{Colors.END}")
    print("─" * 45)
    print("访问 https://open.feishu.cn/app 创建应用\n")
    
    app_id = prompt("App ID (cli_xxx)", config.get("feishu_app_id", ""))
    app_secret = prompt("App Secret", config.get("feishu_app_secret", ""))
    
    print("\n" + "─" * 45)
    print(f" {Colors.BOLD}Step 2: 添加同步任务{Colors.END}")
    print("─" * 45)
    
    tasks = config.get("tasks", [])
    
    while True:
        print(f"\n📝 任务 {len(tasks) + 1}")
        
        note = prompt("任务名称", f"任务{len(tasks) + 1}")
        local = prompt("本地路径 (文件或文件夹)")
        
        while not os.path.exists(local):
            fail(f"路径不存在: {local}")
            local = prompt("本地路径 (文件或文件夹)")
        
        print("\n💡 从飞书 URL 复制 Token: .../folder/[TOKEN] 或 .../docx/[TOKEN]")
        cloud = prompt("云端 Token")
        
        vault = os.path.dirname(local) if os.path.isfile(local) else local
        vault = prompt("Vault 根目录", vault)
        
        tasks.append({
            "note": note,
            "local": local,
            "cloud": cloud,
            "vault_root": vault,
            "enabled": True
        })
        
        ok(f"任务 '{note}' 已添加")
        
        if not confirm("\n继续添加任务？", default=False):
            break
    
    # 保存配置
    config.update({
        "feishu_app_id": app_id,
        "feishu_app_secret": app_secret,
        "feishu_user_access_token": config.get("feishu_user_access_token", ""),
        "feishu_user_refresh_token": config.get("feishu_user_refresh_token", ""),
        "feishu_assets_token": config.get("feishu_assets_token", ""),
        "tasks": tasks
    })
    
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    print("\n" + "═" * 45)
    ok(f"配置已保存到 {config_file}")
    print("═" * 45)
    print("\n下一步: python main.py")
    return 0


# ============================================================
# 命令: check - 健康检查
# ============================================================
def cmd_check(args):
    """健康检查"""
    print_logo()
    print("🔍 健康检查\n")
    
    results = []
    
    # 1. Python 版本
    version = sys.version_info
    passed = version >= (3, 7)
    results.append(("Python 版本", passed, f"{version.major}.{version.minor}"))
    (ok if passed else fail)(f"Python {version.major}.{version.minor}")
    
    # 2. 依赖检查
    deps = {"lark_oapi": "lark-oapi", "dotenv": "python-dotenv", "markdown_it": "markdown-it-py", "keyring": "keyring"}
    all_deps_ok = True
    for mod, pkg in deps.items():
        try:
            importlib.import_module(mod)
            ok(f"{pkg}")
        except ImportError:
            fail(f"{pkg} (pip install {pkg})")
            all_deps_ok = False
    results.append(("依赖包", all_deps_ok, ""))
    
    # 3. 配置文件
    config_file = "sync_config.json"
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            has_id = bool(config.get("feishu_app_id"))
            has_secret = bool(config.get("feishu_app_secret"))
            has_token = bool(config.get("feishu_user_access_token"))
            task_count = len(config.get("tasks", []))
            
            (ok if has_id else fail)(f"App ID {'已配置' if has_id else '未配置'}")
            (ok if has_secret else fail)(f"App Secret {'已配置' if has_secret else '未配置'}")
            (ok if has_token else warn)(f"Access Token {'已授权' if has_token else '待授权'}")
            ok(f"同步任务: {task_count} 个")
            
            results.append(("配置文件", has_id and has_secret, ""))
        except Exception as e:
            fail(f"配置文件错误: {e}")
            results.append(("配置文件", False, str(e)))
    else:
        fail(f"配置文件不存在: {config_file}")
        warn("运行: python scripts/cli.py setup")
        results.append(("配置文件", False, "不存在"))
    
    # 4. 飞书连接
    if results[-1][1]:  # 配置存在才测试连接
        try:
            from src.feishu_client import FeishuClient
            client = FeishuClient(config["feishu_app_id"], config["feishu_app_secret"])
            token = client._get_tenant_access_token()
            (ok if token else fail)(f"API 连接 {'正常' if token else '失败'}")
            results.append(("API 连接", bool(token), ""))
        except Exception as e:
            fail(f"API 连接失败: {e}")
            results.append(("API 连接", False, str(e)))
    
    # 总结
    print("\n" + "─" * 45)
    all_ok = all(r[1] for r in results)
    if all_ok:
        print(f"{Colors.OK}🎉 所有检查通过！{Colors.END}")
    else:
        print(f"{Colors.WARN}⚠ 有问题需要解决{Colors.END}")
    
    return 0 if all_ok else 1


# ============================================================
# 命令: sync - 执行同步
# ============================================================
def cmd_sync(args):
    """执行同步"""
    import subprocess
    
    cmd = [sys.executable, "main.py"]
    
    if args.force:
        cmd.append("--force")
    if args.debug:
        cmd.append("--debug-dump")
    if args.task:
        cmd.extend(["--task", args.task])
    
    return subprocess.call(cmd)


# ============================================================
# 命令: example - 运行示例
# ============================================================
def cmd_example(args):
    """运行示例同步"""
    import subprocess
    
    example_dir = os.path.join(PROJECT_ROOT, "examples", "sample_vault")
    if not os.path.exists(example_dir):
        fail(f"示例目录不存在: {example_dir}")
        return 1
    
    print_logo()
    info(f"示例目录: {example_dir}")
    
    token = args.token or prompt("目标云端 Token", "root")
    
    cmd = [sys.executable, "main.py", example_dir, token, "--force"]
    return subprocess.call(cmd)


# ============================================================
# 主入口
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="DocSync 命令行工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s setup              配置向导
  %(prog)s check              健康检查  
  %(prog)s sync               执行同步
  %(prog)s sync --force       强制覆盖
  %(prog)s example TOKEN      运行示例
"""
    )
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # setup
    setup_parser = subparsers.add_parser("setup", help="配置向导")
    setup_parser.set_defaults(func=cmd_setup)
    
    # check
    check_parser = subparsers.add_parser("check", help="健康检查")
    check_parser.set_defaults(func=cmd_check)
    
    # sync
    sync_parser = subparsers.add_parser("sync", help="执行同步")
    sync_parser.add_argument("--force", "-f", action="store_true", help="强制覆盖")
    sync_parser.add_argument("--debug", "-d", action="store_true", help="调试模式")
    sync_parser.add_argument("--task", "-t", help="指定任务名称")
    sync_parser.set_defaults(func=cmd_sync)
    
    # example
    example_parser = subparsers.add_parser("example", help="运行示例")
    example_parser.add_argument("token", nargs="?", help="目标云端 Token")
    example_parser.set_defaults(func=cmd_example)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
    
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\n\n❌ 已取消")
        return 1


if __name__ == "__main__":
    sys.exit(main())
