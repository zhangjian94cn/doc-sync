import unittest
from unittest.mock import MagicMock, patch
import os
import tempfile
import json
import hashlib
from src.feishu_client import FeishuClient
from src.sync import FolderSyncManager

class TestSyncV2(unittest.TestCase):
    def setUp(self):
        self.patcher = patch('src.feishu_client.lark')
        self.mock_lark = self.patcher.start()
        
    def tearDown(self):
        self.patcher.stop()

    def test_upload_deduplication(self):
        # Setup
        client = FeishuClient("app", "secret")
        client._asset_cache = {}  # Empty cache
        client._save_asset_cache = MagicMock()
        client.user_access_token = "test_token"  # Avoid _get_tenant_access_token call
        
        # Create dummy file
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"content")
            path = f.name
            
        try:
            # Patch requests_module in the actual module where it's used
            with patch('src.feishu.media.requests_module') as mock_requests:
                # Setup mock response for first upload
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.json.return_value = {
                    "code": 0,
                    "data": {"file_token": "token_123"}
                }
                mock_requests.post.return_value = mock_resp
                
                # First upload
                token1 = client.upload_file(path, "parent")
                
                self.assertEqual(token1, "token_123")
                self.assertEqual(mock_requests.post.call_count, 1)
                self.assertEqual(client._save_asset_cache.call_count, 1)
                
                # Second upload (same file) - should use cache
                token2 = client.upload_file(path, "parent")
                
                self.assertEqual(token2, "token_123")
                # Still 1, no new request because it's cached
                self.assertEqual(mock_requests.post.call_count, 1)
            
        finally:
            os.remove(path)

    @patch('src.sync.folder.os.listdir')
    @patch('src.sync.folder.os.path.isdir')
    @patch('src.sync.folder.os.path.exists')
    @patch('src.sync.folder.SyncState')
    def test_sync_deletion(self, MockSyncState, mock_exists, mock_isdir, mock_listdir):
        # Setup
        client = MagicMock()
        # Mock cloud files: [kept, deleted]
        file_kept = MagicMock()
        file_kept.name = "kept"
        file_kept.type = "docx"
        file_kept.token = "token_kept"
        
        file_deleted = MagicMock()
        file_deleted.name = "deleted"
        file_deleted.type = "docx"
        file_deleted.token = "token_deleted"
        
        client.list_folder_files.return_value = [file_kept, file_deleted]
        client.delete_file.return_value = True
        
        # Mock local files: [kept.md]
        mock_listdir.return_value = ["kept.md"]
        
        # Side effect for isdir: true if item has no extension (directory), false if .md
        # In this mock we only have kept.md
        mock_isdir.return_value = False
        
        # Mock SyncState behavior
        mock_state = MockSyncState.return_value
        def get_by_token_side_effect(token):
            if token == "token_kept":
                return {"path": "/local/kept.md", "token": token}
            if token == "token_deleted":
                return {"path": "/local/deleted.md", "token": token}
            return None
        mock_state.get_by_token.side_effect = get_by_token_side_effect
        
        manager = FolderSyncManager("/local", "cloud_root", client=client)
        manager._stats_lock = MagicMock()
        
        # Run
        tasks = manager._collect_sync_tasks("/local", "cloud_root")
        
        # Verify
        # 1. kept.md should produce a task
        # Note: In new logic, it produces a task with type="sync"
        task_kept = next((t for t in tasks if t.get("doc_token") == "token_kept"), None)
        self.assertIsNotNone(task_kept)
        self.assertEqual(task_kept["local_path"], "/local/kept.md")
        
        # 2. deleted should be deleted from cloud
        # Note: In new logic, it produces a task with type="delete_cloud"
        task_deleted = next((t for t in tasks if t.get("doc_token") == "token_deleted"), None)
        self.assertIsNotNone(task_deleted)
        self.assertEqual(task_deleted["type"], "delete_cloud")
        
        # Execute to verify client call
        manager._execute_sync_task(task_deleted, MagicMock())
        client.delete_file.assert_called_once_with("token_deleted", file_type="docx")


