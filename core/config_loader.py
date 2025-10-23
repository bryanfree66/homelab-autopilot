"""
Configuration loader for Homelab Autopilot.

This module provides YAML configuration loading, validation using Pydantic,
and convenient dot-notation access to configuration values.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)


class HypervisorConfig(BaseModel):
    """Hypervisor configuration."""

    model_config = ConfigDict(extra="forbid")

    type: str = Field(..., description="Hypervisor type (e.g., 'proxmox')")
    host: str = Field(..., description="Hypervisor hostname or IP")
    username: str = Field(..., description="Username for authentication")
    password: Optional[str] = Field(None, description="Password for authentication")
    token_id: Optional[str] = Field(None, description="API token ID")
    token_secret: Optional[str] = Field(None, description="API token secret")
    verify_ssl: bool = Field(True, description="Verify SSL certificates")

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        """Validate hypervisor type."""
        allowed_types = ["proxmox", "esxi", "kvm"]
        if v.lower() not in allowed_types:
            raise ValueError(f"Hypervisor type must be one of {allowed_types}")
        return v.lower()


class ProxmoxBackupServerConfig(BaseModel):
    """Proxmox Backup Server configuration."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(False, description="Enable PBS integration")
    server: str = Field(..., description="PBS server hostname or IP")
    port: int = Field(8007, description="PBS API port")
    datastore: str = Field(..., description="PBS datastore name")
    username: str = Field(..., description="PBS username (e.g., root@pam)")
    password: Optional[str] = Field(None, description="PBS password")
    password_command: Optional[str] = Field(
        None, description="Command to retrieve password"
    )
    verify_ssl: bool = Field(True, description="Verify SSL certificates")

    @field_validator("port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Validate port is in valid range."""
        if v < 1 or v > 65535:
            raise ValueError("Port must be between 1 and 65535")
        return v

    @model_validator(mode="after")
    def validate_auth(self) -> "ProxmoxBackupServerConfig":
        """Ensure either password or password_command is provided."""
        if self.enabled and not self.password and not self.password_command:
            raise ValueError(
                "Either 'password' or 'password_command' must be provided for PBS"
            )
        return self


class DirectStorageConfig(BaseModel):
    """Direct storage backup configuration."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(False, description="Enable direct storage backups")
    path: Path = Field(..., description="Directory path for backups")
    format: str = Field("vma", description="Backup format (vma or tar)")

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: Path) -> Path:
        """Ensure path is absolute."""
        if not v.is_absolute():
            raise ValueError("Direct storage path must be absolute")
        return v

    @field_validator("format")
    @classmethod
    def validate_format(cls, v: str) -> str:
        """Validate backup format."""
        allowed_formats = ["vma", "tar"]
        if v.lower() not in allowed_formats:
            raise ValueError(f"Backup format must be one of {allowed_formats}")
        return v.lower()


class BackupConfig(BaseModel):
    """Backup configuration."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(True, description="Enable backups")
    root: Path = Field(..., description="Root directory for backups")
    retention_days: int = Field(30, description="Days to retain backups")
    compression: bool = Field(True, description="Enable compression")
    proxmox_backup_server: Optional[ProxmoxBackupServerConfig] = Field(
        None, description="Proxmox Backup Server configuration"
    )
    direct_storage: Optional[DirectStorageConfig] = Field(
        None, description="Direct storage backup configuration"
    )

    @field_validator("retention_days")
    @classmethod
    def validate_retention(cls, v: int) -> int:
        """Validate retention days is positive."""
        if v < 1:
            raise ValueError("Retention days must be at least 1")
        return v

    @field_validator("root")
    @classmethod
    def validate_root(cls, v: Path) -> Path:
        """Ensure root path is absolute."""
        if not v.is_absolute():
            raise ValueError("Backup root must be an absolute path")
        return v


class UpdateConfig(BaseModel):
    """Update configuration."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(True, description="Enable updates")
    auto_update: bool = Field(False, description="Automatically apply updates")
    check_interval_hours: int = Field(24, description="Hours between update checks")

    @field_validator("check_interval_hours")
    @classmethod
    def validate_interval(cls, v: int) -> int:
        """Validate check interval is reasonable."""
        if v < 1 or v > 168:  # Max 1 week
            raise ValueError("Check interval must be between 1 and 168 hours")
        return v


class MonitoringConfig(BaseModel):
    """Monitoring configuration."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(True, description="Enable monitoring")
    check_interval_minutes: int = Field(5, description="Minutes between health checks")

    @field_validator("check_interval_minutes")
    @classmethod
    def validate_interval(cls, v: int) -> int:
        """Validate check interval is reasonable."""
        if v < 1 or v > 1440:  # Max 1 day
            raise ValueError("Check interval must be between 1 and 1440 minutes")
        return v


class NotificationConfig(BaseModel):
    """Notification configuration."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(True, description="Enable notifications")
    type: str = Field(..., description="Notification type (e.g., 'email', 'slack')")
    settings: Dict[str, Any] = Field(
        default_factory=dict, description="Type-specific settings"
    )

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        """Validate notification type."""
        allowed_types = ["email", "slack", "discord", "webhook"]
        if v.lower() not in allowed_types:
            raise ValueError(f"Notification type must be one of {allowed_types}")
        return v.lower()


class GlobalConfig(BaseModel):
    """Global configuration section."""

    model_config = ConfigDict(extra="forbid")

    hypervisor: HypervisorConfig
    backup: BackupConfig
    update: UpdateConfig = Field(default_factory=UpdateConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    notification: NotificationConfig


class ServiceConfig(BaseModel):
    """Individual service configuration."""

    model_config = ConfigDict(
        extra="allow"
    )  # Allow extra fields for service-specific config

    # Core fields
    name: str = Field(..., description="Service name")
    type: str = Field(
        ..., description="Service type (e.g., 'docker', 'systemd', 'vm', 'lxc')"
    )
    enabled: bool = Field(True, description="Enable this service")
    backup: bool = Field(True, description="Include in backups")
    update: bool = Field(True, description="Include in updates")
    monitor: bool = Field(True, description="Include in monitoring")

    # Proxmox-specific fields (required for vm/lxc types)
    vmid: Optional[int] = Field(None, description="Proxmox VM/LXC ID (100-999999)")
    node: Optional[str] = Field(None, description="Proxmox node name")

    # Docker-specific fields
    container_name: Optional[str] = Field(None, description="Docker container name")
    compose_file: Optional[Path] = Field(None, description="Path to docker-compose.yml")

    # Systemd-specific fields
    service_name: Optional[str] = Field(
        None, description="Systemd service name (e.g., nginx.service)"
    )

    # Host-specific fields (for Proxmox host config backups)
    backup_paths: Optional[List[str]] = Field(
        None, description="Additional paths to backup for host type"
    )

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        """Validate service type."""
        allowed_types = ["docker", "systemd", "vm", "lxc", "generic", "host"]
        if v.lower() not in allowed_types:
            raise ValueError(f"Service type must be one of {allowed_types}")
        return v.lower()

    @field_validator("vmid")
    @classmethod
    def validate_vmid(cls, v: Optional[int]) -> Optional[int]:
        """Validate Proxmox VMID is in valid range."""
        if v is not None and (v < 100 or v > 999999):
            raise ValueError("Proxmox VMID must be between 100 and 999999")
        return v

    @model_validator(mode="after")
    def validate_proxmox_fields(self) -> "ServiceConfig":
        """Ensure Proxmox services have required fields."""
        if self.type in ["vm", "lxc"]:
            if self.vmid is None:
                raise ValueError(
                    f"Service '{self.name}' of type '{self.type}' requires 'vmid' field"
                )
            if self.node is None:
                raise ValueError(
                    f"Service '{self.name}' of type '{self.type}' requires 'node' field"
                )
        return self

    @model_validator(mode="after")
    def validate_docker_fields(self) -> "ServiceConfig":
        """Ensure Docker services have required fields."""
        if self.type == "docker" and self.container_name is None:
            raise ValueError(
                f"Service '{self.name}' of type 'docker' requires 'container_name' field"
            )
        return self

    @model_validator(mode="after")
    def validate_systemd_fields(self) -> "ServiceConfig":
        """Ensure systemd services have required fields."""
        if self.type == "systemd" and self.service_name is None:
            raise ValueError(
                f"Service '{self.name}' of type 'systemd' requires 'service_name' field"
            )
        return self


class HomeLabConfig(BaseModel):
    """Root configuration model for Homelab Autopilot."""

    model_config = ConfigDict(extra="forbid")

    # Use alias to handle 'global' reserved keyword
    global_config: GlobalConfig = Field(..., alias="global")
    services: List[ServiceConfig] = Field(default_factory=list)


class ConfigLoader:
    """
    Configuration loader with YAML parsing, Pydantic validation, and dot-notation access.

    Features:
    - Loads and validates YAML configuration files
    - Supports merging multiple configuration files
    - Provides dot-notation access (up to 5 levels deep)
    - Aggregates validation errors for better debugging

    Example:
        >>> loader = ConfigLoader(Path("config.yaml"))
        >>> hypervisor_type = loader.get("global.hypervisor.type")
        >>> services = loader.get_array("services")
    """

    MAX_DOT_DEPTH = 5

    def __init__(self, config_path: Path, merge_configs: Optional[List[Path]] = None):
        """
        Initialize ConfigLoader with a primary config file.

        Args:
            config_path: Path to the primary YAML configuration file
            merge_configs: Optional list of additional config files to merge

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValidationError: If configuration validation fails
            ValueError: If YAML parsing fails
        """
        self.config_path = config_path
        self.merge_configs = merge_configs or []
        self._raw_config: Dict[str, Any] = {}
        self._validated_config: Optional[HomeLabConfig] = None

        self._load_and_validate()

    def _load_yaml(self, path: Path) -> Dict[str, Any]:
        """
        Load a YAML file and return parsed content.

        Args:
            path: Path to YAML file

        Returns:
            Parsed YAML content as dictionary

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If YAML parsing fails
        """
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = yaml.safe_load(f)
                if content is None:
                    return {}
                if not isinstance(content, dict):
                    raise ValueError(
                        f"Configuration must be a YAML dictionary, got {type(content)}"
                    )
                return content
        except yaml.YAMLError as e:
            raise ValueError(f"Failed to parse YAML file {path}: {e}") from e

    def _merge_configs(
        self, base: Dict[str, Any], override: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Recursively merge two configuration dictionaries.

        Later values override earlier ones. Lists are replaced, not merged,
        EXCEPT for the 'services' list which is appended.

        Args:
            base: Base configuration dictionary
            override: Override configuration dictionary

        Returns:
            Merged configuration dictionary
        """
        result = base.copy()

        for key, value in override.items():
            if key == "services" and isinstance(value, list):
                # Special case: append services instead of replacing
                if key in result and isinstance(result[key], list):
                    result[key] = result[key] + value
                else:
                    result[key] = value
            elif (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                # Recursively merge nested dictionaries
                result[key] = self._merge_configs(result[key], value)
            else:
                # Override or add new key (including list replacement)
                result[key] = value

        return result

    def _load_and_validate(self) -> None:
        """
        Load all config files, merge them, and validate.

        Raises:
            FileNotFoundError: If any config file doesn't exist
            ValidationError: If validation fails
            ValueError: If YAML parsing fails
        """
        # Load primary config
        self._raw_config = self._load_yaml(self.config_path)

        # Merge additional configs
        for merge_path in self.merge_configs:
            merge_data = self._load_yaml(merge_path)
            self._raw_config = self._merge_configs(self._raw_config, merge_data)

        # Validate with Pydantic
        try:
            self._validated_config = HomeLabConfig.model_validate(self._raw_config)
        except ValidationError as e:
            # Re-raise with helpful context
            error_count = len(e.errors())
            error_msg = (
                f"Configuration validation failed with {error_count} error(s):\n"
            )
            for error in e.errors():
                loc = ".".join(str(l) for l in error["loc"])
                error_msg += f"  - {loc}: {error['msg']}\n"
            raise ValidationError.from_exception_data(
                title="Configuration Validation Failed", line_errors=e.errors()
            ) from e

    def _get_nested_value(
        self,
        data: Union[Dict[str, Any], BaseModel],
        keys: List[str],
        default: Any = None,
    ) -> Any:
        """
        Get nested value from dictionary or Pydantic model using key path.

        Args:
            data: Dictionary or Pydantic model to traverse
            keys: List of keys forming the path
            default: Default value if key path doesn't exist

        Returns:
            Value at the key path, or default if not found
        """
        current = data

        for key in keys:
            if isinstance(current, BaseModel):
                # Handle Pydantic models
                if not hasattr(current, key):
                    return default
                current = getattr(current, key)
            elif isinstance(current, dict):
                # Handle dictionaries
                if key not in current:
                    return default
                current = current[key]
            else:
                # Can't traverse further
                return default

        return current

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation.

        Supports up to 5 levels of nesting (e.g., "global.backup.retention_days").
        Special handling for 'global' which maps to 'global_config' internally.

        Args:
            key: Dot-separated key path (e.g., "global.hypervisor.type")
            default: Default value if key doesn't exist

        Returns:
            Configuration value, or default if not found

        Raises:
            ValueError: If key depth exceeds MAX_DOT_DEPTH

        Example:
            >>> loader.get("global.hypervisor.type")
            'proxmox'
            >>> loader.get("global.backup.retention_days", 30)
            30
        """
        if not self._validated_config:
            return default

        keys = key.split(".")

        if len(keys) > self.MAX_DOT_DEPTH:
            raise ValueError(
                f"Dot notation depth exceeds maximum of {self.MAX_DOT_DEPTH} levels: {key}"
            )

        # Handle 'global' alias mapping to 'global_config'
        if keys[0] == "global":
            keys[0] = "global_config"

        return self._get_nested_value(self._validated_config, keys, default)

    def get_array(self, key: str) -> List[Any]:
        """
        Get array/list of configuration values.

        Args:
            key: Dot-separated key path

        Returns:
            List of values, or empty list if not found or not a list

        Example:
            >>> loader.get_array("services")
            [ServiceConfig(...), ServiceConfig(...)]
        """
        value = self.get(key, [])
        if not isinstance(value, list):
            return []
        return value

    def validate(self) -> bool:
        """
        Check if configuration is valid.

        Returns:
            True if configuration is valid, False otherwise

        Note:
            Validation happens automatically during __init__.
            This method is provided for explicit validation checks.
        """
        return self._validated_config is not None

    def get_service_config(self, service_name: str) -> Optional[ServiceConfig]:
        """
        Get configuration for a specific service by name.

        Args:
            service_name: Name of the service to retrieve

        Returns:
            ServiceConfig object if found, None otherwise

        Example:
            >>> service = loader.get_service_config("plex")
            >>> if service:
            ...     print(service.type)
            'docker'
        """
        services = self.get_array("services")
        for service in services:
            if isinstance(service, ServiceConfig) and service.name == service_name:
                return service
        return None

    def get_all_services(self) -> List[ServiceConfig]:
        """
        Get all service configurations.

        Returns:
            List of ServiceConfig objects
        """
        return self.get_array("services")

    def get_raw_config(self) -> Dict[str, Any]:
        """
        Get the raw, unvalidated configuration dictionary.

        Useful for debugging or accessing non-standard fields.

        Returns:
            Raw configuration dictionary
        """
        return self._raw_config.copy()
