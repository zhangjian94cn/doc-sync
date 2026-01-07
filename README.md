# DocSync: Obsidian to Feishu/Lark

**Seamlessly synchronize your Obsidian knowledge base to Feishu/Lark Cloud Documents (Docx).**

DocSync is a powerful synchronization tool that supports perfect Markdown rendering, automatic local image uploading, recursive directory synchronization, and intelligent incremental updates. Keep your knowledge base accessible in the cloud.

[中文文档](README_CN.md)

---

## ✨ Core Features

*   **Perfect Markdown Rendering**: Supports headings, lists (nested), code blocks, blockquotes, task lists, bold/italic/strikethrough, etc.
*   **Smart Image Handling**:
    *   Automatically identifies and uploads local images.
    *   Supports **Obsidian Wiki Link** (`![[image.png]]`).
    *   **Vault-wide Indexing**: Automatically finds and uploads images regardless of their location in subfolders.
*   **User Identity Sync**: Uses User Access Token, so documents belong directly to you, not a bot.
*   **Incremental Update**: Based on Block Tree Hash, only updates changed parts, making it fast and stable.
*   **Directory Sync**: Recursively synchronizes the entire folder structure, maintaining consistency between local and cloud.
*   **Auto Token Refresh**: Built-in automatic token refreshing mechanism, no need for frequent manual logins.

## 🛠️ Installation & Configuration

### 1. Prepare Feishu App

1.  Log in to [Feishu Open Platform](https://open.feishu.cn/app).
2.  Create a "Custom App" (Enterprise Self-built App).
3.  **Permissions**: Enable the following permissions:
    *   `Cloud Docs` -> `docx:document` (includes create/read/write)
    *   `Cloud Drive` -> `drive:drive`, `drive:file:create`, `drive:file:read`
4.  **Security Settings**: Add Redirect URL: `http://127.0.0.1:8000/callback` (for auto-login).
5.  **Publish Version**: You MUST click "Create Version" and publish it for permissions to take effect.

### 2. Local Environment

```bash
# Clone repository
git clone https://github.com/your-repo/doc-sync.git
cd doc-sync

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration

Edit `sync_config.json` to configure your App ID, Secret, and sync tasks.

```json
{
  "feishu_app_id": "cli_xxxxxxxx",
  "feishu_app_secret": "xxxxxxxxxxxxxxxx",
  "feishu_assets_token": "", 
  "tasks": [
    {
      "note": "My Notes",
      "local": "/Users/xxx/obsidian/Vault/Folder",
      "cloud": "folder_token_from_url",
      "vault_root": "/Users/xxx/obsidian/Vault",
      "enabled": true,
      "force": false
    }
  ]
}
```

*   **Global Config**:
    *   `feishu_app_id`, `feishu_app_secret`: Feishu App credentials.
    *   `feishu_assets_token`: (Optional) Token of the Feishu folder to store uploaded images/attachments. If left empty, the program will automatically find or create a `DocSync_Assets` folder in the root directory.
*   **Tasks**:
    *   `local`: Absolute path to the local Markdown file or folder.
    *   `cloud`: Feishu Folder Token (for folder sync) or Document Token (for single file sync).
    *   `vault_root`: Obsidian Vault root directory (used to resolve absolute image paths).

## 🚀 Usage

### First Run (Authorization)

Run any sync command. If no Token is detected, the program will automatically guide you to log in via browser. After successful authorization, the Token will be automatically saved to `sync_config.json`.

### Run Sync

```bash
python3 main.py
```

This will read the `tasks` list from `sync_config.json` and execute them sequentially.

### Command Line Mode (Ad-hoc Task)

```bash
# Sync a single file (Automatically detects if target is a folder or doc)
python3 main.py /path/to/note.md <target_token>

# Force overwrite cloud (Ignore timestamp check)
python3 main.py /path/to/note.md <target_token> --force
```

### Other Commands

```bash
# Clean up backup files (*.bak.*)
python3 main.py --clean
```

## ❓ FAQ

**Q: Error 90003088 (Tenant has not purchased...)**
A: Usually due to insufficient app permissions. Please ensure you have enabled `docx:document` permissions in the Feishu Console and **published a version**. Then re-run the program to re-authorize.

**Q: Error 1061004 (Forbidden)**
A: You do not have permission for the target folder. If using User Token, ensure the target folder was created by you (or you have edit rights). You can set `cloud` to `root` in the config to sync to the root directory, or create a new folder.

**Q: Images not showing up?**
A: Ensure `vault_root` is configured correctly (or can be auto-detected). The program scans all images under `vault_root` to build an index.

**Q: Nested lists not aligned?**
A: We have optimized the list conversion logic to support multi-level indentation. If issues persist, ensure your Markdown source uses standard Tab or 4-space indentation.

---
DocSync is an open-source project. Contributions are welcome!
