"""
Unit tests for the converter module.
"""

import pytest
from src.converter import MarkdownToFeishu, FeishuToMarkdown


class TestMarkdownToFeishu:
    """Tests for MarkdownToFeishu converter."""
    
    def test_parse_heading(self):
        """Test parsing markdown headings."""
        converter = MarkdownToFeishu()
        
        # Test H1
        blocks = converter.parse("# Heading 1")
        assert len(blocks) == 1
        assert blocks[0]["block_type"] == 3  # heading1 = 3
        assert blocks[0]["heading1"]["elements"][0]["text_run"]["content"] == "Heading 1"
        
        # Test H2
        blocks = converter.parse("## Heading 2")
        assert len(blocks) == 1
        assert blocks[0]["block_type"] == 4  # heading2 = 4
    
    def test_parse_paragraph(self):
        """Test parsing simple paragraphs."""
        converter = MarkdownToFeishu()
        blocks = converter.parse("This is a simple paragraph.")
        
        assert len(blocks) == 1
        assert blocks[0]["block_type"] == 2  # text = 2
    
    def test_parse_bold_text(self):
        """Test parsing bold text."""
        converter = MarkdownToFeishu()
        blocks = converter.parse("This is **bold** text")
        
        assert len(blocks) == 1
        elements = blocks[0]["text"]["elements"]
        
        # Find the bold element
        bold_elements = [e for e in elements if e.get("text_run", {}).get("text_element_style", {}).get("bold")]
        assert len(bold_elements) == 1
        assert bold_elements[0]["text_run"]["content"] == "bold"
    
    def test_parse_italic_text(self):
        """Test parsing italic text."""
        converter = MarkdownToFeishu()
        blocks = converter.parse("This is *italic* text")
        
        assert len(blocks) == 1
        elements = blocks[0]["text"]["elements"]
        
        # Find the italic element
        italic_elements = [e for e in elements if e.get("text_run", {}).get("text_element_style", {}).get("italic")]
        assert len(italic_elements) == 1
        assert italic_elements[0]["text_run"]["content"] == "italic"
    
    def test_parse_inline_code(self):
        """Test parsing inline code."""
        converter = MarkdownToFeishu()
        blocks = converter.parse("Use `code` here")
        
        assert len(blocks) == 1
        elements = blocks[0]["text"]["elements"]
        
        # Find the inline code element
        code_elements = [e for e in elements if e.get("text_run", {}).get("text_element_style", {}).get("inline_code")]
        assert len(code_elements) == 1
        assert code_elements[0]["text_run"]["content"] == "code"
    
    def test_parse_code_block(self):
        """Test parsing fenced code blocks."""
        converter = MarkdownToFeishu()
        md = """```python
def hello():
    pass
```"""
        blocks = converter.parse(md)
        
        assert len(blocks) == 1
        assert blocks[0]["block_type"] == 14  # code = 14
        assert "def hello():" in blocks[0]["code"]["elements"][0]["text_run"]["content"]
    
    def test_parse_bullet_list(self):
        """Test parsing bullet lists."""
        converter = MarkdownToFeishu()
        md = """- Item 1
- Item 2
- Item 3"""
        blocks = converter.parse(md)
        
        assert len(blocks) == 3
        for block in blocks:
            assert block["block_type"] == 12  # bullet = 12
    
    def test_parse_ordered_list(self):
        """Test parsing ordered lists."""
        converter = MarkdownToFeishu()
        md = """1. First
2. Second
3. Third"""
        blocks = converter.parse(md)
        
        assert len(blocks) == 3
        for block in blocks:
            assert block["block_type"] == 13  # ordered = 13
    
    def test_parse_nested_list(self):
        """Test parsing nested lists."""
        converter = MarkdownToFeishu()
        md = """- Parent
    - Child 1
    - Child 2
- Another parent"""
        blocks = converter.parse(md)
        
        # Should have 2 root level items
        assert len(blocks) == 2
        # First block should have children
        assert "children" in blocks[0]
        assert len(blocks[0]["children"]) == 2
    
    def test_parse_image(self):
        """Test parsing image references."""
        def mock_uploader(path):
            return f"/absolute/path/to/{path}"
        
        converter = MarkdownToFeishu(image_uploader=mock_uploader)
        blocks = converter.parse("![Alt text](image.png)")
        
        # Should create an image block
        image_blocks = [b for b in blocks if b.get("block_type") == 27]
        assert len(image_blocks) == 1
    
    def test_parse_wiki_link(self):
        """Test parsing Obsidian wiki-style image links."""
        def mock_uploader(path):
            return f"/absolute/path/to/{path}"
        
        converter = MarkdownToFeishu(image_uploader=mock_uploader)
        blocks = converter.parse("![[image.png]]")
        
        # Should create an image block  
        image_blocks = [b for b in blocks if b.get("block_type") == 27]
        assert len(image_blocks) == 1
    
    def test_parse_complex_document(self, sample_markdown):
        """Test parsing a complex markdown document."""
        converter = MarkdownToFeishu()
        blocks = converter.parse(sample_markdown)
        
        # Should have multiple blocks
        assert len(blocks) > 5
        
        # Should have variety of block types
        block_types = set(b["block_type"] for b in blocks)
        assert 3 in block_types  # heading1
        assert 5 in block_types  # heading3
        assert 12 in block_types  # bullet
        assert 13 in block_types  # ordered
        assert 14 in block_types  # code


class TestFeishuToMarkdown:
    """Tests for FeishuToMarkdown converter."""
    
    # Note: These tests require mocking Feishu block objects
    # For now, we just test that the class can be instantiated
    
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
