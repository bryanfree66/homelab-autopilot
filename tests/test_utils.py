"""Tests for utility functions."""

from datetime import datetime
from pathlib import Path

import pytest

from lib.utils import (
    ensure_directory,
    format_bytes,
    get_timestamp,
    human_readable_duration,
    is_valid_hostname,
    is_valid_vmid,
    parse_timestamp,
    safe_remove,
    sanitize_filename,
    validate_path,
)

# Path Operations Tests


class TestValidatePath:
    """Tests for validate_path function."""

    def test_valid_string_path(self, tmp_path):
        """Test validation with string path."""
        result = validate_path(str(tmp_path))
        assert isinstance(result, Path)
        assert result == tmp_path

    def test_valid_path_object(self, tmp_path):
        """Test validation with Path object."""
        result = validate_path(tmp_path)
        assert isinstance(result, Path)
        assert result == tmp_path

    def test_empty_path_raises_error(self):
        """Test that empty path raises ValueError."""
        with pytest.raises(ValueError, match="Path cannot be empty"):
            validate_path("")

    def test_must_exist_with_existing_path(self, tmp_path):
        """Test must_exist with existing path."""
        result = validate_path(tmp_path, must_exist=True)
        assert result.exists()

    def test_must_exist_with_nonexistent_path(self, tmp_path):
        """Test must_exist with nonexistent path raises error."""
        nonexistent = tmp_path / "nonexistent"
        with pytest.raises(FileNotFoundError):
            validate_path(nonexistent, must_exist=True)

    def test_must_be_absolute_with_absolute_path(self, tmp_path):
        """Test must_be_absolute with absolute path."""
        result = validate_path(tmp_path, must_be_absolute=True)
        assert result.is_absolute()

    def test_must_be_absolute_with_relative_path(self):
        """Test must_be_absolute with relative path raises error."""
        with pytest.raises(ValueError, match="Path must be absolute"):
            validate_path("relative/path", must_be_absolute=True)


class TestEnsureDirectory:
    """Tests for ensure_directory function."""

    def test_creates_directory(self, tmp_path):
        """Test directory creation."""
        new_dir = tmp_path / "test_dir"
        result = ensure_directory(new_dir)
        assert result.exists()
        assert result.is_dir()

    def test_creates_nested_directories(self, tmp_path):
        """Test nested directory creation."""
        nested = tmp_path / "a" / "b" / "c"
        result = ensure_directory(nested)
        assert result.exists()
        assert result.is_dir()

    def test_existing_directory_no_error(self, tmp_path):
        """Test no error if directory already exists."""
        result = ensure_directory(tmp_path)
        assert result.exists()

    def test_empty_path_raises_error(self):
        """Test empty path raises error."""
        with pytest.raises(ValueError):
            ensure_directory("")


