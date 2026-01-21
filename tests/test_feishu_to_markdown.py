"""
Unit tests for FeishuToMarkdown converter.

Tests the conversion of Feishu blocks to Markdown with mock block objects.
"""

import pytest
from unittest.mock import Mock, MagicMock

from src.converter import FeishuToMarkdown


class MockBlock:
    """Mock Feishu block for testing."""
    
    def __init__(self, block_id, block_type, parent_id=None, children=None, **kwargs):
        self.block_id = block_id
        self.block_type = block_type
        self.parent_id = parent_id
        self.children = children or []
        
        # Set additional attributes
        for key, value in kwargs.items():
            setattr(self, key, value)


class MockTextObj:
    """Mock text object with elements."""
    
    def __init__(self, text, bold=False, italic=False, inline_code=False):
        self.elements = [MockElement(text, bold, italic, inline_code)]
        self.style = Mock(align=1, folded=False)


class MockElement:
    """Mock text element."""
    
    def __init__(self, text, bold=False, italic=False, inline_code=False):
        self.text_run = MockTextRun(text, bold, italic, inline_code)


class MockTextRun:
    """Mock text run with content and style."""
    
    def __init__(self, content, bold=False, italic=False, inline_code=False):
        self.content = content
        self.text_element_style = Mock(
            bold=bold,
            italic=italic,
            inline_code=inline_code,
            strikethrough=False,
            link=None
        )


