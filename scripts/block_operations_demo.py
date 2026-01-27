#!/usr/bin/env python3
"""块操作演示脚本 - 展示块的增删改查操作

此脚本专注于展示块操作的完整流程：
1. 创建块
2. 读取块
3. 更新块
4. 删除块

运行方式:
    python scripts/block_operations_demo.py
"""

import os
import sys
import time

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from doc_sync.config import FEISHU_APP_ID, FEISHU_APP_SECRET
from doc_sync.feishu_client import FeishuClient

# 从环境变量获取文件夹 token（可选）
FEISHU_FOLDER_TOKEN = os.environ.get("FEISHU_FOLDER_TOKEN", "")


def print_divider(title: str = ""):
    """打印分隔线"""
    if title:
        print(f"\n{'─' * 20} {title} {'─' * 20}")
    else:
        print("─" * 50)


def demo_create_blocks(client: FeishuClient, doc_id: str) -> list:
    """演示创建块"""
    print_divider("CREATE 创建块")
    
    blocks = [
        # 标题块
        {
            "block_type": 3,  # Heading1
            "heading1": {
                "elements": [{"text_run": {"content": "块操作演示文档"}}]
            }
        },
        # 普通文本
        {
            "block_type": 2,
            "text": {
                "elements": [{"text_run": {"content": "这是一个演示文档，展示块的增删改查操作。"}}]
            }
        },
        # 带样式的文本
        {
            "block_type": 2,
            "text": {
                "elements": [
                    {"text_run": {"content": "支持 "}},
                    {"text_run": {"content": "粗体", "text_element_style": {"bold": True}}},
                    {"text_run": {"content": "、"}},
                    {"text_run": {"content": "斜体", "text_element_style": {"italic": True}}},
                    {"text_run": {"content": "、"}},
                    {"text_run": {"content": "删除线", "text_element_style": {"strikethrough": True}}},
                    {"text_run": {"content": " 等样式。"}}
                ]
            }
        },
        # 列表项
        {
            "block_type": 12,  # Bullet
            "bullet": {"elements": [{"text_run": {"content": "列表项 1"}}]}
        },
        {
            "block_type": 12,
            "bullet": {"elements": [{"text_run": {"content": "列表项 2"}}]}
        },
        # 代码块
        {
            "block_type": 14,  # Code
            "code": {
                "elements": [{"text_run": {"content": "# Python 代码\nprint('Hello!')"}}],
                "style": {"language": 49}  # Python
            }
        },
        # 待办事项
        {
            "block_type": 17,  # Todo
            "todo": {
                "elements": [{"text_run": {"content": "待办任务 1"}}],
                "style": {"done": False}
            }
        },
        {
            "block_type": 17,
            "todo": {
                "elements": [{"text_run": {"content": "已完成任务"}}],
                "style": {"done": True}
            }
        }
    ]
    
    print(f"📝 准备创建 {len(blocks)} 个块...")
    success = client.add_blocks(doc_id, blocks)
    
    if success:
        print("✅ 块创建成功!")
    else:
        print("❌ 块创建失败")
    
    return blocks


def demo_read_blocks(client: FeishuClient, doc_id: str) -> list:
    """演示读取块"""
    print_divider("READ 读取块")
    
    # 1. 获取直接子块
    print("\n📖 获取直接子块...")
    children = client.get_block_children(doc_id, doc_id)
    if children:
        print(f"   共 {len(children)} 个直接子块")
        for i, child in enumerate(children[:5]):
            bt = child.get("block_type", "?")
            bid = child.get("block_id", "N/A")[:20]
            print(f"   {i+1}. [type={bt}] {bid}...")
        if len(children) > 5:
            print(f"   ... 还有 {len(children) - 5} 个块")
    
    # 2. 获取单个块详情
    if children:
        first_block_id = children[0].get("block_id")
        print(f"\n📖 获取单个块详情: {first_block_id[:20]}...")
        block_detail = client.get_block(doc_id, first_block_id)
        if block_detail:
            print(f"   块类型: {block_detail.get('block_type')}")
            print(f"   包含字段: {list(block_detail.keys())[:5]}...")
    
    # 3. 获取包含子孙的所有块
    print("\n📖 获取所有子孙块（递归）...")
    all_descendants = client.get_block_children(doc_id, doc_id, with_descendants=True)
    if all_descendants:
        print(f"   共 {len(all_descendants)} 个块（含嵌套）")
    
    return children


