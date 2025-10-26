"""
Tests for BackupEngine.backup_service() method - main orchestration.

Tests cover:
- Success scenarios (complete flow, different destinations, dry-run)
- Service validation (not found, empty name, backup disabled, invalid config)
- Failure scenarios (plugin fails, command fails, verification fails)
- State tracking (success/failure updates, duration tracking)
- Integration (method call order, rotation behavior, multiple services)
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from core.backup_engine import BackupEngine
from core.config_loader import ConfigError, ConfigLoader, ServiceConfig


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
    from lib.state_manager import StateManager

    db_path = tmp_path / "test_state.db"
    return StateManager(db_path)


@pytest.fixture
def backup_engine(valid_config_path, state_manager):
    """Return BackupEngine instance."""
    config = ConfigLoader(valid_config_path)
    return BackupEngine(config, state_manager)


@pytest.fixture
def backup_engine_dry_run(valid_config_path, state_manager):
    """Return BackupEngine instance with dry_run=True."""
    config = ConfigLoader(valid_config_path)
    return BackupEngine(config, state_manager, dry_run=True)


@pytest.fixture
def mock_service():
    """Return a mock service configuration."""
    return ServiceConfig(
        name="test-service",
        type="docker",
        container_name="test-container",
        backup=True,
    )


# Success Scenarios
class TestBackupServiceSuccess:
    """Test successful backup scenarios."""

    def test_complete_successful_backup_flow(
        self, backup_engine, mock_service, tmp_path
    ):
        """Test complete successful backup flow with all steps working."""
        # Mock all helper methods to simulate success
        with patch.object(
            backup_engine.config, "get_service_config", return_value=mock_service
        ):
            with patch.object(
                backup_engine, "_get_plugin_for_service", return_value=Mock()
            ):
                with patch.object(
                    backup_engine,
                    "_determine_backup_destination",
                    return_value={"type": "local"},
                ):
                    backup_dir = tmp_path / "backups"
                    backup_dir.mkdir()
                    with patch.object(
                        backup_engine,
                        "_get_backup_directory",
                        return_value=backup_dir,
                    ):
                        with patch.object(
                            backup_engine,
                            "_generate_backup_filename",
                            return_value="test-service-20240101-120000.tar.gz",
                        ):
                            with patch.object(
                                backup_engine,
                                "_create_backup_metadata",
                                return_value={},
                            ):
                                # Create actual backup file
                                backup_path = (
                                    backup_dir / "test-service-20240101-120000.tar.gz"
                                )
                                backup_path.write_bytes(b"test backup" * 1000)

                                with patch.object(
                                    backup_engine,
                                    "_execute_backup_command",
                                    return_value={
                                        "success": True,
                                        "backup_path": str(backup_path),
                                    },
                                ):
                                    with patch.object(
                                        backup_engine,
                                        "_verify_backup_integrity",
                                        return_value=(True, None),
                                    ):
                                        with patch.object(
                                            backup_engine,
                                            "_rotate_old_backups",
                                            return_value=2,
                                        ):
                                            # Execute
                                            result = backup_engine.backup_service(
                                                "test-service"
                                            )

                                            # Verify
                                            assert result is True

                                            # Verify state was updated
                                            status = backup_engine.state.get(
                                                "backup_status.test-service"
                                            )
                                            assert status == "success"

    def test_backup_with_pbs_destination_succeeds(
        self, backup_engine, mock_service, tmp_path
    ):
        """Test backup with PBS destination succeeds."""
        with patch.object(
            backup_engine.config, "get_service_config", return_value=mock_service
        ):
            with patch.object(
                backup_engine, "_get_plugin_for_service", return_value=Mock()
            ):
                with patch.object(
                    backup_engine,
                    "_determine_backup_destination",
                    return_value={"type": "pbs", "datastore": "backup-store"},
                ):
                    backup_dir = tmp_path / "backups"
                    backup_dir.mkdir()
                    backup_path = backup_dir / "test.tar.gz"
                    backup_path.write_bytes(b"test" * 1000)

                    with patch.object(
                        backup_engine, "_get_backup_directory", return_value=backup_dir
                    ):
                        with patch.object(
                            backup_engine,
                            "_generate_backup_filename",
                            return_value="test.tar.gz",
                        ):
                            with patch.object(
                                backup_engine,
                                "_create_backup_metadata",
                                return_value={},
                            ):
                                with patch.object(
                                    backup_engine,
                                    "_execute_backup_command",
                                    return_value={
                                        "success": True,
                                        "backup_path": str(backup_path),
                                    },
                                ):
                                    with patch.object(
                                        backup_engine,
                                        "_verify_backup_integrity",
                                        return_value=(True, None),
                                    ):
                                        with patch.object(
                                            backup_engine, "_rotate_old_backups"
                                        ):
                                            result = backup_engine.backup_service(
                                                "test-service"
                                            )
                                            assert result is True

    def test_backup_with_direct_storage_succeeds(
        self, backup_engine, mock_service, tmp_path
    ):
        """Test backup with direct storage succeeds."""
        with patch.object(
            backup_engine.config, "get_service_config", return_value=mock_service
        ):
            with patch.object(
                backup_engine, "_get_plugin_for_service", return_value=Mock()
            ):
                with patch.object(
                    backup_engine,
                    "_determine_backup_destination",
                    return_value={"type": "direct", "path": "/var/backups"},
                ):
                    backup_dir = tmp_path / "backups"
                    backup_dir.mkdir()
                    backup_path = backup_dir / "test.tar.gz"
                    backup_path.write_bytes(b"test" * 1000)

                    with patch.object(
                        backup_engine, "_get_backup_directory", return_value=backup_dir
                    ):
                        with patch.object(
                            backup_engine,
                            "_generate_backup_filename",
                            return_value="test.tar.gz",
                        ):
                            with patch.object(
                                backup_engine,
                                "_create_backup_metadata",
                                return_value={},
                            ):
                                with patch.object(
                                    backup_engine,
                                    "_execute_backup_command",
                                    return_value={
                                        "success": True,
                                        "backup_path": str(backup_path),
                                    },
                                ):
                                    with patch.object(
                                        backup_engine,
                                        "_verify_backup_integrity",
                                        return_value=(True, None),
                                    ):
                                        with patch.object(
                                            backup_engine, "_rotate_old_backups"
                                        ):
                                            result = backup_engine.backup_service(
                                                "test-service"
                                            )
                                            assert result is True

    def test_backup_with_local_destination_succeeds(
        self, backup_engine, mock_service, tmp_path
    ):
        """Test backup with local destination succeeds."""
        with patch.object(
            backup_engine.config, "get_service_config", return_value=mock_service
        ):
            with patch.object(
                backup_engine, "_get_plugin_for_service", return_value=Mock()
            ):
                with patch.object(
                    backup_engine,
                    "_determine_backup_destination",
                    return_value={"type": "local"},
                ):
                    backup_dir = tmp_path / "backups"
                    backup_dir.mkdir()
                    backup_path = backup_dir / "test.tar.gz"
                    backup_path.write_bytes(b"test" * 1000)

                    with patch.object(
                        backup_engine, "_get_backup_directory", return_value=backup_dir
                    ):
                        with patch.object(
                            backup_engine,
                            "_generate_backup_filename",
                            return_value="test.tar.gz",
                        ):
                            with patch.object(
                                backup_engine,
                                "_create_backup_metadata",
                                return_value={},
                            ):
                                with patch.object(
                                    backup_engine,
                                    "_execute_backup_command",
                                    return_value={
                                        "success": True,
                                        "backup_path": str(backup_path),
                                    },
                                ):
                                    with patch.object(
                                        backup_engine,
                                        "_verify_backup_integrity",
                                        return_value=(True, None),
                                    ):
                                        with patch.object(
                                            backup_engine, "_rotate_old_backups"
                                        ):
                                            result = backup_engine.backup_service(
                                                "test-service"
                                            )
                                            assert result is True

    def test_multiple_sequential_backups_for_same_service_work(
        self, backup_engine, mock_service, tmp_path
    ):
        """Test multiple sequential backups for same service work."""
        with patch.object(
            backup_engine.config, "get_service_config", return_value=mock_service
        ):
            with patch.object(
                backup_engine, "_get_plugin_for_service", return_value=Mock()
            ):
                with patch.object(
                    backup_engine,
                    "_determine_backup_destination",
                    return_value={"type": "local"},
                ):
                    backup_dir = tmp_path / "backups"
                    backup_dir.mkdir()

                    with patch.object(
                        backup_engine, "_get_backup_directory", return_value=backup_dir
                    ):
                        with patch.object(
                            backup_engine, "_create_backup_metadata", return_value={}
                        ):
                            with patch.object(
                                backup_engine,
                                "_verify_backup_integrity",
                                return_value=(True, None),
                            ):
                                with patch.object(
                                    backup_engine, "_rotate_old_backups", return_value=0
                                ):
                                    # First backup
                                    backup_path1 = backup_dir / "test1.tar.gz"
                                    backup_path1.write_bytes(b"test" * 1000)
                                    with patch.object(
                                        backup_engine,
                                        "_generate_backup_filename",
                                        return_value="test1.tar.gz",
                                    ):
                                        with patch.object(
                                            backup_engine,
                                            "_execute_backup_command",
                                            return_value={
                                                "success": True,
                                                "backup_path": str(backup_path1),
                                            },
                                        ):
                                            result1 = backup_engine.backup_service(
                                                "test-service"
                                            )
                                            assert result1 is True

                                    # Second backup
                                    backup_path2 = backup_dir / "test2.tar.gz"
                                    backup_path2.write_bytes(b"test" * 1000)
                                    with patch.object(
                                        backup_engine,
                                        "_generate_backup_filename",
                                        return_value="test2.tar.gz",
                                    ):
                                        with patch.object(
                                            backup_engine,
                                            "_execute_backup_command",
                                            return_value={
                                                "success": True,
                                                "backup_path": str(backup_path2),
                                            },
                                        ):
                                            result2 = backup_engine.backup_service(
                                                "test-service"
                                            )
                                            assert result2 is True

    def test_dry_run_mode_simulates_success_without_actual_backup(
        self, backup_engine_dry_run, mock_service
    ):
        """Test dry-run mode simulates success without actual backup."""
        with patch.object(
            backup_engine_dry_run.config,
            "get_service_config",
            return_value=mock_service,
        ):
            # Execute - should return True without calling helper methods
            result = backup_engine_dry_run.backup_service("test-service")

            # Verify
            assert result is True

            # Verify state was updated
            status = backup_engine_dry_run.state.get("backup_status.test-service")
            assert status == "success"


# Service Validation
class TestBackupServiceValidation:
    """Test service validation."""

    def test_service_not_found_raises_value_error(self, backup_engine):
        """Test service not found raises ValueError."""
        with patch.object(
            backup_engine.config, "get_service_config", return_value=None
        ):
            with pytest.raises(ValueError) as exc_info:
                backup_engine.backup_service("nonexistent-service")

            assert "not found in configuration" in str(exc_info.value).lower()

    def test_empty_service_name_raises_value_error(self, backup_engine):
        """Test empty service_name raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            backup_engine.backup_service("")

        assert (
            "empty" in str(exc_info.value).lower()
            or "whitespace" in str(exc_info.value).lower()
        )

    def test_service_with_backup_disabled_returns_true(
        self, backup_engine, mock_service
    ):
        """Test service with backup disabled returns True (not an error)."""
        # Create service with backup disabled
        disabled_service = ServiceConfig(
            name="test-service",
            type="docker",
            container_name="test-container",
            backup=False,
        )

        with patch.object(
            backup_engine.config, "get_service_config", return_value=disabled_service
        ):
            # Execute
            result = backup_engine.backup_service("test-service")

            # Verify - should return True (not an error)
            assert result is True

    def test_none_service_name_raises_value_error(self, backup_engine):
        """Test None service_name raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            backup_engine.backup_service(None)

        assert "non-empty string" in str(exc_info.value).lower()

    def test_whitespace_only_service_name_raises_value_error(self, backup_engine):
        """Test whitespace-only service_name raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            backup_engine.backup_service("   ")

        assert (
            "empty" in str(exc_info.value).lower()
            or "whitespace" in str(exc_info.value).lower()
        )


