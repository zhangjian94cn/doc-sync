import json
import os
from typing import Dict, Optional
from doc_sync.logger import logger

class SyncState:
    """
    Manages the synchronization state to track file history.
    This allows distinguishing between "newly created on cloud" and "deleted locally".
    """
    
    def __init__(self, root_path: str):
        self.root_path = os.path.abspath(root_path)
        self.state_path = os.path.join(self.root_path, ".doc_sync_state.json")
        self.data: Dict[str, Dict] = {}
        self.token_map: Dict[str, str] = {} # token -> relative_path
        self._load()

    def _load(self):
        if os.path.exists(self.state_path):
            try:
                with open(self.state_path, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
                    # Rebuild token map
                    for path, info in self.data.items():
                        if "token" in info:
                            self.token_map[info["token"]] = path
            except Exception as e:
                logger.warning(f"Failed to load sync state: {e}")
                self.data = {}

    def save(self):
        try:
            with open(self.state_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save sync state: {e}")

    def _get_rel_path(self, abs_path: str) -> str:
        if abs_path.startswith(self.root_path):
            return os.path.relpath(abs_path, self.root_path)
        return abs_path

    def update(self, abs_path: str, token: str, type: str = "docx"):
        rel_path = self._get_rel_path(abs_path)
        self.data[rel_path] = {
            "token": token,
            "type": type,
            "last_sync": os.path.getmtime(abs_path) if os.path.exists(abs_path) else 0
        }
        self.token_map[token] = rel_path
        self.save()

    def remove(self, abs_path: str):
        rel_path = self._get_rel_path(abs_path)
        if rel_path in self.data:
            token = self.data[rel_path].get("token")
            if token and token in self.token_map:
                del self.token_map[token]
            del self.data[rel_path]
            self.save()

    def remove_by_token(self, token: str):
        if token in self.token_map:
            rel_path = self.token_map[token]
            if rel_path in self.data:
                del self.data[rel_path]
            del self.token_map[token]
            self.save()

    def get_by_path(self, abs_path: str) -> Optional[Dict]:
        rel_path = self._get_rel_path(abs_path)
        return self.data.get(rel_path)

    def get_by_token(self, token: str) -> Optional[Dict]:
        if token in self.token_map:
            return self.data[self.token_map[token]]
        return None
