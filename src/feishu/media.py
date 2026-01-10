"""
Feishu Media Operations Module

Contains methods for media/file handling:
- upload_image, download_image
- upload_file, update_block_image
"""

import os
from typing import Optional

import requests as requests_module

from src.logger import logger


class MediaOperationsMixin:
    """Mixin class providing media operation methods for FeishuClient."""
    
    def upload_image(self, file_path: str, parent_node_token: str, 
                     drive_route_token: str = None) -> Optional[str]:
        """Upload an image to Feishu drive.
        
        Args:
            file_path: Local path to image file
            parent_node_token: Parent folder or document token
            drive_route_token: Optional drive route token
        
        Returns:
            File token if successful, None otherwise
        """
        if not os.path.exists(file_path):
            logger.error(f"Image file not found: {file_path}")
            return None
        
        # Check cache
        try:
            file_hash = self._calculate_file_hash(file_path)
            if file_hash in self._asset_cache:
                logger.debug(f"Image found in cache: {os.path.basename(file_path)}")
                return self._asset_cache[file_hash]
        except Exception:
            pass
        
        url = "https://open.feishu.cn/open-apis/drive/v1/medias/upload_all"
        token = self.user_access_token or self._get_tenant_access_token()
        
        if not token:
            logger.error("Failed to get access token for image upload")
            return None
        
        headers = {"Authorization": f"Bearer {token}"}
        
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        
        self._rate_limit()
        
        try:
            with open(file_path, 'rb') as f:
                files = {'file': (file_name, f)}
                data = {
                    'file_name': file_name,
                    'parent_type': 'docx_image',
                    'parent_node': parent_node_token,
                    'size': str(file_size)
                }
                
                resp = requests_module.post(url, headers=headers, files=files, data=data, timeout=60)
                
                if resp.status_code == 200:
                    result = resp.json()
                    if result.get("code") == 0:
                        file_token = result.get("data", {}).get("file_token")
                        
                        # Cache the result
                        if file_token:
                            self._asset_cache[file_hash] = file_token
                            self._save_asset_cache()
                        
                        return file_token
                    else:
                        logger.error(f"Image upload failed: {result.get('code')} {result.get('msg')}")
                else:
                    logger.error(f"Image upload HTTP error: {resp.status_code}")
                    
        except Exception as e:
            logger.error(f"Image upload exception: {e}")
        
        return None

    def download_image(self, file_token: str, save_path: str) -> bool:
        """Download an image from Feishu drive.
        
        Args:
            file_token: File token to download
            save_path: Local path to save the image
        
        Returns:
            True if successful
        """
        url = f"https://open.feishu.cn/open-apis/drive/v1/medias/{file_token}/download"
        token = self.user_access_token or self._get_tenant_access_token()
        
        if not token:
            return False
        
        headers = {"Authorization": f"Bearer {token}"}
        
        self._rate_limit()
        
        try:
            resp = requests_module.get(url, headers=headers, stream=True, timeout=60)
            if resp.status_code == 200:
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                with open(save_path, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                return True
        except Exception as e:
            logger.error(f"Image download failed: {e}")
        
        return False

    def upload_file(self, file_path: str, parent_node_token: str, 
                    drive_route_token: str = None, parent_type: str = None) -> Optional[str]:
        """Upload a file to Feishu drive.
        
        Args:
            file_path: Local path to file
            parent_node_token: Parent folder token
            drive_route_token: Optional drive route token
            parent_type: Optional parent type ('explorer' or 'docx_file')
        
        Returns:
            File token if successful, None otherwise
        """
        if not os.path.exists(file_path):
            return None
        
        # Check cache
        try:
            file_hash = self._calculate_file_hash(file_path)
            if file_hash in self._asset_cache:
                logger.debug(f"File found in cache (deduplicated): {os.path.basename(file_path)}")
                return self._asset_cache[file_hash]
        except Exception:
            pass
        
        url = "https://open.feishu.cn/open-apis/drive/v1/files/upload_all"
        token = self.user_access_token or self._get_tenant_access_token()
        
        if not token:
            return None
        
        headers = {"Authorization": f"Bearer {token}"}
        
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        p_type = parent_type or "explorer"
        
        self._rate_limit()
        
        try:
            with open(file_path, 'rb') as f:
                files = {'file': (file_name, f)}
                data = {
                    'file_name': file_name,
                    'parent_type': p_type,
                    'parent_node': parent_node_token,
                    'size': str(file_size)
                }
                
                resp = requests_module.post(url, headers=headers, files=files, data=data, timeout=120)
                
                if resp.status_code == 200:
                    result = resp.json()
                    if result.get("code") == 0:
                        file_token = result.get("data", {}).get("file_token")
                        
                        # Cache the result
                        if file_token:
                            self._asset_cache[file_hash] = file_token
                            self._save_asset_cache()
                        
                        return file_token
                    else:
                        logger.error(f"File upload failed: {result.get('code')} {result.get('msg')}")
                else:
                    logger.error(f"File upload HTTP error: {resp.status_code}")
                    
        except Exception as e:
            logger.error(f"File upload exception: {e}")
        
        return None

    def update_block_image(self, document_id: str, block_id: str, token: str) -> bool:
        """Update an image block with a new image token.
        
        Args:
            document_id: Document ID
            block_id: Image block ID to update
            token: New image token
        
        Returns:
            True if successful
        """
        from lark_oapi.api.docx.v1 import (
            PatchDocumentBlockRequest, UpdateBlockRequest, ReplaceImageRequest
        )
        
        self._rate_limit()
        
        request = PatchDocumentBlockRequest.builder() \
            .document_id(document_id) \
            .block_id(block_id) \
            .document_revision_id(-1) \
            .request_body(
                UpdateBlockRequest.builder()
                    .replace_image(
                        ReplaceImageRequest.builder().token(token).build()
                    )
                    .build()
            ).build()
        
        response = self.client.docx.v1.document_block.patch(request, self._get_request_option())
        return response.success()

    def update_block_file(self, document_id: str, block_id: str, token: str) -> bool:
        """Update a file block with a new file token.
        
        Args:
            document_id: Document ID
            block_id: File block ID to update
            token: New file token
        
        Returns:
            True if successful
        """
        from lark_oapi.api.docx.v1 import (
            PatchDocumentBlockRequest, UpdateBlockRequest, ReplaceFileRequest
        )
        
        self._rate_limit()
        
        request = PatchDocumentBlockRequest.builder() \
            .document_id(document_id) \
            .block_id(block_id) \
            .document_revision_id(-1) \
            .request_body(
                UpdateBlockRequest.builder()
                    .replace_file(
                        ReplaceFileRequest.builder().token(token).build()
                    )
                    .build()
            ).build()
        
        response = self.client.docx.v1.document_block.patch(request, self._get_request_option())
        return response.success()
