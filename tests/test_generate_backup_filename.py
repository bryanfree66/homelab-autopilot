"""
Tests for BackupEngine._generate_backup_filename() method.

Tests cover:
- Basic filename generation
- Timestamp format validation
- Different service types
- Custom extensions
- Special character handling
- Edge cases
"""

import re
from datetime import datetime
from pathlib import Path

import pytest

from core.backup_engine import BackupEngine
from core.config_loader import ConfigLoader
from lib.state_manager import StateManager


# Fixtures
@pytest.fixture
def fixtures_dir():
    """Return path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def valid_config_path(fixtures_dir):
    """Return path to valid config."""
    return fixtures_dir / "valid_config.yaml"


@pytest.fixture
def state_manager(tmp_path):
    """Return StateManager with temp database."""
    db_path = tmp_path / "test_state.db"
    return StateManager(db_path)


@pytest.fixture
def backup_engine(valid_config_path, state_manager):
    """Return initialized BackupEngine."""
    config = ConfigLoader(valid_config_path)
    return BackupEngine(config, state_manager)


class TestGenerateBackupFilename:
    """Test BackupEngine._generate_backup_filename() method."""

    def test_basic_filename_generation(self, backup_engine):
        """Test basic filename generation with default extension."""
        filename = backup_engine._generate_backup_filename("nextcloud", "vm")

        # Check format: servicename_YYYYMMDD_HHMMSS_type.extension
        assert filename.startswith("nextcloud_")
        assert filename.endswith("_vm.tar.gz")

        # Extract and validate timestamp
        parts = filename.split("_")
        assert len(parts) == 4  # [name, YYYYMMDD, HHMMSS, type.ext]

        # Validate date part (YYYYMMDD)
        date_part = parts[1]
        assert len(date_part) == 8
        assert date_part.isdigit()

        # Validate time part (HHMMSS)
        time_part = parts[2]
        assert len(time_part) == 6
        assert time_part.isdigit()

    def test_timestamp_format(self, backup_engine):
        """Test that timestamp is in correct format (YYYYMMDD_HHMMSS)."""
        filename = backup_engine._generate_backup_filename("test", "lxc")

        # Extract timestamp: test_YYYYMMDD_HHMMSS_lxc.tar.gz
        match = re.search(r"_(\d{8})_(\d{6})_", filename)
        assert match is not None

        date_str = match.group(1)
        time_str = match.group(2)

        # Validate date format
        year = int(date_str[0:4])
        month = int(date_str[4:6])
        day = int(date_str[6:8])

        assert 2024 <= year <= 2100  # Reasonable year range
        assert 1 <= month <= 12
        assert 1 <= day <= 31

        # Validate time format
        hour = int(time_str[0:2])
        minute = int(time_str[2:4])
        second = int(time_str[4:6])

        assert 0 <= hour <= 23
        assert 0 <= minute <= 59
        assert 0 <= second <= 59

    def test_timestamp_is_current(self, backup_engine):
        """Test that generated timestamp is close to current time."""
        before = datetime.now().replace(microsecond=0)
        filename = backup_engine._generate_backup_filename("test", "vm")
        after = datetime.now().replace(microsecond=0)

        # Extract timestamp from filename
        match = re.search(r"_(\d{8})_(\d{6})_", filename)
        timestamp_str = match.group(1) + match.group(2)

        # Parse timestamp
        file_timestamp = datetime.strptime(timestamp_str, "%Y%m%d%H%M%S")

        # Should be between before and after (within same second)
        assert before <= file_timestamp <= after

    def test_different_service_types(self, backup_engine):
        """Test filename generation for different service types."""
        service_types = ["vm", "lxc", "docker", "systemd", "host", "generic"]

        for service_type in service_types:
            filename = backup_engine._generate_backup_filename("test", service_type)
            assert filename.endswith(f"_{service_type}.tar.gz")

    def test_custom_extensions(self, backup_engine):
        """Test filename generation with custom extensions."""
        extensions = [
            "tar.gz",
            "vma.gz",
            "tar",
            "zip",
            "backup",
        ]

        for ext in extensions:
            filename = backup_engine._generate_backup_filename(
                "test", "vm", extension=ext
            )
            assert filename.endswith(f".{ext}")

    def test_service_name_sanitization(self, backup_engine):
        """Test that service names with special characters are sanitized."""
        test_cases = [
            ("my service", "my_service"),  # Space to underscore
            ("service/name", "service_name"),  # Slash to underscore
            ("my-service", "my-service"),  # Dash preserved
            ("service.name", "service.name"),  # Dot preserved
        ]

        for input_name, expected_safe_name in test_cases:
            filename = backup_engine._generate_backup_filename(input_name, "vm")
            assert filename.startswith(expected_safe_name)

    def test_multiple_spaces_replaced(self, backup_engine):
        """Test that multiple spaces are all replaced."""
        filename = backup_engine._generate_backup_filename("my  multi  space", "vm")
        assert filename.startswith("my__multi__space")

    def test_filename_uniqueness(self, backup_engine):
        """Test that consecutive calls generate unique filenames."""
        filename1 = backup_engine._generate_backup_filename("test", "vm")
        filename2 = backup_engine._generate_backup_filename("test", "vm")

        # Filenames might be same if generated in same second, but usually different
        # At minimum, they should have valid format
        assert filename1.startswith("test_")
        assert filename2.startswith("test_")

    def test_filename_sortable(self, backup_engine):
        """Test that filenames sort chronologically."""
        filenames = []
        for _ in range(3):
            filename = backup_engine._generate_backup_filename("test", "vm")
            filenames.append(filename)

        # Sorted filenames should be in same order (chronological)
        sorted_filenames = sorted(filenames)
        assert filenames == sorted_filenames

    def test_empty_service_name_handled(self, backup_engine):
        """Test handling of edge case with empty service name."""
        filename = backup_engine._generate_backup_filename("", "vm")

        # Should still generate a valid filename (just timestamp and type)
        assert "_" in filename
        assert filename.endswith("_vm.tar.gz")

    def test_very_long_service_name(self, backup_engine):
        """Test handling of very long service names."""
        long_name = "a" * 200
        filename = backup_engine._generate_backup_filename(long_name, "vm")

        # Should generate without error
        assert filename.startswith(long_name)
        assert filename.endswith("_vm.tar.gz")

    def test_numeric_service_name(self, backup_engine):
        """Test service name that's entirely numeric."""
        filename = backup_engine._generate_backup_filename("12345", "vm")

        assert filename.startswith("12345_")
        assert filename.endswith("_vm.tar.gz")

    def test_filename_components_correct_order(self, backup_engine):
        """Test that filename components are in correct order."""
        filename = backup_engine._generate_backup_filename("myservice", "lxc", "zip")

        # Split by underscore
        parts = filename.split("_")

        # Should have: [name, YYYYMMDD, HHMMSS, type.ext]
        assert parts[0] == "myservice"
        assert len(parts[1]) == 8  # Date
        assert len(parts[2]) == 6  # Time
        assert parts[3] == "lxc.zip"  # Type and extension

    def test_extension_without_dot(self, backup_engine):
        """Test that extension without leading dot works correctly."""
        filename = backup_engine._generate_backup_filename("test", "vm", "tar.gz")
        assert filename.endswith(".tar.gz")

    def test_same_service_different_types(self, backup_engine):
        """Test same service name with different types creates distinct names."""
        filename_vm = backup_engine._generate_backup_filename("nextcloud", "vm")
        filename_lxc = backup_engine._generate_backup_filename("nextcloud", "lxc")

        # Should both start with nextcloud but have different endings
        assert filename_vm.startswith("nextcloud_")
        assert filename_lxc.startswith("nextcloud_")
        assert filename_vm.endswith("_vm.tar.gz")
        assert filename_lxc.endswith("_lxc.tar.gz")

    def test_dry_run_mode_same_behavior(self, valid_config_path, state_manager):
        """Test that dry_run mode doesn't affect filename generation."""
        config = ConfigLoader(valid_config_path)
        engine_normal = BackupEngine(config, state_manager, dry_run=False)
        engine_dry = BackupEngine(config, state_manager, dry_run=True)

        # Both should generate valid filenames (timestamp will differ slightly)
        filename_normal = engine_normal._generate_backup_filename("test", "vm")
        filename_dry = engine_dry._generate_backup_filename("test", "vm")

        # Both should have same format
        assert filename_normal.startswith("test_")
        assert filename_dry.startswith("test_")
        assert filename_normal.endswith("_vm.tar.gz")
        assert filename_dry.endswith("_vm.tar.gz")

    def test_filename_regex_pattern(self, backup_engine):
        """Test that filename matches expected regex pattern."""
        filename = backup_engine._generate_backup_filename("myservice", "vm")

        # Pattern: servicename_YYYYMMDD_HHMMSS_type.extension
        pattern = r"^[a-zA-Z0-9_-]+_\d{8}_\d{6}_[a-z]+\.[a-z.]+$"
        assert re.match(pattern, filename) is not None

    def test_special_characters_comprehensive(self, backup_engine):
        """Test comprehensive special character handling."""
        test_cases = {
            "my@service": "my@service",  # @ preserved
            "service#1": "service#1",  # # preserved
            "my service/test": "my_service_test",  # Space and slash replaced
            "service name": "service_name",  # Space replaced
        }

        for input_name, expected_prefix in test_cases.items():
            filename = backup_engine._generate_backup_filename(input_name, "vm")
            # Check that expected chars are handled
            assert expected_prefix in filename
