"""
Tests for BackupEngine._update_backup_state() method.

Tests cover:
- Successful backups with all fields
- Successful backups with partial fields
- Successful backups clear previous errors
- Failed backups with error messages
- Failed backups clear previous path/duration
- Input validation
- StateManager error handling
- Edge cases
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from core.backup_engine import BackupEngine
from core.config_loader import ConfigLoader
from lib.state_manager import StateError, StateManager


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


class TestUpdateBackupStateSuccess:
    """Test successful backup state updates."""

    def test_successful_backup_with_all_fields(self, backup_engine):
        """Test successful backup with path and duration."""
        # Execute
        backup_engine._update_backup_state(
            service_name="nextcloud",
            success=True,
            backup_path="/mnt/backups/nextcloud.tar.gz",
            duration=45.2,
        )

        # Verify all state keys are set
        assert backup_engine.state.get("last_backup.nextcloud") is not None
        assert backup_engine.state.get("backup_status.nextcloud") == "success"
        assert (
            backup_engine.state.get("backup_path.nextcloud")
            == "/mnt/backups/nextcloud.tar.gz"
        )
        assert backup_engine.state.get("backup_duration.nextcloud") == "45.2"
        assert backup_engine.state.get("backup_error.nextcloud") is None

    def test_successful_backup_with_path_only(self, backup_engine):
        """Test successful backup with path but no duration."""
        # Execute
        backup_engine._update_backup_state(
            service_name="gitlab",
            success=True,
            backup_path="/mnt/backups/gitlab.tar.gz",
        )

        # Verify
        assert backup_engine.state.get("backup_status.gitlab") == "success"
        assert (
            backup_engine.state.get("backup_path.gitlab")
            == "/mnt/backups/gitlab.tar.gz"
        )
        # Duration should not be set (no key exists)
        assert backup_engine.state.get("backup_duration.gitlab") is None
        assert backup_engine.state.get("backup_error.gitlab") is None

    def test_successful_backup_with_duration_only(self, backup_engine):
        """Test successful backup with duration but no path."""
        # Execute
        backup_engine._update_backup_state(
            service_name="plex", success=True, duration=30.5
        )

        # Verify
        assert backup_engine.state.get("backup_status.plex") == "success"
        # Path should not be set
        assert backup_engine.state.get("backup_path.plex") is None
        assert backup_engine.state.get("backup_duration.plex") == "30.5"
        assert backup_engine.state.get("backup_error.plex") is None

    def test_successful_backup_clears_previous_error(self, backup_engine):
        """Test that successful backup clears any previous error."""
        # Setup: Create a failed backup first
        backup_engine.state.set("backup_status.service1", "failed")
        backup_engine.state.set(
            "backup_error.service1", "Previous backup failed due to disk space"
        )

        # Execute: Successful backup
        backup_engine._update_backup_state(
            service_name="service1",
            success=True,
            backup_path="/mnt/backups/service1.tar.gz",
        )

        # Verify: Error is cleared
        assert backup_engine.state.get("backup_status.service1") == "success"
        assert backup_engine.state.get("backup_error.service1") is None

    def test_multiple_successful_backups_update_timestamp(self, backup_engine):
        """Test that multiple backups update the timestamp correctly."""
        # First backup
        backup_engine._update_backup_state(
            service_name="test", success=True, backup_path="/path1.tar.gz"
        )
        timestamp1 = backup_engine.state.get("last_backup.test")

        # Second backup (should update timestamp)
        backup_engine._update_backup_state(
            service_name="test", success=True, backup_path="/path2.tar.gz"
        )
        timestamp2 = backup_engine.state.get("last_backup.test")

        # Verify timestamps are different
        assert timestamp1 is not None
        assert timestamp2 is not None
        assert timestamp1 != timestamp2  # Second backup has later timestamp

        # Verify path was updated
        assert backup_engine.state.get("backup_path.test") == "/path2.tar.gz"


class TestUpdateBackupStateFailure:
    """Test failed backup state updates."""

    def test_failed_backup_with_error_message(self, backup_engine):
        """Test failed backup with error message."""
        # Execute
        backup_engine._update_backup_state(
            service_name="service1",
            success=False,
            error_message="Disk full: Cannot write backup file",
        )

        # Verify
        assert backup_engine.state.get("last_backup.service1") is not None
        assert backup_engine.state.get("backup_status.service1") == "failed"
        assert (
            backup_engine.state.get("backup_error.service1")
            == "Disk full: Cannot write backup file"
        )
        # Path and duration should be cleared
        assert backup_engine.state.get("backup_path.service1") is None
        assert backup_engine.state.get("backup_duration.service1") is None

    def test_failed_backup_without_error_message(self, backup_engine):
        """Test failed backup without error message."""
        # Execute
        backup_engine._update_backup_state(service_name="service2", success=False)

        # Verify
        assert backup_engine.state.get("backup_status.service2") == "failed"
        # Error should not be set if not provided
        assert backup_engine.state.get("backup_error.service2") is None
        # Path and duration should still be cleared
        assert backup_engine.state.get("backup_path.service2") is None
        assert backup_engine.state.get("backup_duration.service2") is None

    def test_failed_backup_clears_previous_path_and_duration(self, backup_engine):
        """Test that failed backup clears previous successful backup data."""
        # Setup: Create a successful backup first
        backup_engine.state.set("backup_status.service3", "success")
        backup_engine.state.set("backup_path.service3", "/mnt/backups/old.tar.gz")
        backup_engine.state.set("backup_duration.service3", "45.2")

        # Execute: Failed backup
        backup_engine._update_backup_state(
            service_name="service3",
            success=False,
            error_message="Backup process crashed",
        )

        # Verify: Path and duration are cleared
        assert backup_engine.state.get("backup_status.service3") == "failed"
        assert backup_engine.state.get("backup_path.service3") is None
        assert backup_engine.state.get("backup_duration.service3") is None
        assert (
            backup_engine.state.get("backup_error.service3") == "Backup process crashed"
        )


class TestUpdateBackupStateValidation:
    """Test input validation."""

    def test_empty_service_name_raises_value_error(self, backup_engine):
        """Test that empty service name raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            backup_engine._update_backup_state(service_name="", success=True)

        error_msg = str(exc_info.value)
        assert "empty" in error_msg.lower() or "whitespace" in error_msg.lower()

    def test_none_service_name_raises_value_error(self, backup_engine):
        """Test that None service name raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            backup_engine._update_backup_state(service_name=None, success=True)

        error_msg = str(exc_info.value)
        assert "non-empty string" in error_msg.lower()

    def test_whitespace_only_service_name_raises_value_error(self, backup_engine):
        """Test that whitespace-only service name raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            backup_engine._update_backup_state(service_name="   ", success=True)

        error_msg = str(exc_info.value)
        assert "empty" in error_msg.lower() or "whitespace" in error_msg.lower()


