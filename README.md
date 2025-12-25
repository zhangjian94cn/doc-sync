# Obsidian Feishu Sync

A powerful bidirectional synchronization tool between **Obsidian (Markdown)** and **Feishu/Lark Docs**. Keep your local knowledge base and cloud docs in perfect sync.

[中文文档](README_CN.md)

## ✨ Features

- **🔄 Bidirectional Sync**: Automatically detects changes and syncs the newer version (Local ↔ Cloud).
- **🖼️ Image Support**: Automatically uploads local images to Feishu Drive and embeds them in the document.
- **📂 Folder Sync**: Recursively syncs entire folder structures, maintaining hierarchy.
- **🛡️ Safety First**:
    - Automatic `.bak` backups before overwriting local files.
    - Timestamp-based conflict detection.
- **📝 Rich Text Support**:
    - Headings (H1-H9)
    - Lists (Bullet, Ordered, Todo)
    - Code Blocks & Inline Code
    - Bold, Italic, Strikethrough, Links

## 🚀 Quick Start

Try it out immediately with our built-in example!

1.  **Clone & Install**:
    ```bash
    git clone https://github.com/your-repo/doc-sync.git
    cd doc-sync
    pip install -r requirements.txt
    ```

2.  **Configure**:
    ```bash
    cp .env.example .env
    # Edit .env and fill in your FEISHU_APP_ID and FEISHU_APP_SECRET
    ```

3.  **Run Example**:
    ```bash
    python3 run_example.py
    ```
    Follow the prompts to sync a sample vault to your Feishu Drive.

## 📖 Usage Guide

### 1. Folder Sync (Recommended)
Sync an entire local folder to a cloud folder.

```bash
python3 main.py /path/to/local/folder <cloud_folder_token>
```
*   `cloud_folder_token`: The token of the target Feishu folder. Use `root` to sync to the App's root directory.

### 2. Single File Sync
Sync a single Markdown file.

```bash
python3 main.py /path/to/file.md <doc_token> [--force]
```

### 3. Configuration File (Batch Sync)
Manage multiple sync tasks using `sync_config.json`.

```json
[
  {
    "note": "My Knowledge Base",
    "local": "/Users/me/obsidian/Vault",
    "cloud": "fldcnYourFolderToken",
    "enabled": true
  }
]
```
Run with `python3 main.py`.

## 🛠️ Requirements

- Python 3.8+
- Feishu/Lark Open Platform App (Enable **Docs** and **Drive** permissions)

## 📄 License

MIT
