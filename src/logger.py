import sys
import logging
from datetime import datetime

# ANSI Color Codes
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

class Logger:
    def __init__(self, name="DocSync"):
        self.name = name

    def _log(self, level_color, level_icon, message, end="\n"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"{Colors.CYAN}[{timestamp}]{Colors.ENDC} {level_color}{level_icon} {message}{Colors.ENDC}", end=end)

    def info(self, message, icon="ℹ️ "):
        self._log(Colors.BLUE, icon, message)

    def success(self, message, icon="✅"):
        self._log(Colors.GREEN, icon, message)

    def warning(self, message, icon="⚠️ "):
        self._log(Colors.WARNING, icon, message)

    def error(self, message, icon="❌"):
        self._log(Colors.FAIL, icon, message)

    def debug(self, message, icon="🔧"):
        # Optional: Hide debug logs if needed, or print in gray
        # For now, print in default color but marked as debug
        self._log(Colors.HEADER, icon, message)

    def header(self, message, icon=""):
        print(f"\n{Colors.BOLD}{Colors.HEADER}{'='*40}")
        if icon:
            print(f" {icon} {message}")
        else:
            print(f" {message}")
        print(f"{'='*40}{Colors.ENDC}")

    def rule(self, message=""):
        if message:
            print(f"{Colors.CYAN}{'-'*10} {message} {'-'*10}{Colors.ENDC}")
        else:
            print(f"{Colors.CYAN}{'-'*40}{Colors.ENDC}")

logger = Logger()
