"""
Tests for ProxmoxPlugin hypervisor plugin.

Covers:
- Plugin initialization and matching
- Service validation
- Cluster-aware node discovery
- Backup operations (PBS and direct storage)
- Snapshot operations (create, restore, delete)
- Status queries
- Error handling
"""

from pathlib import Path
from unittest.mock import MagicMock, Mock, call, patch

import pytest
from proxmoxer.core import ResourceException

from core.config_loader import ConfigLoader, ServiceConfig
from lib.state_manager import StateManager
from plugins.hypervisors.proxmox import ProxmoxPlugin

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def fixtures_dir():
    """Return path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def valid_config_path(fixtures_dir):
    """Return path to valid config."""
    return fixtures_dir / "valid_config.yaml"


@pytest.fixture
def state_manager(tmp_path):
    """Return StateManager with temp database."""
    db_path = tmp_path / "test_state.db"
    return StateManager(db_path)


@pytest.fixture
def config_loader(valid_config_path):
    """Return ConfigLoader instance."""
    return ConfigLoader(valid_config_path)


@pytest.fixture
def mock_api_client():
    """Return mock ProxmoxAPI client."""
    mock_api = MagicMock()

    # Mock cluster resources query
    mock_api.cluster.resources.get.return_value = [
        {"vmid": 100, "node": "pve1", "type": "qemu", "status": "running"},
        {"vmid": 101, "node": "pve2", "type": "lxc", "status": "running"},
    ]

    # Mock task status
    mock_api.nodes.return_value.tasks.return_value.status.get.return_value = {
        "status": "stopped",
        "exitstatus": "OK",
    }

    # Mock snapshot operations
    mock_api.nodes.return_value.qemu.return_value.snapshot.create.return_value = True
    mock_api.nodes.return_value.lxc.return_value.snapshot.create.return_value = True

    # Mock status query
    mock_api.nodes.return_value.qemu.return_value.status.current.get.return_value = {
        "status": "running",
        "cpu": 0.25,
        "mem": 2147483648,
        "uptime": 3600,
    }
    mock_api.nodes.return_value.lxc.return_value.status.current.get.return_value = {
        "status": "running",
        "cpu": 0.15,
        "mem": 1073741824,
        "uptime": 7200,
    }

    return mock_api


@pytest.fixture
def plugin(config_loader, state_manager):
    """Return ProxmoxPlugin instance."""
    return ProxmoxPlugin(config=config_loader, state=state_manager)


@pytest.fixture
def vm_service():
    """Return VM service config."""
    return ServiceConfig(
        name="test-vm",
        type="vm",
        vmid=100,
        node="pve1",
        backup=True,
    )


@pytest.fixture
def lxc_service():
    """Return LXC service config."""
    return ServiceConfig(
        name="test-lxc",
        type="lxc",
        vmid=101,
        node="pve2",
        backup=True,
    )


# ============================================================================
# Test: Initialization & Matching
# ============================================================================


def test_plugin_initialization(plugin, config_loader, state_manager):
    """Test that plugin initializes with config and state."""
    assert plugin.config_loader is config_loader
    assert plugin.state_manager is state_manager
    assert plugin._api_client is None  # Not initialized until first use


def test_name_property(plugin):
    """Test that name property returns correct plugin name."""
    assert plugin.name == "ProxmoxPlugin"


def test_matches_vm_type(plugin):
    """Test that matches returns True for VM type."""
    assert plugin.matches({"type": "vm"}) is True


def test_matches_lxc_type(plugin):
    """Test that matches returns True for LXC type."""
    assert plugin.matches({"type": "lxc"}) is True


def test_matches_docker_type(plugin):
    """Test that matches returns False for Docker type."""
    assert plugin.matches({"type": "docker"}) is False


def test_matches_other_type(plugin):
    """Test that matches returns False for other types."""
    assert plugin.matches({"type": "systemd"}) is False


def test_matches_service_config_object(plugin, vm_service):
    """Test that matches works with ServiceConfig object."""
    assert plugin.matches(vm_service) is True


def test_matches_case_insensitive(plugin):
    """Test that matches is case-insensitive."""
    assert plugin.matches({"type": "VM"}) is True
    assert plugin.matches({"type": "LXC"}) is True


# ============================================================================
# Test: API Client Management
# ============================================================================


def test_api_client_initialization(plugin, mock_api_client):
    """Test that API client is created and cached."""
    with patch("plugins.hypervisors.proxmox.ProxmoxAPI", return_value=mock_api_client):
        client1 = plugin._get_api_client()
        client2 = plugin._get_api_client()

        # Should return same cached instance
        assert client1 is client2
        assert client1 is mock_api_client


def test_api_client_connection_error(plugin):
    """Test that connection error is handled gracefully."""
    with patch(
        "plugins.hypervisors.proxmox.ProxmoxAPI",
        side_effect=Exception("Connection refused"),
    ):
        with pytest.raises(ConnectionError, match="Failed to connect to Proxmox API"):
            plugin._get_api_client()


# ============================================================================
# Test: Service Validation
# ============================================================================


def test_validate_service_valid_vm(plugin, vm_service):
    """Test that valid VM service passes validation."""
    plugin._validate_service(vm_service)  # Should not raise


def test_validate_service_valid_lxc(plugin, lxc_service):
    """Test that valid LXC service passes validation."""
    plugin._validate_service(lxc_service)  # Should not raise


def test_validate_service_invalid_type(plugin):
    """Test that invalid service type raises ValueError."""
    service = ServiceConfig(
        name="test",
        type="docker",
        container_name="test",
    )

    with pytest.raises(ValueError, match="ProxmoxPlugin only handles 'vm' or 'lxc'"):
        plugin._validate_service(service)


def test_validate_service_missing_vmid(plugin):
    """Test that missing vmid raises ValueError."""
    # Pydantic will catch this during model creation, but test plugin validation
    # by mocking a service with None vmid
    service = MagicMock()
    service.name = "test-vm"
    service.type = "vm"
    service.vmid = None
    service.node = "pve1"

    with pytest.raises(ValueError, match="missing required 'vmid' field"):
        plugin._validate_service(service)


def test_validate_service_missing_node(plugin):
    """Test that missing node raises ValueError."""
    # Pydantic will catch this during model creation, but test plugin validation
    # by mocking a service with None node
    service = MagicMock()
    service.name = "test-vm"
    service.type = "vm"
    service.vmid = 100
    service.node = None

    with pytest.raises(ValueError, match="missing required 'node' field"):
        plugin._validate_service(service)


def test_validate_service_invalid_vmid_type(plugin):
    """Test that non-integer vmid raises ValueError."""
    # Create service with invalid vmid (this would fail Pydantic validation,
    # but test the plugin's validation)
    service = MagicMock()
    service.name = "test-vm"
    service.type = "vm"
    service.vmid = "not-an-int"
    service.node = "pve1"

    with pytest.raises(ValueError, match="must be integer"):
        plugin._validate_service(service)


# ============================================================================
# Test: Cluster Awareness
# ============================================================================


def test_get_actual_node_found_in_cluster(plugin, vm_service, mock_api_client):
    """Test that actual node is queried from cluster."""
    with patch.object(plugin, "_get_api_client", return_value=mock_api_client):
        node = plugin._get_actual_node(vm_service)
        assert node == "pve1"

        # Verify cluster resources was queried
        mock_api_client.cluster.resources.get.assert_called_with(type="vm")


def test_get_actual_node_migrated_vm(plugin, mock_api_client):
    """Test that migrated VM location is detected."""
    # VM 100 is actually on pve2, not pve1
    mock_api_client.cluster.resources.get.return_value = [
        {"vmid": 100, "node": "pve2", "type": "qemu", "status": "running"},
    ]

    service = ServiceConfig(
        name="test-vm",
        type="vm",
        vmid=100,
        node="pve1",  # Config says pve1
        backup=True,
    )

    with patch.object(plugin, "_get_api_client", return_value=mock_api_client):
        node = plugin._get_actual_node(service)
        assert node == "pve2"  # Should return actual location


def test_get_actual_node_not_found_fallback(plugin, vm_service, mock_api_client):
    """Test fallback to configured node when VM not found."""
    # Return empty list (VM not found in cluster)
    mock_api_client.cluster.resources.get.return_value = []

    with patch.object(plugin, "_get_api_client", return_value=mock_api_client):
        node = plugin._get_actual_node(vm_service)
        assert node == "pve1"  # Falls back to config


def test_get_actual_node_lxc(plugin, lxc_service, mock_api_client):
    """Test cluster query for LXC containers."""
    with patch.object(plugin, "_get_api_client", return_value=mock_api_client):
        node = plugin._get_actual_node(lxc_service)
        assert node == "pve2"

        # Verify correct type was queried
        mock_api_client.cluster.resources.get.assert_called_with(type="lxc")


def test_get_actual_node_api_error_fallback(plugin, vm_service, mock_api_client):
    """Test fallback when cluster API fails."""
    mock_api_client.cluster.resources.get.side_effect = Exception("API error")

    with patch.object(plugin, "_get_api_client", return_value=mock_api_client):
        node = plugin._get_actual_node(vm_service)
        assert node == "pve1"  # Falls back to config


# ============================================================================
# Test: Task Polling
# ============================================================================


def test_wait_for_task_success(plugin, mock_api_client):
    """Test waiting for successful task completion."""
    mock_api_client.nodes.return_value.tasks.return_value.status.get.return_value = {
        "status": "stopped",
        "exitstatus": "OK",
    }

    with patch.object(plugin, "_get_api_client", return_value=mock_api_client):
        result = plugin._wait_for_task("pve1", "UPID:test:123")
        assert result is True


def test_wait_for_task_failure(plugin, mock_api_client):
    """Test waiting for failed task."""
    mock_api_client.nodes.return_value.tasks.return_value.status.get.return_value = {
        "status": "stopped",
        "exitstatus": "ERROR",
    }

    with patch.object(plugin, "_get_api_client", return_value=mock_api_client):
        with patch.object(plugin, "_parse_task_log", return_value="Task failed"):
            result = plugin._wait_for_task("pve1", "UPID:test:123")
            assert result is False


def test_wait_for_task_timeout(plugin, mock_api_client):
    """Test task timeout."""
    mock_api_client.nodes.return_value.tasks.return_value.status.get.return_value = {
        "status": "running",
    }

    with patch.object(plugin, "_get_api_client", return_value=mock_api_client):
        # Use very short timeout
        result = plugin._wait_for_task("pve1", "UPID:test:123", timeout=1)
        assert result is False


def test_wait_for_task_running_then_success(plugin, mock_api_client):
    """Test task that runs briefly then completes."""
    # First call: running, second call: stopped/OK
    mock_api_client.nodes.return_value.tasks.return_value.status.get.side_effect = [
        {"status": "running"},
        {"status": "stopped", "exitstatus": "OK"},
    ]

    with patch.object(plugin, "_get_api_client", return_value=mock_api_client):
        result = plugin._wait_for_task("pve1", "UPID:test:123")
        assert result is True


def test_parse_task_log_with_errors(plugin, mock_api_client):
    """Test parsing task log with error messages."""
    mock_api_client.nodes.return_value.tasks.return_value.log.get.return_value = [
        {"t": "Starting backup..."},
        {"t": "ERROR: Failed to create snapshot"},
        {"t": "ERROR: Backup failed"},
    ]

    with patch.object(plugin, "_get_api_client", return_value=mock_api_client):
        error = plugin._parse_task_log("pve1", "UPID:test:123")
        assert "ERROR" in error
        assert "snapshot" in error or "Backup failed" in error


def test_parse_task_log_no_errors(plugin, mock_api_client):
    """Test parsing task log without errors."""
    mock_api_client.nodes.return_value.tasks.return_value.log.get.return_value = [
        {"t": "Starting backup..."},
        {"t": "Backup completed successfully"},
    ]

    with patch.object(plugin, "_get_api_client", return_value=mock_api_client):
        error = plugin._parse_task_log("pve1", "UPID:test:123")
        assert error == "Backup completed successfully"


# ============================================================================
# Test: Backup - PBS
# ============================================================================


def test_backup_to_pbs_success(plugin, vm_service, mock_api_client):
    """Test successful PBS backup."""
    mock_api_client.nodes.return_value.vzdump.create.return_value = "UPID:test:123"

    with patch.object(plugin, "_get_api_client", return_value=mock_api_client):
        with patch.object(plugin, "_wait_for_task", return_value=True):
            metadata = {
                "use_pbs": True,
                "pbs_config": {"datastore": "backup-datastore"},
                "compression": "zstd",
            }

            result = plugin._backup_to_pbs(vm_service, "pve1", metadata)
            assert result is True

            # Verify vzdump was called with correct params
            mock_api_client.nodes.return_value.vzdump.create.assert_called_with(
                vmid=100,
                storage="backup-datastore",
                mode="snapshot",
                compress="zstd",
                remove=0,
            )


def test_backup_to_pbs_missing_datastore(plugin, vm_service, mock_api_client):
    """Test PBS backup with missing datastore."""
    with patch.object(plugin, "_get_api_client", return_value=mock_api_client):
        metadata = {"use_pbs": True, "pbs_config": {}}

        result = plugin._backup_to_pbs(vm_service, "pve1", metadata)
        assert result is False


def test_backup_to_pbs_task_failure(plugin, vm_service, mock_api_client):
    """Test PBS backup with task failure."""
    mock_api_client.nodes.return_value.vzdump.create.return_value = "UPID:test:123"

    with patch.object(plugin, "_get_api_client", return_value=mock_api_client):
        with patch.object(plugin, "_wait_for_task", return_value=False):
            metadata = {
                "use_pbs": True,
                "pbs_config": {"datastore": "backup-datastore"},
            }

            result = plugin._backup_to_pbs(vm_service, "pve1", metadata)
            assert result is False


def test_backup_to_pbs_api_exception(plugin, vm_service, mock_api_client):
    """Test PBS backup with API exception."""
    mock_api_client.nodes.return_value.vzdump.create.side_effect = ResourceException(
        500, "Internal Server Error", "API error"
    )

    with patch.object(plugin, "_get_api_client", return_value=mock_api_client):
        metadata = {
            "use_pbs": True,
            "pbs_config": {"datastore": "backup-datastore"},
        }

        result = plugin._backup_to_pbs(vm_service, "pve1", metadata)
        assert result is False


# ============================================================================
# Test: Backup - Direct Storage
# ============================================================================


def test_backup_to_storage_success(plugin, vm_service, mock_api_client, tmp_path):
    """Test successful direct storage backup."""
    mock_api_client.nodes.return_value.vzdump.create.return_value = "UPID:test:123"
    destination = tmp_path / "backups" / "test-vm-backup.vma.zst"

    with patch.object(plugin, "_get_api_client", return_value=mock_api_client):
        with patch.object(plugin, "_wait_for_task", return_value=True):
            result = plugin._backup_to_storage(vm_service, "pve1", destination)
            assert result is True

            # Verify vzdump was called
            mock_api_client.nodes.return_value.vzdump.create.assert_called_with(
                vmid=100,
                dumpdir=str(destination.parent),
                mode="snapshot",
                compress="zstd",
                remove=0,
            )


def test_backup_to_storage_task_failure(plugin, vm_service, mock_api_client, tmp_path):
    """Test direct storage backup with task failure."""
    mock_api_client.nodes.return_value.vzdump.create.return_value = "UPID:test:123"
    destination = tmp_path / "backups" / "test-vm-backup.vma.zst"

    with patch.object(plugin, "_get_api_client", return_value=mock_api_client):
        with patch.object(plugin, "_wait_for_task", return_value=False):
            result = plugin._backup_to_storage(vm_service, "pve1", destination)
            assert result is False


def test_backup_to_storage_api_exception(plugin, vm_service, mock_api_client, tmp_path):
    """Test direct storage backup with API exception."""
    mock_api_client.nodes.return_value.vzdump.create.side_effect = ResourceException(
        500, "Internal Server Error", "API error"
    )
    destination = tmp_path / "backups" / "test-vm-backup.vma.zst"

    with patch.object(plugin, "_get_api_client", return_value=mock_api_client):
        result = plugin._backup_to_storage(vm_service, "pve1", destination)
        assert result is False


# ============================================================================
# Test: Backup - Main Method
# ============================================================================


def test_backup_pbs_mode(plugin, vm_service, mock_api_client, tmp_path):
    """Test that backup method delegates to PBS when use_pbs is True."""
    destination = tmp_path / "backups" / "test-vm.vma"

    with patch.object(plugin, "_get_api_client", return_value=mock_api_client):
        with patch.object(plugin, "_get_actual_node", return_value="pve1"):
            with patch.object(plugin, "_backup_to_pbs", return_value=True) as mock_pbs:
                metadata = {
                    "use_pbs": True,
                    "pbs_config": {"datastore": "backup-datastore"},
                }

                result = plugin.backup(vm_service, destination, metadata)
                assert result is True
                mock_pbs.assert_called_once()


def test_backup_direct_storage_mode(plugin, vm_service, mock_api_client, tmp_path):
    """Test that backup method delegates to direct storage when use_pbs is False."""
    destination = tmp_path / "backups" / "test-vm.vma"

    with patch.object(plugin, "_get_api_client", return_value=mock_api_client):
        with patch.object(plugin, "_get_actual_node", return_value="pve1"):
            with patch.object(
                plugin, "_backup_to_storage", return_value=True
            ) as mock_storage:
                metadata = {"use_pbs": False}

                result = plugin.backup(vm_service, destination, metadata)
                assert result is True
                mock_storage.assert_called_once()


def test_backup_validation_error(plugin, tmp_path):
    """Test backup with invalid service."""
    invalid_service = ServiceConfig(
        name="test-docker",
        type="docker",
        container_name="test",
    )
    destination = tmp_path / "backups" / "test.vma"

    result = plugin.backup(invalid_service, destination)
    assert result is False


def test_backup_cluster_aware(plugin, vm_service, mock_api_client, tmp_path):
    """Test that backup queries actual node location."""
    destination = tmp_path / "backups" / "test-vm.vma"

    # VM is actually on pve2, not pve1
    mock_api_client.cluster.resources.get.return_value = [
        {"vmid": 100, "node": "pve2", "type": "qemu", "status": "running"},
    ]

    with patch.object(plugin, "_get_api_client", return_value=mock_api_client):
        with patch.object(
            plugin, "_backup_to_storage", return_value=True
        ) as mock_backup:
            result = plugin.backup(vm_service, destination)
            assert result is True

            # Verify backup was called with actual node (pve2), not config node (pve1)
            _, args, _ = mock_backup.mock_calls[0]
            assert args[1] == "pve2"


# ============================================================================
# Test: Snapshots
# ============================================================================


def test_create_snapshot_vm_success(plugin, vm_service, mock_api_client):
    """Test creating VM snapshot."""
    with patch.object(plugin, "_get_api_client", return_value=mock_api_client):
        with patch.object(plugin, "_get_actual_node", return_value="pve1"):
            result = plugin.create_snapshot(vm_service, "test-snapshot")
            assert result is True

            mock_api_client.nodes.return_value.qemu.return_value.snapshot.create.assert_called_with(
                snapname="test-snapshot",
                description="Homelab Autopilot snapshot",
            )


def test_create_snapshot_lxc_success(plugin, lxc_service, mock_api_client):
    """Test creating LXC snapshot."""
    with patch.object(plugin, "_get_api_client", return_value=mock_api_client):
        with patch.object(plugin, "_get_actual_node", return_value="pve2"):
            result = plugin.create_snapshot(lxc_service, "test-snapshot")
            assert result is True

            mock_api_client.nodes.return_value.lxc.return_value.snapshot.create.assert_called_with(
                snapname="test-snapshot",
                description="Homelab Autopilot snapshot",
            )


def test_create_snapshot_with_task(plugin, vm_service, mock_api_client):
    """Test creating snapshot that returns task UPID."""
    mock_api_client.nodes.return_value.qemu.return_value.snapshot.create.return_value = (
        "UPID:test:123"
    )

    with patch.object(plugin, "_get_api_client", return_value=mock_api_client):
        with patch.object(plugin, "_get_actual_node", return_value="pve1"):
            with patch.object(plugin, "_wait_for_task", return_value=True):
                result = plugin.create_snapshot(vm_service, "test-snapshot")
                assert result is True


def test_create_snapshot_api_error(plugin, vm_service, mock_api_client):
    """Test snapshot creation with API error."""
    mock_api_client.nodes.return_value.qemu.return_value.snapshot.create.side_effect = (
        ResourceException(500, "Internal Server Error", "API error")
    )

    with patch.object(plugin, "_get_api_client", return_value=mock_api_client):
        with patch.object(plugin, "_get_actual_node", return_value="pve1"):
            result = plugin.create_snapshot(vm_service, "test-snapshot")
            assert result is False


def test_restore_snapshot_vm_success(plugin, vm_service, mock_api_client):
    """Test restoring VM snapshot."""
    with patch.object(plugin, "_get_api_client", return_value=mock_api_client):
        with patch.object(plugin, "_get_actual_node", return_value="pve1"):
            result = plugin.restore_snapshot(vm_service, "test-snapshot")
            assert result is True


def test_restore_snapshot_lxc_success(plugin, lxc_service, mock_api_client):
    """Test restoring LXC snapshot."""
    with patch.object(plugin, "_get_api_client", return_value=mock_api_client):
        with patch.object(plugin, "_get_actual_node", return_value="pve2"):
            result = plugin.restore_snapshot(lxc_service, "test-snapshot")
            assert result is True


def test_restore_snapshot_api_error(plugin, vm_service, mock_api_client):
    """Test snapshot restore with API error."""
    mock_api_client.nodes.return_value.qemu.return_value.snapshot.return_value.rollback.post.side_effect = ResourceException(
        500, "Internal Server Error", "API error"
    )

    with patch.object(plugin, "_get_api_client", return_value=mock_api_client):
        with patch.object(plugin, "_get_actual_node", return_value="pve1"):
            result = plugin.restore_snapshot(vm_service, "test-snapshot")
            assert result is False


def test_delete_snapshot_vm_success(plugin, vm_service, mock_api_client):
    """Test deleting VM snapshot."""
    with patch.object(plugin, "_get_api_client", return_value=mock_api_client):
        with patch.object(plugin, "_get_actual_node", return_value="pve1"):
            result = plugin.delete_snapshot(vm_service, "test-snapshot")
            assert result is True


def test_delete_snapshot_lxc_success(plugin, lxc_service, mock_api_client):
    """Test deleting LXC snapshot."""
    with patch.object(plugin, "_get_api_client", return_value=mock_api_client):
        with patch.object(plugin, "_get_actual_node", return_value="pve2"):
            result = plugin.delete_snapshot(lxc_service, "test-snapshot")
            assert result is True


def test_delete_snapshot_api_error(plugin, vm_service, mock_api_client):
    """Test snapshot deletion with API error."""
    mock_api_client.nodes.return_value.qemu.return_value.snapshot.return_value.delete.side_effect = ResourceException(
        500, "Internal Server Error", "API error"
    )

    with patch.object(plugin, "_get_api_client", return_value=mock_api_client):
        with patch.object(plugin, "_get_actual_node", return_value="pve1"):
            result = plugin.delete_snapshot(vm_service, "test-snapshot")
            assert result is False


# ============================================================================
# Test: Status
# ============================================================================


def test_get_status_vm_running(plugin, vm_service, mock_api_client):
    """Test getting status of running VM."""
    with patch.object(plugin, "_get_api_client", return_value=mock_api_client):
        with patch.object(plugin, "_get_actual_node", return_value="pve1"):
            status = plugin.get_status(vm_service)

            assert status["status"] == "running"
            assert status["node"] == "pve1"
            assert status["vmid"] == 100
            assert status["type"] == "vm"
            assert status["cpu"] == 0.25
            assert status["memory"] == 2147483648
            assert status["uptime"] == 3600


def test_get_status_lxc_running(plugin, lxc_service, mock_api_client):
    """Test getting status of running LXC."""
    with patch.object(plugin, "_get_api_client", return_value=mock_api_client):
        with patch.object(plugin, "_get_actual_node", return_value="pve2"):
            status = plugin.get_status(lxc_service)

            assert status["status"] == "running"
            assert status["node"] == "pve2"
            assert status["vmid"] == 101
            assert status["type"] == "lxc"
            assert status["cpu"] == 0.15
            assert status["memory"] == 1073741824
            assert status["uptime"] == 7200


def test_get_status_stopped_vm(plugin, vm_service, mock_api_client):
    """Test getting status of stopped VM."""
    mock_api_client.nodes.return_value.qemu.return_value.status.current.get.return_value = {
        "status": "stopped",
    }

    with patch.object(plugin, "_get_api_client", return_value=mock_api_client):
        with patch.object(plugin, "_get_actual_node", return_value="pve1"):
            status = plugin.get_status(vm_service)

            assert status["status"] == "stopped"
            assert status["node"] == "pve1"
            assert status["vmid"] == 100


def test_get_status_api_error(plugin, vm_service, mock_api_client):
    """Test get_status with API error."""
    mock_api_client.nodes.return_value.qemu.return_value.status.current.get.side_effect = ResourceException(
        500, "Internal Server Error", "API error"
    )

    with patch.object(plugin, "_get_api_client", return_value=mock_api_client):
        with patch.object(plugin, "_get_actual_node", return_value="pve1"):
            status = plugin.get_status(vm_service)
            assert status == {}


def test_get_status_validation_error(plugin):
    """Test get_status with invalid service."""
    invalid_service = ServiceConfig(
        name="test-docker",
        type="docker",
        container_name="test",
    )

    status = plugin.get_status(invalid_service)
    assert status == {}


# ============================================================================
# Test: Helper Methods
# ============================================================================


def test_get_vm_type_vm(plugin, vm_service):
    """Test _get_vm_type returns 'qemu' for VMs."""
    assert plugin._get_vm_type(vm_service) == "qemu"


def test_get_vm_type_lxc(plugin, lxc_service):
    """Test _get_vm_type returns 'lxc' for containers."""
    assert plugin._get_vm_type(lxc_service) == "lxc"
