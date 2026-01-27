# 📚 DocSync - Obsidian to Feishu/Lark

<div align="center">

**将您的 Obsidian 知识库无缝同步到飞书云文档**

[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-114%20passed-brightgreen.svg)](#测试)

</div>

---

## ✨ 核心特性

- 🔄 **智能双向同步** - 自动检测本地/云端变更，按时间戳智能选择同步方向
- 🎯 **完美 Markdown 支持** - 标题、列表、代码块、引用、表格、图片
- 🖼️ **智能资源处理** - 自动上传图片，支持 `![[image.png]]` 语法
- ⚡ **高效增量同步** - 基于 hash 比对 + difflib 增量更新
- 📂 **目录同步** - 递归同步整个文件夹，支持并发处理
- 🔐 **安全存储** - Token 存储在系统钥匙串
- 💾 **智能备份** - 自动备份，版本还原
- 🖥️ **桌面应用** - Electron GUI 界面
- 🔒 **线程安全** - 并发同步时资源索引加锁保护

---

## 🚀 快速开始

### 安装 (推荐)

您可以直接通过 pip 安装本项目，安装后可使用 `docsync` 命令：

```bash
git clone https://github.com/zhangjian94cn/doc-sync.git
cd doc-sync
pip install .

# 配置
docsync setup

# 同步
docsync sync
```

### 开发模式

如果您不想安装，也可以直接运行源码：

```bash
git clone https://github.com/zhangjian94cn/doc-sync.git
cd doc-sync
pip install -r requirements.txt

# 配置
python main.py setup  # 或者 python scripts/cli.py setup

# 同步
python main.py
```

### 桌面应用 (GUI)

```bash
cd electron-app
npm install
npm start
```

<img src="docs/screenshot.png" width="600" alt="DocSync GUI">

---

## 📋 命令速查

### 命令行

| 命令 | 说明 |
|------|------|
| `docsync setup` | 配置向导 |
| `docsync check` | 健康检查 |
| `docsync sync` | 执行同步 |
| `docsync restore <path>` | 还原备份 |
| `docsync clean` | 清理备份 |
| `docsync sync --force` | 强制覆盖云端（忽略云端更新） |
| `python main.py --overwrite` | 全量覆盖模式（清空云端后重新上传） |
| `python scripts/download_doc.py <doc_id>` | 下载飞书文档为 Markdown |
| `python scripts/compare_docs.py <local_file> <doc_token>` | 对比本地与云端文档 |
| `python scripts/compare_docs.py --config` | 批量对比配置中的所有任务 |

### 同步模式说明

| 模式 | 参数 | 说明 |
|------|------|------|
| **智能同步** | 无参数 | 根据修改时间自动判断同步方向 |
| **强制上传** | `--force` | 忽略云端更新，强制将本地内容上传 |
| **全量覆盖** | `--overwrite` | 清空云端文档后完全重写（适合格式错乱时使用） |

### 演示脚本

| 脚本 | 说明 |
|------|------|
| `python examples/api_demo.py` | API 功能演示 |
| `python examples/markdown_convert_demo.py` | Markdown 转换对比 |
| `python scripts/block_operations_demo.py` | 块 CRUD 操作演示 |

### 桌面应用

| 功能 | 位置 |
|------|------|
| 同步 | Dashboard → Sync Now |
| 强制同步 | Dashboard → ☑️ Force Sync |
| 任务管理 | Tasks → 添加/编辑任务 |
| 凭据设置 | Settings → App ID/Secret |
| 健康检查 | Tools → Run Health Check |
| 备份清理 | Tools → Clean Backups |
| 主题切换 | Appearance / 右上角按钮 |

---

## 🔧 配置

### 飞书应用设置

1. 访问 [飞书开放平台](https://open.feishu.cn/app)
2. 创建**企业自建应用**
3. 添加应用能力：**网页应用**
4. 配置权限（见下文权限列表）
5. 配置回调地址：`http://127.0.0.1:8000/callback`
6. **创建版本并发布上线**

### 权限配置

本项目需要以下飞书 API 权限：

| 权限标识 | 权限名称 | 用途 |
|----------|----------|------|
| `docx:document` | 查看、评论和下载云文档 | 读取云文档内容 |
| `docx:document:readonly` | 查看云文档 | 获取文档块列表 |
| `drive:drive` | 查看、评论和下载云空间中所有文件 | 访问云空间文件 |
| `drive:drive:readonly` | 查看云空间中文件夹结构 | 列出文件夹内容 |
| `drive:file:upload` | 上传文件到云空间 | 上传图片和附件 |

> **提示**：首次使用需要 OAuth 授权获取 User Access Token。程序会自动打开浏览器完成授权流程。

### 配置文件

```json
{
  "feishu_app_id": "cli_xxx",
  "feishu_app_secret": "xxx",
  "feishu_assets_token": "xxx",
  "tasks": [{
    "note": "工作笔记",
    "local": "/path/to/folder",
    "cloud": "folder_token",
    "vault_root": "/path/to/vault",
    "enabled": true,
    "force": false
  }]
}
```

### API 文档参考

本项目基于 [飞书开放平台 API](https://open.feishu.cn/document/home/index) 开发，主要使用以下 API：

<details>
<summary><b>📄 云文档 API (DocX)</b></summary>

| API | 用途 | 文档链接 |
|-----|------|----------|
| 获取文档所有块 | 读取文档内容 | [list blocks](https://open.feishu.cn/document/server-docs/docs/docs/docx-v1/document-block/list) |
| 创建块 | 添加文档内容 | [create block](https://open.feishu.cn/document/server-docs/docs/docs/docx-v1/document-block-children/create) |
| 更新块 | 修改内容 | [patch block](https://open.feishu.cn/document/server-docs/docs/docs/docx-v1/document-block/patch) |
| 删除块 | 删除内容 | [delete children](https://open.feishu.cn/document/server-docs/docs/docs/docx-v1/document-block-children/batch_delete) |
| 创建文档 | 新建文档 | [create docx](https://open.feishu.cn/document/server-docs/docs/docs/docx-v1/document/create) |

</details>

<details>
<summary><b>📂 云空间 API (Drive)</b></summary>

| API | 用途 | 文档链接 |
|-----|------|----------|
| 上传文件 | 上传图片/附件 | [upload file](https://open.feishu.cn/document/server-docs/docs/drive-v1/media/upload_all) |
| 下载文件 | 下载云端图片 | [download file](https://open.feishu.cn/document/server-docs/docs/drive-v1/media/download) |
| 创建文件夹 | 新建目录 | [create folder](https://open.feishu.cn/document/server-docs/docs/drive-v1/folder/create_folder) |
| 列出文件 | 获取目录列表 | [list files](https://open.feishu.cn/document/server-docs/docs/drive-v1/folder/list) |
| 获取元数据 | 获取文件信息 | [get file meta](https://open.feishu.cn/document/server-docs/docs/drive-v1/file/get) |
| 删除文件 | 删除文件/文件夹 | [delete file](https://open.feishu.cn/document/server-docs/docs/drive-v1/file/delete) |

</details>

<details>
<summary><b>🔐 认证 API (Auth)</b></summary>

| API | 用途 | 文档链接 |
|-----|------|----------|
| 获取 App Access Token | 应用认证 | [app access token](https://open.feishu.cn/document/server-docs/authentication-management/access-token/app_access_token_internal) |
| 获取 User Access Token | 用户授权 | [user access token](https://open.feishu.cn/document/server-docs/authentication-management/access-token/create) |
| 刷新 User Access Token | 刷新令牌 | [refresh token](https://open.feishu.cn/document/server-docs/authentication-management/access-token/create-2) |

</details>


---

## 📁 项目结构

```
doc-sync/
├── main.py                 # 主入口
├── scripts/
│   ├── cli.py              # 命令行工具
│   ├── compare_docs.py     # 文档对比工具
│   └── download_doc.py     # 文档下载
├── src/
│   ├── sync/               # 同步模块
│   │   ├── manager.py      # 单文件同步 (SyncManager)
│   │   ├── folder.py       # 文件夹同步 (FolderSyncManager)
│   │   ├── state.py        # 同步状态追踪
│   │   └── resource.py     # 资源索引
│   ├── converter/          # Markdown ↔ Feishu 转换器
│   ├── feishu/             # 飞书 API 模块
│   │   ├── base.py         # 基础客户端（认证、限流）
│   │   ├── blocks.py       # 块操作
│   │   ├── documents.py    # 文档操作
│   │   └── media.py        # 媒体上传
│   ├── core/               # 核心功能
│   │   ├── auth.py         # OAuth 认证
│   │   └── restore.py      # 备份还原
│   └── feishu_client.py    # 统一客户端入口
├── tests/                  # Python 测试
├── electron-app/           # 桌面应用
│   ├── gui/                # 前端界面
│   └── tests/              # GUI 测试
└── docs/                   # 文档
```

---

## 🏗️ 架构

```mermaid
graph TB
    subgraph "用户界面"
        CLI[命令行 CLI]
        GUI[Electron GUI]
    end
    
    subgraph "同步引擎"
        SM[SyncManager<br/>单文件同步]
        FM[FolderSyncManager<br/>文件夹同步]
        RS[ResourceIndex<br/>资源索引]
        ST[SyncState<br/>状态追踪]
    end
    
    subgraph "转换器"
        M2F[MarkdownToFeishu]
        F2M[FeishuToMarkdown]
    end
    
    subgraph "飞书客户端"
        FC[FeishuClient]
        BM[BlocksMixin]
        DM[DocumentsMixin]
        MM[MediaMixin]
    end
    
    CLI --> SM
    CLI --> FM
    GUI --> SM
    FM --> SM
    SM --> M2F
    SM --> F2M
    SM --> FC
    FC --> BM
    FC --> DM
    FC --> MM
    SM --> RS
    FM --> ST
```

---

## 🧪 测试

```bash
# Python 单元测试
pytest tests/ -v

# Electron 单元测试
cd electron-app && npm test

# Electron E2E 测试
cd electron-app && npm run test:e2e
```

**测试覆盖**：114 个 Python 测试 + Jest 9 + Playwright 20

---

## 📚 更多文档

- [使用指南](docs/USAGE_GUIDE.md) - 详细使用说明
- [更新日志](docs/CHANGELOG.md) - 版本记录

---

## ❓ 常见问题

| 问题 | 解决方案 |
|------|----------|
| `90003088` 错误 | 应用未发布，去控制台发布 |
| `1061004` 错误 | 无文件夹权限，换自己创建的 |
| `99991677` Token 过期 | 程序会自动刷新，若失败请重新登录 |
| `20005` Token 失效 | 程序会尝试自动刷新或引导重新登录 |
| 图片不显示 | 检查 `vault_root` 配置 |
| 端口 8000 占用 | 关闭占用端口的程序或修改 `AUTH_SERVER_PORT` |
| 同步后内容不一致 | 使用 `scripts/compare_docs.py` 对比排查 |

---

## 🤝 贡献

欢迎 PR 和 Issue！

---

<div align="center">

**⭐ 如果这个项目对您有帮助，请给一个 Star！**

MIT License | Made with ❤️ by [zhangjian94cn](https://github.com/zhangjian94cn)

</div>
