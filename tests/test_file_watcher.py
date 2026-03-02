"""Tests for the FileWatcher used in bidirectional live sync."""
import os
import time
import tempfile
import threading

import pytest

from doc_sync.live.file_watcher import FileWatcher


class TestFileWatcherDebounce:
    """Test debounced change detection."""

    def test_single_change_triggers_callback(self, tmp_path):
        """A single file write should trigger exactly one callback."""
        md_file = tmp_path / "test.md"
        md_file.write_text("# Hello")

        triggered = threading.Event()
        call_count = {"n": 0}
        received_paths = []

        def on_change(path):
            call_count["n"] += 1
            received_paths.append(path)
            triggered.set()

        watcher = FileWatcher(str(md_file), on_change, debounce=0.3)
        watcher.start()

        try:
            time.sleep(0.2)  # Let observer warm up
            md_file.write_text("# Hello World")
            assert triggered.wait(timeout=3.0), "Callback was not triggered"
            time.sleep(0.5)  # Wait for any extra spurious fires
            assert call_count["n"] == 1
            # Verify the path was passed
            assert len(received_paths) == 1
            assert received_paths[0].endswith("test.md")
        finally:
            watcher.stop()

    def test_rapid_changes_debounced(self, tmp_path):
        """Multiple rapid writes should be debounced into a single callback."""
        md_file = tmp_path / "test.md"
        md_file.write_text("initial")

        triggered = threading.Event()
        call_count = {"n": 0}

        def on_change(path):
            call_count["n"] += 1
            triggered.set()

        watcher = FileWatcher(str(md_file), on_change, debounce=0.5)
        watcher.start()

        try:
            time.sleep(0.2)
            # Rapid successive writes
            for i in range(5):
                md_file.write_text(f"change {i}")
                time.sleep(0.05)

            assert triggered.wait(timeout=3.0), "Callback was not triggered"
            time.sleep(0.8)  # Wait for debounce to fully settle
            assert call_count["n"] == 1, f"Expected 1 call, got {call_count['n']}"
        finally:
            watcher.stop()


class TestFileWatcherSuppress:
    """Test suppression context manager."""

    def test_suppress_prevents_callback(self, tmp_path):
        """Writes inside suppress() should not trigger callback."""
        md_file = tmp_path / "test.md"
        md_file.write_text("initial")

        call_count = {"n": 0}

        def on_change(path):
            call_count["n"] += 1

        watcher = FileWatcher(str(md_file), on_change, debounce=0.3)
        watcher.start()

        try:
            time.sleep(0.2)
            with watcher.suppress():
                md_file.write_text("suppressed write")
            
            time.sleep(1.0)  # Wait well past debounce
            assert call_count["n"] == 0, "Callback should not fire during suppression"
        finally:
            watcher.stop()

    def test_callback_works_after_suppress(self, tmp_path):
        """After suppress() exits, normal changes should trigger callback again."""
        md_file = tmp_path / "test.md"
        md_file.write_text("initial")

        triggered = threading.Event()
        call_count = {"n": 0}

        def on_change(path):
            call_count["n"] += 1
            triggered.set()

        watcher = FileWatcher(str(md_file), on_change, debounce=0.3)
        watcher.start()

        try:
            time.sleep(0.2)

            # Suppressed write
            with watcher.suppress():
                md_file.write_text("suppressed")

            time.sleep(0.5)

            # Normal write after suppress
            md_file.write_text("normal write")
            assert triggered.wait(timeout=3.0), "Callback should trigger after suppress ends"
            assert call_count["n"] >= 1
        finally:
            watcher.stop()


class TestFileWatcherLifecycle:
    """Test start/stop lifecycle."""

    def test_no_callback_after_stop(self, tmp_path):
        """After stop(), no callbacks should fire."""
        md_file = tmp_path / "test.md"
        md_file.write_text("initial")

        call_count = {"n": 0}

        def on_change(path):
            call_count["n"] += 1

        watcher = FileWatcher(str(md_file), on_change, debounce=0.3)
        watcher.start()
        time.sleep(0.2)
        watcher.stop()

        md_file.write_text("after stop")
        time.sleep(1.0)
        assert call_count["n"] == 0

    def test_directory_mode_triggers_on_md(self, tmp_path):
        """In directory mode, .md file changes should trigger callback."""
        sub = tmp_path / "notes"
        sub.mkdir()
        md_file = sub / "test.md"
        md_file.write_text("initial md")
        time.sleep(0.3)  # Let FS settle

        triggered = threading.Event()
        received_paths = []

        def on_change(path):
            received_paths.append(path)
            triggered.set()

        watcher = FileWatcher(str(sub), on_change, debounce=0.3)
        watcher.start()

        try:
            time.sleep(0.5)  # Let observer fully warm up

            # Write to .md should trigger
            md_file.write_text("changed md content")
            assert triggered.wait(timeout=3.0), ".md change should trigger callback"
            assert len(received_paths) >= 1, "At least one callback for .md change"
            assert received_paths[0].endswith("test.md")
        finally:
            watcher.stop()
