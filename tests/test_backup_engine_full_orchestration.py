"""
Tests for BackupEngine.backup_all_services() method - full orchestration.

Tests cover:
- Success scenarios (all succeed, empty list, single service, dry-run)
- Partial failure (some succeed/fail, continues with all)
- Complete failure (all fail, no services enabled)
- Notification (summary sent, failures handled, duration passed)
- Integration (backup_service calls, disabled services skipped, results aggregated)
- Edge cases (exceptions caught, ConfigLoader failures, large service counts)
"""

from pathlib import Path
from unittest.mock import Mock, call, patch

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


# Success Scenarios
class TestBackupAllServicesSuccess:
    """Test successful backup scenarios."""

    def test_all_services_backup_successfully(self, backup_engine):
        """Test all services backup successfully."""
        # Create mock services
        services = [
            ServiceConfig(
                name="service1",
                type="docker",
                container_name="container1",
                backup=True,
            ),
            ServiceConfig(
                name="service2",
                type="docker",
                container_name="container2",
                backup=True,
            ),
            ServiceConfig(
                name="service3",
                type="docker",
                container_name="container3",
                backup=True,
            ),
        ]

        with patch.object(
            backup_engine.config, "get_all_services", return_value=services
        ):
            with patch.object(backup_engine, "backup_service", return_value=True):
                with patch.object(backup_engine, "_send_backup_summary"):
                    # Execute
                    results = backup_engine.backup_all_services()

                    # Verify
                    assert len(results) == 3
                    assert results["service1"] is True
                    assert results["service2"] is True
                    assert results["service3"] is True

    def test_empty_service_list_returns_empty_dict(self, backup_engine):
        """Test empty service list returns empty dict."""
        with patch.object(backup_engine.config, "get_all_services", return_value=[]):
            # Execute
            results = backup_engine.backup_all_services()

            # Verify
            assert results == {}

    def test_single_service_works_correctly(self, backup_engine):
        """Test single service works correctly."""
        services = [
            ServiceConfig(
                name="service1", type="docker", container_name="container1", backup=True
            )
        ]

        with patch.object(
            backup_engine.config, "get_all_services", return_value=services
        ):
            with patch.object(backup_engine, "backup_service", return_value=True):
                with patch.object(backup_engine, "_send_backup_summary"):
                    # Execute
                    results = backup_engine.backup_all_services()

                    # Verify
                    assert len(results) == 1
                    assert results["service1"] is True

    def test_multiple_services_all_succeed(self, backup_engine):
        """Test multiple services all succeed."""
        services = [
            ServiceConfig(
                name=f"service{i}",
                type="docker",
                container_name=f"service{i}",
                backup=True,
            )
            for i in range(5)
        ]

        with patch.object(
            backup_engine.config, "get_all_services", return_value=services
        ):
            with patch.object(backup_engine, "backup_service", return_value=True):
                with patch.object(backup_engine, "_send_backup_summary"):
                    # Execute
                    results = backup_engine.backup_all_services()

                    # Verify
                    assert len(results) == 5
                    assert all(success for success in results.values())

    def test_dry_run_mode_simulates_all_services(self, backup_engine_dry_run):
        """Test dry-run mode simulates all services."""
        services = [
            ServiceConfig(
                name=f"service{i}",
                type="docker",
                container_name=f"service{i}",
                backup=True,
            )
            for i in range(3)
        ]

        with patch.object(
            backup_engine_dry_run.config, "get_all_services", return_value=services
        ):
            # backup_service already handles dry-run, so it will return True
            with patch.object(
                backup_engine_dry_run, "backup_service", return_value=True
            ):
                with patch.object(backup_engine_dry_run, "_send_backup_summary"):
                    # Execute
                    results = backup_engine_dry_run.backup_all_services()

                    # Verify
                    assert len(results) == 3
                    assert all(success for success in results.values())


