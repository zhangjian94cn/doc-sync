import http.server
import socketserver
import urllib.parse
import webbrowser
import requests
import json
import os
import threading
from config import FEISHU_APP_ID, FEISHU_APP_SECRET

PORT = 8000
REDIRECT_URI = f"http://127.0.0.1:{PORT}/callback"
ENV_FILE = ".env"

# Shared result container
auth_result = {"token": None}

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
                        # We could also save refresh_token here
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

    def save_token_to_env(self, token):
        # Read existing .env
        lines = []
        if os.path.exists(ENV_FILE):
            with open(ENV_FILE, "r") as f:
                lines = f.readlines()
        
        # Update or Append
        new_lines = []
        found = False
        for line in lines:
            if line.startswith("FEISHU_USER_ACCESS_TOKEN="):
                new_lines.append(f"FEISHU_USER_ACCESS_TOKEN={token}\n")
                found = True
            else:
                new_lines.append(line)
        
        if not found:
            if new_lines and not new_lines[-1].endswith('\n'):
                new_lines.append('\n')
            new_lines.append(f"FEISHU_USER_ACCESS_TOKEN={token}\n")
            
        with open(ENV_FILE, "w") as f:
            f.writelines(new_lines)
        print("✅ Token saved to .env")

    def login(self):
        print("\n🚀 Initiating Feishu Login...")
        print(f"Please ensure Redirect URI is configured: {REDIRECT_URI}")
        
        auth_url = f"https://open.feishu.cn/open-apis/authen/v1/index?redirect_uri={urllib.parse.quote(REDIRECT_URI)}&app_id={FEISHU_APP_ID}"
        print(f"Opening browser...")
        webbrowser.open(auth_url)
        
        # Reset result
        auth_result["token"] = None
        
        with socketserver.TCPServer(("", PORT), AuthHandler) as httpd:
            httpd.authenticator = self
            print(f"📡 Waiting for callback...")
            httpd.serve_forever()
            
        if auth_result["token"]:
            print("✅ Login Successful!")
            self.save_token_to_env(auth_result["token"])
            return auth_result["token"]
        else:
            print("❌ Login Failed.")
            return None

if __name__ == "__main__":
    auth = FeishuAuthenticator()
    auth.login()
