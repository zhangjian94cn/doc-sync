# DocSync: Obsidian to Feishu/Lark

**将你的 Obsidian 知识库无缝同步到飞书云文档 (Feishu/Lark Docx)。**

DocSync 是一个高效的同步工具，支持 Markdown 语法的完美还原、本地图片自动上传、目录结构递归同步以及智能增量更新。让你的知识库在云端触手可及。

[English Documentation](README.md)

---

## ✨ 核心特性

*   **Markdown 完美还原**：支持标题、列表（含嵌套）、代码块、引用、任务列表、粗体/斜体/删除线等。
*   **智能图片处理**：
    *   自动识别并上传本地图片。
    *   支持 **Obsidian Wiki Link** (`![[image.png]]`)。
    *   **全库资源索引**：无论图片在哪个子文件夹，都能自动找到并上传。
*   **用户身份同步**：使用 User Access Token，文档直接归属于你，而非应用机器人。
*   **增量更新**：基于 Block 指纹比对 (Tree Hash)，只更新变更部分，速度飞快且稳定。
*   **目录同步**：递归同步整个文件夹结构，保持本地与云端结构一致。
*   **自动 Token 刷新**：内置 Token 自动刷新机制，无需频繁手动登录。

## 🛠️ 安装与配置

### 1. 准备飞书应用

1.  登录 [飞书开放平台](https://open.feishu.cn/app)。
2.  创建一个“企业自建应用”。
3.  **权限管理**：开启以下权限：
    *   `云文档` -> `docx:document` (包含 create/read/write)
    *   `云空间` -> `drive:drive`, `drive:file:create`, `drive:file:read`
4.  **安全设置**：添加重定向 URL: `http://127.0.0.1:8000/callback` (用于自动登录)。
5.  **发布版本**：务必点击“创建版本”并发布，否则权限不生效。

### 2. 本地环境

```bash
# 克隆仓库
git clone https://github.com/your-repo/doc-sync.git
cd doc-sync

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置

编辑 `sync_config.json`，填入你的 App ID、Secret 以及同步任务。

```json
{
  "feishu_app_id": "cli_xxxxxxxx",
  "feishu_app_secret": "xxxxxxxxxxxxxxxx",
  "feishu_assets_token": "", 
  "tasks": [
    {
      "note": "我的笔记",
      "local": "/Users/xxx/obsidian/Vault/Folder",
      "cloud": "folder_token_from_url",
      "vault_root": "/Users/xxx/obsidian/Vault",
      "enabled": true,
      "force": false
    }
  ]
}
```

*   **全局配置 (Global Config)**:
    *   `feishu_app_id`, `feishu_app_secret`: 飞书应用凭证。
    *   `feishu_assets_token`: (可选) 指定用于存放上传图片/附件的飞书文件夹 Token。如果不填，程序会自动在根目录查找或创建名为 `DocSync_Assets` 的文件夹。
*   **任务配置 (Tasks)**:
    *   `local`: 本地 Markdown 文件或文件夹的绝对路径。
    *   `cloud`: 飞书文件夹 Token (用于同步文件夹) 或 文档 Token (用于同步单文件)。
    *   `vault_root`: Obsidian 仓库根目录 (用于解析绝对路径图片引用)。

## 🚀 使用方法

### 首次运行（授权）

运行任意同步命令，如果未检测到 Token，程序会自动引导你在浏览器中登录授权。授权成功后 Token 会自动保存到 `sync_config.json` 文件中。

### 运行同步

```bash
python3 main.py
```

这会读取 `sync_config.json` 中的 `tasks` 列表并依次执行。

### 命令行模式 (临时任务)

```bash
# 同步单个文件 (会自动检测目标是文件夹还是文档)
python3 main.py /path/to/note.md <target_token>

# 强制覆盖云端 (忽略时间戳检查)
python3 main.py /path/to/note.md <target_token> --force
```

### 其他实用命令

```bash
# 清理产生的备份文件 (*.bak.*)
python3 main.py --clean
```

## ❓ 常见问题

**Q: 报错 90003088 (Tenant has not purchased...)**
A: 通常是因为应用权限不足。请确保在飞书后台开通了 `docx:document` 等权限，并且**发布了版本**。然后重新运行程序重新授权。

**Q: 报错 1061004 (Forbidden)**
A: 你没有目标文件夹的权限。如果使用了 User Token，请确保同步的目标文件夹是你自己创建的（或者你有编辑权限）。你可以将配置中的 `cloud` 设为 `root` 同步到根目录，或者新建一个文件夹。

**Q: 图片显示不出来？**
A: 确保 `vault_root` 配置正确（或能自动检测到）。程序会自动扫描 `vault_root` 下的所有图片建立索引。

**Q: 列表嵌套没对齐？**
A: 我们已经优化了列表转换逻辑，支持多级缩进。如果仍有问题，请确保 Markdown 源码中使用标准的 Tab 或 4 空格缩进。

---
DocSync is an open-source project. Contributions are welcome!
