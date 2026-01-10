"""
Feishu API Client Package

This package provides a modular interface to the Feishu (Lark) API.

For backward compatibility, FeishuClient can be imported from either:
    from src.feishu_client import FeishuClient  # Original
    from src.feishu import FeishuClient          # New (recommended)

Structure:
    - client.py: Core client (auth, rate limiting) 
    - blocks.py: Block operations (future)
    - documents.py: Document operations (future)
    - media.py: Media operations (future)
"""

# Re-export FeishuClient for backward compatibility
from src.feishu_client import FeishuClient

__all__ = ['FeishuClient']
