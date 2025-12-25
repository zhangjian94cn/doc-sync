# Obsidian Feishu Sync (飞书文档同步工具)

一个强大的双向同步工具，连接你的 **Obsidian (本地 Markdown)** 和 **飞书云文档**。

[English Documentation](README.md)

## ✨ 核心特性

- **🔄 双向智能同步**：自动检测更新，支持 本地 -> 云端 和 云端 -> 本地 的双向同步。
- **🖼️ 图片自动上传**：自动识别 Markdown 中的本地图片，上传至飞书云空间并插入文档。
- **📂 文件夹递归同步**：完美保持文件夹层级结构，一键同步整个知识库。
- **🛡️ 安全无忧**：
    - 覆盖本地文件前自动创建 `.bak` 备份。
    - 基于时间戳的冲突检测机制。
- **📝 完美富文本支持**：
    - 标题 (H1-H9)、列表 (无序/有序/任务)
    - 代码块、行内代码
    - 粗体、斜体、删除线、链接

## 📦 桌面客户端 (GUI)

我们现在提供了简单美观的桌面应用，支持 macOS, Windows 和 Linux！

### 安装

1.  前往 [Releases](https://github.com/your-repo/doc-sync/releases) 页面。
2.  下载对应系统的安装包（如 macOS 下载 `.dmg`，Windows 下载 `.exe`）。
3.  安装并运行 "DocSync"。

### 使用

1.  **设置**: 填入你的飞书 App ID 和 App Secret。
2.  **添加任务**: 选择本地文件夹，并填入飞书云端文件夹 Token。
3.  **运行**: 点击 "开始同步" (Start Sync) 按钮即可执行同步。

---

## 🚀 开发者 / 命令行 快速开始

如果你习惯使用命令行，或希望进行二次开发：

1.  **安装依赖**:
    ```bash
    git clone https://github.com/your-repo/doc-sync.git
    cd doc-sync
    pip install -r requirements.txt
    ```

2.  **配置环境**:
    ```bash
    cp .env.example .env
    # 编辑 .env 文件，填入你的 FEISHU_APP_ID 和 FEISHU_APP_SECRET
    ```

3.  **运行示例**:
    ```bash
    python3 run_example.py
    ```
    按照提示输入目标文件夹 Token（直接回车可使用根目录），即可看到演示效果。

## 📖 命令行使用指南

### 1. 文件夹同步 (推荐)
将本地文件夹完整同步到飞书云端文件夹。

```bash
python3 main.py /本地/文件夹/路径 <云端文件夹Token>
```
*   `云端文件夹Token`: 目标飞书文件夹的 Token。如果填 `root`，则同步到机器人的根目录。
    *   *提示：建议在飞书云盘新建一个文件夹，并复制其 Token 使用。*

### 2. 单文件同步
仅同步单个 Markdown 文件。

```bash
python3 main.py /本地/文件.md <文档Token> [--force]
```

### 3. 配置文件模式 (批量同步)
通过 `sync_config.json` 管理多个同步任务。

```json
[
  {
    "note": "我的知识库",
    "local": "/Users/me/obsidian/Vault",
    "cloud": "fldcnYourFolderToken",
    "enabled": true
  }
]
```
直接运行 `python3 main.py` 即可执行配置文件中的任务。

## 🛠️ 前置要求

- Python 3.8+
- 飞书开放平台应用 (需要开启 **云文档** 和 **云空间** 相关权限)

## 📄 开源协议

MIT