def demo_update_blocks(client: FeishuClient, doc_id: str, children: list):
    """演示更新块"""
    print_divider("UPDATE 更新块")
    
    if not children:
        print("⚠️ 没有可更新的块")
        return
    
    # 找到一个文本块
    text_block_id = None
    todo_block_id = None
    
    for child in children:
        bt = child.get("block_type")
        if bt == 2 and not text_block_id:
            text_block_id = child.get("block_id")
        elif bt == 17 and not todo_block_id:
            todo_block_id = child.get("block_id")
    
    # 1. 更新文本内容
    if text_block_id:
        print(f"\n✏️ 更新文本块内容...")
        success = client.update_block_text(doc_id, text_block_id, [
            {"text_run": {"content": "✨ 这段文字已被更新！", 
                          "text_element_style": {"bold": True, "text_color": 5}}}
        ])
        if success:
            print("   ✅ 文本更新成功")
        else:
            print("   ❌ 文本更新失败")
    
    # 2. 批量更新（更新待办状态）
    if todo_block_id:
        print(f"\n✏️ 批量更新块...")
        result = client.batch_update_blocks(doc_id, [
            {
                "block_id": todo_block_id,
                "update_text_style": {
                    "style": {"done": True},
                    "fields": [2]  # done field
                }
            }
        ])
        if result:
            print("   ✅ 批量更新成功")
        else:
            print("   ❌ 批量更新失败")


def demo_delete_blocks(client: FeishuClient, doc_id: str):
    """演示删除块"""
    print_divider("DELETE 删除块")
    
    # 先获取当前块数量
    children = client.get_block_children(doc_id, doc_id)
    if not children or len(children) < 2:
        print("⚠️ 块数量不足，跳过删除演示")
        return
    
    original_count = len(children)
    print(f"📊 当前块数量: {original_count}")
    
    # 删除最后一个块
    print(f"\n🗑️ 删除最后一个块...")
    result = client.delete_block_children(doc_id, doc_id, 
                                          original_count - 1, original_count)
    
    if result:
        new_revision = result.get("document_revision_id")
        print(f"   ✅ 删除成功! 新版本: {new_revision}")
        
        # 验证删除
        children_after = client.get_block_children(doc_id, doc_id)
        print(f"   删除后块数量: {len(children_after)}")
    else:
        print("   ❌ 删除失败")


def main():
    """主函数"""
    print("=" * 60)
    print("🔧 块操作 CRUD 演示")
    print("=" * 60)
    
    # 检查配置
    if not all([FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_FOLDER_TOKEN]):
        print("\n❌ 请配置环境变量: FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_FOLDER_TOKEN")
        return 1
    
    # 创建客户端
    client = FeishuClient(FEISHU_APP_ID, FEISHU_APP_SECRET)
    print("\n✅ 客户端初始化成功")
    
    # 创建测试文档
    doc_id = client.create_docx(FEISHU_FOLDER_TOKEN, f"CRUD演示_{int(time.time())}")
    if not doc_id:
        print("❌ 无法创建测试文档")
        return 1
    print(f"📄 测试文档: {doc_id}")
    
    try:
        # C - Create
        demo_create_blocks(client, doc_id)
        time.sleep(0.5)  # 等待 API
        
        # R - Read
        children = demo_read_blocks(client, doc_id)
        
        # U - Update
        demo_update_blocks(client, doc_id, children)
        time.sleep(0.5)
        
        # D - Delete
        demo_delete_blocks(client, doc_id)
        
        print_divider()
        print("\n✅ CRUD 演示完成!")
        print(f"   文档 ID: {doc_id}")
        print("   你可以在飞书中查看结果")
        
    except Exception as e:
        print(f"\n❌ 演示出错: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
