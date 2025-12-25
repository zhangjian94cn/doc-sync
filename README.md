# FeishuSync

一款简洁美观的桌面客户端，帮助你在 **Obsidian** 与 **飞书/ Lark** 之间实现双向同步。

![FeishuSync](./docs/preview.png)

---

## ✨ 主要功能

- **双向同步**：本地 Markdown ⇄ 飞书云文档
- **任务管理**：可视化添加、编辑、删除同步规则
- **多主题**：深色 / 浅色 / 跟随系统，6 种强调色随心换
- **中英双语**：界面一键切换中文/English
- **安全本地存储**：API 密钥与任务配置全部保存在本地

---

## 🚀 快速开始

### 1. 克隆与安装

```bash
git clone https://github.com/yourname/feishu-sync.git
cd feishu-sync

# Python 依赖
pip install -r requirements.txt

# 前端依赖
cd electron-app
npm install
```

### 2. 运行开发环境

```bash
# 先启动 Electron 界面
npm start

# 如需手动同步，在项目根目录执行
python main.py
```

### 3. 打包发布

```bash
npm run dist   # 一键构建 Python 核心 + Electron 外壳
```

构建完成后，可在 `electron-app/dist/` 找到系统安装包：
- macOS: `FeishuSync-*.dmg`
- Windows: `FeishuSync Setup *.exe`
- Linux: `FeishuSync-*.AppImage`

---

## 🔧 飞书 API 配置

1. 登录[飞书开放平台](https://open.feishu.cn/) → 创建企业自建应用
2. 在「凭证与基础信息」中获取：
   - `App ID`（以 `cli_` 开头）
   - `App Secret`
3. 在「权限管理」中开通：
   - `drive:file:read`
   - `drive:file:write`
   - `docx:document:read`
   - `docx:document:write`
4. 回到 FeishuSync → Settings → 填入凭据 → Save

---

## 📖 使用说明

### 添加同步任务

1. 切换到「Tasks」页
2. 点击「Add Task」→ 填写：
   - 任务名称（任意）
   - Local：选择本地 Obsidian 库文件夹
   - Cloud：飞书云文档文件夹 token（在飞书网页端地址栏获取）
3. 保存后点击「Sync Now」即可开始双向同步

### 外观设置

- **主题**：System / Dark / Light
- **强调色**：6 种配色，含飞书绿、GitHub 蓝等
- **语言**：中文 / English 实时切换

---

## 🛠️ 技术栈

| 模块        | 技术                     |
|-------------|--------------------------|
| 同步核心    | Python 3.10 + Lark SDK   |
| 桌面客户端  | Electron 28 + Vanilla JS |
| 打包        | electron-builder + PyInstaller |

---

## 📄 许可证

MIT © 2024 FeishuSync Team

---

## 🤝 贡献

欢迎提 Issue 与 PR！

---

## ⚠️ 注意

- 首次同步前请**备份**重要笔记，避免冲突覆盖
- 飞书 API 有调用频率限制，大量文件请分批同步
- 本工具为开源个人作品，与飞书官方无关