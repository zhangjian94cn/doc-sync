import json
import os
import requests
import lark_oapi as lark
from lark_oapi.api.docx.v1 import *
from lark_oapi.api.drive.v1 import *
from lark_oapi.api.drive.v1.model.batch_query_meta_request import BatchQueryMetaRequest
from lark_oapi.api.drive.v1.model.meta_request import MetaRequest
from lark_oapi.api.drive.v1.model.request_doc import RequestDoc
from typing import List, Dict, Any, Optional

class FeishuClient:
    """
    Wrapper around Lark/Feishu Open API.
    Handles authentication and operations for Drive and Docx.
    """
    def __init__(self, app_id: str, app_secret: str, user_access_token: str = None):
        self.app_id = app_id
        self.app_secret = app_secret
        self.user_access_token = user_access_token
        
        # Initialize Lark Client with App ID and Secret
        # Enable set token to allow manual token override (for user_access_token)
        self.client = lark.Client.builder() \
            .app_id(app_id) \
            .app_secret(app_secret) \
            .enable_set_token(True) \
            .build()
            
        print(f"[认证] 已初始化 App ID: {app_id[:5]}***")
        if user_access_token:
            print(f"[认证] 已配置 User Access Token")
        else:
            print(f"[认证] 使用自动管理的 Tenant Access Token")

    def _get_request_option(self):
        """
        Helper to return request options. 
        If user_access_token is set, use it.
        Otherwise return None (SDK uses Tenant Token).
        """
        if self.user_access_token:
            return lark.RequestOption.builder().user_access_token(self.user_access_token).build()
        return None

    # ==========================================
    # Auth Helpers (for raw requests)
    # ==========================================

    def _get_tenant_access_token(self) -> Optional[str]:
        """
        Manually fetch Tenant Access Token for operations not covered by SDK (e.g. Explorer API).
        """
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        headers = {"Content-Type": "application/json; charset=utf-8"}
        data = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }
        try:
            resp = requests.post(url, headers=headers, json=data)
            resp.raise_for_status()
            res_json = resp.json()
            if res_json.get("code") != 0:
                print(f"Get tenant token failed: {res_json}")
                return None
            return res_json.get("tenant_access_token")
        except Exception as e:
            print(f"Failed to get tenant access token: {e}")
            return None

    # ==========================================
    # Drive Operations (Meta, Folder, File List, Media)
    # ==========================================

    def upload_image(self, file_path: str, parent_node_token: str, drive_route_token: str = None) -> Optional[str]:
        """
        Upload an image to Feishu Drive.
        
        Args:
            file_path: Local path to image
            parent_node_token: Parent node token (Block ID for docx_image, or Folder Token)
            drive_route_token: Document Token (required for permission check when uploading to block)
        """
        if not os.path.exists(file_path):
            print(f"Image not found: {file_path}")
            return None
            
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        
        # If drive_route_token is not provided, fallback to using parent_node_token 
        # (This handles the old case where we uploaded directly to doc/folder)
        if not drive_route_token:
            drive_route_token = parent_node_token
        
        # Open file in binary mode
        with open(file_path, "rb") as f:
            request = UploadAllMediaRequest.builder() \
                .request_body(
                    UploadAllMediaRequestBody.builder()
                    .file_name(file_name)
                    .parent_type("docx_image") 
                    .parent_node(parent_node_token)
                    .size(file_size)
                    .file(f)
                    .extra(json.dumps({"drive_route_token": drive_route_token}))
                    .build()
                ).build()
            
            response = self.client.drive.v1.media.upload_all(request, self._get_request_option())
            
        if not response.success():
            print(f"Upload image failed: {response.code} {response.msg}")
            return None
            
        return response.data.file_token

    def download_image(self, file_token: str, save_path: str) -> bool:
        """
        Download an image from Feishu Drive and save it locally.
        """
        request = DownloadMediaRequest.builder().file_token(file_token).build()
        
        response = self.client.drive.v1.media.download(request, self._get_request_option())
        
        if not response.success():
            print(f"Download image failed: {response.code} {response.msg}")
            return False
            
        # Ensure directory exists
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        with open(save_path, "wb") as f:
            f.write(response.file_name) # The SDK puts the binary content in `file_name` property? Wait, let me check SDK.
            # Usually SDK returns a response with a stream or content.
            # For Python SDK, `response.file` is likely the stream.
            # Let's check the response object attributes in next step or use `write_to` if available.
        
        return True

    def get_file_info(self, file_token: str) -> Optional[Any]:
        """
        Get file metadata using BatchQueryMetaRequest (Drive API).
        Returns a Meta object with latest_modify_time.
        """
        req_doc = RequestDoc.builder().doc_token(file_token).doc_type("docx").build()
        
        request = BatchQueryMetaRequest.builder() \
            .request_body(
                MetaRequest.builder()
                .request_docs([req_doc])
                .with_url(False)
                .build()
            ).build()
            
        response = self.client.drive.v1.meta.batch_query(request, self._get_request_option())
        
        if not response.success():
            print(f"Get file meta failed: {response.code} {response.msg}")
            return None
            
        if response.data and response.data.metas:
            return response.data.metas[0]
            
        return None

    def list_folder_files(self, folder_token: str) -> List[Any]:
        """
        List files in a specific folder.
        """
        files = []
        page_token = None
        
        while True:
            builder = ListFileRequest.builder() \
                .folder_token(folder_token) \
                .page_size(200)
            
            if page_token:
                builder.page_token(page_token)
                
            request = builder.build()
            
            response = self.client.drive.v1.file.list(request, self._get_request_option())
            
            if not response.success():
                print(f"List files failed: {response.code} {response.msg}")
                break
                
            if response.data and response.data.files:
                files.extend(response.data.files)
                
            page_token = response.data.next_page_token
            if not page_token:
                break
                
        return files

    def create_folder(self, parent_token: str, name: str) -> Optional[str]:
        """
        Create a new folder in the specified parent folder.
        """
        request = CreateFolderFileRequest.builder() \
            .request_body(
                CreateFolderFileRequestBody.builder()
                .name(name)
                .folder_token(parent_token)
                .build()
            ).build()
            
        response = self.client.drive.v1.file.create_folder(request, self._get_request_option())
        
        if not response.success():
             print(f"Create folder failed: {response.code} {response.msg}")
             return None
             
        return response.data.token

    def get_root_folder_token(self) -> Optional[str]:
        """
        Get the token of the root folder (My Space) via Explorer API.
        """
        token = self._get_tenant_access_token()
        if not token:
            return None
            
        url = "https://open.feishu.cn/open-apis/drive/explorer/v2/root_folder/meta"
        headers = {
            "Authorization": f"Bearer {token}"
        }
        
        try:
            resp = requests.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") == 0:
                return data["data"]["token"]
            else:
                print(f"Get root folder meta failed: {data}")
                return None
        except Exception as e:
            print(f"Failed to get root folder token: {e}")
            return None

    # ==========================================
    # Docx Operations (Blocks, Create Doc)
    # ==========================================

    def create_docx(self, parent_token: str, name: str) -> Optional[str]:
        """
        Create a new Docx file in the specified parent folder.
        """
        request = CreateDocumentRequest.builder() \
            .request_body(
                CreateDocumentRequestBody.builder()
                .title(name)
                .folder_token(parent_token)
                .build()
            ).build()
            
        response = self.client.docx.v1.document.create(request, self._get_request_option())
        
        if not response.success():
             print(f"Create docx failed: {response.code} {response.msg}")
             return None
             
        if response.data and response.data.document:
             return response.data.document.document_id
        return None

    def get_all_blocks(self, document_id: str) -> List[Any]:
        """
        Get all direct children blocks (full objects) of the document.
        """
        blocks = []
        page_token = None
        
        while True:
            builder = GetDocumentBlockChildrenRequest.builder() \
                .document_id(document_id) \
                .block_id(document_id) \
                .page_size(500)
            
            if page_token:
                builder.page_token(page_token)
            
            request = builder.build()
                
            response = self.client.docx.v1.document_block_children.get(request, self._get_request_option())
            
            if not response.success():
                print(f"Get blocks failed: {response.code} {response.msg}")
                break
                
            if response.data and response.data.items:
                blocks.extend(response.data.items)
            
            page_token = response.data.page_token
            if not page_token:
                break
                
        return blocks

    def clear_document(self, document_id: str):
        """
        Delete all content in the document.
        """
        # We need total count first
        blocks = self.get_all_blocks(document_id)
        if not blocks:
            return
            
        total_count = len(blocks)
        
        # Delete all children using index range
        request = BatchDeleteDocumentBlockChildrenRequest.builder() \
            .document_id(document_id) \
            .block_id(document_id) \
            .request_body(
                BatchDeleteDocumentBlockChildrenRequestBody.builder()
                .start_index(0)
                .end_index(total_count)
                .build()
            ).build()
            
        response = self.client.docx.v1.document_block_children.batch_delete(request, self._get_request_option())
        if not response.success():
            print(f"Batch delete failed: {response.code} {response.msg}")

    def get_temp_download_url(self, file_token: str) -> Optional[str]:
        """
        Get a temporary download URL for a file/image.
        Valid for 24 hours usually.
        """
        request = BatchGetTmpDownloadUrlMediaRequest.builder() \
            .file_tokens(file_token) \
            .build()
            
        response = self.client.drive.v1.media.batch_get_tmp_download_url(request, self._get_request_option())
        
        if not response.success():
            print(f"Get temp url failed: {response.code} {response.msg}")
            return None
            
        if response.data and response.data.tmp_download_urls:
            return response.data.tmp_download_urls[0].tmp_download_url
            
        return None

    def update_block_image(self, document_id: str, block_id: str, token: str) -> bool:
        """
        Update the image token of a specific block.
        """
        from lark_oapi.api.docx.v1.model import PatchDocumentBlockRequest, UpdateBlockRequest, ReplaceImageRequest
        
        request = PatchDocumentBlockRequest.builder() \
            .document_id(document_id) \
            .block_id(block_id) \
            .request_body(
                UpdateBlockRequest.builder()
                .replace_image(
                    ReplaceImageRequest.builder()
                    .token(token)
                    .build()
                )
                .build()
            ).build()
            
        response = self.client.docx.v1.document_block.patch(request, self._get_request_option())
        if not response.success():
             print(f"Update block image failed: {response.code} {response.msg}")
             return False
        return True

    def delete_blocks_by_index(self, document_id: str, start_index: int, end_index: int):
        """
        Delete blocks by index range.
        """
        request = BatchDeleteDocumentBlockChildrenRequest.builder() \
            .document_id(document_id) \
            .block_id(document_id) \
            .request_body(
                BatchDeleteDocumentBlockChildrenRequestBody.builder()
                .start_index(start_index)
                .end_index(end_index)
                .build()
            ).build()
            
        response = self.client.docx.v1.document_block_children.batch_delete(request, self._get_request_option())
        if not response.success():
            print(f"Delete blocks failed: {response.code} {response.msg}")

    def add_blocks(self, document_id: str, blocks: List[Dict[str, Any]], index: int = -1):
        """
        Add blocks to the document.
        Args:
            document_id: Doc ID
            blocks: List of block dicts
            index: Insertion index. -1 means append to end.
        Optimized: Creates all blocks first (with placeholders for images), then concurrently uploads and updates images.
        """
        from lark_oapi.api.docx.v1.model import Block, Image as DocImage, CreateDocumentBlockChildrenRequest, CreateDocumentBlockChildrenRequestBody
        import concurrent.futures
        
        # 1. Prepare all blocks for creation
        # Identify which blocks are pending images
        pending_image_tasks = [] # List of (index_in_created_blocks, image_path)
        blocks_to_create = []
        
        for idx, block_data in enumerate(blocks):
            # Check if it is a "Pending Upload Image"
            is_pending_image = False
            image_path = None
            
            if isinstance(block_data, dict) and block_data.get("block_type") == 27:
                img_info = block_data.get("image", {})
                token = img_info.get("token")
                if token and isinstance(token, str) and (token.startswith("/") or os.path.exists(token)):
                     is_pending_image = True
                     image_path = token
            
            if is_pending_image:
                # Create Empty Image Block Placeholder
                empty_img = Block.builder().block_type(27).image(DocImage.builder().token("").build()).build()
                blocks_to_create.append(empty_img)
                pending_image_tasks.append({
                    "list_index": len(blocks_to_create) - 1, # Index in the batch list
                    "path": image_path
                })
            else:
                # Regular block
                block_to_add = block_data
                if isinstance(block_data, dict) and block_data.get("block_type") == 27:
                     img_data = block_data.get("image", {})
                     t = img_data.get("token")
                     w = img_data.get("width")
                     h = img_data.get("height")
                     if t:
                        ib = DocImage.builder().token(t)
                        if w: ib.width(w)
                        if h: ib.height(h)
                        block_to_add = Block.builder().block_type(27).image(ib.build()).build()
                blocks_to_create.append(block_to_add)

        if not blocks_to_create:
            return

        # 2. Batch Create Blocks (Chunking if necessary, but SDK might handle or we assume < 50 for now? Feishu limit is usually 50)
        # We need to chunk manually to be safe.
        CHUNK_SIZE = 50
        created_block_ids = []
        
        current_insert_index = index 
        # If index is -1, it stays -1 (append). 
        # If index is >= 0, we need to increment it for subsequent chunks?
        # CreateDocumentBlockChildren documentation says "index": "插在指定的索引位置，-1表示插在最后".
        # If we insert a chunk at index 0, the next chunk should be at index + len(chunk).
        
        for i in range(0, len(blocks_to_create), CHUNK_SIZE):
            chunk = blocks_to_create[i:i + CHUNK_SIZE]
            
            req_body_builder = CreateDocumentBlockChildrenRequestBody.builder().children(chunk)
            if current_insert_index != -1:
                req_body_builder.index(current_insert_index)
                
            request = CreateDocumentBlockChildrenRequest.builder() \
                .document_id(document_id) \
                .block_id(document_id) \
                .request_body(req_body_builder.build()).build()
            
            resp = self.client.docx.v1.document_block_children.create(request, self._get_request_option())
            if not resp.success():
                 print(f"Create blocks chunk {i//CHUNK_SIZE} failed: {resp.code} {resp.msg}")
                 # If creation fails, indices will be messed up. We abort.
                 return
            
            if resp.data and resp.data.children:
                for child in resp.data.children:
                    created_block_ids.append(child.block_id)
            
            # Progress Indication
            # print(f"✨ 已创建 {len(created_block_ids)}/{len(blocks_to_create)} 个文档块...")
            
            if current_insert_index != -1:
                current_insert_index += len(chunk)
        
        # 3. Concurrent Upload & Update
        if not pending_image_tasks:
            return

        print(f"🚀 开始并发上传 {len(pending_image_tasks)} 张图片...")
        
        def process_image_task(task):
            idx = task["list_index"]
            path = task["path"]
            if idx >= len(created_block_ids):
                return False
            
            block_id = created_block_ids[idx]
            file_name = os.path.basename(path)
            # print(f"  - Uploading {file_name} to Block {block_id}")
            
            # Upload
            file_token = self.upload_image(path, block_id, drive_route_token=document_id)
            if file_token:
                # Update
                if self.update_block_image(document_id, block_id, file_token):
                    print(f"  - 📸 图片已就绪: {file_name}")
                    return True
            print(f"  - ❌ 图片处理失败: {file_name}")
            return False

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(process_image_task, pending_image_tasks))
            
        success_count = sum(1 for r in results if r)
        print(f"✅ 图片上传完成: {success_count}/{len(pending_image_tasks)} 成功")
