"""
Sync Module Package

Provides synchronization between local files and Feishu documents/Bitable.

Structure:
    - manager.py: SyncManager - single file synchronization
    - folder.py: FolderSyncManager - folder-level synchronization
    - bitable_sync.py: BitableSyncManager - Bitable synchronization
    - resource.py: ResourceIndex - resource file lookup

Usage:
    from doc_sync.sync import SyncManager, FolderSyncManager
    from doc_sync.sync import BitableSyncManager
"""

from doc_sync.sync.manager import SyncManager, SyncResult, SyncError
from doc_sync.sync.folder import FolderSyncManager
from doc_sync.sync.resource import ResourceIndex
from doc_sync.sync.bitable_sync import BitableSyncManager, BitableSyncResult

__all__ = ['SyncManager', 'FolderSyncManager', 'SyncResult', 'SyncError', 'ResourceIndex',
           'BitableSyncManager', 'BitableSyncResult']
