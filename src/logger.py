import sys
import os
import threading
from datetime import datetime
from enum import Enum
from contextlib import contextmanager
from typing import Optional

# Try to import rich for enhanced output
try:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn
    from rich.table import Table
    from rich.panel import Panel
    from rich import print as rprint
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# ANSI Color Codes (fallback when rich not available)
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
    - 彩色输出（使用 rich 库）
    - 进度条显示
    - 表格汇总
    - 日志级别控制
    - 多线程安全
    """

    def __init__(self, name="DocSync", level=LogLevel.INFO):
        self.name = name
        self.level = level
        self._lock = threading.Lock()
        self._progress: Optional[Progress] = None
        self._current_task = None
        
        # Initialize rich console if available
        if RICH_AVAILABLE:
            self.console = Console()
        else:
            self.console = None

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
        
        with self._lock:
            if RICH_AVAILABLE and self.console:
                # Use rich styling
                style_map = {
                    LogLevel.DEBUG: "dim",
                    LogLevel.INFO: "blue",
                    LogLevel.SUCCESS: "green",
                    LogLevel.WARNING: "yellow",
                    LogLevel.ERROR: "red bold"
                }
                style = style_map.get(level, "")
                self.console.print(f"[cyan][{timestamp}][/cyan] [{style}]{level_icon} {message}[/{style}]")
            else:
                # Fallback to ANSI
                log_line = f"{Colors.CYAN}[{timestamp}]{Colors.ENDC} {level_color}{level_icon} {message}{Colors.ENDC}"
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
        """打印标题"""
        if not self._should_log(LogLevel.INFO):
            return

        with self._lock:
            if RICH_AVAILABLE and self.console:
                title = f"{icon} {message}" if icon else message
                self.console.print(Panel(title, style="bold magenta", width=50))
            else:
                lines = []
                lines.append(f"\n{Colors.BOLD}{Colors.HEADER}{'='*40}")
                if icon:
                    lines.append(f" {icon} {message}")
                else:
                    lines.append(f" {message}")
                lines.append(f"{'='*40}{Colors.ENDC}")
                print("\n".join(lines), flush=True)

    def rule(self, message=""):
        """打印分隔线"""
        if not self._should_log(LogLevel.INFO):
            return

        with self._lock:
            if RICH_AVAILABLE and self.console:
                self.console.rule(message)
            else:
                if message:
                    line = f"{Colors.CYAN}{'-'*10} {message} {'-'*10}{Colors.ENDC}"
                else:
                    line = f"{Colors.CYAN}{'-'*40}{Colors.ENDC}"
                print(line, flush=True)

    @contextmanager
    def progress(self, total: int, description: str = "同步中"):
        """进度条上下文管理器
        
        Usage:
            with logger.progress(10, "同步中") as update:
                for item in items:
                    process(item)
                    update(1)  # Advance by 1
        """
        if RICH_AVAILABLE:
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(bar_width=30),
                TaskProgressColumn(),
                TextColumn("•"),
                TimeElapsedColumn(),
                console=self.console
            ) as progress:
                task = progress.add_task(description, total=total)
                
                def update(advance: int = 1):
                    progress.update(task, advance=advance)
                
                yield update
        else:
            # Fallback: simple counter
            current = [0]
            
            def update(advance: int = 1):
                current[0] += advance
                print(f"\r{description}: {current[0]}/{total}", end="", flush=True)
            
            yield update
            print()  # New line at end

    def summary_table(self, title: str, data: dict):
        """打印汇总表格
        
        Args:
            title: 表格标题
            data: 字典，key 为行名，value 为值
        """
        if not self._should_log(LogLevel.INFO):
            return

        with self._lock:
            if RICH_AVAILABLE and self.console:
                table = Table(title=title, show_header=True, header_style="bold cyan")
                table.add_column("状态", style="dim")
                table.add_column("数量", justify="right")
                
                for key, value in data.items():
                    # Add color based on key content
                    if "成功" in key or "✅" in key:
                        table.add_row(key, f"[green]{value}[/green]")
                    elif "失败" in key or "❌" in key:
                        table.add_row(key, f"[red]{value}[/red]")
                    elif "跳过" in key or "⚠️" in key:
                        table.add_row(key, f"[yellow]{value}[/yellow]")
                    else:
                        table.add_row(key, str(value))
                
                self.console.print(table)
            else:
                # Fallback to simple output
                print(f"\n{Colors.BOLD}{title}{Colors.ENDC}")
                print("-" * 30)
                for key, value in data.items():
                    print(f"  {key}: {value}")
                print("-" * 30)

# 全局日志实例
logger = Logger()

