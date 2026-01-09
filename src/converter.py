import re
import os
from typing import List, Dict, Any, Optional, Callable
from markdown_it import MarkdownIt

from src.logger import logger

class MarkdownToFeishu:
    """Convert Markdown content to Feishu document blocks."""
    
    def __init__(self, image_uploader: Optional[Callable[[str], Optional[str]]] = None):
        """
        Initialize the converter.
        
        Args:
            image_uploader: Optional callback function to resolve/upload images.
                           Takes a path string, returns the resolved path or None.
        """
        self.md = MarkdownIt().enable('table')  # Enable table parsing
        self.image_uploader = image_uploader
        self.list_depth = 0
        
        # Compile Regex Patterns
        self.wiki_link_pattern = re.compile(r'!\[\[(.*?)(?:\|(.*?))?\]\]')
        self.list_item_pattern = re.compile(r'^(\s*)([-*+]|\d+\.)\s+')
        self.weak_indent_pattern = re.compile(r'^( {2,3})(\d+\.|[-*+])\s+')

    def _convert_wiki_links(self, text: str) -> str:
        def replace(match):
            filename = match.group(1).strip()
            alt = match.group(2).strip() if match.group(2) else ""
            filename = filename.replace(" ", "%20")
            return f"![{alt}]({filename})"
        return self.wiki_link_pattern.sub(replace, text)

    def _preprocess_markdown(self, text: str) -> str:
        text = self._convert_wiki_links(text)
        lines = text.split('\n')
        new_lines = []
        in_code_block = False
        
        for i, line in enumerate(lines):
            if line.strip().startswith('```'):
                in_code_block = not in_code_block
            
            if not in_code_block:
                match = self.weak_indent_pattern.match(line)
                if match:
                    current_indent_len = len(match.group(1))
                    needed = 4 - current_indent_len
                    line = " " * needed + line

            if i > 0 and not in_code_block:
                prev_line = lines[i-1]
                if self.list_item_pattern.match(prev_line):
                    is_curr_list = self.list_item_pattern.match(line)
                    is_curr_empty = not line.strip()
                    is_curr_indented = line.startswith(' ') or line.startswith('\t')
                    if not is_curr_list and not is_curr_empty and not is_curr_indented:
                        new_lines.append('')
            
            new_lines.append(line)
            
        return '\n'.join(new_lines)

    def _get_block_field_name(self, block_type: int) -> str:
        mapping = {
            2: "text", 3: "heading1", 4: "heading2", 5: "heading3",
            6: "heading4", 7: "heading5", 8: "heading6", 9: "heading7",
            10: "heading8", 11: "heading9", 12: "bullet", 13: "ordered",
            14: "code", 15: "quote", 17: "todo",  # Feishu Todo is type 17
        }
        return mapping.get(block_type, "text")

    def _check_checkbox(self, block_content: Dict[str, Any]) -> tuple:
        """
        Check if the block content starts with a checkbox pattern.
        Returns: (is_checkbox, is_done, cleaned_content)
        """
        if not block_content or "elements" not in block_content:
            return False, False, block_content
        
        elements = block_content.get("elements", [])
        if not elements:
            return False, False, block_content
        
        first_elem = elements[0]
        if "text_run" not in first_elem:
            return False, False, block_content
        
        content = first_elem["text_run"].get("content", "")
        
        # Check for [ ] or [x] or [X] at the start
        match = re.match(r'^\[([ xX])\]\s*', content)
        if not match:
            return False, False, block_content
        
        is_done = match.group(1).lower() == 'x'
        cleaned_text = content[match.end():]
        
        cleaned_elements = []
        if cleaned_text:
            new_first = dict(first_elem)
            new_first["text_run"] = dict(first_elem["text_run"])
            new_first["text_run"]["content"] = cleaned_text
            cleaned_elements.append(new_first)
        cleaned_elements.extend(elements[1:])
        
        cleaned_content = {"elements": cleaned_elements if cleaned_elements else [{"text_run": {"content": ""}}]}
        return True, is_done, cleaned_content

    def _create_table_block(self, table_rows: List[Dict]) -> Optional[Dict[str, Any]]:
        """Convert parsed table rows to a native Feishu Table block (type 31).
        
        Structure:
        - Table (31) with property (row_size, column_size)
        - Children are TableCell (32) blocks  
        - Each TableCell contains Text (2) blocks
        
        Note: This structure requires the descendants API for creation.
        """
        if not table_rows:
            return None
        
        row_size = len(table_rows)
        col_size = max(len(row['cells']) for row in table_rows) if table_rows else 0
        if col_size == 0:
            return None

        # Build cell blocks with nested text
        cell_blocks = []
        for row in table_rows:
            cells = row['cells']
            while len(cells) < col_size:
                cells.append({"elements": [{"text_run": {"content": ""}}]})
            
            for cell_content in cells:
                text_block = {
                    "block_type": 2,
                    "text": {
                        "elements": cell_content.get("elements", [{"text_run": {"content": ""}}])
                    }
                }
                cell_block = {
                    "block_type": 32,
                    "table_cell": {},
                    "children": [text_block]
                }
                cell_blocks.append(cell_block)
        
        return {
            "block_type": 31,
            "table": {
                "property": {
                    "row_size": row_size,
                    "column_size": col_size
                }
            },
            "children": cell_blocks,
            "_is_native_table": True  # Flag for sync to use descendants API
        }

    def _extract_frontmatter(self, text: str) -> tuple[str, Optional[Dict[str, str]]]:
        """Extract YAML front matter from text."""
        pattern = re.compile(r'^---\s*\n(.*?)\n---\s*(\n|$)', re.DOTALL)
        match = pattern.match(text)
        if match:
            fm_text = match.group(1)
            remaining_text = text[match.end():]
            
            metadata = {}
            for line in fm_text.split('\n'):
                line = line.strip()
                if not line or line.startswith('#'): continue
                if ':' in line:
                    key, val = line.split(':', 1)
                    metadata[key.strip()] = val.strip()
            
            return remaining_text, metadata
        return text, None

    def _create_frontmatter_block(self, metadata: Dict[str, str]) -> Dict[str, Any]:
        """Create a Feishu Quote block for front matter."""
        elements = []
        for i, (k, v) in enumerate(metadata.items()):
            # Key (Bold)
            elements.append({
                "text_run": {
                    "content": k + ": ",
                    "text_element_style": {"bold": True}
                }
            })
            # Value + Newline (except last)
            content = v
            if i < len(metadata) - 1:
                content += "\n"
            elements.append({
                "text_run": {
                    "content": content
                }
            })
            
        return {
            "block_type": 15, # Quote
            "quote": {
                "elements": elements
            }
        }

    def parse(self, text: str) -> List[Dict[str, Any]]:
        # 1. Extract Front Matter
        frontmatter_block = None
        remaining_text, fm_data = self._extract_frontmatter(text)
        if fm_data:
            text = remaining_text
            frontmatter_block = self._create_frontmatter_block(fm_data)
        
        text = self._preprocess_markdown(text)
        tokens = self.md.parse(text)
        
        root_blocks = []
        if frontmatter_block:
            root_blocks.append(frontmatter_block)
            
        parent_stack = [] 
        list_type_stack = [] 
        last_block_stack = [None] 
        self.list_depth = 0
        
        # Table parsing state
        in_table = False
        table_rows = []
        current_row = []
        is_header_row = False
        
        i = 0
        while i < len(tokens):
            token = tokens[i]
            block = None
            
            # Handle table tokens first
            if token.type == 'table_open':
                in_table = True
                table_rows = []
                i += 1
                continue
            elif token.type == 'table_close':
                in_table = False
                block = self._create_table_block(table_rows)
                table_rows = []
                if block:
                    self._add_block_to_tree(block, root_blocks, parent_stack, last_block_stack)
                i += 1
                continue
            elif token.type in ('thead_open', 'tbody_open'):
                is_header_row = token.type == 'thead_open'
                i += 1
                continue
            elif token.type in ('thead_close', 'tbody_close'):
                i += 1
                continue
            elif token.type == 'tr_open':
                current_row = []
                i += 1
                continue
            elif token.type == 'tr_close':
                if current_row:
                    table_rows.append({'cells': current_row, 'is_header': is_header_row})
                current_row = []
                i += 1
                continue
            elif token.type in ('th_open', 'td_open'):
                cell_elements = {"elements": [{"text_run": {"content": ""}}]}
                if i + 1 < len(tokens) and tokens[i+1].type == 'inline':
                    cell_elements = self._create_text_elements_from_token(tokens[i+1])
                    i += 2
                else:
                    i += 1
                current_row.append(cell_elements)
                continue
            elif token.type in ('th_close', 'td_close'):
                i += 1
                continue
            
            if token.type == 'heading_open':
                level = int(token.tag[1:])
                block_type = min(2 + level, 11)
                inline_token = None
                if i + 1 < len(tokens) and tokens[i+1].type == 'inline':
                    inline_token = tokens[i+1]
                    i += 1
                field_name = self._get_block_field_name(block_type)
                block = {
                    "block_type": block_type,
                    field_name: self._create_text_elements_from_token(inline_token)
                }
                
            elif token.type == 'paragraph_open':
                inline_token = None
                if i + 1 < len(tokens) and tokens[i+1].type == 'inline':
                    inline_token = tokens[i+1]
                    i += 1
                
                # Check if we're inside a blockquote
                in_blockquote = any(t.type == 'blockquote_open' for t in tokens[:i] 
                                   if t.type in ('blockquote_open', 'blockquote_close'))
                # More accurate: count opens vs closes
                quote_opens = sum(1 for t in tokens[:i] if t.type == 'blockquote_open')
                quote_closes = sum(1 for t in tokens[:i] if t.type == 'blockquote_close')
                in_blockquote = quote_opens > quote_closes
                
                if in_blockquote:
                    # Create a quote block (type 15)
                    block_content = self._create_text_elements_from_token(inline_token)
                    block = {
                        "block_type": 15,
                        "quote": block_content
                    }
                elif list_type_stack:
                    list_type = list_type_stack[-1]
                    block_content = self._create_text_elements_from_token(inline_token)
                    
                    # Check for checkbox pattern: [ ] or [x]
                    is_checkbox, is_done, cleaned_content = self._check_checkbox(block_content)
                    
                    if is_checkbox:
                        # Create Todo block (type 17)
                        block = {
                            "block_type": 17,
                            "todo": {
                                "elements": cleaned_content.get("elements", []),
                                "style": {
                                    "align": 1,
                                    "done": is_done,
                                    "folded": False
                                }
                            }
                        }
                    else:
                        block_type = 12 if list_type == 'bullet' else 13
                        field_name = self._get_block_field_name(block_type)
                        block = {
                            "block_type": block_type,
                            field_name: block_content
                        }
                else:
                    generated_blocks = self._process_inline_content(inline_token)
                    for b in generated_blocks:
                        self._add_block_to_tree(b, root_blocks, parent_stack, last_block_stack)
                    block = None 
                    
            elif token.type == 'fence':
                lang = token.info.strip()
                content = token.content
                if content.endswith('\n'): content = content[:-1]
                block = {
                    "block_type": 14,
                    "code": {"elements": [{"text_run": {"content": content}}]}
                }
            
            # Handle blockquote
            elif token.type == 'blockquote_open':
                # We'll collect content in the next paragraph
                pass
            elif token.type == 'blockquote_close':
                pass

            if block:
                self._add_block_to_tree(block, root_blocks, parent_stack, last_block_stack)

            elif token.type in ('bullet_list_open', 'ordered_list_open'):
                l_type = 'bullet' if token.type == 'bullet_list_open' else 'ordered'
                list_type_stack.append(l_type)
                
                # If we are already in a list (depth > 0), this is a nested list.
                # The parent is the last block of the CURRENT depth.
                if self.list_depth > 0:
                    parent_block = last_block_stack[self.list_depth] if self.list_depth < len(last_block_stack) else None
                    if parent_block:
                        parent_stack.append(parent_block)
                
                self.list_depth += 1
                while len(last_block_stack) <= self.list_depth:
                    last_block_stack.append(None)
                last_block_stack[self.list_depth] = None 
                
            elif token.type in ('bullet_list_close', 'ordered_list_close'):
                if list_type_stack: list_type_stack.pop()
                self.list_depth -= 1
                if self.list_depth > 0:
                    if parent_stack: parent_stack.pop()

            i += 1
            
        return root_blocks

    def _add_block_to_tree(self, block, root_blocks, parent_stack, last_block_stack):
        if parent_stack:
            parent = parent_stack[-1]
            if "children" not in parent: parent["children"] = []
            parent["children"].append(block)
        else:
            root_blocks.append(block)
        if self.list_depth < len(last_block_stack):
            last_block_stack[self.list_depth] = block

    def _process_inline_content(self, inline_token) -> List[Dict[str, Any]]:
        if not inline_token or not inline_token.children:
            return [{"block_type": 2, "text": {"elements": [{"text_run": {"content": ""}}]}}]

        blocks = []
        current_elements = []
        is_bold = False
        is_italic = False
        is_strikethrough = False
        is_code = False
        
        def flush_text():
            if current_elements:
                blocks.append({
                    "block_type": 2,
                    "text": {"elements": list(current_elements)}
                })
                current_elements.clear()

        i = 0
        children = inline_token.children
        while i < len(children):
            child = children[i]
            if child.type == 'image':
                flush_text()
                src = child.attrs.get('src', '')
                alt = child.content or ""
                ext = src.lower().split('.')[-1] if '.' in src else ''
                is_media_file = ext in {'mp4', 'mov', 'avi', 'mkv', 'webm', 'flv', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'zip', 'rar', '7z', 'tar', 'txt', 'md'}
                
                if src and self.image_uploader:
                    logger.debug(f" 发现资源引用 ({ext}), 准备处理: {src}")
                    file_path = self.image_uploader(src)
                    if file_path:
                        if is_media_file:
                            blocks.append({"block_type": 23, "file": {"token": file_path, "name": alt or os.path.basename(file_path)}})
                            logger.debug(f"文件路径已解析: {file_path}")
                        else:
                            blocks.append({"block_type": 27, "image": {"token": file_path}})
                            logger.debug(f"图片路径已解析: {file_path}")
                    else:
                        logger.warning(f"资源解析失败: {src}")
                        current_elements.append({"text_run": {"content": f"![{alt}]({src})"} })
                else:
                    current_elements.append({"text_run": {"content": f"![{alt}]({src})"} })
            
            elif child.type == 'text':
                text_content = child.content
                if text_content:
                    style = {}
                    if is_bold: style["bold"] = True
                    if is_italic: style["italic"] = True
                    if is_strikethrough: style["strikethrough"] = True
                    if is_code: style["inline_code"] = True
                    element = {"text_run": {"content": text_content}}
                    if style: element["text_run"]["text_element_style"] = style
                    current_elements.append(element)
            elif child.type == 'strong_open': is_bold = True
            elif child.type == 'strong_close': is_bold = False
            elif child.type == 'em_open': is_italic = True
            elif child.type == 'em_close': is_italic = False
            elif child.type == 's_open': is_strikethrough = True
            elif child.type == 's_close': is_strikethrough = False
            elif child.type == 'code_inline':
                style = {"inline_code": True}
                element = {"text_run": {"content": child.content, "text_element_style": style}}
                current_elements.append(element)
            elif child.type == 'softbreak': current_elements.append({"text_run": {"content": "\n"}})
            elif child.type == 'hardbreak': current_elements.append({"text_run": {"content": "\n"}})
            i += 1
            
        flush_text()
        if not blocks: return [{"block_type": 2, "text": {"elements": [{"text_run": {"content": ""}}]}}]
        return blocks

    def _create_text_elements_from_token(self, inline_token) -> Dict[str, Any]:
        if not inline_token or not inline_token.children:
            return {"elements": [{"text_run": {"content": ""}}]}
        elements = []
        is_bold = False
        is_italic = False
        is_strikethrough = False
        is_code = False
        for child in inline_token.children:
            if child.type == 'text':
                text_content = child.content
                if not text_content: continue
                style = {}
                if is_bold: style["bold"] = True
                if is_italic: style["italic"] = True
                if is_strikethrough: style["strikethrough"] = True
                if is_code: style["inline_code"] = True
                element = {"text_run": {"content": text_content}}
                if style: element["text_run"]["text_element_style"] = style
                elements.append(element)
            elif child.type == 'strong_open': is_bold = True
            elif child.type == 'strong_close': is_bold = False
            elif child.type == 'em_open': is_italic = True
            elif child.type == 'em_close': is_italic = False
            elif child.type == 's_open': is_strikethrough = True
            elif child.type == 's_close': is_strikethrough = False
            elif child.type == 'code_inline':
                style = {"inline_code": True}
                element = {"text_run": {"content": child.content, "text_element_style": style}}
                elements.append(element)
            elif child.type == 'softbreak': elements.append({"text_run": {"content": "\n"}})
            elif child.type == 'hardbreak': elements.append({"text_run": {"content": "\n"}})
        if not elements: return {"elements": [{"text_run": {"content": ""}}]}
        return {"elements": elements}