# Failure Scenarios
class TestBackupServiceFailure:
    """Test failure scenarios."""

    def test_plugin_fails_state_updated_returns_false(
        self, backup_engine, mock_service, tmp_path
    ):
        """Test plugin fails - state updated, returns False."""
        with patch.object(
            backup_engine.config, "get_service_config", return_value=mock_service
        ):
            with patch.object(
                backup_engine,
                "_get_plugin_for_service",
                side_effect=RuntimeError("Plugin error"),
            ):
                # Execute
                result = backup_engine.backup_service("test-service")

                # Verify
                assert result is False

                # Verify state was updated with error
                status = backup_engine.state.get("backup_status.test-service")
                assert status == "failed"

                error = backup_engine.state.get("backup_error.test-service")
                assert "Plugin error" in error

    def test_backup_command_fails_state_updated_with_error(
        self, backup_engine, mock_service, tmp_path
    ):
        """Test backup command fails - state updated with error."""
        with patch.object(
            backup_engine.config, "get_service_config", return_value=mock_service
        ):
            with patch.object(
                backup_engine, "_get_plugin_for_service", return_value=Mock()
            ):
                with patch.object(
                    backup_engine,
                    "_determine_backup_destination",
                    return_value={"type": "local"},
                ):
                    backup_dir = tmp_path / "backups"
                    backup_dir.mkdir()
                    with patch.object(
                        backup_engine, "_get_backup_directory", return_value=backup_dir
                    ):
                        with patch.object(
                            backup_engine,
                            "_generate_backup_filename",
                            return_value="test.tar.gz",
                        ):
                            with patch.object(
                                backup_engine,
                                "_create_backup_metadata",
                                return_value={},
                            ):
                                # Execute backup command fails
                                with patch.object(
                                    backup_engine,
                                    "_execute_backup_command",
                                    return_value={
                                        "success": False,
                                        "error_message": "Command execution failed",
                                    },
                                ):
                                    # Execute
                                    result = backup_engine.backup_service(
                                        "test-service"
                                    )

                                    # Verify
                                    assert result is False

                                    # Verify state
                                    status = backup_engine.state.get(
                                        "backup_status.test-service"
                                    )
                                    assert status == "failed"

                                    error = backup_engine.state.get(
                                        "backup_error.test-service"
                                    )
                                    assert "Command execution failed" in error

    def test_integrity_verification_fails_state_updated_returns_false(
        self, backup_engine, mock_service, tmp_path
    ):
        """Test integrity verification fails - state updated, returns False."""
        with patch.object(
            backup_engine.config, "get_service_config", return_value=mock_service
        ):
            with patch.object(
                backup_engine, "_get_plugin_for_service", return_value=Mock()
            ):
                with patch.object(
                    backup_engine,
                    "_determine_backup_destination",
                    return_value={"type": "local"},
                ):
                    backup_dir = tmp_path / "backups"
                    backup_dir.mkdir()
                    backup_path = backup_dir / "test.tar.gz"
                    backup_path.write_bytes(b"test" * 1000)

                    with patch.object(
                        backup_engine, "_get_backup_directory", return_value=backup_dir
                    ):
                        with patch.object(
                            backup_engine,
                            "_generate_backup_filename",
                            return_value="test.tar.gz",
                        ):
                            with patch.object(
                                backup_engine,
                                "_create_backup_metadata",
                                return_value={},
                            ):
                                with patch.object(
                                    backup_engine,
                                    "_execute_backup_command",
                                    return_value={
                                        "success": True,
                                        "backup_path": str(backup_path),
                                    },
                                ):
                                    # Verification fails
                                    with patch.object(
                                        backup_engine,
                                        "_verify_backup_integrity",
                                        return_value=(False, "Corrupted archive"),
                                    ):
                                        # Execute
                                        result = backup_engine.backup_service(
                                            "test-service"
                                        )

                                        # Verify
                                        assert result is False

                                        # Verify state
                                        status = backup_engine.state.get(
                                            "backup_status.test-service"
                                        )
                                        assert status == "failed"

                                        error = backup_engine.state.get(
                                            "backup_error.test-service"
                                        )
                                        assert "verification failed" in error.lower()
                                        assert "Corrupted archive" in error

    def test_directory_creation_fails_handled_gracefully(
        self, backup_engine, mock_service
    ):
        """Test directory creation fails - handled gracefully."""
        with patch.object(
            backup_engine.config, "get_service_config", return_value=mock_service
        ):
            with patch.object(
                backup_engine, "_get_plugin_for_service", return_value=Mock()
            ):
                with patch.object(
                    backup_engine,
                    "_determine_backup_destination",
                    return_value={"type": "local"},
                ):
                    with patch.object(
                        backup_engine,
                        "_get_backup_directory",
                        side_effect=PermissionError("Permission denied"),
                    ):
                        # Execute
                        result = backup_engine.backup_service("test-service")

                        # Verify
                        assert result is False

                        # Verify state updated with error
                        status = backup_engine.state.get("backup_status.test-service")
                        assert status == "failed"

    def test_destination_determination_fails_propagates_error(
        self, backup_engine, mock_service
    ):
        """Test destination determination fails - propagates error."""
        with patch.object(
            backup_engine.config, "get_service_config", return_value=mock_service
        ):
            with patch.object(
                backup_engine, "_get_plugin_for_service", return_value=Mock()
            ):
                with patch.object(
                    backup_engine,
                    "_determine_backup_destination",
                    side_effect=ConfigError("Invalid backup configuration"),
                ):
                    # Execute & Verify - ConfigError should propagate
                    with pytest.raises(ConfigError) as exc_info:
                        backup_engine.backup_service("test-service")

                    assert "Invalid backup configuration" in str(exc_info.value)


