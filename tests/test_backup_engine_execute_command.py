"""
Tests for BackupEngine._execute_backup_command() method.

Tests cover:
- PBS backup success (VM/LXC)
- Direct storage backup success
- Local backup success (Docker/Systemd)
- Plugin method exceptions (graceful error handling)
- Dry run mode (all backup methods)
- Duration tracking validation
- Return dict structure validation
- Error messages are actionable
- Logging verification
- Different service types
"""

import time
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, Mock, patch

import pytest

from core.backup_engine import BackupEngine
from core.config_loader import ConfigLoader, ServiceConfig
from lib.state_manager import StateManager


# Fixtures
@pytest.fixture
def fixtures_dir():
    """Return path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def valid_config_path(fixtures_dir):
    """Return path to basic valid config."""
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
def backup_engine_dry_run(valid_config_path, state_manager):
    """Return BackupEngine instance in dry run mode."""
    config = ConfigLoader(valid_config_path)
    return BackupEngine(config, state_manager, dry_run=True)


@pytest.fixture
def vm_service():
    """Return a VM service config."""
    return ServiceConfig(
        name="test-vm",
        type="vm",
        vmid=100,
        node="pve",
        backup=True,
    )


@pytest.fixture
def lxc_service():
    """Return an LXC service config."""
    return ServiceConfig(
        name="test-lxc",
        type="lxc",
        vmid=101,
        node="pve",
        backup=True,
    )


@pytest.fixture
def docker_service():
    """Return a Docker service config."""
    return ServiceConfig(
        name="test-docker",
        type="docker",
        container_name="test-docker-container",
        backup=True,
    )


@pytest.fixture
def systemd_service():
    """Return a Systemd service config."""
    return ServiceConfig(
        name="test-systemd",
        type="systemd",
        service_name="test-systemd.service",
        backup=True,
    )


@pytest.fixture
def pbs_destination():
    """Return PBS backup destination."""
    return {
        "method": "pbs",
        "pbs_config": {
            "server": "192.168.1.100",
            "port": 8007,
            "datastore": "test-datastore",
            "username": "root@pam",
            "password": "test",
            "verify_ssl": False,
        },
    }


@pytest.fixture
def direct_destination(tmp_path):
    """Return direct storage backup destination."""
    return {
        "method": "direct",
        "path": tmp_path / "direct-storage",
    }


@pytest.fixture
def local_destination(tmp_path):
    """Return local backup destination."""
    return {
        "method": "local",
        "path": tmp_path / "backups",
    }


@pytest.fixture
def mock_metadata():
    """Return mock backup metadata."""
    return {
        "service_name": "test-service",
        "service_type": "vm",
        "backup_method": "pbs",
        "timestamp": "2025-01-24T12:00:00",
        "status": "pending",
    }


class TestExecuteBackupCommandPBS:
    """Test PBS backup execution."""

    def test_pbs_backup_success_vm(
        self, backup_engine, vm_service, pbs_destination, mock_metadata
    ):
        """Test successful PBS backup for VM service."""
        # Create mock plugin
        mock_plugin = Mock()
        mock_plugin.backup_to_pbs.return_value = True

        # Mock _get_plugin_for_service to return our mock plugin
        with patch.object(
            backup_engine, "_get_plugin_for_service", return_value=mock_plugin
        ):
            result = backup_engine._execute_backup_command(
                vm_service, pbs_destination, mock_metadata
            )

        # Verify result structure
        assert isinstance(result, dict)
        assert "success" in result
        assert "backup_path" in result
        assert "duration_seconds" in result
        assert "error_message" in result

        # Verify success
        assert result["success"] is True
        assert result["backup_path"] is None  # PBS stores internally
        assert result["error_message"] is None

        # Verify duration tracking
        assert isinstance(result["duration_seconds"], float)
        assert result["duration_seconds"] >= 0
        assert result["duration_seconds"] < 5  # Should be fast for mock

        # Verify plugin was called correctly
        mock_plugin.backup_to_pbs.assert_called_once_with(
            vm_service, pbs_destination["pbs_config"]
        )

    def test_pbs_backup_success_lxc(
        self, backup_engine, lxc_service, pbs_destination, mock_metadata
    ):
        """Test successful PBS backup for LXC service."""
        mock_plugin = Mock()
        mock_plugin.backup_to_pbs.return_value = True

        with patch.object(
            backup_engine, "_get_plugin_for_service", return_value=mock_plugin
        ):
            result = backup_engine._execute_backup_command(
                lxc_service, pbs_destination, mock_metadata
            )

        assert result["success"] is True
        assert result["backup_path"] is None
        mock_plugin.backup_to_pbs.assert_called_once()

    def test_pbs_backup_failure(
        self, backup_engine, vm_service, pbs_destination, mock_metadata
    ):
        """Test PBS backup failure (plugin returns False)."""
        mock_plugin = Mock()
        mock_plugin.backup_to_pbs.return_value = False

        with patch.object(
            backup_engine, "_get_plugin_for_service", return_value=mock_plugin
        ):
            result = backup_engine._execute_backup_command(
                vm_service, pbs_destination, mock_metadata
            )

        # Verify failure is handled gracefully
        assert result["success"] is False
        assert result["backup_path"] is None
        assert result["error_message"] is not None
        assert "PBS backup failed" in result["error_message"]

        # Duration should still be tracked
        assert result["duration_seconds"] >= 0

    def test_pbs_backup_plugin_exception(
        self, backup_engine, vm_service, pbs_destination, mock_metadata
    ):
        """Test PBS backup handles plugin exceptions gracefully."""
        mock_plugin = Mock()
        mock_plugin.backup_to_pbs.side_effect = RuntimeError(
            "PBS connection timeout"
        )

        with patch.object(
            backup_engine, "_get_plugin_for_service", return_value=mock_plugin
        ):
            result = backup_engine._execute_backup_command(
                vm_service, pbs_destination, mock_metadata
            )

        # Should not raise, but return failure
        assert result["success"] is False
        assert result["error_message"] is not None
        assert "PBS connection timeout" in result["error_message"]
        assert result["backup_path"] is None


class TestExecuteBackupCommandDirect:
    """Test direct storage backup execution."""

    def test_direct_backup_success(
        self,
        backup_engine,
        vm_service,
        direct_destination,
        mock_metadata,
        tmp_path,
    ):
        """Test successful direct storage backup."""
        # Create expected backup path
        expected_path = tmp_path / "backups" / "test-vm_backup.tar.gz"

        mock_plugin = Mock()
        mock_plugin.backup_to_storage.return_value = expected_path

        with patch.object(
            backup_engine, "_get_plugin_for_service", return_value=mock_plugin
        ):
            result = backup_engine._execute_backup_command(
                vm_service, direct_destination, mock_metadata
            )

        # Verify success
        assert result["success"] is True
        assert result["backup_path"] == expected_path
        assert result["error_message"] is None

        # Verify plugin was called with correct arguments
        mock_plugin.backup_to_storage.assert_called_once_with(
            vm_service, direct_destination["path"]
        )

    def test_direct_backup_plugin_exception(
        self, backup_engine, lxc_service, direct_destination, mock_metadata
    ):
        """Test direct storage backup handles exceptions."""
        mock_plugin = Mock()
        mock_plugin.backup_to_storage.side_effect = OSError(
            "Disk full"
        )

        with patch.object(
            backup_engine, "_get_plugin_for_service", return_value=mock_plugin
        ):
            result = backup_engine._execute_backup_command(
                lxc_service, direct_destination, mock_metadata
            )

        # Should handle gracefully
        assert result["success"] is False
        assert "Disk full" in result["error_message"]


class TestExecuteBackupCommandLocal:
    """Test local backup execution."""

    def test_local_backup_success_docker(
        self,
        backup_engine,
        docker_service,
        local_destination,
        mock_metadata,
        tmp_path,
    ):
        """Test successful local backup for Docker service."""
        mock_plugin = Mock()
        mock_plugin.backup.return_value = None  # Local backup doesn't return path

        with patch.object(
            backup_engine, "_get_plugin_for_service", return_value=mock_plugin
        ):
            result = backup_engine._execute_backup_command(
                docker_service, local_destination, mock_metadata
            )

        # Verify success
        assert result["success"] is True
        assert result["error_message"] is None

        # Verify backup_path is set correctly
        assert result["backup_path"] is not None
        assert isinstance(result["backup_path"], Path)
        assert "test-docker" in str(result["backup_path"])
        assert result["backup_path"].suffix == ".gz"

        # Verify plugin was called
        assert mock_plugin.backup.called
        call_args = mock_plugin.backup.call_args
        assert call_args[0][0] == docker_service
        assert isinstance(call_args[0][1], Path)

    def test_local_backup_success_systemd(
        self,
        backup_engine,
        systemd_service,
        local_destination,
        mock_metadata,
    ):
        """Test successful local backup for Systemd service."""
        mock_plugin = Mock()
        mock_plugin.backup.return_value = None

        with patch.object(
            backup_engine, "_get_plugin_for_service", return_value=mock_plugin
        ):
            result = backup_engine._execute_backup_command(
                systemd_service, local_destination, mock_metadata
            )

        assert result["success"] is True
        assert "test-systemd" in str(result["backup_path"])

    def test_local_backup_creates_directory(
        self,
        backup_engine,
        docker_service,
        local_destination,
        mock_metadata,
        tmp_path,
    ):
        """Test that local backup creates service directory."""
        expected_dir = tmp_path / "backups" / "test-docker"
        assert not expected_dir.exists()

        mock_plugin = Mock()
        mock_plugin.backup.return_value = None

        with patch.object(
            backup_engine, "_get_plugin_for_service", return_value=mock_plugin
        ):
            backup_engine._execute_backup_command(
                docker_service, local_destination, mock_metadata
            )

        # Directory should be created
        assert expected_dir.exists()
        assert expected_dir.is_dir()

    def test_local_backup_plugin_exception(
        self,
        backup_engine,
        docker_service,
        local_destination,
        mock_metadata,
    ):
        """Test local backup handles plugin exceptions."""
        mock_plugin = Mock()
        mock_plugin.backup.side_effect = PermissionError(
            "Permission denied"
        )

        with patch.object(
            backup_engine, "_get_plugin_for_service", return_value=mock_plugin
        ):
            result = backup_engine._execute_backup_command(
                docker_service, local_destination, mock_metadata
            )

        assert result["success"] is False
        assert "Permission denied" in result["error_message"]


class TestExecuteBackupCommandDryRun:
    """Test dry run mode for all backup methods."""

    def test_dry_run_pbs_backup(
        self,
        backup_engine_dry_run,
        vm_service,
        pbs_destination,
        mock_metadata,
    ):
        """Test dry run mode for PBS backup."""
        # Should NOT call plugin
        mock_plugin = Mock()

        with patch.object(
            backup_engine_dry_run,
            "_get_plugin_for_service",
            return_value=mock_plugin,
        ):
            result = backup_engine_dry_run._execute_backup_command(
                vm_service, pbs_destination, mock_metadata
            )

        # Should succeed without actually running
        assert result["success"] is True
        assert result["backup_path"] is None  # PBS doesn't have path
        assert result["error_message"] is None

        # Plugin should NOT be called in dry run
        mock_plugin.backup_to_pbs.assert_not_called()

        # Duration should be minimal
        assert result["duration_seconds"] < 1

    def test_dry_run_direct_backup(
        self,
        backup_engine_dry_run,
        lxc_service,
        direct_destination,
        mock_metadata,
    ):
        """Test dry run mode for direct storage backup."""
        mock_plugin = Mock()

        with patch.object(
            backup_engine_dry_run,
            "_get_plugin_for_service",
            return_value=mock_plugin,
        ):
            result = backup_engine_dry_run._execute_backup_command(
                lxc_service, direct_destination, mock_metadata
            )

        assert result["success"] is True
        assert result["backup_path"] is not None  # Should generate mock path
        assert isinstance(result["backup_path"], Path)

        # Plugin should NOT be called
        mock_plugin.backup_to_storage.assert_not_called()

    def test_dry_run_local_backup(
        self,
        backup_engine_dry_run,
        docker_service,
        local_destination,
        mock_metadata,
    ):
        """Test dry run mode for local backup."""
        mock_plugin = Mock()

        with patch.object(
            backup_engine_dry_run,
            "_get_plugin_for_service",
            return_value=mock_plugin,
        ):
            result = backup_engine_dry_run._execute_backup_command(
                docker_service, local_destination, mock_metadata
            )

        assert result["success"] is True
        assert result["backup_path"] is not None
        assert "test-docker" in str(result["backup_path"])

        # Plugin should NOT be called
        mock_plugin.backup.assert_not_called()

    def test_dry_run_no_directory_creation(
        self,
        backup_engine_dry_run,
        docker_service,
        local_destination,
        mock_metadata,
        tmp_path,
    ):
        """Test that dry run doesn't create directories."""
        service_dir = tmp_path / "backups" / "test-docker"

        mock_plugin = Mock()

        with patch.object(
            backup_engine_dry_run,
            "_get_plugin_for_service",
            return_value=mock_plugin,
        ):
            backup_engine_dry_run._execute_backup_command(
                docker_service, local_destination, mock_metadata
            )

        # Directory should NOT be created in dry run
        assert not service_dir.exists()


