"""
Tests for BackupEngine._rotate_old_backups() method.

Tests cover:
- Success cases (deletion, dry-run)
- Failure cases (permission errors, policy failures)
- Input validation
- Edge cases
"""

import os
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from core.backup_engine import BackupEngine, BackupError
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


def create_old_backup_files(backup_dir: Path, count: int, days_old: int):
    """Create backup files with specific age."""
    files = []
    for i in range(count):
        file_path = backup_dir / f"backup_{i}.tar.gz"
        file_path.write_bytes(b"test backup content")

        # Set modification time to days_old days ago
        old_time = time.time() - (days_old * 24 * 60 * 60)
        os.utime(file_path, (old_time, old_time))

        files.append(file_path)

    return files


# Success Cases
class TestRotateOldBackupsSuccess:
    """Test successful backup rotation."""

    def test_successfully_deletes_multiple_old_backups(self, backup_engine, tmp_path):
        """Test successfully deletes multiple old backups and returns correct count."""
        # Setup: Create backup directory with old files
        service_name = "test-service"
        backup_dir = tmp_path / "backups" / "homelab" / service_name
        backup_dir.mkdir(parents=True)

        # Create 3 old backup files (older than retention period)
        old_files = create_old_backup_files(backup_dir, 3, days_old=35)

        # Mock _apply_retention_policy to return the old files
        with patch.object(
            backup_engine, "_apply_retention_policy", return_value=old_files
        ):
            # Execute
            deleted_count = backup_engine._rotate_old_backups(service_name)

        # Verify
        assert deleted_count == 3
        # All files should be deleted
        for file_path in old_files:
            assert not file_path.exists()

    def test_no_old_backups_to_delete_returns_zero(self, backup_engine):
        """Test no old backups to delete returns 0."""
        # Mock _apply_retention_policy to return empty list
        with patch.object(backup_engine, "_apply_retention_policy", return_value=[]):
            # Execute
            deleted_count = backup_engine._rotate_old_backups("test-service")

        # Verify
        assert deleted_count == 0

    def test_single_backup_to_delete_works_correctly(self, backup_engine, tmp_path):
        """Test single backup to delete works correctly."""
        # Setup
        service_name = "test-service"
        backup_dir = tmp_path / "backups" / "homelab" / service_name
        backup_dir.mkdir(parents=True)

        old_file = create_old_backup_files(backup_dir, 1, days_old=35)[0]

        # Mock
        with patch.object(
            backup_engine, "_apply_retention_policy", return_value=[old_file]
        ):
            # Execute
            deleted_count = backup_engine._rotate_old_backups(service_name)

        # Verify
        assert deleted_count == 1
        assert not old_file.exists()

    def test_dry_run_mode_logs_but_doesnt_delete_files(
        self, backup_engine_dry_run, tmp_path
    ):
        """Test dry-run mode logs but doesn't delete files."""
        # Setup
        service_name = "test-service"
        backup_dir = tmp_path / "backups" / "homelab" / service_name
        backup_dir.mkdir(parents=True)

        old_files = create_old_backup_files(backup_dir, 3, days_old=35)

        # Mock
        with patch.object(
            backup_engine_dry_run, "_apply_retention_policy", return_value=old_files
        ):
            # Execute
            deleted_count = backup_engine_dry_run._rotate_old_backups(service_name)

        # Verify
        assert deleted_count == 0  # Nothing actually deleted in dry-run
        # All files should still exist
        for file_path in old_files:
            assert file_path.exists()


