# Obsidian Feishu Sync (Obsidian 飞书同步工具)

一个用于在 Obsidian (Markdown) 和 飞书/Lark 云文档之间进行双向同步的工具。

## 功能特性

*   **双向同步**：自动检测更新的版本（云端 vs 本地）并进行相应的同步。
    *   **本地 -> 云端**：将 Markdown 转换为飞书文档块（支持标题、列表、代码块、粗体/斜体/行内代码等）。
    *   **云端 -> 本地**：将飞书文档块转换回 Markdown 并覆盖本地文件（会自动备份）。
*   **安全优先**：
    *   在从云端覆盖本地文件之前，会自动创建一个 `.bak` 备份文件。
    *   通过检查时间戳来防止意外覆盖。
    *   支持 `--force` 标志强制执行 本地 -> 云端 的同步。
*   **富文本支持**：
    *   标题 (H1-H9)
    *   列表 (无序列表、有序列表、任务列表)
    *   代码块
    *   行内样式 (粗体, 斜体, 删除线, 行内代码, 链接)

## 前置条件

*   Python 3.8+
*   飞书开放平台应用 (需要开启 Docx 和 Drive 相关权限)

## 安装步骤

1.  克隆本项目代码。
2.  安装依赖：
    ```bash
    pip install -r requirements.txt
    ```
3.  配置环境变量：
    ```bash
    cp .env.example .env
    ```
    编辑 `.env` 文件，填入你的 `FEISHU_APP_ID` 和 `FEISHU_APP_SECRET`。

## 使用方法

### 1. 单文件同步 (命令行)

```bash
python3 main.py <path_to_markdown_file> <doc_token> [--force]
```

*   `path_to_markdown_file`: 本地 Markdown 文件的绝对路径。
*   `doc_token`: 飞书文档的 Token (通常在 URL 中找到: `https://.../docx/YOUR_TOKEN_HERE`)。
*   `--force`: 可选。强制将本地内容上传到云端，忽略时间戳和云端的更改。

### 2. 批量同步 (配置文件)

你可以在 `sync_config.json` 中配置多个需要同步的文件对。

1. 在项目根目录创建或编辑 `sync_config.json`：
```json
[
  {
    "note": "项目计划",
    "local": "/Users/username/obsidian/Plan.md",
    "cloud": "QhdpdzmwWoccPQxu1yAcvuuAn7b",
    "enabled": true
  },
  {
    "note": "会议记录",
    "local": "/Users/username/obsidian/Meeting.md",
    "cloud": "AnotherTokenHere",
    "enabled": true
  }
]
```

2. 直接运行脚本（不带参数）：
```bash
python3 main.py
```

3. (可选) 指定自定义配置文件：
```bash
python3 main.py --config my_custom_config.json
```

## 工作原理

1.  **时间戳检查**：比较本地文件和云端文档的最后修改时间。
2.  **云端较新**：
    *   下载云端内容。
    *   将飞书文档块转换为 Markdown。
    *   将本地文件备份为 `Note.md.bak.<timestamp>`。
    *   覆盖本地 `Note.md`。
3.  **本地较新 (或时间相同)**：
    *   解析本地 Markdown。
    *   清空云端文档内容。
    *   将新的内容块上传到飞书。

## 项目结构

*   `main.py`: 程序入口。
*   `src/sync.py`: 核心同步逻辑 (`SyncManager`)。
*   `src/feishu_client.py`: 飞书 Open API 的封装。
*   `src/converter.py`: Markdown <-> 飞书文档块的转换逻辑。
