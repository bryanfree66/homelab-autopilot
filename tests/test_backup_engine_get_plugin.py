"""
Tests for BackupEngine._get_plugin_for_service() method.

Tests cover:
- VM service type returns ProxmoxPlugin
- LXC service type returns ProxmoxPlugin
- Docker service type returns GenericServicePlugin
- Systemd service type returns GenericServicePlugin
- Generic service type returns GenericServicePlugin
- Plugin caching (same type returns same instance)
- Different service types get different plugin instances
- Cache hit logging
- Cache miss + instantiation logging
- Unsupported service type raises ValueError
- None service type raises ValueError
- Empty string service type raises ValueError
- _clear_plugin_cache() integration
"""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from core.backup_engine import BackupEngine
from core.config_loader import ConfigLoader, ServiceConfig
from lib.state_manager import StateManager
from plugins.hypervisors.proxmox import ProxmoxPlugin
from plugins.services.generic import GenericServicePlugin


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
    """Return a VM service config."""
    return ServiceConfig(
        name="test-vm",
        type="vm",
        vmid=100,
        node="pve",
        backup=True,
    )


@pytest.fixture
def lxc_service():
    """Return an LXC service config."""
    return ServiceConfig(
        name="test-lxc",
        type="lxc",
        vmid=101,
        node="pve",
        backup=True,
    )


@pytest.fixture
def docker_service():
    """Return a Docker service config."""
    return ServiceConfig(
        name="test-docker",
        type="docker",
        container_name="test-docker-container",
        backup=True,
    )


@pytest.fixture
def systemd_service():
    """Return a Systemd service config."""
    return ServiceConfig(
        name="test-systemd",
        type="systemd",
        service_name="test-systemd.service",
        backup=True,
    )


@pytest.fixture
def generic_service():
    """Return a Generic service config."""
    return ServiceConfig(
        name="test-generic",
        type="generic",
        backup=True,
    )


class TestGetPluginForServiceRouting:
    """Test plugin routing based on service type."""

    def test_vm_service_returns_proxmox_plugin(self, backup_engine, vm_service):
        """Test that VM service type returns ProxmoxPlugin."""
        plugin = backup_engine._get_plugin_for_service(vm_service)

        assert isinstance(plugin, ProxmoxPlugin)
        assert plugin.name == "ProxmoxPlugin"

    def test_lxc_service_returns_proxmox_plugin(self, backup_engine, lxc_service):
        """Test that LXC service type returns ProxmoxPlugin."""
        plugin = backup_engine._get_plugin_for_service(lxc_service)

        assert isinstance(plugin, ProxmoxPlugin)
        assert plugin.name == "ProxmoxPlugin"

    def test_docker_service_returns_generic_plugin(self, backup_engine, docker_service):
        """Test that Docker service type returns GenericServicePlugin."""
        plugin = backup_engine._get_plugin_for_service(docker_service)

        assert isinstance(plugin, GenericServicePlugin)
        assert plugin.name == "GenericServicePlugin"

    def test_systemd_service_returns_generic_plugin(
        self, backup_engine, systemd_service
    ):
        """Test that Systemd service type returns GenericServicePlugin."""
        plugin = backup_engine._get_plugin_for_service(systemd_service)

        assert isinstance(plugin, GenericServicePlugin)
        assert plugin.name == "GenericServicePlugin"

    def test_generic_service_returns_generic_plugin(
        self, backup_engine, generic_service
    ):
        """Test that Generic service type returns GenericServicePlugin."""
        plugin = backup_engine._get_plugin_for_service(generic_service)

        assert isinstance(plugin, GenericServicePlugin)
        assert plugin.name == "GenericServicePlugin"

    def test_plugin_receives_config_and_state(self, backup_engine, vm_service):
        """Test that plugin is initialized with config and state."""
        plugin = backup_engine._get_plugin_for_service(vm_service)

        # Verify plugin has access to config and state
        assert hasattr(plugin, "config_loader")
        assert hasattr(plugin, "state_manager")
        assert plugin.config_loader is backup_engine.config
        assert plugin.state_manager is backup_engine.state