class TestExecuteBackupCommandValidation:
    """Test return dict structure and validation."""

    def test_return_dict_has_required_keys(
        self,
        backup_engine,
        vm_service,
        pbs_destination,
        mock_metadata,
    ):
        """Test that return dict has all required keys."""
        mock_plugin = Mock()
        mock_plugin.backup_to_pbs.return_value = True

        with patch.object(
            backup_engine, "_get_plugin_for_service", return_value=mock_plugin
        ):
            result = backup_engine._execute_backup_command(
                vm_service, pbs_destination, mock_metadata
            )

        # Check all required keys exist
        required_keys = {
            "success",
            "backup_path",
            "duration_seconds",
            "error_message",
        }
        assert set(result.keys()) == required_keys

    def test_success_is_boolean(
        self,
        backup_engine,
        docker_service,
        local_destination,
        mock_metadata,
    ):
        """Test that success field is boolean."""
        mock_plugin = Mock()
        mock_plugin.backup.return_value = None

        with patch.object(
            backup_engine, "_get_plugin_for_service", return_value=mock_plugin
        ):
            result = backup_engine._execute_backup_command(
                docker_service, local_destination, mock_metadata
            )

        assert isinstance(result["success"], bool)

    def test_duration_is_float(
        self,
        backup_engine,
        vm_service,
        pbs_destination,
        mock_metadata,
    ):
        """Test that duration_seconds is float."""
        mock_plugin = Mock()
        mock_plugin.backup_to_pbs.return_value = True

        with patch.object(
            backup_engine, "_get_plugin_for_service", return_value=mock_plugin
        ):
            result = backup_engine._execute_backup_command(
                vm_service, pbs_destination, mock_metadata
            )

        assert isinstance(result["duration_seconds"], float)
        assert result["duration_seconds"] >= 0

    def test_backup_path_is_path_or_none(
        self,
        backup_engine,
        docker_service,
        local_destination,
        mock_metadata,
    ):
        """Test that backup_path is Path or None."""
        mock_plugin = Mock()
        mock_plugin.backup.return_value = None

        with patch.object(
            backup_engine, "_get_plugin_for_service", return_value=mock_plugin
        ):
            result = backup_engine._execute_backup_command(
                docker_service, local_destination, mock_metadata
            )

        assert result["backup_path"] is None or isinstance(
            result["backup_path"], Path
        )

    def test_error_message_is_string_or_none(
        self,
        backup_engine,
        vm_service,
        pbs_destination,
        mock_metadata,
    ):
        """Test that error_message is string or None."""
        mock_plugin = Mock()
        mock_plugin.backup_to_pbs.return_value = True

        with patch.object(
            backup_engine, "_get_plugin_for_service", return_value=mock_plugin
        ):
            result = backup_engine._execute_backup_command(
                vm_service, pbs_destination, mock_metadata
            )

        assert result["error_message"] is None or isinstance(
            result["error_message"], str
        )


