#!/usr/bin/env python3
"""Markdown 转换对比脚本 - 对比本地转换器和飞书官方 API

此脚本对比两种 Markdown 转飞书块的方式：
1. 本地 MarkdownToFeishu 转换器
2. 飞书官方 convert_content_to_blocks API

运行方式:
    python examples/markdown_convert_demo.py
"""

import os
import sys
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from doc_sync.converter import MarkdownToFeishu
from doc_sync.config import FEISHU_APP_ID, FEISHU_APP_SECRET
from doc_sync.feishu_client import FeishuClient


# 测试用的 Markdown 内容
TEST_MARKDOWN = """---
title: 转换测试文档
author: Demo
---

# 一级标题

这是普通文本段落，包含 **粗体**、*斜体*、~~删除线~~ 和 `行内代码`。

## 二级标题

### 链接和图片

这是一个 [链接示例](https://open.feishu.cn)。

## 列表示例

### 无序列表
- 项目 1
- 项目 2
  - 嵌套项 2.1
  - 嵌套项 2.2
- 项目 3

### 有序列表
1. 第一步
2. 第二步
3. 第三步

### 待办事项
- [ ] 未完成任务
- [x] 已完成任务

## 代码示例

```python
def hello_world():
    print("Hello, Feishu!")
    return True
```

## 引用示例

> 这是一段引用文本
> 可以有多行

## 表格示例

| 功能 | 状态 | 备注 |
|------|------|------|
| 文本 | ✅ | 支持富文本 |
| 列表 | ✅ | 支持嵌套 |
| 代码 | ✅ | 支持语法高亮 |
| 表格 | ✅ | 原生表格 |
"""


def count_block_types(blocks: list) -> dict:
    """统计块类型分布"""
    type_count = {}
    for block in blocks:
        if isinstance(block, dict):
            bt = block.get("block_type", 0)
            type_count[bt] = type_count.get(bt, 0) + 1
    return type_count


def get_block_type_name(bt: int) -> str:
    """获取块类型名称"""
    names = {
        1: "页面", 2: "文本", 3: "标题1", 4: "标题2", 5: "标题3",
        6: "标题4", 7: "标题5", 8: "标题6", 9: "标题7", 10: "标题8",
        11: "标题9", 12: "无序列表", 13: "有序列表", 14: "代码块",
        15: "引用", 17: "待办", 22: "分割线", 27: "图片",
        31: "表格", 32: "表格单元格", 34: "引用容器"
    }
    return names.get(bt, f"类型{bt}")


def demo_local_converter():
    """演示本地转换器"""
    print("\n" + "=" * 60)
    print("📝 本地转换器 (MarkdownToFeishu)")
    print("=" * 60)
    
    converter = MarkdownToFeishu()
    blocks = converter.parse(TEST_MARKDOWN)
    
    print(f"\n✅ 转换完成!")
    print(f"   总块数: {len(blocks)}")
    
    # 统计块类型
    type_count = count_block_types(blocks)
    print("\n   块类型分布:")
    for bt, count in sorted(type_count.items()):
        name = get_block_type_name(bt)
        print(f"      [{bt:2d}] {name}: {count}")
    
    # 显示前几个块的结构
    print("\n   前5个块预览:")
    for i, block in enumerate(blocks[:5]):
        bt = block.get("block_type", "?")
        name = get_block_type_name(bt)
        print(f"      {i+1}. [{bt}] {name}")
    
    return blocks


def demo_api_converter(client: FeishuClient):
    """演示官方 API 转换器"""
    print("\n" + "=" * 60)
    print("🌐 官方 API (convert_content_to_blocks)")
    print("=" * 60)
    
    # 移除 front matter 因为官方 API 可能不支持
    content_without_fm = TEST_MARKDOWN.split("---", 2)[-1].strip()
    
    result = client.convert_content_to_blocks(content_without_fm)
    
    if not result:
        print("\n❌ 转换失败!")
        return None
    
    blocks = result.get("blocks", [])
    first_level = result.get("first_level_block_ids", [])
    
    print(f"\n✅ 转换完成!")
    print(f"   顶层块: {len(first_level)} 个")
    print(f"   总块数: {len(blocks)} 个")
    
    # 统计块类型
    type_count = count_block_types(blocks)
    print("\n   块类型分布:")
    for bt, count in sorted(type_count.items()):
        name = get_block_type_name(bt)
        print(f"      [{bt:2d}] {name}: {count}")
    
    # 显示前几个块的结构
    print("\n   前5个块预览:")
    for i, block in enumerate(blocks[:5]):
        bt = block.get("block_type", "?")
        name = get_block_type_name(bt)
        block_id = block.get("block_id", "N/A")[:15]
        print(f"      {i+1}. [{bt}] {name} ({block_id}...)")
    
    return blocks


def compare_results(local_blocks: list, api_blocks: list):
    """对比转换结果"""
    print("\n" + "=" * 60)
    print("📊 转换结果对比")
    print("=" * 60)
    
    local_types = count_block_types(local_blocks)
    api_types = count_block_types(api_blocks) if api_blocks else {}
    
    all_types = set(local_types.keys()) | set(api_types.keys())
    
    print("\n   | 块类型      | 本地 | API  | 差异 |")
    print("   |-------------|------|------|------|")
    
    for bt in sorted(all_types):
        name = get_block_type_name(bt)[:10].ljust(10)
        local_count = local_types.get(bt, 0)
        api_count = api_types.get(bt, 0)
        diff = api_count - local_count
        diff_str = f"+{diff}" if diff > 0 else str(diff) if diff < 0 else "="
        print(f"   | {name} | {local_count:4d} | {api_count:4d} | {diff_str:>4s} |")
    
    print(f"\n   总计: 本地 {len(local_blocks)} 块, API {len(api_blocks) if api_blocks else 0} 块")
    
    # 分析差异
    print("\n📋 分析结论:")
    if not api_blocks:
        print("   ⚠️ API 转换失败，无法对比")
    elif len(local_blocks) == len(api_blocks):
        print("   ✅ 两种方式生成的块数量相同")
    else:
        print(f"   📊 块数量差异: {abs(len(local_blocks) - len(api_blocks))}")
    
    # 提示不同点
    print("\n💡 选择建议:")
    print("   - 本地转换器: 离线可用、可定制、支持 Front Matter")
    print("   - 官方 API: 格式更标准、支持更多元素、需要网络")


def main():
    """主函数"""
    print("=" * 60)
    print("🔄 Markdown 转换方案对比")
    print("=" * 60)
    
    print("\n📄 测试内容:")
    print("-" * 40)
    lines = TEST_MARKDOWN.strip().split('\n')
    for line in lines[:10]:
        print(f"   {line}")
    print("   ...")
    print(f"   (共 {len(lines)} 行)")
    
    # 1. 本地转换器
    local_blocks = demo_local_converter()
    
    # 2. 官方 API 转换器
    api_blocks = None
    if FEISHU_APP_ID and FEISHU_APP_SECRET:
        print("\n📡 连接飞书 API...")
        try:
            client = FeishuClient(FEISHU_APP_ID, FEISHU_APP_SECRET)
            api_blocks = demo_api_converter(client)
        except Exception as e:
            print(f"   ❌ API 连接失败: {e}")
    else:
        print("\n⚠️ 未配置飞书凭据，跳过 API 转换演示")
        print("   请设置 FEISHU_APP_ID 和 FEISHU_APP_SECRET")
    
    # 3. 对比结果
    compare_results(local_blocks, api_blocks)
    
    print("\n" + "=" * 60)
    print("✅ 对比完成!")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
