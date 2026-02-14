"""
Lightweight HTTP client for Bitable read operations.

This module deliberately avoids importing lark_oapi SDK, because the SDK
interferes with Python's subprocess/os.popen operations on macOS/Python 3.13.
All read operations use curl via os.popen instead.
"""

import os
import json
import urllib.parse
from typing import Any, Dict, List, Optional

from doc_sync.logger import logger


def bitable_http_get(url: str, token: str, params: Dict = None) -> Optional[Dict]:
    """Make a GET request to Feishu Bitable API using curl.
    
    This function runs curl in a subprocess. It must NOT be called from
    a process that has imported lark_oapi or created a lark.Client,
    as the SDK blocks all subsequent child process creation.
    
    Args:
        url: The API URL
        token: User access token or tenant access token
        params: Optional query parameters
        
    Returns:
        Parsed JSON response dict, or None on error
    """
    if not token:
        logger.error("无法获取 access token")
        return None
    
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    
    cmd = f'curl -s -m 15 -H "Authorization: Bearer {token}" -H "Content-Type: application/json; charset=utf-8" "{url}"'
    
    try:
        stream = os.popen(cmd)
        result = stream.read()
        stream.close()
        if not result:
            logger.error(f"HTTP GET 请求返回空响应: {url}")
            return None
        return json.loads(result)
    except Exception as e:
        logger.error(f"HTTP GET 请求失败: {url} - {e}")
        return None


def list_fields(app_token: str, table_id: str, token: str) -> List[Dict]:
    """List all fields in a Bitable table.
    
    Args:
        app_token: The Bitable app token
        table_id: Table ID
        token: User access token
        
    Returns:
        List of field info dicts
    """
    base_url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields"
    params = {"page_size": 100}
    
    all_fields = []
    page_token = None
    
    while True:
        if page_token:
            params["page_token"] = page_token
            
        data = bitable_http_get(base_url, token, params)
        if not data or data.get("code") != 0:
            code = data.get("code") if data else "None"
            msg = data.get("msg") if data else "No response"
            logger.error(f"列出字段失败: {code} {msg}")
            return all_fields
        
        items = data.get("data", {}).get("items") or []
        for item in items:
            all_fields.append({
                "field_id": item.get("field_id"),
                "field_name": item.get("field_name"),
                "type": item.get("type"),
                "property": item.get("property"),
            })
        
        if not data.get("data", {}).get("has_more"):
            break
        page_token = data["data"].get("page_token")
    
    return all_fields


def list_records(app_token: str, table_id: str, token: str,
                 page_size: int = 500) -> List[Dict]:
    """List all records in a Bitable table.
    
    Args:
        app_token: The Bitable app token
        table_id: Table ID
        token: User access token
        page_size: Number of records per page (max 500)
        
    Returns:
        List of record dicts with 'record_id' and 'fields'
    """
    base_url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"
    params = {"page_size": min(page_size, 500)}
    
    all_records = []
    page_token = None
    
    while True:
        if page_token:
            params["page_token"] = page_token
            
        data = bitable_http_get(base_url, token, params)
        if not data or data.get("code") != 0:
            code = data.get("code") if data else "None"
            msg = data.get("msg") if data else "No response"
            logger.error(f"列出记录失败: {code} {msg}")
            return all_records
        
        items = data.get("data", {}).get("items") or []
        for item in items:
            all_records.append({
                "record_id": item.get("record_id"),
                "fields": item.get("fields", {}),
            })
        
        if not data.get("data", {}).get("has_more"):
            break
        page_token = data["data"].get("page_token")
    
    return all_records
