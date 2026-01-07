# 贡献指南

感谢您对 DocSync 项目的兴趣！我们欢迎各种形式的贡献。

## 如何贡献

### 报告问题

如果您发现 bug 或有功能建议，请：

1. 在提交之前搜索 [现有 Issues](https://github.com/zhangjian94cn/doc-sync/issues)，避免重复
2. 使用清晰的标题和描述
3. 包含重现步骤（对于 bug）
4. 附上您的环境信息（Python 版本、操作系统等）

### 提交代码

1. **Fork 仓库**
   ```bash
   # 克隆您fork的仓库
   git clone https://github.com/YOUR_USERNAME/doc-sync.git
   cd doc-sync
   ```

2. **创建分支**
   ```bash
   git checkout -b feature/your-feature-name
   # 或
   git checkout -b fix/your-bug-fix
   ```

3. **编写代码**
   - 遵循现有代码风格
   - 添加必要的注释
   - 更新相关文档

4. **测试**
   ```bash
   # 运行健康检查
   python3 scripts/health_check.py

   # 测试您的更改
   python3 main.py --force
   ```

5. **提交更改**
   ```bash
   git add .
   git commit -m "feat: 添加某某功能"
   # 或
   git commit -m "fix: 修复某某问题"
   ```

6. **推送并创建 PR**
   ```bash
   git push origin feature/your-feature-name
   ```

   然后在 GitHub 上创建 Pull Request

## 代码规范

### 提交信息格式

使用语义化提交信息：

- `feat: 新功能`
- `fix: Bug 修复`
- `docs: 文档更新`
- `style: 代码格式调整`
- `refactor: 代码重构`
- `test: 测试相关`
- `chore: 构建/工具相关`

### Python 代码风格

- 遵循 PEP 8
- 使用有意义的变量名
- 添加 docstring 注释
- 保持函数简洁（单一职责）

示例：
```python
def sync_document(local_path: str, cloud_token: str) -> bool:
    """
    同步单个文档到飞书

    Args:
        local_path: 本地文件路径
        cloud_token: 云端文档或文件夹 Token

    Returns:
        bool: 同步是否成功
    """
    # 实现代码
    pass
```

## 开发环境设置

```bash
# 安装开发依赖
pip install -r requirements.txt

# 设置 DEBUG 日志
export DOCSYNC_LOG_LEVEL=DEBUG

# 运行测试
python3 scripts/health_check.py
```

## 需要帮助的领域

我们特别欢迎以下方面的贡献：

- 📝 改进文档和示例
- 🐛 修复 bug
- ✨ 添加新功能
- 🌍 国际化支持
- 🧪 添加测试用例
- 🎨 改进用户界面/体验

## 问题讨论

在开始重大更改之前，建议先开一个 Issue 讨论您的想法。

## 行为准则

- 保持友好和专业
- 尊重不同的观点
- 接受建设性批评
- 专注于对社区最有利的事情

感谢您的贡献！ 🎉
