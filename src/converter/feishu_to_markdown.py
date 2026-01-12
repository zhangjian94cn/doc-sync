"""
Feishu to Markdown Converter

Converts Feishu document blocks to Markdown content with proper handling of:
- Tables (with nested TableCell -> Text structure)
- Nested lists (recursive children processing)
- Rich text styles (bold, italic, code, links, etc.)
"""

import re
import os
from typing import List, Dict, Any, Optional, Callable

from src.logger import logger


class FeishuToMarkdown:
    """Convert Feishu document blocks to Markdown content.
    
    Supports:
    - Text blocks (with rich text styles)
    - Headings (1-9 levels)
    - Bullet and ordered lists (with nesting)
    - Todo/checkbox items
    - Code blocks (with language detection)
    - Images (with optional download)
    - Quotes
    - Tables (full support)
    - Dividers
    """
    
    def __init__(self, image_downloader: Optional[Callable[[str], Optional[str]]] = None):
        """Initialize the converter.
        
        Args:
            image_downloader: Optional callback(token) -> local_path for downloading images
        """
        self.image_downloader = image_downloader
        self.block_map: Dict[str, Any] = {}
    
    def convert(self, blocks: List[Any]) -> str:
        """Convert a list of Feishu blocks to Markdown.
        
        Args:
            blocks: List of Feishu block objects from API
            
        Returns:
            Markdown string
        """
        # Build block map for nested lookups
        self.block_map = {}
        for block in blocks:
            block_id = getattr(block, 'block_id', None)
            if block_id:
                self.block_map[block_id] = block
        
        md_lines = []
        prev_type = None
        is_first_block = True
        
        # Get document root to find top-level blocks
        doc_root = None
        for block in blocks:
            if block.block_type == 1:  # Page block
                doc_root = block
                break
        
        # Process only root-level blocks (direct children of document)
        root_children_ids = []
        if doc_root and hasattr(doc_root, 'children') and doc_root.children:
            root_children_ids = doc_root.children
        else:
            # Fallback: process all non-Page blocks
            root_children_ids = [b.block_id for b in blocks if b.block_type != 1]
        
        for block_id in root_children_ids:
            block = self.block_map.get(block_id)
            if not block:
                continue
            
            # Check for frontmatter in first Quote block
            if is_first_block and block.block_type == 15:  # Quote
                frontmatter = self._try_extract_frontmatter(block)
                if frontmatter:
                    md_lines.extend(frontmatter)
                    md_lines.append("")  # Blank line after frontmatter
                    is_first_block = False
                    prev_type = -1  # Reset to force blank line before next block
                    continue
            
            is_first_block = False
            curr_type = block.block_type
            
            # Add blank lines between different block types for better readability
            if prev_type is not None:
                # Add blank line before headings
                if curr_type in range(3, 12):
                    md_lines.append("")
                # Add blank line before paragraphs if previous was not a paragraph
                elif curr_type == 2 and prev_type != 2:
                    md_lines.append("")
                # Add blank line before lists if previous was not a list
                elif curr_type in (12, 13, 17) and prev_type not in (12, 13, 17):
                    md_lines.append("")
                # Add blank line before tables
                elif curr_type == 31:
                    md_lines.append("")
                # Add blank line after lists if current is not a list
                elif curr_type not in (12, 13, 17) and prev_type in (12, 13, 17):
                    md_lines.append("")
            
            lines = self._process_block(block, indent_level=0)
            if lines:
                md_lines.extend(lines)
                prev_type = curr_type
        
        return "\n".join(md_lines)
    
    def _try_extract_frontmatter(self, quote_block) -> Optional[List[str]]:
        """Try to extract YAML frontmatter from a quote block.
        
        Detects patterns like:
        > **title: **Value
        > **date: **2026-01-08
        > **tags: **[tag1, tag2]
        
        Returns frontmatter lines if detected, None otherwise.
        """
        text_obj = getattr(quote_block, 'quote', None)
        if not text_obj or not hasattr(text_obj, 'elements') or not text_obj.elements:
            return None
        
        # Extract raw text content with formatting info
        elements = text_obj.elements
        raw_parts = []
        
        for elem in elements:
            if hasattr(elem, 'text_run') and elem.text_run:
                content = getattr(elem.text_run, 'content', "") or ""
                style = getattr(elem.text_run, 'text_element_style', None)
                is_bold = style and getattr(style, 'bold', False)
                raw_parts.append((content, is_bold))
        
        # Try to parse as frontmatter
        # Pattern: bold "key: " followed by non-bold "value\n"
        frontmatter_lines = []
        i = 0
        while i < len(raw_parts):
            content, is_bold = raw_parts[i]
            
            if is_bold and ': ' in content:
                # This is a key
                key = content.rstrip(': ').strip()
                value = ""
                
                # Look for value in next part
                if i + 1 < len(raw_parts):
                    next_content, next_bold = raw_parts[i + 1]
                    if not next_bold:
                        value = next_content.strip().rstrip('\n')
                        i += 1
                
                if key and value:
                    frontmatter_lines.append(f"{key}: {value}")
            
            i += 1
        
        # Only return as frontmatter if we found at least 2 valid key-value pairs
        if len(frontmatter_lines) >= 2:
            return ["---"] + frontmatter_lines + ["---"]
        
        return None

    def _process_block(self, block, indent_level: int = 0) -> List[str]:
        """Process a single block and return list of Markdown lines."""
        b_type = block.block_type
        lines = []
        text_obj = None
        prefix = ""
        suffix = ""
        indent = "  " * indent_level
        
        if b_type == 2:  # Text
            text_obj = block.text
            if not text_obj or not getattr(text_obj, 'elements', None):
                return [""]
                
        elif b_type in range(3, 12):  # Headings 1-9
            level = b_type - 2
            prefix = "#" * level + " "
            text_obj = getattr(block, f"heading{level}", None)
            
        elif b_type == 12:  # Bullet list
            prefix = f"{indent}- "
            text_obj = block.bullet
            
        elif b_type == 13:  # Ordered list
            prefix = f"{indent}1. "
            text_obj = block.ordered
            
        elif b_type == 14:  # Code block
            text_obj = block.code
            lang = ""
            if hasattr(block.code, 'style') and block.code.style:
                lang_code = getattr(block.code.style, 'language', 0)
                lang = self._get_language_name(lang_code)
            prefix = f"```{lang}\n"
            suffix = "\n```"
            
        elif b_type == 15:  # Quote
            text_obj = block.quote
            prefix = "> "
            
        elif b_type == 17:  # Todo
            text_obj = block.todo
            checked = False
            if hasattr(block.todo, 'style') and block.todo.style:
                checked = getattr(block.todo.style, 'done', False)
            prefix = f"{indent}- [x] " if checked else f"{indent}- [ ] "
            
        elif b_type == 27:  # Image
            image_obj = block.image
            token = getattr(image_obj, 'token', "") if image_obj else ""
            if self.image_downloader and token:
                logger.debug(f"发现云端图片，准备下载: {token}")
                local_path = self.image_downloader(token)
                if local_path:
                    return [f"![Image]({local_path})"]
                else:
                    return [f"![下载失败]({token})"]
            else:
                return [f"![Image]({token})"]
                
        elif b_type == 22:  # Divider
            return ["", "---", ""]
            
        elif b_type == 31:  # Table
            return self._process_table(block)
            
        elif b_type == 32:  # TableCell (handled by _process_table)
            return []
            
        else:
            return []

        # Extract text content
        content = ""
        if text_obj and hasattr(text_obj, 'elements') and text_obj.elements:
            for elem in text_obj.elements:
                if hasattr(elem, 'text_run') and elem.text_run:
                    content += self._process_text_run(elem.text_run)
        
        # Build the line
        line = f"{prefix}{content}{suffix}"
        lines.append(line)
        
        # Process children (for nested lists)
        if b_type in (12, 13, 17) and hasattr(block, 'children') and block.children:
            for child_id in block.children:
                child_block = self.block_map.get(child_id)
                if child_block:
                    child_lines = self._process_block(child_block, indent_level + 1)
                    lines.extend(child_lines)
        
        return lines

    def _process_table(self, table_block) -> List[str]:
        """Process a table block to Markdown with proper cell content extraction."""
        try:
            table_obj = table_block.table
            if not table_obj or not hasattr(table_obj, 'property'):
                return ["[表格]"]
            
            table_prop = table_obj.property
            rows = table_prop.row_size
            cols = table_prop.column_size
            
            # Get cell IDs from table.cells or table_block.children
            cell_ids = []
            if hasattr(table_obj, 'cells') and table_obj.cells:
                cell_ids = table_obj.cells
            elif hasattr(table_block, 'children') and table_block.children:
                cell_ids = table_block.children
            
            # Extract cell contents
            cells = []
            for cell_id in cell_ids:
                cell_content = self._extract_cell_content(cell_id)
                cells.append(cell_content)
            
            # Build markdown table
            md_lines = []
            cell_idx = 0
            
            for row_idx in range(rows):
                row_cells = []
                for col_idx in range(cols):
                    if cell_idx < len(cells):
                        # Escape pipe characters and newlines in cell content
                        cell_text = cells[cell_idx].replace("|", "\\|").replace("\n", " ")
                        row_cells.append(cell_text)
                    else:
                        row_cells.append("")
                    cell_idx += 1
                md_lines.append("| " + " | ".join(row_cells) + " |")
                
                # Add separator after header row
                if row_idx == 0:
                    md_lines.append("| " + " | ".join(["---"] * cols) + " |")
            
            return md_lines
            
        except Exception as e:
            logger.warning(f"Table processing error: {e}")
            return ["[表格]"]
    
    def _extract_cell_content(self, cell_id: str) -> str:
        """Extract text content from a table cell by traversing its children."""
        cell_block = self.block_map.get(cell_id)
        if not cell_block:
            return ""
        
        # TableCell (block_type=32) contains children that are the actual content
        if hasattr(cell_block, 'children') and cell_block.children:
            contents = []
            for child_id in cell_block.children:
                child_block = self.block_map.get(child_id)
                if child_block:
                    text = self._extract_block_text(child_block)
                    if text:
                        contents.append(text)
            return " ".join(contents)
        
        # If no children, try to get text directly
        return self._extract_block_text(cell_block)
    
    def _extract_block_text(self, block) -> str:
        """Extract plain text content from a block."""
        text_attrs = ['text', 'heading1', 'heading2', 'heading3', 'heading4', 
                      'heading5', 'heading6', 'heading7', 'heading8', 'heading9',
                      'bullet', 'ordered', 'code', 'quote', 'todo']
        
        for attr in text_attrs:
            text_obj = getattr(block, attr, None)
            if text_obj and hasattr(text_obj, 'elements') and text_obj.elements:
                content = ""
                for elem in text_obj.elements:
                    if hasattr(elem, 'text_run') and elem.text_run:
                        content += self._process_text_run(elem.text_run)
                return content
        
        return ""

    def _process_text_run(self, text_run) -> str:
        """Process a text run with styles to Markdown."""
        text = getattr(text_run, 'content', "") or ""
        style = getattr(text_run, 'text_element_style', None)
        
        if not style or not text:
            return text
            
        # Apply styles in order (inner to outer)
        if getattr(style, 'inline_code', False):
            text = f"`{text}`"
        if getattr(style, 'bold', False):
            text = f"**{text}**"
        if getattr(style, 'italic', False):
            text = f"*{text}*"
        if getattr(style, 'strikethrough', False):
            text = f"~~{text}~~"
        if hasattr(style, 'link') and style.link and hasattr(style.link, 'url') and style.link.url:
            # For links, wrap the styled text
            text = f"[{text}]({style.link.url})"
            
        return text
    
    def _get_language_name(self, lang_code: int) -> str:
        """Convert Feishu language code to Markdown language identifier."""
        lang_map = {
            1: "plaintext", 2: "abap", 3: "ada", 4: "apache", 5: "apex",
            6: "assembly", 7: "bash", 8: "basic", 9: "c", 10: "clojure",
            11: "coffeescript", 12: "cpp", 13: "csharp", 14: "css", 15: "d",
            16: "dart", 17: "delphi", 18: "django", 19: "dockerfile", 20: "elixir",
            21: "elm", 22: "erlang", 23: "fortran", 24: "fsharp", 25: "go",
            26: "graphql", 27: "groovy", 28: "haskell", 29: "html", 30: "java",
            31: "javascript", 32: "json", 33: "julia", 34: "kotlin", 35: "latex",
            36: "lisp", 37: "lua", 38: "makefile", 39: "markdown", 40: "matlab",
            41: "nginx", 42: "objectivec", 43: "ocaml", 44: "pascal", 45: "perl",
            46: "php", 47: "powershell", 48: "prolog", 49: "python", 50: "r",
            51: "ruby", 52: "rust", 53: "scala", 54: "scheme", 55: "scss",
            56: "shell", 57: "sql", 58: "swift", 59: "typescript", 60: "vb",
            61: "vue", 62: "xml", 63: "yaml"
        }
        return lang_map.get(lang_code, "")
