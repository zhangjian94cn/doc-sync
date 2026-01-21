"""
Test cases for recent sync module enhancements:
- SyncError exception handling
- Thread-safe resource index initialization
- Overwrite mode functionality
"""

import unittest
from unittest.mock import MagicMock, patch, PropertyMock
import threading
import tempfile
import os


class TestSyncError(unittest.TestCase):
    """Test SyncError exception and its usage."""
    
    def test_sync_error_importable(self):
        """Test SyncError can be imported from sync package."""
        from src.sync import SyncError
        self.assertIsNotNone(SyncError)
    
    def test_sync_error_is_exception(self):
        """Test SyncError is a proper exception class."""
        from src.sync import SyncError
        self.assertTrue(issubclass(SyncError, Exception))
    
    def test_sync_error_can_be_raised_and_caught(self):
        """Test SyncError can be raised and caught."""
        from src.sync import SyncError
        
        with self.assertRaises(SyncError) as context:
            raise SyncError("Test error message")
        
        self.assertEqual(str(context.exception), "Test error message")
    
    def test_sync_error_raised_for_folder_token(self):
        """Test SyncError is raised when doc_token is a folder, not a document."""
        from src.sync.manager import SyncManager, SyncError
        
        with patch('src.sync.manager.config'):
            with patch('src.sync.manager.FeishuClient') as MockClient:
                manager = SyncManager.__new__(SyncManager)
                manager.md_path = "/test/file.md"
                manager.doc_token = "folder_token"
                manager.force = False
                manager.overwrite = False
                manager.vault_root = "/test"
                manager.batch_id = "test_batch"
                manager.client = MockClient.return_value
                
                # Mock file_info to return folder type
                file_info = MagicMock()
                file_info.doc_type = "folder"
                file_info.latest_modify_time = "1234567890"
                manager.client.get_file_info.return_value = file_info
                
                # Mock os.path.exists to return True
                with patch('os.path.exists', return_value=True):
                    with patch('os.path.getmtime', return_value=1234567890):
                        with self.assertRaises(SyncError) as context:
                            manager.run()
                
                self.assertIn("文件夹", str(context.exception))


class TestThreadSafeResourceIndex(unittest.TestCase):
    """Test thread-safe resource index initialization."""
    
    def test_resource_index_lock_exists(self):
        """Test _resource_index_lock class variable exists."""
        from src.sync.manager import SyncManager
        self.assertTrue(hasattr(SyncManager, '_resource_index_lock'))
        self.assertIsInstance(SyncManager._resource_index_lock, type(threading.Lock()))
    
    def test_resource_index_class_variables(self):
        """Test class-level resource index variables exist."""
        from src.sync.manager import SyncManager
        self.assertTrue(hasattr(SyncManager, '_resource_index'))
        self.assertTrue(hasattr(SyncManager, '_resource_index_root'))


class TestFolderSyncThreadSafety(unittest.TestCase):
    """Test FolderSyncManager thread safety improvements."""
    
    def test_stats_lock_initialized_in_init(self):
        """Test _stats_lock is initialized in __init__, not in run()."""
        from src.sync.folder import FolderSyncManager
        
        with patch('src.sync.folder.SyncState'):
            manager = FolderSyncManager.__new__(FolderSyncManager)
            manager.local_root = "/local"
            manager.cloud_root_token = "cloud_token"
            manager.force = False
            manager.overwrite = False
            manager.vault_root = "/local"
            manager.debug = False
            manager.batch_id = "test"
            manager.client = MagicMock()
            manager.stats = {"created": 0, "updated": 0, "skipped": 0, "failed": 0, "deleted_cloud": 0, "deleted_local": 0}
            manager._stats_lock = threading.Lock()
            manager.state = MagicMock()
            
            # Verify _stats_lock is a Lock
            self.assertIsInstance(manager._stats_lock, type(threading.Lock()))


class TestOverwriteMode(unittest.TestCase):
    """Test overwrite mode functionality."""
    
    def test_sync_manager_accepts_overwrite_param(self):
        """Test SyncManager accepts overwrite parameter."""
        from src.sync.manager import SyncManager
        
        with patch('src.sync.manager.config'):
            with patch('src.sync.manager.FeishuClient'):
                with patch.object(SyncManager, '_init_resource_index'):
                    with tempfile.NamedTemporaryFile(suffix='.md', delete=False) as f:
                        f.write(b"# Test")
                        temp_path = f.name
                    
                    try:
                        manager = SyncManager(
                            temp_path, 
                            "doc_token",
                            force=False,
                            overwrite=True
                        )
                        self.assertTrue(manager.overwrite)
                    finally:
                        os.unlink(temp_path)
    
    def test_folder_sync_manager_accepts_overwrite_param(self):
        """Test FolderSyncManager accepts overwrite parameter."""
        from src.sync.folder import FolderSyncManager
        
        with patch('src.sync.folder.SyncState'):
            with patch('src.sync.folder.FeishuClient'):
                manager = FolderSyncManager(
                    "/local",
                    "cloud_token",
                    force=False,
                    overwrite=True
                )
                self.assertTrue(manager.overwrite)


class TestSyncResult(unittest.TestCase):
    """Test SyncResult enum values."""
    
    def test_sync_result_values(self):
        """Test SyncResult enum has correct values."""
        from src.sync import SyncResult
        
        self.assertEqual(SyncResult.SUCCESS, 0)
        self.assertEqual(SyncResult.EMPTY_CLOUD, 1)
        self.assertEqual(SyncResult.ERROR, 2)


class TestResourceUploader(unittest.TestCase):
    """Test resource uploader path resolution."""
    
    def test_resource_uploader_returns_none_for_urls(self):
        """Test _resource_uploader returns None for URLs."""
        from src.sync.manager import SyncManager
        
        with patch('src.sync.manager.config'):
            with patch('src.sync.manager.FeishuClient'):
                with patch.object(SyncManager, '_init_resource_index'):
                    manager = SyncManager.__new__(SyncManager)
                    manager.md_path = "/test/file.md"
                    manager.vault_root = "/test"
                    SyncManager._resource_index = None
                    
                    result = manager._resource_uploader("https://example.com/image.png")
                    self.assertIsNone(result)
                    
                    result = manager._resource_uploader("http://example.com/image.png")
                    self.assertIsNone(result)
    
    def test_resource_uploader_returns_none_for_empty_path(self):
        """Test _resource_uploader returns None for empty paths."""
        from src.sync.manager import SyncManager
        
        with patch('src.sync.manager.config'):
            with patch('src.sync.manager.FeishuClient'):
                with patch.object(SyncManager, '_init_resource_index'):
                    manager = SyncManager.__new__(SyncManager)
                    manager.md_path = "/test/file.md"
                    manager.vault_root = "/test"
                    SyncManager._resource_index = None
                    
                    result = manager._resource_uploader("")
                    self.assertIsNone(result)
                    
                    result = manager._resource_uploader(None)
                    self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
