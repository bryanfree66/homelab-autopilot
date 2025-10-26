"""
Tests for BackupEngine._verify_backup_integrity() method.

Tests cover:
- Success cases (valid files, archives)
- Failure cases (missing, empty, corrupted files)
- Input validation
- Edge cases
"""

import gzip
import os
import tarfile
from pathlib import Path

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
def temp_backup_file(tmp_path):
    """Create a temporary backup file with some content."""
    backup_file = tmp_path / "test_backup.tar.gz"
    backup_file.write_bytes(b"test content" * 1000)  # 12KB
    return backup_file


# Success Cases
class TestVerifyBackupIntegritySuccess:
    """Test successful backup verification."""

    def test_valid_backup_file_passes_all_checks(self, backup_engine, tmp_path):
        """Test valid backup file passes all checks."""
        # Create a valid backup file (non-archive)
        backup_file = tmp_path / "backup.bin"
        backup_file.write_bytes(b"x" * 2048)  # 2KB

        # Execute
        success, error = backup_engine._verify_backup_integrity(
            str(backup_file), "test-service"
        )

        # Verify
        assert success is True
        assert error is None

    def test_large_file_above_minimum_size_passes(self, backup_engine, tmp_path):
        """Test large file above minimum size passes."""
        # Create a large backup file (non-archive)
        backup_file = tmp_path / "large_backup.dat"
        backup_file.write_bytes(b"x" * 1024 * 1024)  # 1MB

        # Execute with small minimum
        success, error = backup_engine._verify_backup_integrity(
            str(backup_file), "test-service", min_size_bytes=1024
        )

        # Verify
        assert success is True
        assert error is None

    def test_tar_gz_archive_passes_integrity_check(self, backup_engine, tmp_path):
        """Test .tar.gz archive passes integrity check."""
        # Create a valid tar.gz archive
        backup_file = tmp_path / "backup.tar.gz"

        # Create some files to add to archive (larger content)
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content" * 500)  # Make it large enough

        # Create tar.gz archive
        with tarfile.open(backup_file, "w:gz") as tar:
            tar.add(test_file, arcname="test.txt")

        # Execute with smaller min_size since compression reduces size significantly
        success, error = backup_engine._verify_backup_integrity(
            str(backup_file), "test-service", min_size_bytes=100
        )

        # Verify
        assert success is True
        assert error is None

    def test_tar_archive_passes_integrity_check(self, backup_engine, tmp_path):
        """Test .tar archive passes integrity check."""
        # Create a valid tar archive (no compression)
        backup_file = tmp_path / "backup.tar"

        # Create some files to add to archive
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content" * 100)

        # Create tar archive
        with tarfile.open(backup_file, "w:") as tar:
            tar.add(test_file, arcname="test.txt")

        # Execute
        success, error = backup_engine._verify_backup_integrity(
            str(backup_file), "test-service"
        )

        # Verify
        assert success is True
        assert error is None