class TestUpdateBackupStateErrorHandling:
    """Test error handling."""

    def test_state_manager_failure_raises_state_error(self, backup_engine):
        """Test that StateManager exception is wrapped in StateError."""
        # Mock state manager to fail
        with patch.object(
            backup_engine.state,
            "set",
            side_effect=Exception("Database connection lost"),
        ):
            with pytest.raises(StateError) as exc_info:
                backup_engine._update_backup_state(
                    service_name="test", success=True, backup_path="/path.tar.gz"
                )

            error_msg = str(exc_info.value)
            assert "test" in error_msg
            assert "Database connection lost" in error_msg

    def test_exception_chaining_preserved(self, backup_engine):
        """Test that exception chaining is preserved for debugging."""
        original_exception = RuntimeError("Original error")

        with patch.object(backup_engine.state, "set", side_effect=original_exception):
            with pytest.raises(StateError) as exc_info:
                backup_engine._update_backup_state(service_name="test", success=True)

            # Verify exception chaining
            assert exc_info.value.__cause__ is original_exception


class TestUpdateBackupStateEdgeCases:
    """Test edge cases."""

    def test_negative_duration_value(self, backup_engine):
        """Test that negative duration is stored (validation happens elsewhere)."""
        # Execute with negative duration
        backup_engine._update_backup_state(
            service_name="test", success=True, duration=-5.0
        )

        # Verify: Should be stored as-is
        assert backup_engine.state.get("backup_duration.test") == "-5.0"

    def test_zero_duration_value(self, backup_engine):
        """Test that zero duration is handled correctly."""
        # Execute with zero duration
        backup_engine._update_backup_state(
            service_name="test", success=True, duration=0.0
        )

        # Verify: Should be stored
        assert backup_engine.state.get("backup_duration.test") == "0.0"

    def test_very_long_error_message(self, backup_engine):
        """Test that very long error message is handled gracefully."""
        # Create a very long error message
        long_error = "Error: " + "x" * 10000

        # Execute
        backup_engine._update_backup_state(
            service_name="test", success=False, error_message=long_error
        )

        # Verify: Should be stored as-is
        stored_error = backup_engine.state.get("backup_error.test")
        assert stored_error == long_error
        assert len(stored_error) > 10000

    def test_special_characters_in_service_name(self, backup_engine):
        """Test service name with special characters."""
        # Execute
        backup_engine._update_backup_state(
            service_name="my-service_v2", success=True, backup_path="/path.tar.gz"
        )

        # Verify
        assert backup_engine.state.get("backup_status.my-service_v2") == "success"
        assert backup_engine.state.get("backup_path.my-service_v2") == "/path.tar.gz"

    def test_timestamp_is_iso_format(self, backup_engine):
        """Test that timestamp is in ISO 8601 format."""
        # Execute
        backup_engine._update_backup_state(service_name="test", success=True)

        # Verify: Get timestamp and check it's ISO format
        timestamp = backup_engine.state.get("last_backup.test")
        assert timestamp is not None
        # Should contain 'T' separator and timezone info
        assert "T" in timestamp
        # ISO format with timezone should end with +00:00 or Z
        assert "+" in timestamp or timestamp.endswith("Z")

    def test_duration_stored_as_string(self, backup_engine):
        """Test that duration is stored as string in state."""
        # Execute
        backup_engine._update_backup_state(
            service_name="test", success=True, duration=123.45
        )

        # Verify: Duration is stored as string
        duration = backup_engine.state.get("backup_duration.test")
        assert isinstance(duration, str)
        assert duration == "123.45"

    def test_service_name_case_sensitivity(self, backup_engine):
        """Test that service names are case-sensitive."""
        # Execute backups for different cases
        backup_engine._update_backup_state(
            service_name="MyService", success=True, backup_path="/path1.tar.gz"
        )
        backup_engine._update_backup_state(
            service_name="myservice", success=False, error_message="Failed"
        )

        # Verify: Different state for different cases
        assert backup_engine.state.get("backup_status.MyService") == "success"
        assert backup_engine.state.get("backup_status.myservice") == "failed"
        assert backup_engine.state.get("backup_path.MyService") == "/path1.tar.gz"
        assert backup_engine.state.get("backup_path.myservice") is None


