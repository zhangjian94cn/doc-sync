#!/usr/bin/env python3
"""
DocSync 配置向导 - Setup Wizard
帮助用户快速配置 DocSync
"""

import os
import json
import sys

def print_header():
    """打印欢迎信息"""
    print("=" * 60)
    print("  DocSync 配置向导 - Setup Wizard")
    print("  帮助您快速配置 Obsidian 到飞书的同步工具")
    print("=" * 60)
    print()

def print_step(step_num, title):
    """打印步骤标题"""
    print(f"\n{'─' * 60}")
    print(f"  第 {step_num} 步: {title}")
    print('─' * 60)

def get_input(prompt, default="", required=True):
    """获取用户输入"""
    if default:
        full_prompt = f"{prompt} [{default}]: "
    else:
        full_prompt = f"{prompt}: "

    while True:
        value = input(full_prompt).strip()
        if value:
            return value
        elif default:
            return default
        elif not required:
            return ""
        else:
            print("  ⚠️  此项为必填项，请输入有效值")

def confirm(prompt):
    """确认操作"""
    while True:
        response = input(f"{prompt} (y/n): ").strip().lower()
        if response in ['y', 'yes', '是']:
            return True
        elif response in ['n', 'no', '否']:
            return False
        else:
            print("  ⚠️  请输入 y 或 n")

def create_config():
    """创建配置文件"""
    print_header()

    print("欢迎使用 DocSync！让我们开始配置您的同步任务。\n")
    print("📌 提示：您需要先在飞书开放平台创建应用。")
    print("   详见: https://open.feishu.cn/app\n")

    if not confirm("是否已经创建了飞书应用？"):
        print("\n请先访问 https://open.feishu.cn/app 创建应用。")
        print("需要的权限：")
        print("  - Cloud Docs -> docx:document")
        print("  - Cloud Drive -> drive:drive, drive:file:create, drive:file:read")
        print("\n配置完成后请重新运行本向导。")
        sys.exit(0)

    # 步骤 1: 飞书应用配置
    print_step(1, "飞书应用配置")
    print("请输入您的飞书应用信息（在飞书开放平台的应用详情页获取）\n")

    app_id = get_input("飞书 App ID (以 cli_ 开头)")
    while not app_id.startswith("cli_"):
        print("  ⚠️  App ID 应该以 'cli_' 开头")
        app_id = get_input("飞书 App ID (以 cli_ 开头)")

    app_secret = get_input("飞书 App Secret")

    # 步骤 2: 资源存储配置
    print_step(2, "资源存储配置（可选）")
    print("您可以指定一个飞书文件夹来存储上传的图片和附件。")
    print("如果留空，程序会自动在根目录创建 'DocSync_Assets' 文件夹。\n")

    assets_token = get_input("资源文件夹 Token", required=False)

    # 步骤 3: 同步任务配置
    print_step(3, "配置同步任务")
    print("现在让我们配置第一个同步任务。\n")

    tasks = []
    add_more = True
    task_num = 1

    while add_more:
        print(f"\n📝 任务 {task_num}")
        print("─" * 40)

        task_note = get_input("任务备注（例如：工作笔记、个人日记）", f"同步任务 {task_num}")

        print("\n本地路径配置：")
        local_path = get_input("本地 Markdown 文件或文件夹路径")
        while not os.path.exists(local_path):
            print(f"  ⚠️  路径不存在: {local_path}")
            local_path = get_input("本地 Markdown 文件或文件夹路径")

        print("\n云端目标配置：")
        print("💡 提示：打开飞书文件夹或文档，从 URL 中复制 Token")
        print("   示例：https://feishu.cn/drive/folder/[THIS_IS_TOKEN]")
        cloud_token = get_input("云端文件夹/文档 Token")

        print("\n Obsidian Vault 根目录：")
        print("💡 用于解析图片引用，通常是您的 Obsidian 仓库根目录")
        vault_root = get_input("Vault 根目录", local_path if os.path.isdir(local_path) else os.path.dirname(local_path))

        force_sync = confirm("\n是否每次都强制覆盖云端（忽略时间戳检查）？")

        task = {
            "note": task_note,
            "local": local_path,
            "cloud": cloud_token,
            "vault_root": vault_root,
            "enabled": True,
            "force": force_sync
        }

        tasks.append(task)
        task_num += 1

        print("\n✅ 任务配置完成！")
        add_more = confirm("\n是否继续添加更多同步任务？")

    # 创建配置对象
    config = {
        "_readme": "配置文件说明：本文件用于配置飞书同步参数。带 _desc 后缀的字段为说明注释，请勿删除。",

        "feishu_app_id_desc": "飞书开放平台应用的 App ID (以 cli_ 开头)",
        "feishu_app_id": app_id,

        "feishu_app_secret_desc": "飞书开放平台应用的 App Secret",
        "feishu_app_secret": app_secret,

        "feishu_user_access_token_desc": "[自动管理] 用户的 Access Token，用于访问文档和云空间 (程序自动刷新，勿动)",
        "feishu_user_access_token": "",

        "feishu_user_refresh_token_desc": "[自动管理] 用于刷新 Access Token 的 Refresh Token (程序自动刷新，勿动)",
        "feishu_user_refresh_token": "",

        "feishu_assets_token_desc": "指定存放图片/附件的飞书文件夹 Token。若留空，程序会自动在根目录创建 'DocSync_Assets'",
        "feishu_assets_token": assets_token,

        "tasks_desc": "同步任务列表配置",
        "tasks": []
    }

    # 添加任务配置（带说明）
    for i, task in enumerate(tasks):
        task_with_desc = {
            "note": task["note"],
            "local_desc": "本地文件或文件夹的绝对路径",
            "local": task["local"],
            "cloud_desc": "飞书目标位置的 Token (文件夹Token 或 文档Token)",
            "cloud": task["cloud"],
            "vault_root_desc": "Obsidian 仓库根目录，用于解析 Markdown 中的绝对路径图片引用 (如 ![[image.png]])",
            "vault_root": task["vault_root"],
            "enabled_desc": "是否启用此任务 (true/false)",
            "enabled": task["enabled"],
            "force_desc": "是否强制覆盖云端 (true: 忽略时间戳对比; false: 仅当本地更新时上传)",
            "force": task["force"]
        }
        config["tasks"].append(task_with_desc)

    # 保存配置
    config_file = "sync_config.json"

    if os.path.exists(config_file):
        if not confirm(f"\n⚠️  配置文件 {config_file} 已存在，是否覆盖？"):
            backup_file = f"{config_file}.backup"
            print(f"\n💾 原配置已备份到: {backup_file}")
            with open(config_file, 'r', encoding='utf-8') as f:
                with open(backup_file, 'w', encoding='utf-8') as bf:
                    bf.write(f.read())

    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    # 完成
    print("\n" + "=" * 60)
    print("  ✅ 配置完成！")
    print("=" * 60)
    print(f"\n配置文件已保存到: {config_file}")
    print("\n下一步操作：")
    print("  1. 运行首次同步: python3 main.py")
    print("  2. 程序会自动打开浏览器进行飞书授权")
    print("  3. 授权成功后，同步将自动开始")
    print("\n📖 更多帮助：python3 main.py --help")
    print()

if __name__ == "__main__":
    try:
        create_config()
    except KeyboardInterrupt:
        print("\n\n❌ 配置已取消")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ 配置过程中出现错误: {e}")
        sys.exit(1)
