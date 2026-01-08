# 更新日志 (Changelog)

本文档记录 DocSync 项目的重要更新和优化要点，供开发者参考和学习。

---

## [2026-01-08] 全面代码优化

### 🔧 代码质量优化

#### 1. 异常处理细化
**问题**：裸 `except:` 语句会捕获所有异常，难以定位问题。

**优化方案**：
```python
# ❌ 之前
try:
    data = json.load(f)
except:
    return []

# ✅ 之后
try:
    data = json.load(f)
except json.JSONDecodeError as e:
    logger.error(f"配置文件 JSON 格式错误: {e}")
    return []
except IOError as e:
    logger.error(f"读取配置文件失败: {e}")
    return []
```

**要点**：区分不同异常类型，提供有意义的错误信息。

---

#### 2. 类型注解
**问题**：缺少类型注解降低代码可读性和 IDE 支持。

**优化方案**：
```python
# ❌ 之前
def image_uploader(path):
    ...

# ✅ 之后
from typing import Optional, Callable

def __init__(self, image_uploader: Optional[Callable[[str], Optional[str]]] = None):
    ...
```

**要点**：为函数参数和返回值添加类型注解，特别是回调函数。

---

#### 3. 硬编码提取
**问题**：魔法数字散落在代码中，难以维护。

**优化方案**：将所有配置常量集中到 `config.py`：
```python
# config.py
AUTH_SERVER_PORT: int = 8000
BATCH_CHUNK_SIZE: int = 10
SYNC_DIFF_THRESHOLD: int = 15
MAX_PARALLEL_WORKERS: int = 4
API_MAX_RETRIES: int = 3
```

**要点**：配置集中管理，便于修改和测试。

---

### ⚡ 性能优化

#### 4. 资源索引缓存
**问题**：每次查找资源都递归遍历整个 Vault，大型仓库性能差。

**优化方案**：创建 `ResourceIndex` 类，一次构建索引后 O(1) 查找：
```python
class ResourceIndex:
    def __init__(self, vault_root: str, extensions: Set[str] = None):
        self._index: Dict[str, str] = {}
        self._build_index()
    
    def find(self, filename: str) -> Optional[str]:
        return self._index.get(os.path.basename(filename))
```

**要点**：
- 首次扫描建立 `文件名 -> 完整路径` 映射
- 类级别缓存，同一 Vault 只构建一次
- 支持按扩展名过滤

---

#### 5. API 重试机制
**问题**：网络请求失败或遇到速率限制时直接报错。

**优化方案**：创建 `retry.py` 模块，实现指数退避重试：
```python
@retry_on_failure(max_retries=3, base_delay=1.0)
def api_call():
    ...

# 遇到 429/5xx 时自动重试，延迟 1s -> 2s -> 4s
```

**要点**：
- 检查 `Retry-After` 响应头
- 只重试可恢复的错误（429, 500, 502, 503, 504）
- 超时限制避免无限等待

---

### 🏗️ 架构优化

#### 6. 多线程日志安全
**问题**：并发同步时多个线程同时输出，日志混乱。

**优化方案**：
```python
class Logger:
    def __init__(self):
        self._lock = threading.Lock()
    
    def _log(self, level, message):
        with self._lock:
            print(message, flush=True)
```

**要点**：
- 使用 `threading.Lock()` 确保原子输出
- `flush=True` 立即刷新缓冲区
- 多行输出（如 header）合并为单次 print

---

#### 7. 并发文件夹同步
**问题**：串行处理每个文件，大型仓库同步慢。

**优化方案**：
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

with ThreadPoolExecutor(max_workers=4) as executor:
    futures = {executor.submit(sync_file, f): f for f in files}
    for future in as_completed(futures):
        result = future.result()
```

**要点**：
- 先收集所有任务，再并行执行
- 使用 `as_completed` 处理完成的任务
- 线程锁保护共享状态（如统计计数）

---

### 🔐 安全性优化

#### 8. Token 安全存储
**问题**：access_token 明文存储在 JSON 文件中。

**优化方案**：使用系统钥匙串存储敏感信息：
```python
import keyring

# 存储
keyring.set_password("docsync", "access_token", token)

# 读取
token = keyring.get_password("docsync", "access_token")
```

**要点**：
- macOS 使用 Keychain，Windows 使用 Credential Manager
- JSON 文件作为后备，keyring 失败时降级
- 不在 JSON 中存储任何 token（keyring 可用时）

---

## 编码最佳实践总结

| 场景 | 最佳实践 |
|------|----------|
| 异常处理 | 捕获具体异常类型，提供有意义的错误信息 |
| 类型注解 | 为所有公共 API 添加类型提示 |
| 配置管理 | 集中管理配置，避免硬编码 |
| 资源查找 | 缓存索引避免重复扫描 |
| 网络请求 | 实现重试和超时机制 |
| 多线程 | 使用锁保护共享资源，确保输出原子性 |
| 敏感信息 | 使用系统钥匙串存储，不硬编码密钥 |
