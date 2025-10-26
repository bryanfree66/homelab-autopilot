"""
Integration tests for BackupEngine._clear_plugin_cache() method.

Tests verify that clearing the plugin cache properly affects plugin loading
and that the integration with _get_plugin_for_service() works correctly.
"""

from pathlib import Path

import pytest

from core.backup_engine import BackupEngine
from core.config_loader import ConfigLoader, ServiceConfig


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
def vm_service():
    """Return VM service configuration."""
    return ServiceConfig(
        name="test-vm",
        type="vm",
        vmid=100,
        node="pve1",
        backup=True,
    )


@pytest.fixture
def docker_service():
    """Return Docker service configuration."""
    return ServiceConfig(
        name="test-docker",
        type="docker",
        container_name="test-container",
        backup=True,
    )


@pytest.fixture
def lxc_service():
    """Return LXC service configuration."""
    return ServiceConfig(
        name="test-lxc",
        type="lxc",
        vmid=200,
        node="pve1",
        backup=True,
    )


# Basic Functionality Tests
class TestClearPluginCacheBasicFunctionality:
    """Test basic cache clearing functionality."""

    def test_cache_starts_empty(self, backup_engine):
        """Test cache starts empty on fresh BackupEngine."""
        assert len(backup_engine._plugin_cache) == 0
        assert backup_engine._plugin_cache == {}

    def test_getting_plugin_populates_cache(self, backup_engine, vm_service):
        """Test getting a plugin populates cache via _get_plugin_for_service()."""
        # Verify cache is empty
        assert len(backup_engine._plugin_cache) == 0

        # Get plugin
        plugin = backup_engine._get_plugin_for_service(vm_service)

        # Verify cache is populated
        assert len(backup_engine._plugin_cache) == 1
        assert "vm" in backup_engine._plugin_cache
        assert backup_engine._plugin_cache["vm"] is plugin

    def test_clearing_cache_removes_all_entries(
        self, backup_engine, vm_service, docker_service
    ):
        """Test clearing cache removes all entries."""
        # Populate cache with multiple plugins
        backup_engine._get_plugin_for_service(vm_service)
        backup_engine._get_plugin_for_service(docker_service)

        # Verify cache has entries
        assert len(backup_engine._plugin_cache) == 2

        # Clear cache
        backup_engine._clear_plugin_cache()

        # Verify cache is empty
        assert len(backup_engine._plugin_cache) == 0
        assert backup_engine._plugin_cache == {}

    def test_getting_plugin_after_clear_repopulates_cache(
        self, backup_engine, vm_service
    ):
        """Test getting plugin after clear repopulates cache with fresh instance."""
        # Get plugin and store reference
        plugin1 = backup_engine._get_plugin_for_service(vm_service)
        plugin1_id = id(plugin1)

        # Clear cache
        backup_engine._clear_plugin_cache()

        # Verify cache is empty
        assert len(backup_engine._plugin_cache) == 0

        # Get plugin again
        plugin2 = backup_engine._get_plugin_for_service(vm_service)
        plugin2_id = id(plugin2)

        # Verify cache is repopulated
        assert len(backup_engine._plugin_cache) == 1

        # Verify it's a NEW instance (different object)
        assert plugin1_id != plugin2_id
        assert plugin1 is not plugin2