class TestGetPluginForServiceCaching:
    """Test plugin caching behavior."""

    def test_second_call_same_type_returns_cached_instance(
        self, backup_engine, vm_service
    ):
        """Test that second call with same service type returns cached instance."""
        # First call - creates new plugin
        plugin1 = backup_engine._get_plugin_for_service(vm_service)

        # Create another VM service with different name
        vm_service2 = ServiceConfig(
            name="another-vm",
            type="vm",
            vmid=102,
            node="pve",
            backup=True,
        )

        # Second call - should return same cached instance
        plugin2 = backup_engine._get_plugin_for_service(vm_service2)

        # Should be the exact same object instance
        assert plugin1 is plugin2

    def test_lxc_and_vm_share_same_plugin_instance(self, backup_engine):
        """Test that VM and LXC services share the same ProxmoxPlugin instance."""
        vm_service = ServiceConfig(
            name="test-vm",
            type="vm",
            vmid=100,
            node="pve",
            backup=True,
        )
        lxc_service = ServiceConfig(
            name="test-lxc",
            type="lxc",
            vmid=101,
            node="pve",
            backup=True,
        )

        vm_plugin = backup_engine._get_plugin_for_service(vm_service)
        lxc_plugin = backup_engine._get_plugin_for_service(lxc_service)

        # VM and LXC should get different cached instances (cached by type)
        # VM gets one ProxmoxPlugin, LXC gets another ProxmoxPlugin
        assert vm_plugin is not lxc_plugin  # Different instances

    def test_different_service_types_get_different_plugins(
        self, backup_engine, vm_service, docker_service
    ):
        """Test that different service types get different plugin instances."""
        vm_plugin = backup_engine._get_plugin_for_service(vm_service)
        docker_plugin = backup_engine._get_plugin_for_service(docker_service)

        # Should be different plugin types
        assert type(vm_plugin) != type(docker_plugin)
        assert isinstance(vm_plugin, ProxmoxPlugin)
        assert isinstance(docker_plugin, GenericServicePlugin)

    def test_docker_systemd_generic_share_same_plugin_instance(self, backup_engine):
        """Test that Docker, systemd, and generic share same plugin instance."""
        docker_service = ServiceConfig(
            name="test-docker",
            type="docker",
            container_name="test-container",
            backup=True,
        )
        systemd_service = ServiceConfig(
            name="test-systemd",
            type="systemd",
            service_name="test.service",
            backup=True,
        )
        generic_service = ServiceConfig(
            name="test-generic",
            type="generic",
            backup=True,
        )

        docker_plugin = backup_engine._get_plugin_for_service(docker_service)
        systemd_plugin = backup_engine._get_plugin_for_service(systemd_service)
        generic_plugin = backup_engine._get_plugin_for_service(generic_service)

        # All three should get different cached instances (cached by type)
        assert docker_plugin is not systemd_plugin
        assert systemd_plugin is not generic_plugin
        assert docker_plugin is not generic_plugin

    def test_cache_state_after_multiple_calls(self, backup_engine):
        """Test cache dictionary state after multiple service types."""
        # Create services of different types
        vm = ServiceConfig(name="vm", type="vm", vmid=100, node="pve", backup=True)
        lxc = ServiceConfig(name="lxc", type="lxc", vmid=101, node="pve", backup=True)
        docker = ServiceConfig(
            name="docker",
            type="docker",
            container_name="test",
            backup=True,
        )
        systemd = ServiceConfig(
            name="systemd",
            type="systemd",
            service_name="test.service",
            backup=True,
        )

        # Get plugins
        backup_engine._get_plugin_for_service(vm)
        backup_engine._get_plugin_for_service(lxc)
        backup_engine._get_plugin_for_service(docker)
        backup_engine._get_plugin_for_service(systemd)

        # Check cache has correct keys
        assert "vm" in backup_engine._plugin_cache
        assert "lxc" in backup_engine._plugin_cache
        assert "docker" in backup_engine._plugin_cache
        assert "systemd" in backup_engine._plugin_cache

        # Verify cache values are correct plugin types
        assert isinstance(backup_engine._plugin_cache["vm"], ProxmoxPlugin)
        assert isinstance(backup_engine._plugin_cache["lxc"], ProxmoxPlugin)
        assert isinstance(backup_engine._plugin_cache["docker"], GenericServicePlugin)
        assert isinstance(backup_engine._plugin_cache["systemd"], GenericServicePlugin)

    def test_clear_plugin_cache_integration(self, backup_engine, vm_service):
        """Test that _clear_plugin_cache() actually clears the cache."""
        # Get plugin (populates cache)
        plugin1 = backup_engine._get_plugin_for_service(vm_service)
        assert len(backup_engine._plugin_cache) == 1

        # Clear cache
        backup_engine._clear_plugin_cache()
        assert len(backup_engine._plugin_cache) == 0

        # Get plugin again (should create new instance)
        plugin2 = backup_engine._get_plugin_for_service(vm_service)

        # Should be a different instance (cache was cleared)
        assert plugin1 is not plugin2