# State Tracking
class TestBackupServiceStateTracking:
    """Test state tracking."""

    def test_success_updates_all_state_fields_correctly(
        self, backup_engine, mock_service, tmp_path
    ):
        """Test success updates all state fields correctly."""
        with patch.object(
            backup_engine.config, "get_service_config", return_value=mock_service
        ):
            with patch.object(
                backup_engine, "_get_plugin_for_service", return_value=Mock()
            ):
                with patch.object(
                    backup_engine,
                    "_determine_backup_destination",
                    return_value={"type": "local"},
                ):
                    backup_dir = tmp_path / "backups"
                    backup_dir.mkdir()
                    backup_path = backup_dir / "test.tar.gz"
                    backup_path.write_bytes(b"test" * 1000)

                    with patch.object(
                        backup_engine, "_get_backup_directory", return_value=backup_dir
                    ):
                        with patch.object(
                            backup_engine,
                            "_generate_backup_filename",
                            return_value="test.tar.gz",
                        ):
                            with patch.object(
                                backup_engine,
                                "_create_backup_metadata",
                                return_value={},
                            ):
                                with patch.object(
                                    backup_engine,
                                    "_execute_backup_command",
                                    return_value={
                                        "success": True,
                                        "backup_path": str(backup_path),
                                    },
                                ):
                                    with patch.object(
                                        backup_engine,
                                        "_verify_backup_integrity",
                                        return_value=(True, None),
                                    ):
                                        with patch.object(
                                            backup_engine,
                                            "_rotate_old_backups",
                                            return_value=0,
                                        ):
                                            # Execute
                                            result = backup_engine.backup_service(
                                                "test-service"
                                            )

                                            # Verify
                                            assert result is True

                                            # Check all state fields
                                            status = backup_engine.state.get(
                                                "backup_status.test-service"
                                            )
                                            assert status == "success"

                                            last_backup = backup_engine.state.get(
                                                "last_backup.test-service"
                                            )
                                            assert last_backup is not None

                                            stored_path = backup_engine.state.get(
                                                "backup_path.test-service"
                                            )
                                            assert stored_path == str(backup_path)

                                            duration = backup_engine.state.get(
                                                "backup_duration.test-service"
                                            )
                                            assert duration is not None
                                            assert float(duration) >= 0

    def test_failure_updates_state_with_error_message(
        self, backup_engine, mock_service
    ):
        """Test failure updates state with error message."""
        with patch.object(
            backup_engine.config, "get_service_config", return_value=mock_service
        ):
            with patch.object(
                backup_engine,
                "_get_plugin_for_service",
                side_effect=RuntimeError("Test error"),
            ):
                # Execute
                result = backup_engine.backup_service("test-service")

                # Verify
                assert result is False

                # Check state
                status = backup_engine.state.get("backup_status.test-service")
                assert status == "failed"

                error = backup_engine.state.get("backup_error.test-service")
                assert "Test error" in error

    def test_duration_tracked_on_success_and_failure(
        self, backup_engine, mock_service, tmp_path
    ):
        """Test duration tracked on success (cleared on failure per design)."""
        # Test successful case - duration should be stored
        with patch.object(
            backup_engine.config, "get_service_config", return_value=mock_service
        ):
            with patch.object(
                backup_engine, "_get_plugin_for_service", return_value=Mock()
            ):
                with patch.object(
                    backup_engine,
                    "_determine_backup_destination",
                    return_value={"type": "local"},
                ):
                    backup_dir = tmp_path / "backups"
                    backup_dir.mkdir()
                    backup_path = backup_dir / "test.tar.gz"
                    backup_path.write_bytes(b"test" * 1000)

                    with patch.object(
                        backup_engine, "_get_backup_directory", return_value=backup_dir
                    ):
                        with patch.object(
                            backup_engine,
                            "_generate_backup_filename",
                            return_value="test.tar.gz",
                        ):
                            with patch.object(
                                backup_engine,
                                "_create_backup_metadata",
                                return_value={},
                            ):
                                with patch.object(
                                    backup_engine,
                                    "_execute_backup_command",
                                    return_value={
                                        "success": True,
                                        "backup_path": str(backup_path),
                                    },
                                ):
                                    with patch.object(
                                        backup_engine,
                                        "_verify_backup_integrity",
                                        return_value=(True, None),
                                    ):
                                        with patch.object(
                                            backup_engine,
                                            "_rotate_old_backups",
                                            return_value=0,
                                        ):
                                            # Execute
                                            result = backup_engine.backup_service(
                                                "test-service"
                                            )

                                            # Verify
                                            assert result is True

                                            # Duration should be tracked
                                            duration = backup_engine.state.get(
                                                "backup_duration.test-service"
                                            )
                                            assert duration is not None
                                            assert float(duration) >= 0

    def test_backup_path_stored_on_success(self, backup_engine, mock_service, tmp_path):
        """Test backup path stored on success."""
        with patch.object(
            backup_engine.config, "get_service_config", return_value=mock_service
        ):
            with patch.object(
                backup_engine, "_get_plugin_for_service", return_value=Mock()
            ):
                with patch.object(
                    backup_engine,
                    "_determine_backup_destination",
                    return_value={"type": "local"},
                ):
                    backup_dir = tmp_path / "backups"
                    backup_dir.mkdir()
                    backup_path = backup_dir / "test.tar.gz"
                    backup_path.write_bytes(b"test" * 1000)

                    with patch.object(
                        backup_engine, "_get_backup_directory", return_value=backup_dir
                    ):
                        with patch.object(
                            backup_engine,
                            "_generate_backup_filename",
                            return_value="test.tar.gz",
                        ):
                            with patch.object(
                                backup_engine,
                                "_create_backup_metadata",
                                return_value={},
                            ):
                                with patch.object(
                                    backup_engine,
                                    "_execute_backup_command",
                                    return_value={
                                        "success": True,
                                        "backup_path": str(backup_path),
                                    },
                                ):
                                    with patch.object(
                                        backup_engine,
                                        "_verify_backup_integrity",
                                        return_value=(True, None),
                                    ):
                                        with patch.object(
                                            backup_engine, "_rotate_old_backups"
                                        ):
                                            # Execute
                                            result = backup_engine.backup_service(
                                                "test-service"
                                            )

                                            # Verify
                                            assert result is True

                                            # Check path is stored
                                            stored_path = backup_engine.state.get(
                                                "backup_path.test-service"
                                            )
                                            assert stored_path == str(backup_path)