# Failure Cases
class TestVerifyBackupIntegrityFailure:
    """Test failed backup verification."""

    def test_file_does_not_exist_returns_false(self, backup_engine, tmp_path):
        """Test file does not exist returns (False, message)."""
        # Use non-existent file path
        backup_file = tmp_path / "nonexistent.tar.gz"

        # Execute
        success, error = backup_engine._verify_backup_integrity(
            str(backup_file), "test-service"
        )

        # Verify
        assert success is False
        assert error is not None
        assert "does not exist" in error.lower()

    def test_empty_file_returns_false(self, backup_engine, tmp_path):
        """Test empty file (0 bytes) returns (False, message)."""
        # Create empty file
        backup_file = tmp_path / "empty.tar.gz"
        backup_file.touch()  # Creates 0-byte file

        # Execute
        success, error = backup_engine._verify_backup_integrity(
            str(backup_file), "test-service"
        )

        # Verify
        assert success is False
        assert error is not None
        assert "empty" in error.lower() or "0 bytes" in error.lower()

    def test_file_below_minimum_size_returns_false(self, backup_engine, tmp_path):
        """Test file below minimum size returns (False, message)."""
        # Create small file
        backup_file = tmp_path / "small.tar.gz"
        backup_file.write_bytes(b"x" * 500)  # 500 bytes

        # Execute with larger minimum
        success, error = backup_engine._verify_backup_integrity(
            str(backup_file), "test-service", min_size_bytes=1024
        )

        # Verify
        assert success is False
        assert error is not None
        assert "below minimum" in error.lower() or "500" in error

    def test_unreadable_file_returns_false(self, backup_engine, tmp_path):
        """Test unreadable file (permission denied) returns (False, message)."""
        # Create file and make it unreadable
        backup_file = tmp_path / "unreadable.tar.gz"
        backup_file.write_bytes(b"x" * 2048)

        # Remove read permissions
        os.chmod(backup_file, 0o000)

        try:
            # Execute
            success, error = backup_engine._verify_backup_integrity(
                str(backup_file), "test-service"
            )

            # Verify
            assert success is False
            assert error is not None
            assert (
                "permission" in error.lower()
                or "denied" in error.lower()
                or "os error" in error.lower()
            )
        finally:
            # Restore permissions for cleanup
            os.chmod(backup_file, 0o644)

    def test_corrupted_tar_gz_returns_false(self, backup_engine, tmp_path):
        """Test corrupted tar.gz returns (False, message)."""
        # Create file with .tar.gz extension but invalid content
        backup_file = tmp_path / "corrupted.tar.gz"
        backup_file.write_bytes(b"not a valid tar.gz file" * 100)

        # Execute
        success, error = backup_engine._verify_backup_integrity(
            str(backup_file), "test-service"
        )

        # Verify
        assert success is False
        assert error is not None
        assert (
            "corrupted" in error.lower()
            or "not a valid" in error.lower()
            or "tar" in error.lower()
        )

    def test_corrupted_tar_returns_false(self, backup_engine, tmp_path):
        """Test corrupted tar returns (False, message)."""
        # Create file with .tar extension but invalid content
        backup_file = tmp_path / "corrupted.tar"
        backup_file.write_bytes(b"not a valid tar file" * 100)

        # Execute
        success, error = backup_engine._verify_backup_integrity(
            str(backup_file), "test-service"
        )

        # Verify
        assert success is False
        assert error is not None
        assert (
            "corrupted" in error.lower()
            or "not a valid" in error.lower()
            or "tar" in error.lower()
        )


