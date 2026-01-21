import json
import os
from typing import Optional

CONFIG_FILE = "sync_config.json"
KEYRING_SERVICE = "docsync"

# ============================================================
# Global Configuration Variables
# ============================================================
FEISHU_APP_ID: str = ""
FEISHU_APP_SECRET: str = ""
FEISHU_USER_ACCESS_TOKEN: str = ""
FEISHU_USER_REFRESH_TOKEN: str = ""
FEISHU_ASSETS_TOKEN: str = ""

# ============================================================
# Application Constants (previously hardcoded)
# ============================================================
# OAuth callback server port
AUTH_SERVER_PORT: int = 8000

# Feishu API batch operation chunk size
BATCH_CHUNK_SIZE: int = 10

# Threshold for full sync vs incremental sync (number of changes)
# Set to 0 to always use full overwrite (more reliable for nested content)
SYNC_DIFF_THRESHOLD: int = 0

# Maximum workers for parallel operations
MAX_PARALLEL_WORKERS: int = 4

# API retry settings
API_MAX_RETRIES: int = 3
API_RETRY_BASE_DELAY: float = 1.0

# Whether to use keyring for secure token storage
USE_KEYRING: bool = True

# ============================================================
# Secure Token Storage (keyring)
# ============================================================
def _get_keyring():
    """Get keyring module if available."""
    try:
        import keyring
        return keyring
    except ImportError:
        return None


def _load_token_from_keyring(key: str) -> Optional[str]:
    """Load a token from keyring."""
    keyring = _get_keyring()
    if keyring and USE_KEYRING:
        try:
            return keyring.get_password(KEYRING_SERVICE, key)
        except Exception:
            pass
    return None


def _save_token_to_keyring(key: str, value: str) -> bool:
    """Save a token to keyring."""
    keyring = _get_keyring()
    if keyring and USE_KEYRING and value:
        try:
            keyring.set_password(KEYRING_SERVICE, key, value)
            return True
        except Exception:
            pass
    return False


# ============================================================
# Configuration Loading
# ============================================================
def load_config_from_json() -> None:
    """Load configuration from sync_config.json and keyring."""
    global FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_USER_ACCESS_TOKEN, FEISHU_USER_REFRESH_TOKEN, FEISHU_ASSETS_TOKEN
    
    # Load from JSON file
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    FEISHU_APP_ID = data.get("feishu_app_id", "")
                    FEISHU_APP_SECRET = data.get("feishu_app_secret", "")
                    FEISHU_ASSETS_TOKEN = data.get("feishu_assets_token", "")
                    
                    # Try to load tokens from keyring first
                    FEISHU_USER_ACCESS_TOKEN = _load_token_from_keyring("access_token") or data.get("feishu_user_access_token", "")
                    FEISHU_USER_REFRESH_TOKEN = _load_token_from_keyring("refresh_token") or data.get("feishu_user_refresh_token", "")
        except json.JSONDecodeError as e:
            print(f"配置文件 JSON 格式错误: {e}")
        except IOError as e:
            print(f"读取配置文件失败: {e}")


def save_tokens(access_token: str, refresh_token: str) -> None:
    """Save updated tokens to keyring (preferred) and JSON file (fallback)."""
    global FEISHU_USER_ACCESS_TOKEN, FEISHU_USER_REFRESH_TOKEN
    FEISHU_USER_ACCESS_TOKEN = access_token
    FEISHU_USER_REFRESH_TOKEN = refresh_token
    
    # Try to save to keyring first
    keyring_saved = False
    if _save_token_to_keyring("access_token", access_token):
        if _save_token_to_keyring("refresh_token", refresh_token):
            keyring_saved = True
    
    # Also save to JSON file (as backup or if keyring unavailable)
    data = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                content = json.load(f)
                if isinstance(content, dict):
                    data = content
                elif isinstance(content, list):
                    data = {"tasks": content}
        except Exception:
            pass
    
    if keyring_saved:
        # Don't store tokens in JSON if keyring is working
        data.pop("feishu_user_access_token", None)
        data.pop("feishu_user_refresh_token", None)
    else:
        # Fallback to JSON storage
        data["feishu_user_access_token"] = access_token
        data["feishu_user_refresh_token"] = refresh_token
    
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except IOError as e:
        print(f"保存配置文件失败: {e}")


# Load configuration on module import
load_config_from_json()

