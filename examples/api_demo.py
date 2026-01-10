#!/usr/bin/env python3
"""API 演示脚本 - 展示所有飞书文档操作 API 的使用方法

此脚本演示了 doc-sync 项目中所有可用的飞书 API 方法，
包括文档创建、块操作、内容转换等功能。

使用前请确保已配置环境变量或 .env 文件：
- FEISHU_APP_ID
- FEISHU_APP_SECRET  
- FEISHU_FOLDER_TOKEN (用于测试的目标文件夹)

运行方式:
    python examples/api_demo.py
"""

import os
import sys
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import FEISHU_APP_ID, FEISHU_APP_SECRET
from src.feishu_client import FeishuClient
from src.logger import logger

# 从环境变量获取文件夹 token
FEISHU_FOLDER_TOKEN = os.environ.get("FEISHU_FOLDER_TOKEN", "")


def demo_document_operations(client: FeishuClient, folder_token: str):
    """演示文档操作 API"""
    print("\n" + "=" * 60)
    print("📄 文档操作演示")
    print("=" * 60)
    
    # 1. 创建文档
    print("\n1️⃣ 创建新文档...")
    doc_id = client.create_docx(folder_token, f"API演示文档_{int(time.time())}")
    if doc_id:
        print(f"   ✅ 文档创建成功: {doc_id}")
    else:
        print("   ❌ 文档创建失败")
        return None
    
    return doc_id


def demo_block_operations(client: FeishuClient, doc_id: str):
    """演示块操作 API"""
    print("\n" + "=" * 60)
    print("📦 块操作演示")
    print("=" * 60)
    
    # 1. 添加块
    print("\n1️⃣ 添加多种类型的块...")
    blocks = [
        {
            "block_type": 3,  # Heading1
            "heading1": {
                "elements": [{"text_run": {"content": "API 演示文档"}}]
            }
        },
        {
            "block_type": 2,  # Text
            "text": {
                "elements": [
                    {"text_run": {"content": "这是一个 "}},
                    {"text_run": {"content": "粗体", "text_element_style": {"bold": True}}},
                    {"text_run": {"content": " 和 "}},
                    {"text_run": {"content": "斜体", "text_element_style": {"italic": True}}},
                    {"text_run": {"content": " 文本演示。"}}
                ]
            }
        },
        {
            "block_type": 12,  # Bullet
            "bullet": {
                "elements": [{"text_run": {"content": "无序列表项 1"}}]
            }
        },
        {
            "block_type": 12,  # Bullet
            "bullet": {
                "elements": [{"text_run": {"content": "无序列表项 2"}}]
            }
        },
        {
            "block_type": 14,  # Code
            "code": {
                "elements": [{"text_run": {"content": "print('Hello, Feishu!')"}}],
                "style": {"language": 49}  # Python
            }
        }
    ]
    
    success = client.add_blocks(doc_id, blocks)
    if success:
        print("   ✅ 块添加成功")
    else:
        print("   ❌ 块添加失败")
    
    # 2. 获取所有块
    print("\n2️⃣ 获取所有块...")
    all_blocks = client.get_all_blocks(doc_id)
    print(f"   ✅ 共获取 {len(all_blocks) if all_blocks else 0} 个块")
    
    # 3. 获取子块（使用新 API）
    print("\n3️⃣ 获取文档子块（支持分页）...")
    children = client.get_block_children(doc_id, doc_id)
    if children:
        print(f"   ✅ 直接子块数量: {len(children)}")
        for i, child in enumerate(children[:3]):  # 只显示前3个
            block_type = child.get("block_type", "?")
            print(f"      - [{block_type}] {child.get('block_id', 'N/A')[:20]}...")
    
    # 4. 获取包含子孙块
    print("\n4️⃣ 获取所有子孙块（递归）...")
    descendants = client.get_block_children(doc_id, doc_id, with_descendants=True)
    if descendants:
        print(f"   ✅ 包含子孙共: {len(descendants)} 个块")
    
    return children


def demo_batch_update(client: FeishuClient, doc_id: str, children: list):
    """演示批量更新 API"""
    print("\n" + "=" * 60)
    print("✏️ 批量更新演示")
    print("=" * 60)
    
    if not children or len(children) < 2:
        print("   ⚠️ 没有足够的块进行批量更新演示")
        return
    
    # 找一个文本块来更新
    text_block = None
    for child in children:
        if child.get("block_type") == 2:  # Text block
            text_block = child
            break
    
    if not text_block:
        print("   ⚠️ 未找到可更新的文本块")
        return
    
    block_id = text_block.get("block_id")
    print(f"\n1️⃣ 批量更新块样式...")
    
    # 使用 batch_update_blocks
    update_requests = [
        {
            "block_id": block_id,
            "update_text_elements": {
                "elements": [
                    {"text_run": {"content": "✨ 这段文字已被批量更新！", 
                                  "text_element_style": {"bold": True, "text_color": 5}}}
                ]
            }
        }
    ]
    
    result = client.batch_update_blocks(doc_id, update_requests)
    if result:
        print(f"   ✅ 批量更新成功，返回 {len(result)} 个更新结果")
    else:
        print("   ❌ 批量更新失败")