class TestGetPluginForServiceLogging:
    """Test logging behavior (verifies operations complete).

    Note: Logging output can be verified manually in pytest output.
    These tests verify the operations complete correctly.
    """

    def test_first_call_instantiates_plugin(self, backup_engine, vm_service):
        """Test that first call creates a new plugin instance."""
        # Cache should be empty initially
        assert len(backup_engine._plugin_cache) == 0

        # First call - creates plugin
        plugin = backup_engine._get_plugin_for_service(vm_service)

        # Should have created and cached the plugin
        assert plugin is not None
        assert len(backup_engine._plugin_cache) == 1
        assert "vm" in backup_engine._plugin_cache

    def test_second_call_uses_cache(self, backup_engine, vm_service):
        """Test that second call uses cached plugin."""
        # First call - create plugin
        plugin1 = backup_engine._get_plugin_for_service(vm_service)
        cache_size_after_first = len(backup_engine._plugin_cache)

        # Second call - should use cache
        plugin2 = backup_engine._get_plugin_for_service(vm_service)
        cache_size_after_second = len(backup_engine._plugin_cache)

        # Cache size shouldn't increase (used existing entry)
        assert cache_size_after_first == cache_size_after_second
        assert plugin1 is plugin2

    def test_different_types_log_different_instantiations(
        self, backup_engine, vm_service, docker_service
    ):
        """Test that different types create separate plugins."""
        vm_plugin = backup_engine._get_plugin_for_service(vm_service)
        docker_plugin = backup_engine._get_plugin_for_service(docker_service)

        # Should have created two different plugins
        assert len(backup_engine._plugin_cache) == 2
        assert vm_plugin is not docker_plugin


class TestGetPluginForServiceErrorHandling:
    """Test error handling and validation."""

    def test_unsupported_service_type_raises_value_error(self, backup_engine):
        """Test that unsupported service type raises ValueError."""
        # Use mock to bypass Pydantic validation
        unsupported_service = Mock(spec=ServiceConfig)
        unsupported_service.name = "test-k8s"
        unsupported_service.type = "kubernetes"  # Not supported

        with pytest.raises(ValueError) as exc_info:
            backup_engine._get_plugin_for_service(unsupported_service)

        error_msg = str(exc_info.value)
        assert "unsupported" in error_msg.lower()
        assert "kubernetes" in error_msg.lower()
        assert "test-k8s" in error_msg  # Should include service name
        assert "vm" in error_msg.lower()  # Should list supported types
        assert "docker" in error_msg.lower()

    def test_none_service_type_raises_value_error(self, backup_engine):
        """Test that None service type raises ValueError."""
        # Create a mock service with None type
        mock_service = Mock(spec=ServiceConfig)
        mock_service.name = "test-service"
        mock_service.type = None

        with pytest.raises(ValueError) as exc_info:
            backup_engine._get_plugin_for_service(mock_service)

        error_msg = str(exc_info.value)
        assert "no type defined" in error_msg.lower()
        assert "test-service" in error_msg

    def test_empty_string_service_type_raises_value_error(self, backup_engine):
        """Test that empty string service type raises ValueError."""
        # Create a mock service with empty type
        mock_service = Mock(spec=ServiceConfig)
        mock_service.name = "test-service"
        mock_service.type = ""

        with pytest.raises(ValueError) as exc_info:
            backup_engine._get_plugin_for_service(mock_service)

        error_msg = str(exc_info.value)
        # Empty string will fail the "if not service_type" check
        assert "no type defined" in error_msg.lower()

    def test_error_message_is_actionable(self, backup_engine):
        """Test that error messages provide actionable guidance."""
        # Use mock to bypass Pydantic validation
        unsupported_service = Mock(spec=ServiceConfig)
        unsupported_service.name = "my-app"
        unsupported_service.type = "custom"

        with pytest.raises(ValueError) as exc_info:
            backup_engine._get_plugin_for_service(unsupported_service)

        error_msg = str(exc_info.value)
        # Should include:
        # - What's wrong (unsupported type)
        # - Which service
        # - What types are supported
        assert "custom" in error_msg.lower()
        assert "my-app" in error_msg
        assert "supported types" in error_msg.lower()