class TestSafeRemove:
    """Tests for safe_remove function."""

    def test_remove_file(self, tmp_path):
        """Test file removal."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        result = safe_remove(test_file)
        assert result is True
        assert not test_file.exists()

    def test_remove_directory(self, tmp_path):
        """Test directory removal."""
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()
        result = safe_remove(test_dir)
        assert result is True
        assert not test_dir.exists()

    def test_remove_nonexistent_with_missing_ok(self, tmp_path):
        """Test removing nonexistent path with missing_ok=True."""
        nonexistent = tmp_path / "nonexistent"
        result = safe_remove(nonexistent, missing_ok=True)
        assert result is False

    def test_remove_nonexistent_without_missing_ok(self, tmp_path):
        """Test removing nonexistent path with missing_ok=False raises error."""
        nonexistent = tmp_path / "nonexistent"
        with pytest.raises(FileNotFoundError):
            safe_remove(nonexistent, missing_ok=False)


# Date/Time Tests


class TestGetTimestamp:
    """Tests for get_timestamp function."""

    def test_returns_string(self):
        """Test returns string."""
        result = get_timestamp()
        assert isinstance(result, str)

    def test_iso_format(self):
        """Test returns valid ISO format."""
        result = get_timestamp()
        # Should be parseable as ISO format
        datetime.fromisoformat(result)

    def test_contains_date_and_time(self):
        """Test timestamp contains date and time."""
        result = get_timestamp()
        assert "T" in result or " " in result


class TestParseTimestamp:
    """Tests for parse_timestamp function."""

    def test_parse_valid_timestamp(self):
        """Test parsing valid ISO timestamp."""
        timestamp = "2024-01-15T10:30:45"
        result = parse_timestamp(timestamp)
        assert isinstance(result, datetime)
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_parse_invalid_timestamp(self):
        """Test parsing invalid timestamp raises error."""
        with pytest.raises(ValueError, match="Invalid timestamp format"):
            parse_timestamp("not-a-timestamp")

    def test_roundtrip_timestamp(self):
        """Test get and parse timestamp roundtrip."""
        original = get_timestamp()
        parsed = parse_timestamp(original)
        assert isinstance(parsed, datetime)


class TestHumanReadableDuration:
    """Tests for human_readable_duration function."""

    def test_seconds_only(self):
        """Test duration under 1 minute."""
        assert human_readable_duration(45) == "45s"

    def test_minutes_and_seconds(self):
        """Test duration with minutes."""
        assert human_readable_duration(125) == "2m 5s"

    def test_hours_minutes_seconds(self):
        """Test duration with hours."""
        assert human_readable_duration(3665) == "1h 1m 5s"

    def test_days_hours_minutes(self):
        """Test duration with days."""
        assert human_readable_duration(90000) == "1d 1h"

    def test_zero_seconds(self):
        """Test zero duration."""
        assert human_readable_duration(0) == "0s"

    def test_negative_duration_raises_error(self):
        """Test negative duration raises error."""
        with pytest.raises(ValueError, match="Duration cannot be negative"):
            human_readable_duration(-10)


# Format Tests


class TestFormatBytes:
    """Tests for format_bytes function."""

    def test_bytes(self):
        """Test formatting bytes."""
        assert format_bytes(512) == "512.00 B"

    def test_kilobytes(self):
        """Test formatting kilobytes."""
        assert format_bytes(1536) == "1.50 KB"

    def test_megabytes(self):
        """Test formatting megabytes."""
        assert format_bytes(1048576) == "1.00 MB"

    def test_gigabytes(self):
        """Test formatting gigabytes."""
        assert format_bytes(1073741824) == "1.00 GB"

    def test_zero_bytes(self):
        """Test zero bytes."""
        assert format_bytes(0) == "0.00 B"

    def test_negative_bytes_raises_error(self):
        """Test negative bytes raises error."""
        with pytest.raises(ValueError, match="Bytes value cannot be negative"):
            format_bytes(-100)

    def test_custom_precision(self):
        """Test custom precision."""
        assert format_bytes(1536, precision=1) == "1.5 KB"


class TestSanitizeFilename:
    """Tests for sanitize_filename function."""

    def test_removes_invalid_characters(self):
        """Test invalid characters are removed."""
        assert sanitize_filename("my:file/name?.txt") == "my_file_name_.txt"

    def test_valid_filename_unchanged(self):
        """Test valid filename unchanged."""
        assert sanitize_filename("valid_filename.txt") == "valid_filename.txt"

    def test_removes_leading_trailing_spaces(self):
        """Test leading/trailing spaces removed."""
        assert sanitize_filename("  filename.txt  ") == "filename.txt"

    def test_empty_filename_raises_error(self):
        """Test empty filename raises error."""
        with pytest.raises(ValueError, match="Filename cannot be empty"):
            sanitize_filename("")

    def test_custom_replacement(self):
        """Test custom replacement character."""
        assert sanitize_filename("my:file.txt", replacement="-") == "my-file.txt"


# Validator Tests


class TestIsValidVmid:
    """Tests for is_valid_vmid function."""

    def test_valid_vmid_minimum(self):
        """Test minimum valid VMID."""
        assert is_valid_vmid(100) is True

    def test_valid_vmid_maximum(self):
        """Test maximum valid VMID."""
        assert is_valid_vmid(999999) is True

    def test_valid_vmid_middle(self):
        """Test middle range VMID."""
        assert is_valid_vmid(500) is True

    def test_invalid_vmid_too_low(self):
        """Test VMID below minimum."""
        assert is_valid_vmid(99) is False

    def test_invalid_vmid_too_high(self):
        """Test VMID above maximum."""
        assert is_valid_vmid(1000000) is False

    def test_invalid_vmid_negative(self):
        """Test negative VMID."""
        assert is_valid_vmid(-1) is False


class TestIsValidHostname:
    """Tests for is_valid_hostname function."""

    def test_valid_simple_hostname(self):
        """Test simple hostname."""
        assert is_valid_hostname("server01") is True

    def test_valid_fqdn(self):
        """Test FQDN."""
        assert is_valid_hostname("server01.example.com") is True

    def test_valid_with_hyphens(self):
        """Test hostname with hyphens."""
        assert is_valid_hostname("my-server") is True

    def test_valid_with_underscores(self):
        """Test hostname with underscores."""
        assert is_valid_hostname("my_server") is True

    def test_invalid_empty_hostname(self):
        """Test empty hostname."""
        assert is_valid_hostname("") is False

    def test_invalid_too_long(self):
        """Test hostname too long."""
        long_hostname = "a" * 254
        assert is_valid_hostname(long_hostname) is False

    def test_invalid_double_dots(self):
        """Test hostname with double dots."""
        assert is_valid_hostname("server..local") is False

    def test_invalid_special_characters(self):
        """Test hostname with special characters."""
        assert is_valid_hostname("server@local") is False
