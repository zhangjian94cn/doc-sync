"""
Feishu Block Operations Module

Contains methods for block manipulation:
- get_block, get_block_children
- update_block_text, batch_update_blocks
- delete_block_children, delete_blocks_by_index
- add_blocks, create_table
"""

import json
import time
from typing import Any, Dict, List, Optional

import lark_oapi as lark
import requests as requests_module

from doc_sync.logger import logger
from doc_sync.config import BATCH_CHUNK_SIZE, API_MAX_RETRIES, API_RETRY_BASE_DELAY


class BlockOperationsMixin:
    """Mixin class providing block operation methods for FeishuClient."""
    
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
                block_data = json.loads(lark.JSON.marshal(response.data.block))
                return block_data
            else:
                logger.error(f"Get block failed: code={response.code}, msg={response.msg}")
                return None
                
        except Exception as e:
            logger.error(f"Get block exception: {e}")
            return None

    def get_block_children(self, document_id: str, block_id: str,
                           page_size: int = 500,
                           with_descendants: bool = False) -> Optional[List[Dict[str, Any]]]:
        """Get all children blocks of a specified block.
        
        This method handles pagination automatically and returns all children.
        
        Args:
            document_id: Document ID
            block_id: Block ID whose children to retrieve (use document_id for root)
            page_size: Maximum number of blocks per page (default 500, max 500)
            with_descendants: If True, also fetch all nested children recursively
        
        Returns:
            List of block dicts, or None if failed
        """
        url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks/{block_id}/children"
        
        token = self.user_access_token or self._get_tenant_access_token()
        if not token:
            logger.error("Failed to get access token for get_block_children")
            return None
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        all_children = []
        page_token = None
        max_retries = API_MAX_RETRIES
        retry_delay = API_RETRY_BASE_DELAY
        
        while True:
            self._rate_limit()
            
            params = {"page_size": min(page_size, 500)}
            if page_token:
                params["page_token"] = page_token
            
            for attempt in range(max_retries):
                try:
                    resp = requests_module.get(url, headers=headers, params=params, timeout=30)
                    
                    if resp.status_code == 200:
                        data = resp.json()
                        
                        if data.get("code") == 99991400:  # Rate limit
                            if attempt < max_retries - 1:
                                logger.warning(f"Rate limited (99991400), retrying in {retry_delay}s...")
                                time.sleep(retry_delay)
                                retry_delay *= 2
                                continue
                            else:
                                logger.error("Rate limit exceeded after retries")
                                return all_children if all_children else None
                        
                        if data.get("code") == 0:
                            items = data.get("data", {}).get("items", [])
                            all_children.extend(items)
                            page_token = data.get("data", {}).get("page_token")
                            
                            if with_descendants:
                                for item in items:
                                    if item.get("children"):
                                        logger.success("Created descendants successfully")
                            break
                        else:
                            logger.error(f"Get block children failed: {data.get('code')} {data.get('msg')}")
                            return all_children if all_children else None
                    else:
                        logger.error(f"Get block children HTTP error: {resp.status_code}")
                        return all_children if all_children else None
                        
                except Exception as e:
                    logger.error(f"Get block children exception: {e}")
                    if attempt == max_retries - 1:
                        return all_children if all_children else None
            
            if not page_token:
                break
        
        return all_children

    def update_block_text(self, document_id: str, block_id: str, 
                          elements: List[Dict[str, Any]]) -> bool:
        """Update text block content with rich text elements.
        
        Args:
            document_id: Document ID
            block_id: Block ID to update
            elements: List of text elements
        
        Returns:
            bool: True if successful
        """
        from lark_oapi.api.docx.v1 import (
            PatchDocumentBlockRequest, UpdateBlockRequest, UpdateTextElementsRequest,
            TextElement, TextRun, TextElementStyle, MentionUser, MentionDoc, Reminder
        )
        
        self._rate_limit()
        
        try:
            text_elements = []
            for elem in elements:
                te_builder = TextElement.builder()
                
                if "text_run" in elem:
                    tr = elem["text_run"]
                    tr_builder = TextRun.builder().content(tr.get("content", ""))
                    
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

    def delete_block_children(self, document_id: str, block_id: str,
                              start_index: int, end_index: int,
                              client_token: str = None) -> bool:
        """Delete a range of child blocks from a parent block.
        
        Args:
            document_id: Document ID
            block_id: Parent block ID whose children to delete
            start_index: Start index (inclusive, 0-based)
            end_index: End index (exclusive)
            client_token: Optional idempotency token
        
        Returns:
            bool: True if successful
        """
        from lark_oapi.api.docx.v1 import (
            BatchDeleteDocumentBlockChildrenRequest,
            BatchDeleteDocumentBlockChildrenRequestBody
        )
        
        self._rate_limit()
        
        max_retries = API_MAX_RETRIES
        retry_delay = API_RETRY_BASE_DELAY
        
        for attempt in range(max_retries):
            try:
                builder = BatchDeleteDocumentBlockChildrenRequest.builder() \
                    .document_id(document_id) \
                    .block_id(block_id) \
                    .request_body(
                        BatchDeleteDocumentBlockChildrenRequestBody.builder()
                            .start_index(start_index)
                            .end_index(end_index)
                            .build()
                    )
                
                if client_token:
                    builder.client_token(client_token)
                
                request = builder.build()
                response = self.client.docx.v1.document_block_children.batch_delete(
                    request, self._get_request_option()
                )
                
                if response.success():
                    logger.debug(f"Deleted blocks [{start_index}:{end_index}] from {block_id}")
                    return True
                elif response.code == 99991400:  # Rate limit
                    if attempt < max_retries - 1:
                        logger.warning(f"Rate limited, retrying in {retry_delay}s...")
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    else:
                        logger.error("Rate limit exceeded after retries")
                        return False
                else:
                    logger.error(f"Delete block children failed: {response.code} {response.msg}")
                    return False
                    
            except Exception as e:
                logger.error(f"Delete block children exception: {e}")
                return False
        
        return False

    def delete_blocks_by_index(self, document_id: str, start_index: int, end_index: int) -> bool:
        """Delete blocks by index range from document root."""
        return self.delete_block_children(document_id, document_id, start_index, end_index)
