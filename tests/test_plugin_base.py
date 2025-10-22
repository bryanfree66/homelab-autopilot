"""
Tests for plugin base classes.

This module tests the abstract base classes for the plugin system to ensure:
- Abstract methods are properly enforced
- Plugin initialization works correctly
- Helper methods function as expected
- The plugin interface is correctly defined
"""

from pathlib import Path
from typing import Any, Dict, Optional

import pytest

from plugins.base import (
    HypervisorPlugin,
    NotificationPlugin,
    PluginBase,
    ServicePlugin,
)


# Mock ServiceConfig for testing
class MockServiceConfig:
    """Mock ServiceConfig for testing plugin methods."""

    def __init__(
        self,
        name: str = "test-service",
        service_type: str = "vm",
        vmid: Optional[int] = None,
        node: Optional[str] = None,
        container_name: Optional[str] = None,
    ):
        self.name = name
        self.type = service_type
        self.vmid = vmid
        self.node = node
        self.container_name = container_name


# Concrete implementations for testing


class ConcretePlugin(PluginBase):
    """Concrete plugin implementation for testing PluginBase."""

    @property
    def name(self) -> str:
        return "TestPlugin"

    def matches(self, target: Dict[str, Any]) -> bool:
        return target.get("type") == "test"


class ConcreteHypervisorPlugin(HypervisorPlugin):
    """Concrete hypervisor plugin for testing."""

    @property
    def name(self) -> str:
        return "TestHypervisor"

    def matches(self, service: Any) -> bool:
        return service.type in ["vm", "lxc"]

    def backup(self, service: Any, destination: Path) -> bool:
        return True

    def create_snapshot(self, service: Any, snapshot_name: str) -> bool:
        return True

    def restore_snapshot(self, service: Any, snapshot_name: str) -> bool:
        return True

    def delete_snapshot(self, service: Any, snapshot_name: str) -> bool:
        return True

    def get_status(self, service: Any) -> Dict[str, Any]:
        return {"running": True, "cpu": 25, "memory": 512}


class ConcreteServicePlugin(ServicePlugin):
    """Concrete service plugin for testing."""

    @property
    def name(self) -> str:
        return "TestService"

    def matches(self, service: Any) -> bool:
        return service.type == "docker"

    def backup(self, service: Any, destination: Path) -> bool:
        return True

    def update(self, service: Any) -> bool:
        return True

    def validate(self, service: Any) -> bool:
        return True

    def rollback(self, service: Any) -> bool:
        return False  # Not supported

    def get_status(self, service: Any) -> Dict[str, Any]:
        return {"running": True, "healthy": True}