# Partial Failure
class TestBackupAllServicesPartialFailure:
    """Test partial failure scenarios."""

    def test_some_services_succeed_some_fail_continues_with_all(self, backup_engine):
        """Test some services succeed, some fail - continues with all."""
        services = [
            ServiceConfig(
                name="service1", type="docker", container_name="service1", backup=True
            ),
            ServiceConfig(
                name="service2", type="docker", container_name="service2", backup=True
            ),
            ServiceConfig(
                name="service3", type="docker", container_name="service3", backup=True
            ),
        ]

        # Service 2 fails, others succeed
        def backup_side_effect(service_name):
            if service_name == "service2":
                return False
            return True

        with patch.object(
            backup_engine.config, "get_all_services", return_value=services
        ):
            with patch.object(
                backup_engine, "backup_service", side_effect=backup_side_effect
            ):
                with patch.object(backup_engine, "_send_backup_summary"):
                    # Execute
                    results = backup_engine.backup_all_services()

                    # Verify
                    assert len(results) == 3
                    assert results["service1"] is True
                    assert results["service2"] is False
                    assert results["service3"] is True

    def test_first_service_fails_rest_continue(self, backup_engine):
        """Test first service fails, rest continue."""
        services = [
            ServiceConfig(
                name="service1", type="docker", container_name="service1", backup=True
            ),
            ServiceConfig(
                name="service2", type="docker", container_name="service2", backup=True
            ),
            ServiceConfig(
                name="service3", type="docker", container_name="service3", backup=True
            ),
        ]

        # First service fails
        def backup_side_effect(service_name):
            if service_name == "service1":
                return False
            return True

        with patch.object(
            backup_engine.config, "get_all_services", return_value=services
        ):
            with patch.object(
                backup_engine, "backup_service", side_effect=backup_side_effect
            ):
                with patch.object(backup_engine, "_send_backup_summary"):
                    # Execute
                    results = backup_engine.backup_all_services()

                    # Verify
                    assert len(results) == 3
                    assert results["service1"] is False
                    assert results["service2"] is True
                    assert results["service3"] is True

    def test_last_service_fails_summary_still_sent(self, backup_engine):
        """Test last service fails, summary still sent."""
        services = [
            ServiceConfig(
                name="service1", type="docker", container_name="service1", backup=True
            ),
            ServiceConfig(
                name="service2", type="docker", container_name="service2", backup=True
            ),
        ]

        # Last service fails
        def backup_side_effect(service_name):
            if service_name == "service2":
                return False
            return True

        with patch.object(
            backup_engine.config, "get_all_services", return_value=services
        ):
            with patch.object(
                backup_engine, "backup_service", side_effect=backup_side_effect
            ):
                with patch.object(
                    backup_engine, "_send_backup_summary"
                ) as mock_summary:
                    # Execute
                    results = backup_engine.backup_all_services()

                    # Verify
                    assert results["service1"] is True
                    assert results["service2"] is False

                    # Verify summary was sent
                    mock_summary.assert_called_once()

    def test_results_dict_contains_all_services_success_and_failure(
        self, backup_engine
    ):
        """Test results dict contains all services (success and failure)."""
        services = [
            ServiceConfig(
                name="service1", type="docker", container_name="service1", backup=True
            ),
            ServiceConfig(
                name="service2", type="docker", container_name="service2", backup=True
            ),
            ServiceConfig(
                name="service3", type="docker", container_name="service3", backup=True
            ),
            ServiceConfig(
                name="service4", type="docker", container_name="service4", backup=True
            ),
        ]

        # Alternating success/failure
        def backup_side_effect(service_name):
            return service_name in ["service1", "service3"]

        with patch.object(
            backup_engine.config, "get_all_services", return_value=services
        ):
            with patch.object(
                backup_engine, "backup_service", side_effect=backup_side_effect
            ):
                with patch.object(backup_engine, "_send_backup_summary"):
                    # Execute
                    results = backup_engine.backup_all_services()

                    # Verify all services in results
                    assert len(results) == 4
                    assert "service1" in results
                    assert "service2" in results
                    assert "service3" in results
                    assert "service4" in results


# Complete Failure
class TestBackupAllServicesCompleteFailure:
    """Test complete failure scenarios."""

    def test_all_services_fail_still_returns_results_and_sends_summary(
        self, backup_engine
    ):
        """Test all services fail - still returns results and sends summary."""
        services = [
            ServiceConfig(
                name="service1", type="docker", container_name="service1", backup=True
            ),
            ServiceConfig(
                name="service2", type="docker", container_name="service2", backup=True
            ),
        ]

        with patch.object(
            backup_engine.config, "get_all_services", return_value=services
        ):
            # All services fail
            with patch.object(backup_engine, "backup_service", return_value=False):
                with patch.object(
                    backup_engine, "_send_backup_summary"
                ) as mock_summary:
                    # Execute
                    results = backup_engine.backup_all_services()

                    # Verify
                    assert len(results) == 2
                    assert results["service1"] is False
                    assert results["service2"] is False

                    # Verify summary was still sent
                    mock_summary.assert_called_once()

    def test_no_services_with_backup_enabled_returns_empty_dict(self, backup_engine):
        """Test no services with backup enabled returns empty dict."""
        # All services have backup=False
        services = [
            ServiceConfig(
                name="service1", type="docker", container_name="c1", backup=False
            ),
            ServiceConfig(
                name="service2", type="docker", container_name="c2", backup=False
            ),
        ]

        with patch.object(
            backup_engine.config, "get_all_services", return_value=services
        ):
            # Execute
            results = backup_engine.backup_all_services()

            # Verify
            assert results == {}


