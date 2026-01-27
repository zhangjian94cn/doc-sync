"""
Unit tests for the utils module.
"""

import pytest
from doc_sync.utils import pad_center, parse_cloud_time


class TestPadCenter:
    """Tests for pad_center function."""
    
    def test_ascii_text(self):
        """Test centering ASCII text."""
        result = pad_center("test", 10)
        assert len(result) == 10
        assert result == "   test   "
    
    def test_short_width(self):
        """Test when text is longer than width."""
        result = pad_center("long text", 5)
        assert result == "long text"  # Should return unchanged
    
    def test_cjk_text(self):
        """Test centering text with CJK characters."""
        # CJK characters count as 2 display units
        result = pad_center("测试", 10)
        # "测试" = 4 display units, need 6 more (3 left, 3 right)
        assert result == "   测试   "
    
    def test_mixed_text(self):
        """Test centering mixed ASCII and CJK text."""
        result = pad_center("Hi测试", 12)
        # "Hi" = 2, "测试" = 4, total = 6 display units
        # Need 6 more (3 left, 3 right)
        assert result == "   Hi测试   "
    
    def test_exact_width(self):
        """Test when text exactly matches width."""
        result = pad_center("test", 4)
        assert result == "test"


class TestParseCloudTime:
    """Tests for parse_cloud_time function."""
    
    def test_seconds_timestamp(self):
        """Test parsing timestamp in seconds."""
        result = parse_cloud_time("1704672000")  # 2024-01-08 00:00:00 UTC
        assert result == 1704672000.0
    
    def test_milliseconds_timestamp(self):
        """Test parsing timestamp in milliseconds."""
        result = parse_cloud_time("1704672000000")
        assert result == 1704672000.0  # Should convert to seconds
    
    def test_edge_case_large_seconds(self):
        """Test edge case where seconds timestamp is large but still seconds."""
        # This is year 2286, but still seconds
        result = parse_cloud_time("9999999999")
        assert result == 9999999999.0
    
    def test_milliseconds_threshold(self):
        """Test the threshold between seconds and milliseconds."""
        # Just above 10 billion = milliseconds
        result = parse_cloud_time("10000000001")
        assert result == 10000000.001
