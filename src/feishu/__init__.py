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

# Re-export FeishuClient for backward compatibility
from src.feishu_client import FeishuClient

# Export base class and mixins for subclassing
from src.feishu.base import FeishuClientBase
from src.feishu.blocks import BlockOperationsMixin
from src.feishu.documents import DocumentOperationsMixin
from src.feishu.media import MediaOperationsMixin

__all__ = [
    'FeishuClient',
    'FeishuClientBase',
    'BlockOperationsMixin',
    'DocumentOperationsMixin',
    'MediaOperationsMixin',
]
