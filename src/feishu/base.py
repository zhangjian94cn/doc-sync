"""
Base Feishu Client Module

Contains core client functionality:
- Authentication (app credentials, tokens)
- Rate limiting
- Asset caching
- Common utilities
"""

import json
import os
import hashlib
import time
import threading
from typing import Any, Dict, List, Optional

import requests as requests_module
import lark_oapi as lark

from src.logger import logger
from src.config import BATCH_CHUNK_SIZE, API_MAX_RETRIES, API_RETRY_BASE_DELAY


class FeishuClientBase:
    """Base class for Feishu API client with authentication and rate limiting."""
    
    # Rate limiting: max 5 requests per second (飞书 API 限制)
    _rate_limit_interval = 0.2  # 200ms between requests
    _last_request_time = 0
    _rate_limit_lock = threading.Lock()
    
    def __init__(self, app_id: str, app_secret: str, user_access_token: str = None):
        """Initialize the Feishu client.
        
        Args:
            app_id: Feishu app ID
            app_secret: Feishu app secret
            user_access_token: Optional user access token for user-level permissions
        """
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
        with FeishuClientBase._rate_limit_lock:
            now = time.time()
            elapsed = now - FeishuClientBase._last_request_time
            if elapsed < FeishuClientBase._rate_limit_interval:
                time.sleep(FeishuClientBase._rate_limit_interval - elapsed)
            FeishuClientBase._last_request_time = time.time()

    def _load_asset_cache(self) -> Dict[str, str]:
        """Load asset cache from disk."""
        if os.path.exists(self.asset_cache_path):
            try:
                with open(self.asset_cache_path, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {}

    def _save_asset_cache(self):
        """Save asset cache to disk."""
        try:
            os.makedirs(os.path.dirname(self.asset_cache_path), exist_ok=True)
            with open(self.asset_cache_path, 'w') as f:
                json.dump(self._asset_cache, f)
        except Exception as e:
            logger.warning(f"Failed to save asset cache: {e}")

    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA256 hash of a file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _get_request_option(self):
        """Get request option with user access token if available."""
        if self.user_access_token:
            return lark.RequestOption.builder().user_access_token(self.user_access_token).build()
        return None

    def _get_tenant_access_token(self) -> Optional[str]:
        """Get tenant access token from Feishu API."""
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        headers = {"Content-Type": "application/json; charset=utf-8"}
        data = {"app_id": self.app_id, "app_secret": self.app_secret}
        try:
            self._rate_limit()
            resp = requests_module.post(url, headers=headers, json=data, timeout=10)
            if resp.status_code == 200 and resp.json().get("code") == 0:
                return resp.json().get("tenant_access_token")
            logger.warning(f"获取 tenant_access_token 失败: {resp.status_code}")
            return None
        except requests_module.exceptions.Timeout:
            logger.error("获取 tenant_access_token 超时")
            return None
        except requests_module.exceptions.RequestException as e:
            logger.error(f"获取 tenant_access_token 网络错误: {e}")
            return None

    def _get_content_key(self, b_type: int) -> Optional[str]:
        """Get the content key for a block type."""
        content_keys = {
            2: 'text', 3: 'heading1', 4: 'heading2', 5: 'heading3',
            6: 'heading4', 7: 'heading5', 8: 'heading6', 9: 'heading7',
            10: 'heading8', 11: 'heading9', 12: 'bullet', 13: 'ordered',
            14: 'code', 15: 'quote', 17: 'todo'
        }
        return content_keys.get(b_type)
