"""
Tests for BackupEngine._get_backup_config() method.

Tests cover:
- Basic config loading
- Caching behavior
- PBS configuration handling
- Direct storage configuration handling
- Hybrid configuration (both PBS and direct)
- Missing configuration handling
"""

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
    """Return path to basic valid config (no PBS/direct)."""
    return fixtures_dir / "valid_config.yaml"


@pytest.fixture
def valid_config_pbs_path(fixtures_dir):
    """Return path to config with PBS."""
    return fixtures_dir / "valid_config_pbs.yaml"


@pytest.fixture
def valid_config_direct_path(fixtures_dir):
    """Return path to config with direct storage."""
    return fixtures_dir / "valid_config_direct.yaml"


@pytest.fixture
def valid_config_hybrid_path(fixtures_dir):
    """Return path to config with both PBS and direct."""
    return fixtures_dir / "valid_config_hybrid.yaml"


@pytest.fixture
def state_manager(tmp_path):
    """Return StateManager with temp database."""
    db_path = tmp_path / "test_state.db"
    return StateManager(db_path)


class TestGetBackupConfig:
    """Test BackupEngine._get_backup_config() method."""

    def test_basic_config_loading(self, valid_config_path, state_manager):
        """Test loading basic backup config without PBS or direct storage."""
        config = ConfigLoader(valid_config_path)
        engine = BackupEngine(config, state_manager)

        backup_config = engine._get_backup_config()

        # Check basic fields
        assert backup_config is not None
        assert backup_config["enabled"] is True
        assert isinstance(backup_config["root"], Path)
        assert str(backup_config["root"]) == "/mnt/backups"
        assert backup_config["retention_days"] == 30
        assert backup_config["compression"] is True

        # PBS and direct storage should be None
        assert backup_config["proxmox_backup_server"] is None
        assert backup_config["direct_storage"] is None

    def test_config_caching(self, valid_config_path, state_manager):
        """Test that config is cached after first call."""
        config = ConfigLoader(valid_config_path)
        engine = BackupEngine(config, state_manager)

        # First call
        config1 = engine._get_backup_config()

        # Second call should return same object (cached)
        config2 = engine._get_backup_config()

        assert config1 is config2  # Same object reference

    def test_cache_attribute_initialized(self, valid_config_path, state_manager):
        """Test that cache attribute is None initially."""
        config = ConfigLoader(valid_config_path)
        engine = BackupEngine(config, state_manager)

        assert engine._backup_config_cache is None

        # After calling, should be populated
        engine._get_backup_config()
        assert engine._backup_config_cache is not None

    def test_pbs_config_loading(self, valid_config_pbs_path, state_manager):
        """Test loading config with PBS enabled."""
        config = ConfigLoader(valid_config_pbs_path)
        engine = BackupEngine(config, state_manager)

        backup_config = engine._get_backup_config()

        # Check PBS config exists and is correct
        pbs = backup_config["proxmox_backup_server"]
        assert pbs is not None
        assert pbs["enabled"] is True
        assert pbs["server"] == "192.168.1.100"
        assert pbs["port"] == 8007
        assert pbs["datastore"] == "test-datastore"
        assert pbs["username"] == "root@pam"
        assert pbs["password"] == "pbs_password"
        assert pbs["password_command"] is None
        assert pbs["verify_ssl"] is False

    def test_direct_storage_config_loading(
        self, valid_config_direct_path, state_manager
    ):
        """Test loading config with direct storage enabled."""
        config = ConfigLoader(valid_config_direct_path)
        engine = BackupEngine(config, state_manager)

        backup_config = engine._get_backup_config()

        # Check direct storage config exists and is correct
        direct = backup_config["direct_storage"]
        assert direct is not None
        assert direct["enabled"] is True
        assert isinstance(direct["path"], Path)
        assert str(direct["path"]) == "/mnt/nfs/backups"
        assert direct["format"] == "vma"

    def test_hybrid_config_loading(self, valid_config_hybrid_path, state_manager):
        """Test loading config with both PBS and direct storage."""
        config = ConfigLoader(valid_config_hybrid_path)
        engine = BackupEngine(config, state_manager)

        backup_config = engine._get_backup_config()

        # Both should be present
        assert backup_config["proxmox_backup_server"] is not None
        assert backup_config["direct_storage"] is not None

        # Verify PBS
        pbs = backup_config["proxmox_backup_server"]
        assert pbs["enabled"] is True
        assert pbs["server"] == "192.168.1.100"

        # Verify direct storage
        direct = backup_config["direct_storage"]
        assert direct["enabled"] is True
        assert str(direct["path"]) == "/mnt/nfs/backups"

    def test_pbs_with_password_command(self, tmp_path, state_manager):
        """Test PBS config with password_command instead of password."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
global:
  hypervisor:
    type: proxmox
    host: localhost
    username: admin
  backup:
    root: /tmp/backups
    proxmox_backup_server:
      enabled: true
      server: 192.168.1.100
      datastore: test
      username: root@pam
      password_command: "cat /secret"
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
        engine = BackupEngine(config, state_manager)

        backup_config = engine._get_backup_config()

        pbs = backup_config["proxmox_backup_server"]
        assert pbs["password"] is None
        assert pbs["password_command"] == "cat /secret"

    def test_returns_dict_type(self, valid_config_path, state_manager):
        """Test that method returns a dict, not Pydantic model."""
        config = ConfigLoader(valid_config_path)
        engine = BackupEngine(config, state_manager)

        backup_config = engine._get_backup_config()

        assert isinstance(backup_config, dict)

        # Should be subscriptable
        assert backup_config["enabled"] is True
        assert "root" in backup_config
        assert "retention_days" in backup_config

    def test_dry_run_doesnt_affect_config(self, valid_config_path, state_manager):
        """Test that dry_run mode doesn't affect config loading."""
        config = ConfigLoader(valid_config_path)
        engine = BackupEngine(config, state_manager, dry_run=True)

        backup_config = engine._get_backup_config()

        # Should work normally in dry run mode
        assert backup_config is not None
        assert backup_config["enabled"] is True

    def test_config_paths_are_path_objects(self, valid_config_path, state_manager):
        """Test that paths in config are Path objects."""
        config = ConfigLoader(valid_config_path)
        engine = BackupEngine(config, state_manager)

        backup_config = engine._get_backup_config()

        assert isinstance(backup_config["root"], Path)

    def test_direct_storage_paths_are_path_objects(
        self, valid_config_direct_path, state_manager
    ):
        """Test that direct storage paths are Path objects."""
        config = ConfigLoader(valid_config_direct_path)
        engine = BackupEngine(config, state_manager)

        backup_config = engine._get_backup_config()

        direct = backup_config["direct_storage"]
        assert isinstance(direct["path"], Path)

    def test_disabled_pbs_still_returned(self, tmp_path, state_manager):
        """Test that disabled PBS config is still returned (with enabled=false)."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
global:
  hypervisor:
    type: proxmox
    host: localhost
    username: admin
  backup:
    root: /tmp/backups
    proxmox_backup_server:
      enabled: false
      server: 192.168.1.100
      datastore: test
      username: root@pam
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
        engine = BackupEngine(config, state_manager)

        backup_config = engine._get_backup_config()

        pbs = backup_config["proxmox_backup_server"]
        assert pbs is not None
        assert pbs["enabled"] is False  # Explicitly disabled