class FeishuToMarkdown:
    def __init__(self, image_downloader=None):
        self.image_downloader = image_downloader

    def convert(self, blocks: List[Any]) -> str:
        md_lines = []
        for block in blocks:
            line = self._process_block(block)
            if line is not None:
                md_lines.append(line)
        return "\n".join(md_lines)

    def _process_block(self, block) -> Optional[str]:
        b_type = block.block_type
        content = ""
        text_obj = None
        prefix = ""
        suffix = ""
        
        if b_type == 2: # Text
            text_obj = block.text
            if not text_obj or not text_obj.elements: return "" 
        elif b_type in range(3, 12): # Headings
            level = b_type - 2
            prefix = "#" * level + " "
            if b_type == 3: text_obj = block.heading1
            elif b_type == 4: text_obj = block.heading2
            elif b_type == 5: text_obj = block.heading3
            elif b_type == 6: text_obj = block.heading4
            elif b_type == 7: text_obj = block.heading5
            elif b_type == 8: text_obj = block.heading6
            elif b_type == 9: text_obj = block.heading7
            elif b_type == 10: text_obj = block.heading8
            elif b_type == 11: text_obj = block.heading9
        elif b_type == 12: # Bullet
            prefix = "- "
            text_obj = block.bullet
        elif b_type == 13: # Ordered
            prefix = "1. " 
            text_obj = block.ordered
        elif b_type == 14: # Code
            text_obj = block.code
            prefix = "```\n"
            suffix = "\n```"
        elif b_type == 22: # Todo
            text_obj = block.todo
            checked = False
            if hasattr(block.todo, 'style') and block.todo.style and block.todo.style.done:
                 checked = True
            prefix = "- [x] " if checked else "- [ ] "
        elif b_type == 27: # Image
            image_obj = block.image
            token = image_obj.token
            if self.image_downloader:
                logger.debug(f"发现云端图片，准备下载: {token}")
                local_path = self.image_downloader(token)
                if local_path: return f"![Image]({local_path})"
                else: return f"![下载失败]({token})"
            else: return f"![Image]({token})"
        else:
            return None

        if text_obj and text_obj.elements:
            for elem in text_obj.elements:
                if elem.text_run:
                    content += self._process_text_run(elem.text_run)
        
        return f"{prefix}{content}{suffix}"

    def _process_text_run(self, text_run) -> str:
        text = text_run.content
        style = text_run.text_element_style
        if not style: return text
        if style.inline_code: text = f"`{text}`"
        if style.bold: text = f"**{text}**"
        if style.italic: text = f"*{text}*"
        if style.strikethrough: text = f"~~{text}~~"
        if style.link and style.link.url: text = f"[{text}]({style.link.url})"
        return text