# Failure Cases
class TestRotateOldBackupsFailure:
    """Test failed backup rotation scenarios."""

    def test_permission_error_on_one_file_continues_with_others(
        self, backup_engine, tmp_path
    ):
        """Test permission error on one file continues with others (partial success)."""
        # Setup
        service_name = "test-service"
        backup_dir = tmp_path / "backups" / "homelab" / service_name
        backup_dir.mkdir(parents=True)

        old_files = create_old_backup_files(backup_dir, 3, days_old=35)

        # Create a side effect function that raises PermissionError for middle file
        original_unlink = Path.unlink

        def unlink_with_error(self, *args, **kwargs):
            if self == old_files[1]:
                raise PermissionError("Permission denied")
            return original_unlink(self, *args, **kwargs)

        # Mock
        with patch.object(
            backup_engine, "_apply_retention_policy", return_value=old_files
        ):
            with patch.object(Path, "unlink", unlink_with_error):
                # Execute
                deleted_count = backup_engine._rotate_old_backups(service_name)

        # Verify: Should delete 2 out of 3 files
        assert deleted_count == 2
        assert not old_files[0].exists()
        assert old_files[1].exists()  # Failed to delete
        assert not old_files[2].exists()

    def test_all_files_fail_to_delete_returns_zero(self, backup_engine, tmp_path):
        """Test all files fail to delete returns 0 (logs warnings)."""
        # Setup
        service_name = "test-service"
        backup_dir = tmp_path / "backups" / "homelab" / service_name
        backup_dir.mkdir(parents=True)

        old_files = create_old_backup_files(backup_dir, 3, days_old=35)

        # Mock unlink to always raise PermissionError
        with patch.object(
            backup_engine, "_apply_retention_policy", return_value=old_files
        ):
            with patch.object(
                Path, "unlink", side_effect=PermissionError("Permission denied")
            ):
                # Execute
                deleted_count = backup_engine._rotate_old_backups(service_name)

        # Verify
        assert deleted_count == 0
        # All files should still exist
        for file_path in old_files:
            assert file_path.exists()

    def test_apply_retention_policy_raises_backup_error(self, backup_engine):
        """Test _apply_retention_policy() raises exception wraps in BackupError."""
        # Mock _apply_retention_policy to raise BackupError
        with patch.object(
            backup_engine,
            "_apply_retention_policy",
            side_effect=BackupError("Test backup error"),
        ):
            # Execute & Verify
            with pytest.raises(BackupError) as exc_info:
                backup_engine._rotate_old_backups("test-service")

            assert "Test backup error" in str(exc_info.value)

    def test_apply_retention_policy_raises_generic_exception(self, backup_engine):
        """Test generic exception from _apply_retention_policy() is wrapped."""
        # Mock _apply_retention_policy to raise generic exception
        with patch.object(
            backup_engine,
            "_apply_retention_policy",
            side_effect=RuntimeError("Unexpected error"),
        ):
            # Execute & Verify
            with pytest.raises(BackupError) as exc_info:
                backup_engine._rotate_old_backups("test-service")

            error_msg = str(exc_info.value)
            assert "Failed to apply retention policy" in error_msg
            assert "Unexpected error" in error_msg


