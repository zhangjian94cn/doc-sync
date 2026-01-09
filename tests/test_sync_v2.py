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
        client._asset_cache = {} # Empty cache
        client._save_asset_cache = MagicMock()
        
        # Create dummy file
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"content")
            path = f.name
            
        try:
            # First upload
            client.client.drive.v1.media.upload_all = MagicMock()
            mock_resp = MagicMock()
            mock_resp.success.return_value = True
            mock_resp.data.file_token = "token_123"
            client.client.drive.v1.media.upload_all.return_value = mock_resp
            
            token1 = client.upload_file(path, "parent")
            
            self.assertEqual(token1, "token_123")
            self.assertEqual(client.client.drive.v1.media.upload_all.call_count, 1)
            self.assertEqual(client._save_asset_cache.call_count, 1)
            
            # Second upload (same file)
            token2 = client.upload_file(path, "parent")
            
            self.assertEqual(token2, "token_123")
            self.assertEqual(client.client.drive.v1.media.upload_all.call_count, 1) # Still 1, no new call
            
        finally:
            os.remove(path)

    @patch('src.sync.os.listdir')
    @patch('src.sync.os.path.isdir')
    @patch('src.sync.os.path.exists')
    def test_sync_deletion(self, mock_exists, mock_isdir, mock_listdir):
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
        
        manager = FolderSyncManager("/local", "cloud_root", client=client)
        
        # Run
        tasks = manager._collect_sync_tasks("/local", "cloud_root")
        
        # Verify
        # 1. kept.md should produce a task
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["local_path"], "/local/kept.md")
        self.assertEqual(tasks[0]["doc_token"], "token_kept")
        
        # 2. deleted should be deleted from cloud
        client.delete_file.assert_called_once_with("token_deleted", file_type="docx")
