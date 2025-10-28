"""
Tests for GenericServicePlugin service plugin.

Covers:
- Plugin initialization and matching
- Docker client management
- Docker backups (containers, volumes, compose)
- Systemd backups
- Generic file backups
- Update operations
- Validation
- Status queries
- Error handling
"""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, Mock, call, mock_open, patch

import pytest
import requests

from core.config_loader import ConfigLoader, ServiceConfig
from lib.state_manager import StateManager
from plugins.services.generic import GenericServicePlugin

# ============================================================================
# Fixtures
# ============================================================================


class MockService:
    """Mock service for testing with custom attributes."""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __getattr__(self, name):
        # Return None for undefined attributes instead of raising
        return None


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
def plugin(config_loader, state_manager):
    """Return GenericServicePlugin instance."""
    return GenericServicePlugin(config=config_loader, state=state_manager)


@pytest.fixture
def mock_docker_client():
    """Return mock Docker client."""
    mock_client = MagicMock()
    mock_client.ping.return_value = True

    # Mock container
    mock_container = MagicMock()
    mock_container.status = "running"
    mock_container.image.tags = ["nginx:latest"]
    mock_container.image.id = "sha256:abc123"
    mock_container.attrs = {
        "Created": "2024-01-01T00:00:00Z",
        "Mounts": [
            {"Type": "volume", "Name": "data-vol", "Destination": "/data"},
            {"Type": "bind", "Source": "/host/path", "Destination": "/app"},
        ],
        "Config": {
            "Env": ["FOO=bar"],
            "Labels": {"app": "test"},
            "Cmd": ["nginx"],
            "Entrypoint": ["/entrypoint.sh"],
        },
        "NetworkSettings": {"Ports": {"80/tcp": [{"HostPort": "8080"}]}},
        "State": {"Health": {"Status": "healthy"}},
    }
    mock_client.containers.get.return_value = mock_container

    # Mock volume operations
    mock_client.containers.run.return_value = b"tar data"

    # Mock image operations
    mock_image = MagicMock()
    mock_client.images.pull.return_value = mock_image

    return mock_client


@pytest.fixture
def docker_service():
    """Return Docker service config."""
    return ServiceConfig(
        name="test-docker",
        type="docker",
        container_name="test-container",
        compose_file="/opt/test/docker-compose.yml",
        backup=True,
    )


@pytest.fixture
def systemd_service():
    """Return systemd service config."""
    return MockService(
        name="test-systemd",
        type="systemd",
        backup=True,
        service_name="test-systemd",
        config_paths=["/etc/test/config"],
        data_paths=["/var/lib/test/data"],
        package_name=None,
    )


@pytest.fixture
def generic_service():
    """Return generic service config."""
    return MockService(
        name="test-generic",
        type="generic",
        backup=True,
        backup_paths=["/etc/important", "/var/data"],
    )


# ============================================================================
# Test: Initialization & Matching
# ============================================================================


def test_plugin_initialization(plugin, config_loader, state_manager):
    """Test that plugin initializes with config and state."""
    assert plugin.config_loader is config_loader
    assert plugin.state_manager is state_manager
    assert plugin._docker_client is None


def test_name_property(plugin):
    """Test that name property returns correct plugin name."""
    assert plugin.name == "GenericServicePlugin"


def test_matches_docker_type(plugin):
    """Test that matches returns True for Docker type."""
    assert plugin.matches({"type": "docker"}) is True


def test_matches_systemd_type(plugin):
    """Test that matches returns True for systemd type."""
    assert plugin.matches({"type": "systemd"}) is True


def test_matches_generic_type(plugin):
    """Test that matches returns True for generic type."""
    assert plugin.matches({"type": "generic"}) is True


def test_matches_vm_type(plugin):
    """Test that matches returns False for VM type."""
    assert plugin.matches({"type": "vm"}) is False


def test_matches_service_config_object(plugin, docker_service):
    """Test that matches works with ServiceConfig object."""
    assert plugin.matches(docker_service) is True


