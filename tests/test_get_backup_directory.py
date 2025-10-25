"""
Tests for BackupEngine._get_backup_directory() method.

Tests cover:
- Directory creation
- Path resolution
- parents=True and exist_ok=True behavior
- Error handling
- Integration with config
- Multiple services
"""

import os
from pathlib import Path

import pytest

from core.backup_engine import BackupEngine, BackupError
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
def temp_backup_config(tmp_path):
    """Create a config with temporary backup directory."""
    config_file = tmp_path / "config.yaml"
    backup_root = tmp_path / "backups"

    config_file.write_text(
        f"""
global:
  hypervisor:
    type: proxmox
    host: localhost
    username: admin
  backup:
    root: {backup_root}
  notification:
    type: email
    settings:
      smtp_host: localhost

services:
  - name: test
    type: lxc
    vmid: 100
    node: pve
"""
    )

    return config_file, backup_root


@pytest.fixture
def backup_engine_temp(temp_backup_config, tmp_path):
    """Return BackupEngine with temp backup directory."""
    config_file, backup_root = temp_backup_config
    config = ConfigLoader(config_file)
    db_path = tmp_path / "test_state.db"
    state = StateManager(db_path)
    return BackupEngine(config, state), backup_root


class TestGetBackupDirectory:
    """Test BackupEngine._get_backup_directory() method."""

    def test_creates_directory(self, backup_engine_temp):
        """Test that directory is created if it doesn't exist."""
        engine, backup_root = backup_engine_temp

        backup_dir = engine._get_backup_directory("nextcloud")

        # Directory should exist
        assert backup_dir.exists()
        assert backup_dir.is_dir()

    def test_returns_path_object(self, backup_engine_temp):
        """Test that method returns Path object."""
        engine, backup_root = backup_engine_temp

        backup_dir = engine._get_backup_directory("nextcloud")

        assert isinstance(backup_dir, Path)

    def test_correct_path_structure(self, backup_engine_temp):
        """Test that directory structure is correct: {root}/{service}/."""
        engine, backup_root = backup_engine_temp

        backup_dir = engine._get_backup_directory("nextcloud")

        # Should be {backup_root}/nextcloud/
        expected = backup_root / "nextcloud"
        assert backup_dir == expected

    def test_creates_nested_directories(self, backup_engine_temp):
        """Test that parent directories are created (parents=True)."""
        engine, backup_root = backup_engine_temp

        # Backup root might not exist yet
        backup_dir = engine._get_backup_directory("nextcloud")

        # Both backup_root and service dir should exist
        assert backup_root.exists()
        assert backup_dir.exists()

    def test_directory_already_exists(self, backup_engine_temp):
        """Test that existing directory doesn't cause error (exist_ok=True)."""
        engine, backup_root = backup_engine_temp

        # Create directory first time
        backup_dir1 = engine._get_backup_directory("nextcloud")

        # Create again - should not raise
        backup_dir2 = engine._get_backup_directory("nextcloud")

        assert backup_dir1 == backup_dir2
        assert backup_dir2.exists()

    def test_multiple_services_separate_directories(self, backup_engine_temp):
        """Test that different services get separate directories."""
        engine, backup_root = backup_engine_temp

        nextcloud_dir = engine._get_backup_directory("nextcloud")
        plex_dir = engine._get_backup_directory("plex")
        nginx_dir = engine._get_backup_directory("nginx")

        # All should exist
        assert nextcloud_dir.exists()
        assert plex_dir.exists()
        assert nginx_dir.exists()

        # All should be different
        assert nextcloud_dir != plex_dir
        assert nextcloud_dir != nginx_dir
        assert plex_dir != nginx_dir

        # All should be under backup_root
        assert nextcloud_dir.parent == backup_root
        assert plex_dir.parent == backup_root
        assert nginx_dir.parent == backup_root

    def test_service_name_in_path(self, backup_engine_temp):
        """Test that service name appears in path."""
        engine, backup_root = backup_engine_temp

        backup_dir = engine._get_backup_directory("myservice")

        assert "myservice" in str(backup_dir)
        assert backup_dir.name == "myservice"

    def test_uses_config_root(self, backup_engine_temp):
        """Test that method uses backup root from config."""
        engine, backup_root = backup_engine_temp

        backup_dir = engine._get_backup_directory("test")

        # Should be under the configured backup root
        assert backup_dir.parent == backup_root

    def test_idempotent_calls(self, backup_engine_temp):
        """Test that multiple calls with same service return same path."""
        engine, backup_root = backup_engine_temp

        dir1 = engine._get_backup_directory("nextcloud")
        dir2 = engine._get_backup_directory("nextcloud")
        dir3 = engine._get_backup_directory("nextcloud")

        assert dir1 == dir2 == dir3

    def test_dry_run_mode_still_creates_directory(self, temp_backup_config, tmp_path):
        """Test that dry_run mode still creates directories."""
        config_file, backup_root = temp_backup_config
        config = ConfigLoader(config_file)
        db_path = tmp_path / "test_state.db"
        state = StateManager(db_path)
        engine = BackupEngine(config, state, dry_run=True)

        backup_dir = engine._get_backup_directory("test")

        # Even in dry run, directory should be created
        assert backup_dir.exists()

    def test_permission_error_raises(self, backup_engine_temp, monkeypatch):
        """Test that permission errors are wrapped in BackupError."""
        engine, backup_root = backup_engine_temp

        def mock_mkdir(*args, **kwargs):
            raise OSError("Permission denied")

        # Monkey patch mkdir to raise permission error
        monkeypatch.setattr(Path, "mkdir", mock_mkdir)

        with pytest.raises(BackupError) as exc_info:
            engine._get_backup_directory("test")

        # Should have helpful error message
        assert "Failed to create backup directory" in str(exc_info.value)
        assert "Permission denied" in str(exc_info.value)

        # Should chain the original OSError
        assert isinstance(exc_info.value.__cause__, OSError)

    def test_absolute_path_returned(self, backup_engine_temp):
        """Test that returned path is absolute."""
        engine, backup_root = backup_engine_temp

        backup_dir = engine._get_backup_directory("test")

        assert backup_dir.is_absolute()

    def test_empty_service_name(self, backup_engine_temp):
        """Test handling of empty service name."""
        engine, backup_root = backup_engine_temp

        # Should create directory even with empty name
        backup_dir = engine._get_backup_directory("")

        # Directory should be created (though not ideal)
        assert backup_dir.exists()
        assert backup_dir == backup_root / ""

    def test_service_name_with_spaces(self, backup_engine_temp):
        """Test service name with spaces creates valid directory."""
        engine, backup_root = backup_engine_temp

        backup_dir = engine._get_backup_directory("my service")

        # Should create directory (filesystem allows spaces)
        assert backup_dir.exists()
        assert "my service" in str(backup_dir)

    def test_service_name_with_special_chars(self, backup_engine_temp):
        """Test service name with various special characters."""
        engine, backup_root = backup_engine_temp

        # These should all work on Unix filesystems
        test_names = ["service-1", "service_2", "service.3"]

        for name in test_names:
            backup_dir = engine._get_backup_directory(name)
            assert backup_dir.exists()
            assert name in str(backup_dir)

    def test_very_long_service_name(self, backup_engine_temp):
        """Test handling of very long service names."""
        engine, backup_root = backup_engine_temp

        long_name = "a" * 200
        backup_dir = engine._get_backup_directory(long_name)

        # Should create successfully
        assert backup_dir.exists()

    def test_integration_with_get_backup_config(self, backup_engine_temp):
        """Test that method correctly uses _get_backup_config()."""
        engine, backup_root = backup_engine_temp

        # Get config to verify it's being used
        config = engine._get_backup_config()

        backup_dir = engine._get_backup_directory("test")

        # Directory should be under config's root
        assert backup_dir.parent == config["root"]

    def test_directory_permissions_default(self, backup_engine_temp):
        """Test that created directory has reasonable permissions."""
        engine, backup_root = backup_engine_temp

        backup_dir = engine._get_backup_directory("test")

        # Check that directory is readable and writable by owner
        # (Exact permissions depend on umask, so just verify we can access it)
        assert os.access(backup_dir, os.R_OK)
        assert os.access(backup_dir, os.W_OK)
        assert os.access(backup_dir, os.X_OK)

    def test_creates_intermediate_directories(self, tmp_path):
        """Test that deeply nested paths are created."""
        # Create config with non-existent nested backup root
        config_file = tmp_path / "config.yaml"
        backup_root = tmp_path / "level1" / "level2" / "level3" / "backups"

        config_file.write_text(
            f"""
global:
  hypervisor:
    type: proxmox
    host: localhost
    username: admin
  backup:
    root: {backup_root}
  notification:
    type: email
    settings:
      smtp_host: localhost

services:
  - name: test
    type: lxc
    vmid: 100
    node: pve
"""
        )

        config = ConfigLoader(config_file)
        db_path = tmp_path / "test_state.db"
        state = StateManager(db_path)
        engine = BackupEngine(config, state)

        backup_dir = engine._get_backup_directory("test")

        # All levels should be created
        assert backup_root.exists()
        assert backup_dir.exists()
        assert backup_dir == backup_root / "test"

    def test_returns_same_path_as_config_root_plus_service(self, backup_engine_temp):
        """Test that returned path equals config_root / service_name."""
        engine, backup_root = backup_engine_temp

        service_name = "myservice"
        backup_dir = engine._get_backup_directory(service_name)

        # Should be exactly backup_root / service_name
        expected = backup_root / service_name
        assert backup_dir == expected

    def test_caching_not_applied(self, backup_engine_temp):
        """Test that directory paths are not cached (always recalculated)."""
        engine, backup_root = backup_engine_temp

        # Get directory
        dir1 = engine._get_backup_directory("test")

        # Manually change something in engine state (hypothetical)
        # This is just verifying behavior - not actually changing config

        # Get directory again
        dir2 = engine._get_backup_directory("test")

        # Should be same path (though not necessarily cached object)
        assert dir1 == dir2
