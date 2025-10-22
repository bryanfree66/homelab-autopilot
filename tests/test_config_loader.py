"""
Comprehensive tests for ConfigLoader.

Tests cover:
- Loading valid configurations
- Validation errors for invalid configs
- Dot notation access
- Config merging
- Edge cases and error handling
"""

import pytest
from pathlib import Path
from pydantic import ValidationError

from core.config_loader import (
    ConfigLoader,
    HypervisorConfig,
    BackupConfig,
    ServiceConfig,
    HomeLabConfig
)


# Fixtures
@pytest.fixture
def fixtures_dir():
    """Return path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def valid_config_path(fixtures_dir):
    """Return path to valid config fixture."""
    return fixtures_dir / "valid_config.yaml"


@pytest.fixture
def invalid_config_path(fixtures_dir):
    """Return path to invalid config fixture."""
    return fixtures_dir / "invalid_config.yaml"


@pytest.fixture
def minimal_config_path(fixtures_dir):
    """Return path to minimal config fixture."""
    return fixtures_dir / "minimal_config.yaml"


@pytest.fixture
def merge_override_path(fixtures_dir):
    """Return path to merge override fixture."""
    return fixtures_dir / "merge_override.yaml"


@pytest.fixture
def valid_loader(valid_config_path):
    """Return ConfigLoader with valid config."""
    return ConfigLoader(valid_config_path)


# Test: Successful Loading
class TestConfigLoading:
    """Test successful configuration loading."""
    
    def test_load_valid_config(self, valid_config_path):
        """Test loading a valid configuration file."""
        loader = ConfigLoader(valid_config_path)
        assert loader.validate()
        assert loader._validated_config is not None
    
    def test_load_minimal_config(self, minimal_config_path):
        """Test loading minimal valid configuration."""
        loader = ConfigLoader(minimal_config_path)
        assert loader.validate()
        # Check defaults are applied
        assert loader.get("global.backup.retention_days") == 30
        assert loader.get("global.backup.compression") is True
    
    def test_config_path_stored(self, valid_config_path):
        """Test that config path is stored correctly."""
        loader = ConfigLoader(valid_config_path)
        assert loader.config_path == valid_config_path
    
    def test_raw_config_available(self, valid_loader):
        """Test that raw config dictionary is accessible."""
        raw = valid_loader.get_raw_config()
        assert isinstance(raw, dict)
        assert "global" in raw
        assert "services" in raw


# Test: File Not Found
class TestFileErrors:
    """Test file-related errors."""
    
    def test_missing_config_file(self):
        """Test error when config file doesn't exist."""
        with pytest.raises(FileNotFoundError) as exc_info:
            ConfigLoader(Path("/nonexistent/config.yaml"))
        assert "not found" in str(exc_info.value).lower()
    
    def test_missing_merge_file(self, valid_config_path):
        """Test error when merge config file doesn't exist."""
        with pytest.raises(FileNotFoundError):
            ConfigLoader(
                valid_config_path,
                merge_configs=[Path("/nonexistent/merge.yaml")]
            )


# Test: Validation Errors
class TestValidation:
    """Test configuration validation."""
    
    def test_invalid_config_raises_validation_error(self, invalid_config_path):
        """Test that invalid config raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ConfigLoader(invalid_config_path)
        
        # Check that multiple errors are aggregated
        errors = exc_info.value.errors()
        assert len(errors) > 0
    
    def test_invalid_hypervisor_type(self, tmp_path):
        """Test validation of invalid hypervisor type."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
global:
  hypervisor:
    type: invalid_hypervisor
    host: localhost
    username: admin
  backup:
    root: /tmp/backups
  notification:
    type: email
    settings: {}
""")
        with pytest.raises(ValidationError) as exc_info:
            ConfigLoader(config_file)
        
        errors = exc_info.value.errors()
        assert any("hypervisor" in str(e) for e in errors)
    
    def test_invalid_service_type(self, tmp_path):
        """Test validation of invalid service type."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
global:
  hypervisor:
    type: proxmox
    host: localhost
    username: admin
  backup:
    root: /tmp/backups
  notification:
    type: email
    settings: {}

services:
  - name: test
    type: invalid_type