def test_matches_case_insensitive(plugin):
    """Test that matches is case-insensitive."""
    assert plugin.matches({"type": "DOCKER"}) is True
    assert plugin.matches({"type": "Systemd"}) is True


# ============================================================================
# Test: Docker Client Management
# ============================================================================


def test_docker_client_initialization(plugin, mock_docker_client):
    """Test that Docker client is created and cached."""
    with patch(
        "plugins.services.generic.docker.from_env", return_value=mock_docker_client
    ):
        client1 = plugin._get_docker_client()
        client2 = plugin._get_docker_client()

        # Should return same cached instance
        assert client1 is client2
        assert client1 is mock_docker_client
        mock_docker_client.ping.assert_called_once()


def test_docker_client_connection_error(plugin):
    """Test that Docker connection error is handled."""
    with patch(
        "plugins.services.generic.docker.from_env",
        side_effect=Exception("Connection refused"),
    ):
        with pytest.raises(ConnectionError):
            plugin._get_docker_client()


# ============================================================================
# Test: Docker Backups
# ============================================================================


def test_get_docker_volumes(plugin, mock_docker_client):
    """Test getting Docker volumes from container."""
    with patch.object(plugin, "_get_docker_client", return_value=mock_docker_client):
        volumes = plugin._get_docker_volumes("test-container")

        assert len(volumes) == 1  # Only named volume, not bind mount
        assert volumes[0]["name"] == "data-vol"
        assert volumes[0]["mount"] == "/data"


def test_get_docker_volumes_container_not_found(plugin, mock_docker_client):
    """Test getting volumes when container not found."""
    import docker

    mock_docker_client.containers.get.side_effect = docker.errors.NotFound("Not found")

    with patch.object(plugin, "_get_docker_client", return_value=mock_docker_client):
        volumes = plugin._get_docker_volumes("nonexistent")
        assert volumes == []


def test_backup_docker_volume(plugin, mock_docker_client, tmp_path):
    """Test backing up a Docker volume."""
    with patch.object(plugin, "_get_docker_client", return_value=mock_docker_client):
        result = plugin._backup_docker_volume("data-vol", tmp_path)

        assert result is True
        assert (tmp_path / "data-vol.tar.gz").exists()


def test_backup_docker_service_success(
    plugin, docker_service, mock_docker_client, tmp_path
):
    """Test successful Docker service backup."""
    destination = tmp_path / "backup.tar.gz"

    # Mock compose file exists
    with patch("pathlib.Path.exists", return_value=True):
        with patch("shutil.copy2"):
            with patch.object(
                plugin, "_get_docker_client", return_value=mock_docker_client
            ):
                with patch.object(plugin, "_get_docker_volumes", return_value=[]):
                    with patch.object(plugin, "_create_tar_archive", return_value=True):
                        result = plugin._backup_docker_service(
                            docker_service, destination
                        )

                        assert result is True


def test_backup_docker_service_container_not_found(
    plugin, docker_service, mock_docker_client, tmp_path
):
    """Test Docker backup when container not found."""
    import docker

    mock_docker_client.containers.get.side_effect = docker.errors.NotFound("Not found")
    destination = tmp_path / "backup.tar.gz"

    with patch.object(plugin, "_get_docker_client", return_value=mock_docker_client):
        result = plugin._backup_docker_service(docker_service, destination)
        assert result is False


def test_backup_docker_service_with_volumes(
    plugin, docker_service, mock_docker_client, tmp_path
):
    """Test Docker backup includes volumes."""
    destination = tmp_path / "backup.tar.gz"
    volumes = [{"name": "vol1", "mount": "/data"}]

    with patch("pathlib.Path.exists", return_value=False):
        with patch.object(
            plugin, "_get_docker_client", return_value=mock_docker_client
        ):
            with patch.object(plugin, "_get_docker_volumes", return_value=volumes):
                with patch.object(plugin, "_backup_docker_volume", return_value=True):
                    with patch.object(plugin, "_create_tar_archive", return_value=True):
                        result = plugin._backup_docker_service(
                            docker_service, destination
                        )

                        assert result is True


# ============================================================================
# Test: Systemd Backups
# ============================================================================


