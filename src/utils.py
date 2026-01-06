import hashlib
import json
import os
from datetime import datetime
from typing import Any, Dict, List

def pad_center(text: str, width: int) -> str:
    """
    Pad string with spaces to center it, aware of wide characters (CJK).
    """
    display_len = 0
    for char in text:
        if ord(char) > 127:
            display_len += 2
        else:
            display_len += 1
    
    padding = width - display_len
    if padding <= 0:
        return text
    
    left = padding // 2
    right = padding - left
    return " " * left + text + " " * right

def parse_cloud_time(timestamp: str) -> float:
    """
    Heuristic to detect if timestamp is in milliseconds or seconds.
    """
    ts = int(timestamp)
    if ts > 10000000000:
        return ts / 1000.0
    return float(ts)

def calculate_block_hash(block_data: Any, is_cloud_obj: bool = False) -> str:
    """
    Compute a hash for block content to compare equality.
    Ignores IDs, revision info, and irrelevant styles.
    """
    content_fingerprint = {}
    
    if is_cloud_obj:
        # Map Cloud Object to simplified dict
        b_type = block_data.block_type
        content_fingerprint["type"] = b_type
        
        # Extract content based on type
        # This mapping must match what MarkdownToFeishu produces
        attr_map = {
            2: "text", 3: "heading1", 4: "heading2", 5: "heading3",
            6: "heading4", 7: "heading5", 8: "heading6", 9: "heading7",
            10: "heading8", 11: "heading9", 12: "bullet", 13: "ordered",
            14: "code", 22: "todo", 23: "file", 27: "image"
        }
        
        attr_name = attr_map.get(b_type)
        if attr_name and hasattr(block_data, attr_name):
            attr_obj = getattr(block_data, attr_name)
            if attr_obj:
                if hasattr(attr_obj, "to_dict"):
                     content_fingerprint["content"] = attr_obj.to_dict()
                elif hasattr(attr_obj, "__dict__"):
                     content_fingerprint["content"] = {k: v for k, v in attr_obj.__dict__.items() if not k.startswith('_')}
                else:
                     content_fingerprint["content"] = str(attr_obj)
        
        # Special handling for Image Block: Ignore token/path differences
        if b_type == 27 and isinstance(content_fingerprint.get("content"), dict):
            content_fingerprint["content"].pop("token", None)
                
    else:
        # Local Block Dict
        b_type = block_data.get("block_type")
        content_fingerprint["type"] = b_type
        
        for k, v in block_data.items():
            if k != "block_type" and k != "alt":
                if isinstance(v, dict):
                    content_fingerprint["content"] = v.copy()
                else:
                    content_fingerprint["content"] = v
                break
        
        # Special handling for Image Block (Local)
        if b_type == 27 and isinstance(content_fingerprint.get("content"), dict):
            content_fingerprint["content"].pop("token", None)
    
    # Clean and Normalize
    clean_fp = _clean_dict(content_fingerprint)
    
    # Pre-process content (e.g. empty images for comparison)
    if isinstance(clean_fp.get("content"), dict):
        clean_fp["content"] = _preprocess_content_for_hash(clean_fp.get("type"), clean_fp["content"])
    
    if isinstance(clean_fp, dict):
         clean_fp = {k: v for k, v in clean_fp.items() if v}

    return hashlib.md5(json.dumps(clean_fp, sort_keys=True, default=lambda x: str(x)).encode('utf-8')).hexdigest()

def _clean_dict(d: Any) -> Any:
    """Recursively remove empty/None values and specific style fields."""
    if hasattr(d, "to_dict"):
        d = d.to_dict()
    elif hasattr(d, "__dict__"):
        d = {k: v for k, v in d.__dict__.items() if not k.startswith('_')}

    if isinstance(d, dict):
        new_d = {}
        for k, v in d.items():
            # Ignore style fields that don't affect semantic content
            if k == "style": continue
            
            clean_v = _clean_dict(v)
            if v is None: continue
            
            if k == "text_element_style" and isinstance(clean_v, dict):
                clean_v = {sk: sv for sk, sv in clean_v.items() if sv}
                if not clean_v: continue
            
            # Keep empty structures if they are meaningful? Usually safe to drop.
            # But be careful with empty text runs.
            new_d[k] = clean_v
        return new_d
    
    if isinstance(d, list):
        return [_clean_dict(x) for x in d]
    
    return d

def _preprocess_content_for_hash(block_type, content_dict):
    # 1. Image / File: Empty it (we only check existence/position, not binary content change yet)
    if block_type == 27 or block_type == 23:
        return {}
    
    # 2. Code: Merge elements text (Cloud splits lines, Local might not)
    if block_type == 14:
        if "elements" in content_dict:
            full_text = ""
            for el in content_dict["elements"]:
                if "text_run" in el and "content" in el["text_run"]:
                    full_text += el["text_run"]["content"]
            return {"elements": [{"text_run": {"content": full_text}}]}
            
    return content_dict
