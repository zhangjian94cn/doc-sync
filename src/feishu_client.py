import json
import os
import hashlib
import time
import threading
from typing import Any, Dict, List, Optional

import requests
import lark_oapi as lark
from lark_oapi.api.docx.v1 import *
from lark_oapi.api.drive.v1 import *
from lark_oapi.api.drive.v1.model.batch_query_meta_request import BatchQueryMetaRequest
from lark_oapi.api.drive.v1.model.meta_request import MetaRequest
from lark_oapi.api.drive.v1.model.request_doc import RequestDoc

from src.logger import logger
from src.config import BATCH_CHUNK_SIZE, API_MAX_RETRIES, API_RETRY_BASE_DELAY

class FeishuClient:
    # Rate limiting: max 5 requests per second (飞书 API 限制)
    _rate_limit_interval = 0.2  # 200ms between requests
    _last_request_time = 0
    _rate_limit_lock = threading.Lock()
    
    def __init__(self, app_id: str, app_secret: str, user_access_token: str = None):
        self.app_id = app_id
        self.app_secret = app_secret
        self.user_access_token = user_access_token
        self.client = lark.Client.builder() \
            .app_id(app_id) \
            .app_secret(app_secret) \
            .enable_set_token(True) \
            .log_level(lark.LogLevel.INFO) \
            .build()
        
        self.asset_cache_path = os.path.join(os.path.expanduser("~"), ".doc_sync", "assets_cache.json")
        self._asset_cache = self._load_asset_cache()
    
    def _rate_limit(self):
        """Ensure minimum interval between API requests."""
        with FeishuClient._rate_limit_lock:
            now = time.time()
            elapsed = now - FeishuClient._last_request_time
            if elapsed < FeishuClient._rate_limit_interval:
                time.sleep(FeishuClient._rate_limit_interval - elapsed)
            FeishuClient._last_request_time = time.time()

    def _load_asset_cache(self) -> Dict[str, str]:
        if os.path.exists(self.asset_cache_path):
            try:
                with open(self.asset_cache_path, 'r') as f: return json.load(f)
            except: pass
        return {}

    def _save_asset_cache(self):
        try:
            os.makedirs(os.path.dirname(self.asset_cache_path), exist_ok=True)
            with open(self.asset_cache_path, 'w') as f: json.dump(self._asset_cache, f)
        except Exception as e:
            logger.warning(f"Failed to save asset cache: {e}")

    def _calculate_file_hash(self, file_path: str) -> str:
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _get_request_option(self):
        if self.user_access_token:
            return lark.RequestOption.builder().user_access_token(self.user_access_token).build()
        return None

    def _get_tenant_access_token(self) -> Optional[str]:
        """Get tenant access token from Feishu API."""
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        headers = {"Content-Type": "application/json; charset=utf-8"}
        data = {"app_id": self.app_id, "app_secret": self.app_secret}
        try:
            self._rate_limit()  # Throttle requests
            resp = requests.post(url, headers=headers, json=data, timeout=10)
            if resp.status_code == 200 and resp.json().get("code") == 0:
                return resp.json().get("tenant_access_token")
            logger.warning(f"获取 tenant_access_token 失败: {resp.status_code}")
            return None
        except requests.exceptions.Timeout:
            logger.error("获取 tenant_access_token 超时")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"获取 tenant_access_token 网络错误: {e}")
            return None

    def upload_file(self, file_path: str, parent_node_token: str, drive_route_token: str = None, parent_type: str = None) -> Optional[str]:
        if not os.path.exists(file_path): return None
        
        # Check cache
        try:
            file_hash = self._calculate_file_hash(file_path)
            if file_hash in self._asset_cache:
                logger.debug(f"File found in cache (deduplicated): {os.path.basename(file_path)}")
                return self._asset_cache[file_hash]
        except Exception as e:
            logger.warning(f"Hash calculation failed: {e}")
            file_hash = None

        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        if not drive_route_token: drive_route_token = parent_node_token
        if not parent_type:
            parent_type = "explorer" if parent_node_token.startswith("fld") else "docx_file"
        with open(file_path, "rb") as f:
            request = UploadAllMediaRequest.builder().request_body(
                UploadAllMediaRequestBody.builder().file_name(file_name).parent_type(parent_type).parent_node(parent_node_token).size(file_size).file(f).build()
            ).build()
            response = self.client.drive.v1.media.upload_all(request, self._get_request_option())
        if not response.success():
            logger.error(f"Upload file failed: {response.code} {response.msg}")
            return None
        
        token = response.data.file_token
        if file_hash:
            self._asset_cache[file_hash] = token
            self._save_asset_cache()
        return token

    def update_block_file(self, document_id: str, block_id: str, token: str) -> bool:
        from lark_oapi.api.docx.v1.model import PatchDocumentBlockRequest, UpdateBlockRequest, ReplaceFileRequest
        request = PatchDocumentBlockRequest.builder().document_id(document_id).block_id(block_id).request_body(
            UpdateBlockRequest.builder().replace_file(ReplaceFileRequest.builder().token(token).build()).build()
        ).build()
        response = self.client.docx.v1.document_block.patch(request, self._get_request_option())
        return response.success()

    def update_block_text(self, document_id: str, block_id: str, 
                          elements: List[Dict[str, Any]]) -> bool:
        """Update text block content with rich text elements.
        
        Args:
            document_id: Document ID
            block_id: Block ID to update
            elements: List of text elements, e.g.:
                [
                    {"text_run": {"content": "Bold text", "text_element_style": {"bold": True}}},
                    {"mention_user": {"user_id": "ou_xxx"}},
                    {"mention_doc": {"token": "docxxx", "obj_type": 1, "url": "https://..."}}
                ]
        
        Returns:
            bool: True if successful
        """
        from lark_oapi.api.docx.v1 import (
            PatchDocumentBlockRequest, UpdateBlockRequest, UpdateTextElementsRequest,
            TextElement, TextRun, TextElementStyle, MentionUser, MentionDoc, Reminder
        )
        
        self._rate_limit()
        
        try:
            # Build TextElement objects from dicts
            text_elements = []
            for elem in elements:
                te_builder = TextElement.builder()
                
                if "text_run" in elem:
                    tr = elem["text_run"]
                    tr_builder = TextRun.builder().content(tr.get("content", ""))
                    
                    # Apply text styles if present
                    style = tr.get("text_element_style", {})
                    if style:
                        style_builder = TextElementStyle.builder()
                        if style.get("bold"): style_builder.bold(True)
                        if style.get("italic"): style_builder.italic(True)
                        if style.get("strikethrough"): style_builder.strikethrough(True)
                        if style.get("underline"): style_builder.underline(True)
                        if style.get("inline_code"): style_builder.inline_code(True)
                        if "background_color" in style: style_builder.background_color(style["background_color"])
                        if "text_color" in style: style_builder.text_color(style["text_color"])
                        tr_builder.text_element_style(style_builder.build())
                    
                    te_builder.text_run(tr_builder.build())
                
                elif "mention_user" in elem:
                    mu = elem["mention_user"]
                    te_builder.mention_user(
                        MentionUser.builder().user_id(mu.get("user_id", "")).build()
                    )
                
                elif "mention_doc" in elem:
                    md = elem["mention_doc"]
                    te_builder.mention_doc(
                        MentionDoc.builder()
                            .token(md.get("token", ""))
                            .obj_type(md.get("obj_type", 1))
                            .url(md.get("url", ""))
                            .build()
                    )
                
                elif "reminder" in elem:
                    rem = elem["reminder"]
                    te_builder.reminder(
                        Reminder.builder()
                            .create_user_id(rem.get("create_user_id", ""))
                            .expire_time(rem.get("expire_time", ""))
                            .notify_time(rem.get("notify_time", ""))
                            .build()
                    )
                
                text_elements.append(te_builder.build())
            
            # Build the patch request
            request = PatchDocumentBlockRequest.builder() \
                .document_id(document_id) \
                .block_id(block_id) \
                .document_revision_id(-1) \
                .request_body(
                    UpdateBlockRequest.builder()
                        .update_text_elements(
                            UpdateTextElementsRequest.builder()
                                .elements(text_elements)
                                .build()
                        )
                        .build()
                ) \
                .build()
            
            response = self.client.docx.v1.document_block.patch(request, self._get_request_option())
            
            if response.success():
                logger.debug(f"Block text updated successfully: {block_id}")
                return True
            else:
                logger.error(f"Update block text failed: code={response.code}, msg={response.msg}")
                return False
                
        except Exception as e:
            logger.error(f"Update block text exception: {e}")
            return False

    def get_block(self, document_id: str, block_id: str) -> Optional[Dict[str, Any]]:
        """Get a single block's content by its ID.
        
        Args:
            document_id: Document ID
            block_id: Block ID to retrieve
        
        Returns:
            Dict containing block data, or None if failed
        """
        from lark_oapi.api.docx.v1 import GetDocumentBlockRequest
        
        self._rate_limit()
        
        try:
            request = GetDocumentBlockRequest.builder() \
                .document_id(document_id) \
                .block_id(block_id) \
                .document_revision_id(-1) \
                .build()
            
            response = self.client.docx.v1.document_block.get(request, self._get_request_option())
            
            if response.success():
                # Convert to dict
                block_data = json.loads(lark.JSON.marshal(response.data.block))
                return block_data
            else:
                logger.error(f"Get block failed: code={response.code}, msg={response.msg}")
                return None
                
        except Exception as e:
            logger.error(f"Get block exception: {e}")
            return None

    def upload_image(self, file_path: str, parent_node_token: str, drive_route_token: str = None) -> Optional[str]:
        if not os.path.exists(file_path): return None
        
        # Check cache
        try:
            file_hash = self._calculate_file_hash(file_path)
            if file_hash in self._asset_cache:
                logger.debug(f"Image found in cache (deduplicated): {os.path.basename(file_path)}")
                return self._asset_cache[file_hash]
        except: file_hash = None

        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        if not drive_route_token: drive_route_token = parent_node_token
        with open(file_path, "rb") as f:
            request = UploadAllMediaRequest.builder().request_body(
                UploadAllMediaRequestBody.builder().file_name(file_name).parent_type("docx_image").parent_node(parent_node_token).size(file_size).file(f).extra(json.dumps({"drive_route_token": drive_route_token})).build()
            ).build()
            response = self.client.drive.v1.media.upload_all(request, self._get_request_option())
        if not response.success(): return None
        
        token = response.data.file_token
        if file_hash:
            self._asset_cache[file_hash] = token
            self._save_asset_cache()
        return token

    def download_image(self, file_token: str, save_path: str) -> bool:
        request = DownloadMediaRequest.builder().file_token(file_token).build()
        response = self.client.drive.v1.media.download(request, self._get_request_option())
        if not response.success(): return False
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        try:
            with open(save_path, "wb") as f:
                if hasattr(response, 'file') and response.file:
                    if hasattr(response.file, 'read'): f.write(response.file.read())
                    else: f.write(response.file)
                else: return False
        except: return False
        return True

    def delete_file(self, file_token: str, file_type: str = "docx") -> bool:
        """Delete a file or folder by token.
        
        Args:
            file_token: The token of the file/folder to delete
            file_type: One of 'file', 'docx', 'folder', 'bitable', 'sheet', etc.
        """
        request = DeleteFileRequest.builder().file_token(file_token).type(file_type).build()
        response = self.client.drive.v1.file.delete(request, self._get_request_option())
        if response.success():
            logger.info(f"Deleted remote {file_type}: {file_token}")
            return True
        logger.error(f"Failed to delete {file_token}: {response.code} {response.msg}")
        return False

    def get_file_info(self, file_token: str, obj_type: str = "docx") -> Optional[Any]:
        req_doc = RequestDoc.builder().doc_token(file_token).doc_type(obj_type).build()
        request = BatchQueryMetaRequest.builder().request_body(MetaRequest.builder().request_docs([req_doc]).with_url(False).build()).build()
        response = self.client.drive.v1.meta.batch_query(request, self._get_request_option())
        if response.success() and response.data and response.data.metas: return response.data.metas[0]
        return None

    def list_folder_files(self, folder_token: str) -> List[Any]:
        files = []
        page_token = None
        while True:
            builder = ListFileRequest.builder().folder_token(folder_token).page_size(200)
            if page_token: builder.page_token(page_token)
            response = self.client.drive.v1.file.list(builder.build(), self._get_request_option())
            if not response.success():
                logger.error(f"List folder files failed: {response.code} {response.msg}")
                break
            if response.data and response.data.files: files.extend(response.data.files)
            page_token = response.data.next_page_token
            if not page_token: break
        return files

    def create_folder(self, parent_token: str, name: str) -> Optional[str]:
        request = CreateFolderFileRequest.builder().request_body(CreateFolderFileRequestBody.builder().name(name).folder_token(parent_token).build()).build()
        response = self.client.drive.v1.file.create_folder(request, self._get_request_option())
        if response.success(): return response.data.token
        return None

    def get_or_create_assets_folder(self) -> Optional[str]:
        from lark_oapi.api.drive.v1.model import CreateFolderFileRequest, CreateFolderFileRequestBody, ListFileRequest
        
        # Try to use configured assets token first
        try:
            from config import FEISHU_ASSETS_TOKEN
            if FEISHU_ASSETS_TOKEN:
                return FEISHU_ASSETS_TOKEN
        except: pass

        root_token = ""
        try:
            url = "https://open.feishu.cn/open-apis/drive/explorer/v2/root_folder/meta"
            token = self.user_access_token or self._get_tenant_access_token()
            headers = {"Authorization": f"Bearer {token}"}
            resp = requests.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 0: root_token = data["data"]["token"]
        except: pass
        
        if not root_token: return None

        list_req = ListFileRequest.builder().folder_token(root_token).build()
        list_resp = self.client.drive.v1.file.list(list_req, self._get_request_option())
        target_name = "DocSync_Assets"
        if list_resp.success() and list_resp.data and list_resp.data.files:
            for file in list_resp.data.files:
                if file.name == target_name and file.type == "folder": return file.token
        
        create_req = CreateFolderFileRequest.builder().request_body(CreateFolderFileRequestBody.builder().name(target_name).folder_token(root_token).build()).build()
        create_resp = self.client.drive.v1.file.create_folder(create_req, self._get_request_option())
        if create_resp.success(): return create_resp.data.token
        return None
    
    def get_root_folder_token(self) -> Optional[str]:
        return self.get_or_create_assets_folder()

    def create_docx(self, parent_token: str, name: str) -> Optional[str]:
        request = CreateDocumentRequest.builder().request_body(CreateDocumentRequestBody.builder().title(name).folder_token(parent_token).build()).build()
        option = self._get_request_option()
        token_type = "User Token" if option and option.user_access_token else "Tenant Token"
        token_preview = option.user_access_token[:5] if option and option.user_access_token else "N/A"
        # logger.debug(f"Creating Docx using {token_type} ({token_preview}...)")
        response = self.client.docx.v1.document.create(request, option)
        if response.success() and response.data and response.data.document: return response.data.document.document_id
        logger.error(f"Create docx failed: {response.code} {response.msg}")
        return None

    def get_all_blocks(self, document_id: str) -> List[Any]:
        # Alias for list_document_blocks but keeping old name for compatibility
        return self.list_document_blocks(document_id)

    def list_document_blocks(self, document_id: str) -> List[Any]:
        from lark_oapi.api.docx.v1.model import ListDocumentBlockRequest
        blocks = []
        page_token = None
        while True:
            builder = ListDocumentBlockRequest.builder().document_id(document_id).page_size(500)
            if page_token: builder.page_token(page_token)
            resp = self.client.docx.v1.document_block.list(builder.build(), self._get_request_option())
            if not resp.success():
                logger.error(f"List blocks failed: {resp.code} {resp.msg}")
                break
            if resp.data and resp.data.items: blocks.extend(resp.data.items)
            page_token = resp.data.page_token
            if not page_token: break
        return blocks

    def clear_document(self, document_id: str):
        blocks = self.get_all_blocks(document_id)
        if not blocks: return
        request = BatchDeleteDocumentBlockChildrenRequest.builder().document_id(document_id).block_id(document_id).request_body(
            BatchDeleteDocumentBlockChildrenRequestBody.builder().start_index(0).end_index(len(blocks)).build()
        ).build()
        self.client.docx.v1.document_block_children.batch_delete(request, self._get_request_option())

    def update_block_image(self, document_id: str, block_id: str, token: str) -> bool:
        from lark_oapi.api.docx.v1.model import PatchDocumentBlockRequest, UpdateBlockRequest, ReplaceImageRequest
        request = PatchDocumentBlockRequest.builder().document_id(document_id).block_id(block_id).request_body(
            UpdateBlockRequest.builder().replace_image(ReplaceImageRequest.builder().token(token).build()).build()
        ).build()
        response = self.client.docx.v1.document_block.patch(request, self._get_request_option())
        return response.success()

    def delete_blocks_by_index(self, document_id: str, start_index: int, end_index: int):
        request = BatchDeleteDocumentBlockChildrenRequest.builder().document_id(document_id).block_id(document_id).request_body(
            BatchDeleteDocumentBlockChildrenRequestBody.builder().start_index(start_index).end_index(end_index).build()
        ).build()
        self.client.docx.v1.document_block_children.batch_delete(request, self._get_request_option())

    def add_blocks(self, document_id: str, blocks: List[Dict[str, Any]], index: int = -1):
        # Separate table blocks from regular blocks
        # Tables with _is_native_table flag need special handling via descendants API
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
                if kids: children_map[idx] = kids
                
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
            
            if not batch_payload: return

            if file_uploads:
                root_folder = self.get_root_folder_token()
                p_token = root_folder if root_folder else document_id
                p_type = "explorer" if root_folder else "docx_file"
                for idx, path in file_uploads:
                    token = self.upload_file(path, p_token, parent_type=p_type)
                    if token:
                        batch_payload[idx]["file"]["token"] = token
                    else:
                        # Upload failed, convert to error text block
                        logger.error(f"文件上传失败，跳过: {os.path.basename(path)}")
                        batch_payload[idx] = {
                            "block_type": 2,
                            "text": {
                                "elements": [{
                                    "text_run": {
                                        "content": f"⚠️ 文件上传失败: {os.path.basename(path)}"
                                    }
                                }]
                            }
                        }
            
            created_ids = self._batch_create(document_id, parent_id, batch_payload, insert_index)
            if not created_ids: return

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

    def _batch_create(self, document_id, parent_id, blocks_dict_list, index=-1) -> List[str]:
        # Use raw requests to bypass SDK limitations and control payload precisely
        url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks/{parent_id}/children"
        
        token = self.user_access_token or self._get_tenant_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8"
        }
        
        created_ids = []
        chunk_size = BATCH_CHUNK_SIZE  # Use config constant
        
        def clean_block(b):
            b_new = b.copy()
            b_type = b_new.get("block_type")
            
            # Remove children for all block types
            # Note: Native Table (31) would need children, but we use code block for now
            b_new.pop("children", None)
            
            # Handle File Block (Type 23)
            # Feishu batch create API doesn't support file blocks directly
            # Convert file blocks to text blocks with file links
            if b_type == 23:
                if "file" in b_new:
                    f_data = b_new["file"]
                    token = f_data.get("token")
                    name = f_data.get("name", "File")
                    file_url = f"https://www.feishu.cn/file/{token}"

                    # Determine icon based on file extension
                    icon = "📄"
                    if name.lower().endswith('.pdf'):
                        icon = "📑"
                    elif name.lower().endswith(('.zip', '.rar', '.7z', '.tar')):
                        icon = "📦"
                    elif name.lower().endswith(('.mp4', '.mov', '.avi', '.mkv')):
                        icon = "🎬"

                    # Convert to text block with link
                    b_new = {
                        "block_type": 2,
                        "text": {
                            "elements": [{
                                "text_run": {
                                    "content": f"{icon} {name}",
                                    "text_element_style": {
                                        "link": {
                                            "url": file_url
                                        }
                                    }
                                }
                            }]
                        }
                    }
                    # Update block type
                    b_type = 2

            # Handle Image Block (Type 27)
            # If token is empty, the image will be uploaded after block creation
            if b_type == 27:
                if "image" in b_new:
                    token = b_new["image"].get("token")
                    # If token is empty, provide empty image object
                    # Feishu will create an empty image block
                    if not token or token == "":
                        b_new["image"] = {}
                    else:
                        b_new["image"] = {"token": token}
                else:
                    # If no image field at all, add empty one
                    b_new["image"] = {}
            
            # Handle Ordered List Style
            if b_type == 13:
                if "ordered" not in b_new: b_new["ordered"] = {}
                if "elements" not in b_new["ordered"]: b_new["ordered"]["elements"] = []
                # Don't force style.sequence, let Feishu handle it
            
            # Clean empty text_element_style
            content_key = self._get_content_key(b_type)
            if content_key and content_key in b_new:
                content_obj = b_new[content_key]
                if "elements" in content_obj:
                    for el in content_obj["elements"]:
                        if "text_run" in el:
                            tr = el["text_run"]
                            if "text_element_style" in tr:
                                # Recursively check if style object is empty or has all false/null values
                                style = tr["text_element_style"]
                                if not style or all(not v for v in style.values()):
                                    del tr["text_element_style"]
                                # IMPORTANT: Check for 'link' object inside style
                                elif "link" in style:
                                    # If link is present but empty or invalid, it might cause issues too
                                    # But usually link has 'url', so it's truthy.
                                    # Let's ensure 'link' object is valid if present
                                    if not style["link"] or not style["link"].get("url"):
                                         del style["link"]
                                         # Re-check if style is empty after removing link
                                         if not style or all(not v for v in style.values()):
                                             del tr["text_element_style"]
            return b_new

        for i in range(0, len(blocks_dict_list), chunk_size):
            chunk = blocks_dict_list[i:i + chunk_size]
            payload_children = [clean_block(b) for b in chunk]
            current_index = index if (index != -1 and i == 0) else -1
            
            body = {"children": payload_children, "index": current_index}

            # Retry logic for rate limiting
            max_retries = 3
            retry_delay = 1.0  # Initial delay in seconds
            
            for attempt in range(max_retries):
                try:
                    self._rate_limit()  # Throttle requests
                    resp = requests.post(url, headers=headers, json=body)
                    
                    # Handle rate limiting (HTTP 429 or code 99991400)
                    if resp.status_code == 429:
                        if attempt < max_retries - 1:
                            import time
                            logger.warning(f"Rate limited (429), retrying in {retry_delay}s...")
                            time.sleep(retry_delay)
                            retry_delay *= 2  # Exponential backoff
                            continue
                        else:
                            logger.error(f"Rate limited after {max_retries} retries")
                            break
                    
                    if resp.status_code == 200:
                        res_json = resp.json()
                        
                        # Check for rate limit error code
                        if res_json.get("code") == 99991400:
                            if attempt < max_retries - 1:
                                import time
                                logger.warning(f"Rate limited (99991400), retrying in {retry_delay}s...")
                                time.sleep(retry_delay)
                                retry_delay *= 2
                                continue
                            else:
                                logger.error(f"Rate limited after {max_retries} retries")
                                break
                        
                        if res_json.get("code") == 0:
                            for child in res_json["data"]["children"]:
                                created_ids.append(child["block_id"])
                            break  # Success, exit retry loop
                        else:
                            logger.error(f"Batch create failed (API Error):")
                            logger.error(f"   - Code: {res_json.get('code')}")
                            logger.error(f"   - Msg: {res_json.get('msg')}")
                            break  # Non-retryable error
                    else:
                        # Handle 400 errors that might contain rate limit
                        try:
                            res_json = resp.json()
                            if res_json.get("code") == 99991400:
                                if attempt < max_retries - 1:
                                    import time
                                    logger.warning(f"Rate limited, retrying in {retry_delay}s...")
                                    time.sleep(retry_delay)
                                    retry_delay *= 2
                                    continue
                        except:
                            pass
                        
                        logger.error(f"Batch create failed (HTTP {resp.status_code}):")
                        logger.error(f"   - Response: {resp.text}")
                        break
                        
                except Exception as e:
                    logger.error(f"Batch create exception: {e}")
                    break
                    
        return created_ids

    def _create_descendants(self, document_id: str, parent_id: str, 
                           top_block_ids: List[str], descendants: List[Dict], 
                           index: int = 0) -> bool:
        """Create nested block structures (like tables) using descendants API.
        
        Args:
            document_id: The document ID
            parent_id: The parent block ID (usually document_id for root)
            top_block_ids: IDs of top-level blocks to add as children
            descendants: Flat list of all blocks with their relationships
            index: Insert position
            
        Returns:
            True if successful, False otherwise
        """
        from lark_oapi.api.docx.v1 import (
            CreateDocumentBlockDescendantRequest, 
            CreateDocumentBlockDescendantRequestBody,
            Block, Table, TableProperty, TableCell, Text, TextElement, TextRun
        )
        
        self._rate_limit()
        
        try:
            # Build Block objects from dicts
            block_objs = []
            for d in descendants:
                block_builder = Block.builder().block_id(d.get("block_id", ""))
                
                b_type = d.get("block_type")
                block_builder.block_type(b_type)
                
                # Set children IDs
                children_ids = d.get("children", [])
                if isinstance(children_ids, list):
                    block_builder.children(children_ids)
                
                # Set content based on block type
                if b_type == 31:  # Table
                    table_data = d.get("table", {})
                    prop = table_data.get("property", {})
                    table_builder = Table.builder().property(
                        TableProperty.builder()
                            .row_size(prop.get("row_size", 1))
                            .column_size(prop.get("column_size", 1))
                            .build()
                    )
                    block_builder.table(table_builder.build())
                    
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
                                    .text_run(TextRun.builder()
                                        .content(tr.get("content", ""))
                                        .build())
                                    .build()
                            )
                    if text_elements:
                        block_builder.text(Text.builder().elements(text_elements).build())
                
                block_objs.append(block_builder.build())
            
            # Build request
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
            
            # Make request with user token
            option = lark.RequestOption.builder()
            if self.user_access_token:
                option.user_access_token(self.user_access_token)
            
            response = self.client.docx.v1.document_block_descendant.create(request, option.build())
            
            if response.success():
                logger.success(f"Created descendants successfully")
                return True
            else:
                logger.error(f"Create descendants failed: code={response.code}, msg={response.msg}")
                return False
                
        except Exception as e:
            logger.error(f"Create descendants exception: {e}")
            return False

    def create_table(self, document_id: str, table_block: Dict, index: int = -1) -> bool:
        """Create a native table using descendants API.
        
        Args:
            document_id: The document ID
            table_block: Table block dict with nested structure from converter
            index: Insert position (-1 for end)
            
        Returns:
            True if successful, False otherwise
        """
        import uuid
        
        # Generate unique IDs for blocks
        table_id = f"table_{uuid.uuid4().hex[:8]}"
        
        table_data = table_block.get("table", {})
        prop = table_data.get("property", {})
        row_size = prop.get("row_size", 1)
        col_size = prop.get("column_size", 1)
        
        children = table_block.get("children", [])
        
        # Build descendants list
        descendants = []
        cell_ids = []
        
        # Add table block
        table_desc = {
            "block_id": table_id,
            "block_type": 31,
            "children": [],  # Will fill with cell IDs
            "table": {
                "property": {
                    "row_size": row_size,
                    "column_size": col_size
                }
            }
        }
        
        # Process each cell
        for i, cell in enumerate(children):
            cell_id = f"cell_{uuid.uuid4().hex[:8]}"
            cell_ids.append(cell_id)
            
            # Get text content from cell's children
            cell_children = cell.get("children", [])
            text_child_ids = []
            
            for j, text_block in enumerate(cell_children):
                text_id = f"text_{uuid.uuid4().hex[:8]}"
                text_child_ids.append(text_id)
                
                # Add text block to descendants
                descendants.append({
                    "block_id": text_id,
                    "block_type": 2,
                    "children": [],
                    "text": text_block.get("text", {"elements": [{"text_run": {"content": ""}}]})
                })
            
            # Add cell block to descendants
            descendants.append({
                "block_id": cell_id,
                "block_type": 32,
                "children": text_child_ids
            })
        
        # Update table with cell IDs
        table_desc["children"] = cell_ids
        
        # Add table at the beginning (it's the top-level block)
        descendants.insert(0, table_desc)
        
        # Create using descendants API
        return self._create_descendants(
            document_id, 
            document_id,  # parent_id = document_id for root level
            [table_id],   # top-level block IDs
            descendants,
            index if index >= 0 else 0
        )

    def _get_content_key(self, b_type):
        mapping = {
            2: "text", 12: "bullet", 13: "ordered", 17: "todo", 14: "code",
            3: "heading1", 4: "heading2", 5: "heading3", 6: "heading4",
            7: "heading5", 8: "heading6", 9: "heading7", 10: "heading8", 11: "heading9"
        }
        return mapping.get(b_type)

    def _dict_to_block_obj(self, b):
        from lark_oapi.api.docx.v1.model import Block, Text, TextElement, TextElementStyle, TextRun, Link, Image, File
        bt = b.get("block_type")
        builder = Block.builder().block_type(bt)
        if bt == 2: builder.text(self._build_text_obj(b.get("text")))
        elif bt in range(3, 12):
            h_obj = self._build_text_obj(b.get(f"heading{bt-2}"))
            if bt==3: builder.heading1(h_obj)
            elif bt==4: builder.heading2(h_obj)
            elif bt==5: builder.heading3(h_obj)
            elif bt==6: builder.heading4(h_obj)
            elif bt==7: builder.heading5(h_obj)
            elif bt==8: builder.heading6(h_obj)
            elif bt==9: builder.heading7(h_obj)
            elif bt==10: builder.heading8(h_obj)
            elif bt==11: builder.heading9(h_obj)
        elif bt == 12: builder.bullet(self._build_text_obj(b.get("bullet")))
        elif bt == 13: builder.ordered(self._build_text_obj(b.get("ordered")))
        elif bt == 14: builder.code(self._build_text_obj(b.get("code")))
        elif bt == 17: builder.todo(self._build_text_obj(b.get("todo")))  # Todo is type 17
        elif bt == 27: builder.image(Image.builder().token(b.get("image", {}).get("token")).build())
        elif bt == 23:
            f_data = b.get("file", {})
            t = f_data.get("token")
            n = f_data.get("name", "File")
            file_url = f"https://www.feishu.cn/file/{t}"
            link_style = TextElementStyle.builder().link(Link.builder().url(file_url).build()).build()
            icon = "📄"
            if n.lower().endswith(('.pdf')): icon = "📑"
            elif n.lower().endswith(('.zip')): icon = "📦"
            text_run = TextRun.builder().content(f"{icon} {n}").text_element_style(link_style).build()
            return Block.builder().block_type(2).text(Text.builder().elements([TextElement.builder().text_run(text_run).build()]).build()).build()
        return builder.build()

    def _build_text_obj(self, data):
        from lark_oapi.api.docx.v1.model import Text, TextElement, TextElementStyle, TextRun, Link
        if not data: return None
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
