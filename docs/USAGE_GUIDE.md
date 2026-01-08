# DocSync 使用指南

完整的 Obsidian → 飞书云文档同步最佳实践指南。

---

## 目录

1. [快速开始](#快速开始)
2. [飞书配置详解](#飞书配置详解)
3. [配置文件说明](#配置文件说明)
4. [使用场景与最佳实践](#使用场景与最佳实践)
5. [常见问题排查](#常见问题排查)
6. [高级用法](#高级用法)

---

## 快速开始

### 5 分钟快速体验

```bash
# 1. 克隆项目
git clone https://github.com/zhangjian94cn/doc-sync.git
cd doc-sync

# 2. 安装依赖
pip install -r requirements.txt

# 3. 运行配置向导
python3 scripts/setup_wizard.py

# 4. 开始同步
python3 main.py
```

---

## 飞书配置详解

### 第一步：创建飞书应用

1. 访问 [飞书开放平台](https://open.feishu.cn/app)
2. 点击 **「创建企业自建应用」**
3. 填写应用名称（如 `DocSync`）和描述
4. 记录 **App ID** 和 **App Secret**

### 第二步：配置应用权限

进入 **「权限管理」** → **「API 权限」**，开启以下权限：

| 权限范围 | 权限名称 | 用途 |
|---------|---------|------|
| 云文档 | `docx:document` | 创建、读取、编辑文档 |
| 云空间 | `drive:drive` | 云空间基础权限 |
| 云空间 | `drive:file:create` | 创建文件 |
| 云空间 | `drive:file:read` | 读取文件 |
| 用户信息 | `authen:read` | 用户身份验证 |

### 第三步：配置重定向 URL

进入 **「安全设置」**：

1. 找到 **「重定向 URL」** 配置
2. 添加：`http://127.0.0.1:8000/callback`
3. 保存配置

> ⚠️ **重要**：URL 必须与代码中的 `AUTH_SERVER_PORT` 配置一致（默认 8000）

### 第四步：发布应用版本

> ⚠️ **这是最关键的一步，很多人会忽略！**

1. 进入 **「版本管理与发布」**
2. 点击 **「创建版本」**
3. 填写版本号（如 1.0.0）和更新说明
4. 提交审核（企业自建应用通常自动通过）
5. **确认版本状态为「已发布」**

只有发布后，权限配置才会生效！

### 第五步：获取文件夹/文档 Token

**获取文件夹 Token：**
1. 在飞书中打开目标文件夹
2. 查看 URL：`https://feishu.cn/drive/folder/xxxxxxxxxxxxx`
3. `xxxxxxxxxxxxx` 就是文件夹 Token

**获取文档 Token：**
1. 在飞书中打开目标文档
2. 查看 URL：`https://feishu.cn/docx/xxxxxxxxxxxxx`
3. `xxxxxxxxxxxxx` 就是文档 Token

---

## 配置文件说明

### sync_config.json 完整配置

```json
{
  "feishu_app_id": "cli_xxxxxxxxxx",
  "feishu_app_secret": "xxxxxxxxxxxxxxxxxxxxxxxx",
  "feishu_assets_token": "",
  "tasks": [
    {
      "note": "工作笔记同步",
      "local": "/Users/xxx/Obsidian/Work",
      "cloud": "fldxxxxxxxxxx",
      "vault_root": "/Users/xxx/Obsidian",
      "enabled": true,
      "force": false
    },
    {
      "note": "个人博客",
      "local": "/Users/xxx/Obsidian/Blog/posts",
      "cloud": "fldyyyyyyyyyyy",
      "vault_root": "/Users/xxx/Obsidian",
      "enabled": true
    }
  ]
}
```

### 配置项详解

| 字段 | 必填 | 说明 |
|------|------|------|
| `feishu_app_id` | ✅ | 飞书应用 ID，以 `cli_` 开头 |
| `feishu_app_secret` | ✅ | 飞书应用密钥 |
| `feishu_assets_token` | ❌ | 资源文件存储的文件夹 Token |
| `tasks` | ✅ | 同步任务列表 |

**任务配置项：**

| 字段 | 必填 | 说明 |
|------|------|------|
| `note` | ❌ | 任务备注名称 |
| `local` | ✅ | 本地文件或文件夹路径 |
| `cloud` | ✅ | 飞书文件夹或文档 Token |
| `vault_root` | ❌ | Obsidian 仓库根目录（用于解析图片路径） |
| `enabled` | ❌ | 是否启用，默认 `true` |
| `force` | ❌ | 强制覆盖云端，默认 `false` |

---

## 使用场景与最佳实践

### 场景 1：单文件同步

**需求**：将一篇笔记同步到飞书指定文档

```bash
# 同步到已有文档
python3 main.py /path/to/note.md docx_token_here

# 同步到文件夹（自动创建同名文档）
python3 main.py /path/to/note.md folder_token_here
```

**最佳实践**：
- 首次同步使用 `--force` 确保覆盖空文档
- 后续同步会自动检测变更

---

### 场景 2：文件夹批量同步

**需求**：将整个笔记目录同步到飞书，保持目录结构

**配置**：
```json
{
  "tasks": [
    {
      "note": "技术笔记",
      "local": "/Users/xxx/Obsidian/Tech",
      "cloud": "fldxxxxxxxxxx"
    }
  ]
}
```

```bash
python3 main.py
```

**最佳实践**：
- 本地子目录会自动在云端创建对应文件夹
- `.md` 文件自动转换为飞书文档
- 隐藏文件（`.` 开头）和 `assets` 目录会被跳过

---

### 场景 3：包含图片的笔记同步

**需求**：笔记包含本地图片，需要一并上传

**Obsidian 目录结构**：
```
/Obsidian/
├── .obsidian/
├── assets/
│   ├── image1.png
│   └── diagram.svg
└── notes/
    └── article.md   # 引用 ![[image1.png]]
```

**配置**：
```json
{
  "tasks": [
    {
      "local": "/Users/xxx/Obsidian/notes",
      "cloud": "fldxxxxxxxxxx",
      "vault_root": "/Users/xxx/Obsidian"  // ← 关键配置
    }
  ]
}
```

**最佳实践**：
- 必须配置 `vault_root` 为 Obsidian 仓库根目录
- 支持 `![[image.png]]` 和 `![alt](path/to/image.png)` 两种语法
- 图片会自动上传并替换为飞书内部链接

---

### 场景 4：双向同步（云端优先）

**需求**：团队在飞书编辑，需要同步回本地

**工作流程**：
1. 运行 `python3 main.py`
2. 程序检测云端修改时间 > 本地修改时间
3. 自动切换为「反向同步」模式
4. 云端内容覆盖本地（会创建 `.bak` 备份）

**最佳实践**：
- 反向同步前会自动创建备份 `note.md.bak.20260108_120000`
- 使用 `--restore` 可以交互式还原备份

---

### 场景 5：定时自动同步

**需求**：每小时自动同步一次

**macOS/Linux (crontab)**：
```bash
# 编辑定时任务
crontab -e

# 添加以下行（每小时整点同步）
0 * * * * cd /path/to/doc-sync && /usr/bin/python3 main.py >> /tmp/docsync.log 2>&1
```

**最佳实践**：
- 建议设置日志级别：`export DOCSYNC_LOG_LEVEL=WARNING`
- 重定向输出到日志文件便于排查问题

---

### 场景 6：CI/CD 集成

**需求**：Git push 后自动同步文档到飞书

**GitHub Actions 示例**：
```yaml
name: Sync to Feishu

on:
  push:
    paths:
      - 'docs/**'

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Sync to Feishu
        env:
          FEISHU_APP_ID: ${{ secrets.FEISHU_APP_ID }}
          FEISHU_APP_SECRET: ${{ secrets.FEISHU_APP_SECRET }}
          FEISHU_ACCESS_TOKEN: ${{ secrets.FEISHU_ACCESS_TOKEN }}
        run: python main.py --force
```

---

## 常见问题排查

### Q1: 提示 "90003088 Tenant has not purchased"

**原因**：应用版本未发布。

**解决**：
1. 进入飞书开放平台 → 版本管理
2. 创建并发布新版本
3. 等待 1-2 分钟后重试

---

### Q2: 提示 "1061004 Forbidden"

**原因**：没有目标文件夹的访问权限。

**解决**：
- 确保目标文件夹是你创建的
- 或者在飞书中将文件夹共享给应用机器人
- 或者使用用户身份访问（推荐）

---

### Q3: 图片上传失败

**原因**：`vault_root` 配置错误或图片路径无效。

**排查步骤**：
```bash
# 开启 DEBUG 模式查看详细日志
export DOCSYNC_LOG_LEVEL=DEBUG
python3 main.py
```

检查日志中的 "资源索引构建" 和 "本地资源未找到" 信息。

---

### Q4: Token 过期

**现象**：提示 "99991677 Token Expired"

**解决**：程序会自动尝试刷新 Token。如果刷新失败：
```bash
# 重新登录授权
python3 scripts/setup_wizard.py
```

---

## 高级用法

### 调试模式

```bash
# 同步后打印云端文档结构
python3 main.py --debug-dump

# 查看详细日志
export DOCSYNC_LOG_LEVEL=DEBUG
python3 main.py
```

### 备份还原

```bash
# 交互式还原备份
python3 main.py --restore /path/to/note.md

# 可用命令
>>> 1              # 还原到第1个版本
>>> show 1         # 查看版本详情
>>> diff 1         # 对比差异
>>> log            # 重新显示版本列表
```

### 清理备份

```bash
# 清理所有 .bak.* 文件
python3 main.py --clean
```

### 健康检查

```bash
# 检查环境配置
python3 scripts/health_check.py
```

---

## 推荐工作流

### 个人使用

```
Obsidian 编辑 → 保存 → 手动运行 python3 main.py → 飞书查看
```

### 团队协作

```
Obsidian 编辑 → Git Push → GitHub Actions 自动同步 → 飞书分享
```

### 知识库运营

```
Obsidian 写作 → 定期同步 → 飞书对外分享 → 反向同步更新
```

---

## 支持的 Markdown 语法

| 语法 | 支持状态 | 飞书对应 |
|------|----------|----------|
| 标题 H1-H9 | ✅ | 对应级别标题 |
| 粗体/斜体 | ✅ | 文本样式 |
| 删除线 | ✅ | 删除线样式 |
| 行内代码 | ✅ | 行内代码 |
| 代码块 | ✅ | 代码块 |
| 有序列表 | ✅ | 有序列表 |
| 无序列表 | ✅ | 无序列表 |
| 任务列表 | ✅ | Todo Block |
| 引用块 | ✅ | 引用 Block |
| 图片 | ✅ | 图片 Block |
| 链接 | ✅ | 文本链接 |
| 表格 | ⏳ | 开发中 |

---

## 获取帮助

- **GitHub Issues**: [提交问题](https://github.com/zhangjian94cn/doc-sync/issues)
- **更新日志**: [CHANGELOG.md](./CHANGELOG.md)