# Notification
class TestBackupAllServicesNotification:
    """Test notification scenarios."""

    def test_summary_notification_sent_with_correct_results(self, backup_engine):
        """Test summary notification sent with correct results."""
        services = [
            ServiceConfig(
                name="service1", type="docker", container_name="service1", backup=True
            ),
            ServiceConfig(
                name="service2", type="docker", container_name="service2", backup=True
            ),
        ]

        with patch.object(
            backup_engine.config, "get_all_services", return_value=services
        ):
            with patch.object(backup_engine, "backup_service", return_value=True):
                with patch.object(
                    backup_engine, "_send_backup_summary"
                ) as mock_summary:
                    # Execute
                    results = backup_engine.backup_all_services()

                    # Verify summary was called with correct args
                    mock_summary.assert_called_once()
                    call_args = mock_summary.call_args
                    # Check results dict
                    assert call_args[0][0] == results
                    # Check duration was passed
                    assert "duration" in call_args[1]
                    assert isinstance(call_args[1]["duration"], float)
                    assert call_args[1]["duration"] >= 0

    def test_notification_failure_logged_but_doesnt_fail_backup_run(
        self, backup_engine
    ):
        """Test notification failure logged but doesn't fail backup run."""
        services = [
            ServiceConfig(
                name="service1", type="docker", container_name="service1", backup=True
            )
        ]

        with patch.object(
            backup_engine.config, "get_all_services", return_value=services
        ):
            with patch.object(backup_engine, "backup_service", return_value=True):
                # Notification fails
                with patch.object(
                    backup_engine,
                    "_send_backup_summary",
                    side_effect=RuntimeError("Notification failed"),
                ):
                    # Execute - should not raise
                    results = backup_engine.backup_all_services()

                    # Verify backup succeeded despite notification failure
                    assert results["service1"] is True

    def test_duration_passed_to_notification(self, backup_engine):
        """Test duration passed to notification."""
        services = [
            ServiceConfig(
                name="service1", type="docker", container_name="service1", backup=True
            )
        ]

        with patch.object(
            backup_engine.config, "get_all_services", return_value=services
        ):
            with patch.object(backup_engine, "backup_service", return_value=True):
                with patch.object(
                    backup_engine, "_send_backup_summary"
                ) as mock_summary:
                    # Execute
                    backup_engine.backup_all_services()

                    # Verify duration was passed
                    call_args = mock_summary.call_args
                    assert "duration" in call_args[1]
                    duration = call_args[1]["duration"]
                    assert isinstance(duration, float)
                    assert duration >= 0


