"""Tests for Checkbox/Todo conversion."""
import pytest
from doc_sync.converter import MarkdownToFeishu


class TestCheckboxConversion:
    """Test Obsidian checkbox to Feishu Todo block conversion."""
    
    def test_unchecked_checkbox(self):
        """Test unchecked checkbox - [ ] converts to todo with done=False."""
        md = "- [ ] 未完成任务"
        converter = MarkdownToFeishu()
        blocks = converter.parse(md)
        
        assert len(blocks) == 1
        assert blocks[0]["block_type"] == 17  # Feishu Todo is type 17
        assert blocks[0]["todo"]["style"]["done"] == False
        elements = blocks[0]["todo"]["elements"]
        assert any("未完成任务" in e.get("text_run", {}).get("content", "") for e in elements)
    
    def test_checked_checkbox(self):
        """Test checked checkbox - [x] converts to todo with done=True."""
        md = "- [x] 已完成任务"
        converter = MarkdownToFeishu()
        blocks = converter.parse(md)
        
        assert len(blocks) == 1
        assert blocks[0]["block_type"] == 17
        assert blocks[0]["todo"]["style"]["done"] == True
        elements = blocks[0]["todo"]["elements"]
        assert any("已完成任务" in e.get("text_run", {}).get("content", "") for e in elements)
    
    def test_checked_uppercase_checkbox(self):
        """Test checked checkbox with uppercase X."""
        md = "- [X] Task with uppercase X"
        converter = MarkdownToFeishu()
        blocks = converter.parse(md)
        
        assert blocks[0]["block_type"] == 17
        assert blocks[0]["todo"]["style"]["done"] == True
    
    def test_regular_list_unchanged(self):
        """Test that regular bullet list is not affected."""
        md = "- 普通列表项"
        converter = MarkdownToFeishu()
        blocks = converter.parse(md)
        
        assert len(blocks) == 1
        assert blocks[0]["block_type"] == 12  # bullet
    
    def test_multiple_checkboxes(self):
        """Test multiple checkboxes in a list."""
        md = """- [ ] 任务1
- [x] 任务2
- [ ] 任务3"""
        converter = MarkdownToFeishu()
        blocks = converter.parse(md)
        
        assert len(blocks) == 3
        assert blocks[0]["block_type"] == 17
        assert blocks[0]["todo"]["style"]["done"] == False
        assert blocks[1]["block_type"] == 17
        assert blocks[1]["todo"]["style"]["done"] == True
        assert blocks[2]["block_type"] == 17
        assert blocks[2]["todo"]["style"]["done"] == False
