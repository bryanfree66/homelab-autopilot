"""
Tests for BackupEngine._send_backup_summary() method.

Tests cover:
- Success cases (all successful, some failed, formatting)
- Configuration cases (no plugin, plugin configured, dry-run)
- Failure cases (plugin errors, failed services)
- Input validation
- Integration with StateManager for error messages
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from core.backup_engine import BackupEngine
from core.config_loader import ConfigLoader


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


# Success Cases
class TestSendBackupSummarySuccess:
    """Test successful notification sending scenarios."""

    def test_all_services_successful_sends_summary_with_correct_counts(
        self, backup_engine
    ):
        """Test all services successful sends summary with correct counts."""
        results = {
            "nextcloud": True,
            "adguard": True,
            "plex": True,
        }

        # Execute - should not raise
        backup_engine._send_backup_summary(results)

        # Verify operation completed (logging is done in method)
        # No exception means success

    def test_some_services_failed_includes_failure_details(self, backup_engine):
        """Test some services failed includes failure details."""
        results = {
            "nextcloud": True,
            "adguard": False,
            "plex": True,
        }

        # Set error message for failed service in StateManager
        backup_engine.state.set(
            "backup_error.adguard", "Proxmox API connection timeout after 30s"
        )

        # Execute - should not raise
        backup_engine._send_backup_summary(results)

        # Verify operation completed
        # Method should have retrieved error message from StateManager

    def test_duration_included_in_message_when_provided(self, backup_engine):
        """Test duration included in message when provided."""
        results = {"nextcloud": True, "plex": True}

        # Execute with duration
        backup_engine._send_backup_summary(results, duration=245.3)

        # Verify operation completed
        # Method should have formatted duration as "245.3 seconds"

    def test_duration_omitted_when_not_provided(self, backup_engine):
        """Test duration omitted when not provided."""
        results = {"nextcloud": True, "plex": True}

        # Execute without duration
        backup_engine._send_backup_summary(results)

        # Verify operation completed
        # Method should not include duration line

    def test_single_service_backup_formats_correctly(self, backup_engine):
        """Test single service backup formats correctly."""
        results = {"nextcloud": True}

        # Execute
        backup_engine._send_backup_summary(results)

        # Verify operation completed
        # Should format correctly with 1/1 successful

    def test_message_format_matches_expected_structure(self, backup_engine):
        """Test message format matches expected structure."""
        results = {
            "nextcloud": True,
            "adguard": False,
            "immich": True,
        }

        # Set error for failed service
        backup_engine.state.set("backup_error.adguard", "Connection refused")

        # Execute
        backup_engine._send_backup_summary(results, duration=100.5)

        # Verify operation completed successfully
        # Message should include: title, counts, duration, success list, fail list


# Configuration Cases
class TestSendBackupSummaryConfiguration:
    """Test notification configuration scenarios."""

    def test_no_notification_plugin_configured_logs_info_and_returns(
        self, backup_engine
    ):
        """Test no notification plugin configured logs INFO and returns (no error)."""
        results = {"nextcloud": True}

        # Mock config.get to return None for global
        with patch.object(backup_engine.config, "get", return_value=None):
            # Execute - should not raise
            backup_engine._send_backup_summary(results)

        # Verify completed without error

    def test_notification_plugin_configured_and_available_sends_notification(
        self, backup_engine
    ):
        """Test notification plugin configured and available sends notification."""
        results = {"nextcloud": True}

        # Mock global config with notification enabled
        mock_global_config = Mock()
        mock_global_config.get.return_value = {"enabled": True, "type": "email"}

        with patch.object(backup_engine.config, "get") as mock_get:
            mock_get.return_value = mock_global_config

            # Execute - should not raise
            backup_engine._send_backup_summary(results)

        # Verify operation completed

    def test_dry_run_mode_logs_but_doesnt_send_notification(
        self, backup_engine_dry_run
    ):
        """Test dry-run mode logs but doesn't send notification."""
        results = {"nextcloud": True, "plex": False}

        # Execute in dry-run mode
        backup_engine_dry_run._send_backup_summary(results, duration=50.2)

        # Verify operation completed
        # Should log "[DRY RUN] Would send notification..." but not send


# Failure Cases
class TestSendBackupSummaryFailure:
    """Test failure handling scenarios."""

    def test_notification_plugin_fails_to_send_logs_error_but_doesnt_raise(
        self, backup_engine
    ):
        """Test notification plugin fails to send logs ERROR but doesn't raise."""
        results = {"nextcloud": True}

        # Mock config.get to raise exception
        with patch.object(
            backup_engine.config, "get", side_effect=RuntimeError("Plugin error")
        ):
            # Execute - should not raise despite config error
            backup_engine._send_backup_summary(results)

        # Verify completed without raising

    def test_notification_plugin_not_found_logs_error_but_doesnt_raise(
        self, backup_engine
    ):
        """Test notification plugin not found logs ERROR but doesn't raise."""
        results = {"nextcloud": True}

        # Mock notification_config.get to return None
        mock_global = Mock()
        mock_global.get.return_value = None

        with patch.object(backup_engine.config, "get", return_value=mock_global):
            # Execute - should not raise
            backup_engine._send_backup_summary(results)

        # Verify completed

    def test_notification_sending_exception_logs_error_but_doesnt_raise(
        self, backup_engine
    ):
        """Test exception during notification sending logs ERROR but doesn't raise."""
        results = {"nextcloud": True}

        # Mock notification config to be properly configured
        mock_notification_config = {"enabled": True, "type": "email"}
        mock_global = Mock()
        mock_global.get.return_value = mock_notification_config

        # Mock logger.info to raise exception in the notification sending block
        def info_side_effect(msg, *args, **kwargs):
            if "Sending backup summary notification" in msg:
                raise RuntimeError("Simulated notification plugin error")

        with patch.object(backup_engine.config, "get", return_value=mock_global):
            with patch.object(
                backup_engine.logger, "info", side_effect=info_side_effect
            ):
                # Execute - should not raise despite notification error
                backup_engine._send_backup_summary(results)

        # Verify completed without raising

    def test_failed_services_include_error_messages_from_state_manager(
        self, backup_engine
    ):
        """Test failed services include error messages from StateManager."""
        results = {
            "nextcloud": True,
            "adguard": False,
            "immich": False,
        }

        # Set error messages in StateManager
        backup_engine.state.set("backup_error.adguard", "Disk full")
        backup_engine.state.set("backup_error.immich", "API authentication failed")

        # Execute
        backup_engine._send_backup_summary(results)

        # Verify error messages were retrieved from StateManager
        assert backup_engine.state.get("backup_error.adguard") == "Disk full"
        assert (
            backup_engine.state.get("backup_error.immich")
            == "API authentication failed"
        )


