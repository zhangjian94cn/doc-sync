#!/usr/bin/env python3
"""
DocSync 健康检查脚本 - Health Check
检查配置、依赖和连接是否正常
"""

import os
import sys
import json
import importlib

def print_header(title):
    """打印标题"""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print('=' * 60)

def print_check(name, status, message=""):
    """打印检查结果"""
    status_icon = "✅" if status else "❌"
    print(f"{status_icon} {name:40} ", end="")
    if message:
        print(f"({message})")
    else:
        print()

def check_python_version():
    """检查 Python 版本"""
    print_header("1. Python 环境检查")

    version = sys.version_info
    is_ok = version >= (3, 7)
    print_check(
        "Python 版本",
        is_ok,
        f"{version.major}.{version.minor}.{version.micro}" + (" 符合要求" if is_ok else " 需要 3.7+")
    )
    return is_ok

def check_dependencies():
    """检查依赖包"""
    print_header("2. 依赖包检查")

    required_packages = {
        "lark_oapi": "lark-oapi",
        "dotenv": "python-dotenv",
        "markdown_it": "markdown-it-py"
    }

    all_ok = True
    for module_name, package_name in required_packages.items():
        try:
            importlib.import_module(module_name)
            print_check(f"{package_name:30}", True, "已安装")
        except ImportError:
            print_check(f"{package_name:30}", False, "未安装")
            all_ok = False

    if not all_ok:
        print("\n💡 安装缺失的依赖: pip install -r requirements.txt")

    return all_ok

def check_config_file():
    """检查配置文件"""
    print_header("3. 配置文件检查")

    config_file = "sync_config.json"
    if not os.path.exists(config_file):
        print_check("配置文件存在", False, f"{config_file} 不存在")
        print("\n💡 运行配置向导: python3 setup_wizard.py")
        return False

    print_check("配置文件存在", True, config_file)

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # 检查必要字段
        has_app_id = "feishu_app_id" in config and config["feishu_app_id"]
        has_app_secret = "feishu_app_secret" in config and config["feishu_app_secret"]

        print_check("App ID 已配置", has_app_id)
        print_check("App Secret 已配置", has_app_secret)

        # 检查 Token
        has_access_token = config.get("feishu_user_access_token", "")
        has_refresh_token = config.get("feishu_user_refresh_token", "")

        print_check(
            "用户 Access Token",
            bool(has_access_token),
            "已获取" if has_access_token else "未获取（首次运行时自动授权）"
        )
        print_check(
            "Refresh Token",
            bool(has_refresh_token),
            "已获取" if has_refresh_token else "未获取（首次运行时自动授权）"
        )

        # 检查任务配置
        tasks = config.get("tasks", [])
        print_check("同步任务数量", len(tasks) > 0, f"{len(tasks)} 个任务")

        if tasks:
            print("\n  任务列表：")
            for i, task in enumerate(tasks, 1):
                enabled = task.get("enabled", False)
                note = task.get("note", f"任务 {i}")
                local = task.get("local", "")
                exists = os.path.exists(local) if local else False

                status_icon = "✅" if enabled and exists else "⚠️ " if enabled else "⏸️ "
                print(f"    {status_icon} {note:30} ", end="")

                if not enabled:
                    print("(已禁用)")
                elif not exists:
                    print(f"(本地路径不存在: {local})")
                else:
                    print(f"({local})")

        return has_app_id and has_app_secret

    except json.JSONDecodeError:
        print_check("配置文件格式", False, "JSON 格式错误")
        return False
    except Exception as e:
        print_check("配置文件读取", False, str(e))
        return False

def check_connection():
    """检查飞书连接"""
    print_header("4. 飞书 API 连接检查")

    config_file = "sync_config.json"
    if not os.path.exists(config_file):
        print_check("跳过连接检查", False, "配置文件不存在")
        return False

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)

        app_id = config.get("feishu_app_id")
        app_secret = config.get("feishu_app_secret")

        if not app_id or not app_secret:
            print_check("App 凭证", False, "App ID 或 Secret 未配置")
            return False

        # 尝试导入并测试连接
        from src.feishu_client import FeishuClient

        client = FeishuClient(app_id, app_secret)

        # 尝试获取 tenant access token
        try:
            token = client._get_tenant_access_token()
            print_check("获取 Tenant Access Token", bool(token), "成功")
        except Exception as e:
            print_check("获取 Tenant Access Token", False, str(e))
            return False

        # 检查用户 token
        user_token = config.get("feishu_user_access_token")
        if user_token:
            print_check("用户 Access Token", True, "已配置")
        else:
            print_check("用户 Access Token", False, "未授权（首次运行时将自动引导授权）")

        return True

    except Exception as e:
        print_check("连接测试", False, str(e))
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("  DocSync 健康检查")
    print("=" * 60)

    results = []

    # 执行各项检查
    results.append(("Python 版本", check_python_version()))
    results.append(("依赖包", check_dependencies()))
    results.append(("配置文件", check_config_file()))
    results.append(("飞书连接", check_connection()))

    # 总结
    print_header("检查总结")

    all_passed = all(result[1] for result in results)

    for name, passed in results:
        status_icon = "✅" if passed else "❌"
        print(f"  {status_icon} {name}")

    if all_passed:
        print("\n🎉 所有检查通过！您可以开始使用 DocSync 了。")
        print("\n下一步：")
        print("  运行同步: python3 main.py")
    else:
        print("\n⚠️  有一些问题需要解决。")
        print("\n建议：")
        if not results[0][1]:
            print("  - 升级 Python 到 3.7 或更高版本")
        if not results[1][1]:
            print("  - 运行: pip install -r requirements.txt")
        if not results[2][1]:
            print("  - 运行配置向导: python3 setup_wizard.py")
        if not results[3][1]:
            print("  - 检查飞书应用配置和网络连接")

    print()
    return 0 if all_passed else 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n❌ 检查已中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