class TestExecuteBackupCommandDurationTracking:
    """Test duration tracking for RTO metrics."""

    def test_duration_tracked_on_success(
        self,
        backup_engine,
        vm_service,
        pbs_destination,
        mock_metadata,
    ):
        """Test that duration is tracked on successful backup."""
        mock_plugin = Mock()
        mock_plugin.backup_to_pbs.return_value = True

        # Add small delay to plugin call
        def slow_backup(*args):
            time.sleep(0.05)
            return True

        mock_plugin.backup_to_pbs.side_effect = slow_backup

        with patch.object(
            backup_engine, "_get_plugin_for_service", return_value=mock_plugin
        ):
            result = backup_engine._execute_backup_command(
                vm_service, pbs_destination, mock_metadata
            )

        # Duration should reflect actual time
        assert result["duration_seconds"] >= 0.05
        assert result["duration_seconds"] < 5  # Reasonable upper bound

    def test_duration_tracked_on_failure(
        self,
        backup_engine,
        vm_service,
        pbs_destination,
        mock_metadata,
    ):
        """Test that duration is tracked even on failure."""
        mock_plugin = Mock()

        def slow_failure(*args):
            time.sleep(0.05)
            raise RuntimeError("Backup failed")

        mock_plugin.backup_to_pbs.side_effect = slow_failure

        with patch.object(
            backup_engine, "_get_plugin_for_service", return_value=mock_plugin
        ):
            result = backup_engine._execute_backup_command(
                vm_service, pbs_destination, mock_metadata
            )

        # Duration should be tracked even on error
        assert result["success"] is False
        assert result["duration_seconds"] >= 0.05

    def test_duration_precision(
        self,
        backup_engine,
        docker_service,
        local_destination,
        mock_metadata,
    ):
        """Test that duration has 2 decimal places precision."""
        mock_plugin = Mock()
        mock_plugin.backup.return_value = None

        with patch.object(
            backup_engine, "_get_plugin_for_service", return_value=mock_plugin
        ):
            result = backup_engine._execute_backup_command(
                docker_service, local_destination, mock_metadata
            )

        # Should be rounded to 2 decimal places
        duration_str = str(result["duration_seconds"])
        if "." in duration_str:
            decimal_places = len(duration_str.split(".")[1])
            assert decimal_places <= 2


