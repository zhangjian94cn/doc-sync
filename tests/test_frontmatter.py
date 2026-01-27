from doc_sync.converter import MarkdownToFeishu

def test_extract_frontmatter():
    converter = MarkdownToFeishu()
    text = """---
title: Test Title
date: 2026-01-08
tags: [a, b, c]
---

Content
"""
    remaining, metadata = converter._extract_frontmatter(text)
    
    assert "Content" in remaining
    assert "---" not in remaining
    assert metadata["title"] == "Test Title"
    assert metadata["date"] == "2026-01-08"
    assert metadata["tags"] == "[a, b, c]"

def test_extract_frontmatter_no_match():
    converter = MarkdownToFeishu()
    text = "# Title\nNo frontmatter"
    remaining, metadata = converter._extract_frontmatter(text)
    
    assert remaining == text
    assert metadata is None

def test_parse_frontmatter_to_block():
    converter = MarkdownToFeishu()
    text = """---
key: value
---
"""
    blocks = converter.parse(text)
    
    assert len(blocks) == 1
    assert blocks[0]["block_type"] == 15 # Quote
    elements = blocks[0]["quote"]["elements"]
    assert "text_run" in elements[0]
    assert elements[0]["text_run"]["content"] == "key: "
    assert elements[0]["text_run"]["text_element_style"]["bold"] is True
    assert elements[1]["text_run"]["content"] == "value"
