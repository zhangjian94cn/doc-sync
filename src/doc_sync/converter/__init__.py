"""
Converter Package

Bidirectional conversion between Markdown and Feishu document blocks.

Usage:
    from doc_sync.converter import MarkdownToFeishu, FeishuToMarkdown
    
    # Markdown → Feishu
    converter = MarkdownToFeishu(image_uploader=my_uploader)
    blocks = converter.parse(markdown_text)
    
    # Feishu → Markdown
    converter = FeishuToMarkdown(image_downloader=my_downloader)
    markdown = converter.convert(feishu_blocks)
"""

from doc_sync.converter.markdown_to_feishu import MarkdownToFeishu
from doc_sync.converter.feishu_to_markdown import FeishuToMarkdown

__all__ = ['MarkdownToFeishu', 'FeishuToMarkdown']


