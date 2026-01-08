# DocSync Scripts

统一命令行工具，简洁易用。

## 🚀 快速使用

```bash
# 配置向导
python scripts/cli.py setup

# 健康检查
python scripts/cli.py check

# 执行同步
python scripts/cli.py sync               # 使用配置文件
python scripts/cli.py sync path token    # 指定文件和目标
python scripts/cli.py sync --force       # 强制覆盖

# 备份管理
python scripts/cli.py restore path       # 还原备份
python scripts/cli.py clean              # 清理所有备份
```

## � 命令说明

| 命令 | 说明 |
|------|------|
| `setup` | 交互式配置 App ID、同步任务 |
| `check` | 检查依赖、配置、API 连接 |
| `sync` | 执行同步（可指定路径或使用配置） |
| `restore` | 交互式选择并还原备份版本 |
| `clean` | 删除所有 `.bak.*` 备份文件 |

## ⚡ 快速开始

```bash
# 首次使用
python scripts/cli.py setup   # 1. 配置
python scripts/cli.py check   # 2. 检查
python scripts/cli.py sync    # 3. 同步
```

## 🔧 高级用法

### 调试模式
```bash
python scripts/cli.py sync --debug
# 或
export DOCSYNC_LOG_LEVEL=DEBUG
python main.py
```

### 定时同步
```bash
# crontab -e
0 * * * * cd /path/to/doc-sync && python main.py >> /tmp/docsync.log 2>&1
```
