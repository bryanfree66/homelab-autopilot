"""
Tests for BackupEngine._determine_backup_destination() method.

Tests cover:
- VM/LXC with PBS enabled (success)
- VM/LXC with PBS enabled but incomplete config (error)
- VM/LXC with PBS enabled but connectivity fails (error)
- VM/LXC with direct_storage enabled (success)
- VM/LXC with direct_storage enabled but no path (error)
- VM/LXC with neither PBS nor direct_storage (local fallback)
- Docker/systemd services (always local)
- Cluster safety warnings for node-local paths
- Edge cases
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests

from core.backup_engine import BackupEngine, BackupError
from core.config_loader import ConfigLoader, ServiceConfig
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
def state_manager(tmp_path):
    """Return StateManager with temp database."""
    db_path = tmp_path / "test_state.db"
    return StateManager(db_path)


@pytest.fixture
def backup_engine(valid_config_path, state_manager):
    """Return BackupEngine instance."""
    config = ConfigLoader(valid_config_path)
    return BackupEngine(config, state_manager)


@pytest.fixture
def vm_service():
    """Return a VM service configuration."""
    return ServiceConfig(
        name="test-vm",
        type="vm",
        vmid=100,
        node="pve",
        enabled=True,
        backup=True,
    )


@pytest.fixture
def lxc_service():
    """Return an LXC service configuration."""
    return ServiceConfig(
        name="test-lxc",
        type="lxc",
        vmid=101,
        node="pve",
        enabled=True,
        backup=True,
    )


@pytest.fixture
def docker_service():
    """Return a Docker service configuration."""
    return ServiceConfig(
        name="test-docker",
        type="docker",
        container_name="test-container",
        enabled=True,
        backup=True,
    )


@pytest.fixture
def systemd_service():
    """Return a systemd service configuration."""
    return ServiceConfig(
        name="test-systemd",
        type="systemd",
        service_name="nginx.service",
        enabled=True,
        backup=True,
    )


class TestDetermineBackupDestinationPBS:
    """Test PBS backup destination logic."""

    def test_vm_with_pbs_enabled_success(self, backup_engine, vm_service):
        """Test VM with PBS enabled returns PBS method."""
        # Mock _get_backup_config to return PBS config
        mock_config = {
            "enabled": True,
            "root": Path("/mnt/backups"),
            "retention_days": 30,
            "compression": True,
            "proxmox_backup_server": {
                "enabled": True,
                "server": "192.168.1.100",
                "port": 8007,
                "datastore": "test-datastore",
                "username": "root@pam",
                "password": "test_password",
                "password_command": None,
                "verify_ssl": False,
            },
            "direct_storage": None,
        }

        # Mock successful PBS connectivity check
        mock_response = Mock()
        mock_response.raise_for_status = Mock()

        with patch.object(
            backup_engine, "_get_backup_config", return_value=mock_config
        ):
            with patch("requests.get", return_value=mock_response) as mock_get:
                result = backup_engine._determine_backup_destination(vm_service)

                # Verify method is PBS
                assert result["method"] == "pbs"
                assert "pbs_config" in result
                assert result["pbs_config"]["server"] == "192.168.1.100"
                assert result["pbs_config"]["datastore"] == "test-datastore"

                # Verify connectivity check was made
                mock_get.assert_called_once()
                call_args = mock_get.call_args
                assert "192.168.1.100:8007" in call_args[0][0]
                assert call_args[1]["timeout"] == 5
                assert call_args[1]["verify"] is False

    def test_lxc_with_pbs_enabled_success(self, backup_engine, lxc_service):
        """Test LXC with PBS enabled returns PBS method."""
        mock_config = {
            "enabled": True,
            "root": Path("/mnt/backups"),
            "retention_days": 30,
            "compression": True,
            "proxmox_backup_server": {
                "enabled": True,
                "server": "pbs.local",
                "port": 8007,
                "datastore": "backup-store",
                "username": "backup@pam",
                "password": "secret",
                "password_command": None,
                "verify_ssl": True,
            },
            "direct_storage": None,
        }

        mock_response = Mock()
        mock_response.raise_for_status = Mock()

        with patch.object(
            backup_engine, "_get_backup_config", return_value=mock_config
        ):
            with patch("requests.get", return_value=mock_response):
                result = backup_engine._determine_backup_destination(lxc_service)

                assert result["method"] == "pbs"
                assert result["pbs_config"]["server"] == "pbs.local"

    def test_pbs_incomplete_config_missing_server(self, backup_engine, vm_service):
        """Test PBS with missing server raises BackupError."""
        mock_config = {
            "enabled": True,
            "root": Path("/mnt/backups"),
            "retention_days": 30,
            "compression": True,
            "proxmox_backup_server": {
                "enabled": True,
                "server": "",  # Missing
                "port": 8007,
                "datastore": "test-datastore",
                "username": "root@pam",
                "password": "test_password",
                "password_command": None,
                "verify_ssl": False,
            },
            "direct_storage": None,
        }

        with patch.object(
            backup_engine, "_get_backup_config", return_value=mock_config
        ):
            with pytest.raises(BackupError) as exc_info:
                backup_engine._determine_backup_destination(vm_service)

            assert "incomplete" in str(exc_info.value).lower()
            assert "server" in str(exc_info.value)

    def test_pbs_incomplete_config_missing_datastore(self, backup_engine, vm_service):
        """Test PBS with missing datastore raises BackupError."""
        mock_config = {
            "enabled": True,
            "root": Path("/mnt/backups"),
            "retention_days": 30,
            "compression": True,
            "proxmox_backup_server": {
                "enabled": True,
                "server": "192.168.1.100",
                "port": 8007,
                "datastore": None,  # Missing
                "username": "root@pam",
                "password": "test_password",
                "password_command": None,
                "verify_ssl": False,
            },
            "direct_storage": None,
        }

        with patch.object(
            backup_engine, "_get_backup_config", return_value=mock_config
        ):
            with pytest.raises(BackupError) as exc_info:
                backup_engine._determine_backup_destination(vm_service)

            assert "incomplete" in str(exc_info.value).lower()
            assert "datastore" in str(exc_info.value)

    def test_pbs_incomplete_config_missing_username(self, backup_engine, vm_service):
        """Test PBS with missing username raises BackupError."""
        mock_config = {
            "enabled": True,
            "root": Path("/mnt/backups"),
            "retention_days": 30,
            "compression": True,
            "proxmox_backup_server": {
                "enabled": True,
                "server": "192.168.1.100",
                "port": 8007,
                "datastore": "test-datastore",
                "username": "",  # Missing
                "password": "test_password",
                "password_command": None,
                "verify_ssl": False,
            },
            "direct_storage": None,
        }

        with patch.object(
            backup_engine, "_get_backup_config", return_value=mock_config
        ):
            with pytest.raises(BackupError) as exc_info:
                backup_engine._determine_backup_destination(vm_service)

            assert "incomplete" in str(exc_info.value).lower()
            assert "username" in str(exc_info.value)

    def test_pbs_incomplete_config_multiple_missing(self, backup_engine, vm_service):
        """Test PBS with multiple missing fields raises BackupError."""
        mock_config = {
            "enabled": True,
            "root": Path("/mnt/backups"),
            "retention_days": 30,
            "compression": True,
            "proxmox_backup_server": {
                "enabled": True,
                "server": "",  # Missing
                "port": 8007,
                "datastore": "",  # Missing
                "username": "root@pam",
                "password": "test_password",
                "password_command": None,
                "verify_ssl": False,
            },
            "direct_storage": None,
        }

        with patch.object(
            backup_engine, "_get_backup_config", return_value=mock_config
        ):
            with pytest.raises(BackupError) as exc_info:
                backup_engine._determine_backup_destination(vm_service)

            error_msg = str(exc_info.value)
            assert "incomplete" in error_msg.lower()
            assert "server" in error_msg
            assert "datastore" in error_msg

    def test_pbs_connectivity_timeout(self, backup_engine, vm_service):
        """Test PBS connectivity timeout raises BackupError."""
        mock_config = {
            "enabled": True,
            "root": Path("/mnt/backups"),
            "retention_days": 30,
            "compression": True,
            "proxmox_backup_server": {
                "enabled": True,
                "server": "192.168.1.100",
                "port": 8007,
                "datastore": "test-datastore",
                "username": "root@pam",
                "password": "test_password",
                "password_command": None,
                "verify_ssl": False,
            },
            "direct_storage": None,
        }

        with patch.object(
            backup_engine, "_get_backup_config", return_value=mock_config
        ):
            with patch(
                "requests.get", side_effect=requests.exceptions.Timeout("Timeout")
            ):
                with pytest.raises(BackupError) as exc_info:
                    backup_engine._determine_backup_destination(vm_service)

                error_msg = str(exc_info.value)
                assert "timed out" in error_msg.lower()
                assert "192.168.1.100:8007" in error_msg
                assert "5 seconds" in error_msg

    def test_pbs_connectivity_connection_error(self, backup_engine, vm_service):
        """Test PBS connectivity connection error raises BackupError."""
        mock_config = {
            "enabled": True,
            "root": Path("/mnt/backups"),
            "retention_days": 30,
            "compression": True,
            "proxmox_backup_server": {
                "enabled": True,
                "server": "unreachable.server",
                "port": 8007,
                "datastore": "test-datastore",
                "username": "root@pam",
                "password": "test_password",
                "password_command": None,
                "verify_ssl": False,
            },
            "direct_storage": None,
        }

        with patch.object(
            backup_engine, "_get_backup_config", return_value=mock_config
        ):
            with patch(
                "requests.get",
                side_effect=requests.exceptions.ConnectionError("Connection refused"),
            ):
                with pytest.raises(BackupError) as exc_info:
                    backup_engine._determine_backup_destination(vm_service)

                error_msg = str(exc_info.value)
                assert "cannot connect" in error_msg.lower()
                assert "unreachable.server:8007" in error_msg

    def test_pbs_connectivity_generic_request_error(self, backup_engine, vm_service):
        """Test PBS connectivity generic request error raises BackupError."""
        mock_config = {
            "enabled": True,
            "root": Path("/mnt/backups"),
            "retention_days": 30,
            "compression": True,
            "proxmox_backup_server": {
                "enabled": True,
                "server": "192.168.1.100",
                "port": 8007,
                "datastore": "test-datastore",
                "username": "root@pam",
                "password": "test_password",
                "password_command": None,
                "verify_ssl": False,
            },
            "direct_storage": None,
        }

        with patch.object(
            backup_engine, "_get_backup_config", return_value=mock_config
        ):
            with patch(
                "requests.get",
                side_effect=requests.exceptions.RequestException("Generic error"),
            ):
                with pytest.raises(BackupError) as exc_info:
                    backup_engine._determine_backup_destination(vm_service)

                error_msg = str(exc_info.value)
                assert "connectivity check failed" in error_msg.lower()
                assert "192.168.1.100:8007" in error_msg

    def test_pbs_uses_custom_port(self, backup_engine, vm_service):
        """Test PBS connectivity uses custom port from config."""
        mock_config = {
            "enabled": True,
            "root": Path("/mnt/backups"),
            "retention_days": 30,
            "compression": True,
            "proxmox_backup_server": {
                "enabled": True,
                "server": "192.168.1.100",
                "port": 9999,  # Custom port
                "datastore": "test-datastore",
                "username": "root@pam",
                "password": "test_password",
                "password_command": None,
                "verify_ssl": False,
            },
            "direct_storage": None,
        }

        mock_response = Mock()
        mock_response.raise_for_status = Mock()

        with patch.object(
            backup_engine, "_get_backup_config", return_value=mock_config
        ):
            with patch("requests.get", return_value=mock_response) as mock_get:
                backup_engine._determine_backup_destination(vm_service)

                # Verify custom port was used
                call_args = mock_get.call_args
                assert "192.168.1.100:9999" in call_args[0][0]

    def test_pbs_verify_ssl_true(self, backup_engine, vm_service):
        """Test PBS connectivity respects verify_ssl=True."""
        mock_config = {
            "enabled": True,
            "root": Path("/mnt/backups"),
            "retention_days": 30,
            "compression": True,
            "proxmox_backup_server": {
                "enabled": True,
                "server": "192.168.1.100",
                "port": 8007,
                "datastore": "test-datastore",
                "username": "root@pam",
                "password": "test_password",
                "password_command": None,
                "verify_ssl": True,  # SSL verification enabled
            },
            "direct_storage": None,
        }

        mock_response = Mock()
        mock_response.raise_for_status = Mock()

        with patch.object(
            backup_engine, "_get_backup_config", return_value=mock_config
        ):
            with patch("requests.get", return_value=mock_response) as mock_get:
                backup_engine._determine_backup_destination(vm_service)

                # Verify SSL was enabled
                call_args = mock_get.call_args
                assert call_args[1]["verify"] is True


class TestDetermineBackupDestinationDirectStorage:
    """Test direct storage backup destination logic."""

    def test_vm_with_direct_storage_success(self, backup_engine, vm_service):
        """Test VM with direct storage enabled returns direct method."""
        mock_config = {
            "enabled": True,
            "root": Path("/mnt/backups"),
            "retention_days": 30,
            "compression": True,
            "proxmox_backup_server": None,
            "direct_storage": {
                "enabled": True,
                "path": Path("/mnt/nfs/backups"),
                "format": "vma",
            },
        }

        with patch.object(
            backup_engine, "_get_backup_config", return_value=mock_config
        ):
            result = backup_engine._determine_backup_destination(vm_service)

            assert result["method"] == "direct"
            assert result["path"] == Path("/mnt/nfs/backups")

    def test_lxc_with_direct_storage_success(self, backup_engine, lxc_service):
        """Test LXC with direct storage enabled returns direct method."""
        mock_config = {
            "enabled": True,
            "root": Path("/mnt/backups"),
            "retention_days": 30,
            "compression": True,
            "proxmox_backup_server": None,
            "direct_storage": {
                "enabled": True,
                "path": Path("/ceph/backups"),
                "format": "tar",
            },
        }

        with patch.object(
            backup_engine, "_get_backup_config", return_value=mock_config
        ):
            result = backup_engine._determine_backup_destination(lxc_service)

            assert result["method"] == "direct"
            assert result["path"] == Path("/ceph/backups")

    def test_direct_storage_missing_path(self, backup_engine, vm_service):
        """Test direct storage with missing path raises BackupError."""
        mock_config = {
            "enabled": True,
            "root": Path("/mnt/backups"),
            "retention_days": 30,
            "compression": True,
            "proxmox_backup_server": None,
            "direct_storage": {
                "enabled": True,
                "path": None,  # Missing path
                "format": "vma",
            },
        }

        with patch.object(
            backup_engine, "_get_backup_config", return_value=mock_config
        ):
            with pytest.raises(BackupError) as exc_info:
                backup_engine._determine_backup_destination(vm_service)

            error_msg = str(exc_info.value)
            assert "path is not configured" in error_msg.lower()

    def test_direct_storage_node_local_warning_mnt(
        self, backup_engine, vm_service, caplog
    ):
        """Test direct storage with /mnt path does NOT log warning."""
        mock_config = {
            "enabled": True,
            "root": Path("/mnt/backups"),
            "retention_days": 30,
            "compression": True,
            "proxmox_backup_server": None,
            "direct_storage": {
                "enabled": True,
                "path": Path("/mnt/shared/backups"),
                "format": "vma",
            },
        }

        with patch.object(
            backup_engine, "_get_backup_config", return_value=mock_config
        ):
            backup_engine._determine_backup_destination(vm_service)

            # Should NOT have warning about node-local path
            assert "does not appear to be on shared storage" not in caplog.text

    def test_direct_storage_node_local_warning_nfs(
        self, backup_engine, vm_service, caplog
    ):
        """Test direct storage with /nfs path does NOT log warning."""
        mock_config = {
            "enabled": True,
            "root": Path("/mnt/backups"),
            "retention_days": 30,
            "compression": True,
            "proxmox_backup_server": None,
            "direct_storage": {
                "enabled": True,
                "path": Path("/nfs/backups"),
                "format": "vma",
            },
        }

        with patch.object(
            backup_engine, "_get_backup_config", return_value=mock_config
        ):
            backup_engine._determine_backup_destination(vm_service)

            # Should NOT have warning
            assert "does not appear to be on shared storage" not in caplog.text

    def test_direct_storage_node_local_warning_ceph(
        self, backup_engine, vm_service, caplog
    ):
        """Test direct storage with /ceph path does NOT log warning."""
        mock_config = {
            "enabled": True,
            "root": Path("/mnt/backups"),
            "retention_days": 30,
            "compression": True,
            "proxmox_backup_server": None,
            "direct_storage": {
                "enabled": True,
                "path": Path("/ceph/storage/backups"),
                "format": "vma",
            },
        }

        with patch.object(
            backup_engine, "_get_backup_config", return_value=mock_config
        ):
            backup_engine._determine_backup_destination(vm_service)

            # Should NOT have warning
            assert "does not appear to be on shared storage" not in caplog.text

    def test_direct_storage_node_local_warning_local_path(
        self, backup_engine, vm_service
    ):
        """Test direct storage with local path DOES log warning."""
        mock_config = {
            "enabled": True,
            "root": Path("/mnt/backups"),
            "retention_days": 30,
            "compression": True,
            "proxmox_backup_server": None,
            "direct_storage": {
                "enabled": True,
                "path": Path("/var/backups"),  # Node-local path
                "format": "vma",
            },
        }

        with patch.object(
            backup_engine, "_get_backup_config", return_value=mock_config
        ):
            with patch.object(backup_engine.logger, "warning") as mock_warning:
                backup_engine._determine_backup_destination(vm_service)

                # Should have called warning with message about non-shared storage
                mock_warning.assert_called_once()
                warning_msg = mock_warning.call_args[0][0]
                assert "does not appear to be on shared storage" in warning_msg
                assert "/var/backups" in warning_msg
                assert "cluster environment" in warning_msg.lower()

    def test_direct_storage_node_local_warning_home_path(
        self, backup_engine, vm_service
    ):
        """Test direct storage with /home path DOES log warning."""
        mock_config = {
            "enabled": True,
            "root": Path("/mnt/backups"),
            "retention_days": 30,
            "compression": True,
            "proxmox_backup_server": None,
            "direct_storage": {
                "enabled": True,
                "path": Path("/home/backups"),  # Node-local path
                "format": "vma",
            },
        }

        with patch.object(
            backup_engine, "_get_backup_config", return_value=mock_config
        ):
            with patch.object(backup_engine.logger, "warning") as mock_warning:
                backup_engine._determine_backup_destination(vm_service)

                # Should have warning
                mock_warning.assert_called_once()
                warning_msg = mock_warning.call_args[0][0]
                assert "does not appear to be on shared storage" in warning_msg


class TestDetermineBackupDestinationLocalFallback:
    """Test local fallback backup destination logic."""

    def test_vm_no_pbs_no_direct_falls_back_to_local(self, backup_engine, vm_service):
        """Test VM with neither PBS nor direct storage falls back to local."""
        mock_config = {
            "enabled": True,
            "root": Path("/mnt/backups"),
            "retention_days": 30,
            "compression": True,
            "proxmox_backup_server": None,
            "direct_storage": None,
        }

        with patch.object(
            backup_engine, "_get_backup_config", return_value=mock_config
        ):
            result = backup_engine._determine_backup_destination(vm_service)

            assert result["method"] == "local"
            assert result["path"] == Path("/mnt/backups")

    def test_lxc_no_pbs_no_direct_falls_back_to_local(self, backup_engine, lxc_service):
        """Test LXC with neither PBS nor direct storage falls back to local."""
        mock_config = {
            "enabled": True,
            "root": Path("/mnt/backups"),
            "retention_days": 30,
            "compression": True,
            "proxmox_backup_server": None,
            "direct_storage": None,
        }

        with patch.object(
            backup_engine, "_get_backup_config", return_value=mock_config
        ):
            result = backup_engine._determine_backup_destination(lxc_service)

            assert result["method"] == "local"
            assert result["path"] == Path("/mnt/backups")

    def test_vm_pbs_disabled_falls_back(self, backup_engine, vm_service):
        """Test VM with PBS disabled falls back to local."""
        mock_config = {
            "enabled": True,
            "root": Path("/mnt/backups"),
            "retention_days": 30,
            "compression": True,
            "proxmox_backup_server": {
                "enabled": False,  # Disabled
                "server": "192.168.1.100",
                "port": 8007,
                "datastore": "test-datastore",
                "username": "root@pam",
                "password": "test_password",
                "password_command": None,
                "verify_ssl": False,
            },
            "direct_storage": None,
        }

        with patch.object(
            backup_engine, "_get_backup_config", return_value=mock_config
        ):
            result = backup_engine._determine_backup_destination(vm_service)

            assert result["method"] == "local"

    def test_vm_direct_storage_disabled_falls_back(self, backup_engine, vm_service):
        """Test VM with direct storage disabled falls back to local."""
        mock_config = {
            "enabled": True,
            "root": Path("/mnt/backups"),
            "retention_days": 30,
            "compression": True,
            "proxmox_backup_server": None,
            "direct_storage": {
                "enabled": False,  # Disabled
                "path": Path("/mnt/nfs/backups"),
                "format": "vma",
            },
        }

        with patch.object(
            backup_engine, "_get_backup_config", return_value=mock_config
        ):
            result = backup_engine._determine_backup_destination(vm_service)

            assert result["method"] == "local"


class TestDetermineBackupDestinationOtherServiceTypes:
    """Test backup destination for non-VM/LXC service types."""

    def test_docker_always_uses_local(self, backup_engine, docker_service):
        """Test Docker service always uses local backup."""
        mock_config = {
            "enabled": True,
            "root": Path("/mnt/backups"),
            "retention_days": 30,
            "compression": True,
            "proxmox_backup_server": {
                "enabled": True,
                "server": "192.168.1.100",
                "port": 8007,
                "datastore": "test-datastore",
                "username": "root@pam",
                "password": "test_password",
                "password_command": None,
                "verify_ssl": False,
            },
            "direct_storage": {
                "enabled": True,
                "path": Path("/mnt/nfs/backups"),
                "format": "vma",
            },
        }

        with patch.object(
            backup_engine, "_get_backup_config", return_value=mock_config
        ):
            result = backup_engine._determine_backup_destination(docker_service)

            # Should use local even though PBS and direct are available
            assert result["method"] == "local"
            assert result["path"] == Path("/mnt/backups")

    def test_systemd_always_uses_local(self, backup_engine, systemd_service):
        """Test systemd service always uses local backup."""
        mock_config = {
            "enabled": True,
            "root": Path("/mnt/backups"),
            "retention_days": 30,
            "compression": True,
            "proxmox_backup_server": {
                "enabled": True,
                "server": "192.168.1.100",
                "port": 8007,
                "datastore": "test-datastore",
                "username": "root@pam",
                "password": "test_password",
                "password_command": None,
                "verify_ssl": False,
            },
            "direct_storage": None,
        }

        with patch.object(
            backup_engine, "_get_backup_config", return_value=mock_config
        ):
            result = backup_engine._determine_backup_destination(systemd_service)

            # Should use local
            assert result["method"] == "local"
            assert result["path"] == Path("/mnt/backups")

    def test_generic_service_uses_local(self, backup_engine):
        """Test generic service type uses local backup."""
        generic_service = ServiceConfig(
            name="test-generic",
            type="generic",
            enabled=True,
            backup=True,
        )

        mock_config = {
            "enabled": True,
            "root": Path("/mnt/backups"),
            "retention_days": 30,
            "compression": True,
            "proxmox_backup_server": None,
            "direct_storage": None,
        }

        with patch.object(
            backup_engine, "_get_backup_config", return_value=mock_config
        ):
            result = backup_engine._determine_backup_destination(generic_service)

            assert result["method"] == "local"

    def test_host_service_uses_local(self, backup_engine):
        """Test host service type uses local backup."""
        host_service = ServiceConfig(
            name="proxmox-host-config",
            type="host",
            enabled=True,
            backup=True,
        )

        mock_config = {
            "enabled": True,
            "root": Path("/mnt/backups"),
            "retention_days": 30,
            "compression": True,
            "proxmox_backup_server": None,
            "direct_storage": None,
        }

        with patch.object(
            backup_engine, "_get_backup_config", return_value=mock_config
        ):
            result = backup_engine._determine_backup_destination(host_service)

            assert result["method"] == "local"


class TestDetermineBackupDestinationPriority:
    """Test backup destination priority (PBS > direct > local)."""

    def test_vm_pbs_takes_priority_over_direct(self, backup_engine, vm_service):
        """Test VM with both PBS and direct storage prioritizes PBS."""
        mock_config = {
            "enabled": True,
            "root": Path("/mnt/backups"),
            "retention_days": 30,
            "compression": True,
            "proxmox_backup_server": {
                "enabled": True,
                "server": "192.168.1.100",
                "port": 8007,
                "datastore": "test-datastore",
                "username": "root@pam",
                "password": "test_password",
                "password_command": None,
                "verify_ssl": False,
            },
            "direct_storage": {
                "enabled": True,
                "path": Path("/mnt/nfs/backups"),
                "format": "vma",
            },
        }

        mock_response = Mock()
        mock_response.raise_for_status = Mock()

        with patch.object(
            backup_engine, "_get_backup_config", return_value=mock_config
        ):
            with patch("requests.get", return_value=mock_response):
                result = backup_engine._determine_backup_destination(vm_service)

                # Should use PBS, not direct storage
                assert result["method"] == "pbs"

    def test_vm_direct_takes_priority_over_local(self, backup_engine, vm_service):
        """Test VM with direct storage and no PBS prioritizes direct."""
        mock_config = {
            "enabled": True,
            "root": Path("/mnt/backups"),
            "retention_days": 30,
            "compression": True,
            "proxmox_backup_server": None,
            "direct_storage": {
                "enabled": True,
                "path": Path("/mnt/nfs/backups"),
                "format": "vma",
            },
        }

        with patch.object(
            backup_engine, "_get_backup_config", return_value=mock_config
        ):
            result = backup_engine._determine_backup_destination(vm_service)

            # Should use direct, not local
            assert result["method"] == "direct"


class TestDetermineBackupDestinationEdgeCases:
    """Test edge cases and unusual scenarios."""

    def test_service_type_case_insensitive_vm(self, backup_engine):
        """Test service type is case-insensitive (VM)."""
        vm_uppercase = ServiceConfig(
            name="test",
            type="VM",  # Uppercase
            vmid=100,
            node="pve",
            enabled=True,
            backup=True,
        )

        mock_config = {
            "enabled": True,
            "root": Path("/mnt/backups"),
            "retention_days": 30,
            "compression": True,
            "proxmox_backup_server": None,
            "direct_storage": {
                "enabled": True,
                "path": Path("/mnt/nfs/backups"),
                "format": "vma",
            },
        }

        with patch.object(
            backup_engine, "_get_backup_config", return_value=mock_config
        ):
            result = backup_engine._determine_backup_destination(vm_uppercase)

            # Should still detect as VM and use direct storage
            assert result["method"] == "direct"

    def test_service_type_case_insensitive_lxc(self, backup_engine):
        """Test service type is case-insensitive (LXC)."""
        lxc_mixed = ServiceConfig(
            name="test",
            type="LXC",  # Mixed case
            vmid=101,
            node="pve",
            enabled=True,
            backup=True,
        )

        mock_config = {
            "enabled": True,
            "root": Path("/mnt/backups"),
            "retention_days": 30,
            "compression": True,
            "proxmox_backup_server": None,
            "direct_storage": {
                "enabled": True,
                "path": Path("/mnt/nfs/backups"),
                "format": "vma",
            },
        }

        with patch.object(
            backup_engine, "_get_backup_config", return_value=mock_config
        ):
            result = backup_engine._determine_backup_destination(lxc_mixed)

            # Should still detect as LXC and use direct storage
            assert result["method"] == "direct"

    def test_returns_dict_with_correct_keys_pbs(self, backup_engine, vm_service):
        """Test PBS result dict has correct structure."""
        mock_config = {
            "enabled": True,
            "root": Path("/mnt/backups"),
            "retention_days": 30,
            "compression": True,
            "proxmox_backup_server": {
                "enabled": True,
                "server": "192.168.1.100",
                "port": 8007,
                "datastore": "test-datastore",
                "username": "root@pam",
                "password": "test_password",
                "password_command": None,
                "verify_ssl": False,
            },
            "direct_storage": None,
        }

        mock_response = Mock()
        mock_response.raise_for_status = Mock()

        with patch.object(
            backup_engine, "_get_backup_config", return_value=mock_config
        ):
            with patch("requests.get", return_value=mock_response):
                result = backup_engine._determine_backup_destination(vm_service)

                # Check dict structure
                assert isinstance(result, dict)
                assert "method" in result
                assert "pbs_config" in result
                assert "path" not in result  # Should NOT have path for PBS

    def test_returns_dict_with_correct_keys_direct(self, backup_engine, vm_service):
        """Test direct storage result dict has correct structure."""
        mock_config = {
            "enabled": True,
            "root": Path("/mnt/backups"),
            "retention_days": 30,
            "compression": True,
            "proxmox_backup_server": None,
            "direct_storage": {
                "enabled": True,
                "path": Path("/mnt/nfs/backups"),
                "format": "vma",
            },
        }

        with patch.object(
            backup_engine, "_get_backup_config", return_value=mock_config
        ):
            result = backup_engine._determine_backup_destination(vm_service)

            # Check dict structure
            assert isinstance(result, dict)
            assert "method" in result
            assert "path" in result
            assert "pbs_config" not in result  # Should NOT have PBS config

    def test_returns_dict_with_correct_keys_local(self, backup_engine, docker_service):
        """Test local result dict has correct structure."""
        mock_config = {
            "enabled": True,
            "root": Path("/mnt/backups"),
            "retention_days": 30,
            "compression": True,
            "proxmox_backup_server": None,
            "direct_storage": None,
        }

        with patch.object(
            backup_engine, "_get_backup_config", return_value=mock_config
        ):
            result = backup_engine._determine_backup_destination(docker_service)

            # Check dict structure
            assert isinstance(result, dict)
            assert "method" in result
            assert "path" in result
            assert "pbs_config" not in result  # Should NOT have PBS config

    def test_path_is_path_object_direct(self, backup_engine, vm_service):
        """Test that direct storage path is a Path object."""
        mock_config = {
            "enabled": True,
            "root": Path("/mnt/backups"),
            "retention_days": 30,
            "compression": True,
            "proxmox_backup_server": None,
            "direct_storage": {
                "enabled": True,
                "path": Path("/mnt/nfs/backups"),
                "format": "vma",
            },
        }

        with patch.object(
            backup_engine, "_get_backup_config", return_value=mock_config
        ):
            result = backup_engine._determine_backup_destination(vm_service)

            assert isinstance(result["path"], Path)

    def test_path_is_path_object_local(self, backup_engine, docker_service):
        """Test that local backup path is a Path object."""
        mock_config = {
            "enabled": True,
            "root": Path("/mnt/backups"),
            "retention_days": 30,
            "compression": True,
            "proxmox_backup_server": None,
            "direct_storage": None,
        }

        with patch.object(
            backup_engine, "_get_backup_config", return_value=mock_config
        ):
            result = backup_engine._determine_backup_destination(docker_service)

            assert isinstance(result["path"], Path)