class ConcreteNotificationPlugin(NotificationPlugin):
    """Concrete notification plugin for testing."""

    @property
    def name(self) -> str:
        return "TestNotification"

    def matches(self, notification_config: Dict[str, Any]) -> bool:
        return notification_config.get("type") == "test"

    def send_notification(
        self,
        title: str,
        message: str,
        level: str = "info",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        return True

    def test_connection(self) -> bool:
        return True


# Tests for PluginBase


class TestPluginBase:
    """Tests for the PluginBase abstract class."""

    def test_cannot_instantiate_abstract_class(self):
        """Test that PluginBase cannot be instantiated directly."""
        with pytest.raises(TypeError):
            PluginBase({})

    def test_concrete_plugin_initialization(self):
        """Test that concrete plugin can be initialized with config."""
        config = {"setting": "value", "enabled": True}
        plugin = ConcretePlugin(config)

        assert plugin.config == config
        assert plugin.config["setting"] == "value"
        assert plugin.config["enabled"] is True

    def test_concrete_plugin_name_property(self):
        """Test that name property works correctly."""
        plugin = ConcretePlugin({})
        assert plugin.name == "TestPlugin"

    def test_concrete_plugin_matches(self):
        """Test that matches method works correctly."""
        plugin = ConcretePlugin({})

        assert plugin.matches({"type": "test"}) is True
        assert plugin.matches({"type": "other"}) is False
        assert plugin.matches({}) is False

    def test_missing_abstract_method_raises_error(self):
        """Test that missing abstract methods prevent instantiation."""

        class IncompletePlugin(PluginBase):
            @property
            def name(self) -> str:
                return "Incomplete"

            # Missing matches() method

        with pytest.raises(TypeError):
            IncompletePlugin({})


# Tests for HypervisorPlugin


class TestHypervisorPlugin:
    """Tests for the HypervisorPlugin abstract class."""

    def test_cannot_instantiate_abstract_class(self):
        """Test that HypervisorPlugin cannot be instantiated directly."""
        with pytest.raises(TypeError):
            HypervisorPlugin({})

    def test_concrete_hypervisor_plugin_initialization(self):
        """Test that concrete hypervisor plugin initializes correctly."""
        config = {"host": "pve.local", "username": "root"}
        plugin = ConcreteHypervisorPlugin(config)

        assert plugin.config == config
        assert plugin.name == "TestHypervisor"

    def test_hypervisor_plugin_matches(self):
        """Test hypervisor plugin matches method."""
        plugin = ConcreteHypervisorPlugin({})

        vm_service = MockServiceConfig(service_type="vm", vmid=100, node="pve1")
        lxc_service = MockServiceConfig(service_type="lxc", vmid=101, node="pve1")
        docker_service = MockServiceConfig(service_type="docker")

        assert plugin.matches(vm_service) is True
        assert plugin.matches(lxc_service) is True
        assert plugin.matches(docker_service) is False

    def test_hypervisor_plugin_backup(self):
        """Test hypervisor plugin backup method."""
        plugin = ConcreteHypervisorPlugin({})
        service = MockServiceConfig(service_type="vm", vmid=100, node="pve1")
        destination = Path("/backups/test")

        result = plugin.backup(service, destination)
        assert result is True

    def test_hypervisor_plugin_snapshot_operations(self):
        """Test hypervisor plugin snapshot methods."""
        plugin = ConcreteHypervisorPlugin({})
        service = MockServiceConfig(service_type="vm", vmid=100, node="pve1")

        # Create snapshot
        assert plugin.create_snapshot(service, "snap1") is True

        # Restore snapshot
        assert plugin.restore_snapshot(service, "snap1") is True

        # Delete snapshot
        assert plugin.delete_snapshot(service, "snap1") is True

    def test_hypervisor_plugin_get_status(self):
        """Test hypervisor plugin get_status method."""
        plugin = ConcreteHypervisorPlugin({})
        service = MockServiceConfig(service_type="vm", vmid=100, node="pve1")

        status = plugin.get_status(service)
        assert isinstance(status, dict)
        assert "running" in status
        assert status["running"] is True
        assert "cpu" in status
        assert "memory" in status

    def test_incomplete_hypervisor_plugin_raises_error(self):
        """Test that incomplete hypervisor plugin cannot be instantiated."""

        class IncompleteHypervisorPlugin(HypervisorPlugin):
            @property
            def name(self) -> str:
                return "Incomplete"

            def matches(self, service: Any) -> bool:
                return True

            # Missing required methods: backup, create_snapshot, etc.

        with pytest.raises(TypeError):
            IncompleteHypervisorPlugin({})


# Tests for ServicePlugin


class TestServicePlugin:
    """Tests for the ServicePlugin abstract class."""

    def test_cannot_instantiate_abstract_class(self):
        """Test that ServicePlugin cannot be instantiated directly."""
        with pytest.raises(TypeError):
            ServicePlugin({})

    def test_concrete_service_plugin_initialization(self):
        """Test that concrete service plugin initializes correctly."""
        config = {"docker_socket": "/var/run/docker.sock"}
        plugin = ConcreteServicePlugin(config)

        assert plugin.config == config
        assert plugin.name == "TestService"

    def test_service_plugin_matches(self):
        """Test service plugin matches method."""
        plugin = ConcreteServicePlugin({})

        docker_service = MockServiceConfig(
            service_type="docker", container_name="test-container"
        )
        vm_service = MockServiceConfig(service_type="vm", vmid=100, node="pve1")

        assert plugin.matches(docker_service) is True
        assert plugin.matches(vm_service) is False

    def test_service_plugin_backup(self):
        """Test service plugin backup method."""
        plugin = ConcreteServicePlugin({})
        service = MockServiceConfig(
            service_type="docker", container_name="test-container"
        )
        destination = Path("/backups/test")

        result = plugin.backup(service, destination)
        assert result is True

    def test_service_plugin_update(self):
        """Test service plugin update method."""
        plugin = ConcreteServicePlugin({})
        service = MockServiceConfig(
            service_type="docker", container_name="test-container"
        )

        result = plugin.update(service)
        assert result is True

    def test_service_plugin_validate(self):
        """Test service plugin validate method."""
        plugin = ConcreteServicePlugin({})
        service = MockServiceConfig(
            service_type="docker", container_name="test-container"
        )

        result = plugin.validate(service)
        assert result is True

    def test_service_plugin_rollback(self):
        """Test service plugin rollback method."""
        plugin = ConcreteServicePlugin({})
        service = MockServiceConfig(
            service_type="docker", container_name="test-container"
        )

        # This implementation doesn't support rollback
        result = plugin.rollback(service)
        assert result is False

    def test_service_plugin_get_status(self):
        """Test service plugin get_status method."""
        plugin = ConcreteServicePlugin({})
        service = MockServiceConfig(
            service_type="docker", container_name="test-container"
        )

        status = plugin.get_status(service)
        assert isinstance(status, dict)
        assert "running" in status
        assert "healthy" in status

    def test_incomplete_service_plugin_raises_error(self):
        """Test that incomplete service plugin cannot be instantiated."""

        class IncompleteServicePlugin(ServicePlugin):
            @property
            def name(self) -> str:
                return "Incomplete"

            def matches(self, service: Any) -> bool:
                return True

            # Missing required methods: backup, update, validate, rollback, get_status

        with pytest.raises(TypeError):
            IncompleteServicePlugin({})


# Tests for NotificationPlugin


class TestNotificationPlugin:
    """Tests for the NotificationPlugin abstract class."""

    def test_cannot_instantiate_abstract_class(self):
        """Test that NotificationPlugin cannot be instantiated directly."""
        with pytest.raises(TypeError):
            NotificationPlugin({})

    def test_concrete_notification_plugin_initialization(self):
        """Test that concrete notification plugin initializes correctly."""
        config = {"type": "test", "settings": {"endpoint": "http://test"}}
        plugin = ConcreteNotificationPlugin(config)

        assert plugin.config == config
        assert plugin.name == "TestNotification"

    def test_notification_plugin_matches(self):
        """Test notification plugin matches method."""
        plugin = ConcreteNotificationPlugin({})

        test_config = {"type": "test", "enabled": True}
        other_config = {"type": "email", "enabled": True}

        assert plugin.matches(test_config) is True
        assert plugin.matches(other_config) is False

    def test_notification_plugin_send_notification(self):
        """Test notification plugin send_notification method."""
        plugin = ConcreteNotificationPlugin({})

        result = plugin.send_notification(
            title="Test Alert",
            message="This is a test",
            level="info",
            metadata={"service": "test"},
        )
        assert result is True

    def test_notification_plugin_test_connection(self):
        """Test notification plugin test_connection method."""
        plugin = ConcreteNotificationPlugin({})
        assert plugin.test_connection() is True

    def test_notification_plugin_format_message(self):
        """Test notification plugin format_message helper method."""
        plugin = ConcreteNotificationPlugin({})

        # Without metadata
        formatted = plugin.format_message("Title", "Message", "info")
        assert "Title" in formatted
        assert "Message" in formatted

        # With metadata
        metadata = {"service": "test-service", "duration": 120}
        formatted = plugin.format_message("Title", "Message", "info", metadata)
        assert "Title" in formatted
        assert "Message" in formatted
        assert "service" in formatted
        assert "test-service" in formatted
        assert "duration" in formatted
        assert "120" in formatted

    def test_notification_plugin_get_emoji_for_level(self):
        """Test notification plugin get_emoji_for_level helper method."""
        plugin = ConcreteNotificationPlugin({})

        assert plugin.get_emoji_for_level("success") == "✅"
        assert plugin.get_emoji_for_level("info") == "ℹ️"
        assert plugin.get_emoji_for_level("warning") == "⚠️"
        assert plugin.get_emoji_for_level("error") == "❌"

        # Case insensitive
        assert plugin.get_emoji_for_level("SUCCESS") == "✅"
        assert plugin.get_emoji_for_level("Error") == "❌"

        # Unknown level returns default
        assert plugin.get_emoji_for_level("unknown") == "📢"

    def test_incomplete_notification_plugin_raises_error(self):
        """Test that incomplete notification plugin cannot be instantiated."""

        class IncompleteNotificationPlugin(NotificationPlugin):
            @property
            def name(self) -> str:
                return "Incomplete"

            # Missing required methods: send_notification, test_connection

        with pytest.raises(TypeError):
            IncompleteNotificationPlugin({})


# Integration tests


class TestPluginIntegration:
    """Integration tests for plugin system."""

    def test_multiple_plugins_can_coexist(self):
        """Test that multiple plugin types can be instantiated together."""
        hypervisor = ConcreteHypervisorPlugin({"host": "pve.local"})
        service = ConcreteServicePlugin({"socket": "/var/run/docker.sock"})
        notification = ConcreteNotificationPlugin({"type": "test"})

        assert hypervisor.name == "TestHypervisor"
        assert service.name == "TestService"
        assert notification.name == "TestNotification"

    def test_plugins_maintain_separate_configs(self):
        """Test that each plugin maintains its own configuration."""
        config1 = {"setting": "value1"}
        config2 = {"setting": "value2"}

        plugin1 = ConcretePlugin(config1)
        plugin2 = ConcretePlugin(config2)

        assert plugin1.config["setting"] == "value1"
        assert plugin2.config["setting"] == "value2"

    def test_plugin_workflow_simulation(self):
        """Test a simulated backup workflow using plugins."""
        # Setup
        hypervisor = ConcreteHypervisorPlugin({"host": "pve.local"})
        notification = ConcreteNotificationPlugin({"type": "test"})

        vm_service = MockServiceConfig(service_type="vm", vmid=100, node="pve1")
        destination = Path("/backups/vm-100")

        # Check if hypervisor handles this service
        assert hypervisor.matches(vm_service) is True

        # Create snapshot before backup
        snapshot_created = hypervisor.create_snapshot(vm_service, "pre-backup-snap")
        assert snapshot_created is True

        # Perform backup
        backup_success = hypervisor.backup(vm_service, destination)
        assert backup_success is True

        # Send notification
        notification_sent = notification.send_notification(
            title="Backup Complete",
            message=f"Backed up {vm_service.name}",
            level="success",
            metadata={"vmid": vm_service.vmid},
        )
        assert notification_sent is True

        # Cleanup snapshot
        snapshot_deleted = hypervisor.delete_snapshot(vm_service, "pre-backup-snap")
        assert snapshot_deleted is True