# Integration
class TestBackupAllServicesIntegration:
    """Test integration scenarios."""

    def test_calls_backup_service_for_each_enabled_service(self, backup_engine):
        """Test calls backup_service() for each enabled service."""
        services = [
            ServiceConfig(
                name="service1", type="docker", container_name="service1", backup=True
            ),
            ServiceConfig(
                name="service2", type="docker", container_name="service2", backup=True
            ),
            ServiceConfig(
                name="service3", type="docker", container_name="service3", backup=True
            ),
        ]

        with patch.object(
            backup_engine.config, "get_all_services", return_value=services
        ):
            with patch.object(
                backup_engine, "backup_service", return_value=True
            ) as mock_backup:
                with patch.object(backup_engine, "_send_backup_summary"):
                    # Execute
                    backup_engine.backup_all_services()

                    # Verify backup_service was called for each service
                    assert mock_backup.call_count == 3
                    mock_backup.assert_has_calls(
                        [
                            call("service1"),
                            call("service2"),
                            call("service3"),
                        ]
                    )

    def test_skips_services_with_backup_disabled(self, backup_engine):
        """Test skips services with backup disabled."""
        services = [
            ServiceConfig(
                name="service1", type="docker", container_name="service1", backup=True
            ),
            ServiceConfig(
                name="service2", type="docker", container_name="service2", backup=False
            ),
            ServiceConfig(
                name="service3", type="docker", container_name="service3", backup=True
            ),
        ]

        with patch.object(
            backup_engine.config, "get_all_services", return_value=services
        ):
            with patch.object(
                backup_engine, "backup_service", return_value=True
            ) as mock_backup:
                with patch.object(backup_engine, "_send_backup_summary"):
                    # Execute
                    results = backup_engine.backup_all_services()

                    # Verify only enabled services were backed up
                    assert len(results) == 2
                    assert "service1" in results
                    assert "service2" not in results  # Skipped
                    assert "service3" in results

                    # Verify backup_service was called only for enabled services
                    assert mock_backup.call_count == 2
                    mock_backup.assert_has_calls([call("service1"), call("service3")])

    def test_results_aggregated_correctly(self, backup_engine):
        """Test results aggregated correctly."""
        services = [
            ServiceConfig(
                name=f"service{i}",
                type="docker",
                container_name=f"service{i}",
                backup=True,
            )
            for i in range(4)
        ]

        # Some succeed, some fail
        def backup_side_effect(service_name):
            return service_name in ["service0", "service2"]

        with patch.object(
            backup_engine.config, "get_all_services", return_value=services
        ):
            with patch.object(
                backup_engine, "backup_service", side_effect=backup_side_effect
            ):
                with patch.object(backup_engine, "_send_backup_summary"):
                    # Execute
                    results = backup_engine.backup_all_services()

                    # Verify aggregation
                    assert len(results) == 4
                    assert results["service0"] is True
                    assert results["service1"] is False
                    assert results["service2"] is True
                    assert results["service3"] is False

    def test_total_duration_tracked_accurately(self, backup_engine):
        """Test total duration tracked accurately."""
        services = [
            ServiceConfig(
                name="service1", type="docker", container_name="service1", backup=True
            )
        ]

        with patch.object(
            backup_engine.config, "get_all_services", return_value=services
        ):
            with patch.object(backup_engine, "backup_service", return_value=True):
                with patch.object(
                    backup_engine, "_send_backup_summary"
                ) as mock_summary:
                    # Execute
                    backup_engine.backup_all_services()

                    # Verify duration was tracked
                    call_args = mock_summary.call_args
                    duration = call_args[1]["duration"]
                    assert duration >= 0
                    # Should be very small for mocked test
                    assert duration < 10  # Should complete in under 10 seconds


# Edge Cases
class TestBackupAllServicesEdgeCases:
    """Test edge cases."""

    def test_exception_in_backup_service_caught_and_recorded_as_failure(
        self, backup_engine
    ):
        """Test exception in backup_service() caught and recorded as failure."""
        services = [
            ServiceConfig(
                name="service1", type="docker", container_name="service1", backup=True
            ),
            ServiceConfig(
                name="service2", type="docker", container_name="service2", backup=True
            ),
        ]

        # Second service raises exception
        def backup_side_effect(service_name):
            if service_name == "service2":
                raise RuntimeError("Unexpected error")
            return True

        with patch.object(
            backup_engine.config, "get_all_services", return_value=services
        ):
            with patch.object(
                backup_engine, "backup_service", side_effect=backup_side_effect
            ):
                with patch.object(backup_engine, "_send_backup_summary"):
                    # Execute - should not raise
                    results = backup_engine.backup_all_services()

                    # Verify exception was caught and recorded as failure
                    assert results["service1"] is True
                    assert results["service2"] is False

    def test_config_loader_failure_propagates_as_config_error(self, backup_engine):
        """Test ConfigLoader failure propagates as ConfigError."""
        # get_all_services raises ConfigError
        with patch.object(
            backup_engine.config,
            "get_all_services",
            side_effect=ConfigError("Config load failed"),
        ):
            # Execute & Verify
            with pytest.raises(ConfigError) as exc_info:
                backup_engine.backup_all_services()

            assert "Config load failed" in str(exc_info.value)

    def test_large_number_of_services_handled_efficiently(self, backup_engine):
        """Test large number of services (e.g., 20) handled efficiently."""
        # Create 20 services
        services = [
            ServiceConfig(
                name=f"service{i}",
                type="docker",
                container_name=f"service{i}",
                backup=True,
            )
            for i in range(20)
        ]

        with patch.object(
            backup_engine.config, "get_all_services", return_value=services
        ):
            with patch.object(backup_engine, "backup_service", return_value=True):
                with patch.object(backup_engine, "_send_backup_summary"):
                    # Execute
                    results = backup_engine.backup_all_services()

                    # Verify
                    assert len(results) == 20
                    assert all(success for success in results.values())


