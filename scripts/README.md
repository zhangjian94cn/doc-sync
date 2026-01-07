# 脚本工具目录

此目录包含 DocSync 的各种辅助脚本和工具。

## 工具脚本

### 🎨 setup_wizard.py
**配置向导** - 交互式配置工具

```bash
python3 scripts/setup_wizard.py
```

功能：
- 引导您配置飞书应用
- 创建同步任务
- 自动生成配置文件
- 输入验证和帮助提示

### 🩺 health_check.py
**健康检查** - 环境和配置诊断工具

```bash
python3 scripts/health_check.py
```

检查项目：
- Python 版本
- 依赖包安装
- 配置文件完整性
- 飞书 API 连接
- 任务配置验证

### 🧪 run_example.py
**示例运行脚本** - 快速测试同步功能

```bash
python3 scripts/run_example.py
```

功能：
- 使用示例数据测试同步
- 验证功能是否正常

### 🔧 run_sync_task.sh
**同步任务脚本** - Shell 脚本封装

```bash
./scripts/run_sync_task.sh
```

### 🖥️ start_gui.sh
**GUI 启动脚本** - 启动 Electron 图形界面

```bash
./scripts/start_gui.sh
```

## 使用建议

### 首次使用

1. **运行配置向导**：
   ```bash
   python3 scripts/setup_wizard.py
   ```

2. **健康检查**：
   ```bash
   python3 scripts/health_check.py
   ```

3. **开始同步**：
   ```bash
   python3 main.py
   ```

### 日常使用

```bash
# 正常同步
python3 main.py

# 调试模式
export DOCSYNC_LOG_LEVEL=DEBUG
python3 main.py

# 强制覆盖
python3 main.py --force
```

## 权限说明

某些脚本可能需要执行权限：

```bash
chmod +x scripts/*.sh
```
