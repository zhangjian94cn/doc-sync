"""
Constants Module

Defines constants used across the doc-sync project.
"""

# =============================================================================
# Feishu Block Types
# =============================================================================

class BlockType:
    """Feishu document block types."""
    PAGE = 1
    TEXT = 2
    HEADING1 = 3
    HEADING2 = 4
    HEADING3 = 5
    HEADING4 = 6
    HEADING5 = 7
    HEADING6 = 8
    HEADING7 = 9
    HEADING8 = 10
    HEADING9 = 11
    BULLET = 12
    ORDERED = 13
    CODE = 14
    QUOTE = 15
    TODO = 17
    DIVIDER = 22
    FILE = 23
    IMAGE = 27
    TABLE = 31
    TABLE_CELL = 32


# Block type to field name mapping
BLOCK_TYPE_FIELD_MAP = {
    BlockType.TEXT: "text",
    BlockType.HEADING1: "heading1",
    BlockType.HEADING2: "heading2",
    BlockType.HEADING3: "heading3",
    BlockType.HEADING4: "heading4",
    BlockType.HEADING5: "heading5",
    BlockType.HEADING6: "heading6",
    BlockType.HEADING7: "heading7",
    BlockType.HEADING8: "heading8",
    BlockType.HEADING9: "heading9",
    BlockType.BULLET: "bullet",
    BlockType.ORDERED: "ordered",
    BlockType.CODE: "code",
    BlockType.QUOTE: "quote",
    BlockType.TODO: "todo",
    BlockType.IMAGE: "image",
    BlockType.FILE: "file",
    BlockType.TABLE: "table",
    BlockType.TABLE_CELL: "table_cell",
}


# =============================================================================
# API Constants
# =============================================================================

FEISHU_API_BASE_URL = "https://open.feishu.cn/open-apis"

# Rate limit: max 5 requests per second
API_RATE_LIMIT_INTERVAL = 0.2  # 200ms between requests

# Retry settings (also in config.py for backwards compatibility)
DEFAULT_MAX_RETRIES = 5
DEFAULT_RETRY_BASE_DELAY = 1.0


# =============================================================================
# Sync Constants
# =============================================================================

# Files/directories to skip during sync
SYNC_SKIP_EXTENSIONS = {
    ".excalidraw",
    ".excalidraw.md", 
    ".canvas",
}

SYNC_SKIP_DIRECTORIES = {
    "assets",
    "attachments", 
    "_attachments",
    ".obsidian",
    ".trash",
    ".git",
}
