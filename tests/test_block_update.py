"""Tests for block update functionality."""
import pytest
from unittest.mock import Mock, patch, MagicMock


class TestUpdateBlockText:
    """Test update_block_text method."""
    
    @pytest.fixture
    def mock_client(self):
        """Create a mock FeishuClient."""
        with patch('src.feishu_client.lark') as mock_lark:
            mock_lark_client = MagicMock()
            mock_lark.Client.builder.return_value.app_id.return_value.app_secret.return_value.enable_set_token.return_value.log_level.return_value.build.return_value = mock_lark_client
            
            from src.feishu_client import FeishuClient
            client = FeishuClient("test_id", "test_secret", "test_token")
            client.client = mock_lark_client
            yield client
    
    def test_update_text_run_basic(self, mock_client):
        """Test updating with basic text content."""
        # Setup mock response
        mock_response = Mock()
        mock_response.success.return_value = True
        mock_client.client.docx.v1.document_block.patch.return_value = mock_response
        
        elements = [
            {"text_run": {"content": "Hello World"}}
        ]
        
        result = mock_client.update_block_text("doc123", "block456", elements)
        
        assert result is True
        mock_client.client.docx.v1.document_block.patch.assert_called_once()
    
    def test_update_text_with_styles(self, mock_client):
        """Test updating with styled text."""
        mock_response = Mock()
        mock_response.success.return_value = True
        mock_client.client.docx.v1.document_block.patch.return_value = mock_response
        
        elements = [
            {
                "text_run": {
                    "content": "Styled text",
                    "text_element_style": {
                        "bold": True,
                        "italic": True,
                        "strikethrough": True,
                        "underline": True,
                        "text_color": 2,
                        "background_color": 3
                    }
                }
            }
        ]
        
        result = mock_client.update_block_text("doc123", "block456", elements)
        
        assert result is True
    
    def test_update_mention_user(self, mock_client):
        """Test updating with @user mention."""
        mock_response = Mock()
        mock_response.success.return_value = True
        mock_client.client.docx.v1.document_block.patch.return_value = mock_response
        
        elements = [
            {"mention_user": {"user_id": "ou_xxx123"}}
        ]
        
        result = mock_client.update_block_text("doc123", "block456", elements)
        
        assert result is True
    
    def test_update_mention_doc(self, mock_client):
        """Test updating with @doc mention."""
        mock_response = Mock()
        mock_response.success.return_value = True
        mock_client.client.docx.v1.document_block.patch.return_value = mock_response
        
        elements = [
            {
                "mention_doc": {
                    "token": "doctoken123",
                    "obj_type": 1,
                    "url": "https://feishu.cn/docx/doctoken123"
                }
            }
        ]
        
        result = mock_client.update_block_text("doc123", "block456", elements)
        
        assert result is True
    
    def test_update_reminder(self, mock_client):
        """Test updating with reminder."""
        mock_response = Mock()
        mock_response.success.return_value = True
        mock_client.client.docx.v1.document_block.patch.return_value = mock_response
        
        elements = [
            {
                "reminder": {
                    "create_user_id": "ou_xxx123",
                    "expire_time": "1647961200000",
                    "notify_time": "1647961200000"
                }
            }
        ]
        
        result = mock_client.update_block_text("doc123", "block456", elements)
        
        assert result is True
    
    def test_update_mixed_elements(self, mock_client):
        """Test updating with multiple element types."""
        mock_response = Mock()
        mock_response.success.return_value = True
        mock_client.client.docx.v1.document_block.patch.return_value = mock_response
        
        elements = [
            {"mention_user": {"user_id": "ou_xxx123"}},
            {"text_run": {"content": " 测试", "text_element_style": {"bold": True}}},
            {"text_run": {"content": "文本", "text_element_style": {"italic": True}}},
            {"mention_doc": {"token": "docxxx", "obj_type": 1, "url": "https://..."}}
        ]
        
        result = mock_client.update_block_text("doc123", "block456", elements)
        
        assert result is True
    
    def test_update_failure(self, mock_client):
        """Test handling of API failure."""
        mock_response = Mock()
        mock_response.success.return_value = False
        mock_response.code = 500
        mock_response.msg = "Server error"
        mock_client.client.docx.v1.document_block.patch.return_value = mock_response
        
        elements = [{"text_run": {"content": "Test"}}]
        
        result = mock_client.update_block_text("doc123", "block456", elements)
        
        assert result is False
    
    def test_update_empty_elements(self, mock_client):
        """Test updating with empty elements list."""
        mock_response = Mock()
        mock_response.success.return_value = True
        mock_client.client.docx.v1.document_block.patch.return_value = mock_response
        
        result = mock_client.update_block_text("doc123", "block456", [])
        
        assert result is True