class TestIncrementalSync(unittest.TestCase):
    """Test incremental sync block update functionality."""
    
    def setUp(self):
        self.patcher = patch('src.feishu_client.lark')
        self.mock_lark = self.patcher.start()
        
    def tearDown(self):
        self.patcher.stop()
    
    def test_try_update_block_content_matching_types(self):
        """Test that matching block types generate update requests."""
        from src.sync.manager import SyncManager
        
        with patch('src.sync.manager.config'):
            manager = SyncManager.__new__(SyncManager)
            manager.client = MagicMock()
            manager.doc_token = "test_doc"
        
            cloud_block = {
                "block_id": "cloud_block_123",
                "block_type": 2,  # text
                "text": {"elements": [{"text_run": {"content": "old content"}}]}
            }
            
            local_block = {
                "block_type": 2,  # text
                "text": {"elements": [{"text_run": {"content": "new content"}}]}
            }
            
            result = manager._try_update_block_content(cloud_block, local_block)
            
            self.assertIsNotNone(result)
            self.assertEqual(result["block_id"], "cloud_block_123")
            self.assertIn("update_text_elements", result)
    
    def test_try_update_block_content_different_types(self):
        """Test that different block types return None (no update)."""
        from src.sync.manager import SyncManager
        
        with patch('src.sync.manager.config'):
            manager = SyncManager.__new__(SyncManager)
            manager.client = MagicMock()
            manager.doc_token = "test_doc"
        
            cloud_block = {
                "block_id": "cloud_block_123",
                "block_type": 2,  # text
                "text": {"elements": [{"text_run": {"content": "content"}}]}
            }
            
            local_block = {
                "block_type": 3,  # heading1 - different from cloud
                "heading1": {"elements": [{"text_run": {"content": "heading"}}]}
            }
            
            result = manager._try_update_block_content(cloud_block, local_block)
            
            self.assertIsNone(result)
    
    def test_try_update_block_content_heading_types(self):
        """Test update for heading block types."""
        from src.sync.manager import SyncManager
        
        with patch('src.sync.manager.config'):
            manager = SyncManager.__new__(SyncManager)
            manager.client = MagicMock()
            manager.doc_token = "test_doc"
            
            for heading_num in range(1, 10):
                block_type = 2 + heading_num  # heading1=3, heading2=4, etc.
                field_name = f"heading{heading_num}"
                
                cloud_block = {
                    "block_id": f"heading_{heading_num}_id",
                    "block_type": block_type,
                    field_name: {"elements": [{"text_run": {"content": "old"}}]}
                }
                
                local_block = {
                    "block_type": block_type,
                    field_name: {"elements": [{"text_run": {"content": "new"}}]}
                }
                
                result = manager._try_update_block_content(cloud_block, local_block)
                
                self.assertIsNotNone(result, f"Failed for heading{heading_num}")
                self.assertEqual(result["block_id"], f"heading_{heading_num}_id")
    
    def test_try_update_block_content_list_types(self):
        """Test update for bullet and ordered list types."""
        from src.sync.manager import SyncManager
        
        with patch('src.sync.manager.config'):
            manager = SyncManager.__new__(SyncManager)
            manager.client = MagicMock()
            manager.doc_token = "test_doc"
            
            # Test bullet list (type 12)
            cloud_block = {
                "block_id": "bullet_id",
                "block_type": 12,
                "bullet": {"elements": [{"text_run": {"content": "old item"}}]}
            }
            local_block = {
                "block_type": 12,
                "bullet": {"elements": [{"text_run": {"content": "new item"}}]}
            }
            
            result = manager._try_update_block_content(cloud_block, local_block)
            self.assertIsNotNone(result)
            
            # Test ordered list (type 13)
            cloud_block = {
                "block_id": "ordered_id",
                "block_type": 13,
                "ordered": {"elements": [{"text_run": {"content": "old item"}}]}
            }
            local_block = {
                "block_type": 13,
                "ordered": {"elements": [{"text_run": {"content": "new item"}}]}
            }
            
            result = manager._try_update_block_content(cloud_block, local_block)
            self.assertIsNotNone(result)
