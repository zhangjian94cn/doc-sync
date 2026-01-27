"""
Sync Module Package

Provides synchronization between local Markdown files and Feishu documents.

Structure:
    - manager.py: SyncManager - single file synchronization
    - folder.py: FolderSyncManager - folder-level synchronization
    - resource.py: ResourceIndex - resource file lookup

Usage:
    from doc_sync.sync import SyncManager, FolderSyncManager
"""

from doc_sync.sync.manager import SyncManager, SyncResult, SyncError
from doc_sync.sync.folder import FolderSyncManager
from doc_sync.sync.resource import ResourceIndex

__all__ = ['SyncManager', 'FolderSyncManager', 'SyncResult', 'SyncError', 'ResourceIndex']