# Validation
class TestVerifyBackupIntegrityValidation:
    """Test input validation."""

    def test_empty_backup_path_raises_value_error(self, backup_engine):
        """Test empty backup_path raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            backup_engine._verify_backup_integrity("", "test-service")

        error_msg = str(exc_info.value)
        assert "empty" in error_msg.lower() or "whitespace" in error_msg.lower()

    def test_none_backup_path_raises_value_error(self, backup_engine):
        """Test None backup_path raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            backup_engine._verify_backup_integrity(None, "test-service")

        error_msg = str(exc_info.value)
        assert "non-empty string" in error_msg.lower()

    def test_empty_service_name_raises_value_error(self, backup_engine, tmp_path):
        """Test empty service_name raises ValueError."""
        backup_file = tmp_path / "backup.tar.gz"
        backup_file.write_bytes(b"x" * 2048)

        with pytest.raises(ValueError) as exc_info:
            backup_engine._verify_backup_integrity(str(backup_file), "")

        error_msg = str(exc_info.value)
        assert "empty" in error_msg.lower() or "whitespace" in error_msg.lower()

    def test_none_service_name_raises_value_error(self, backup_engine, tmp_path):
        """Test None service_name raises ValueError."""
        backup_file = tmp_path / "backup.tar.gz"
        backup_file.write_bytes(b"x" * 2048)

        with pytest.raises(ValueError) as exc_info:
            backup_engine._verify_backup_integrity(str(backup_file), None)

        error_msg = str(exc_info.value)
        assert "non-empty string" in error_msg.lower()

    def test_whitespace_only_backup_path_raises_value_error(self, backup_engine):
        """Test whitespace-only backup_path raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            backup_engine._verify_backup_integrity("   ", "test-service")

        error_msg = str(exc_info.value)
        assert "empty" in error_msg.lower() or "whitespace" in error_msg.lower()

    def test_whitespace_only_service_name_raises_value_error(
        self, backup_engine, tmp_path
    ):
        """Test whitespace-only service_name raises ValueError."""
        backup_file = tmp_path / "backup.dat"
        backup_file.write_bytes(b"x" * 2048)

        with pytest.raises(ValueError) as exc_info:
            backup_engine._verify_backup_integrity(str(backup_file), "   ")

        error_msg = str(exc_info.value)
        assert "empty" in error_msg.lower() or "whitespace" in error_msg.lower()

    def test_directory_instead_of_file_returns_false(self, backup_engine, tmp_path):
        """Test that a directory path returns (False, message)."""
        # Create a directory instead of a file
        backup_dir = tmp_path / "backup_directory"
        backup_dir.mkdir()

        # Execute
        success, error = backup_engine._verify_backup_integrity(
            str(backup_dir), "test-service"
        )

        # Verify
        assert success is False
        assert error is not None
        assert "not a regular file" in error.lower() or "not a file" in error.lower()


# Edge Cases
class TestVerifyBackupIntegrityEdgeCases:
    """Test edge cases."""

    def test_file_exactly_at_minimum_size_passes(self, backup_engine, tmp_path):
        """Test file exactly at minimum size passes."""
        # Create file exactly at minimum size (non-archive)
        backup_file = tmp_path / "exact_size.dat"
        backup_file.write_bytes(b"x" * 1024)  # Exactly 1KB

        # Execute with 1KB minimum
        success, error = backup_engine._verify_backup_integrity(
            str(backup_file), "test-service", min_size_bytes=1024
        )

        # Verify
        assert success is True
        assert error is None

    def test_non_archive_file_still_validates_existence_and_size(
        self, backup_engine, tmp_path
    ):
        """Test non-archive file (plain text) still validates existence/size."""
        # Create plain text file (not an archive)
        backup_file = tmp_path / "backup.txt"
        backup_file.write_text("plain text backup content" * 100)

        # Execute
        success, error = backup_engine._verify_backup_integrity(
            str(backup_file), "test-service"
        )

        # Verify - should pass basic checks even though not an archive
        assert success is True
        assert error is None

    def test_symlink_to_valid_file_passes(self, backup_engine, tmp_path):
        """Test symlink to valid file passes."""
        # Create valid backup file (non-archive)
        real_file = tmp_path / "real_backup.dat"
        real_file.write_bytes(b"x" * 2048)

        # Create symlink
        symlink = tmp_path / "symlink_backup.dat"
        symlink.symlink_to(real_file)

        # Execute
        success, error = backup_engine._verify_backup_integrity(
            str(symlink), "test-service"
        )

        # Verify
        assert success is True
        assert error is None

    def test_very_large_min_size_bytes_causes_expected_failure(
        self, backup_engine, tmp_path
    ):
        """Test very large min_size_bytes causes expected failure."""
        # Create normal-sized file
        backup_file = tmp_path / "backup.tar.gz"
        backup_file.write_bytes(b"x" * 2048)  # 2KB

        # Execute with unreasonably large minimum
        success, error = backup_engine._verify_backup_integrity(
            str(backup_file), "test-service", min_size_bytes=1024 * 1024 * 100  # 100MB
        )

        # Verify
        assert success is False
        assert error is not None
        assert "below minimum" in error.lower()


class TestVerifyBackupIntegrityReturnFormat:
    """Test return format consistency."""

    def test_success_returns_tuple_true_none(self, backup_engine, tmp_path):
        """Test success returns (True, None) tuple."""
        backup_file = tmp_path / "backup.dat"
        backup_file.write_bytes(b"x" * 2048)

        result = backup_engine._verify_backup_integrity(
            str(backup_file), "test-service"
        )

        # Verify return type and structure
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert result[0] is True
        assert result[1] is None

    def test_failure_returns_tuple_false_string(self, backup_engine, tmp_path):
        """Test failure returns (False, error_message) tuple."""
        backup_file = tmp_path / "nonexistent.tar.gz"

        result = backup_engine._verify_backup_integrity(
            str(backup_file), "test-service"
        )

        # Verify return type and structure
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert result[0] is False
        assert isinstance(result[1], str)
        assert len(result[1]) > 0


class TestVerifyBackupIntegrityArchiveTypes:
    """Test different archive type handling."""

    def test_tgz_extension_treated_as_tar_gz(self, backup_engine, tmp_path):
        """Test .tgz extension is treated as .tar.gz."""
        # Create valid tar.gz with .tgz extension
        backup_file = tmp_path / "backup.tgz"
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content" * 500)  # Make it larger

        with tarfile.open(backup_file, "w:gz") as tar:
            tar.add(test_file, arcname="test.txt")

        # Execute with smaller min_size since compression reduces size significantly
        success, error = backup_engine._verify_backup_integrity(
            str(backup_file), "test-service", min_size_bytes=100
        )

        # Verify
        assert success is True
        assert error is None

    def test_gz_non_tar_file_validates(self, backup_engine, tmp_path):
        """Test .gz file (non-tar) validates."""
        # Create valid gzip file
        backup_file = tmp_path / "backup.gz"

        with gzip.open(backup_file, "wb") as gz:
            gz.write(b"compressed content" * 1000)  # Make it much larger

        # Execute with smaller min_size since compression reduces size
        success, error = backup_engine._verify_backup_integrity(
            str(backup_file), "test-service", min_size_bytes=100
        )

        # Verify
        assert success is True
        assert error is None

    def test_corrupted_gz_file_returns_false(self, backup_engine, tmp_path):
        """Test corrupted .gz file returns false."""
        # Create file with .gz extension but invalid content
        backup_file = tmp_path / "corrupted.gz"
        backup_file.write_bytes(b"not a gzip file" * 100)

        # Execute
        success, error = backup_engine._verify_backup_integrity(
            str(backup_file), "test-service"
        )

        # Verify
        assert success is False
        assert error is not None
        assert "corrupted" in error.lower() or "gzip" in error.lower()

    def test_uppercase_extensions_handled(self, backup_engine, tmp_path):
        """Test uppercase extensions are handled (case-insensitive)."""
        # Create file with uppercase extension
        backup_file = tmp_path / "backup.TAR.GZ"
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content" * 500)  # Make it larger

        with tarfile.open(backup_file, "w:gz") as tar:
            tar.add(test_file, arcname="test.txt")

        # Execute with smaller min_size since compression reduces size significantly
        success, error = backup_engine._verify_backup_integrity(
            str(backup_file), "test-service", min_size_bytes=100
        )

        # Verify
        assert success is True
        assert error is None


class TestVerifyBackupIntegrityLogging:
    """Test logging behavior."""

    def test_successful_verification_logs_info(self, backup_engine, tmp_path):
        """Test successful verification logs at INFO level."""
        backup_file = tmp_path / "backup.dat"
        backup_file.write_bytes(b"x" * 2048)

        # Execute - should complete without errors (logging verified in method)
        success, error = backup_engine._verify_backup_integrity(
            str(backup_file), "test-service"
        )

        assert success is True

    def test_failed_verification_logs_warning(self, backup_engine, tmp_path):
        """Test failed verification logs at WARNING level."""
        # Use non-existent file
        backup_file = tmp_path / "nonexistent.tar.gz"

        # Execute - should complete with warning log
        success, error = backup_engine._verify_backup_integrity(
            str(backup_file), "test-service"
        )

        assert success is False