class TestExecuteBackupCommandLogging:
    """Test logging output verification.

    Note: These tests verify that operations complete successfully.
    Logging output can be verified manually in the pytest output
    (see "Captured stderr call" sections).
    """

    def test_successful_backup_completes_with_logging(
        self,
        backup_engine,
        vm_service,
        pbs_destination,
        mock_metadata,
    ):
        """Test that successful backup completes and logs appropriately."""
        mock_plugin = Mock()
        mock_plugin.backup_to_pbs.return_value = True

        with patch.object(
            backup_engine, "_get_plugin_for_service", return_value=mock_plugin
        ):
            result = backup_engine._execute_backup_command(
                vm_service, pbs_destination, mock_metadata
            )

        # Verify operation completed successfully (logs are visible in test output)
        assert result["success"] is True

    def test_failed_backup_completes_with_error_logging(
        self,
        backup_engine,
        vm_service,
        pbs_destination,
        mock_metadata,
    ):
        """Test that failed backup completes and logs errors appropriately."""
        mock_plugin = Mock()
        mock_plugin.backup_to_pbs.side_effect = RuntimeError("Test error")

        with patch.object(
            backup_engine, "_get_plugin_for_service", return_value=mock_plugin
        ):
            result = backup_engine._execute_backup_command(
                vm_service, pbs_destination, mock_metadata
            )

        # Verify error is handled gracefully (error logs visible in test output)
        assert result["success"] is False
        assert "Test error" in result["error_message"]

    def test_dry_run_completes_with_dry_run_logging(
        self,
        backup_engine_dry_run,
        vm_service,
        pbs_destination,
        mock_metadata,
    ):
        """Test that dry run completes and logs with DRY RUN prefix."""
        result = backup_engine_dry_run._execute_backup_command(
            vm_service, pbs_destination, mock_metadata
        )

        # Verify dry run succeeds (DRY RUN logs visible in test output)
        assert result["success"] is True

    def test_local_backup_completes_with_logging(
        self,
        backup_engine,
        docker_service,
        local_destination,
        mock_metadata,
    ):
        """Test that local backup completes and logs appropriately."""
        mock_plugin = Mock()
        mock_plugin.backup.return_value = None

        with patch.object(
            backup_engine, "_get_plugin_for_service", return_value=mock_plugin
        ):
            result = backup_engine._execute_backup_command(
                docker_service, local_destination, mock_metadata
            )

        # Verify operation completed (completion logs visible in test output)
        assert result["success"] is True


