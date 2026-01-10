"""
Converter Package

Provides bidirectional conversion between Markdown and Feishu document blocks.

Usage:
    from src.converter import MarkdownToFeishu, FeishuToMarkdown
    
    # Or import from submodules
    from src.converter.markdown_to_feishu import MarkdownToFeishu
    from src.converter.feishu_to_markdown import FeishuToMarkdown

Classes:
    - MarkdownToFeishu: Convert Markdown → Feishu blocks
    - FeishuToMarkdown: Convert Feishu blocks → Markdown
"""

# For backward compatibility, re-export from original file
# Classes are defined in the parent module (src/converter.py)
import sys
import importlib.util

# Import from the original converter.py file
spec = importlib.util.spec_from_file_location(
    "converter_original",
    __file__.replace("/converter/__init__.py", "/converter.py")
)
converter_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(converter_module)

MarkdownToFeishu = converter_module.MarkdownToFeishu
FeishuToMarkdown = converter_module.FeishuToMarkdown

__all__ = ['MarkdownToFeishu', 'FeishuToMarkdown']
