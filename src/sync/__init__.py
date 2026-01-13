"""
Sync Module Package

Provides synchronization between local Markdown files and Feishu documents.

Structure:
    - manager.py: SyncManager - single file synchronization
    - folder.py: FolderSyncManager - folder-level synchronization
    - resource.py: ResourceIndex - resource file lookup

Usage:
    from src.sync import SyncManager, FolderSyncManager
"""

from src.sync.manager import SyncManager, SyncResult, SyncError
from src.sync.folder import FolderSyncManager
from src.sync.resource import ResourceIndex

__all__ = ['SyncManager', 'FolderSyncManager', 'SyncResult', 'SyncError', 'ResourceIndex']