def demo_content_conversion(client: FeishuClient):
    """演示内容转换 API"""
    print("\n" + "=" * 60)
    print("🔄 Markdown/HTML 转换演示")
    print("=" * 60)
    
    markdown_content = """
# 转换测试

这是 **粗体** 和 *斜体* 文本。

## 列表示例

- 无序项 1
- 无序项 2

1. 有序项 1
2. 有序项 2

## 代码示例

```python
def hello():
    return "Hello, World!"
```

## 表格示例

| 名称 | 描述 |
|------|------|
| API | 接口 |
| SDK | 开发包 |
"""

    print("\n1️⃣ 转换 Markdown 为飞书块...")
    result = client.convert_content_to_blocks(markdown_content.strip())
    
    if result:
        blocks = result.get("blocks", [])
        first_level = result.get("first_level_block_ids", [])
        print(f"   ✅ 转换成功!")
        print(f"      - 顶层块 ID: {len(first_level)} 个")
        print(f"      - 总块数: {len(blocks)} 个")
        
        # 统计块类型
        type_count = {}
        for block in blocks:
            bt = block.get("block_type", 0)
            type_count[bt] = type_count.get(bt, 0) + 1
        
        print("      - 块类型分布:")
        type_names = {
            2: "文本", 3: "标题1", 4: "标题2", 5: "标题3",
            12: "无序列表", 13: "有序列表", 14: "代码块",
            15: "引用", 17: "待办", 31: "表格", 32: "表格单元格"
        }
        for bt, count in sorted(type_count.items()):
            name = type_names.get(bt, f"类型{bt}")
            print(f"        [{bt}] {name}: {count}")
    else:
        print("   ❌ 转换失败")
    
    return result


def demo_delete_operations(client: FeishuClient, doc_id: str):
    """演示删除操作 API"""
    print("\n" + "=" * 60)
    print("🗑️ 删除操作演示")
    print("=" * 60)
    
    # 先添加一些要删除的块
    print("\n1️⃣ 添加临时块用于删除演示...")
    temp_blocks = [
        {"block_type": 2, "text": {"elements": [{"text_run": {"content": "临时块 1 - 将被删除"}}]}},
        {"block_type": 2, "text": {"elements": [{"text_run": {"content": "临时块 2 - 将被删除"}}]}},
        {"block_type": 2, "text": {"elements": [{"text_run": {"content": "临时块 3 - 将保留"}}]}}
    ]
    client.add_blocks(doc_id, temp_blocks)
    
    # 获取当前子块数量
    children = client.get_block_children(doc_id, doc_id)
    if children:
        print(f"   当前子块数量: {len(children)}")
    
    # 删除前两个临时块
    print("\n2️⃣ 删除子块范围 [0:2]...")
    
    # 获取最新的子块数量
    children = client.get_block_children(doc_id, doc_id)
    if children and len(children) >= 2:
        result = client.delete_block_children(doc_id, doc_id, 
                                               len(children) - 3, len(children) - 1)
        if result:
            print(f"   ✅ 删除成功! 新版本号: {result.get('document_revision_id')}")
        else:
            print("   ❌ 删除失败")
    
    # 验证删除结果
    children_after = client.get_block_children(doc_id, doc_id)
    if children_after:
        print(f"   删除后子块数量: {len(children_after)}")


def cleanup(client: FeishuClient, doc_id: str):
    """清理演示文档"""
    print("\n" + "=" * 60)
    print("🧹 清理演示文档")
    print("=" * 60)
    
    print("\n删除演示文档...")
    success = client.delete_file(doc_id, "docx")
    if success:
        print("   ✅ 文档已删除")
    else:
        print("   ⚠️ 文档删除失败（可能需要手动删除）")


def main():
    """主函数"""
    print("=" * 60)
    print("🚀 飞书文档 API 演示")
    print("=" * 60)
    
    # 检查配置
    if not all([FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_FOLDER_TOKEN]):
        print("\n❌ 错误: 请配置以下环境变量:")
        print("   - FEISHU_APP_ID")
        print("   - FEISHU_APP_SECRET")
        print("   - FEISHU_FOLDER_TOKEN")
        return 1
    
    # 创建客户端
    print(f"\n📡 连接飞书 API...")
    client = FeishuClient(FEISHU_APP_ID, FEISHU_APP_SECRET)
    print("   ✅ 客户端初始化成功")
    
    doc_id = None
    
    try:
        # 1. 文档操作
        doc_id = demo_document_operations(client, FEISHU_FOLDER_TOKEN)
        if not doc_id:
            return 1
        
        # 2. 块操作
        children = demo_block_operations(client, doc_id)
        
        # 3. 批量更新
        demo_batch_update(client, doc_id, children)
        
        # 4. 内容转换
        demo_content_conversion(client)
        
        # 5. 删除操作
        demo_delete_operations(client, doc_id)
        
        print("\n" + "=" * 60)
        print("✅ 所有演示完成!")
        print("=" * 60)
        print(f"\n📄 演示文档 ID: {doc_id}")
        print("   你可以在飞书中查看文档，或取消下面的注释来删除它")
        
        # 取消注释以自动清理
        # cleanup(client, doc_id)
        
    except Exception as e:
        logger.error(f"演示过程出错: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