class TestUpdateBackupStateStateKeys:
    """Test that correct state keys are used."""

    def test_all_state_keys_for_successful_backup(self, backup_engine):
        """Test all state keys are set correctly for successful backup."""
        # Execute
        backup_engine._update_backup_state(
            service_name="test",
            success=True,
            backup_path="/path.tar.gz",
            duration=30.0,
        )

        # Verify all expected keys exist
        assert backup_engine.state.get("last_backup.test") is not None
        assert backup_engine.state.get("backup_status.test") == "success"
        assert backup_engine.state.get("backup_path.test") == "/path.tar.gz"
        assert backup_engine.state.get("backup_duration.test") == "30.0"
        assert backup_engine.state.get("backup_error.test") is None

    def test_all_state_keys_for_failed_backup(self, backup_engine):
        """Test all state keys are set correctly for failed backup."""
        # Execute
        backup_engine._update_backup_state(
            service_name="test", success=False, error_message="Test error"
        )

        # Verify all expected keys exist
        assert backup_engine.state.get("last_backup.test") is not None
        assert backup_engine.state.get("backup_status.test") == "failed"
        assert backup_engine.state.get("backup_path.test") is None
        assert backup_engine.state.get("backup_duration.test") is None
        assert backup_engine.state.get("backup_error.test") == "Test error"

    def test_state_key_format(self, backup_engine):
        """Test that state keys follow the correct format."""
        # Mock state to track calls
        mock_state = Mock()
        backup_engine.state = mock_state

        # Execute
        backup_engine._update_backup_state(
            service_name="my-service",
            success=True,
            backup_path="/path.tar.gz",
            duration=10.5,
        )

        # Verify state.set was called with correct keys
        calls = [call[0] for call in mock_state.set.call_args_list]
        expected_keys = [
            ("last_backup.my-service",),
            ("backup_status.my-service",),
            ("backup_path.my-service",),
            ("backup_duration.my-service",),
            ("backup_error.my-service",),
        ]

        # Check that all expected keys were used
        for expected_key in expected_keys:
            assert any(
                call[0] == expected_key[0] for call in calls
            ), f"Expected key {expected_key[0]} not found in calls"
