import json
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
    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        
        # Initialize Lark Client with App ID and Secret
        # This automatically handles Tenant Access Token management for SDK calls
        self.client = lark.Client.builder() \
            .app_id(app_id) \
            .app_secret(app_secret) \
            .build()
            
        print(f"[认证] 已初始化 App ID: {app_id[:5]}*** (使用自动管理的 Tenant Access Token)。")

    def _get_request_option(self):
        """
        Helper to return request options. 
        When using Tenant Access Token with the SDK, we typically don't need extra options.
        """
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
    # Drive Operations (Meta, Folder, File List)
    # ==========================================

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

    def add_blocks(self, document_id: str, blocks: List[Dict[str, Any]]):
        """
        Add blocks to the end of the document.
        """
        for block in blocks:
            request = CreateDocumentBlockChildrenRequest.builder() \
                .document_id(document_id) \
                .block_id(document_id) \
                .request_body(
                    CreateDocumentBlockChildrenRequestBody.builder()
                    .children([block])
                    .build()
                ).build()
            
            try:
                response = self.client.docx.v1.document_block_children.create(request, self._get_request_option())
            except Exception as e:
                print(f"Create block failed with exception: {e}")
                continue

            if not response.success():
                print(f"Create block failed: {response.code} {response.msg}")