class TestFeishuToMarkdown:
    """Tests for FeishuToMarkdown converter."""
    
    def test_instantiation(self):
        """Test that converter can be instantiated."""
        converter = FeishuToMarkdown()
        assert converter is not None
    
    def test_instantiation_with_downloader(self):
        """Test instantiation with image downloader."""
        def mock_downloader(token):
            return f"/path/to/{token}.png"
        
        converter = FeishuToMarkdown(image_downloader=mock_downloader)
        assert converter.image_downloader is not None
    
    def test_convert_simple_text(self):
        """Test converting a simple text block."""
        converter = FeishuToMarkdown()
        
        # Create mock blocks
        page = MockBlock("doc_token", 1, children=["block1"])
        
        text_block = MockBlock("block1", 2, parent_id="doc_token", 
                               text=MockTextObj("Hello World"))
        
        result = converter.convert([page, text_block])
        assert "Hello World" in result
    
    def test_convert_heading(self):
        """Test converting heading blocks."""
        converter = FeishuToMarkdown()
        
        page = MockBlock("doc_token", 1, children=["block1"])
        heading_block = MockBlock("block1", 3, parent_id="doc_token",
                                  heading1=MockTextObj("Title"))
        
        result = converter.convert([page, heading_block])
        assert "# Title" in result
    
    def test_convert_bullet_list(self):
        """Test converting bullet list blocks."""
        converter = FeishuToMarkdown()
        
        page = MockBlock("doc_token", 1, children=["block1", "block2"])
        bullet1 = MockBlock("block1", 12, parent_id="doc_token",
                            bullet=MockTextObj("Item 1"))
        bullet2 = MockBlock("block2", 12, parent_id="doc_token",
                            bullet=MockTextObj("Item 2"))
        
        result = converter.convert([page, bullet1, bullet2])
        assert "- Item 1" in result
        assert "- Item 2" in result
    
    def test_convert_nested_list(self):
        """Test converting nested list blocks."""
        converter = FeishuToMarkdown()
        
        page = MockBlock("doc_token", 1, children=["parent"])
        parent = MockBlock("parent", 12, parent_id="doc_token", 
                          children=["child"],
                          bullet=MockTextObj("Parent"))
        child = MockBlock("child", 12, parent_id="parent",
                         bullet=MockTextObj("Child"))
        
        result = converter.convert([page, parent, child])
        assert "- Parent" in result
        assert "  - Child" in result
    
    def test_convert_ordered_list(self):
        """Test converting ordered list blocks."""
        converter = FeishuToMarkdown()
        
        page = MockBlock("doc_token", 1, children=["block1", "block2"])
        ordered1 = MockBlock("block1", 13, parent_id="doc_token",
                           ordered=MockTextObj("First item"))
        ordered2 = MockBlock("block2", 13, parent_id="doc_token",
                           ordered=MockTextObj("Second item"))
        
        result = converter.convert([page, ordered1, ordered2])
        assert "1. First item" in result
        assert "2. Second item" in result

    def test_convert_nested_ordered_list(self):
        """Test converting nested ordered list blocks with correct numbering."""
        converter = FeishuToMarkdown()
        
        # Structure:
        # 1. Item 1
        #    1. Item 1.1
        #    2. Item 1.2
        # 2. Item 2
        
        page = MockBlock("root", 1, children=["n1", "n4"])
        n1 = MockBlock("n1", 13, parent_id="root", children=["n2", "n3"],
                      ordered=MockTextObj("Item 1"))
        n2 = MockBlock("n2", 13, parent_id="n1",
                      ordered=MockTextObj("Item 1.1"))
        n3 = MockBlock("n3", 13, parent_id="n1",
                      ordered=MockTextObj("Item 1.2"))
        n4 = MockBlock("n4", 13, parent_id="root",
                      ordered=MockTextObj("Item 2"))
        
        result = converter.convert([page, n1, n2, n3, n4])
        
        assert "1. Item 1" in result
        assert "  1. Item 1.1" in result
        assert "  2. Item 1.2" in result
        assert "2. Item 2" in result
    
    def test_convert_bold_text(self):
        """Test converting text with bold style."""
        converter = FeishuToMarkdown()
        
        page = MockBlock("doc_token", 1, children=["block1"])
        text_block = MockBlock("block1", 2, parent_id="doc_token",
                               text=MockTextObj("Bold text", bold=True))
        
        result = converter.convert([page, text_block])
        assert "**Bold text**" in result
    
    def test_convert_italic_text(self):
        """Test converting text with italic style."""
        converter = FeishuToMarkdown()
        
        page = MockBlock("doc_token", 1, children=["block1"])
        text_block = MockBlock("block1", 2, parent_id="doc_token",
                               text=MockTextObj("Italic text", italic=True))
        
        result = converter.convert([page, text_block])
        assert "*Italic text*" in result
    
    def test_convert_inline_code(self):
        """Test converting text with inline code style."""
        converter = FeishuToMarkdown()
        
        page = MockBlock("doc_token", 1, children=["block1"])
        text_block = MockBlock("block1", 2, parent_id="doc_token",
                               text=MockTextObj("code_here", inline_code=True))
        
        result = converter.convert([page, text_block])
        assert "`code_here`" in result
    
    def test_convert_quote(self):
        """Test converting quote blocks."""
        converter = FeishuToMarkdown()
        
        page = MockBlock("doc_token", 1, children=["block1"])
        quote = MockBlock("block1", 15, parent_id="doc_token",
                         quote=MockTextObj("This is a quote"))
        
        result = converter.convert([page, quote])
        assert "> This is a quote" in result
    
    def test_convert_divider(self):
        """Test converting divider blocks."""
        converter = FeishuToMarkdown()
        
        page = MockBlock("doc_token", 1, children=["block1"])
        divider = MockBlock("block1", 22, parent_id="doc_token")
        
        result = converter.convert([page, divider])
        assert "---" in result
    
    def test_convert_table(self):
        """Test converting table blocks with nested structure."""
        converter = FeishuToMarkdown()
        
        # Create table structure: Table -> TableCell -> Text
        page = MockBlock("doc_token", 1, children=["table1"])
        
        # Table block
        table_prop = Mock(row_size=2, column_size=2)
        table_obj = Mock(property=table_prop, cells=["cell1", "cell2", "cell3", "cell4"])
        table = MockBlock("table1", 31, parent_id="doc_token",
                         children=["cell1", "cell2", "cell3", "cell4"],
                         table=table_obj)
        
        # TableCell blocks with child Text blocks
        cell1 = MockBlock("cell1", 32, parent_id="table1", children=["text1"], table_cell={})
        cell2 = MockBlock("cell2", 32, parent_id="table1", children=["text2"], table_cell={})
        cell3 = MockBlock("cell3", 32, parent_id="table1", children=["text3"], table_cell={})
        cell4 = MockBlock("cell4", 32, parent_id="table1", children=["text4"], table_cell={})
        
        # Text blocks inside cells
        text1 = MockBlock("text1", 2, parent_id="cell1", text=MockTextObj("Header1"))
        text2 = MockBlock("text2", 2, parent_id="cell2", text=MockTextObj("Header2"))
        text3 = MockBlock("text3", 2, parent_id="cell3", text=MockTextObj("Data1"))
        text4 = MockBlock("text4", 2, parent_id="cell4", text=MockTextObj("Data2"))
        
        blocks = [page, table, cell1, cell2, cell3, cell4, text1, text2, text3, text4]
        result = converter.convert(blocks)
        
        # Verify table structure
        assert "| Header1 | Header2 |" in result
        assert "| --- | --- |" in result
        assert "| Data1 | Data2 |" in result
    
    def test_convert_empty_blocks(self):
        """Test converting empty block list."""
        converter = FeishuToMarkdown()
        result = converter.convert([])
        assert result == ""
    
    def test_image_block_without_downloader(self):
        """Test image block when no downloader is provided."""
        converter = FeishuToMarkdown()
        
        page = MockBlock("doc_token", 1, children=["block1"])
        image_obj = Mock(token="test_token_123")
        image = MockBlock("block1", 27, parent_id="doc_token", image=image_obj)
        
        result = converter.convert([page, image])
        assert "![Image](test_token_123)" in result
    
    def test_image_block_with_downloader(self):
        """Test image block when downloader is provided."""
        def mock_downloader(token):
            return f"/local/path/{token}.png"
        
        converter = FeishuToMarkdown(image_downloader=mock_downloader)
        
        page = MockBlock("doc_token", 1, children=["block1"])
        image_obj = Mock(token="test_token")
        image = MockBlock("block1", 27, parent_id="doc_token", image=image_obj)
        
        result = converter.convert([page, image])
        assert "![Image](/local/path/test_token.png)" in result


class TestTableProcessing:
    """Tests specifically for table processing."""
    
    def test_table_with_special_characters(self):
        """Test table cells containing pipe characters."""
        converter = FeishuToMarkdown()
        
        page = MockBlock("doc_token", 1, children=["table1"])
        
        table_prop = Mock(row_size=1, column_size=2)
        table_obj = Mock(property=table_prop, cells=["cell1", "cell2"])
        table = MockBlock("table1", 31, parent_id="doc_token",
                         children=["cell1", "cell2"], table=table_obj)
        
        cell1 = MockBlock("cell1", 32, parent_id="table1", children=["text1"], table_cell={})
        cell2 = MockBlock("cell2", 32, parent_id="table1", children=["text2"], table_cell={})
        
        text1 = MockBlock("text1", 2, parent_id="cell1", text=MockTextObj("A|B"))
        text2 = MockBlock("text2", 2, parent_id="cell2", text=MockTextObj("C|D"))
        
        blocks = [page, table, cell1, cell2, text1, text2]
        result = converter.convert(blocks)
        
        # Pipe should be escaped
        assert "A\\|B" in result or "A|B" not in result.split('\n')[0]
