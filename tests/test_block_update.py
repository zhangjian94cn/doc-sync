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


class TestGetBlock:
    """Test get_block method."""
    
    @pytest.fixture
    def mock_client(self):
        """Create a mock FeishuClient."""
        with patch('src.feishu_client.lark') as mock_lark:
            mock_lark_client = MagicMock()
            mock_lark.Client.builder.return_value.app_id.return_value.app_secret.return_value.enable_set_token.return_value.log_level.return_value.build.return_value = mock_lark_client
            mock_lark.JSON.marshal.return_value = '{"block_type": 2, "text": {"elements": []}}'
            
            from src.feishu_client import FeishuClient
            client = FeishuClient("test_id", "test_secret", "test_token")
            client.client = mock_lark_client
            yield client
    
    def test_get_block_success(self, mock_client):
        """Test successful block retrieval."""
        mock_response = Mock()
        mock_response.success.return_value = True
        mock_response.data.block = Mock()
        mock_client.client.docx.v1.document_block.get.return_value = mock_response
        
        # Patch lark in the module where it's actually used
        with patch('src.feishu.blocks.lark') as mock_lark:
            mock_lark.JSON.marshal.return_value = '{"block_type": 2, "text": {"elements": [{"text_run": {"content": "Hello"}}]}}'
            
            result = mock_client.get_block("doc123", "block456")
        
        assert result is not None
        assert result["block_type"] == 2
        mock_client.client.docx.v1.document_block.get.assert_called_once()
    
    def test_get_block_failure(self, mock_client):
        """Test handling of API failure."""
        mock_response = Mock()
        mock_response.success.return_value = False
        mock_response.code = 404
        mock_response.msg = "Block not found"
        mock_client.client.docx.v1.document_block.get.return_value = mock_response
        
        result = mock_client.get_block("doc123", "block456")
        
        assert result is None


class TestBatchUpdateBlocks:
    """Test batch_update_blocks method."""
    
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
    
    def test_batch_update_text_elements(self, mock_client):
        """Test batch updating text elements."""
        with patch('src.feishu_client.requests_module') as mock_requests:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "code": 0,
                "data": {"blocks": [{"block_id": "block1"}, {"block_id": "block2"}]}
            }
            mock_requests.patch.return_value = mock_response
            
            requests = [
                {
                    "block_id": "block1",
                    "update_text_elements": {
                        "elements": [{"text_run": {"content": "Hello"}}]
                    }
                },
                {
                    "block_id": "block2",
                    "update_text_elements": {
                        "elements": [{"text_run": {"content": "World"}}]
                    }
                }
            ]
            
            result = mock_client.batch_update_blocks("doc123", requests)
            
            assert result is not None
            assert len(result) == 2
    
    def test_batch_update_text_style(self, mock_client):
        """Test batch updating text styles."""
        with patch('src.feishu_client.requests_module') as mock_requests:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "code": 0,
                "data": {"blocks": [{"block_id": "block1"}]}
            }
            mock_requests.patch.return_value = mock_response
            
            requests = [
                {
                    "block_id": "block1",
                    "update_text_style": {
                        "style": {"done": True, "align": 2},
                        "fields": [1, 2]
                    }
                }
            ]
            
            result = mock_client.batch_update_blocks("doc123", requests)
            
            assert result is not None
    
    def test_batch_update_table_operations(self, mock_client):
        """Test batch updating with table operations."""
        with patch('src.feishu_client.requests_module') as mock_requests:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "code": 0,
                "data": {"blocks": [{"block_id": "table1"}]}
            }
            mock_requests.patch.return_value = mock_response
            
            requests = [
                {
                    "block_id": "table1",
                    "merge_table_cells": {
                        "row_start_index": 0,
                        "row_end_index": 1,
                        "column_start_index": 0,
                        "column_end_index": 2
                    }
                }
            ]
            
            result = mock_client.batch_update_blocks("doc123", requests)
            
            assert result is not None
    
    def test_batch_update_failure(self, mock_client):
        """Test handling of batch update failure."""
        with patch('src.feishu_client.requests_module') as mock_requests:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "code": 500,
                "msg": "Internal error"
            }
            mock_requests.patch.return_value = mock_response
            
            result = mock_client.batch_update_blocks("doc123", [])
            
            assert result is None
    
    def test_batch_update_rate_limit_retry(self, mock_client):
        """Test batch update retries on rate limit."""
        with patch('src.feishu_client.requests_module') as mock_requests:
            # First call returns rate limit, second succeeds
            mock_response_429 = Mock()
            mock_response_429.status_code = 429
            
            mock_response_ok = Mock()
            mock_response_ok.status_code = 200
            mock_response_ok.json.return_value = {
                "code": 0,
                "data": {"blocks": [{"block_id": "block1"}]}
            }
            
            mock_requests.patch.side_effect = [mock_response_429, mock_response_ok]
            
            result = mock_client.batch_update_blocks("doc123", [{"block_id": "block1"}])
            
            # Should succeed after retry
            assert result is not None