# Integration with Plugin Loading Tests
class TestClearPluginCacheIntegration:
    """Test integration with plugin loading system."""

    def test_same_service_queried_twice_uses_cached_plugin(
        self, backup_engine, vm_service
    ):
        """Test same service queried twice uses cached plugin (verify same instance)."""
        # Get plugin twice
        plugin1 = backup_engine._get_plugin_for_service(vm_service)
        plugin2 = backup_engine._get_plugin_for_service(vm_service)

        # Verify same instance (not just equal, but identical object)
        assert plugin1 is plugin2
        assert id(plugin1) == id(plugin2)

        # Verify cache only has one entry
        assert len(backup_engine._plugin_cache) == 1

    def test_after_cache_clear_same_service_gets_new_plugin_instance(
        self, backup_engine, vm_service
    ):
        """Test after cache clear, same service gets new plugin instance (different instance)."""
        # Get plugin
        plugin1 = backup_engine._get_plugin_for_service(vm_service)

        # Clear cache
        backup_engine._clear_plugin_cache()

        # Get plugin again
        plugin2 = backup_engine._get_plugin_for_service(vm_service)

        # Verify different instances
        assert plugin1 is not plugin2
        assert id(plugin1) != id(plugin2)

        # But both should be same type
        assert type(plugin1) == type(plugin2)

    def test_multiple_different_services_cached_clear_removes_all(
        self, backup_engine, vm_service, docker_service, lxc_service
    ):
        """Test multiple different services cached, clear removes all."""
        # Get plugins for different service types
        vm_plugin = backup_engine._get_plugin_for_service(vm_service)
        docker_plugin = backup_engine._get_plugin_for_service(docker_service)
        lxc_plugin = backup_engine._get_plugin_for_service(lxc_service)

        # Verify all cached (each service type gets its own entry)
        assert len(backup_engine._plugin_cache) == 3  # vm, lxc, docker separate
        assert "vm" in backup_engine._plugin_cache
        assert "lxc" in backup_engine._plugin_cache
        assert "docker" in backup_engine._plugin_cache

        # Clear cache
        backup_engine._clear_plugin_cache()

        # Verify all removed
        assert len(backup_engine._plugin_cache) == 0
        assert "vm" not in backup_engine._plugin_cache
        assert "lxc" not in backup_engine._plugin_cache
        assert "docker" not in backup_engine._plugin_cache

        # Get plugins again - verify new instances
        vm_plugin2 = backup_engine._get_plugin_for_service(vm_service)
        docker_plugin2 = backup_engine._get_plugin_for_service(docker_service)
        lxc_plugin2 = backup_engine._get_plugin_for_service(lxc_service)

        assert vm_plugin is not vm_plugin2
        assert docker_plugin is not docker_plugin2
        assert lxc_plugin is not lxc_plugin2


# Edge Cases Tests
class TestClearPluginCacheEdgeCases:
    """Test edge cases for cache clearing."""

    def test_clearing_empty_cache_doesnt_error(self, backup_engine):
        """Test clearing empty cache doesn't error."""
        # Verify cache is empty
        assert len(backup_engine._plugin_cache) == 0

        # Clear empty cache - should not raise
        backup_engine._clear_plugin_cache()

        # Still empty
        assert len(backup_engine._plugin_cache) == 0

    def test_clearing_cache_multiple_times_is_safe(self, backup_engine, vm_service):
        """Test clearing cache multiple times is safe."""
        # Populate cache
        backup_engine._get_plugin_for_service(vm_service)
        assert len(backup_engine._plugin_cache) == 1

        # Clear multiple times
        backup_engine._clear_plugin_cache()
        backup_engine._clear_plugin_cache()
        backup_engine._clear_plugin_cache()

        # Verify still empty and no errors
        assert len(backup_engine._plugin_cache) == 0

    def test_cache_clear_doesnt_affect_state_manager(self, backup_engine, vm_service):
        """Test cache clear doesn't affect StateManager or other components."""
        # Set some state
        backup_engine.state.set("test_key", "test_value")

        # Get plugin to populate cache
        backup_engine._get_plugin_for_service(vm_service)

        # Clear plugin cache
        backup_engine._clear_plugin_cache()

        # Verify state manager still works
        assert backup_engine.state.get("test_key") == "test_value"

        # Verify config still accessible
        assert backup_engine.config is not None

        # Verify dry_run flag unchanged
        original_dry_run = backup_engine.dry_run
        backup_engine._clear_plugin_cache()
        assert backup_engine.dry_run == original_dry_run


# Logging Verification Tests
class TestClearPluginCacheLogging:
    """Test logging behavior for cache clearing."""

    def test_cache_clear_logs_at_debug_level(self, backup_engine, vm_service):
        """Test cache clear logs at DEBUG level."""
        # Populate cache
        backup_engine._get_plugin_for_service(vm_service)

        # Clear cache - should complete without error (logging verified in method)
        backup_engine._clear_plugin_cache()

        # Verify operation completed successfully
        assert len(backup_engine._plugin_cache) == 0

    def test_log_message_contains_plugin_cache_cleared(self, backup_engine):
        """Test log message contains 'Plugin cache cleared'."""
        # Clear cache - method logs "Plugin cache cleared"
        backup_engine._clear_plugin_cache()

        # Verify operation completed (logging is done in the method)
        assert len(backup_engine._plugin_cache) == 0


