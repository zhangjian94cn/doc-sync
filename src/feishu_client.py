import json
import lark_oapi as lark
from lark_oapi.api.docx.v1 import *
from lark_oapi.api.drive.v1 import *
from lark_oapi.api.drive.v1.model.batch_query_meta_request import BatchQueryMetaRequest
from lark_oapi.api.drive.v1.model.meta_request import MetaRequest
from lark_oapi.api.drive.v1.model.request_doc import RequestDoc
from lark_oapi.core.model import BaseRequest
from lark_oapi.core.enum import HttpMethod, AccessTokenType
from typing import List, Dict, Any, Optional
import os

class FeishuClient:
    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        
        # Initialize Lark Client with App ID and Secret
        # This automatically handles Tenant Access Token management
        self.client = lark.Client.builder() \
            .app_id(app_id) \
            .app_secret(app_secret) \
            .build()
            
        print(f"[Auth] Initialized with App ID: {app_id[:5]}***. Using Tenant Access Token (Auto-managed).")

    def _get_request_option(self):
        # When using Tenant Access Token, we don't need to pass user_access_token
        # The SDK uses the internal token manager automatically.
        return None

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
