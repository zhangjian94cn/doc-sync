import re
import os
from typing import List, Dict, Any, Optional, Callable

from src.logger import logger

class FeishuToMarkdown:
    """Convert Feishu document blocks to Markdown content.
    
    Supports:
    - Text blocks (with rich text styles)
    - Headings (1-9 levels)
    - Bullet and ordered lists
    - Todo/checkbox items
    - Code blocks (with language detection)
    - Images (with optional download)
    - Quotes
    - Tables (basic support)
    """
    
    def __init__(self, image_downloader=None):
        """Initialize the converter.
        
        Args:
            image_downloader: Optional callback(token) -> local_path for downloading images
        """
        self.image_downloader = image_downloader
        self.indent_level = 0
    
    def convert(self, blocks: List[Any]) -> str:
        """Convert a list of Feishu blocks to Markdown."""
        md_lines = []
        prev_type = None
        
        for block in blocks:
            line = self._process_block(block)
            if line is not None:
                # Add blank line before headings (except first)
                if hasattr(block, 'block_type'):
                    curr_type = block.block_type
                    if curr_type in range(3, 12) and prev_type and prev_type not in range(3, 12):
                        md_lines.append("")
                    prev_type = curr_type
                
                md_lines.append(line)
        
        return "\n".join(md_lines)

    def _process_block(self, block) -> Optional[str]:
        """Process a single block and return Markdown string."""
        b_type = block.block_type
        content = ""
        text_obj = None
        prefix = ""
        suffix = ""
        indent = "  " * self.indent_level
        
        if b_type == 2:  # Text
            text_obj = block.text
            if not text_obj or not text_obj.elements:
                return ""
                
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
            # Try to get language
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
            token = image_obj.token if hasattr(image_obj, 'token') else ""
            if self.image_downloader and token:
                logger.debug(f"发现云端图片，准备下载: {token}")
                local_path = self.image_downloader(token)
                if local_path:
                    return f"![Image]({local_path})"
                else:
                    return f"![下载失败]({token})"
            else:
                return f"![Image]({token})"
                
        elif b_type == 22:  # Divider
            return "\n---\n"
            
        elif b_type == 31:  # Table
            return self._process_table(block)
            
        else:
            return None

        if text_obj and hasattr(text_obj, 'elements') and text_obj.elements:
            for elem in text_obj.elements:
                if hasattr(elem, 'text_run') and elem.text_run:
                    content += self._process_text_run(elem.text_run)

        return f"{prefix}{content}{suffix}"

    def _process_table(self, table_block) -> str:
        """Process a table block to Markdown."""
        try:
            table_prop = table_block.table.property
            rows = table_prop.row_size
            cols = table_prop.column_size
            
            # Get cell contents if available
            cells = []
            if hasattr(table_block, 'children') and table_block.children:
                for child in table_block.children:
                    if hasattr(child, 'table_cell'):
                        cell_text = ""
                        if hasattr(child, 'text') and child.text and child.text.elements:
                            for elem in child.text.elements:
                                if elem.text_run:
                                    cell_text += elem.text_run.content or ""
                        cells.append(cell_text)
            
            # Build markdown table
            md_lines = []
            cell_idx = 0
            
            for row_idx in range(rows):
                row_cells = []
                for col_idx in range(cols):
                    if cell_idx < len(cells):
                        row_cells.append(cells[cell_idx])
                    else:
                        row_cells.append("")
                    cell_idx += 1
                md_lines.append("| " + " | ".join(row_cells) + " |")
                
                # Add separator after header row
                if row_idx == 0:
                    md_lines.append("| " + " | ".join(["---"] * cols) + " |")
            
            return "\n".join(md_lines)
            
        except Exception as e:
            logger.debug(f"Table processing error: {e}")
            return "[表格]"

    def _process_text_run(self, text_run) -> str:
        """Process a text run with styles to Markdown."""
        text = text_run.content or ""
        style = getattr(text_run, 'text_element_style', None)
        
        if not style:
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

