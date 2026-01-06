# DocSync: Obsidian to Feishu/Lark

将你的 Obsidian 知识库无缝同步到飞书云文档 (Feishu/Lark Docx)。
支持 Markdown 语法、图片上传、增量更新、目录同步、以及 Obsidian 特有的 Wiki Link。

## ✨ 核心特性

- **Markdown 完美还原**：支持标题、列表、代码块、引用、任务列表等。
- **智能图片处理**：
  - 自动识别并上传本地图片。
  - 支持 **Obsidian Wiki Link** (`![[image.png]]`)。
  - **全库资源索引**：无论图片在哪个子文件夹，都能自动找到并上传。
- **用户身份同步**：使用 User Access Token，文档直接归属于你，而非应用机器人。
- **增量更新**：基于 Block 指纹比对，只更新变更部分，速度飞快。
- **目录同步**：递归同步整个文件夹结构。

## 🛠️ 安装与配置

### 1. 准备飞书应用

1. 登录 [飞书开放平台](https://open.feishu.cn/app)。
2. 创建一个“企业自建应用”。
3. **权限管理**：开启以下权限：
   - `云文档` -> `docx:document` (包含 create/read/write)
   - `云空间` -> `drive:drive`, `drive:file:create`, `drive:file:read`
4. **安全设置**：添加重定向 URL: `http://127.0.0.1:8000/callback` (用于自动登录)。
5. **发布版本**：务必点击“创建版本”并发布。

### 2. 本地环境

```bash
# 安装依赖
pip install -r requirements.txt
```

### 3. 配置凭证

复制 `.env.example` 到 `.env`，填入 `FEISHU_APP_ID` 和 `FEISHU_APP_SECRET`。

```ini
FEISHU_APP_ID=cli_xxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxx
# FEISHU_USER_ACCESS_TOKEN 留空，首次运行会自动获取
```

## 🚀 使用方法

### 首次运行（授权）

运行任意同步命令，如果未检测到 Token，程序会自动引导你在浏览器中登录授权。授权成功后 Token 会自动保存到 `.env` 文件。

### 配置文件模式 (推荐)

编辑 `sync_config.json`：

```json
[
  {
    "local": "/Users/xxx/obsidian/Vault/Folder",
    "cloud": "folder_token_from_url",
    "note": "我的笔记",
    "enabled": true,
    "force": false,
    "vault_root": "/Users/xxx/obsidian/Vault" 
  }
]
```

- `cloud`: 飞书文件夹 Token (URL 中 `folder/` 后面那串)。
- `vault_root`: Obsidian 仓库根目录 (用于解析绝对路径图片引用)。如果不填，程序会自动向上查找 `.obsidian` 文件夹来确定根目录。

运行：
```bash
python3 main.py
```

### 命令行模式

```bash
# 同步单个文件
python3 main.py /path/to/note.md <folder_token>

# 强制覆盖云端 (忽略时间戳检查)
python3 main.py /path/to/note.md <folder_token> --force
```

## ❓ 常见问题

**Q: 报错 90003088 (Tenant has not purchased...)**
A: 通常是因为应用权限不足。请确保在飞书后台开通了 `docx:document` 等权限，并且**发布了版本**。然后重新运行程序重新授权。

**Q: 报错 1061004 (Forbidden)**
A: 你没有目标文件夹的权限。如果使用了 User Token，请确保同步的目标文件夹是你自己创建的（或者你有编辑权限）。你可以将配置中的 `cloud` 设为 `root` 同步到根目录，或者新建一个文件夹。

**Q: 图片显示不出来？**
A: 确保 `vault_root` 配置正确（或能自动检测到）。程序会自动扫描 `vault_root` 下的所有图片建立索引。

**Q: 列表嵌套没对齐？**
A: 飞书 API 限制，目前通过全角空格模拟视觉缩进。建议使用 4 空格或 Tab 进行标准缩进。
