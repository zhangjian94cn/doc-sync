from typing import List, Dict, Any, Optional
import re
from markdown_it import MarkdownIt

class MarkdownToFeishu:
    def __init__(self):
        self.md = MarkdownIt()
        
    def _preprocess_markdown(self, text: str) -> str:
        """
        Pre-process markdown text to handle user-specific formatting preferences.
        Specifically, break "Lazy Continuation" of lists.
        If a line follows a list item but is not indented, insert a blank line to force a new block.
        """
        lines = text.split('\n')
        new_lines = []
        in_code_block = False
        
        # Regex to detect list item start
        # Matches: "- ", "* ", "+ ", "1. ", "10. "
        list_pattern = re.compile(r'^(\s*)([-*+]|\d+\.)\s+')
        
        for i, line in enumerate(lines):
            # Toggle code block (simple detection)
            if line.strip().startswith('```'):
                in_code_block = not in_code_block
                
            if i > 0 and not in_code_block:
                prev_line = lines[i-1]
                
                # If previous line looks like a list item
                if list_pattern.match(prev_line):
                    # And current line is NOT empty, NOT a list item, and NOT indented
                    is_curr_list = list_pattern.match(line)
                    is_curr_empty = not line.strip()
                    is_curr_indented = line.startswith(' ') or line.startswith('\t')
                    
                    if not is_curr_list and not is_curr_empty and not is_curr_indented:
                        # Insert blank line to break the list
                        new_lines.append('')
            
            new_lines.append(line)
            
        return '\n'.join(new_lines)

    def _get_block_field_name(self, block_type: int) -> str:
        mapping = {
            2: "text",
            3: "heading1",
            4: "heading2",
            5: "heading3",
            6: "heading4",
            7: "heading5",
            8: "heading6",
            9: "heading7",
            10: "heading8",
            11: "heading9",
            12: "bullet",
            13: "ordered",
            14: "code",
            22: "todo",
        }
        return mapping.get(block_type, "text")

    def parse(self, text: str) -> List[Dict[str, Any]]:
        # Preprocess text to fix list lazy continuation issues
        text = self._preprocess_markdown(text)
        tokens = self.md.parse(text)
        blocks = []
        
        # State to track list context
        list_stack = [] # 'bullet' or 'ordered'
        
        i = 0
        while i < len(tokens):
            token = tokens[i]
            
            if token.type == 'heading_open':
                level = int(token.tag[1:])
                # Feishu H1=3, H2=4, ... H9=11
                block_type = min(2 + level, 11)
                
                # Get inline token for content
                inline_token = None
                if i + 1 < len(tokens) and tokens[i+1].type == 'inline':
                    inline_token = tokens[i+1]
                    i += 1
                
                field_name = self._get_block_field_name(block_type)
                blocks.append({
                    "block_type": block_type,
                    field_name: self._create_text_elements_from_token(inline_token)
                })
                
            elif token.type == 'bullet_list_open':
                list_stack.append('bullet')
                
            elif token.type == 'bullet_list_close':
                if list_stack: list_stack.pop()
                
            elif token.type == 'ordered_list_open':
                list_stack.append('ordered')
                
            elif token.type == 'ordered_list_close':
                if list_stack: list_stack.pop()
                
            elif token.type == 'list_item_open':
                pass # Just a container
                
            elif token.type == 'paragraph_open':
                inline_token = None
                if i + 1 < len(tokens) and tokens[i+1].type == 'inline':
                    inline_token = tokens[i+1]
                    i += 1
                
                # Check if we are inside a list
                if list_stack:
                    list_type = list_stack[-1]
                    if list_type == 'bullet':
                        block_type = 12
                    elif list_type == 'ordered':
                        block_type = 13
                    else:
                        block_type = 2
                        
                    field_name = self._get_block_field_name(block_type)
                    blocks.append({
                        "block_type": block_type,
                        field_name: self._create_text_elements_from_token(inline_token)
                    })
                else:
                    # Regular paragraph
                    blocks.append({
                        "block_type": 2, # Text
                        "text": self._create_text_elements_from_token(inline_token)
                    })
                    
            elif token.type == 'fence':
                # Code block
                lang = token.info.strip()
                content = token.content
                # Remove trailing newline from content if present
                if content.endswith('\n'):
                    content = content[:-1]
                    
                blocks.append({
                    "block_type": 14, # Code
                    "code": {
                        "language": 1, # Default Plain Text. Mapping is complex.
                        "wrap": True,
                        "body": {"elements": [{"text_run": {"content": content}}]}
                    }
                })
                
            # Handle other types or ignore
            
            i += 1
            
        return blocks

    def _create_text_elements_from_token(self, inline_token) -> Dict[str, Any]:
        """
        Parses an inline token (which contains children like text, strong_open, em_open, etc.)
        and returns a Feishu Text object structure: {"elements": [...]}
        """
        if not inline_token or not inline_token.children:
            return {"elements": [{"text_run": {"content": ""}}]}
            
        elements = []
        
        # Style state
        is_bold = False
        is_italic = False
        is_strikethrough = False
        is_code = False # Inline code
        
        for child in inline_token.children:
            if child.type == 'text':
                text_content = child.content
                if not text_content:
                    continue
                    
                style = {}
                if is_bold: style["bold"] = True
                if is_italic: style["italic"] = True
                if is_strikethrough: style["strikethrough"] = True
                if is_code: style["inline_code"] = True
                
                element = {
                    "text_run": {
                        "content": text_content,
                    }
                }
                
                if style:
                    element["text_run"]["text_element_style"] = style
                    
                elements.append(element)
                
            elif child.type == 'strong_open':
                is_bold = True
            elif child.type == 'strong_close':
                is_bold = False
                
            elif child.type == 'em_open':
                is_italic = True
            elif child.type == 'em_close':
                is_italic = False
                
            elif child.type == 's_open':
                is_strikethrough = True
            elif child.type == 's_close':
                is_strikethrough = False
                
            elif child.type == 'code_inline':
                style = {"inline_code": True}
                element = {
                    "text_run": {
                        "content": child.content,
                        "text_element_style": style
                    }
                }
                elements.append(element)
            
            elif child.type == 'softbreak':
                # Soft break -> Newline (User Preference)
                elements.append({"text_run": {"content": "\n"}})
                
            elif child.type == 'hardbreak':
                # Hard break -> Newline
                elements.append({"text_run": {"content": "\n"}})
            
        if not elements:
             return {"elements": [{"text_run": {"content": ""}}]}
             
        return {"elements": elements}


class FeishuToMarkdown:
    def __init__(self):
        pass

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
        
        # Mapping block types
        # 2: Text (Paragraph)
        # 3-11: Headings 1-9
        # 12: Bullet
        # 13: Ordered
        # 14: Code
        # 22: Todo
        
        text_obj = None
        prefix = ""
        suffix = ""
        
        if b_type == 2: # Text
            text_obj = block.text
            # Empty text block is a newline
            if not text_obj or not text_obj.elements:
                return "" 
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
        
        if not style:
            return text
            
        if style.inline_code:
            text = f"`{text}`"
            return text
            
        if style.bold:
            text = f"**{text}**"
        if style.italic:
            text = f"*{text}*"
        if style.strikethrough:
            text = f"~~{text}~~"
            
        if style.link and style.link.url:
            text = f"[{text}]({style.link.url})"
            
        return text
