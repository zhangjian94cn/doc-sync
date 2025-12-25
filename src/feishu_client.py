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

    def upload_file(self, file_path: str, parent_node_token: str, drive_route_token: str = None, parent_type: str = None) -> Optional[str]:
        """
        Upload a general file (pdf, video, zip, etc.) to Feishu Drive.
        
        Args:
            file_path: Local path to file
            parent_node_token: Doc Token (for docx_file) or Folder Token (for explorer)
            drive_route_token: Document Token (required for permission check if needed)
            parent_type: Explicitly set upload type (explorer/docx_file)
        """
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            return None
            
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        
        if not drive_route_token:
            drive_route_token = parent_node_token
            
        # Determine parent type
        if not parent_type:
            # Folder tokens start with 'fld', Doc tokens start with 'dox'
            # Note: Some folder tokens might not start with 'fld', so explicit type is preferred
            parent_type = "explorer" if parent_node_token.startswith("fld") else "docx_file"
            
        # print(f"DEBUG: Uploading to {parent_node_token} (Type: {parent_type})")
        
        # Open file in binary mode
        with open(file_path, "rb") as f:
            request = UploadAllMediaRequest.builder() \
                .request_body(
                    UploadAllMediaRequestBody.builder()
                    .file_name(file_name)
                    .parent_type(parent_type) 
                    .parent_node(parent_node_token)
                    .size(file_size)
                    .file(f)
                    .build()
                ).build()
            
            response = self.client.drive.v1.media.upload_all(request, self._get_request_option())
            
        if not response.success():
            print(f"Upload file failed: {response.code} {response.msg}")
            # Fallback: Try uploading to explorer root if docx_file fails? 
            # But that breaks block binding usually. Let's assume docx_file works for File Block.
            return None
            
        return response.data.file_token

    def update_block_file(self, document_id: str, block_id: str, token: str) -> bool:
        """
        Update the file token of a specific block (Type 23).
        """
        from lark_oapi.api.docx.v1.model import PatchDocumentBlockRequest, UpdateBlockRequest, ReplaceFileRequest
        
        request = PatchDocumentBlockRequest.builder() \
            .document_id(document_id) \
            .block_id(block_id) \
            .request_body(
                UpdateBlockRequest.builder()
                .replace_file(
                    ReplaceFileRequest.builder()
                    .token(token)
                    .build()
                )
                .build()
            ).build()
            
        response = self.client.docx.v1.document_block.patch(request, self._get_request_option())
        if not response.success():
             print(f"Update block file failed: {response.code} {response.msg}")
             return False
        return True

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

    def get_or_create_assets_folder(self) -> Optional[str]:
        """
        Get or create 'DocSync_Assets' folder in the root directory.
        """
        from lark_oapi.api.drive.v1.model import CreateFolderFileRequest, CreateFolderFileRequestBody, ListFileRequest
        import requests
        
        # 0. Get Root Token via Explorer V2 API
        root_token = ""
        try:
            url = "https://open.feishu.cn/open-apis/drive/explorer/v2/root_folder/meta"
            headers = {
                "Authorization": f"Bearer {self._get_tenant_access_token()}"
            }
            resp = requests.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 0:
                    root_token = data["data"]["token"]
        except Exception as e:
            print(f"Failed to get root token: {e}")
            
        if not root_token:
             # print("❌ 无法获取根文件夹 Token，将降级到文档附件上传")
             return None

        # 1. List files in root to check existence
        list_req = ListFileRequest.builder().folder_token(root_token).build()
        list_resp = self.client.drive.v1.file.list(list_req, self._get_request_option())
        
        target_name = "DocSync_Assets"
        
        if list_resp.success() and list_resp.data and list_resp.data.files:
            for file in list_resp.data.files:
                if file.name == target_name and file.type == "folder":
                    # print(f"✅ Found assets folder: {file.token}")
                    return file.token
        
        # 2. Create if not found
        create_req = CreateFolderFileRequest.builder() \
            .request_body(CreateFolderFileRequestBody.builder()
                .name(target_name)
                .folder_token(root_token)
                .build()) \
            .build()
            
        create_resp = self.client.drive.v1.file.create_folder(create_req, self._get_request_option())
        if create_resp.success():
            # print(f"✅ Created assets folder: {create_resp.data.token}")
            return create_resp.data.token
            
        print(f"Failed to create assets folder: {create_resp.code} {create_resp.msg}")
        return None

    def get_root_folder_token(self) -> Optional[str]:
        return self.get_or_create_assets_folder()

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
        Optimized: 
        1. Pre-uploads Files (Type 23) to Doc.
        2. Creates all blocks (Images use placeholders).
        3. Concurrently uploads and updates Images.
        """
        from lark_oapi.api.docx.v1.model import Block, Image as DocImage, File as DocFile, CreateDocumentBlockChildrenRequest, CreateDocumentBlockChildrenRequestBody
        import concurrent.futures
        
        # 0. Pre-upload Files (Type 23)
        # We upload files first to get tokens, then create Text Blocks with Links.
        # This is because creating native File Blocks via API is unstable/unsupported.
        file_tasks = []
        for idx, block in enumerate(blocks):
            if isinstance(block, dict) and block.get("block_type") == 23:
                f_info = block.get("file", {})
                token = f_info.get("token")
                if token and isinstance(token, str) and (token.startswith("/") or os.path.exists(token)):
                    file_tasks.append((idx, token))
        
        if file_tasks:
            print(f"🚀 正在预上传 {len(file_tasks)} 个附件文件...")
            
            # Use Root Folder to ensure files have standalone URLs
            root_folder = self.get_root_folder_token()
            if not root_folder:
                 print("❌ 无法获取根文件夹 Token，尝试使用文档附件上传（链接可能不可访问）")
                 parent_token = document_id
                 p_type = "docx_file"
            else:
                 parent_token = root_folder
                 p_type = "explorer"
            
            def upload_task(item):
                idx, path = item
                token = self.upload_file(path, parent_token, parent_type=p_type)
                return idx, token
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                results = list(executor.map(upload_task, file_tasks))
            
            success_count = 0
            for idx, token in results:
                if token:
                    blocks[idx]["file"]["token"] = token
                    success_count += 1
            print(f"✅ 附件上传完成: {success_count}/{len(file_tasks)} 成功")

        # 1. Prepare all blocks for creation
        pending_media_tasks = [] # List of {index, path, type}
        blocks_to_create = []
        
        for idx, block_data in enumerate(blocks):
            is_pending = False
            task_type = None
            file_path = None
            
            # Check Image (Type 27)
            if isinstance(block_data, dict) and block_data.get("block_type") == 27:
                img_info = block_data.get("image", {})
                token = img_info.get("token")
                if token and isinstance(token, str) and (token.startswith("/") or os.path.exists(token)):
                     is_pending = True
                     task_type = 'image'
                     file_path = token
            
            # File (Type 23) is already handled in Pre-upload phase.

            if is_pending:
                # Create Empty Placeholder (Only for Image)
                empty_block = Block.builder().block_type(27).image(DocImage.builder().token("").build()).build()
                blocks_to_create.append(empty_block)
                pending_media_tasks.append({
                    "list_index": len(blocks_to_create) - 1,
                    "path": file_path,
                    "type": task_type
                })
            else:
                # Regular block conversion
                block_to_add = block_data
                if isinstance(block_data, dict):
                    bt = block_data.get("block_type")
                    if bt == 27:
                         img_data = block_data.get("image", {})
                         t = img_data.get("token")
                         w = img_data.get("width")
                         h = img_data.get("height")
                         if t:
                            ib = DocImage.builder().token(t)
                            if w: ib.width(w)
                            if h: ib.height(h)
                            block_to_add = Block.builder().block_type(27).image(ib.build()).build()
                    elif bt == 23:
                         file_data = block_data.get("file", {})
                         t = file_data.get("token")
                         n = file_data.get("name")
                         
                         # Fallback to Text Block with Link
                         from lark_oapi.api.docx.v1.model import Text, TextElement, TextElementStyle, TextRun, Link
                         
                         # Construct URL
                         file_url = f"https://www.feishu.cn/file/{t}"
                         
                         link_style = TextElementStyle.builder().link(Link.builder().url(file_url).build()).build()
                         
                         # Add an icon prefix based on extension
                         icon = "📄"
                         if n:
                             if n.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm')): icon = "🎥"
                             elif n.lower().endswith(('.pdf')): icon = "📑"
                             elif n.lower().endswith(('.zip', '.rar', '.7z', '.tar', '.gz')): icon = "📦"
                             elif n.lower().endswith(('.xls', '.xlsx', '.csv')): icon = "📊"
                             elif n.lower().endswith(('.doc', '.docx')): icon = "📝"
                             elif n.lower().endswith(('.ppt', '.pptx')): icon = "📽️"
                         
                         text_run = TextRun.builder().content(f"{icon} {n}").text_element_style(link_style).build()
                         text_elem = TextElement.builder().text_run(text_run).build()
                         text_obj = Text.builder().elements([text_elem]).build()
                         
                         block_to_add = Block.builder().block_type(2).text(text_obj).build()
                         
                blocks_to_create.append(block_to_add)




        if not blocks_to_create:
            return

        # 2. Batch Create Blocks
        CHUNK_SIZE = 50
        created_block_ids = []
        
        current_insert_index = index 
        
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
                 return
            
            if resp.data and resp.data.children:
                for child in resp.data.children:
                    created_block_ids.append(child.block_id)
            
            # Progress Indication
            # print(f"✨ 已创建 {len(created_block_ids)}/{len(blocks_to_create)} 个文档块...")
            
            if current_insert_index != -1:
                current_insert_index += len(chunk)
        
        # 3. Concurrent Upload & Update
        if not pending_media_tasks:
            return

        print(f"🚀 开始并发上传 {len(pending_media_tasks)} 张图片...")
        
        def process_media_task(task):
            idx = task["list_index"]
            path = task["path"]
            t_type = task["type"]
            
            if idx >= len(created_block_ids):
                return False
            
            block_id = created_block_ids[idx]
            file_name = os.path.basename(path)
            
            file_token = None
            update_success = False
            
            if t_type == 'image':
                file_token = self.upload_image(path, block_id, drive_route_token=document_id)
                if file_token:
                    update_success = self.update_block_image(document_id, block_id, file_token)
            
            if update_success:
                print(f"  - 📸 媒体已就绪 ({t_type}): {file_name}")
                return True
            
            print(f"  - ❌ 媒体处理失败 ({t_type}): {file_name}")
            return False

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(process_media_task, pending_media_tasks))
            
        success_count = sum(1 for r in results if r)
        print(f"✅ 图片上传完成: {success_count}/{len(pending_media_tasks)} 成功")
