"""
Feishu API Client Package

This package provides a modular interface to the Feishu (Lark) API.

Package Structure:
    - base.py: Core client (authentication, rate limiting, caching)
    - blocks.py: Block operations (get/update/delete/batch)
    - documents.py: Document operations (create/clear/list)
    - media.py: Media operations (upload/download image/file)
    - bitable.py: Bitable (多维表格) operations (table/field/record/view)

Usage:
    from doc_sync.feishu import FeishuClient
    
    # Or import specific mixins for custom clients
    from doc_sync.feishu.base import FeishuClientBase
    from doc_sync.feishu.blocks import BlockOperationsMixin
    from doc_sync.feishu.documents import DocumentOperationsMixin
    from doc_sync.feishu.media import MediaOperationsMixin
    from doc_sync.feishu.bitable import BitableOperationsMixin
"""

# Export base class and mixins (no circular import)
from doc_sync.feishu.base import FeishuClientBase
from doc_sync.feishu.blocks import BlockOperationsMixin
from doc_sync.feishu.documents import DocumentOperationsMixin
from doc_sync.feishu.media import MediaOperationsMixin
from doc_sync.feishu.bitable import BitableOperationsMixin


def __getattr__(name):
    """Lazy import FeishuClient to avoid circular import."""
    if name == 'FeishuClient':
        from doc_sync.feishu_client import FeishuClient
        return FeishuClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    'FeishuClient',
    'FeishuClientBase',
    'BlockOperationsMixin',
    'DocumentOperationsMixin',
    'MediaOperationsMixin',
    'BitableOperationsMixin',
]

