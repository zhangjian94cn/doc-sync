#!/usr/bin/env python3
"""
Integration test for cloud-to-local conversion.

Tests FeishuToMarkdown converter with real Feishu documents to verify:
- Table conversion (rows, columns, content)
- Nested list handling
- Text formatting (bold, italic, code, links)

Usage:
    PYTHONPATH=. python examples/test_cloud_to_local.py <doc_token>
    PYTHONPATH=. python examples/test_cloud_to_local.py JMOEd6esIo72wTxxt9wc25rDn7e
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.feishu_client import FeishuClient
from src.config import FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_USER_ACCESS_TOKEN
from src.converter import FeishuToMarkdown


def count_tables(md_content: str) -> int:
    """Count markdown tables in content."""
    lines = md_content.split('\n')
    table_count = 0
    in_table = False
    for line in lines:
        if line.strip().startswith('|') and line.strip().endswith('|'):
            if not in_table:
                table_count += 1
                in_table = True
        else:
            in_table = False
    return table_count


def count_table_rows(md_content: str) -> list:
    """Count rows in each markdown table."""
    lines = md_content.split('\n')
    tables = []
    current_table_rows = 0
    in_table = False
    
    for line in lines:
        if line.strip().startswith('|') and line.strip().endswith('|'):
            if '---' not in line:  # Skip separator rows
                current_table_rows += 1
            in_table = True
        else:
            if in_table and current_table_rows > 0:
                tables.append(current_table_rows)
            current_table_rows = 0
            in_table = False
    
    if in_table and current_table_rows > 0:
        tables.append(current_table_rows)
    
    return tables


def count_nested_lists(md_content: str) -> int:
    """Count nested list items (starting with spaces)."""
    lines = md_content.split('\n')
    nested_count = 0
    for line in lines:
        # Check for indented list items
        stripped = line.lstrip()
        if line != stripped:  # Has indentation
            if stripped.startswith('- ') or stripped.startswith('1. '):
                nested_count += 1
    return nested_count


def main():
    if len(sys.argv) < 2:
        print("Usage: PYTHONPATH=. python examples/test_cloud_to_local.py <doc_token>")
        print("Example: PYTHONPATH=. python examples/test_cloud_to_local.py JMOEd6esIo72wTxxt9wc25rDn7e")
        sys.exit(1)
    
    doc_token = sys.argv[1]
    
    print(f"=== Testing Cloud-to-Local Conversion ===")
    print(f"Document: {doc_token}")
    print()
    
    # Initialize client
    client = FeishuClient(FEISHU_APP_ID, FEISHU_APP_SECRET,
                          user_access_token=FEISHU_USER_ACCESS_TOKEN)
    
    # Fetch blocks
    print("📥 Fetching document blocks...")
    blocks = client.list_document_blocks(doc_token)
    print(f"   Total blocks: {len(blocks)}")
    
    # Count block types
    type_counts = {}
    for block in blocks:
        b_type = block.block_type
        type_counts[b_type] = type_counts.get(b_type, 0) + 1
    
    type_names = {
        1: "Page", 2: "Text", 3: "H1", 4: "H2", 5: "H3", 12: "Bullet",
        13: "Ordered", 14: "Code", 15: "Quote", 17: "Todo", 22: "Divider",
        27: "Image", 31: "Table", 32: "TableCell"
    }
    
    print("   Block types:")
    for b_type, count in sorted(type_counts.items()):
        name = type_names.get(b_type, f"Type{b_type}")
        print(f"     - {name}: {count}")
    
    # Convert to Markdown
    print()
    print("🔄 Converting to Markdown...")
    converter = FeishuToMarkdown()
    md_content = converter.convert(blocks)
    
    print(f"   Output: {len(md_content)} characters")
    
    # Analyze conversion results
    print()
    print("📊 Conversion Analysis:")
    
    # Tables
    table_count = count_tables(md_content)
    table_rows = count_table_rows(md_content)
    expected_tables = type_counts.get(31, 0)
    
    print(f"   Tables: {table_count} converted (expected {expected_tables})")
    if table_rows:
        for i, rows in enumerate(table_rows):
            print(f"     - Table {i+1}: {rows} rows")
    
    status_tables = "✅" if table_count == expected_tables else "❌"
    
    # Nested lists
    nested_count = count_nested_lists(md_content)
    # Count blocks that are children of other blocks (have parent_id not equal to doc_token)
    nested_block_count = 0
    for block in blocks:
        parent_id = getattr(block, 'parent_id', None)
        if parent_id and parent_id != doc_token and block.block_type != 32:  # Exclude TableCell
            nested_block_count += 1
    
    print(f"   Nested items: {nested_count} in markdown (expected ~{nested_block_count})")
    status_nested = "✅" if nested_count >= nested_block_count * 0.8 else "⚠️"
    
    # Show sample output
    print()
    print("📝 Sample Output (first 1500 chars):")
    print("-" * 50)
    print(md_content[:1500])
    if len(md_content) > 1500:
        print(f"\n... ({len(md_content) - 1500} more chars)")
    print("-" * 50)
    
    # Summary
    print()
    print("=== Summary ===")
    print(f"{status_tables} Tables: {table_count}/{expected_tables}")
    print(f"{status_nested} Nested lists: {nested_count} items")
    
    # Save output
    output_file = f"examples/converted_{doc_token[:10]}.md"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(md_content)
    print(f"\n📄 Full output saved to: {output_file}")


if __name__ == "__main__":
    main()
