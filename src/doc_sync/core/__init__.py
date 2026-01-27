"""
Core Module Package

Core functionality used across the application:
- auth: Authentication helpers
- retry: Retry decorators and utilities
- restore: Backup and restore functionality

Usage:
    from doc_sync.core import auth, retry, restore
    from doc_sync.core.retry import retry_on_rate_limit
"""

from doc_sync.core import auth as auth
from doc_sync.core import retry as retry
from doc_sync.core import restore as restore
from doc_sync.core.retry import retry_on_rate_limit, retry_on_failure, with_rate_limit_retry

__all__ = [
    'auth', 'retry', 'restore',
    'retry_on_rate_limit', 'retry_on_failure', 'with_rate_limit_retry'
]


