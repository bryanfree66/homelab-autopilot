"""
Tests for BackupEngine._create_backup_metadata() method.

Tests cover:
- VM with PBS backup (includes pbs_details, vmid, node)
- VM with direct storage (includes backup_path, file_size)
- LXC with local fallback
- Docker service (no vmid, no node)
- Systemd service
- With/without duration_seconds
- With/without backup_path
- backup_path doesn't exist
- backup_path exists (calculate file_size)
- Permission error handling
- Timestamp format validation
- JSON serializability
"""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

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
def vm_service():
    """Return a VM service configuration."""
    return ServiceConfig(
        name="test-vm",
        type="vm",
        vmid=200,
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
        vmid=100,
        node="pve-node2",
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


@pytest.fixture
def pbs_destination():
    """Return PBS backup destination."""
    return {
        "method": "pbs",
        "pbs_config": {
            "server": "pbs.local",
            "datastore": "homelab",
            "username": "root@pam",
            "password": "secret",
            "port": 8007,
            "verify_ssl": False,
        },
    }


@pytest.fixture
def direct_destination():
    """Return direct storage backup destination."""
    return {
        "method": "direct",
        "path": Path("/mnt/nfs/backups"),
    }


@pytest.fixture
def local_destination():
    """Return local backup destination."""
    return {
        "method": "local",
        "path": Path("/mnt/backups"),
    }


class TestCreateBackupMetadataBasicFields:
    """Test basic metadata field creation."""

    def test_vm_with_pbs_basic_fields(self, backup_engine, vm_service, pbs_destination):
        """Test VM with PBS includes all basic required fields."""
        metadata = backup_engine._create_backup_metadata(
            vm_service, pbs_destination
        )

        # Check required fields
        assert metadata["service_name"] == "test-vm"
        assert metadata["service_type"] == "vm"
        assert metadata["backup_method"] == "pbs"
        assert metadata["status"] == "pending"
        assert "timestamp" in metadata

    def test_docker_with_local_basic_fields(
        self, backup_engine, docker_service, local_destination
    ):
        """Test Docker service includes all basic required fields."""
        metadata = backup_engine._create_backup_metadata(
            docker_service, local_destination
        )

        assert metadata["service_name"] == "test-docker"
        assert metadata["service_type"] == "docker"
        assert metadata["backup_method"] == "local"
        assert metadata["status"] == "pending"

    def test_service_type_lowercase(self, backup_engine, local_destination):
        """Test that service type is normalized to lowercase."""
        service = ServiceConfig(
            name="test",
            type="VM",  # Uppercase
            vmid=100,
            node="pve",
            enabled=True,
            backup=True,
        )

        metadata = backup_engine._create_backup_metadata(service, local_destination)

        assert metadata["service_type"] == "vm"  # Should be lowercase


class TestCreateBackupMetadataTimestamp:
    """Test timestamp generation and format."""

    def test_timestamp_is_iso_format(self, backup_engine, vm_service, pbs_destination):
        """Test that timestamp is valid ISO 8601 format."""
        metadata = backup_engine._create_backup_metadata(
            vm_service, pbs_destination
        )

        timestamp = metadata["timestamp"]

        # Should be parseable as ISO datetime
        parsed = datetime.fromisoformat(timestamp)
        assert isinstance(parsed, datetime)

    def test_timestamp_is_recent(self, backup_engine, vm_service, pbs_destination):
        """Test that timestamp is current (within last few seconds)."""
        before = datetime.now()
        metadata = backup_engine._create_backup_metadata(
            vm_service, pbs_destination
        )
        after = datetime.now()

        timestamp = datetime.fromisoformat(metadata["timestamp"])

        # Timestamp should be between before and after
        assert before <= timestamp <= after

    def test_multiple_calls_have_different_timestamps(
        self, backup_engine, vm_service, pbs_destination
    ):
        """Test that multiple calls generate different timestamps."""
        metadata1 = backup_engine._create_backup_metadata(
            vm_service, pbs_destination
        )

        # Small delay
        import time
        time.sleep(0.01)

        metadata2 = backup_engine._create_backup_metadata(
            vm_service, pbs_destination
        )

        # Timestamps should be different
        assert metadata1["timestamp"] != metadata2["timestamp"]


class TestCreateBackupMetadataBackupPath:
    """Test backup_path and file_size_bytes handling."""

    def test_no_backup_path_provided(
        self, backup_engine, vm_service, pbs_destination
    ):
        """Test metadata when no backup_path is provided."""
        metadata = backup_engine._create_backup_metadata(
            vm_service, pbs_destination
        )

        assert metadata["backup_path"] is None
        assert metadata["file_size_bytes"] is None

    def test_backup_path_does_not_exist(
        self, backup_engine, vm_service, local_destination, tmp_path
    ):
        """Test metadata when backup_path doesn't exist yet."""
        nonexistent_path = tmp_path / "does_not_exist.tar.gz"

        metadata = backup_engine._create_backup_metadata(
            vm_service, local_destination, backup_path=nonexistent_path
        )

        assert metadata["backup_path"] == str(nonexistent_path)
        assert metadata["file_size_bytes"] is None

    def test_backup_path_exists_calculates_size(
        self, backup_engine, vm_service, local_destination, tmp_path
    ):
        """Test metadata calculates file size for existing backup."""
        # Create test file with known size
        test_file = tmp_path / "test_backup.tar.gz"
        test_content = b"x" * 1024  # 1 KB
        test_file.write_bytes(test_content)

        metadata = backup_engine._create_backup_metadata(
            vm_service, local_destination, backup_path=test_file
        )

        assert metadata["backup_path"] == str(test_file)
        assert metadata["file_size_bytes"] == 1024

    def test_backup_path_exists_large_file(
        self, backup_engine, vm_service, local_destination, tmp_path
    ):
        """Test metadata with larger file size."""
        test_file = tmp_path / "large_backup.tar.gz"
        test_content = b"x" * (10 * 1024 * 1024)  # 10 MB
        test_file.write_bytes(test_content)

        metadata = backup_engine._create_backup_metadata(
            vm_service, local_destination, backup_path=test_file
        )

        assert metadata["file_size_bytes"] == 10 * 1024 * 1024

    def test_backup_path_exists_empty_file(
        self, backup_engine, vm_service, local_destination, tmp_path
    ):
        """Test metadata with zero-byte file."""
        test_file = tmp_path / "empty.tar.gz"
        test_file.touch()

        metadata = backup_engine._create_backup_metadata(
            vm_service, local_destination, backup_path=test_file
        )

        assert metadata["file_size_bytes"] == 0

    def test_backup_path_permission_error(
        self, backup_engine, vm_service, local_destination, tmp_path
    ):
        """Test metadata handles permission error gracefully."""
        test_file = tmp_path / "restricted.tar.gz"
        test_file.touch()

        # Mock stat() to raise PermissionError
        with patch.object(Path, "stat", side_effect=PermissionError("Access denied")):
            metadata = backup_engine._create_backup_metadata(
                vm_service, local_destination, backup_path=test_file
            )

        # Should handle gracefully
        assert metadata["backup_path"] == str(test_file)
        assert metadata["file_size_bytes"] is None

    def test_backup_path_os_error(
        self, backup_engine, vm_service, local_destination, tmp_path
    ):
        """Test metadata handles OSError gracefully."""
        test_file = tmp_path / "error.tar.gz"
        test_file.touch()

        # Mock stat() to raise OSError
        with patch.object(Path, "stat", side_effect=OSError("I/O error")):
            metadata = backup_engine._create_backup_metadata(
                vm_service, local_destination, backup_path=test_file
            )

        # Should handle gracefully
        assert metadata["backup_path"] == str(test_file)
        assert metadata["file_size_bytes"] is None


class TestCreateBackupMetadataDuration:
    """Test duration_seconds handling."""

    def test_no_duration_provided(
        self, backup_engine, vm_service, pbs_destination
    ):
        """Test metadata when no duration is provided."""
        metadata = backup_engine._create_backup_metadata(
            vm_service, pbs_destination
        )

        assert metadata["duration_seconds"] is None

    def test_duration_provided(
        self, backup_engine, vm_service, pbs_destination
    ):
        """Test metadata includes duration when provided."""
        metadata = backup_engine._create_backup_metadata(
            vm_service, pbs_destination, duration_seconds=45.2
        )

        assert metadata["duration_seconds"] == 45.2

    def test_duration_zero(
        self, backup_engine, vm_service, pbs_destination
    ):
        """Test metadata with zero duration."""
        metadata = backup_engine._create_backup_metadata(
            vm_service, pbs_destination, duration_seconds=0.0
        )

        assert metadata["duration_seconds"] == 0.0

    def test_duration_very_large(
        self, backup_engine, vm_service, pbs_destination
    ):
        """Test metadata with very large duration."""
        metadata = backup_engine._create_backup_metadata(
            vm_service, pbs_destination, duration_seconds=3600.5
        )

        assert metadata["duration_seconds"] == 3600.5


class TestCreateBackupMetadataVmLxcFields:
    """Test VM/LXC specific fields (vmid, node)."""

    def test_vm_includes_vmid_and_node(
        self, backup_engine, vm_service, pbs_destination
    ):
        """Test VM metadata includes vmid and node."""
        metadata = backup_engine._create_backup_metadata(
            vm_service, pbs_destination
        )

        assert metadata["vmid"] == 200
        assert metadata["node"] == "pve"

    def test_lxc_includes_vmid_and_node(
        self, backup_engine, lxc_service, local_destination
    ):
        """Test LXC metadata includes vmid and node."""
        metadata = backup_engine._create_backup_metadata(
            lxc_service, local_destination
        )

        assert metadata["vmid"] == 100
        assert metadata["node"] == "pve-node2"

    def test_vm_without_vmid_graceful_handling(
        self, backup_engine, pbs_destination
    ):
        """Test VM with vmid=None (edge case, should handle gracefully)."""
        # Create service with vmid set to None (bypassing validation for test)
        service = ServiceConfig(
            name="test-vm-no-vmid",
            type="vm",
            vmid=100,  # Required by validation
            node="pve",
            enabled=True,
            backup=True,
        )
        # Manually set vmid to None to test graceful handling
        service.vmid = None

        metadata = backup_engine._create_backup_metadata(
            service, pbs_destination
        )

        assert metadata["vmid"] is None
        assert metadata["node"] == "pve"

    def test_vm_without_node_graceful_handling(
        self, backup_engine, pbs_destination
    ):
        """Test VM with node=None (edge case, should handle gracefully)."""
        # Create service with node set to None (bypassing validation for test)
        service = ServiceConfig(
            name="test-vm-no-node",
            type="vm",
            vmid=300,
            node="pve",  # Required by validation
            enabled=True,
            backup=True,
        )
        # Manually set node to None to test graceful handling
        service.node = None

        metadata = backup_engine._create_backup_metadata(
            service, pbs_destination
        )

        assert metadata["vmid"] == 300
        assert metadata["node"] is None

    def test_docker_no_vmid_or_node(
        self, backup_engine, docker_service, local_destination
    ):
        """Test Docker service has no vmid or node."""
        metadata = backup_engine._create_backup_metadata(
            docker_service, local_destination
        )

        assert metadata["vmid"] is None
        assert metadata["node"] is None

    def test_systemd_no_vmid_or_node(
        self, backup_engine, systemd_service, local_destination
    ):
        """Test systemd service has no vmid or node."""
        metadata = backup_engine._create_backup_metadata(
            systemd_service, local_destination
        )

        assert metadata["vmid"] is None
        assert metadata["node"] is None


class TestCreateBackupMetadataPbsDetails:
    """Test PBS-specific details."""

    def test_pbs_includes_pbs_details(
        self, backup_engine, vm_service, pbs_destination
    ):
        """Test PBS backup includes pbs_details."""
        metadata = backup_engine._create_backup_metadata(
            vm_service, pbs_destination
        )

        assert metadata["pbs_details"] is not None
        assert metadata["pbs_details"]["server"] == "pbs.local"
        assert metadata["pbs_details"]["datastore"] == "homelab"
        assert metadata["pbs_details"]["username"] == "root@pam"

    def test_pbs_details_no_password(
        self, backup_engine, vm_service, pbs_destination
    ):
        """Test PBS details don't include password for security."""
        metadata = backup_engine._create_backup_metadata(
            vm_service, pbs_destination
        )

        # Password should NOT be in metadata
        assert "password" not in metadata["pbs_details"]

    def test_direct_storage_no_pbs_details(
        self, backup_engine, vm_service, direct_destination
    ):
        """Test direct storage backup has no pbs_details."""
        metadata = backup_engine._create_backup_metadata(
            vm_service, direct_destination
        )

        assert metadata["pbs_details"] is None

    def test_local_backup_no_pbs_details(
        self, backup_engine, vm_service, local_destination
    ):
        """Test local backup has no pbs_details."""
        metadata = backup_engine._create_backup_metadata(
            vm_service, local_destination
        )

        assert metadata["pbs_details"] is None

    def test_pbs_details_structure(
        self, backup_engine, vm_service, pbs_destination
    ):
        """Test PBS details has correct structure."""
        metadata = backup_engine._create_backup_metadata(
            vm_service, pbs_destination
        )

        pbs_details = metadata["pbs_details"]
        assert isinstance(pbs_details, dict)
        assert "server" in pbs_details
        assert "datastore" in pbs_details
        assert "username" in pbs_details


class TestCreateBackupMetadataStatus:
    """Test status field."""

    def test_status_is_pending(
        self, backup_engine, vm_service, pbs_destination
    ):
        """Test initial status is 'pending'."""
        metadata = backup_engine._create_backup_metadata(
            vm_service, pbs_destination
        )

        assert metadata["status"] == "pending"

    def test_status_always_pending_regardless_of_method(
        self, backup_engine, vm_service, pbs_destination, direct_destination, local_destination
    ):
        """Test status is always 'pending' regardless of backup method."""
        metadata_pbs = backup_engine._create_backup_metadata(
            vm_service, pbs_destination
        )
        metadata_direct = backup_engine._create_backup_metadata(
            vm_service, direct_destination
        )
        metadata_local = backup_engine._create_backup_metadata(
            vm_service, local_destination
        )

        assert metadata_pbs["status"] == "pending"
        assert metadata_direct["status"] == "pending"
        assert metadata_local["status"] == "pending"


class TestCreateBackupMetadataJsonSerializable:
    """Test that metadata is JSON-serializable."""

    def test_metadata_is_json_serializable_pbs(
        self, backup_engine, vm_service, pbs_destination
    ):
        """Test PBS metadata can be serialized to JSON."""
        metadata = backup_engine._create_backup_metadata(
            vm_service, pbs_destination
        )

        # Should not raise
        json_str = json.dumps(metadata)
        assert isinstance(json_str, str)

        # Should be deserializable
        loaded = json.loads(json_str)
        assert loaded["service_name"] == "test-vm"

    def test_metadata_is_json_serializable_direct(
        self, backup_engine, vm_service, direct_destination, tmp_path
    ):
        """Test direct storage metadata can be serialized to JSON."""
        test_file = tmp_path / "backup.tar.gz"
        test_file.write_bytes(b"test")

        metadata = backup_engine._create_backup_metadata(
            vm_service, direct_destination, backup_path=test_file
        )

        # Should not raise
        json_str = json.dumps(metadata)
        loaded = json.loads(json_str)
        assert loaded["backup_path"] == str(test_file)

    def test_metadata_is_json_serializable_with_all_fields(
        self, backup_engine, vm_service, pbs_destination, tmp_path
    ):
        """Test fully populated metadata can be serialized to JSON."""
        test_file = tmp_path / "backup.tar.gz"
        test_file.write_bytes(b"x" * 1024)

        metadata = backup_engine._create_backup_metadata(
            vm_service,
            pbs_destination,
            backup_path=test_file,
            duration_seconds=123.45,
        )

        # Should not raise
        json_str = json.dumps(metadata)
        loaded = json.loads(json_str)

        # Verify all fields present
        assert "service_name" in loaded
        assert "backup_method" in loaded
        assert "timestamp" in loaded
        assert "backup_path" in loaded
        assert "file_size_bytes" in loaded
        assert "duration_seconds" in loaded
        assert "vmid" in loaded
        assert "node" in loaded
        assert "pbs_details" in loaded
        assert "status" in loaded


class TestCreateBackupMetadataIntegration:
    """Integration tests with various service types and destinations."""

    def test_vm_with_pbs_full_metadata(
        self, backup_engine, vm_service, pbs_destination
    ):
        """Test complete VM with PBS metadata."""
        metadata = backup_engine._create_backup_metadata(
            vm_service,
            pbs_destination,
            duration_seconds=67.8,
        )

        # All expected fields should be present
        expected_fields = [
            "service_name", "service_type", "backup_method", "timestamp",
            "backup_path", "file_size_bytes", "duration_seconds",
            "vmid", "node", "pbs_details", "status"
        ]
        for field in expected_fields:
            assert field in metadata

        # Verify values
        assert metadata["service_name"] == "test-vm"
        assert metadata["service_type"] == "vm"
        assert metadata["backup_method"] == "pbs"
        assert metadata["vmid"] == 200
        assert metadata["node"] == "pve"
        assert metadata["duration_seconds"] == 67.8
        assert metadata["pbs_details"] is not None

    def test_lxc_with_direct_storage_full_metadata(
        self, backup_engine, lxc_service, direct_destination, tmp_path
    ):
        """Test complete LXC with direct storage metadata."""
        backup_file = tmp_path / "lxc-backup.tar"
        backup_file.write_bytes(b"x" * 2048)

        metadata = backup_engine._create_backup_metadata(
            lxc_service,
            direct_destination,
            backup_path=backup_file,
            duration_seconds=30.5,
        )

        assert metadata["service_name"] == "test-lxc"
        assert metadata["service_type"] == "lxc"
        assert metadata["backup_method"] == "direct"
        assert metadata["vmid"] == 100
        assert metadata["node"] == "pve-node2"
        assert metadata["backup_path"] == str(backup_file)
        assert metadata["file_size_bytes"] == 2048
        assert metadata["duration_seconds"] == 30.5
        assert metadata["pbs_details"] is None

    def test_docker_with_local_minimal_metadata(
        self, backup_engine, docker_service, local_destination
    ):
        """Test Docker with local backup minimal metadata."""
        metadata = backup_engine._create_backup_metadata(
            docker_service,
            local_destination,
        )

        assert metadata["service_name"] == "test-docker"
        assert metadata["service_type"] == "docker"
        assert metadata["backup_method"] == "local"
        assert metadata["vmid"] is None
        assert metadata["node"] is None
        assert metadata["backup_path"] is None
        assert metadata["file_size_bytes"] is None
        assert metadata["duration_seconds"] is None
        assert metadata["pbs_details"] is None

    def test_systemd_with_local_and_path(
        self, backup_engine, systemd_service, local_destination, tmp_path
    ):
        """Test systemd service with local backup and path."""
        backup_file = tmp_path / "nginx-config.tar.gz"
        backup_file.write_bytes(b"config" * 100)

        metadata = backup_engine._create_backup_metadata(
            systemd_service,
            local_destination,
            backup_path=backup_file,
        )

        assert metadata["service_name"] == "test-systemd"
        assert metadata["service_type"] == "systemd"
        assert metadata["backup_method"] == "local"
        assert metadata["backup_path"] == str(backup_file)
        assert metadata["file_size_bytes"] == 600
        assert metadata["vmid"] is None
        assert metadata["node"] is None


class TestCreateBackupMetadataEdgeCases:
    """Test edge cases and unusual scenarios."""

    def test_generic_service_type(self, backup_engine, local_destination):
        """Test generic service type."""
        service = ServiceConfig(
            name="generic-service",
            type="generic",
            enabled=True,
            backup=True,
        )

        metadata = backup_engine._create_backup_metadata(
            service, local_destination
        )

        assert metadata["service_type"] == "generic"
        assert metadata["vmid"] is None
        assert metadata["node"] is None

    def test_host_service_type(self, backup_engine, local_destination):
        """Test host service type."""
        service = ServiceConfig(
            name="proxmox-host-config",
            type="host",
            enabled=True,
            backup=True,
        )

        metadata = backup_engine._create_backup_metadata(
            service, local_destination
        )

        assert metadata["service_type"] == "host"
        assert metadata["vmid"] is None
        assert metadata["node"] is None

    def test_service_name_with_special_characters(
        self, backup_engine, pbs_destination
    ):
        """Test service name with special characters."""
        service = ServiceConfig(
            name="my-service_v2.0",
            type="docker",
            container_name="my-service-v2",
            enabled=True,
            backup=True,
        )

        metadata = backup_engine._create_backup_metadata(
            service, pbs_destination
        )

        assert metadata["service_name"] == "my-service_v2.0"

    def test_empty_pbs_config(self, backup_engine, vm_service):
        """Test handling of empty PBS config dict."""
        destination = {
            "method": "pbs",
            "pbs_config": {},
        }

        metadata = backup_engine._create_backup_metadata(
            vm_service, destination
        )

        assert metadata["pbs_details"] is not None
        assert metadata["pbs_details"]["server"] is None
        assert metadata["pbs_details"]["datastore"] is None
        assert metadata["pbs_details"]["username"] is None

    def test_missing_pbs_config_key(self, backup_engine, vm_service):
        """Test handling when pbs_config key is missing."""
        destination = {
            "method": "pbs",
            # Missing pbs_config key
        }

        metadata = backup_engine._create_backup_metadata(
            vm_service, destination
        )

        # Should handle gracefully with empty dict
        assert metadata["pbs_details"] is not None
        assert metadata["pbs_details"]["server"] is None
