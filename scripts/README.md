# DocSync Scripts

本目录包含 DocSync 的辅助脚本工具。

## 🚀 推荐方式：统一 CLI

```bash
# 配置向导 - 交互式配置 App ID、同步任务
python scripts/cli.py setup

# 健康检查 - 检查依赖、配置、连接
python scripts/cli.py check

# 执行同步
python scripts/cli.py sync
python scripts/cli.py sync --force    # 强制覆盖
python scripts/cli.py sync --task "工作笔记"  # 指定任务

# 运行示例
python scripts/cli.py example
```

## 📁 脚本说明

| 脚本 | 说明 | 推荐用法 |
|------|------|----------|
| `cli.py` | **统一命令行入口** | `python scripts/cli.py <command>` |
| `setup_wizard.py` | 详细配置向导 | 使用 `cli.py setup` 替代 |
| `health_check.py` | 详细健康检查 | 使用 `cli.py check` 替代 |
| `run_example.py` | 运行示例 | 使用 `cli.py example` 替代 |

## ⚡ 快速开始

```bash
# 首次使用
python scripts/cli.py setup   # 1. 配置
python scripts/cli.py check   # 2. 检查
python main.py                # 3. 同步

# 日常使用
python main.py                # 直接同步
```

## 🔧 高级用法

### 定时同步 (crontab)
```bash
# 每小时同步
0 * * * * cd /path/to/doc-sync && python main.py >> /tmp/docsync.log 2>&1
```

### 调试模式
```bash
export DOCSYNC_LOG_LEVEL=DEBUG
python main.py
```
