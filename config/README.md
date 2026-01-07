# 配置目录

此目录包含 DocSync 的配置模板和示例。

## 文件说明

### sync_config.template.json

配置文件模板，包含：
- 详细的字段说明
- 配置示例
- 帮助信息

## 使用方法

### 方式一：使用配置向导（推荐）

```bash
python3 scripts/setup_wizard.py
```

配置向导会自动在根目录创建 `sync_config.json` 文件。

### 方式二：手动复制模板

```bash
# 复制模板到根目录
cp config/sync_config.template.json sync_config.json

# 编辑配置文件
vim sync_config.json  # 或使用其他编辑器
```

## 配置文件位置

**注意**：实际使用的配置文件应该放在项目根目录：

```
doc-sync/
├── sync_config.json  ← 实际配置文件（不会提交到 git）
└── config/
    └── sync_config.template.json  ← 配置模板
```

`sync_config.json` 已被添加到 `.gitignore`，不会提交到版本控制系统。

## 快速开始

1. 运行配置向导：`python3 scripts/setup_wizard.py`
2. 或手动复制模板：`cp config/sync_config.template.json sync_config.json`
3. 编辑配置文件，填入您的飞书应用信息
4. 运行同步：`python3 main.py`