def test_backup_systemd_service_success(plugin, systemd_service, tmp_path):
    """Test successful systemd service backup."""
    destination = tmp_path / "backup.tar.gz"

    # Create mock service file
    service_file = tmp_path / "test-systemd.service"
    service_file.write_text("[Unit]\nDescription=Test")

    with patch("pathlib.Path.exists", return_value=True):
        with patch("shutil.copy2"):
            with patch("shutil.copytree"):
                with patch.object(plugin, "_create_tar_archive", return_value=True):
                    result = plugin._backup_systemd_service(
                        systemd_service, destination
                    )
                    assert result is True


def test_backup_systemd_service_permission_error(plugin, systemd_service, tmp_path):
    """Test systemd backup with permission error."""
    destination = tmp_path / "backup.tar.gz"

    with patch("pathlib.Path.exists", return_value=True):
        with patch("shutil.copy2", side_effect=PermissionError("Access denied")):
            result = plugin._backup_systemd_service(systemd_service, destination)
            assert result is False


# ============================================================================
# Test: Generic File Backups
# ============================================================================


def test_backup_generic_files_success(plugin, generic_service, tmp_path):
    """Test successful generic file backup."""
    destination = tmp_path / "backup.tar.gz"

    with patch("pathlib.Path.exists", return_value=True):
        with patch("shutil.copytree"):
            with patch("shutil.copy2"):
                with patch.object(plugin, "_create_tar_archive", return_value=True):
                    result = plugin._backup_generic_files(generic_service, destination)
                    assert result is True


def test_backup_generic_files_no_backup_paths(plugin, tmp_path):
    """Test generic backup with no backup_paths defined."""
    service = MockService(name="test", type="generic", backup=True, backup_paths=None)
    destination = tmp_path / "backup.tar.gz"

    result = plugin._backup_generic_files(service, destination)
    assert result is False


def test_backup_generic_files_paths_not_found(plugin, generic_service, tmp_path):
    """Test generic backup when paths don't exist."""
    destination = tmp_path / "backup.tar.gz"

    with patch("pathlib.Path.exists", return_value=False):
        result = plugin._backup_generic_files(generic_service, destination)
        assert result is False


# ============================================================================
# Test: Main Backup Method
# ============================================================================


def test_backup_routes_to_docker(plugin, docker_service, tmp_path):
    """Test that backup routes to Docker method."""
    destination = tmp_path / "backup.tar.gz"

    with patch.object(
        plugin, "_backup_docker_service", return_value=True
    ) as mock_docker:
        result = plugin.backup(docker_service, destination)
        assert result is True
        mock_docker.assert_called_once_with(docker_service, destination)


def test_backup_routes_to_systemd(plugin, systemd_service, tmp_path):
    """Test that backup routes to systemd method."""
    destination = tmp_path / "backup.tar.gz"

    with patch.object(
        plugin, "_backup_systemd_service", return_value=True
    ) as mock_systemd:
        result = plugin.backup(systemd_service, destination)
        assert result is True
        mock_systemd.assert_called_once_with(systemd_service, destination)


def test_backup_routes_to_generic(plugin, generic_service, tmp_path):
    """Test that backup routes to generic method."""
    destination = tmp_path / "backup.tar.gz"

    with patch.object(
        plugin, "_backup_generic_files", return_value=True
    ) as mock_generic:
        result = plugin.backup(generic_service, destination)
        assert result is True
        mock_generic.assert_called_once_with(generic_service, destination)


def test_backup_unsupported_type(plugin, tmp_path):
    """Test backup with unsupported service type."""
    # Create a mock service with unsupported type (Pydantic prevents this at creation)
    service = MockService(type="unsupported", name="test")
    destination = tmp_path / "backup.tar.gz"

    result = plugin.backup(service, destination)
    assert result is False


# ============================================================================
# Test: Update Methods
# ============================================================================


def test_update_docker_with_compose(plugin, docker_service):
    """Test updating Docker service with compose file."""
    with patch("pathlib.Path.exists", return_value=True):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            result = plugin._update_docker_service(docker_service)
            assert result is True

            # Verify pull and up were called
            assert mock_run.call_count == 2


