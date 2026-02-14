"""
Converter Package

Bidirectional conversion between Markdown and Feishu document blocks.
Also provides conversion between local data files and Bitable records.

Usage:
    from doc_sync.converter import MarkdownToFeishu, FeishuToMarkdown
    from doc_sync.converter import BitableConverter
    
    # Markdown → Feishu
    converter = MarkdownToFeishu(image_uploader=my_uploader)
    blocks = converter.parse(markdown_text)
    
    # Feishu → Markdown
    converter = FeishuToMarkdown(image_downloader=my_downloader)
    markdown = converter.convert(feishu_blocks)
    
    # CSV → Bitable records
    fields, records = BitableConverter.csv_to_records("data.csv")
"""

from doc_sync.converter.markdown_to_feishu import MarkdownToFeishu
from doc_sync.converter.feishu_to_markdown import FeishuToMarkdown
from doc_sync.converter.bitable_converter import BitableConverter

__all__ = ['MarkdownToFeishu', 'FeishuToMarkdown', 'BitableConverter']


