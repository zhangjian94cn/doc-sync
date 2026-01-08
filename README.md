# 📚 DocSync - Obsidian to Feishu/Lark

<div align="center">

**将您的 Obsidian 知识库无缝同步到飞书云文档**

[![Python Version](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](docs/CONTRIBUTING.md)

</div>

---

## ✨ 核心特性

- 🎯 **完美 Markdown 支持** - 标题、列表、代码块、引用、图片等
- 🖼️ **智能资源处理** - 自动上传本地图片，支持 `![[image.png]]` 语法
- ⚡ **高效同步** - 增量更新，只同步变更部分
- 📂 **目录同步** - 递归同步整个文件夹结构
- 🔐 **安全存储** - Token 存储在系统钥匙串中
-  **智能备份** - 自动备份，支持版本还原

---

## 🚀 快速开始

### 安装

```bash
git clone https://github.com/zhangjian94cn/doc-sync.git
cd doc-sync
pip install -r requirements.txt
```

### 配置

```bash
# 运行配置向导
python scripts/cli.py setup

# 检查环境
python scripts/cli.py check
```

### 同步

```bash
# 执行同步
python main.py

# 强制覆盖云端
python main.py --force

# 同步指定文件
python main.py /path/to/note.md <folder_token>
```

---

## 📋 命令速查

| 命令 | 说明 |
|------|------|
| `python scripts/cli.py setup` | 配置向导 |
| `python scripts/cli.py check` | 健康检查 |
| `python scripts/cli.py sync` | 执行同步 |
| `python scripts/cli.py restore <path>` | 还原备份 |
| `python scripts/cli.py clean` | 清理备份 |
| `python main.py --help` | 查看所有选项 |

---

## 🔧 配置飞书应用

<details>
<summary><b>点击展开详细步骤</b></summary>

1. 访问 [飞书开放平台](https://open.feishu.cn/app)
2. 创建**企业自建应用**
3. 配置权限：
   - `docx:document` - 文档读写
   - `drive:drive` - 云空间权限
   - `drive:file:create` - 创建文件
   - `drive:file:read` - 读取文件
4. 设置回调地址：`http://127.0.0.1:8000/callback`
5. **创建版本并发布**（权限才会生效）

</details>

---

## 📖 配置文件

`sync_config.json` 示例：

```json
{
  "feishu_app_id": "cli_xxxxxxxxxx",
  "feishu_app_secret": "your_secret",
  "tasks": [
    {
      "note": "工作笔记",
      "local": "/Users/xxx/Obsidian/Work",
      "cloud": "folder_token",
      "vault_root": "/Users/xxx/Obsidian",
      "enabled": true
    }
  ]
}
```

**获取 Token**：打开飞书文件夹/文档，从 URL 复制
- 文件夹：`https://feishu.cn/drive/folder/[TOKEN]`
- 文档：`https://feishu.cn/docx/[TOKEN]`

---

## 🛠️ 高级功能

### 日志级别

```bash
export DOCSYNC_LOG_LEVEL=DEBUG  # DEBUG/INFO/WARNING/ERROR
python main.py
```

### 备份还原

```bash
# 交互式还原
python main.py --restore /path/to/note.md

# 还原命令：show <n>, diff <n>, <n> (还原), log, q
```

---

## ❓ 常见问题

| 问题 | 解决方案 |
|------|----------|
| `90003088 Tenant has not purchased` | 应用未发布版本，去控制台创建并发布 |
| `1061004 Forbidden` | 没有目标文件夹权限，换一个自己创建的文件夹 |
| 图片不显示 | 检查 `vault_root` 配置是否正确 |

---

## 📂 项目结构

```
doc-sync/
├── main.py           # 主入口
├── scripts/
│   └── cli.py        # 统一命令行工具
├── src/              # 核心模块
├── tests/            # 单元测试
├── docs/             # 详细文档
└── examples/         # 示例文件
```

---

## � 更多文档

- [使用指南](docs/USAGE_GUIDE.md) - 详细使用说明和最佳实践
- [更新日志](docs/CHANGELOG.md) - 版本更新记录
- [贡献指南](docs/CONTRIBUTING.md) - 如何参与开发

---

## 🤝 贡献

欢迎贡献代码、报告问题或提出建议！

```bash
# 运行测试
pytest tests/ -v
```

---

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE)

---

<div align="center">

**⭐ 如果这个项目对您有帮助，请给一个 Star！**

Made with ❤️ by [zhangjian94cn](https://github.com/zhangjian94cn)

</div>
