"""
Feishu API Client Package

This package provides a modular interface to the Feishu (Lark) API.

Package Structure:
    - base.py: Core client (authentication, rate limiting, caching)
    - blocks.py: Block operations (get/update/delete/batch) [future]
    - documents.py: Document operations (create/clear/list) [future]
    - media.py: Media operations (upload/download image/file) [future]

Usage:
    from src.feishu import FeishuClient
    
    # Or import specific modules
    from src.feishu.base import FeishuClientBase
"""

# Re-export FeishuClient for backward compatibility
# The main client is still in src/feishu_client.py during transition
from src.feishu_client import FeishuClient

# Export base class for subclassing
from src.feishu.base import FeishuClientBase

__all__ = ['FeishuClient', 'FeishuClientBase']