class TestExecuteBackupCommandErrorMessages:
    """Test error messages are actionable."""

    def test_error_message_contains_service_name(
        self,
        backup_engine,
        vm_service,
        pbs_destination,
        mock_metadata,
    ):
        """Test error messages include service name."""
        mock_plugin = Mock()
        mock_plugin.backup_to_pbs.side_effect = RuntimeError("Test error")

        with patch.object(
            backup_engine, "_get_plugin_for_service", return_value=mock_plugin
        ):
            result = backup_engine._execute_backup_command(
                vm_service, pbs_destination, mock_metadata
            )

        assert vm_service.name in result["error_message"]

    def test_error_message_contains_method(
        self,
        backup_engine,
        docker_service,
        local_destination,
        mock_metadata,
    ):
        """Test error messages include backup method."""
        mock_plugin = Mock()
        mock_plugin.backup.side_effect = OSError("Disk error")

        with patch.object(
            backup_engine, "_get_plugin_for_service", return_value=mock_plugin
        ):
            result = backup_engine._execute_backup_command(
                docker_service, local_destination, mock_metadata
            )

        assert "local" in result["error_message"].lower()

    def test_error_message_contains_exception_details(
        self,
        backup_engine,
        lxc_service,
        direct_destination,
        mock_metadata,
    ):
        """Test error messages include exception details."""
        mock_plugin = Mock()
        error_msg = "Connection refused on port 8007"
        mock_plugin.backup_to_storage.side_effect = ConnectionError(error_msg)

        with patch.object(
            backup_engine, "_get_plugin_for_service", return_value=mock_plugin
        ):
            result = backup_engine._execute_backup_command(
                lxc_service, direct_destination, mock_metadata
            )

        assert error_msg in result["error_message"]

    def test_pbs_failure_has_actionable_message(
        self,
        backup_engine,
        vm_service,
        pbs_destination,
        mock_metadata,
    ):
        """Test PBS failure provides actionable guidance."""
        mock_plugin = Mock()
        mock_plugin.backup_to_pbs.return_value = False

        with patch.object(
            backup_engine, "_get_plugin_for_service", return_value=mock_plugin
        ):
            result = backup_engine._execute_backup_command(
                vm_service, pbs_destination, mock_metadata
            )

        # Should suggest checking PBS logs
        error = result["error_message"]
        assert "PBS" in error
        assert "logs" in error or "Check" in error


