# Obsidian Feishu Sync

A bidirectional synchronization tool between Obsidian (Markdown) and Feishu/Lark Docs.

## Features

*   **Bidirectional Sync**: Automatically detects the newer version (Cloud vs Local) and syncs accordingly.
    *   **Local -> Cloud**: Converts Markdown to Feishu Blocks (Headings, Lists, Code, Bold/Italic/Inline Code supported).
    *   **Cloud -> Local**: Converts Feishu Blocks back to Markdown and overwrites local file (with automatic backup).
*   **Safety First**:
    *   Creates a `.bak` backup of your local file before overwriting from cloud.
    *   Checks timestamps to prevent accidental overwrites.
    *   Supports `--force` flag to enforce Local -> Cloud sync.
*   **Rich Content Support**:
    *   Headings (H1-H9)
    *   Lists (Bullet, Ordered, Todo)
    *   Code Blocks
    *   Inline Styles (Bold, Italic, Strikethrough, Inline Code, Links)

## Prerequisites

*   Python 3.8+
*   Feishu Open Platform App (with Docx and Drive permissions)

## Installation

1.  Clone the repository.
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Configure environment variables:
    ```bash
    cp .env.example .env
    ```
    Edit `.env` and fill in your `FEISHU_APP_ID`, `FEISHU_APP_SECRET`, and `FEISHU_USER_ACCESS_TOKEN`.

## Usage

### Important: Folder Visibility
By default, the App (Bot) syncs files to its own private cloud space ("My Space" of the bot). To view and manage these files:
1.  Create a **Folder** in your own Feishu Drive.
2.  Share this folder with your **App/Bot** (Search for the App Name in the Share/Collaborate menu) and grant **"Can Edit"** permission.
3.  Copy the folder token from the URL (e.g., `folder/fldcn...` -> `fldcn...`).
4.  Use this token in your configuration.

### 1. Folder Sync
Sync an entire local folder to a cloud folder.
```bash
python3 main.py /path/to/local/folder <cloud_folder_token>
```
*   `cloud_folder_token`: The token of the target Feishu folder. If you use `root`, it will sync to the Bot's root folder (not recommended for visibility).

### 2. Single File Sync (Command Line)
```bash
python3 main.py <path_to_markdown_file> <doc_token> [--force]
```

*   `path_to_markdown_file`: Absolute path to your local Markdown file.
*   `doc_token`: The token of the Feishu document (found in the URL: `https://.../docx/YOUR_TOKEN_HERE`).
*   `--force`: Optional. Forces upload from Local to Cloud, ignoring timestamps and cloud changes.

### 3. Batch Sync (Config File)
You can configure multiple sync tasks (both files and folders) in `sync_config.json`.

1. Create or edit `sync_config.json` in the project root:
```json
[
  {
    "note": "My Obsidian Vault",
    "local": "/Users/username/obsidian/Vault",
    "cloud": "fldcnYourSharedFolderToken",
    "enabled": true
  },
  {
    "note": "Project Plan (Single File)",
    "local": "/Users/username/obsidian/Plan.md",
    "cloud": "docxYourDocToken",
    "enabled": true
  }
]
```

2. Run the script without arguments:
```bash
python3 main.py
```

3. (Optional) Specify a custom config file:
```bash
python3 main.py --config my_custom_config.json
```

## How it works

1.  **Timestamp Check**: Compares the modification time of the local file and the cloud document.
2.  **Cloud Newer**:
    *   Downloads cloud content.
    *   Converts Feishu Blocks to Markdown.
    *   Backs up local file to `Note.md.bak.<timestamp>`.
    *   Overwrites `Note.md`.
3.  **Local Newer (or Equal)**:
    *   Parses local Markdown.
    *   Clears cloud document.
    *   Uploads new blocks to Feishu.

## Project Structure

*   `main.py`: Entry point.
*   `src/sync.py`: Core synchronization logic (`SyncManager`).
*   `src/feishu_client.py`: Wrapper for Lark Open API.
*   `src/converter.py`: Markdown <-> Feishu Block conversion logic.