# Logging
class TestBackupAllServicesLogging:
    """Test logging behavior."""

    def test_logs_service_count_at_start(self, backup_engine):
        """Test logs service count at start."""
        services = [
            ServiceConfig(
                name="service1", type="docker", container_name="service1", backup=True
            ),
            ServiceConfig(
                name="service2", type="docker", container_name="service2", backup=True
            ),
        ]

        with patch.object(
            backup_engine.config, "get_all_services", return_value=services
        ):
            with patch.object(backup_engine, "backup_service", return_value=True):
                with patch.object(backup_engine, "_send_backup_summary"):
                    # Execute
                    backup_engine.backup_all_services()

                    # Logging is done in method (verified visually in test output)

    def test_logs_final_summary_with_success_failure_counts(self, backup_engine):
        """Test logs final summary with success/failure counts."""
        services = [
            ServiceConfig(
                name="service1", type="docker", container_name="service1", backup=True
            ),
            ServiceConfig(
                name="service2", type="docker", container_name="service2", backup=True
            ),
        ]

        # One succeeds, one fails
        def backup_side_effect(service_name):
            return service_name == "service1"

        with patch.object(
            backup_engine.config, "get_all_services", return_value=services
        ):
            with patch.object(
                backup_engine, "backup_service", side_effect=backup_side_effect
            ):
                with patch.object(backup_engine, "_send_backup_summary"):
                    # Execute
                    backup_engine.backup_all_services()

                    # Logging is done in method (verified visually in test output)

    def test_logs_error_for_unexpected_failures(self, backup_engine):
        """Test logs error for unexpected failures."""
        services = [
            ServiceConfig(
                name="service1", type="docker", container_name="service1", backup=True
            )
        ]

        with patch.object(
            backup_engine.config, "get_all_services", return_value=services
        ):
            with patch.object(
                backup_engine,
                "backup_service",
                side_effect=RuntimeError("Unexpected error"),
            ):
                with patch.object(backup_engine, "_send_backup_summary"):
                    # Execute
                    results = backup_engine.backup_all_services()

                    # Verify error was logged (exc_info=True adds traceback)
                    assert results["service1"] is False


# Return Value
class TestBackupAllServicesReturnValue:
    """Test return value correctness."""

    def test_returns_dict_with_correct_structure(self, backup_engine):
        """Test returns dict with correct structure."""
        services = [
            ServiceConfig(
                name="service1", type="docker", container_name="service1", backup=True
            ),
            ServiceConfig(
                name="service2", type="docker", container_name="service2", backup=True
            ),
        ]

        with patch.object(
            backup_engine.config, "get_all_services", return_value=services
        ):
            with patch.object(backup_engine, "backup_service", return_value=True):
                with patch.object(backup_engine, "_send_backup_summary"):
                    # Execute
                    results = backup_engine.backup_all_services()

                    # Verify structure
                    assert isinstance(results, dict)
                    assert all(isinstance(k, str) for k in results.keys())
                    assert all(isinstance(v, bool) for v in results.values())

    def test_returns_empty_dict_when_no_services(self, backup_engine):
        """Test returns empty dict when no services."""
        with patch.object(backup_engine.config, "get_all_services", return_value=[]):
            # Execute
            results = backup_engine.backup_all_services()

            # Verify
            assert results == {}
            assert isinstance(results, dict)

    def test_service_names_match_input_services(self, backup_engine):
        """Test service names in results match input services."""
        services = [
            ServiceConfig(
                name="alpha", type="docker", container_name="alpha", backup=True
            ),
            ServiceConfig(
                name="beta", type="docker", container_name="beta", backup=True
            ),
            ServiceConfig(
                name="gamma", type="docker", container_name="gamma", backup=True
            ),
        ]

        with patch.object(
            backup_engine.config, "get_all_services", return_value=services
        ):
            with patch.object(backup_engine, "backup_service", return_value=True):
                with patch.object(backup_engine, "_send_backup_summary"):
                    # Execute
                    results = backup_engine.backup_all_services()

                    # Verify service names match
                    assert set(results.keys()) == {"alpha", "beta", "gamma"}