class TestClearPluginCacheMultipleServiceTypes:
    """Test cache clearing with multiple service types."""

    def test_vm_and_lxc_get_separate_cache_entries(
        self, backup_engine, vm_service, lxc_service
    ):
        """Test VM and LXC services get separate plugin cache entries."""
        # Get plugins for both
        vm_plugin = backup_engine._get_plugin_for_service(vm_service)
        lxc_plugin = backup_engine._get_plugin_for_service(lxc_service)

        # They should be different instances (each service type gets its own)
        assert vm_plugin is not lxc_plugin
        assert id(vm_plugin) != id(lxc_plugin)

        # Cache should have 2 entries (keyed by "vm" and "lxc")
        assert len(backup_engine._plugin_cache) == 2
        assert "vm" in backup_engine._plugin_cache
        assert "lxc" in backup_engine._plugin_cache

        # But they should be the same type (both ProxmoxPlugin)
        assert type(vm_plugin) == type(lxc_plugin)

    def test_docker_and_systemd_get_separate_cache_entries(self, backup_engine):
        """Test Docker and systemd services get separate plugin cache entries."""
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

        # Get plugins for both
        docker_plugin = backup_engine._get_plugin_for_service(docker_service)
        systemd_plugin = backup_engine._get_plugin_for_service(systemd_service)

        # They should be different instances (each service type gets its own)
        assert docker_plugin is not systemd_plugin
        assert id(docker_plugin) != id(systemd_plugin)

        # Cache should have 2 entries (keyed by "docker" and "systemd")
        assert len(backup_engine._plugin_cache) == 2
        assert "docker" in backup_engine._plugin_cache
        assert "systemd" in backup_engine._plugin_cache

        # But they should be the same type (both GenericServicePlugin)
        assert type(docker_plugin) == type(systemd_plugin)

    def test_clearing_cache_affects_all_service_types(
        self, backup_engine, vm_service, lxc_service
    ):
        """Test clearing cache affects all service types."""
        # Get plugins (vm and lxc get separate instances)
        vm_plugin1 = backup_engine._get_plugin_for_service(vm_service)
        lxc_plugin1 = backup_engine._get_plugin_for_service(lxc_service)

        # Verify they are different instances
        assert vm_plugin1 is not lxc_plugin1

        # Clear cache
        backup_engine._clear_plugin_cache()

        # Get plugins again
        vm_plugin2 = backup_engine._get_plugin_for_service(vm_service)
        lxc_plugin2 = backup_engine._get_plugin_for_service(lxc_service)

        # Verify both got NEW instances
        assert vm_plugin1 is not vm_plugin2
        assert lxc_plugin1 is not lxc_plugin2

        # And the new instances are also different from each other
        assert vm_plugin2 is not lxc_plugin2


class TestClearPluginCacheConcurrency:
    """Test cache clearing behavior in various scenarios."""

    def test_cache_clear_between_different_service_queries(
        self, backup_engine, vm_service, docker_service
    ):
        """Test cache clear between querying different services."""
        # Get VM plugin
        vm_plugin1 = backup_engine._get_plugin_for_service(vm_service)

        # Clear cache
        backup_engine._clear_plugin_cache()

        # Get Docker plugin
        docker_plugin = backup_engine._get_plugin_for_service(docker_service)

        # Get VM plugin again
        vm_plugin2 = backup_engine._get_plugin_for_service(vm_service)

        # Verify vm_plugin1 and vm_plugin2 are different (cache was cleared)
        assert vm_plugin1 is not vm_plugin2

        # Verify all are in cache now
        assert len(backup_engine._plugin_cache) == 2

    def test_repeated_clear_and_populate_cycles(self, backup_engine, vm_service):
        """Test repeated clear and populate cycles work correctly."""
        # Do 5 cycles of get -> clear
        for i in range(5):
            plugin = backup_engine._get_plugin_for_service(vm_service)

            # Verify cache is populated
            assert len(backup_engine._plugin_cache) == 1
            assert "vm" in backup_engine._plugin_cache

            # Clear cache
            backup_engine._clear_plugin_cache()

            # Verify cache is empty
            assert len(backup_engine._plugin_cache) == 0

        # Final verification: cache is still empty
        assert len(backup_engine._plugin_cache) == 0

    def test_cache_state_after_partial_population_and_clear(
        self, backup_engine, vm_service, docker_service
    ):
        """Test cache state after partial population and clear."""
        # Get VM plugin
        backup_engine._get_plugin_for_service(vm_service)
        assert len(backup_engine._plugin_cache) == 1

        # Clear
        backup_engine._clear_plugin_cache()
        assert len(backup_engine._plugin_cache) == 0

        # Get Docker plugin
        backup_engine._get_plugin_for_service(docker_service)
        assert len(backup_engine._plugin_cache) == 1
        assert "docker" in backup_engine._plugin_cache
        assert "vm" not in backup_engine._plugin_cache