class TestExecuteBackupCommandDifferentServiceTypes:
    """Test with different service types."""

    def test_vm_service_backup(
        self,
        backup_engine,
        vm_service,
        pbs_destination,
        mock_metadata,
    ):
        """Test backup with VM service type."""
        mock_plugin = Mock()
        mock_plugin.backup_to_pbs.return_value = True

        with patch.object(
            backup_engine, "_get_plugin_for_service", return_value=mock_plugin
        ):
            result = backup_engine._execute_backup_command(
                vm_service, pbs_destination, mock_metadata
            )

        assert result["success"] is True
        assert vm_service.type == "vm"

    def test_lxc_service_backup(
        self,
        backup_engine,
        lxc_service,
        pbs_destination,
        mock_metadata,
    ):
        """Test backup with LXC service type."""
        mock_plugin = Mock()
        mock_plugin.backup_to_pbs.return_value = True

        with patch.object(
            backup_engine, "_get_plugin_for_service", return_value=mock_plugin
        ):
            result = backup_engine._execute_backup_command(
                lxc_service, pbs_destination, mock_metadata
            )

        assert result["success"] is True
        assert lxc_service.type == "lxc"

    def test_docker_service_backup(
        self,
        backup_engine,
        docker_service,
        local_destination,
        mock_metadata,
    ):
        """Test backup with Docker service type."""
        mock_plugin = Mock()
        mock_plugin.backup.return_value = None

        with patch.object(
            backup_engine, "_get_plugin_for_service", return_value=mock_plugin
        ):
            result = backup_engine._execute_backup_command(
                docker_service, local_destination, mock_metadata
            )

        assert result["success"] is True
        assert docker_service.type == "docker"

    def test_systemd_service_backup(
        self,
        backup_engine,
        systemd_service,
        local_destination,
        mock_metadata,
    ):
        """Test backup with Systemd service type."""
        mock_plugin = Mock()
        mock_plugin.backup.return_value = None

        with patch.object(
            backup_engine, "_get_plugin_for_service", return_value=mock_plugin
        ):
            result = backup_engine._execute_backup_command(
                systemd_service, local_destination, mock_metadata
            )

        assert result["success"] is True
        assert systemd_service.type == "systemd"


class TestExecuteBackupCommandEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_unknown_backup_method(
        self,
        backup_engine,
        vm_service,
        mock_metadata,
    ):
        """Test handling of unknown backup method."""
        invalid_destination = {
            "method": "unknown_method",
        }

        mock_plugin = Mock()

        with patch.object(
            backup_engine, "_get_plugin_for_service", return_value=mock_plugin
        ):
            result = backup_engine._execute_backup_command(
                vm_service, invalid_destination, mock_metadata
            )

        # Should fail gracefully
        assert result["success"] is False
        assert "unknown" in result["error_message"].lower()

    def test_plugin_get_raises_exception(
        self,
        backup_engine,
        vm_service,
        pbs_destination,
        mock_metadata,
    ):
        """Test handling when _get_plugin_for_service raises."""
        with patch.object(
            backup_engine,
            "_get_plugin_for_service",
            side_effect=ValueError("No plugin found"),
        ):
            result = backup_engine._execute_backup_command(
                vm_service, pbs_destination, mock_metadata
            )

        # Should handle gracefully
        assert result["success"] is False
        assert "No plugin found" in result["error_message"]

    def test_metadata_not_used_but_accepted(
        self,
        backup_engine,
        docker_service,
        local_destination,
        mock_metadata,
    ):
        """Test that metadata parameter is accepted (for future use)."""
        mock_plugin = Mock()
        mock_plugin.backup.return_value = None

        # Should accept metadata even if not currently used
        with patch.object(
            backup_engine, "_get_plugin_for_service", return_value=mock_plugin
        ):
            result = backup_engine._execute_backup_command(
                docker_service, local_destination, mock_metadata
            )

        assert result["success"] is True
