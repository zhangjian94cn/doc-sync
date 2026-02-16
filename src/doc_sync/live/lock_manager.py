"""
Block Lock Manager

Thread-safe in-memory lock manager for block-level collaborative editing.
Each block can only be locked by one user at a time.
"""

import threading
import time
from typing import Dict, Optional


class LockManager:
    """Manages per-block locks for collaborative editing.
    
    Each block can be locked by at most one user. Locks are stored in-memory
    and are released when the user explicitly unlocks or disconnects.
    """

    def __init__(self, lock_timeout: float = 300.0):
        """Initialize the lock manager.
        
        Args:
            lock_timeout: Seconds after which an idle lock is automatically released.
                          Default 300s (5 minutes).
        """
        self._locks: Dict[str, Dict] = {}  # block_id -> {"user": str, "acquired_at": float}
        self._mutex = threading.Lock()
        self._lock_timeout = lock_timeout

    def acquire(self, block_id: str, user: str) -> bool:
        """Acquire a lock on a block.
        
        Args:
            block_id: The block ID to lock.
            user: The user requesting the lock.
            
        Returns:
            True if the lock was acquired, False if already held by another user.
        """
        with self._mutex:
            self._cleanup_expired()
            existing = self._locks.get(block_id)
            if existing is not None:
                if existing["user"] == user:
                    # Refresh the lock timestamp
                    existing["acquired_at"] = time.time()
                    return True
                return False
            self._locks[block_id] = {
                "user": user,
                "acquired_at": time.time()
            }
            return True

    def release(self, block_id: str, user: str) -> bool:
        """Release a lock on a block.
        
        Args:
            block_id: The block ID to unlock.
            user: The user releasing the lock (must be the holder).
            
        Returns:
            True if the lock was released, False if not held by this user.
        """
        with self._mutex:
            existing = self._locks.get(block_id)
            if existing is None:
                return True  # Already unlocked
            if existing["user"] != user:
                return False  # Not the lock holder
            del self._locks[block_id]
            return True

    def release_all(self, user: str) -> int:
        """Release all locks held by a user (e.g., on disconnect).
        
        Args:
            user: The user whose locks should be released.
            
        Returns:
            Number of locks released.
        """
        with self._mutex:
            to_remove = [bid for bid, info in self._locks.items() if info["user"] == user]
            for bid in to_remove:
                del self._locks[bid]
            return len(to_remove)

    def get_holder(self, block_id: str) -> Optional[str]:
        """Get the user holding a lock on a block.
        
        Returns:
            The user name, or None if the block is unlocked.
        """
        with self._mutex:
            self._cleanup_expired()
            info = self._locks.get(block_id)
            return info["user"] if info else None

    def get_locks(self) -> Dict[str, str]:
        """Get all current locks.
        
        Returns:
            Dict mapping block_id to user name.
        """
        with self._mutex:
            self._cleanup_expired()
            return {bid: info["user"] for bid, info in self._locks.items()}

    def _cleanup_expired(self):
        """Remove locks that have exceeded the timeout. Must be called with mutex held."""
        if self._lock_timeout <= 0:
            return
        now = time.time()
        expired = [
            bid for bid, info in self._locks.items()
            if now - info["acquired_at"] > self._lock_timeout
        ]
        for bid in expired:
            del self._locks[bid]
