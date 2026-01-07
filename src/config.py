import json
import os

CONFIG_FILE = "sync_config.json"

# Global Configuration Variables
FEISHU_APP_ID = ""
FEISHU_APP_SECRET = ""
FEISHU_USER_ACCESS_TOKEN = ""
FEISHU_USER_REFRESH_TOKEN = ""
FEISHU_ASSETS_TOKEN = ""

def load_config_from_json():
    """Load configuration from sync_config.json"""
    global FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_USER_ACCESS_TOKEN, FEISHU_USER_REFRESH_TOKEN, FEISHU_ASSETS_TOKEN
    
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                if isinstance(data, dict):
                    FEISHU_APP_ID = data.get("feishu_app_id", "")
                    FEISHU_APP_SECRET = data.get("feishu_app_secret", "")
                    FEISHU_USER_ACCESS_TOKEN = data.get("feishu_user_access_token", "")
                    FEISHU_USER_REFRESH_TOKEN = data.get("feishu_user_refresh_token", "")
                    FEISHU_ASSETS_TOKEN = data.get("feishu_assets_token", "")
            except Exception as e:
                print(f"Error loading config: {e}")

def save_tokens(access_token, refresh_token):
    """Save updated tokens back to sync_config.json"""
    global FEISHU_USER_ACCESS_TOKEN, FEISHU_USER_REFRESH_TOKEN
    FEISHU_USER_ACCESS_TOKEN = access_token
    FEISHU_USER_REFRESH_TOKEN = refresh_token
    
    data = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            try:
                content = json.load(f)
                if isinstance(content, dict):
                    data = content
                elif isinstance(content, list):
                    data = {"tasks": content}
            except:
                pass
    
    data["feishu_user_access_token"] = access_token
    data["feishu_user_refresh_token"] = refresh_token
    
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# Load configuration on module import
load_config_from_json()