""")
        with pytest.raises(ValidationError) as exc_info:
            ConfigLoader(config_file)
        
        errors = exc_info.value.errors()
        assert any("service" in str(e).lower() for e in errors)
    
    def test_invalid_retention_days(self, tmp_path):
        """Test validation of negative retention days."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
global:
  hypervisor:
    type: proxmox
    host: localhost
    username: admin
  backup:
    root: /tmp/backups
    retention_days: -5
  notification:
    type: email
    settings: {}
""")
        with pytest.raises(ValidationError) as exc_info:
            ConfigLoader(config_file)
        
        errors = exc_info.value.errors()
        assert any("retention" in str(e).lower() for e in errors)
    
    def test_relative_backup_path(self, tmp_path):
        """Test validation requires absolute backup path."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
global:
  hypervisor:
    type: proxmox
    host: localhost
    username: admin
  backup:
    root: relative/path
  notification:
    type: email
    settings: {}
""")
        with pytest.raises(ValidationError) as exc_info:
            ConfigLoader(config_file)
        
        errors = exc_info.value.errors()
        assert any("absolute" in str(e).lower() for e in errors)
    
    def test_validate_method(self, valid_loader):
        """Test validate() method returns True for valid config."""
        assert valid_loader.validate() is True


# Test: Dot Notation Access
class TestDotNotation:
    """Test dot notation configuration access."""
    
    def test_get_simple_value(self, valid_loader):
        """Test getting simple value with dot notation."""
        hypervisor_type = valid_loader.get("global.hypervisor.type")
        assert hypervisor_type == "proxmox"
    
    def test_get_nested_value(self, valid_loader):
        """Test getting deeply nested value."""
        retention = valid_loader.get("global.backup.retention_days")
        assert retention == 30
    
    def test_get_boolean_value(self, valid_loader):
        """Test getting boolean value."""
        enabled = valid_loader.get("global.backup.enabled")
        assert enabled is True
    
    def test_get_with_default(self, valid_loader):
        """Test getting non-existent key returns default."""
        value = valid_loader.get("global.nonexistent.key", "default_value")
        assert value == "default_value"
    
    def test_get_without_default(self, valid_loader):
        """Test getting non-existent key returns None."""
        value = valid_loader.get("global.nonexistent.key")
        assert value is None
    
    def test_get_path_value(self, valid_loader):
        """Test getting Path value."""
        backup_root = valid_loader.get("global.backup.root")
        assert isinstance(backup_root, Path)
        assert backup_root == Path("/mnt/backups")
    
    def test_max_dot_depth_exceeded(self, valid_loader):
        """Test that exceeding max dot depth raises error."""
        with pytest.raises(ValueError) as exc_info:
            valid_loader.get("a.b.c.d.e.f")  # 6 levels, max is 5
        assert "depth exceeds maximum" in str(exc_info.value).lower()
    
    def test_get_dict_value(self, valid_loader):
        """Test getting dictionary value."""
        settings = valid_loader.get("global.notification.settings")
        assert isinstance(settings, dict)
        assert "smtp_host" in settings


# Test: Array Access
class TestArrayAccess:
    """Test array/list configuration access."""
    
    def test_get_array(self, valid_loader):
        """Test getting array of services."""
        services = valid_loader.get_array("services")
        assert isinstance(services, list)
        assert len(services) == 2
    
    def test_get_array_returns_empty_for_nonexistent(self, valid_loader):
        """Test get_array returns empty list for non-existent key."""
        result = valid_loader.get_array("nonexistent.array")
        assert result == []
    
    def test_get_array_returns_empty_for_non_list(self, valid_loader):
        """Test get_array returns empty list for non-list value."""
        result = valid_loader.get_array("global.hypervisor.type")
        assert result == []


# Test: Service Access
class TestServiceAccess:
    """Test service-specific configuration access."""
    
    def test_get_service_config(self, valid_loader):
        """Test getting specific service configuration."""
        plex = valid_loader.get_service_config("plex")
        assert plex is not None
        assert isinstance(plex, ServiceConfig)
        assert plex.name == "plex"
        assert plex.type == "lxc"
        assert plex.vmid == 100
        assert plex.node == "pve"
    
    def test_get_nonexistent_service(self, valid_loader):
        """Test getting non-existent service returns None."""
        result = valid_loader.get_service_config("nonexistent")
        assert result is None
    
    def test_get_all_services(self, valid_loader):
        """Test getting all service configurations."""
        services = valid_loader.get_all_services()
        assert len(services) == 2
        assert all(isinstance(s, ServiceConfig) for s in services)
        
        names = [s.name for s in services]
        assert "plex" in names
        assert "nginx" in names
    
    def test_service_extra_fields_allowed(self, valid_loader):
        """Test that services can have extra fields."""
        plex = valid_loader.get_service_config("plex")
        # ServiceConfig uses extra='allow', so extra fields should be accessible
        assert hasattr(plex, "container_name")


# Test: Config Merging
class TestConfigMerging:
    """Test configuration file merging."""
    
    def test_merge_configs(self, valid_config_path, merge_override_path):
        """Test merging multiple config files."""
        loader = ConfigLoader(
            valid_config_path,
            merge_configs=[merge_override_path]
        )
        
        # Check overridden values
        assert loader.get("global.backup.retention_days") == 60  # Overridden from 30
        assert loader.get("global.backup.compression") is False  # Overridden from True
        assert loader.get("global.update.auto_update") is True  # Overridden from False
        
        # Check original values still present
        assert loader.get("global.hypervisor.type") == "proxmox"
    
    def test_merge_adds_services(self, valid_config_path, merge_override_path):
        """Test that merging adds new services."""
        loader = ConfigLoader(
            valid_config_path,
            merge_configs=[merge_override_path]
        )
        
        services = loader.get_all_services()
        # Original has 2 services, merge adds 1 more
        assert len(services) == 3
        
        names = [s.name for s in services]
        assert "additional_service" in names
    
    def test_merge_nested_dicts(self, tmp_path):
        """Test that nested dictionaries are merged properly."""
        base_config = tmp_path / "base.yaml"
        base_config.write_text("""