class TestGetBlockChildren:
    """Test get_block_children method."""
    
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
    
    def test_get_children_success(self, mock_client):
        """Test successful retrieval of child blocks."""
        with patch('src.feishu.blocks.requests_module') as mock_requests:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "code": 0,
                "data": {
                    "items": [
                        {"block_id": "block1", "block_type": 2},
                        {"block_id": "block2", "block_type": 3}
                    ]
                }
            }
            mock_requests.get.return_value = mock_response
            
            result = mock_client.get_block_children("doc123", "doc123")
            
            assert result is not None
            assert len(result) == 2
            assert result[0]["block_id"] == "block1"
    
    def test_get_children_with_descendants(self, mock_client):
        """Test retrieval with descendants flag."""
        with patch('src.feishu.blocks.requests_module') as mock_requests:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "code": 0,
                "data": {
                    "items": [
                        {"block_id": "table1", "block_type": 31},
                        {"block_id": "cell1", "block_type": 32},
                        {"block_id": "text1", "block_type": 2},
                        {"block_id": "cell2", "block_type": 32}
                    ]
                }
            }
            mock_requests.get.return_value = mock_response
            
            result = mock_client.get_block_children(
                "doc123", "table_block_id", with_descendants=True
            )
            
            assert result is not None
            assert len(result) == 4
            # Verify params include with_descendants
            mock_requests.get.assert_called_once()
    
    def test_get_children_pagination(self, mock_client):
        """Test pagination handling."""
        with patch('src.feishu.blocks.requests_module') as mock_requests:
            # First page with page_token
            page1_response = Mock()
            page1_response.status_code = 200
            page1_response.json.return_value = {
                "code": 0,
                "data": {
                    "items": [{"block_id": "block1"}],
                    "page_token": "next_page_token"
                }
            }
            
            # Second page without page_token
            page2_response = Mock()
            page2_response.status_code = 200
            page2_response.json.return_value = {
                "code": 0,
                "data": {
                    "items": [{"block_id": "block2"}]
                }
            }
            
            mock_requests.get.side_effect = [page1_response, page2_response]
            
            result = mock_client.get_block_children("doc123", "doc123")
            
            assert result is not None
            assert len(result) == 2
            assert mock_requests.get.call_count == 2
    
    def test_get_children_failure(self, mock_client):
        """Test handling of API failure."""
        with patch('src.feishu.blocks.requests_module') as mock_requests:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "code": 500,
                "msg": "Internal error"
            }
            mock_requests.get.return_value = mock_response
            
            result = mock_client.get_block_children("doc123", "doc123")
            
            assert result is None
    
    def test_get_children_rate_limit_retry(self, mock_client):
        """Test rate limit retry logic."""
        with patch('src.feishu.blocks.requests_module') as mock_requests:
            # First call returns rate limit error in body, second succeeds
            mock_response_limited = Mock()
            mock_response_limited.status_code = 200
            mock_response_limited.json.return_value = {
                "code": 99991400,
                "msg": "rate limit exceeded"
            }
            
            mock_response_ok = Mock()
            mock_response_ok.status_code = 200
            mock_response_ok.json.return_value = {
                "code": 0,
                "data": {"items": [{"block_id": "block1"}]}
            }
            
            mock_requests.get.side_effect = [mock_response_limited, mock_response_ok]
            
            result = mock_client.get_block_children("doc123", "doc123")
            
            assert result is not None
            assert len(result) == 1