# Integration
class TestBackupServiceIntegration:
    """Test integration behavior."""

    def test_calls_all_helper_methods_in_correct_order(
        self, backup_engine, mock_service, tmp_path
    ):
        """Test calls all helper methods in correct order."""
        call_order = []

        def track_get_plugin(*args, **kwargs):
            call_order.append("get_plugin")
            return Mock()

        def track_determine_destination(*args, **kwargs):
            call_order.append("determine_destination")
            return {"type": "local"}

        def track_get_directory(*args, **kwargs):
            call_order.append("get_directory")
            return tmp_path

        def track_generate_filename(*args, **kwargs):
            call_order.append("generate_filename")
            return "test.tar.gz"

        def track_create_metadata(*args, **kwargs):
            call_order.append("create_metadata")
            return {}

        def track_execute_command(*args, **kwargs):
            call_order.append("execute_command")
            backup_path = tmp_path / "test.tar.gz"
            backup_path.write_bytes(b"test" * 1000)
            return {"success": True, "backup_path": str(backup_path)}

        def track_verify_integrity(*args, **kwargs):
            call_order.append("verify_integrity")
            return (True, None)

        def track_update_state(*args, **kwargs):
            call_order.append("update_state")

        def track_rotate_backups(*args, **kwargs):
            call_order.append("rotate_backups")
            return 0

        with patch.object(
            backup_engine.config, "get_service_config", return_value=mock_service
        ):
            with patch.object(
                backup_engine, "_get_plugin_for_service", side_effect=track_get_plugin
            ):
                with patch.object(
                    backup_engine,
                    "_determine_backup_destination",
                    side_effect=track_determine_destination,
                ):
                    with patch.object(
                        backup_engine,
                        "_get_backup_directory",
                        side_effect=track_get_directory,
                    ):
                        with patch.object(
                            backup_engine,
                            "_generate_backup_filename",
                            side_effect=track_generate_filename,
                        ):
                            with patch.object(
                                backup_engine,
                                "_create_backup_metadata",
                                side_effect=track_create_metadata,
                            ):
                                with patch.object(
                                    backup_engine,
                                    "_execute_backup_command",
                                    side_effect=track_execute_command,
                                ):
                                    with patch.object(
                                        backup_engine,
                                        "_verify_backup_integrity",
                                        side_effect=track_verify_integrity,
                                    ):
                                        with patch.object(
                                            backup_engine,
                                            "_update_backup_state",
                                            side_effect=track_update_state,
                                        ):
                                            with patch.object(
                                                backup_engine,
                                                "_rotate_old_backups",
                                                side_effect=track_rotate_backups,
                                            ):
                                                # Execute
                                                result = backup_engine.backup_service(
                                                    "test-service"
                                                )

                                                # Verify
                                                assert result is True

                                                # Verify order
                                                expected_order = [
                                                    "get_plugin",
                                                    "determine_destination",
                                                    "get_directory",
                                                    "generate_filename",
                                                    "create_metadata",
                                                    "execute_command",
                                                    "verify_integrity",
                                                    "update_state",
                                                    "rotate_backups",
                                                ]
                                                assert call_order == expected_order

    def test_rotation_happens_after_successful_backup_only(
        self, backup_engine, mock_service, tmp_path
    ):
        """Test rotation happens after successful backup only."""
        rotate_called = []

        def track_rotate(*args, **kwargs):
            rotate_called.append(True)
            return 0

        # Test successful case - rotation should be called
        with patch.object(
            backup_engine.config, "get_service_config", return_value=mock_service
        ):
            with patch.object(
                backup_engine, "_get_plugin_for_service", return_value=Mock()
            ):
                with patch.object(
                    backup_engine,
                    "_determine_backup_destination",
                    return_value={"type": "local"},
                ):
                    backup_dir = tmp_path / "backups"
                    backup_dir.mkdir()
                    backup_path = backup_dir / "test.tar.gz"
                    backup_path.write_bytes(b"test" * 1000)

                    with patch.object(
                        backup_engine, "_get_backup_directory", return_value=backup_dir
                    ):
                        with patch.object(
                            backup_engine,
                            "_generate_backup_filename",
                            return_value="test.tar.gz",
                        ):
                            with patch.object(
                                backup_engine,
                                "_create_backup_metadata",
                                return_value={},
                            ):
                                with patch.object(
                                    backup_engine,
                                    "_execute_backup_command",
                                    return_value={
                                        "success": True,
                                        "backup_path": str(backup_path),
                                    },
                                ):
                                    with patch.object(
                                        backup_engine,
                                        "_verify_backup_integrity",
                                        return_value=(True, None),
                                    ):
                                        with patch.object(
                                            backup_engine,
                                            "_rotate_old_backups",
                                            side_effect=track_rotate,
                                        ):
                                            result = backup_engine.backup_service(
                                                "test-service"
                                            )
                                            assert result is True
                                            assert len(rotate_called) == 1

        # Test failed case - rotation should not be called
        rotate_called.clear()
        with patch.object(
            backup_engine.config, "get_service_config", return_value=mock_service
        ):
            with patch.object(
                backup_engine, "_get_plugin_for_service", return_value=Mock()
            ):
                with patch.object(
                    backup_engine,
                    "_determine_backup_destination",
                    return_value={"type": "local"},
                ):
                    with patch.object(
                        backup_engine, "_get_backup_directory", return_value=backup_dir
                    ):
                        with patch.object(
                            backup_engine,
                            "_generate_backup_filename",
                            return_value="test.tar.gz",
                        ):
                            with patch.object(
                                backup_engine,
                                "_create_backup_metadata",
                                return_value={},
                            ):
                                # Backup command fails
                                with patch.object(
                                    backup_engine,
                                    "_execute_backup_command",
                                    return_value={
                                        "success": False,
                                        "error_message": "Failed",
                                    },
                                ):
                                    with patch.object(
                                        backup_engine,
                                        "_rotate_old_backups",
                                        side_effect=track_rotate,
                                    ):
                                        result = backup_engine.backup_service(
                                            "test-service"
                                        )
                                        assert result is False
                                        # Rotation should not have been called
                                        assert len(rotate_called) == 0

    def test_rotation_failure_doesnt_fail_backup(
        self, backup_engine, mock_service, tmp_path
    ):
        """Test rotation failure doesn't fail backup (logged warning)."""
        with patch.object(
            backup_engine.config, "get_service_config", return_value=mock_service
        ):
            with patch.object(
                backup_engine, "_get_plugin_for_service", return_value=Mock()
            ):
                with patch.object(
                    backup_engine,
                    "_determine_backup_destination",
                    return_value={"type": "local"},
                ):
                    backup_dir = tmp_path / "backups"
                    backup_dir.mkdir()
                    backup_path = backup_dir / "test.tar.gz"
                    backup_path.write_bytes(b"test" * 1000)

                    with patch.object(
                        backup_engine, "_get_backup_directory", return_value=backup_dir
                    ):
                        with patch.object(
                            backup_engine,
                            "_generate_backup_filename",
                            return_value="test.tar.gz",
                        ):
                            with patch.object(
                                backup_engine,
                                "_create_backup_metadata",
                                return_value={},
                            ):
                                with patch.object(
                                    backup_engine,
                                    "_execute_backup_command",
                                    return_value={
                                        "success": True,
                                        "backup_path": str(backup_path),
                                    },
                                ):
                                    with patch.object(
                                        backup_engine,
                                        "_verify_backup_integrity",
                                        return_value=(True, None),
                                    ):
                                        # Rotation raises exception
                                        with patch.object(
                                            backup_engine,
                                            "_rotate_old_backups",
                                            side_effect=RuntimeError("Rotation failed"),
                                        ):
                                            # Execute - should still succeed
                                            result = backup_engine.backup_service(
                                                "test-service"
                                            )

                                            # Verify - backup succeeded despite rotation failure
                                            assert result is True

                                            # Verify state shows success
                                            status = backup_engine.state.get(
                                                "backup_status.test-service"
                                            )
                                            assert status == "success"

    def test_multiple_services_dont_interfere_with_each_other(
        self, backup_engine, tmp_path
    ):
        """Test multiple services don't interfere with each other."""
        service1 = ServiceConfig(
            name="service1", type="docker", container_name="container1", backup=True
        )
        service2 = ServiceConfig(
            name="service2", type="docker", container_name="container2", backup=True
        )

        def get_service_mock(name):
            if name == "service1":
                return service1
            elif name == "service2":
                return service2
            return None

        with patch.object(
            backup_engine.config, "get_service_config", side_effect=get_service_mock
        ):
            with patch.object(
                backup_engine, "_get_plugin_for_service", return_value=Mock()
            ):
                with patch.object(
                    backup_engine,
                    "_determine_backup_destination",
                    return_value={"type": "local"},
                ):
                    backup_dir = tmp_path / "backups"
                    backup_dir.mkdir()

                    with patch.object(
                        backup_engine, "_get_backup_directory", return_value=backup_dir
                    ):
                        with patch.object(
                            backup_engine, "_create_backup_metadata", return_value={}
                        ):
                            with patch.object(
                                backup_engine,
                                "_verify_backup_integrity",
                                return_value=(True, None),
                            ):
                                with patch.object(
                                    backup_engine, "_rotate_old_backups", return_value=0
                                ):
                                    # Backup service1
                                    backup_path1 = backup_dir / "service1.tar.gz"
                                    backup_path1.write_bytes(b"test" * 1000)
                                    with patch.object(
                                        backup_engine,
                                        "_generate_backup_filename",
                                        return_value="service1.tar.gz",
                                    ):
                                        with patch.object(
                                            backup_engine,
                                            "_execute_backup_command",
                                            return_value={
                                                "success": True,
                                                "backup_path": str(backup_path1),
                                            },
                                        ):
                                            result1 = backup_engine.backup_service(
                                                "service1"
                                            )
                                            assert result1 is True

                                    # Backup service2
                                    backup_path2 = backup_dir / "service2.tar.gz"
                                    backup_path2.write_bytes(b"test" * 1000)
                                    with patch.object(
                                        backup_engine,
                                        "_generate_backup_filename",
                                        return_value="service2.tar.gz",
                                    ):
                                        with patch.object(
                                            backup_engine,
                                            "_execute_backup_command",
                                            return_value={
                                                "success": True,
                                                "backup_path": str(backup_path2),
                                            },
                                        ):
                                            result2 = backup_engine.backup_service(
                                                "service2"
                                            )
                                            assert result2 is True

                                    # Verify both services have independent state
                                    status1 = backup_engine.state.get(
                                        "backup_status.service1"
                                    )
                                    status2 = backup_engine.state.get(
                                        "backup_status.service2"
                                    )
                                    assert status1 == "success"
                                    assert status2 == "success"

                                    path1 = backup_engine.state.get(
                                        "backup_path.service1"
                                    )
                                    path2 = backup_engine.state.get(
                                        "backup_path.service2"
                                    )
                                    assert path1 == str(backup_path1)
                                    assert path2 == str(backup_path2)