def test_update_docker_compose_not_found(plugin, docker_service):
    """Test Docker update when compose file not found."""
    with patch("pathlib.Path.exists", return_value=False):
        result = plugin._update_docker_service(docker_service)
        assert result is False


def test_update_docker_standalone(plugin, mock_docker_client):
    """Test updating standalone Docker container."""
    service = ServiceConfig(
        name="test-docker", type="docker", container_name="test-container", backup=True
    )

    with patch.object(plugin, "_get_docker_client", return_value=mock_docker_client):
        result = plugin._update_docker_service(service)
        assert result is True
        mock_docker_client.images.pull.assert_called_once()


def test_update_systemd_with_package(plugin, systemd_service):
    """Test updating systemd service with package."""
    systemd_service.package_name = "nginx"

    with patch("shutil.which", return_value="/usr/bin/apt-get"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            result = plugin._update_systemd_service(systemd_service)
            assert result is True


def test_update_systemd_restart_only(plugin, systemd_service):
    """Test systemd update without package (restart only)."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)

        result = plugin._update_systemd_service(systemd_service)
        assert result is True


def test_update_routes_to_docker(plugin, docker_service):
    """Test that update routes to Docker method."""
    with patch.object(
        plugin, "_update_docker_service", return_value=True
    ) as mock_update:
        result = plugin.update(docker_service)
        assert result is True
        mock_update.assert_called_once()


def test_update_generic_not_supported(plugin, generic_service):
    """Test that generic services don't support updates."""
    result = plugin.update(generic_service)
    assert result is False


# ============================================================================
# Test: Validate Methods
# ============================================================================


def test_validate_docker_running(plugin, docker_service, mock_docker_client):
    """Test validating running Docker container."""
    with patch.object(plugin, "_get_docker_client", return_value=mock_docker_client):
        result = plugin.validate(docker_service)
        assert result is True


def test_validate_docker_stopped(plugin, docker_service, mock_docker_client):
    """Test validating stopped Docker container."""
    mock_docker_client.containers.get.return_value.status = "exited"

    with patch.object(plugin, "_get_docker_client", return_value=mock_docker_client):
        result = plugin.validate(docker_service)
        assert result is False


def test_validate_docker_unhealthy(plugin, docker_service, mock_docker_client):
    """Test validating unhealthy Docker container."""
    container = mock_docker_client.containers.get.return_value
    container.attrs["State"]["Health"]["Status"] = "unhealthy"

    with patch.object(plugin, "_get_docker_client", return_value=mock_docker_client):
        result = plugin.validate(docker_service)
        assert result is False


def test_validate_systemd_active(plugin, systemd_service):
    """Test validating active systemd service."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="active\n")

        result = plugin.validate(systemd_service)
        assert result is True


def test_validate_systemd_inactive(plugin, systemd_service):
    """Test validating inactive systemd service."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="inactive\n")

        result = plugin.validate(systemd_service)
        assert result is False


def test_validate_generic_paths_exist(plugin, generic_service):
    """Test validating generic service with existing paths."""
    with patch("pathlib.Path.exists", return_value=True):
        result = plugin.validate(generic_service)
        assert result is True


def test_validate_generic_paths_missing(plugin, generic_service):
    """Test validating generic service with missing paths."""
    with patch("pathlib.Path.exists", return_value=False):
        result = plugin.validate(generic_service)
        assert result is False


def test_validate_with_health_check_url(plugin, docker_service, mock_docker_client):
    """Test validation with HTTP health check."""
    docker_service.health_check_url = "http://localhost:8080/health"

    with patch.object(plugin, "_get_docker_client", return_value=mock_docker_client):
        with patch("requests.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200)

            result = plugin.validate(docker_service)
            assert result is True
            mock_get.assert_called_once()


def test_validate_health_check_fails(plugin, docker_service, mock_docker_client):
    """Test validation when health check fails."""
    docker_service.health_check_url = "http://localhost:8080/health"

    with patch.object(plugin, "_get_docker_client", return_value=mock_docker_client):
        with patch("requests.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=500)

            result = plugin.validate(docker_service)
            assert result is False


# ============================================================================
# Test: Rollback Methods
# ============================================================================


def test_rollback_not_supported(plugin, docker_service):
    """Test that rollback returns False (not supported)."""
    result = plugin.rollback(docker_service)
    assert result is False


# ============================================================================
# Test: Status Methods
# ============================================================================


def test_get_status_docker_running(plugin, docker_service, mock_docker_client):
    """Test getting status of running Docker container."""
    with patch.object(plugin, "_get_docker_client", return_value=mock_docker_client):
        status = plugin.get_status(docker_service)

        assert status["running"] is True
        assert status["status"] == "running"
        assert status["image"] == "nginx:latest"
        assert "created" in status


def test_get_status_docker_not_found(plugin, docker_service, mock_docker_client):
    """Test getting status when container not found."""
    import docker

    mock_docker_client.containers.get.side_effect = docker.errors.NotFound("Not found")

    with patch.object(plugin, "_get_docker_client", return_value=mock_docker_client):
        status = plugin.get_status(docker_service)

        assert status["running"] is False
        assert "error" in status


def test_get_status_systemd_active(plugin, systemd_service):
    """Test getting status of active systemd service."""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="active\n"),
            MagicMock(returncode=0, stdout="enabled\n"),
        ]

        status = plugin.get_status(systemd_service)

        assert status["running"] is True
        assert status["active"] == "active"
        assert status["enabled"] is True


def test_get_status_generic_paths_exist(plugin, generic_service):
    """Test getting status of generic service."""
    with patch("pathlib.Path.exists", return_value=True):
        status = plugin.get_status(generic_service)

        assert status["running"] is None
        assert status["paths_exist"] is True


# ============================================================================
# Test: Helper Methods
# ============================================================================


def test_create_manifest(plugin, docker_service):
    """Test creating backup manifest."""
    metadata = {"test": "data"}
    manifest = plugin._create_manifest(docker_service, metadata)

    assert manifest["service_name"] == "test-docker"
    assert manifest["service_type"] == "docker"
    assert "backup_date" in manifest
    assert manifest["version"] == "1.0"
    assert manifest["metadata"] == metadata


def test_create_tar_archive_success(plugin, tmp_path):
    """Test creating tar archive."""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "file.txt").write_text("test")

    destination = tmp_path / "backup.tar.gz"

    result = plugin._create_tar_archive([source_dir], destination)
    assert result is True
    assert destination.exists()


