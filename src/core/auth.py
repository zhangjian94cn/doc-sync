import http.server
import socketserver
import urllib.parse
import webbrowser
import threading
from typing import Optional, Dict, Any

import requests

from src.config import FEISHU_APP_ID, FEISHU_APP_SECRET, AUTH_SERVER_PORT

REDIRECT_URI = f"http://127.0.0.1:{AUTH_SERVER_PORT}/callback"
ENV_FILE = ".env"

# Shared result container
auth_result = {"token": None, "refresh_token": None}

class AuthHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass # Silence request logs

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        if parsed_path.path == "/callback":
            query = urllib.parse.parse_qs(parsed_path.query)
            code = query.get("code", [None])[0]
            
            if code:
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"<h1>Login Successful!</h1><p>You can close this window and return to terminal.</p><script>window.close()</script>")
                
                try:
                    # Use the authenticator instance attached to server
                    token_data = self.server.authenticator._exchange_token(code)
                    if token_data:
                        auth_result["token"] = token_data.get("access_token")
                        auth_result["refresh_token"] = token_data.get("refresh_token")
                except Exception as e:
                    print(f"Auth Error: {e}")
                
                # Stop server in a separate thread to allow response to finish
                threading.Thread(target=self.server.shutdown).start()
            else:
                self.send_error(400, "Missing code")
        else:
            self.send_error(404)

class FeishuAuthenticator:
    def _get_app_access_token(self):
        url = "https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal"
        payload = {
            "app_id": FEISHU_APP_ID,
            "app_secret": FEISHU_APP_SECRET
        }
        try:
            resp = requests.post(url, json=payload)
            if resp.status_code == 200:
                return resp.json().get("app_access_token")
            print(f"Failed to get app_access_token: {resp.text}")
        except Exception as e:
            print(f"Error getting app token: {e}")
        return None

    def _exchange_token(self, code):
        app_token = self._get_app_access_token()
        if not app_token: return None

        url = "https://open.feishu.cn/open-apis/authen/v1/access_token"
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {app_token}"
        }
        payload = {
            "grant_type": "authorization_code",
            "code": code
        }
        
        try:
            resp = requests.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                return resp.json().get("data")
            else:
                print(f"Error exchanging token: {resp.text}")
        except Exception as e:
            print(f"Exception: {e}")
        return None

    def _refresh_token_api(self, refresh_token):
        app_token = self._get_app_access_token()
        if not app_token: return None
        
        url = "https://open.feishu.cn/open-apis/authen/v1/refresh_access_token"
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {app_token}"
        }
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token
        }
        try:
            resp = requests.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                return resp.json().get("data")
            print(f"Error refreshing token: {resp.text}")
        except Exception as e:
            print(f"Exception refreshing token: {e}")
        return None

    def save_tokens_to_config(self, access_token, refresh_token=None):
        from src import config
        config.save_tokens(access_token, refresh_token)
        print("✅ Tokens saved to sync_config.json")

    def login(self):
        print("\n🚀 Initiating Feishu Login...")
        print(f"Please ensure Redirect URI is configured: {REDIRECT_URI}")
        
        auth_url = f"https://open.feishu.cn/open-apis/authen/v1/index?redirect_uri={urllib.parse.quote(REDIRECT_URI)}&app_id={FEISHU_APP_ID}"
        print(f"Opening browser...")
        webbrowser.open(auth_url)
        
        # Reset result
        auth_result["token"] = None
        auth_result["refresh_token"] = None
        
        try:
            # Allow address reuse to prevent "Address already in use" error
            socketserver.TCPServer.allow_reuse_address = True
            with socketserver.TCPServer(("", AUTH_SERVER_PORT), AuthHandler) as httpd:
                httpd.authenticator = self
                print(f"📡 Waiting for callback on port {AUTH_SERVER_PORT}...")
                httpd.serve_forever()
        except OSError as e:
            if e.errno == 48:  # Address already in use (macOS)
                print(f"❌ Port {AUTH_SERVER_PORT} is already in use.")
                print(f"   Please close the application using this port or change AUTH_SERVER_PORT in config.")
            elif e.errno == 98:  # Address already in use (Linux)
                print(f"❌ Port {AUTH_SERVER_PORT} is already in use.")
                print(f"   Please close the application using this port or change AUTH_SERVER_PORT in config.")
            else:
                print(f"❌ Failed to start auth server: {e}")
            return None
        except Exception as e:
            print(f"❌ Auth server error: {e}")
            return None
            
        if auth_result["token"]:
            print("✅ Login Successful!")
            self.save_tokens_to_config(auth_result["token"], auth_result["refresh_token"])
            return auth_result["token"]
        else:
            print("❌ Login Failed.")
            return None

    def refresh(self):
        from src import config
        refresh_token = config.FEISHU_USER_REFRESH_TOKEN
        
        if not refresh_token:
            print("❌ No Refresh Token found. Cannot auto-refresh.")
            return None
            
        print("🔄 Refreshing User Access Token...")
        data = self._refresh_token_api(refresh_token)
        if data:
            new_access = data.get("access_token")
            new_refresh = data.get("refresh_token")
            self.save_tokens_to_config(new_access, new_refresh)
            
            # Update memory config (save_tokens handles this but good to be explicit)
            # config.FEISHU_USER_ACCESS_TOKEN = new_access
            # config.FEISHU_USER_REFRESH_TOKEN = new_refresh
            
            print(f"✅ Token Refreshed!")
            return new_access
        else:
            print("❌ Failed to refresh token. Refresh token might be expired.")
            return None

if __name__ == "__main__":
    auth = FeishuAuthenticator()
    auth.login()
