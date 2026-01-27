#!/usr/bin/env python3
"""
Debug script to inspect cloud document structure for FeishuToMarkdown debugging.

This script fetches blocks from a Feishu document and prints their structure
to help debug cloud-to-local conversion issues.

Usage:
    python examples/debug_cloud_structure.py <doc_token>
    python examples/debug_cloud_structure.py JMOEd6esIo72wTxxt9wc25rDn7e
"""

import sys
import json
import lark_oapi as lark

from doc_sync.feishu_client import FeishuClient
from doc_sync.config import FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_USER_ACCESS_TOKEN
from doc_sync.converter import FeishuToMarkdown


def inspect_block(block, depth=0):
    """Print detailed info about a block."""
    indent = "  " * depth
    b_type = block.block_type
    
    type_names = {
        1: "Page", 2: "Text", 3: "H1", 4: "H2", 5: "H3", 6: "H4", 7: "H5", 8: "H6",
        9: "H7", 10: "H8", 11: "H9", 12: "Bullet", 13: "Ordered", 14: "Code",
        15: "Quote", 17: "Todo", 22: "Divider", 23: "File", 27: "Image",
        31: "Table", 32: "TableCell"
    }
    type_name = type_names.get(b_type, f"Unknown({b_type})")
    
    print(f"{indent}[{type_name}] block_id={block.block_id[:15]}...")
    
    # Print text content
    text_attrs = ['text', 'heading1', 'heading2', 'heading3', 'heading4', 'heading5', 
                  'heading6', 'heading7', 'heading8', 'heading9', 'bullet', 'ordered',
                  'code', 'quote', 'todo']
    for attr in text_attrs:
        obj = getattr(block, attr, None)
        if obj and hasattr(obj, 'elements') and obj.elements:
            content = ""
            for elem in obj.elements:
                if hasattr(elem, 'text_run') and elem.text_run:
                    content += elem.text_run.content or ""
            if content:
                print(f"{indent}  content: {content[:50]}{'...' if len(content) > 50 else ''}")
            break
    
    # Print table info
    if b_type == 31 and hasattr(block, 'table') and block.table:
        table = block.table
        if hasattr(table, 'property') and table.property:
            print(f"{indent}  table: rows={table.property.row_size}, cols={table.property.column_size}")
        if hasattr(table, 'cells'):
            print(f"{indent}  cells attr exists: {table.cells}")
    
    # Print children info
    if hasattr(block, 'children') and block.children:
        print(f"{indent}  children_ids: {len(block.children)}")
    
    # Print table_cell info
    if b_type == 32:
        print(f"{indent}  (TableCell)")


def main():
    if len(sys.argv) < 2:
        print("Usage: python examples/debug_cloud_structure.py <doc_token>")
        print("Example: python examples/debug_cloud_structure.py JMOEd6esIo72wTxxt9wc25rDn7e")
        sys.exit(1)
    
    doc_token = sys.argv[1]
    
    print(f"=== Inspecting document: {doc_token} ===\n")
    
    # Initialize client
    client = FeishuClient(FEISHU_APP_ID, FEISHU_APP_SECRET, 
                          user_access_token=FEISHU_USER_ACCESS_TOKEN)
    
    # Fetch all blocks
    print("Fetching blocks...")
    blocks = client.list_document_blocks(doc_token)
    print(f"Total blocks: {len(blocks)}\n")
    
    # Build block map
    block_map = {b.block_id: b for b in blocks}
    
    # Print structure
    print("=== Block Structure ===\n")
    
    for block in blocks:
        # Skip Page block
        if block.block_type == 1:
            continue
        
        # Only print root-level blocks (parent is document)
        parent_id = getattr(block, 'parent_id', None)
        if parent_id == doc_token:
            inspect_block(block)
            
            # Print children
            if hasattr(block, 'children') and block.children:
                for child_id in block.children:
                    child = block_map.get(child_id)
                    if child:
                        inspect_block(child, 1)
                        # Second level children
                        if hasattr(child, 'children') and child.children:
                            for grandchild_id in child.children:
                                grandchild = block_map.get(grandchild_id)
                                if grandchild:
                                    inspect_block(grandchild, 2)
    
    # Test conversion
    print("\n=== Testing FeishuToMarkdown Conversion ===\n")
    
    converter = FeishuToMarkdown()
    # Filter out Page block
    content_blocks = [b for b in blocks if b.block_type != 1]
    
    try:
        md_output = converter.convert(content_blocks)
        print("Converted Markdown (first 2000 chars):")
        print("-" * 50)
        print(md_output[:2000])
        if len(md_output) > 2000:
            print(f"\n... ({len(md_output) - 2000} more chars)")
    except Exception as e:
        print(f"Conversion error: {e}")
        import traceback
        traceback.print_exc()
    
    # Export raw JSON for detailed analysis
    print("\n=== Exporting Raw Block Data ===")
    output_file = f"examples/debug_output_{doc_token[:10]}.json"
    raw_data = []
    for b in blocks:
        try:
            raw_data.append(json.loads(lark.JSON.marshal(b)))
        except:
            pass
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(raw_data, f, ensure_ascii=False, indent=2)
    print(f"Raw data exported to: {output_file}")


if __name__ == "__main__":
    main()
