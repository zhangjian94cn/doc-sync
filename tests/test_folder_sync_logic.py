import unittest
from unittest.mock import MagicMock, patch
import os
from src.sync.folder import FolderSyncManager

class TestFolderSyncLogic(unittest.TestCase):
    def setUp(self):
        # Mock dependencies
        self.client_mock = MagicMock()
        self.state_mock = MagicMock()
        
        # Patch SyncState to return our mock
        self.state_patcher = patch('src.sync.folder.SyncState', return_value=self.state_mock)
        self.state_patcher.start()
        
    def tearDown(self):
        self.state_patcher.stop()

    @patch('src.sync.folder.os.listdir')
    @patch('src.sync.folder.os.path.isdir')
    @patch('src.sync.folder.os.path.exists')
    @patch('src.sync.folder.os.makedirs')
    def test_collect_tasks_logic(self, mock_makedirs, mock_exists, mock_isdir, mock_listdir):
        # Setup common mocks
        manager = FolderSyncManager("/local", "cloud_root", client=self.client_mock)
        
        # 1. Setup Local Files
        # - local_doc.md (exists)
        mock_listdir.return_value = ["local_doc.md"]
        
        # Helper to handle isdir/exists calls
        def isdir_side_effect(path):
            return False # No folders locally
        mock_isdir.side_effect = isdir_side_effect
        
        # 2. Setup Cloud Files
        # - local_doc (matches local_doc.md)
        # - cloud_only_doc (new on cloud)
        # - deleted_local_doc (was local, now deleted)
        
        cloud_file1 = MagicMock()
        cloud_file1.name = "local_doc"
        cloud_file1.type = "docx"
        cloud_file1.token = "token_local_doc"
        
        cloud_file2 = MagicMock()
        cloud_file2.name = "cloud_only_doc"
        cloud_file2.type = "docx"
        cloud_file2.token = "token_cloud_only"
        
        cloud_file3 = MagicMock()
        cloud_file3.name = "deleted_local_doc"
        cloud_file3.type = "docx"
        cloud_file3.token = "token_deleted"
        
        self.client_mock.list_folder_files.return_value = [cloud_file1, cloud_file2, cloud_file3]
        
        # 3. Setup SyncState
        # - token_local_doc: known
        # - token_deleted: known (so we know it was deleted locally)
        # - token_cloud_only: unknown (so it's new on cloud)
        
        def get_by_token_side_effect(token):
            if token == "token_local_doc":
                return {"path": "local_doc.md", "token": token}
            if token == "token_deleted":
                return {"path": "deleted_local_doc.md", "token": token}
            return None # Unknown
        
        self.state_mock.get_by_token.side_effect = get_by_token_side_effect
        
        # Run collection
        tasks = manager._collect_sync_tasks("/local", "cloud_root")
        
        # Verify Tasks
        
        # Task 1: local_doc.md -> Sync (Update)
        # It exists locally and on cloud.
        task_sync = next((t for t in tasks if t.get("local_path") == "/local/local_doc.md"), None)
        self.assertIsNotNone(task_sync)
        self.assertEqual(task_sync["type"], "sync")
        self.assertEqual(task_sync["doc_token"], "token_local_doc")
        
        # Task 2: cloud_only_doc -> Download (Sync with is_new=False but implicit download logic in Manager)
        # It's new on cloud (not in state), so we should sync it to local.
        task_download = next((t for t in tasks if t.get("local_path") == "/local/cloud_only_doc.md"), None)
        self.assertIsNotNone(task_download)
        self.assertEqual(task_download["type"], "sync")
        self.assertEqual(task_download["doc_token"], "token_cloud_only")
        
        # Task 3: deleted_local_doc -> Delete Cloud
        # It's in state but not in local files -> Local deletion.
        task_delete = next((t for t in tasks if t.get("doc_token") == "token_deleted"), None)
        self.assertIsNotNone(task_delete)
        self.assertEqual(task_delete["type"], "delete_cloud")

    @patch('src.sync.folder.os.listdir')
    @patch('src.sync.folder.os.path.isdir')
    def test_collect_tasks_new_local_file(self, mock_isdir, mock_listdir):
        manager = FolderSyncManager("/local", "cloud_root", client=self.client_mock)
        
        # Local has new_file.md
        mock_listdir.return_value = ["new_file.md"]
        mock_isdir.return_value = False
        
        # Cloud is empty
        self.client_mock.list_folder_files.return_value = []
        
        # Client create_docx returns new token
        self.client_mock.create_docx.return_value = "new_token_123"
        
        tasks = manager._collect_sync_tasks("/local", "cloud_root")
        
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["type"], "sync")
        self.assertEqual(tasks[0]["is_new"], True)
        self.assertEqual(tasks[0]["doc_token"], "new_token_123")
        
        # Verify create_docx called
        self.client_mock.create_docx.assert_called_with("cloud_root", "new_file")
        
        # Verify state updated
        self.state_mock.update.assert_called_with("/local/new_file.md", "new_token_123")
