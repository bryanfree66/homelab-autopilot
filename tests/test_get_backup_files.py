"""
Tests for BackupEngine._get_backup_files() method.

Tests cover:
- Empty directory handling
- Single and multiple files
- Sorting by modification time
- File vs directory filtering
- Error handling
- Integration with _get_backup_directory
"""

import time
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


class TestGetBackupFiles:
    """Test BackupEngine._get_backup_files() method."""

    def test_empty_directory_returns_empty_list(self, backup_engine_temp):
        """Test that empty directory returns empty list."""
        engine, backup_root = backup_engine_temp

        # Create directory but no files
        backup_dir = engine._get_backup_directory("nextcloud")

        files = engine._get_backup_files("nextcloud")

        assert files == []
        assert isinstance(files, list)

    def test_returns_list_of_paths(self, backup_engine_temp):
        """Test that method returns list of Path objects."""
        engine, backup_root = backup_engine_temp

        # Create a backup file
        backup_dir = engine._get_backup_directory("nextcloud")
        test_file = backup_dir / "nextcloud_20250124_120000_vm.tar.gz"
        test_file.touch()

        files = engine._get_backup_files("nextcloud")

        assert isinstance(files, list)
        assert len(files) == 1
        assert isinstance(files[0], Path)

    def test_single_file_returned(self, backup_engine_temp):
        """Test that single file is returned correctly."""
        engine, backup_root = backup_engine_temp

        backup_dir = engine._get_backup_directory("nextcloud")
        test_file = backup_dir / "nextcloud_20250124_120000_vm.tar.gz"
        test_file.touch()

        files = engine._get_backup_files("nextcloud")

        assert len(files) == 1
        assert files[0] == test_file

    def test_multiple_files_returned(self, backup_engine_temp):
        """Test that multiple files are returned."""
        engine, backup_root = backup_engine_temp

        backup_dir = engine._get_backup_directory("nextcloud")

        # Create multiple backup files
        file1 = backup_dir / "nextcloud_20250120_120000_vm.tar.gz"
        file2 = backup_dir / "nextcloud_20250121_120000_vm.tar.gz"
        file3 = backup_dir / "nextcloud_20250122_120000_vm.tar.gz"

        file1.touch()
        file2.touch()
        file3.touch()

        files = engine._get_backup_files("nextcloud")

        assert len(files) == 3
        assert file1 in files
        assert file2 in files
        assert file3 in files

    def test_files_sorted_by_age_oldest_first(self, backup_engine_temp):
        """Test that files are sorted by modification time (oldest first)."""
        engine, backup_root = backup_engine_temp

        backup_dir = engine._get_backup_directory("nextcloud")

        # Create files with delays to ensure different mtimes
        oldest = backup_dir / "oldest.tar.gz"
        oldest.touch()
        time.sleep(0.01)

        middle = backup_dir / "middle.tar.gz"
        middle.touch()
        time.sleep(0.01)

        newest = backup_dir / "newest.tar.gz"
        newest.touch()

        files = engine._get_backup_files("nextcloud")

        # Should be sorted oldest to newest
        assert files[0] == oldest
        assert files[1] == middle
        assert files[2] == newest

    def test_ignores_subdirectories(self, backup_engine_temp):
        """Test that subdirectories are not included in results."""
        engine, backup_root = backup_engine_temp

        backup_dir = engine._get_backup_directory("nextcloud")

        # Create a file and a subdirectory
        backup_file = backup_dir / "backup.tar.gz"
        backup_file.touch()

        subdir = backup_dir / "subdir"
        subdir.mkdir()

        files = engine._get_backup_files("nextcloud")

        # Should only return the file, not the directory
        assert len(files) == 1
        assert files[0] == backup_file

    def test_nonexistent_service_returns_empty_list(self, backup_engine_temp):
        """Test that nonexistent service directory returns empty list."""
        engine, backup_root = backup_engine_temp

        # Don't create directory for this service
        files = engine._get_backup_files("nonexistent")

        # Should return empty list (directory created by _get_backup_directory)
        assert files == []

    def test_different_services_isolated(self, backup_engine_temp):
        """Test that different services have separate file lists."""
        engine, backup_root = backup_engine_temp

        # Create backups for nextcloud
        nextcloud_dir = engine._get_backup_directory("nextcloud")
        nextcloud_file = nextcloud_dir / "nextcloud_backup.tar.gz"
        nextcloud_file.touch()

        # Create backups for plex
        plex_dir = engine._get_backup_directory("plex")
        plex_file = plex_dir / "plex_backup.tar.gz"
        plex_file.touch()

        # Get files for each service
        nextcloud_files = engine._get_backup_files("nextcloud")
        plex_files = engine._get_backup_files("plex")

        # Each should only see their own files
        assert len(nextcloud_files) == 1
        assert len(plex_files) == 1
        assert nextcloud_files[0] == nextcloud_file
        assert plex_files[0] == plex_file

    def test_various_file_extensions(self, backup_engine_temp):
        """Test that files with various extensions are returned."""
        engine, backup_root = backup_engine_temp

        backup_dir = engine._get_backup_directory("test")

        # Create files with different extensions
        file1 = backup_dir / "backup.tar.gz"
        file2 = backup_dir / "backup.vma.gz"
        file3 = backup_dir / "backup.zip"
        file4 = backup_dir / "backup.backup"

        file1.touch()
        file2.touch()
        file3.touch()
        file4.touch()

        files = engine._get_backup_files("test")

        assert len(files) == 4
        assert file1 in files
        assert file2 in files
        assert file3 in files
        assert file4 in files

    def test_hidden_files_returned(self, backup_engine_temp):
        """Test that hidden files (starting with .) are returned."""
        engine, backup_root = backup_engine_temp

        backup_dir = engine._get_backup_directory("test")

        visible_file = backup_dir / "backup.tar.gz"
        hidden_file = backup_dir / ".hidden_backup.tar.gz"

        visible_file.touch()
        hidden_file.touch()

        files = engine._get_backup_files("test")

        # Both should be returned
        assert len(files) == 2
        assert visible_file in files
        assert hidden_file in files

    def test_symlinks_handled(self, backup_engine_temp):
        """Test that symlinks are handled appropriately."""
        engine, backup_root = backup_engine_temp

        backup_dir = engine._get_backup_directory("test")

        # Create a real file
        real_file = backup_dir / "backup.tar.gz"
        real_file.touch()

        # Create a symlink to it
        symlink = backup_dir / "latest.tar.gz"
        symlink.symlink_to(real_file)

        files = engine._get_backup_files("test")

        # Should include both (symlinks are files)
        assert len(files) == 2
        assert real_file in files
        assert symlink in files

    def test_empty_filename_filter(self, backup_engine_temp):
        """Test that files with no extension are still returned."""
        engine, backup_root = backup_engine_temp

        backup_dir = engine._get_backup_directory("test")

        # Create file with no extension
        no_ext = backup_dir / "backup_file"
        no_ext.touch()

        files = engine._get_backup_files("test")

        assert len(files) == 1
        assert files[0] == no_ext

    def test_integration_with_get_backup_directory(self, backup_engine_temp):
        """Test that method correctly uses _get_backup_directory."""
        engine, backup_root = backup_engine_temp

        service_name = "integration_test"

        # Create a file
        backup_dir = engine._get_backup_directory(service_name)
        test_file = backup_dir / "test.tar.gz"
        test_file.touch()

        # Get files should find it
        files = engine._get_backup_files(service_name)

        assert len(files) == 1
        # File should be in the directory from _get_backup_directory
        assert files[0].parent == backup_dir

    def test_dry_run_mode_same_behavior(self, temp_backup_config, tmp_path):
        """Test that dry_run mode doesn't affect file listing."""
        config_file, backup_root = temp_backup_config
        config = ConfigLoader(config_file)
        db_path = tmp_path / "test_state.db"
        state = StateManager(db_path)
        engine = BackupEngine(config, state, dry_run=True)

        # Create files
        backup_dir = engine._get_backup_directory("test")
        test_file = backup_dir / "test.tar.gz"
        test_file.touch()

        files = engine._get_backup_files("test")

        # Should work normally in dry run
        assert len(files) == 1
        assert files[0] == test_file

    def test_sorting_with_same_mtime(self, backup_engine_temp):
        """Test behavior when files have same modification time."""
        engine, backup_root = backup_engine_temp

        backup_dir = engine._get_backup_directory("test")

        # Create files rapidly (may have same mtime on some systems)
        file1 = backup_dir / "a.tar.gz"
        file2 = backup_dir / "b.tar.gz"
        file3 = backup_dir / "c.tar.gz"

        file1.touch()
        file2.touch()
        file3.touch()

        files = engine._get_backup_files("test")

        # Should return all files (order may vary if mtimes identical)
        assert len(files) == 3
        assert file1 in files
        assert file2 in files
        assert file3 in files

    def test_large_number_of_files(self, backup_engine_temp):
        """Test handling of directory with many files."""
        engine, backup_root = backup_engine_temp

        backup_dir = engine._get_backup_directory("test")

        # Create 50 files
        for i in range(50):
            test_file = backup_dir / f"backup_{i:03d}.tar.gz"
            test_file.touch()
            # Small delay to ensure different mtimes
            if i % 10 == 0:
                time.sleep(0.01)

        files = engine._get_backup_files("test")

        assert len(files) == 50

    def test_files_are_absolute_paths(self, backup_engine_temp):
        """Test that returned paths are absolute."""
        engine, backup_root = backup_engine_temp

        backup_dir = engine._get_backup_directory("test")
        test_file = backup_dir / "test.tar.gz"
        test_file.touch()

        files = engine._get_backup_files("test")

        assert files[0].is_absolute()

    def test_permission_error_returns_empty_list(
        self, backup_engine_temp, monkeypatch
    ):
        """Test that permission errors return empty list."""
        engine, backup_root = backup_engine_temp

        # Create directory and file
        backup_dir = engine._get_backup_directory("test")
        test_file = backup_dir / "test.tar.gz"
        test_file.touch()

        # Mock iterdir to raise permission error
        def mock_iterdir(*args):
            raise OSError("Permission denied")

        monkeypatch.setattr(Path, "iterdir", mock_iterdir)

        files = engine._get_backup_files("test")

        # Should return empty list on error
        assert files == []

    def test_returns_newest_last(self, backup_engine_temp):
        """Test that newest file is last in list."""
        engine, backup_root = backup_engine_temp

        backup_dir = engine._get_backup_directory("test")

        # Create files with clear time separation
        old_file = backup_dir / "old.tar.gz"
        old_file.touch()
        time.sleep(0.02)

        new_file = backup_dir / "new.tar.gz"
        new_file.touch()

        files = engine._get_backup_files("test")

        # Oldest first, newest last
        assert files[0] == old_file
        assert files[-1] == new_file
