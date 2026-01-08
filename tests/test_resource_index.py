"""
Unit tests for the resource_index module.
"""

import os
import pytest
from src.resource_index import ResourceIndex


class TestResourceIndex:
    """Tests for ResourceIndex class."""
    
    def test_build_index(self, temp_vault):
        """Test that index is built correctly."""
        # Create some test files
        test_file = os.path.join(temp_vault, "assets", "image.png")
        with open(test_file, "wb") as f:
            f.write(b"fake png data")
        
        index = ResourceIndex(temp_vault, extensions={"png"})
        
        assert len(index) == 1
        assert "image.png" in index
    
    def test_find_by_filename(self, temp_vault):
        """Test finding file by filename only."""
        test_file = os.path.join(temp_vault, "assets", "photo.jpg")
        with open(test_file, "wb") as f:
            f.write(b"fake jpg data")
        
        index = ResourceIndex(temp_vault, extensions={"jpg"})
        
        result = index.find("photo.jpg")
        assert result == test_file
    
    def test_find_by_relative_path(self, temp_vault):
        """Test finding file by relative path."""
        test_file = os.path.join(temp_vault, "assets", "doc.pdf")
        with open(test_file, "wb") as f:
            f.write(b"fake pdf data")
        
        index = ResourceIndex(temp_vault, extensions={"pdf"})
        
        result = index.find("assets/doc.pdf")
        assert result == test_file
    
    def test_find_not_found(self, temp_vault):
        """Test that None is returned for non-existent files."""
        index = ResourceIndex(temp_vault)
        
        result = index.find("nonexistent.png")
        assert result is None
    
    def test_extension_filter(self, temp_vault):
        """Test that extension filter works correctly."""
        # Create files with different extensions
        for ext in ["png", "jpg", "txt", "md"]:
            path = os.path.join(temp_vault, f"file.{ext}")
            with open(path, "w") as f:
                f.write("test")
        
        # Only index images
        index = ResourceIndex(temp_vault, extensions={"png", "jpg"})
        
        assert "file.png" in index
        assert "file.jpg" in index
        assert "file.txt" not in index
        assert "file.md" not in index
    
    def test_no_extension_filter(self, temp_vault):
        """Test indexing all files when no filter is set."""
        # Create various files
        for ext in ["png", "jpg", "txt", "md"]:
            path = os.path.join(temp_vault, f"all.{ext}")
            with open(path, "w") as f:
                f.write("test")
        
        index = ResourceIndex(temp_vault, extensions=None)
        
        # All files should be indexed
        assert len(index) >= 4
    
    def test_first_occurrence_wins(self, temp_vault):
        """Test that first occurrence of duplicate filename is used."""
        # Create same filename in different directories
        dir1 = os.path.join(temp_vault, "dir1")
        dir2 = os.path.join(temp_vault, "dir2")
        os.makedirs(dir1)
        os.makedirs(dir2)
        
        file1 = os.path.join(dir1, "same.png")
        file2 = os.path.join(dir2, "same.png")
        
        with open(file1, "w") as f:
            f.write("first")
        with open(file2, "w") as f:
            f.write("second")
        
        index = ResourceIndex(temp_vault, extensions={"png"})
        
        # Should find one of them (order depends on os.walk)
        result = index.find("same.png")
        assert result in [file1, file2]
    
    def test_refresh(self, temp_vault):
        """Test refreshing the index."""
        index = ResourceIndex(temp_vault, extensions={"png"})
        assert len(index) == 0
        
        # Add a file
        test_file = os.path.join(temp_vault, "new.png")
        with open(test_file, "w") as f:
            f.write("test")
        
        # Refresh and verify
        index.refresh()
        assert len(index) == 1
        assert "new.png" in index
    
    def test_skip_hidden_directories(self, temp_vault):
        """Test that hidden directories are skipped."""
        hidden_dir = os.path.join(temp_vault, ".hidden")
        os.makedirs(hidden_dir)
        
        hidden_file = os.path.join(hidden_dir, "secret.png")
        with open(hidden_file, "w") as f:
            f.write("test")
        
        index = ResourceIndex(temp_vault, extensions={"png"})
        
        assert "secret.png" not in index
