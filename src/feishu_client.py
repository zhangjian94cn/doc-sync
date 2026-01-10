"""
Feishu Client Module

Complete Feishu API client combining all operations from modular mixins.
This is the main entry point for Feishu API interactions.

Architecture:
    - FeishuClientBase: Core authentication, rate limiting, caching
    - BlockOperationsMixin: Block CRUD operations  
    - DocumentOperationsMixin: Document operations
    - MediaOperationsMixin: Image and file upload/download
"""

import os
import time
import uuid
from typing import Any, Dict, List, Optional

import lark_oapi as lark
import requests as requests_module

from src.logger import logger
from src.config import BATCH_CHUNK_SIZE, API_MAX_RETRIES, API_RETRY_BASE_DELAY

# Import base and mixin classes
from src.feishu.base import FeishuClientBase
from src.feishu.blocks import BlockOperationsMixin
from src.feishu.documents import DocumentOperationsMixin
from src.feishu.media import MediaOperationsMixin


class FeishuClient(FeishuClientBase, BlockOperationsMixin, DocumentOperationsMixin, MediaOperationsMixin):
    """
    Complete Feishu API client with all operations.
    
    Inherits from:
        - FeishuClientBase: Core authentication, rate limiting, caching
        - BlockOperationsMixin: Block CRUD operations
        - DocumentOperationsMixin: Document operations
        - MediaOperationsMixin: Image and file upload/download
    
    Additional Methods:
        - add_blocks: Add blocks with nested structure support
        - create_table: Create native tables using descendants API
        - convert_content_to_blocks: Convert Markdown/HTML to blocks
        - batch_update_blocks: Batch update multiple blocks
    """
    
    def __init__(self, app_id: str, app_secret: str, user_access_token: str = None):
        """Initialize the Feishu client with credentials."""
        super().__init__(app_id, app_secret, user_access_token)

    # =========================================================================
    # Content Conversion Methods
    # =========================================================================
    
    def convert_content_to_blocks(self, content: str, 
                                   content_type: str = "markdown") -> Optional[Dict[str, Any]]:
        """Convert Markdown/HTML content to Feishu document blocks.
        
        Uses the official Feishu API to convert content.
        
        Args:
            content: The Markdown or HTML content to convert
            content_type: Either "markdown" or "html"
        
        Returns:
            Dict with first_level_block_ids and blocks, or None if failed
        """
        self._rate_limit()
        
        url = "https://open.feishu.cn/open-apis/docx/v1/documents/blocks/convert"
        
        token = self.user_access_token or self._get_tenant_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8"
        }
        
        body = {"content_type": content_type, "content": content}
        
        retry_delay = API_RETRY_BASE_DELAY
        
        for attempt in range(API_MAX_RETRIES):
            try:
                resp = requests_module.post(url, headers=headers, json=body, timeout=30)
                
                if resp.status_code == 429 or (resp.status_code == 200 and resp.json().get("code") == 99991400):
                    if attempt < API_MAX_RETRIES - 1:
                        logger.warning(f"Rate limited, retrying in {retry_delay}s...")
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    logger.error(f"Rate limited after {API_MAX_RETRIES} retries")
                    return None
                
                if resp.status_code == 200:
                    res_json = resp.json()
                    if res_json.get("code") == 0:
                        data = res_json.get("data", {})
                        return {
                            "first_level_block_ids": data.get("first_level_block_ids", []),
                            "blocks": data.get("blocks", [])
                        }
                    logger.error(f"Convert content failed: {res_json.get('code')} {res_json.get('msg')}")
                    return None
                else:
                    logger.error(f"Convert content HTTP error: {resp.status_code}")
                    return None
                    
            except Exception as e:
                logger.error(f"Convert content exception: {e}")
                return None
        
        return None

    def batch_update_blocks(self, document_id: str, 
                            requests: List[Dict[str, Any]]) -> Optional[List[Dict]]:
        """Batch update multiple blocks in a single API call.
        
        Supports up to 200 blocks per request.
        
        Args:
            document_id: Document ID
            requests: List of update requests
        
        Returns:
            List of updated block data, or None if failed
        """
        url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks/batch_update"
        
        token = self.user_access_token or self._get_tenant_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8"
        }
        
        body = {"requests": requests}
        retry_delay = API_RETRY_BASE_DELAY
        
        for attempt in range(API_MAX_RETRIES):
            try:
                self._rate_limit()
                resp = requests_module.patch(url, headers=headers, json=body, timeout=30)
                
                if resp.status_code == 429 or (resp.status_code == 200 and resp.json().get("code") == 99991400):
                    if attempt < API_MAX_RETRIES - 1:
                        logger.warning(f"Rate limited, retrying in {retry_delay}s...")
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    logger.error(f"Rate limited after {API_MAX_RETRIES} retries")
                    return None
                
                if resp.status_code == 200:
                    res_json = resp.json()
                    if res_json.get("code") == 0:
                        return res_json.get("data", {}).get("blocks", [])
                    logger.error(f"Batch update failed: {res_json.get('code')} {res_json.get('msg')}")
                    return None
                else:
                    logger.error(f"Batch update HTTP error: {resp.status_code}")
                    return None
                    
            except Exception as e:
                logger.error(f"Batch update exception: {e}")
                return None
        
        return None

    # =========================================================================
    # Block Creation Methods (Unique to FeishuClient)
    # =========================================================================
    
    def add_blocks(self, document_id: str, blocks: List[Dict[str, Any]], index: int = -1):
        """Add blocks to a document with full nested structure support.
        
        Handles:
        - Native tables via descendants API
        - Image uploads
        - File uploads
        - Nested children blocks
        
        Args:
            document_id: Document ID
            blocks: List of block dicts to add
            index: Insert position (-1 for end)
        """
        # Separate table blocks from regular blocks
        table_blocks = []
        regular_blocks = []
        
        for b in blocks:
            if b.get("block_type") == 31 and b.get("_is_native_table"):
                table_blocks.append(b)
            else:
                regular_blocks.append(b)
        
        # Handle table blocks separately using create_table
        current_index = index
        for table_block in table_blocks:
            self.create_table(document_id, table_block, current_index)
            if current_index >= 0:
                current_index += 1
        
        # Handle regular blocks with existing logic
        if not regular_blocks:
            return
            
        def create_level(parent_id, current_blocks, insert_index=-1):
            batch_payload = []
            children_map = {} 
            media_tasks = [] 
            file_uploads = [] 

            for idx, b in enumerate(current_blocks):
                b_copy = b.copy()
                kids = b_copy.pop("children", None)
                if kids: 
                    children_map[idx] = kids
                
                b_type = b_copy.get("block_type")
                if b_type == 27:
                    img_info = b_copy.get("image", {})
                    token = img_info.get("token")
                    if token and isinstance(token, str) and (token.startswith("/") or os.path.exists(token)):
                        b_copy["image"]["token"] = "" 
                        media_tasks.append({"idx": idx, "path": token, "type": "image"})
                elif b_type == 23:
                    f_info = b_copy.get("file", {})
                    token = f_info.get("token")
                    if token and isinstance(token, str) and (token.startswith("/") or os.path.exists(token)):
                        file_uploads.append((idx, token))
                batch_payload.append(b_copy)
            
            if not batch_payload: 
                return

            if file_uploads:
                root_folder = self.get_root_folder_token()
                p_token = root_folder if root_folder else document_id
                p_type = "explorer" if root_folder else "docx_file"
                for idx, path in file_uploads:
                    token = self.upload_file(path, p_token, parent_type=p_type)
                    if token:
                        batch_payload[idx]["file"]["token"] = token
                    else:
                        logger.error(f"文件上传失败，跳过: {os.path.basename(path)}")
                        batch_payload[idx] = {
                            "block_type": 2,
                            "text": {
                                "elements": [{
                                    "text_run": {"content": f"⚠️ 文件上传失败: {os.path.basename(path)}"}
                                }]
                            }
                        }
            
            created_ids = self._batch_create(document_id, parent_id, batch_payload, insert_index)
            if not created_ids: 
                return

            for task in media_tasks:
                idx = task["idx"]
                if idx < len(created_ids):
                    block_id = created_ids[idx]
                    path = task["path"]
                    token = self.upload_image(path, block_id, drive_route_token=document_id)
                    if token:
                        self.update_block_image(document_id, block_id, token)
                        logger.success(f"图片已上传: {os.path.basename(path)}")

            for idx, kids in children_map.items():
                if idx < len(created_ids):
                    parent_block_id = created_ids[idx]
                    create_level(parent_block_id, kids)

        create_level(document_id, regular_blocks, index)

    def _batch_create(self, document_id: str, parent_id: str, 
                      blocks_dict_list: List[Dict], index: int = -1) -> List[str]:
        """Batch create blocks using raw requests API.
        
        Args:
            document_id: Document ID
            parent_id: Parent block ID
            blocks_dict_list: List of block dicts to create
            index: Insert position
        
        Returns:
            List of created block IDs
        """
        url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks/{parent_id}/children"
        
        token = self.user_access_token or self._get_tenant_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8"
        }
        
        created_ids = []
        
        def clean_block(b):
            b_new = b.copy()
            b_type = b_new.get("block_type")
            b_new.pop("children", None)
            
            # Handle File Block (Type 23) - convert to text link
            if b_type == 23:
                if "file" in b_new:
                    f_data = b_new["file"]
                    token = f_data.get("token")
                    name = f_data.get("name", "File")
                    file_url = f"https://www.feishu.cn/file/{token}"
                    
                    icon = "📄"
                    if name.lower().endswith('.pdf'):
                        icon = "📑"
                    elif name.lower().endswith(('.zip', '.rar', '.7z', '.tar')):
                        icon = "📦"
                    elif name.lower().endswith(('.mp4', '.mov', '.avi', '.mkv')):
                        icon = "🎬"
                    
                    b_new = {
                        "block_type": 2,
                        "text": {
                            "elements": [{
                                "text_run": {
                                    "content": f"{icon} {name}",
                                    "text_element_style": {"link": {"url": file_url}}
                                }
                            }]
                        }
                    }
                    b_type = 2
            
            # Handle Image Block (Type 27)
            if b_type == 27:
                if "image" in b_new:
                    img_token = b_new["image"].get("token")
                    b_new["image"] = {"token": img_token} if img_token else {}
                else:
                    b_new["image"] = {}
            
            # Handle Ordered List Style
            if b_type == 13:
                if "ordered" not in b_new: 
                    b_new["ordered"] = {}
                if "elements" not in b_new["ordered"]: 
                    b_new["ordered"]["elements"] = []
            
            # Clean empty text_element_style
            content_key = self._get_content_key(b_type)
            if content_key and content_key in b_new:
                content_obj = b_new[content_key]
                if "elements" in content_obj:
                    for el in content_obj["elements"]:
                        if "text_run" in el:
                            tr = el["text_run"]
                            if "text_element_style" in tr:
                                style = tr["text_element_style"]
                                if not style or all(not v for v in style.values()):
                                    del tr["text_element_style"]
                                elif "link" in style:
                                    if not style["link"] or not style["link"].get("url"):
                                        del style["link"]
                                        if not style or all(not v for v in style.values()):
                                            del tr["text_element_style"]
            return b_new

        for i in range(0, len(blocks_dict_list), BATCH_CHUNK_SIZE):
            chunk = blocks_dict_list[i:i + BATCH_CHUNK_SIZE]
            payload_children = [clean_block(b) for b in chunk]
            current_index = index if (index != -1 and i == 0) else -1
            
            body = {"children": payload_children, "index": current_index}
            retry_delay = API_RETRY_BASE_DELAY
            
            for attempt in range(API_MAX_RETRIES):
                try:
                    self._rate_limit()
                    resp = requests_module.post(url, headers=headers, json=body, timeout=30)
                    
                    if resp.status_code == 429:
                        if attempt < API_MAX_RETRIES - 1:
                            logger.warning(f"Rate limited (429), retrying in {retry_delay}s...")
                            time.sleep(retry_delay)
                            retry_delay *= 2
                            continue
                        logger.error(f"Rate limited after {API_MAX_RETRIES} retries")
                        break
                    
                    if resp.status_code == 200:
                        res_json = resp.json()
                        
                        if res_json.get("code") == 99991400:
                            if attempt < API_MAX_RETRIES - 1:
                                logger.warning(f"Rate limited, retrying in {retry_delay}s...")
                                time.sleep(retry_delay)
                                retry_delay *= 2
                                continue
                            logger.error(f"Rate limited after retries")
                            break
                        
                        if res_json.get("code") == 0:
                            for child in res_json["data"]["children"]:
                                created_ids.append(child["block_id"])
                            break
                        else:
                            logger.error(f"Batch create failed: {res_json.get('code')} {res_json.get('msg')}")
                            break
                    else:
                        logger.error(f"Batch create failed (HTTP {resp.status_code})")
                        break
                        
                except Exception as e:
                    logger.error(f"Batch create exception: {e}")
                    break
                    
        return created_ids

    # =========================================================================
    # Table Creation Methods
    # =========================================================================

    def _create_descendants(self, document_id: str, parent_id: str, 
                           top_block_ids: List[str], descendants: List[Dict], 
                           index: int = 0) -> bool:
        """Create nested block structures using descendants API.
        
        Args:
            document_id: The document ID
            parent_id: The parent block ID
            top_block_ids: IDs of top-level blocks
            descendants: Flat list of all blocks
            index: Insert position
        
        Returns:
            True if successful
        """
        from lark_oapi.api.docx.v1 import (
            CreateDocumentBlockDescendantRequest, 
            CreateDocumentBlockDescendantRequestBody,
            Block, Table, TableProperty, TableCell, Text, TextElement, TextRun
        )
        
        self._rate_limit()
        
        try:
            block_objs = []
            for d in descendants:
                block_builder = Block.builder().block_id(d.get("block_id", ""))
                b_type = d.get("block_type")
                block_builder.block_type(b_type)
                
                children_ids = d.get("children", [])
                if isinstance(children_ids, list):
                    block_builder.children(children_ids)
                
                if b_type == 31:  # Table
                    table_data = d.get("table", {})
                    prop = table_data.get("property", {})
                    block_builder.table(
                        Table.builder().property(
                            TableProperty.builder()
                                .row_size(prop.get("row_size", 1))
                                .column_size(prop.get("column_size", 1))
                                .build()
                        ).build()
                    )
                elif b_type == 32:  # TableCell
                    block_builder.table_cell(TableCell.builder().build())
                elif b_type == 2:  # Text
                    text_data = d.get("text", {})
                    elements = text_data.get("elements", [])
                    text_elements = []
                    for el in elements:
                        if "text_run" in el:
                            tr = el["text_run"]
                            text_elements.append(
                                TextElement.builder()
                                    .text_run(TextRun.builder().content(tr.get("content", "")).build())
                                    .build()
                            )
                    if text_elements:
                        block_builder.text(Text.builder().elements(text_elements).build())
                
                block_objs.append(block_builder.build())
            
            request = CreateDocumentBlockDescendantRequest.builder() \
                .document_id(document_id) \
                .block_id(parent_id) \
                .document_revision_id(-1) \
                .request_body(CreateDocumentBlockDescendantRequestBody.builder()
                    .children_id(top_block_ids)
                    .index(index)
                    .descendants(block_objs)
                    .build()) \
                .build()
            
            option = lark.RequestOption.builder()
            if self.user_access_token:
                option.user_access_token(self.user_access_token)
            
            response = self.client.docx.v1.document_block_descendant.create(request, option.build())
            
            if response.success():
                logger.success("Created descendants successfully")
                return True
            else:
                logger.error(f"Create descendants failed: {response.code} {response.msg}")
                return False
                
        except Exception as e:
            logger.error(f"Create descendants exception: {e}")
            return False

    def create_table(self, document_id: str, table_block: Dict, index: int = -1) -> bool:
        """Create a native table using descendants API.
        
        Args:
            document_id: The document ID
            table_block: Table block dict with nested structure
            index: Insert position (-1 for end)
        
        Returns:
            True if successful
        """
        table_id = f"table_{uuid.uuid4().hex[:8]}"
        
        table_data = table_block.get("table", {})
        prop = table_data.get("property", {})
        row_size = prop.get("row_size", 1)
        col_size = prop.get("column_size", 1)
        children = table_block.get("children", [])
        
        descendants = []
        cell_ids = []
        
        table_desc = {
            "block_id": table_id,
            "block_type": 31,
            "children": [],
            "table": {"property": {"row_size": row_size, "column_size": col_size}}
        }
        
        for cell in children:
            cell_id = f"cell_{uuid.uuid4().hex[:8]}"
            cell_ids.append(cell_id)
            
            cell_children = cell.get("children", [])
            text_child_ids = []
            
            for text_block in cell_children:
                text_id = f"text_{uuid.uuid4().hex[:8]}"
                text_child_ids.append(text_id)
                
                descendants.append({
                    "block_id": text_id,
                    "block_type": 2,
                    "children": [],
                    "text": text_block.get("text", {"elements": [{"text_run": {"content": ""}}]})
                })
            
            descendants.append({
                "block_id": cell_id,
                "block_type": 32,
                "children": text_child_ids
            })
        
        table_desc["children"] = cell_ids
        descendants.insert(0, table_desc)
        
        return self._create_descendants(
            document_id, document_id, [table_id], descendants,
            index if index >= 0 else 0
        )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _dict_to_block_obj(self, b: Dict):
        """Convert block dict to Block object."""
        from lark_oapi.api.docx.v1.model import (
            Block, Text, TextElement, TextElementStyle, TextRun, Link, Image
        )
        
        bt = b.get("block_type")
        builder = Block.builder().block_type(bt)
        
        if bt == 2:
            builder.text(self._build_text_obj(b.get("text")))
        elif bt in range(3, 12):
            h_obj = self._build_text_obj(b.get(f"heading{bt-2}"))
            heading_methods = {
                3: builder.heading1, 4: builder.heading2, 5: builder.heading3,
                6: builder.heading4, 7: builder.heading5, 8: builder.heading6,
                9: builder.heading7, 10: builder.heading8, 11: builder.heading9
            }
            heading_methods[bt](h_obj)
        elif bt == 12:
            builder.bullet(self._build_text_obj(b.get("bullet")))
        elif bt == 13:
            builder.ordered(self._build_text_obj(b.get("ordered")))
        elif bt == 14:
            builder.code(self._build_text_obj(b.get("code")))
        elif bt == 17:
            builder.todo(self._build_text_obj(b.get("todo")))
        elif bt == 27:
            builder.image(Image.builder().token(b.get("image", {}).get("token")).build())
        elif bt == 23:
            f_data = b.get("file", {})
            t = f_data.get("token")
            n = f_data.get("name", "File")
            file_url = f"https://www.feishu.cn/file/{t}"
            link_style = TextElementStyle.builder().link(Link.builder().url(file_url).build()).build()
            icon = "📄"
            if n.lower().endswith('.pdf'):
                icon = "📑"
            elif n.lower().endswith('.zip'):
                icon = "📦"
            text_run = TextRun.builder().content(f"{icon} {n}").text_element_style(link_style).build()
            return Block.builder().block_type(2).text(
                Text.builder().elements([TextElement.builder().text_run(text_run).build()]).build()
            ).build()
        
        return builder.build()

    def _build_text_obj(self, data: Optional[Dict]):
        """Build Text object from dict."""
        from lark_oapi.api.docx.v1.model import Text, TextElement, TextElementStyle, TextRun, Link
        
        if not data:
            return None
        
        elements = []
        for e in data.get("elements", []):
            tr = e.get("text_run")
            if tr:
                style_data = tr.get("text_element_style", {})
                style_builder = TextElementStyle.builder()
                has_style = False
                
                if style_data.get("bold"):
                    style_builder.bold(True)
                    has_style = True
                if style_data.get("italic"):
                    style_builder.italic(True)
                    has_style = True
                if style_data.get("strikethrough"):
                    style_builder.strikethrough(True)
                    has_style = True
                if style_data.get("inline_code"):
                    style_builder.inline_code(True)
                    has_style = True
                if style_data.get("link"):
                    style_builder.link(Link.builder().url(style_data["link"].get("url")).build())
                    has_style = True
                
                tr_builder = TextRun.builder().content(tr.get("content"))
                if has_style:
                    tr_builder.text_element_style(style_builder.build())
                    
                elements.append(TextElement.builder().text_run(tr_builder.build()).build())
        
        return Text.builder().elements(elements).build()

    # =========================================================================
    # Override Methods for Configuration
    # =========================================================================
    
    def get_root_folder_token(self) -> Optional[str]:
        """Get root folder token for file uploads."""
        return self.get_or_create_assets_folder()

    def get_or_create_assets_folder(self) -> Optional[str]:
        """Get or create the assets folder for file uploads.
        
        Overrides mixin method to support config-based assets token.
        """
        from lark_oapi.api.drive.v1 import CreateFolderFileRequest, CreateFolderFileRequestBody, ListFileRequest
        
        # Try config first
        try:
            from config import FEISHU_ASSETS_TOKEN
            if FEISHU_ASSETS_TOKEN:
                return FEISHU_ASSETS_TOKEN
        except:
            pass

        # Get root folder
        root_token = ""
        try:
            url = "https://open.feishu.cn/open-apis/drive/explorer/v2/root_folder/meta"
            token = self.user_access_token or self._get_tenant_access_token()
            headers = {"Authorization": f"Bearer {token}"}
            resp = requests_module.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 0:
                    root_token = data["data"]["token"]
        except:
            pass
        
        if not root_token:
            return None

        # Check for existing assets folder
        list_req = ListFileRequest.builder().folder_token(root_token).build()
        list_resp = self.client.drive.v1.file.list(list_req, self._get_request_option())
        target_name = "DocSync_Assets"
        if list_resp.success() and list_resp.data and list_resp.data.files:
            for file in list_resp.data.files:
                if file.name == target_name and file.type == "folder":
                    return file.token
        
        # Create assets folder
        create_req = CreateFolderFileRequest.builder().request_body(
            CreateFolderFileRequestBody.builder().name(target_name).folder_token(root_token).build()
        ).build()
        create_resp = self.client.drive.v1.file.create_folder(create_req, self._get_request_option())
        if create_resp.success():
            return create_resp.data.token
        return None