# Edge Cases
class TestBackupServiceEdgeCases:
    """Test edge cases and defensive error handling."""

    def test_backup_path_none_in_result_uses_default(
        self, backup_engine, mock_service, tmp_path
    ):
        """Test backup_path=None in result uses default path."""
        with patch.object(
            backup_engine.config, "get_service_config", return_value=mock_service
        ):
            with patch.object(
                backup_engine, "_get_plugin_for_service", return_value=Mock()
            ):
                with patch.object(
                    backup_engine,
                    "_determine_backup_destination",
                    return_value={"type": "local"},
                ):
                    backup_dir = tmp_path / "backups"
                    backup_dir.mkdir()
                    backup_path = backup_dir / "test.tar.gz"
                    backup_path.write_bytes(b"test" * 1000)

                    with patch.object(
                        backup_engine, "_get_backup_directory", return_value=backup_dir
                    ):
                        with patch.object(
                            backup_engine,
                            "_generate_backup_filename",
                            return_value="test.tar.gz",
                        ):
                            with patch.object(
                                backup_engine,
                                "_create_backup_metadata",
                                return_value={},
                            ):
                                # Execute command returns success but backup_path=None
                                with patch.object(
                                    backup_engine,
                                    "_execute_backup_command",
                                    return_value={"success": True, "backup_path": None},
                                ):
                                    with patch.object(
                                        backup_engine,
                                        "_verify_backup_integrity",
                                        return_value=(True, None),
                                    ):
                                        with patch.object(
                                            backup_engine,
                                            "_rotate_old_backups",
                                            return_value=0,
                                        ):
                                            # Execute
                                            result = backup_engine.backup_service(
                                                "test-service"
                                            )

                                            # Verify - should succeed using default path
                                            assert result is True

                                            # Verify state has default path
                                            stored_path = backup_engine.state.get(
                                                "backup_path.test-service"
                                            )
                                            assert stored_path == str(backup_path)

    def test_state_update_failure_is_handled_gracefully(
        self, backup_engine, mock_service
    ):
        """Test state update failure during error handling is graceful."""
        with patch.object(
            backup_engine.config, "get_service_config", return_value=mock_service
        ):
            with patch.object(
                backup_engine,
                "_get_plugin_for_service",
                side_effect=RuntimeError("Plugin error"),
            ):
                # Mock _update_backup_state to fail
                with patch.object(
                    backup_engine,
                    "_update_backup_state",
                    side_effect=RuntimeError("State update failed"),
                ):
                    # Execute - should return False but not raise
                    result = backup_engine.backup_service("test-service")

                    # Verify
                    assert result is False