class TestDeleteBlockChildren:
    """Test delete_block_children method."""
    
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
    
    def test_delete_children_success(self, mock_client):
        """Test successful deletion of child blocks."""
        mock_response = Mock()
        mock_response.success.return_value = True
        mock_client.client.docx.v1.document_block_children.batch_delete.return_value = mock_response
        
        result = mock_client.delete_block_children("doc123", "block456", 0, 2)
        
        # Now returns bool, not dict
        assert result is True
    
    def test_delete_children_with_client_token(self, mock_client):
        """Test deletion with idempotency token."""
        mock_response = Mock()
        mock_response.success.return_value = True
        mock_client.client.docx.v1.document_block_children.batch_delete.return_value = mock_response
        
        result = mock_client.delete_block_children(
            "doc123", "block456", 1, 3, client_token="my-token"
        )
        
        # Now returns bool, not dict
        assert result is True
    
    def test_delete_children_failure(self, mock_client):
        """Test handling of API failure."""
        mock_response = Mock()
        mock_response.success.return_value = False
        mock_response.code = 1770001
        mock_response.msg = "invalid param"
        mock_client.client.docx.v1.document_block_children.batch_delete.return_value = mock_response
        
        result = mock_client.delete_block_children("doc123", "block456", 0, 1)
        
        # Now returns False instead of None
        assert result is False
    
    def test_delete_children_rate_limit_retry(self, mock_client):
        """Test rate limit retry logic."""
        # First call returns rate limit, second succeeds
        mock_response_limited = Mock()
        mock_response_limited.success.return_value = False
        mock_response_limited.code = 99991400
        mock_response_limited.msg = "rate limited"
        
        mock_response_ok = Mock()
        mock_response_ok.success.return_value = True
        
        mock_client.client.docx.v1.document_block_children.batch_delete.side_effect = [
            mock_response_limited, mock_response_ok
        ]
        
        result = mock_client.delete_block_children("doc123", "block456", 0, 1)
        
        # Now returns bool
        assert result is True


class TestConvertContentToBlocks:
    """Test convert_content_to_blocks method."""
    
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
    
    def test_convert_markdown_success(self, mock_client):
        """Test successful Markdown conversion."""
        with patch('src.feishu_client.requests_module') as mock_requests:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "code": 0,
                "data": {
                    "first_level_block_ids": ["block1", "block2"],
                    "blocks": [
                        {"block_id": "block1", "block_type": 3, "heading1": {}},
                        {"block_id": "block2", "block_type": 2, "text": {}}
                    ]
                }
            }
            mock_requests.post.return_value = mock_response
            
            result = mock_client.convert_content_to_blocks("# Hello\n\nWorld")
            
            assert result is not None
            assert len(result["first_level_block_ids"]) == 2
            assert len(result["blocks"]) == 2
    
    def test_convert_html_content(self, mock_client):
        """Test HTML content conversion."""
        with patch('src.feishu_client.requests_module') as mock_requests:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "code": 0,
                "data": {
                    "first_level_block_ids": ["block1"],
                    "blocks": [{"block_id": "block1", "block_type": 2}]
                }
            }
            mock_requests.post.return_value = mock_response
            
            result = mock_client.convert_content_to_blocks(
                "<p>Hello <strong>World</strong></p>",
                content_type="html"
            )
            
            assert result is not None
            mock_requests.post.assert_called_once()
    
    def test_convert_with_table(self, mock_client):
        """Test conversion with table content."""
        with patch('src.feishu_client.requests_module') as mock_requests:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "code": 0,
                "data": {
                    "first_level_block_ids": ["table1"],
                    "blocks": [
                        {"block_id": "table1", "block_type": 31, "table": {"merge_info": {}}},
                        {"block_id": "cell1", "block_type": 32}
                    ]
                }
            }
            mock_requests.post.return_value = mock_response
            
            result = mock_client.convert_content_to_blocks("|A|B|\n|--|--|\n|1|2|")
            
            assert result is not None
            assert len(result["blocks"]) == 2
    
    def test_convert_failure(self, mock_client):
        """Test handling of conversion failure."""
        with patch('src.feishu_client.requests_module') as mock_requests:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "code": 1770001,
                "msg": "invalid param"
            }
            mock_requests.post.return_value = mock_response
            
            result = mock_client.convert_content_to_blocks("")
            
            assert result is None
    
    def test_convert_rate_limit_retry(self, mock_client):
        """Test rate limit retry logic."""
        with patch('src.feishu_client.requests_module') as mock_requests:
            mock_response_429 = Mock()
            mock_response_429.status_code = 429
            
            mock_response_ok = Mock()
            mock_response_ok.status_code = 200
            mock_response_ok.json.return_value = {
                "code": 0,
                "data": {
                    "first_level_block_ids": ["block1"],
                    "blocks": [{"block_id": "block1"}]
                }
            }
            
            mock_requests.post.side_effect = [mock_response_429, mock_response_ok]
            
            result = mock_client.convert_content_to_blocks("# Test")
            
            assert result is not None
