"""
Live Sync Module

Provides real-time collaborative block editing via WebSocket server.

Usage:
    from doc_sync.live.lock_manager import LockManager
    from doc_sync.live.live_server import LiveSyncServer
"""


def __getattr__(name):
    """Lazy imports to avoid loading heavy dependencies (FeishuClient) at import time."""
    if name == "LockManager":
        from doc_sync.live.lock_manager import LockManager
        return LockManager
    if name == "LiveSyncServer":
        from doc_sync.live.live_server import LiveSyncServer
        return LiveSyncServer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["LockManager", "LiveSyncServer"]