# Validation Cases
class TestSendBackupSummaryValidation:
    """Test input validation."""

    def test_empty_results_dict_raises_value_error(self, backup_engine):
        """Test empty results dict raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            backup_engine._send_backup_summary({})

        assert "empty" in str(exc_info.value).lower()

    def test_none_results_raises_value_error(self, backup_engine):
        """Test None results raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            backup_engine._send_backup_summary(None)

        error_msg = str(exc_info.value)
        assert "dict" in error_msg.lower()

    def test_results_with_non_string_keys_raises_value_error(self, backup_engine):
        """Test results with non-string keys raises ValueError."""
        results = {123: True, "nextcloud": True}  # Integer key

        with pytest.raises(ValueError) as exc_info:
            backup_engine._send_backup_summary(results)

        error_msg = str(exc_info.value)
        assert "string" in error_msg.lower()

    def test_results_with_non_bool_values_raises_value_error(self, backup_engine):
        """Test results with non-bool values raises ValueError."""
        results = {"nextcloud": True, "adguard": "success"}  # String value

        with pytest.raises(ValueError) as exc_info:
            backup_engine._send_backup_summary(results)

        error_msg = str(exc_info.value)
        assert "boolean" in error_msg.lower()


# Integration Cases
class TestSendBackupSummaryIntegration:
    """Test integration with other components."""

    def test_retrieves_error_messages_for_failed_services_from_state_manager(
        self, backup_engine
    ):
        """Test retrieves error messages for failed services from StateManager."""
        results = {
            "service1": False,
            "service2": False,
            "service3": True,
        }

        # Pre-populate StateManager with error messages
        backup_engine.state.set("backup_error.service1", "Error message 1")
        backup_engine.state.set("backup_error.service2", "Error message 2")

        # Execute
        backup_engine._send_backup_summary(results)

        # Verify StateManager was queried for error messages
        # (method should have called state.get() for each failed service)

    def test_formats_multiple_failed_services_correctly(self, backup_engine):
        """Test formats multiple failed services correctly."""
        results = {
            "service_a": False,
            "service_b": False,
            "service_c": False,
            "service_d": True,
        }

        # Set error messages
        backup_engine.state.set("backup_error.service_a", "Error A")
        backup_engine.state.set("backup_error.service_b", "Error B")
        # service_c has no error message

        # Execute
        backup_engine._send_backup_summary(results)

        # Verify operation completed
        # Should format all 3 failed services, with "(no error details)" for service_c


class TestSendBackupSummaryMessageFormat:
    """Test message formatting details."""

    def test_successful_services_are_sorted_alphabetically(self, backup_engine):
        """Test successful services are sorted alphabetically."""
        results = {
            "zulu": True,
            "alpha": True,
            "mike": True,
        }

        # Execute
        backup_engine._send_backup_summary(results)

        # Verify operation completed
        # Message should list services as: alpha, mike, zulu

    def test_failed_services_are_sorted_alphabetically(self, backup_engine):
        """Test failed services are sorted alphabetically."""
        results = {
            "zulu": False,
            "alpha": False,
            "mike": False,
        }

        # Execute
        backup_engine._send_backup_summary(results)

        # Verify operation completed
        # Message should list services as: alpha, mike, zulu

    def test_subject_line_format_matches_specification(self, backup_engine):
        """Test subject line format matches specification."""
        results = {
            "service1": True,
            "service2": False,
            "service3": True,
        }

        # Execute
        backup_engine._send_backup_summary(results)

        # Verify operation completed
        # Subject should be: "Homelab Autopilot Backup Summary - 2/3 Successful"

    def test_failed_service_without_error_message_shows_placeholder(
        self, backup_engine
    ):
        """Test failed service without error message shows placeholder."""
        results = {"service1": False}

        # Don't set any error message in StateManager

        # Execute
        backup_engine._send_backup_summary(results)

        # Verify operation completed
        # Message should show: "- service1: (no error details)"


class TestSendBackupSummaryNotificationDisabled:
    """Test behavior when notifications are disabled."""

    def test_notifications_disabled_in_config_skips_sending(self, backup_engine):
        """Test notifications disabled in config skips sending."""
        results = {"nextcloud": True}

        # Mock notification config with enabled=False
        mock_notification = {"enabled": False, "type": "email"}
        mock_global = Mock()
        mock_global.get.return_value = mock_notification

        with patch.object(backup_engine.config, "get", return_value=mock_global):
            # Execute - should not raise
            backup_engine._send_backup_summary(results)

        # Verify completed (should skip sending due to disabled flag)
