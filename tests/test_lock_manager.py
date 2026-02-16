"""Tests for the LockManager used in real-time collaborative editing."""
import time
import threading
import pytest

from doc_sync.live.lock_manager import LockManager


class TestLockManagerAcquire:
    """Test lock acquisition behavior."""

    def test_acquire_lock_success(self):
        """First user can acquire a lock on any block."""
        lm = LockManager()
        assert lm.acquire("block_1", "alice") is True

    def test_acquire_same_block_same_user(self):
        """Same user re-acquiring the same block should succeed (refresh)."""
        lm = LockManager()
        lm.acquire("block_1", "alice")
        assert lm.acquire("block_1", "alice") is True

    def test_acquire_different_blocks(self):
        """Different users can lock different blocks."""
        lm = LockManager()
        assert lm.acquire("block_1", "alice") is True
        assert lm.acquire("block_2", "bob") is True

    def test_lock_conflict(self):
        """Second user should be denied lock on block held by another user."""
        lm = LockManager()
        lm.acquire("block_1", "alice")
        assert lm.acquire("block_1", "bob") is False

    def test_get_holder(self):
        """get_holder returns the correct user for a locked block."""
        lm = LockManager()
        lm.acquire("block_1", "alice")
        assert lm.get_holder("block_1") == "alice"

    def test_get_holder_unlocked(self):
        """get_holder returns None for an unlocked block."""
        lm = LockManager()
        assert lm.get_holder("block_1") is None


class TestLockManagerRelease:
    """Test lock release behavior."""

    def test_release_by_holder(self):
        """Lock holder can release the lock."""
        lm = LockManager()
        lm.acquire("block_1", "alice")
        assert lm.release("block_1", "alice") is True
        assert lm.get_holder("block_1") is None

    def test_release_by_non_holder(self):
        """Non-holder cannot release another user's lock."""
        lm = LockManager()
        lm.acquire("block_1", "alice")
        assert lm.release("block_1", "bob") is False
        assert lm.get_holder("block_1") == "alice"

    def test_release_unlocked(self):
        """Releasing an already-unlocked block returns True."""
        lm = LockManager()
        assert lm.release("block_1", "alice") is True

    def test_release_then_reacquire(self):
        """After release, another user can acquire the block."""
        lm = LockManager()
        lm.acquire("block_1", "alice")
        lm.release("block_1", "alice")
        assert lm.acquire("block_1", "bob") is True
        assert lm.get_holder("block_1") == "bob"


class TestLockManagerReleaseAll:
    """Test releasing all locks for a user (disconnect cleanup)."""

    def test_release_all_single_lock(self):
        """release_all releases the single lock held by a user."""
        lm = LockManager()
        lm.acquire("block_1", "alice")
        count = lm.release_all("alice")
        assert count == 1
        assert lm.get_holder("block_1") is None

    def test_release_all_multiple_locks(self):
        """release_all releases all locks held by a user."""
        lm = LockManager()
        lm.acquire("block_1", "alice")
        lm.acquire("block_2", "alice")
        lm.acquire("block_3", "alice")
        count = lm.release_all("alice")
        assert count == 3
        assert lm.get_locks() == {}

    def test_release_all_no_locks(self):
        """release_all returns 0 if user holds no locks."""
        lm = LockManager()
        lm.acquire("block_1", "bob")
        count = lm.release_all("alice")
        assert count == 0
        assert lm.get_holder("block_1") == "bob"

    def test_release_all_does_not_affect_others(self):
        """release_all only frees locks held by the specified user."""
        lm = LockManager()
        lm.acquire("block_1", "alice")
        lm.acquire("block_2", "bob")
        lm.release_all("alice")
        assert lm.get_holder("block_1") is None
        assert lm.get_holder("block_2") == "bob"


class TestLockManagerGetLocks:
    """Test get_locks returns correct state."""

    def test_empty(self):
        lm = LockManager()
        assert lm.get_locks() == {}

    def test_with_locks(self):
        lm = LockManager()
        lm.acquire("block_1", "alice")
        lm.acquire("block_2", "bob")
        locks = lm.get_locks()
        assert locks == {"block_1": "alice", "block_2": "bob"}


class TestLockManagerTimeout:
    """Test automatic lock expiry."""

    def test_expired_lock_released(self):
        """Locks past timeout should be automatically released."""
        lm = LockManager(lock_timeout=0.1)
        lm.acquire("block_1", "alice")
        time.sleep(0.15)
        # The expired lock should be cleaned up on next access
        assert lm.get_holder("block_1") is None

    def test_expired_lock_allows_reacquire(self):
        """After lock expires, another user can acquire it."""
        lm = LockManager(lock_timeout=0.1)
        lm.acquire("block_1", "alice")
        time.sleep(0.15)
        assert lm.acquire("block_1", "bob") is True


class TestLockManagerThreadSafety:
    """Test thread safety of lock operations."""

    def test_concurrent_lock_attempts(self):
        """Only one of many concurrent lock attempts should succeed."""
        lm = LockManager()
        results = {}

        def try_lock(user):
            results[user] = lm.acquire("block_1", user)

        threads = [
            threading.Thread(target=try_lock, args=(f"user_{i}",))
            for i in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Exactly one should have succeeded
        winners = [u for u, success in results.items() if success]
        assert len(winners) == 1
        assert lm.get_holder("block_1") == winners[0]
