"""Tests for Table conversion."""
import pytest
from src.converter import MarkdownToFeishu


class TestTableConversion:
    """Test Markdown table to native Table block conversion."""
    
    def test_simple_table(self):
        """Test basic 2x2 table generates native Table block."""
        md = """| A | B |
|---|---|
| 1 | 2 |"""
        converter = MarkdownToFeishu()
        blocks = converter.parse(md)
        
        assert len(blocks) == 1
        assert blocks[0]["block_type"] == 31  # Native Table
        assert blocks[0].get("_is_native_table") == True
        
        # Check property
        props = blocks[0]["table"]["property"]
        assert props["row_size"] == 2
        assert props["column_size"] == 2
        
        # Check children (cells)
        children = blocks[0]["children"]
        assert len(children) == 4  # 2 rows * 2 cols
        assert children[0]["block_type"] == 32  # TableCell
    
    def test_table_with_header(self):
        """Test table structure with header row."""
        md = """| Name | Age |
|------|-----|
| John | 30  |"""
        converter = MarkdownToFeishu()
        blocks = converter.parse(md)
        
        assert blocks[0]["block_type"] == 31
        props = blocks[0]["table"]["property"]
        assert props["row_size"] == 2
        assert props["column_size"] == 2
    
    def test_table_cell_content(self):
        """Test that table cell content is preserved."""
        md = """| Hello | World |
|-------|-------|
| A     | B     |"""
        converter = MarkdownToFeishu()
        blocks = converter.parse(md)
        
        # Check first cell has text block child
        first_cell = blocks[0]["children"][0]
        assert first_cell["block_type"] == 32
        text_block = first_cell["children"][0]
        assert text_block["block_type"] == 2
        content = text_block["text"]["elements"][0]["text_run"]["content"]
        assert "Hello" in content
    
    def test_table_in_document(self):
        """Test table mixed with other content."""
        md = """# Title

| Col1 | Col2 |
|------|------|
| A    | B    |

Some text."""
        converter = MarkdownToFeishu()
        blocks = converter.parse(md)
        
        assert len(blocks) >= 2
        table_block = next((b for b in blocks if b["block_type"] == 31), None)
        assert table_block is not None
        assert table_block.get("_is_native_table") == True