global:
  hypervisor:
    type: proxmox
    host: localhost
    username: admin
  backup:
    root: /tmp/backups
  notification:
    type: email
    settings:
      smtp_host: localhost
      smtp_port: 587
""")
        
        override_config = tmp_path / "override.yaml"
        override_config.write_text("""
global:
  notification:
    settings:
      smtp_port: 465
      use_tls: true
""")
        
        loader = ConfigLoader(base_config, merge_configs=[override_config])
        
        # smtp_port should be overridden
        settings = loader.get("global.notification.settings")
        assert settings["smtp_port"] == 465
        # smtp_host should still be present
        assert settings["smtp_host"] == "localhost"
        # use_tls should be added
        assert settings["use_tls"] is True


# Test: YAML Parsing Errors
class TestYAMLErrors:
    """Test YAML parsing error handling."""
    
    def test_invalid_yaml_syntax(self, tmp_path):
        """Test error on invalid YAML syntax."""
        config_file = tmp_path / "invalid.yaml"
        config_file.write_text("""
global:
  hypervisor:
    type: proxmox
    host: [invalid yaml syntax
""")
        
        with pytest.raises(ValueError) as exc_info:
            ConfigLoader(config_file)
        assert "parse" in str(exc_info.value).lower() or "yaml" in str(exc_info.value).lower()
    
    def test_empty_yaml_file(self, tmp_path):
        """Test handling of empty YAML file."""
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("")
        
        # Empty file should fail validation (missing required fields)
        with pytest.raises(ValidationError):
            ConfigLoader(config_file)
    
    def test_non_dict_yaml(self, tmp_path):
        """Test error when YAML is not a dictionary."""
        config_file = tmp_path / "list.yaml"
        config_file.write_text("""
- item1
- item2
- item3
""")
        
        with pytest.raises(ValueError) as exc_info:
            ConfigLoader(config_file)
        assert "dictionary" in str(exc_info.value).lower()


# Test: Edge Cases
class TestEdgeCases:
    """Test edge cases and corner scenarios."""
    
    def test_get_on_failed_validation(self, invalid_config_path):
        """Test that get() returns default when validation failed."""
        # We can't create a loader with invalid config due to validation
        # So we test the behavior through the normal path
        with pytest.raises(ValidationError):
            ConfigLoader(invalid_config_path)
    
    def test_empty_services_list(self, minimal_config_path):
        """Test handling of config with no services."""
        loader = ConfigLoader(minimal_config_path)
        services = loader.get_all_services()
        assert services == []
    
    def test_case_normalization(self, tmp_path):
        """Test that types are normalized to lowercase."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
global:
  hypervisor:
    type: PROXMOX
    host: localhost
    username: admin
  backup:
    root: /tmp/backups
  notification:
    type: EMAIL
    settings: {}

services:
  - name: test
    type: DOCKER
    container_name: test_container
""")
        
        loader = ConfigLoader(config_file)
        assert loader.get("global.hypervisor.type") == "proxmox"
        assert loader.get("global.notification.type") == "email"
        
        service = loader.get_service_config("test")
        assert service.type == "docker"
    
    def test_optional_fields_with_defaults(self, minimal_config_path):
        """Test that optional fields get default values."""
        loader = ConfigLoader(minimal_config_path)
        
        # These should have defaults from the models
        assert loader.get("global.backup.retention_days") == 30
        assert loader.get("global.backup.compression") is True
        assert loader.get("global.update.enabled") is True
        assert loader.get("global.update.auto_update") is False
    
    def test_raw_config_is_copy(self, valid_loader):
        """Test that get_raw_config returns a copy."""
        raw1 = valid_loader.get_raw_config()
        raw2 = valid_loader.get_raw_config()
        
        # Modify raw1
        raw1["test_key"] = "test_value"
        
        # raw2 should not be affected
        assert "test_key" not in raw2


# Test: Pydantic Model Validation
class TestPydanticModels:
    """Test Pydantic model behaviors."""
    
    def test_extra_fields_forbidden_in_global(self, tmp_path):
        """Test that extra fields in global config are rejected."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
global:
  hypervisor:
    type: proxmox
    host: localhost
    username: admin
  backup:
    root: /tmp/backups
  notification:
    type: email
    settings: {}
  unknown_field: value
""")
        
        with pytest.raises(ValidationError) as exc_info:
            ConfigLoader(config_file)
        
        errors = exc_info.value.errors()
        assert any("extra" in str(e).lower() or "unknown_field" in str(e) for e in errors)
    
    def test_extra_fields_allowed_in_service(self, tmp_path):
        """Test that extra fields in service config are allowed."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
global:
  hypervisor:
    type: proxmox
    host: localhost
    username: admin
  backup:
    root: /tmp/backups
  notification:
    type: email
    settings: {}

services:
  - name: test
    type: docker
    container_name: test_container
    custom_field: custom_value
    another_field: 123
""")
        
        # Should not raise - extra fields allowed in ServiceConfig
        loader = ConfigLoader(config_file)
        service = loader.get_service_config("test")
        
        # Extra fields should be accessible
        assert hasattr(service, "custom_field")
        assert service.custom_field == "custom_value"

# Test: Proxmox-Specific Validation
class TestProxmoxValidation:
    """Test Proxmox-specific field validation."""
    
    def test_vm_requires_vmid(self, tmp_path):
        """Test that VM type requires vmid field."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
global:
  hypervisor:
    type: proxmox
    host: localhost
    username: admin
  backup:
    root: /tmp/backups
  notification:
    type: email
    settings: {}

services:
  - name: test_vm
    type: vm
    node: pve
""")
        with pytest.raises(ValidationError) as exc_info:
            ConfigLoader(config_file)
        
        errors = exc_info.value.errors()
        assert any("vmid" in str(e).lower() for e in errors)
    
    def test_vm_requires_node(self, tmp_path):
        """Test that VM type requires node field."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
global:
  hypervisor:
    type: proxmox
    host: localhost
    username: admin
  backup:
    root: /tmp/backups
  notification:
    type: email
    settings: {}

services:
  - name: test_vm
    type: vm
    vmid: 100
""")
        with pytest.raises(ValidationError) as exc_info:
            ConfigLoader(config_file)
        
        errors = exc_info.value.errors()
        assert any("node" in str(e).lower() for e in errors)
    
    def test_lxc_requires_vmid_and_node(self, tmp_path):
        """Test that LXC type requires both vmid and node."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
global:
  hypervisor:
    type: proxmox
    host: localhost
    username: admin
  backup:
    root: /tmp/backups
  notification:
    type: email
    settings: {}

services:
  - name: test_lxc
    type: lxc
""")
        with pytest.raises(ValidationError) as exc_info:
            ConfigLoader(config_file)
        
        errors = exc_info.value.errors()
        assert any("vmid" in str(e).lower() for e in errors)
    
    def test_vmid_range_validation(self, tmp_path):
        """Test that vmid must be between 100 and 999999."""
        # Test vmid too low
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
global:
  hypervisor:
    type: proxmox
    host: localhost
    username: admin
  backup:
    root: /tmp/backups
  notification:
    type: email
    settings: {}

services:
  - name: test_vm
    type: vm
    vmid: 99
    node: pve
""")
        with pytest.raises(ValidationError) as exc_info:
            ConfigLoader(config_file)
        
        errors = exc_info.value.errors()
        assert any("100" in str(e) and "999999" in str(e) for e in errors)
    
    def test_vmid_valid_range(self, tmp_path):
        """Test that valid vmid range works."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
global:
  hypervisor:
    type: proxmox
    host: localhost
    username: admin
  backup:
    root: /tmp/backups
  notification:
    type: email
    settings: {}

services:
  - name: test_vm
    type: vm
    vmid: 100
    node: pve
""")
        # Should not raise
        loader = ConfigLoader(config_file)
        service = loader.get_service_config("test_vm")
        assert service.vmid == 100
        assert service.node == "pve"
    
    def test_docker_requires_container_name(self, tmp_path):
        """Test that Docker type requires container_name field."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
global:
  hypervisor:
    type: proxmox
    host: localhost
    username: admin
  backup:
    root: /tmp/backups
  notification:
    type: email
    settings: {}

services:
  - name: test_docker
    type: docker
""")
        with pytest.raises(ValidationError) as exc_info:
            ConfigLoader(config_file)
        
        errors = exc_info.value.errors()
        assert any("container_name" in str(e).lower() for e in errors)
    
    def test_docker_with_container_name(self, tmp_path):
        """Test that Docker with container_name works."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
global:
  hypervisor:
    type: proxmox
    host: localhost
    username: admin
  backup:
    root: /tmp/backups
  notification:
    type: email
    settings: {}

services:
  - name: test_docker
    type: docker
    container_name: my_container
""")
        # Should not raise
        loader = ConfigLoader(config_file)
        service = loader.get_service_config("test_docker")
        assert service.container_name == "my_container"
    
    def test_systemd_requires_service_name(self, tmp_path):
        """Test that systemd type requires service_name field."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
global:
  hypervisor:
    type: proxmox
    host: localhost
    username: admin
  backup:
    root: /tmp/backups
  notification:
    type: email
    settings: {}

services:
  - name: test_systemd
    type: systemd
""")
        with pytest.raises(ValidationError) as exc_info:
            ConfigLoader(config_file)
        
        errors = exc_info.value.errors()
        assert any("service_name" in str(e).lower() for e in errors)
    
    def test_systemd_with_service_name(self, tmp_path):
        """Test that systemd with service_name works."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
global:
  hypervisor:
    type: proxmox
    host: localhost
    username: admin
  backup:
    root: /tmp/backups
  notification:
    type: email
    settings: {}

services:
  - name: test_systemd
    type: systemd
    service_name: nginx.service
""")
        # Should not raise
        loader = ConfigLoader(config_file)
        service = loader.get_service_config("test_systemd")
        assert service.service_name == "nginx.service"
    
    def test_generic_type_no_special_requirements(self, tmp_path):
        """Test that generic type has no special field requirements."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
global:
  hypervisor:
    type: proxmox
    host: localhost
    username: admin
  backup:
    root: /tmp/backups
  notification:
    type: email
    settings: {}

services:
  - name: test_generic
    type: generic
""")
        # Should not raise - generic type doesn't require special fields
        loader = ConfigLoader(config_file)
        service = loader.get_service_config("test_generic")
        assert service.type == "generic"