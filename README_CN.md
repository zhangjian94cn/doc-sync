# Obsidian Feishu Sync (飞书文档同步工具)

一个强大的双向同步工具，连接你的 **Obsidian (本地 Markdown)** 和 **飞书云文档**。

[English Documentation](README.md)

## ✨ 核心特性

- **🔄 双向智能同步**：自动检测更新，支持 本地 -> 云端 和 云端 -> 本地 的双向同步。
- **🖼️ 图片自动上传**：自动识别 Markdown 中的本地图片，上传至飞书云空间并插入文档。
- **📂 文件夹递归同步**：完美保持文件夹层级结构，一键同步整个知识库。
- **🛡️ 安全备份与还原**：
    - 每次覆盖本地文件前自动创建带有**批次ID**的备份。
    - 提供交互式还原工具，支持一键回滚到任意历史版本。
- **📝 完美富文本支持**：
    - 标题 (H1-H9)、列表 (无序/有序/任务)
    - 代码块、行内代码
    - 粗体、斜体、删除线、链接

## 📦 桌面客户端 (GUI)

我们现在提供了简单美观的桌面应用，支持 macOS, Windows 和 Linux！

### 安装与运行

1.  **安装依赖**:
    ```bash
    cd electron-app && npm install
    ```
2.  **启动应用**:
    ```bash
    ./start_gui.sh
    ```

## 🚀 命令行快速开始

### 1. 安装

```bash
git clone https://github.com/your-repo/doc-sync.git
cd doc-sync
pip install -r requirements.txt
```

### 2. 配置凭证

复制 `.env.example` 为 `.env` 并填入你的飞书应用凭证：

```bash
FEISHU_APP_ID=cli_xxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxx
```

### 3. 使用指南

#### 📂 文件夹同步 (推荐)
将本地 Obsidian 仓库完整同步到飞书云端文件夹。

```bash
python3 main.py /本地/文件夹/路径 <云端文件夹Token>
```

#### 📄 单文件同步
仅同步单个 Markdown 文件。

```bash
python3 main.py /本地/文件.md <文档Token> [--force]
```

#### ↩️ 备份还原 (New!)
如果不小心覆盖了本地文件，可以使用还原模式查看历史版本并回滚。

```bash
python3 main.py --restore /本地/文件夹/路径
```
*系统会列出所有备份批次，选择序号即可一键还原该批次下的所有文件。*

#### ⚙️ 批量同步 (配置文件)
通过 `sync_config.json` 管理多个同步任务，直接运行 `python3 main.py` 即可。

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

## 🛠️ 常用命令速查

| 功能 | 命令 | 说明 |
| :--- | :--- | :--- |
| **同步** | `python3 main.py [path] [token]` | 基础同步命令 |
| **强制上传** | `... --force` | 忽略时间戳，强制覆盖云端 |
| **还原备份** | `python3 main.py --restore [path]` | 交互式还原历史版本 |
| **清理备份** | `python3 main.py --clean` | 删除所有 .bak 备份文件 |
| **指定根目录** | `... --vault-root [path]` | 解决绝对路径资源引用问题 |
| **查看帮助** | `python3 main.py -h` | 显示完整帮助信息 |

## 📄 开源协议

MIT