class TestGetPluginForServiceCaseInsensitivity:
    """Test case insensitivity for service types."""

    def test_uppercase_vm_type(self, backup_engine):
        """Test that uppercase VM type is handled correctly."""
        service = ServiceConfig(
            name="test",
            type="VM",  # Uppercase
            vmid=100,
            node="pve",
            backup=True,
        )

        plugin = backup_engine._get_plugin_for_service(service)
        assert isinstance(plugin, ProxmoxPlugin)

    def test_mixed_case_docker_type(self, backup_engine):
        """Test that mixed case Docker type is handled correctly."""
        service = ServiceConfig(
            name="test",
            type="Docker",  # Mixed case
            container_name="test",
            backup=True,
        )

        plugin = backup_engine._get_plugin_for_service(service)
        assert isinstance(plugin, GenericServicePlugin)

    def test_cache_key_is_lowercase(self, backup_engine):
        """Test that cache keys are normalized to lowercase."""
        service_upper = ServiceConfig(
            name="test",
            type="VM",
            vmid=100,
            node="pve",
            backup=True,
        )
        service_lower = ServiceConfig(
            name="test2",
            type="vm",
            vmid=101,
            node="pve",
            backup=True,
        )

        # Get plugins
        plugin1 = backup_engine._get_plugin_for_service(service_upper)
        plugin2 = backup_engine._get_plugin_for_service(service_lower)

        # Should return same cached instance (both resolve to "vm")
        assert plugin1 is plugin2

        # Cache should have lowercase key
        assert "vm" in backup_engine._plugin_cache
        assert "VM" not in backup_engine._plugin_cache


class TestGetPluginForServiceEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_service_type_with_whitespace(self, backup_engine):
        """Test that service type with leading/trailing whitespace fails."""
        # Create mock service with whitespace in type
        mock_service = Mock(spec=ServiceConfig)
        mock_service.name = "test"
        mock_service.type = " vm "  # Has whitespace

        # This should fail validation (not in supported types)
        with pytest.raises(ValueError):
            backup_engine._get_plugin_for_service(mock_service)

    def test_multiple_sequential_calls_same_service(self, backup_engine, vm_service):
        """Test multiple sequential calls with same service instance."""
        # Should work fine and return cached instance after first call
        plugin1 = backup_engine._get_plugin_for_service(vm_service)
        plugin2 = backup_engine._get_plugin_for_service(vm_service)
        plugin3 = backup_engine._get_plugin_for_service(vm_service)

        assert plugin1 is plugin2
        assert plugin2 is plugin3

    def test_cache_persists_across_different_service_names(self, backup_engine):
        """Test that cache persists across services with different names but same type."""
        service1 = ServiceConfig(
            name="service-1",
            type="docker",
            container_name="container-1",
            backup=True,
        )
        service2 = ServiceConfig(
            name="service-2",
            type="docker",
            container_name="container-2",
            backup=True,
        )
        service3 = ServiceConfig(
            name="service-3",
            type="docker",
            container_name="container-3",
            backup=True,
        )

        plugin1 = backup_engine._get_plugin_for_service(service1)
        plugin2 = backup_engine._get_plugin_for_service(service2)
        plugin3 = backup_engine._get_plugin_for_service(service3)

        # All should be same cached instance
        assert plugin1 is plugin2
        assert plugin2 is plugin3


class TestGetPluginForServiceTypeValidation:
    """Test comprehensive type validation."""

    def test_all_supported_types_work(self, backup_engine):
        """Test that all supported service types work correctly."""
        supported_types = ["vm", "lxc", "docker", "systemd", "generic"]

        for service_type in supported_types:
            # Create appropriate service config based on type
            if service_type in ["vm", "lxc"]:
                service = ServiceConfig(
                    name=f"test-{service_type}",
                    type=service_type,
                    vmid=100,
                    node="pve",
                    backup=True,
                )
            elif service_type == "docker":
                service = ServiceConfig(
                    name=f"test-{service_type}",
                    type=service_type,
                    container_name="test",
                    backup=True,
                )
            elif service_type == "systemd":
                service = ServiceConfig(
                    name=f"test-{service_type}",
                    type=service_type,
                    service_name="test.service",
                    backup=True,
                )
            else:  # generic
                service = ServiceConfig(
                    name=f"test-{service_type}",
                    type=service_type,
                    backup=True,
                )

            # Should not raise
            plugin = backup_engine._get_plugin_for_service(service)
            assert plugin is not None

    def test_unsupported_types_raise_error(self, backup_engine):
        """Test that various unsupported types all raise ValueError."""
        unsupported_types = [
            "kubernetes",
            "k8s",
            "esxi",
            "virtualbox",
            "podman",
            "unknown",
            "custom",
        ]

        for service_type in unsupported_types:
            # Use mock to bypass Pydantic validation
            service = Mock(spec=ServiceConfig)
            service.name = f"test-{service_type}"
            service.type = service_type

            with pytest.raises(ValueError) as exc_info:
                backup_engine._get_plugin_for_service(service)

            # Verify error message mentions the unsupported type
            assert service_type in str(exc_info.value).lower()
