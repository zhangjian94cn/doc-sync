# 📚 DocSync - Obsidian to Feishu/Lark

<div align="center">

**将您的 Obsidian 知识库无缝同步到飞书云文档**

[![Python Version](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

[English](README.md) | [中文文档](README_CN.md)

</div>

---

## ✨ 核心特性

### 🎯 完美的 Markdown 支持
- ✅ **标题** (H1-H9)
- ✅ **列表** (有序、无序、任务列表、多级嵌套)
- ✅ **代码块** (支持语法高亮)
- ✅ **引用块**
- ✅ **文本样式** (粗体、斜体、删除线、行内代码)
- ✅ **链接和图片**

### 🖼️ 智能资源处理
- 📤 **自动上传** - 识别并上传本地图片和附件
- 🔗 **Obsidian 支持** - 完美支持 Wiki 链接 `![[image.png]]`
- 📁 **递归索引** - 自动查找仓库中任意位置的资源文件
- 📎 **文件支持** - 支持图片、视频、PDF、Office 文档等多种格式

### ⚡ 高效同步
- 🔄 **增量更新** - 基于 Block Tree Hash，只更新变更部分
- 📂 **目录同步** - 递归同步整个文件夹结构
- 🎭 **用户身份** - 使用 User Access Token，文档归属于你而非机器人
- 🔐 **自动续期** - 内置 Token 自动刷新，无需频繁登录

### 🛠️ 易用性
- 🎨 **配置向导** - 交互式配置向导，快速上手
- 🩺 **健康检查** - 一键检查环境和配置状态
- 📊 **详细日志** - 彩色日志输出，清晰显示同步过程
- 🎚️ **日志级别** - 支持 DEBUG/INFO/WARNING/ERROR 级别控制

---

## 🚀 快速开始

### 1️⃣ 安装

```bash
# 克隆仓库
git clone https://github.com/zhangjian94cn/doc-sync.git
cd doc-sync

# 安装依赖
pip install -r requirements.txt
```

### 2️⃣ 配置飞书应用

<details>
<summary><b>点击展开详细步骤</b></summary>

1. 访问 [飞书开放平台](https://open.feishu.cn/app)
2. 点击 **创建企业自建应用**
3. 配置应用权限：
   - `云文档` -> `docx:document` (文档的创建、读取、编辑)
   - `云空间` -> `drive:drive` (云空间基础权限)
   - `云空间` -> `drive:file:create` (文件创建)
   - `云空间` -> `drive:file:read` (文件读取)
4. 设置回调地址：`http://127.0.0.1:8000/callback`
5. **重要**：点击 **创建版本** 并发布，权限才会生效

</details>

### 3️⃣ 运行配置向导

```bash
python3 scripts/setup_wizard.py
```

向导会引导您：
- 输入飞书应用凭证
- 配置同步任务
- 设置资源存储位置

### 4️⃣ 开始同步

```bash
# 运行配置的所有同步任务
python3 main.py

# 强制覆盖云端（忽略时间戳检查）
python3 main.py --force

# 同步单个文件（临时任务）
python3 main.py /path/to/note.md <folder_or_doc_token>
```

---

## 📖 详细文档

### 配置文件说明

配置文件 `sync_config.json` 包含以下部分：

```json
{
  "feishu_app_id": "cli_xxxxxxxxxx",
  "feishu_app_secret": "your_app_secret",
  "feishu_assets_token": "",
  "tasks": [
    {
      "note": "工作笔记",
      "local": "/Users/xxx/Obsidian/Work",
      "cloud": "folder_token_from_feishu_url",
      "vault_root": "/Users/xxx/Obsidian",
      "enabled": true,
      "force": false
    }
  ]
}
```

#### 全局配置
- `feishu_app_id`: 飞书应用 ID (以 `cli_` 开头)
- `feishu_app_secret`: 飞书应用密钥
- `feishu_assets_token`: (可选) 资源存储文件夹 Token

#### 任务配置
- `note`: 任务描述
- `local`: 本地文件或文件夹路径
- `cloud`: 飞书文件夹或文档 Token
- `vault_root`: Obsidian 仓库根目录
- `enabled`: 是否启用该任务
- `force`: 是否强制覆盖云端

### 如何获取 Token

#### 文件夹 Token
1. 在飞书中打开目标文件夹
2. 从 URL 复制 Token：`https://feishu.cn/drive/folder/[THIS_IS_TOKEN]`

#### 文档 Token
1. 在飞书中打开目标文档
2. 从 URL 复制 Token：`https://feishu.cn/docx/[THIS_IS_TOKEN]`

---

## 🛠️ 高级功能

### 日志级别控制

```bash
# 设置日志级别为 DEBUG（显示所有日志）
export DOCSYNC_LOG_LEVEL=DEBUG
python3 main.py

# 设置日志级别为 ERROR（只显示错误）
export DOCSYNC_LOG_LEVEL=ERROR
python3 main.py
```

### 健康检查

```bash
python3 scripts/health_check.py
```

检查项目：
- ✅ Python 版本
- ✅ 依赖包安装
- ✅ 配置文件完整性
- ✅ 飞书 API 连接

### 清理备份文件

```bash
python3 main.py --clean
```

---

## 💡 使用技巧

### 1. 首次授权
首次运行时，程序会自动打开浏览器引导您授权。授权后 Token 会自动保存，无需每次登录。

### 2. 多任务配置
您可以在 `sync_config.json` 中配置多个同步任务，程序会按顺序执行。

### 3. 选择性同步
使用 `enabled: false` 可以临时禁用某个任务，而不需要删除配置。

### 4. 强制同步
使用 `--force` 参数可以忽略时间戳检查，强制覆盖云端内容。

---

## ❓ 常见问题

<details>
<summary><b>Q: 提示 "90003088 Tenant has not purchased" 错误</b></summary>

**A:** 权限配置不足。请确保：
1. 在飞书控制台启用了所需权限
2. **点击了"创建版本"并发布**
3. 重新运行程序进行授权

</details>

<details>
<summary><b>Q: 提示 "1061004 Forbidden" 错误</b></summary>

**A:** 没有目标文件夹的权限。请确保：
1. 目标文件夹是您创建的（或您有编辑权限）
2. 或者使用 `"cloud": "root"` 同步到根目录
3. 或者在飞书中新建一个文件夹

</details>

<details>
<summary><b>Q: 图片无法显示</b></summary>

**A:** 请检查：
1. `vault_root` 配置是否正确
2. 图片文件是否存在
3. 图片路径引用是否正确

程序会递归扫描 `vault_root` 下的所有图片建立索引。

</details>

<details>
<summary><b>Q: 列表嵌套层级不对</b></summary>

**A:** 确保 Markdown 源文件使用标准的 Tab 或 4 空格缩进。

</details>

<details>
<summary><b>Q: 如何同步到指定文档而不是文件夹</b></summary>

**A:** 将 `cloud` 字段设置为文档的 Token（而不是文件夹 Token）。

</details>

---

## 🤝 贡献

欢迎贡献代码、报告问题或提出建议！

1. Fork 本仓库
2. 创建您的特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交您的更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

---

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

---

## 🙏 致谢

- [Lark Open Platform](https://open.feishu.cn/) - 飞书开放平台
- [markdown-it-py](https://github.com/executablebooks/markdown-it-py) - Markdown 解析器
- 所有贡献者和使用者

---

## 📞 联系方式

- **Issues**: [GitHub Issues](https://github.com/zhangjian94cn/doc-sync/issues)
- **Pull Requests**: [GitHub PRs](https://github.com/zhangjian94cn/doc-sync/pulls)

---

<div align="center">

**⭐ 如果这个项目对您有帮助，请给一个 Star！**

Made with ❤️ by [zhangjian94cn](https://github.com/zhangjian94cn)

</div>