def test_create_tar_archive_permission_error(plugin, tmp_path):
    """Test tar archive creation with permission error."""
    source_dir = tmp_path / "source"
    source_dir.mkdir()

    destination = tmp_path / "readonly" / "backup.tar.gz"

    with patch("tarfile.open", side_effect=PermissionError("Access denied")):
        result = plugin._create_tar_archive([source_dir], destination)
        assert result is False


# ============================================================================
# Test: Error Handling
# ============================================================================


def test_backup_handles_exceptions(plugin, docker_service, tmp_path):
    """Test that backup handles unexpected exceptions."""
    destination = tmp_path / "backup.tar.gz"

    with patch.object(
        plugin, "_backup_docker_service", side_effect=Exception("Unexpected error")
    ):
        result = plugin.backup(docker_service, destination)
        assert result is False


def test_update_handles_exceptions(plugin, docker_service):
    """Test that update handles unexpected exceptions."""
    with patch.object(
        plugin, "_update_docker_service", side_effect=Exception("Unexpected error")
    ):
        result = plugin.update(docker_service)
        assert result is False


def test_validate_handles_exceptions(plugin, docker_service):
    """Test that validate handles unexpected exceptions."""
    with patch.object(plugin, "_get_docker_client", side_effect=Exception("Error")):
        result = plugin.validate(docker_service)
        assert result is False


def test_get_status_handles_exceptions(plugin, docker_service):
    """Test that get_status handles unexpected exceptions."""
    with patch.object(plugin, "_get_docker_client", side_effect=Exception("Error")):
        status = plugin.get_status(docker_service)
        assert status == {}
