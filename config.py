import os
from dotenv import load_dotenv

load_dotenv()

FEISHU_APP_ID = os.getenv("FEISHU_APP_ID")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET")
# Optional: User Access Token for higher privileges
FEISHU_USER_ACCESS_TOKEN = os.getenv("FEISHU_USER_ACCESS_TOKEN")
# Optional: FEISHU_USER_ACCESS_TOKEN is deprecated in favor of Tenant Token

if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
    print("Warning: FEISHU_APP_ID or FEISHU_APP_SECRET is missing in .env")
    print("Please configure them to use the Bot (App) identity.")
