"""
File Watcher Module

Monitors local Markdown files for changes and triggers sync callbacks.
Features:
- Debounced change detection to avoid rapid-fire syncs during editing
- Suppression context manager to prevent feedback loops during cloud→local writes
- Passes changed file path to callback for folder-level watching
"""

import asyncio
import os
import time
import threading
from contextlib import contextmanager
from typing import Callable, Optional

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent

from doc_sync.logger import logger


class _DebouncedHandler(FileSystemEventHandler):
    """Watchdog handler with debounce logic.
    
    Collects file change events and fires a single callback after
    `debounce` seconds of inactivity, preventing rapid successive triggers
    when editors perform multiple write operations on save.
    """

    def __init__(self, target_path: str, callback: Callable[[str], None],
                 debounce: float = 1.0):
        super().__init__()
        self.target_path = os.path.realpath(os.path.abspath(target_path))
        self.callback = callback
        self.debounce = debounce
        self._timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()
        self._suppressed = False
        self._is_file = os.path.isfile(target_path)
        self._pending_path: Optional[str] = None

    def _matches(self, event) -> bool:
        """Check if event matches the watched target."""
        if event.is_directory:
            return False
        src = os.path.realpath(event.src_path)
        if self._is_file:
            return src == self.target_path
        # Directory mode: only watch .md files
        return src.startswith(self.target_path + os.sep) and src.endswith(".md")

    def on_modified(self, event):
        if self._matches(event):
            self._schedule(os.path.realpath(event.src_path))

    def on_created(self, event):
        if self._matches(event):
            self._schedule(os.path.realpath(event.src_path))

    def _schedule(self, path: str):
        """Schedule (or reschedule) the debounced callback."""
        with self._lock:
            if self._suppressed:
                return
            self._pending_path = path
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self.debounce, self._fire)
            self._timer.daemon = True
            self._timer.start()

    def _fire(self):
        """Execute the callback."""
        with self._lock:
            self._timer = None
            if self._suppressed:
                return
            path = self._pending_path
        try:
            self.callback(path)
        except Exception as e:
            logger.error(f"文件变更回调执行失败: {e}")

    @contextmanager
    def suppress(self):
        """Context manager to suppress change detection (e.g. during cloud→local writeback)."""
        with self._lock:
            self._suppressed = True
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
        try:
            yield
        finally:
            # Small delay before re-enabling to let FS events settle
            time.sleep(0.2)
            with self._lock:
                self._suppressed = False


class FileWatcher:
    """Watch a local file or directory for changes.
    
    Usage:
        watcher = FileWatcher("/path/to/note.md", on_change_callback)
        watcher.start()
        ...
        with watcher.suppress():
            # Write to file without triggering callback
            open("/path/to/note.md", "w").write(content)
        ...
        watcher.stop()
    """

    def __init__(self, path: str, callback: Callable[[str], None],
                 debounce: float = 1.0):
        """
        Args:
            path: Absolute path to a .md file or directory to watch.
            callback: Function called with the changed file path (from a background thread).
            debounce: Seconds to wait after last change before triggering callback.
        """
        self.path = os.path.abspath(path)
        self._handler = _DebouncedHandler(self.path, callback, debounce)
        self._observer = Observer()
        
        # Determine watch target
        if os.path.isfile(self.path):
            watch_dir = os.path.dirname(self.path)
            recursive = False
        else:
            watch_dir = self.path
            recursive = True
        
        self._observer.schedule(self._handler, watch_dir, recursive=recursive)

    def start(self):
        """Start watching for file changes."""
        self._observer.start()
        logger.info(f"文件监听已启动: {self.path}", icon="👁️")

    def stop(self):
        """Stop watching for file changes."""
        # Cancel any pending debounce timer first
        with self._handler._lock:
            if self._handler._timer is not None:
                self._handler._timer.cancel()
                self._handler._timer = None
            self._handler._suppressed = True  # Prevent any further firing
        self._observer.stop()
        self._observer.join(timeout=3.0)
        logger.info(f"文件监听已停止: {self.path}", icon="🛑")

    @contextmanager
    def suppress(self):
        """Context manager to suppress change callbacks (use during cloud→local writes)."""
        with self._handler.suppress():
            yield
