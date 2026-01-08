import sys
import os
import threading
from datetime import datetime
from enum import Enum

# ANSI Color Codes
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    GRAY = '\033[90m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

class LogLevel(Enum):
    """日志级别"""
    DEBUG = 0
    INFO = 1
    SUCCESS = 2
    WARNING = 3
    ERROR = 4

class Logger:
    """
    增强的日志记录器（线程安全）

    支持：
    - 彩色输出
    - 日志级别控制
    - 时间戳
    - 图标显示
    - 多线程安全
    """

    def __init__(self, name="DocSync", level=LogLevel.INFO):
        self.name = name
        self.level = level
        self._lock = threading.Lock()  # 线程锁，确保日志输出原子性

        # 从环境变量读取日志级别
        env_level = os.getenv("DOCSYNC_LOG_LEVEL", "").upper()
        if env_level == "DEBUG":
            self.level = LogLevel.DEBUG
        elif env_level == "ERROR":
            self.level = LogLevel.ERROR
        elif env_level == "WARNING":
            self.level = LogLevel.WARNING

    def set_level(self, level: LogLevel):
        """设置日志级别"""
        self.level = level

    def _should_log(self, level: LogLevel) -> bool:
        """检查是否应该输出此级别的日志"""
        return level.value >= self.level.value

    def _log(self, level: LogLevel, level_color, level_icon, message, end="\n"):
        """内部日志方法（线程安全）"""
        if not self._should_log(level):
            return

        timestamp = datetime.now().strftime("%H:%M:%S")
        log_line = f"{Colors.CYAN}[{timestamp}]{Colors.ENDC} {level_color}{level_icon} {message}{Colors.ENDC}"
        
        # 使用锁确保完整的日志行作为原子操作输出
        with self._lock:
            print(log_line, end=end, flush=True)

    def debug(self, message, icon="🔧"):
        """调试信息 - 仅在 DEBUG 模式显示"""
        self._log(LogLevel.DEBUG, Colors.GRAY, icon, message)

    def info(self, message, icon="ℹ️ "):
        """一般信息"""
        self._log(LogLevel.INFO, Colors.BLUE, icon, message)

    def success(self, message, icon="✅"):
        """成功信息"""
        self._log(LogLevel.SUCCESS, Colors.GREEN, icon, message)

    def warning(self, message, icon="⚠️ "):
        """警告信息"""
        self._log(LogLevel.WARNING, Colors.WARNING, icon, message)

    def error(self, message, icon="❌"):
        """错误信息"""
        self._log(LogLevel.ERROR, Colors.FAIL, icon, message)

    def header(self, message, icon=""):
        """打印标题（线程安全）"""
        if not self._should_log(LogLevel.INFO):
            return

        # 构建完整的标题块，一次性输出
        lines = []
        lines.append(f"\n{Colors.BOLD}{Colors.HEADER}{'='*40}")
        if icon:
            lines.append(f" {icon} {message}")
        else:
            lines.append(f" {message}")
        lines.append(f"{'='*40}{Colors.ENDC}")
        
        with self._lock:
            print("\n".join(lines), flush=True)

    def rule(self, message=""):
        """打印分隔线（线程安全）"""
        if not self._should_log(LogLevel.INFO):
            return

        if message:
            line = f"{Colors.CYAN}{'-'*10} {message} {'-'*10}{Colors.ENDC}"
        else:
            line = f"{Colors.CYAN}{'-'*40}{Colors.ENDC}"
        
        with self._lock:
            print(line, flush=True)

# 全局日志实例
logger = Logger()

