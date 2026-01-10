"""
Feishu Document Operations Module

Contains methods for document manipulation:
- create_docx, clear_document
- list_document_blocks, get_all_blocks
- create_folder, list_folder_files
- get_file_info, delete_file
"""

import time
from typing import Any, Dict, List, Optional

import lark_oapi as lark
from lark_oapi.api.docx.v1 import *

from src.logger import logger
from src.config import API_MAX_RETRIES, API_RETRY_BASE_DELAY


class DocumentOperationsMixin:
    """Mixin class providing document operation methods for FeishuClient."""
    
    def create_docx(self, parent_token: str, name: str) -> Optional[str]:
        """Create a new Feishu document.
        
        Args:
            parent_token: Parent folder token
            name: Document name
        
        Returns:
            Document token if successful, None otherwise
        """
        self._rate_limit()
        request = CreateDocumentRequest.builder().request_body(
            CreateDocumentRequestBody.builder().folder_token(parent_token).title(name).build()
        ).build()
        response = self.client.docx.v1.document.create(request, self._get_request_option())
        if response.success():
            return response.data.document.document_id
        logger.error(f"创建文档失败: {response.code} {response.msg}")
        return None

    def list_document_blocks(self, document_id: str) -> List[Any]:
        """List all blocks in a document with rate limit retry."""
        from lark_oapi.api.docx.v1.model import ListDocumentBlockRequest
        blocks = []
        page_token = None
        
        max_retries = API_MAX_RETRIES
        retry_delay = API_RETRY_BASE_DELAY
        
        while True:
            self._rate_limit()
            builder = ListDocumentBlockRequest.builder().document_id(document_id).page_size(500)
            if page_token: builder.page_token(page_token)
            
            for attempt in range(max_retries):
                resp = self.client.docx.v1.document_block.list(builder.build(), self._get_request_option())
                
                if resp.success():
                    if resp.data and resp.data.items: 
                        blocks.extend(resp.data.items)
                    page_token = resp.data.page_token
                    break
                elif resp.code == 99991400:  # Rate limit
                    if attempt < max_retries - 1:
                        logger.warning(f"Rate limited (99991400), retrying in {retry_delay}s...")
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    else:
                        logger.error(f"List blocks failed after {max_retries} retries: {resp.code} {resp.msg}")
                        return blocks
                else:
                    logger.error(f"List blocks failed: {resp.code} {resp.msg}")
                    return blocks
            
            if not page_token: 
                break
        
        return blocks

    def get_all_blocks(self, document_id: str) -> List[Any]:
        """Get all blocks from a document (alias for list_document_blocks)."""
        return self.list_document_blocks(document_id)

    def clear_document(self, document_id: str):
        """Clear all blocks from a document."""
        self._rate_limit()
        blocks = self.get_all_blocks(document_id)
        if not blocks: 
            return
        
        max_retries = API_MAX_RETRIES
        retry_delay = API_RETRY_BASE_DELAY
        
        for attempt in range(max_retries):
            request = BatchDeleteDocumentBlockChildrenRequest.builder().document_id(document_id).block_id(document_id).request_body(
                BatchDeleteDocumentBlockChildrenRequestBody.builder().start_index(0).end_index(len(blocks)).build()
            ).build()
            resp = self.client.docx.v1.document_block_children.batch_delete(request, self._get_request_option())
            
            if resp.success():
                logger.debug(f"Document {document_id} cleared successfully")
                return
            elif resp.code == 99991400:  # Rate limit
                if attempt < max_retries - 1:
                    logger.warning(f"Rate limited (99991400), retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    logger.error(f"Clear document failed after {max_retries} retries: {resp.code} {resp.msg}")
            else:
                logger.error(f"Clear document failed: {resp.code} {resp.msg}")
                return

    def create_folder(self, parent_token: str, name: str) -> Optional[str]:
        """Create a folder in Feishu drive.
        
        Args:
            parent_token: Parent folder token
            name: Folder name
        
        Returns:
            New folder token if successful, None otherwise
        """
        from lark_oapi.api.drive.v1 import CreateFolderFileRequest, CreateFolderFileRequestBody
        
        self._rate_limit()
        request = CreateFolderFileRequest.builder().request_body(
            CreateFolderFileRequestBody.builder().folder_token(parent_token).name(name).build()
        ).build()
        resp = self.client.drive.v1.file.create_folder(request, self._get_request_option())
        if resp.success():
            return resp.data.token
        return None

    def list_folder_files(self, folder_token: str) -> List[Any]:
        """List all files in a folder."""
        from lark_oapi.api.drive.v1 import ListFileRequest
        
        self._rate_limit()
        files = []
        page_token = None
        
        while True:
            builder = ListFileRequest.builder().folder_token(folder_token).page_size(200)
            if page_token:
                builder.page_token(page_token)
            resp = self.client.drive.v1.file.list(builder.build(), self._get_request_option())
            if not resp.success():
                return files
            if resp.data and resp.data.files:
                files.extend(resp.data.files)
            page_token = resp.data.page_token if resp.data else None
            if not page_token:
                break
        
        return files

    def get_file_info(self, file_token: str, obj_type: str = "docx") -> Optional[Dict[str, Any]]:
        """Get file information by token."""
        from lark_oapi.api.drive.v1.model import BatchQueryMetaRequest, MetaRequest, RequestDoc
        
        self._rate_limit()
        request = BatchQueryMetaRequest.builder().request_body(
            MetaRequest.builder().request_docs([RequestDoc.builder().doc_token(file_token).doc_type(obj_type).build()]).build()
        ).build()
        resp = self.client.drive.v1.meta.batch_query(request, self._get_request_option())
        if resp.success() and resp.data.metas:
            return resp.data.metas[0]
        return None

    def delete_file(self, file_token: str, file_type: str = "docx") -> bool:
        """Delete a file or folder by token.
        
        Args:
            file_token: The token of the file/folder to delete
            file_type: One of 'file', 'docx', 'folder', 'bitable', 'sheet', etc.
        """
        from lark_oapi.api.drive.v1 import DeleteFileRequest
        
        self._rate_limit()
        request = DeleteFileRequest.builder().file_token(file_token).type(file_type).build()
        resp = self.client.drive.v1.file.delete(request, self._get_request_option())
        if resp.success():
            logger.debug(f"Deleted {file_type}: {file_token}")
            return True
        logger.error(f"Delete failed: {resp.code} {resp.msg}")
        return False

    def get_or_create_assets_folder(self) -> Optional[str]:
        """Get or create the assets folder for file uploads."""
        root_token = self.get_root_folder_token()
        if not root_token:
            return None
        
        files = self.list_folder_files(root_token)
        for f in files:
            if f.name == "_assets" and f.type == "folder":
                return f.token
        
        # Create assets folder
        return self.create_folder(root_token, "_assets")

    def get_root_folder_token(self) -> Optional[str]:
        """Get root folder token (to be overridden by config)."""
        return None  # Override in main client
