"""
Feishu API Client Package

This package provides a modular interface to the Feishu (Lark) API.

Package Structure:
    - base.py: Core client (authentication, rate limiting, caching)
    - blocks.py: Block operations (get/update/delete/batch)
    - documents.py: Document operations (create/clear/list)
    - media.py: Media operations (upload/download image/file)

Usage:
    from src.feishu import FeishuClient
    
    # Or import specific mixins for custom clients
    from src.feishu.base import FeishuClientBase
    from src.feishu.blocks import BlockOperationsMixin
    from src.feishu.documents import DocumentOperationsMixin
    from src.feishu.media import MediaOperationsMixin
"""

# Export base class and mixins (no circular import)
from src.feishu.base import FeishuClientBase
from src.feishu.blocks import BlockOperationsMixin
from src.feishu.documents import DocumentOperationsMixin
from src.feishu.media import MediaOperationsMixin


def __getattr__(name):
    """Lazy import FeishuClient to avoid circular import."""
    if name == 'FeishuClient':
        from src.feishu_client import FeishuClient
        return FeishuClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    'FeishuClient',
    'FeishuClientBase',
    'BlockOperationsMixin',
    'DocumentOperationsMixin',
    'MediaOperationsMixin',
]