# Validation
class TestRotateOldBackupsValidation:
    """Test input validation."""

    def test_empty_service_name_raises_value_error(self, backup_engine):
        """Test empty service_name raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            backup_engine._rotate_old_backups("")

        error_msg = str(exc_info.value)
        assert "empty" in error_msg.lower() or "whitespace" in error_msg.lower()

    def test_none_service_name_raises_value_error(self, backup_engine):
        """Test None service_name raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            backup_engine._rotate_old_backups(None)

        error_msg = str(exc_info.value)
        assert "non-empty string" in error_msg.lower()

    def test_whitespace_only_service_name_raises_value_error(self, backup_engine):
        """Test whitespace-only service_name raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            backup_engine._rotate_old_backups("   ")

        error_msg = str(exc_info.value)
        assert "empty" in error_msg.lower() or "whitespace" in error_msg.lower()


# Edge Cases
class TestRotateOldBackupsEdgeCases:
    """Test edge cases."""

    def test_file_already_deleted_between_policy_and_deletion(
        self, backup_engine, tmp_path
    ):
        """Test file already deleted (missing between policy check and deletion)."""
        # Setup
        service_name = "test-service"
        backup_dir = tmp_path / "backups" / "homelab" / service_name
        backup_dir.mkdir(parents=True)

        # Create files
        old_files = create_old_backup_files(backup_dir, 3, days_old=35)

        # Delete middle file before rotation
        old_files[1].unlink()

        # Mock
        with patch.object(
            backup_engine, "_apply_retention_policy", return_value=old_files
        ):
            # Execute
            deleted_count = backup_engine._rotate_old_backups(service_name)

        # Verify: Should delete 2 out of 3 (one was already gone)
        assert deleted_count == 2
        assert not old_files[0].exists()
        assert not old_files[1].exists()
        assert not old_files[2].exists()

    def test_very_large_number_of_files_to_delete(self, backup_engine, tmp_path):
        """Test very large number of files to delete (performance check)."""
        # Setup
        service_name = "test-service"
        backup_dir = tmp_path / "backups" / "homelab" / service_name
        backup_dir.mkdir(parents=True)

        # Create 100 old files
        old_files = create_old_backup_files(backup_dir, 100, days_old=35)

        # Mock
        with patch.object(
            backup_engine, "_apply_retention_policy", return_value=old_files
        ):
            # Execute
            deleted_count = backup_engine._rotate_old_backups(service_name)

        # Verify
        assert deleted_count == 100
        for file_path in old_files:
            assert not file_path.exists()

    def test_files_with_special_characters_in_names(self, backup_engine, tmp_path):
        """Test files with special characters in names."""
        # Setup
        service_name = "test-service"
        backup_dir = tmp_path / "backups" / "homelab" / service_name
        backup_dir.mkdir(parents=True)

        # Create files with special characters
        special_names = [
            "backup-2024-01-01_10:30:00.tar.gz",
            "backup_[test]_v2.tar.gz",
            "backup (copy).tar.gz",
        ]

        old_files = []
        for name in special_names:
            file_path = backup_dir / name
            file_path.write_bytes(b"test")

            # Make it old
            old_time = time.time() - (35 * 24 * 60 * 60)
            os.utime(file_path, (old_time, old_time))
            old_files.append(file_path)

        # Mock
        with patch.object(
            backup_engine, "_apply_retention_policy", return_value=old_files
        ):
            # Execute
            deleted_count = backup_engine._rotate_old_backups(service_name)

        # Verify
        assert deleted_count == 3
        for file_path in old_files:
            assert not file_path.exists()


class TestRotateOldBackupsLogging:
    """Test logging behavior."""

    def test_logs_each_successful_deletion(self, backup_engine, tmp_path):
        """Test logs each successful deletion with filename."""
        # Setup
        service_name = "test-service"
        backup_dir = tmp_path / "backups" / "homelab" / service_name
        backup_dir.mkdir(parents=True)

        old_files = create_old_backup_files(backup_dir, 2, days_old=35)

        # Mock
        with patch.object(
            backup_engine, "_apply_retention_policy", return_value=old_files
        ):
            # Execute
            deleted_count = backup_engine._rotate_old_backups(service_name)

        # Verify execution succeeded
        assert deleted_count == 2

    def test_logs_summary_at_end(self, backup_engine, tmp_path):
        """Test logs summary at end."""
        # Setup
        service_name = "test-service"
        backup_dir = tmp_path / "backups" / "homelab" / service_name
        backup_dir.mkdir(parents=True)

        old_files = create_old_backup_files(backup_dir, 3, days_old=35)

        # Mock
        with patch.object(
            backup_engine, "_apply_retention_policy", return_value=old_files
        ):
            # Execute
            deleted_count = backup_engine._rotate_old_backups(service_name)

        # Verify execution succeeded
        assert deleted_count == 3

    def test_logs_warning_for_permission_error(self, backup_engine, tmp_path):
        """Test logs warning for individual file failures."""
        # Setup
        service_name = "test-service"
        backup_dir = tmp_path / "backups" / "homelab" / service_name
        backup_dir.mkdir(parents=True)

        old_files = create_old_backup_files(backup_dir, 2, days_old=35)

        # Create a side effect function that raises PermissionError for first file
        original_unlink = Path.unlink

        def unlink_with_error(self, *args, **kwargs):
            if self == old_files[0]:
                raise PermissionError("Permission denied")
            return original_unlink(self, *args, **kwargs)

        # Mock
        with patch.object(
            backup_engine, "_apply_retention_policy", return_value=old_files
        ):
            with patch.object(Path, "unlink", unlink_with_error):
                # Execute
                deleted_count = backup_engine._rotate_old_backups(service_name)

        # Verify: Should still process and report
        assert deleted_count == 1


class TestRotateOldBackupsReturnValue:
    """Test return value correctness."""

    def test_returns_exact_count_of_deleted_files(self, backup_engine, tmp_path):
        """Test returns exact count of successfully deleted files."""
        # Setup
        service_name = "test-service"
        backup_dir = tmp_path / "backups" / "homelab" / service_name
        backup_dir.mkdir(parents=True)

        old_files = create_old_backup_files(backup_dir, 5, days_old=35)

        # Mock
        with patch.object(
            backup_engine, "_apply_retention_policy", return_value=old_files
        ):
            # Execute
            deleted_count = backup_engine._rotate_old_backups(service_name)

        # Verify
        assert deleted_count == 5
        assert isinstance(deleted_count, int)

    def test_returns_zero_when_all_deletions_fail(self, backup_engine, tmp_path):
        """Test returns zero when all deletions fail."""
        # Setup
        service_name = "test-service"
        backup_dir = tmp_path / "backups" / "homelab" / service_name
        backup_dir.mkdir(parents=True)

        old_files = create_old_backup_files(backup_dir, 3, days_old=35)

        # Mock unlink to always raise PermissionError
        with patch.object(
            backup_engine, "_apply_retention_policy", return_value=old_files
        ):
            with patch.object(
                Path, "unlink", side_effect=PermissionError("Permission denied")
            ):
                # Execute
                deleted_count = backup_engine._rotate_old_backups(service_name)

        # Verify
        assert deleted_count == 0

    def test_returns_zero_in_dry_run_mode(self, backup_engine_dry_run, tmp_path):
        """Test returns zero in dry-run mode."""
        # Setup
        service_name = "test-service"
        backup_dir = tmp_path / "backups" / "homelab" / service_name
        backup_dir.mkdir(parents=True)

        old_files = create_old_backup_files(backup_dir, 5, days_old=35)

        # Mock
        with patch.object(
            backup_engine_dry_run, "_apply_retention_policy", return_value=old_files
        ):
            # Execute
            deleted_count = backup_engine_dry_run._rotate_old_backups(service_name)

        # Verify
        assert deleted_count == 0
        # Files should still exist
        for file_path in old_files:
            assert file_path.exists()
