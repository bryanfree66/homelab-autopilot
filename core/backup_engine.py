"""
Backup Engine for Homelab Autopilot.

This module orchestrates backup operations across all configured services,
supporting multiple backup strategies including Proxmox Backup Server (PBS),
direct storage, and file-based backups.
"""

# pylint: disable=too-many-lines

import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union

import requests

from core.config_loader import ConfigLoader, ServiceConfig
from lib.logger import get_logger
from lib.state_manager import StateError, StateManager
from plugins.base import HypervisorPlugin, ServicePlugin
from plugins.hypervisors.proxmox import ProxmoxPlugin
from plugins.services.generic import GenericServicePlugin


class BackupError(Exception):
    """
    Exception raised for backup-related errors.

    Used for invalid backup configurations, failed operations, and other
    backup problems that should fail fast or require attention.
    """


class BackupEngine:
    """
    Orchestrates backup operations across all services.

    Supports multiple backup strategies:
    - Proxmox Backup Server (PBS) for VMs/LXCs
    - Direct storage (vzdump to directory)
    - Config/file backups for services

    Attributes:
        config: Configuration loader instance
        state: State manager for tracking backups
        dry_run: If True, simulate backups without executing
        logger: Logger instance
    """

    def __init__(
        self,
        config_loader: ConfigLoader,
        state_manager: StateManager,
        dry_run: bool = False,
    ):
        """
        Initialize BackupEngine.

        Args:
            config_loader: Configuration loader instance
            state_manager: State manager for tracking backups
            dry_run: If True, simulate backups without executing

        Raises:
            BackupError: If backup configuration is invalid or missing

        Example:
            >>> config = ConfigLoader(Path("config.yaml"))
            >>> state = StateManager(Path("state.db"))
            >>> engine = BackupEngine(config, state)
        """
        self.config = config_loader
        self.state = state_manager
        self.dry_run = dry_run
        self.logger = get_logger()
        self._plugin_cache: Dict[str, Union[HypervisorPlugin, ServicePlugin]] = {}
        self._backup_config_cache: Optional[Dict[str, Any]] = None

        # Validate backup configuration on initialization (fail fast)
        self._validate_backup_config()

        if self.dry_run:
            self.logger.info("BackupEngine initialized in DRY RUN mode")
        else:
            self.logger.info("BackupEngine initialized")

    def _validate_backup_config(self) -> None:
        """
        Validate backup configuration on initialization.

        Ensures required backup settings exist and are valid.

        Raises:
            BackupError: If backup configuration is invalid or missing required values
        """
        # Check if backup is enabled
        backup_enabled = self.config.get("global.backup.enabled", True)
        if not backup_enabled:
            self.logger.warning("Backup is disabled in configuration")
            return

        # Validate backup root path exists
        try:
            backup_root = self.config.get("global.backup.root")
            if not backup_root:
                raise BackupError(
                    "Backup root path (global.backup.root) is required but not configured"
                )

            backup_path = Path(backup_root)
            if not backup_path.is_absolute():
                raise BackupError(f"Backup root path must be absolute: {backup_root}")

        except Exception as e:
            if isinstance(e, BackupError):
                raise
            raise BackupError(
                f"Invalid backup configuration: {e}. "
                "Please ensure global.backup.root is set in your configuration."
            ) from e

        # Validate retention policy
        retention_days = self.config.get("global.backup.retention_days")
        if retention_days is not None:
            if not isinstance(retention_days, int) or retention_days < 1:
                raise BackupError(
                    f"Backup retention_days must be a positive integer, got: {retention_days}"
                )

        self.logger.debug("Backup configuration validated successfully")

    # ========================================================================
    # Main Orchestration Methods
    # ========================================================================

    def backup_all_services(self) -> Dict[str, bool]:
        """
        Backup all enabled services with backup=true.

        Iterates through all configured services, backs them up sequentially,
        and sends a single summary notification at completion.

        Returns:
            Dict mapping service_name -> success status
            Example: {"nextcloud": True, "adguard": False, "plex": True}

        Example:
            >>> engine = BackupEngine(config, state)
            >>> results = engine.backup_all_services()
            >>> print(f"Backed up {sum(results.values())} services successfully")
        """
        raise NotImplementedError

    def backup_service(self, service_name: str) -> bool:
        """
        Backup a specific service by name.

        Args:
            service_name: Name of service to backup

        Returns:
            True if backup succeeded, False otherwise

        Raises:
            ValueError: If service not found in configuration

        Example:
            >>> engine = BackupEngine(config, state)
            >>> success = engine.backup_service("nextcloud")
            >>> if success:
            ...     print("Backup completed successfully")
        """
        raise NotImplementedError

    # ========================================================================
    # Plugin Management
    # ========================================================================

    def _get_plugin_for_service(
        self, service: ServiceConfig
    ) -> Union[HypervisorPlugin, ServicePlugin]:
        """
        Get appropriate plugin for service type.

        Plugins are cached to avoid re-instantiation. Routes to:
        - HypervisorPlugin for vm/lxc types (e.g., ProxmoxPlugin)
        - ServicePlugin for docker/systemd/generic types

        Args:
            service: Service configuration

        Returns:
            Plugin instance (cached)

        Raises:
            ValueError: If no plugin found for service type

        Example:
            >>> service = config.get_service_config("nextcloud")
            >>> plugin = engine._get_plugin_for_service(service)
            >>> print(plugin.name)
        """
        # Validate service type
        service_type = service.type
        if not service_type:
            raise ValueError(
                f"Service '{service.name}' has no type defined. "
                f"Service type is required for plugin selection."
            )

        service_type = service_type.lower()

        # Check cache first
        if service_type in self._plugin_cache:
            self.logger.debug(f"Using cached plugin for service type '{service_type}'")
            return self._plugin_cache[service_type]

        # Define supported service types
        hypervisor_types = ["vm", "lxc"]
        service_types = ["docker", "systemd", "generic"]
        supported_types = hypervisor_types + service_types

        # Validate service type is supported
        if service_type not in supported_types:
            raise ValueError(
                f"Unsupported service type '{service_type}' for service '{service.name}'. "
                f"Supported types: {', '.join(supported_types)}"
            )

        # Instantiate appropriate plugin based on service type
        plugin: Union[HypervisorPlugin, ServicePlugin]

        if service_type in hypervisor_types:
            # Use ProxmoxPlugin for VM/LXC types
            self.logger.debug(
                f"Instantiating ProxmoxPlugin for service type '{service_type}'"
            )
            plugin = ProxmoxPlugin(config=self.config, state=self.state)

        elif service_type in service_types:
            # Use GenericServicePlugin for Docker/systemd/generic types
            self.logger.debug(
                f"Instantiating GenericServicePlugin for service type '{service_type}'"
            )
            plugin = GenericServicePlugin(config=self.config, state=self.state)

        else:
            # Should never reach here due to validation above, but for safety
            raise ValueError(
                f"Unable to determine plugin for service type '{service_type}'"
            )

        # Cache the plugin
        self._plugin_cache[service_type] = plugin
        self.logger.debug(f"Cached {plugin.name} for service type '{service_type}'")

        return plugin

    def _clear_plugin_cache(self) -> None:
        """
        Clear the plugin cache.

        Useful for testing or when configuration changes require
        plugin re-initialization.

        Example:
            >>> engine._clear_plugin_cache()
        """
        self._plugin_cache.clear()
        self.logger.debug("Plugin cache cleared")

    # ========================================================================
    # Backup Operations
    # ========================================================================

    # pylint: disable=too-many-locals
    def _determine_backup_destination(self, service: ServiceConfig) -> Dict[str, Any]:
        """
        Determine where and how to backup based on configuration.

        Implements the backup decision logic:
        - For VM/LXC: Check PBS -> direct storage -> fallback to root
        - For other services: Use backup root

        Args:
            service: Service configuration

        Returns:
            Dict with backup strategy details:
                {
                    'method': 'pbs' | 'direct' | 'local',
                    'path': Path to backup location,
                    'pbs_config': PBS config dict (if method='pbs'),
                }

        Raises:
            BackupError: If PBS is enabled but config is incomplete or unreachable,
                        or if direct_storage is enabled but path is not configured

        Example:
            >>> service = config.get_service_config("nextcloud")
            >>> dest = engine._determine_backup_destination(service)
            >>> print(dest['method'])  # 'pbs' or 'direct' or 'local'
        """
        backup_config = self._get_backup_config()
        service_type = service.type.lower()

        # For VM/LXC types, check PBS -> direct storage -> local
        if service_type in ["vm", "lxc"]:
            # 1a. Check PBS first
            pbs_config = backup_config.get("proxmox_backup_server")
            if pbs_config and pbs_config.get("enabled"):
                self.logger.debug(
                    f"Service '{service.name}' ({service_type}): Checking PBS configuration"
                )

                # Validate PBS config is complete
                required_fields = ["server", "datastore", "username"]
                missing_fields = [
                    field for field in required_fields if not pbs_config.get(field)
                ]
                if missing_fields:
                    raise BackupError(
                        f"PBS is enabled but configuration is incomplete. "
                        f"Missing required fields: {', '.join(missing_fields)}. "
                        f"Please update global.backup.proxmox_backup_server in your configuration."
                    )

                # Validate PBS connectivity
                server = pbs_config["server"]
                port = pbs_config.get("port", 8007)
                verify_ssl = pbs_config.get("verify_ssl", True)

                self.logger.debug(f"Validating PBS connectivity to {server}:{port}")

                try:
                    # Use a lightweight API endpoint to test connectivity
                    url = f"https://{server}:{port}/api2/json/version"
                    response = requests.get(url, verify=verify_ssl, timeout=5)
                    response.raise_for_status()

                    self.logger.info(
                        f"Service '{service.name}': Using PBS at {server}:{port}"
                    )

                    return {
                        "method": "pbs",
                        "pbs_config": pbs_config,
                    }

                except requests.exceptions.Timeout as exc:
                    raise BackupError(
                        f"PBS connectivity check failed: Connection to {server}:{port} timed out after 5 seconds. "
                        f"Please verify the server is reachable and the configuration is correct."
                    ) from exc
                except requests.exceptions.ConnectionError as e:
                    raise BackupError(
                        f"PBS connectivity check failed: Cannot connect to {server}:{port}. "
                        f"Error: {e}. Please verify the server address and network connectivity."
                    ) from e
                except requests.exceptions.RequestException as e:
                    raise BackupError(
                        f"PBS connectivity check failed for {server}:{port}: {e}. "
                        f"Please verify the PBS server is running and accessible."
                    ) from e

            # 1b. Check direct storage next
            direct_config = backup_config.get("direct_storage")
            if direct_config and direct_config.get("enabled"):
                self.logger.debug(
                    f"Service '{service.name}' ({service_type}): Checking direct storage configuration"
                )

                # Validate that path is configured
                direct_path = direct_config.get("path")
                if not direct_path:
                    raise BackupError(
                        "Direct storage is enabled but path is not configured. "
                        "Please set global.backup.direct_storage.path in your configuration."
                    )

                # Cluster safety: Warn if path doesn't look like shared storage
                path_str = str(direct_path)
                shared_prefixes = ["/mnt", "/nfs", "/ceph"]
                is_shared = any(
                    path_str.startswith(prefix) for prefix in shared_prefixes
                )

                if not is_shared:
                    self.logger.warning(
                        f"Direct storage path '{path_str}' does not appear to be on shared storage "
                        f"(expected path starting with {', '.join(shared_prefixes)}). "
                        f"In a cluster environment, this may cause backups to be inaccessible from other nodes."
                    )

                self.logger.info(
                    f"Service '{service.name}': Using direct storage at {direct_path}"
                )

                return {
                    "method": "direct",
                    "path": direct_path,
                }

            # 1c. Fallback to local
            self.logger.debug(
                f"Service '{service.name}' ({service_type}): Using local backup (fallback)"
            )

        # For other service types (docker, systemd, generic, host), always use local
        else:
            self.logger.debug(
                f"Service '{service.name}' ({service_type}): Using local backup"
            )

        # Return local backup configuration
        backup_root = backup_config["root"]
        return {
            "method": "local",
            "path": backup_root,
        }

    # pylint: disable=too-many-branches
    def _create_backup_metadata(
        self,
        service: ServiceConfig,
        backup_destination: Dict[str, Any],
        backup_path: Optional[Path] = None,
        duration_seconds: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Create metadata dictionary for a backup operation.

        Generates comprehensive metadata for tracking, auditing, and RTO analysis.
        All metadata is JSON-serializable for storage in state DB or logs.

        Args:
            service: Service configuration
            backup_destination: Output from _determine_backup_destination()
            backup_path: Actual backup file path (if applicable, e.g., for direct/local)
            duration_seconds: Backup operation duration for RTO tracking

        Returns:
            Dict containing backup metadata with all relevant fields.
            All values are JSON-serializable.

        Example:
            >>> service = config.get_service_config("nextcloud")
            >>> destination = engine._determine_backup_destination(service)
            >>> metadata = engine._create_backup_metadata(
            ...     service, destination, Path("/mnt/backups/nextcloud.tar.gz"), 45.2
            ... )
            >>> print(metadata['service_name'])  # 'nextcloud'
            >>> print(metadata['backup_method'])  # 'pbs' or 'direct' or 'local'
        """
        # Extract basic service information
        metadata: Dict[str, Any] = {
            "service_name": service.name,
            "service_type": service.type.lower(),
            "backup_method": backup_destination["method"],
            "timestamp": datetime.now().isoformat(),
            "status": "pending",  # Initial status, updated later by backup operation
        }

        # Add backup path if provided
        if backup_path is not None:
            metadata["backup_path"] = str(backup_path)

            # Calculate file size if path exists
            try:
                if backup_path.exists():
                    metadata["file_size_bytes"] = backup_path.stat().st_size
                    self.logger.debug(
                        f"Backup file size for {service.name}: {metadata['file_size_bytes']} bytes"
                    )
                else:
                    metadata["file_size_bytes"] = None
                    self.logger.debug(
                        f"Backup path {backup_path} does not exist yet, file_size set to None"
                    )
            except PermissionError as e:
                self.logger.warning(
                    f"Permission denied when checking backup file size for {backup_path}: {e}. "
                    f"Setting file_size_bytes to None."
                )
                metadata["file_size_bytes"] = None
            except OSError as e:
                self.logger.warning(
                    f"Error accessing backup file {backup_path}: {e}. "
                    f"Setting file_size_bytes to None."
                )
                metadata["file_size_bytes"] = None
        else:
            metadata["backup_path"] = None
            metadata["file_size_bytes"] = None

        # Add duration if provided
        if duration_seconds is not None:
            metadata["duration_seconds"] = duration_seconds
        else:
            metadata["duration_seconds"] = None

        # Add VM/LXC specific fields
        if service.type.lower() in ["vm", "lxc"]:
            if service.vmid is not None:
                metadata["vmid"] = service.vmid
            else:
                metadata["vmid"] = None
                self.logger.debug(
                    f"Service {service.name} is type {service.type} but has no vmid"
                )

            # Add node as hint (cluster-safe: not authoritative)
            if service.node is not None:
                metadata["node"] = service.node
            else:
                metadata["node"] = None
                self.logger.debug(f"Service {service.name} has no node specified")
        else:
            # Non-VM/LXC services don't have vmid or node
            metadata["vmid"] = None
            metadata["node"] = None

        # Add PBS-specific details if using PBS backup
        if backup_destination["method"] == "pbs":
            pbs_config = backup_destination.get("pbs_config", {})
            metadata["pbs_details"] = {
                "server": pbs_config.get("server"),
                "datastore": pbs_config.get("datastore"),
                "username": pbs_config.get("username"),
                # Don't include password for security
            }
            self.logger.debug(
                f"Added PBS details for {service.name}: {pbs_config.get('server')}/{pbs_config.get('datastore')}"
            )
        else:
            metadata["pbs_details"] = None

        self.logger.debug(
            f"Created backup metadata for {service.name}: method={metadata['backup_method']}, "
            f"status={metadata['status']}"
        )

        return metadata

    # pylint: disable=too-many-locals,too-many-statements
    def _execute_backup_command(
        self,
        service: ServiceConfig,
        backup_destination: Dict[str, Any],
        _backup_metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute the backup command based on the backup method.

        This method coordinates the actual backup execution by delegating to the
        appropriate plugin method based on the backup destination method (PBS,
        direct storage, or local).

        Args:
            service: Service configuration
            backup_destination: Output from _determine_backup_destination() containing:
                - method: 'pbs' | 'direct' | 'local'
                - path: Backup location path (for direct/local)
                - pbs_config: PBS configuration (for pbs method)
            backup_metadata: Output from _create_backup_metadata()

        Returns:
            Dict with backup execution result:
                {
                    'success': bool,
                    'backup_path': Optional[Path],  # Final backup location
                    'duration_seconds': float,  # For RTO metrics
                    'error_message': Optional[str],  # If failed
                }

        Example:
            >>> service = config.get_service_config("nextcloud")
            >>> destination = engine._determine_backup_destination(service)
            >>> metadata = engine._create_backup_metadata(service, destination)
            >>> result = engine._execute_backup_command(service, destination, metadata)
            >>> if result['success']:
            ...     print(f"Backup created at {result['backup_path']}")
        """
        method = backup_destination["method"]
        start_time = time.time()

        # Initialize result dict
        result: Dict[str, Any] = {
            "success": False,
            "backup_path": None,
            "duration_seconds": 0.0,
            "error_message": None,
        }

        # Handle dry run mode
        if self.dry_run:
            self.logger.info(
                f"DRY RUN: Would execute {method} backup for service '{service.name}'"
            )

            # Simulate successful backup with mock duration
            mock_duration = round(time.time() - start_time + 0.1, 2)

            # For local/direct methods, generate what the path WOULD be
            mock_path = None
            if method == "local":
                filename = self._generate_backup_filename(service.name, service.type)
                mock_path = Path(backup_destination["path"]) / service.name / filename
            elif method == "direct":
                filename = self._generate_backup_filename(service.name, service.type)
                mock_path = Path(backup_destination["path"]) / filename

            return {
                "success": True,
                "backup_path": mock_path,
                "duration_seconds": mock_duration,
                "error_message": None,
            }

        # Log backup start
        self.logger.info(
            f"Starting {method} backup for service '{service.name}' (type: {service.type})"
        )

        try:
            # Get plugin for service
            plugin = self._get_plugin_for_service(service)

            # Execute backup based on method
            if method == "pbs":
                # PBS backup: delegate to plugin
                pbs_config = backup_destination["pbs_config"]
                success = plugin.backup_to_pbs(service, pbs_config)

                if success:
                    result["success"] = True
                    result["backup_path"] = None  # PBS stores internally
                    self.logger.info(
                        f"PBS backup completed for service '{service.name}'"
                    )
                else:
                    result["error_message"] = (
                        "PBS backup failed. Check PBS server logs for details."
                    )
                    self.logger.error(f"PBS backup failed for service '{service.name}'")

            elif method == "direct":
                # Direct storage backup: plugin creates backup at specified path
                storage_path = backup_destination["path"]
                backup_path = plugin.backup_to_storage(service, storage_path)

                result["success"] = True
                result["backup_path"] = backup_path
                self.logger.info(
                    f"Direct storage backup completed for service '{service.name}' at {backup_path}"
                )

            elif method == "local":
                # Local backup: generate filename and full path
                filename = self._generate_backup_filename(service.name, service.type)
                backup_dir = Path(backup_destination["path"]) / service.name

                # Ensure backup directory exists
                backup_dir.mkdir(parents=True, exist_ok=True)

                backup_path = backup_dir / filename
                plugin.backup(service, backup_path)

                result["success"] = True
                result["backup_path"] = backup_path
                self.logger.info(
                    f"Local backup completed for service '{service.name}' at {backup_path}"
                )

            else:
                # Unknown method (should never happen due to validation)
                result["error_message"] = (
                    f"Unknown backup method '{method}'. This is a bug."
                )
                self.logger.error(
                    f"Unknown backup method '{method}' for service '{service.name}'"
                )

        except Exception as e:  # pylint: disable=broad-exception-caught
            # Catch all exceptions and return failure result (intentionally broad for safety)
            error_msg = (
                f"Backup execution failed for service '{service.name}' using {method} method: {e}. "
                f"Check logs for details."
            )
            result["error_message"] = error_msg

            # Log with full traceback
            self.logger.error(
                f"Backup failed for service '{service.name}':\n{traceback.format_exc()}"
            )

        # Calculate duration
        duration = round(time.time() - start_time, 2)
        result["duration_seconds"] = duration

        # Log completion
        if result["success"]:
            self.logger.info(
                f"Backup completed for service '{service.name}' in {duration}s"
            )
        else:
            self.logger.error(
                f"Backup failed for service '{service.name}' after {duration}s: {result['error_message']}"
            )

        return result

    def _perform_backup(
        self, service: ServiceConfig, destination: Dict[str, Any]
    ) -> bool:
        """
        Perform the actual backup operation.

        Delegates to the appropriate plugin based on service type and
        destination configuration.

        Args:
            service: Service configuration
            destination: Backup destination details from _determine_backup_destination

        Returns:
            True if backup succeeded

        Example:
            >>> service = config.get_service_config("nextcloud")
            >>> dest = engine._determine_backup_destination(service)
            >>> success = engine._perform_backup(service, dest)
        """
        raise NotImplementedError

    def verify_backup(self, backup_path: Path) -> bool:
        """
        Verify backup integrity.

        Performs basic validation:
        - File exists
        - File size > 0
        - Can read/extract archive (if applicable)

        Args:
            backup_path: Path to backup file

        Returns:
            True if backup is valid

        Example:
            >>> backup_file = Path("/mnt/backups/nextcloud_20250124_120000_vm.tar.gz")
            >>> if engine.verify_backup(backup_file):
            ...     print("Backup is valid")
        """
        raise NotImplementedError

    # ========================================================================
    # Retention Policy
    # ========================================================================

    def apply_retention_policy(self, service_name: str) -> int:
        """
        Delete old backups based on retention_days configuration.

        Only applies to direct storage backups. PBS manages its own retention
        policies internally.

        Args:
            service_name: Service to apply policy to

        Returns:
            Number of backups deleted

        Raises:
            ValueError: If service not found in configuration

        Example:
            >>> deleted = engine.apply_retention_policy("nextcloud")
            >>> print(f"Deleted {deleted} old backups")
        """
        raise NotImplementedError

    def _get_backup_files(self, service_name: str) -> list[Path]:
        """
        Get all backup files for a service, sorted by age (oldest first).

        Args:
            service_name: Service name

        Returns:
            List of backup file paths, sorted by modification time (oldest first)

        Example:
            >>> backups = engine._get_backup_files("nextcloud")
            >>> print(f"Found {len(backups)} backups")
        """
        # Get backup directory
        backup_dir = self._get_backup_directory(service_name)

        # Check if directory exists (should always exist after _get_backup_directory)
        if not backup_dir.exists():
            self.logger.warning(f"Backup directory does not exist: {backup_dir}")
            return []

        # Get all files (not directories) in backup directory
        try:
            files = [f for f in backup_dir.iterdir() if f.is_file()]
        except OSError as e:
            self.logger.error(f"Error reading backup directory {backup_dir}: {e}")
            return []

        # Sort by modification time (oldest first)
        files.sort(key=lambda f: f.stat().st_mtime)

        self.logger.debug(f"Found {len(files)} backup files for {service_name}")

        return files

    # ========================================================================
    # State Tracking
    # ========================================================================

    def _update_backup_state(
        self,
        service_name: str,
        success: bool,
        backup_path: Optional[Path] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Update state database with backup information.

        Tracks:
        - last_backup.{service_name}: ISO timestamp
        - backup_status.{service_name}: "success" or "failed"
        - backup_path.{service_name}: Path to latest backup
        - backup_error.{service_name}: Error message (if failed)

        Args:
            service_name: Service name
            success: Whether backup succeeded
            backup_path: Path to backup file (if successful)
            error_message: Error message (if failed)

        Example:
            >>> engine._update_backup_state(
            ...     "nextcloud",
            ...     True,
            ...     Path("/mnt/backups/nextcloud_20250124_120000_vm.tar.gz")
            ... )
        """
        raise NotImplementedError

    def get_last_backup_time(self, service_name: str) -> Optional[str]:
        """
        Get the timestamp of the last successful backup for a service.

        Args:
            service_name: Name of the service to query

        Returns:
            ISO 8601 timestamp string of last backup, or None if never backed up

        Raises:
            ValueError: If service_name is empty or invalid
            StateError: If state manager query fails

        Example:
            >>> last_backup = engine.get_last_backup_time("nextcloud")
            >>> if last_backup:
            ...     print(f"Last backup: {last_backup}")
        """
        # Validate input
        if not service_name or not isinstance(service_name, str):
            raise ValueError(
                f"Service name must be a non-empty string, got: {service_name!r}"
            )

        if not service_name.strip():
            raise ValueError("Service name cannot be empty or whitespace only")

        # Query StateManager
        try:
            self.logger.debug(f"Querying last backup time for service '{service_name}'")
            timestamp = self.state.get(f"last_backup.{service_name}")

            if timestamp:
                self.logger.debug(f"Last backup for '{service_name}': {timestamp}")
            else:
                self.logger.debug(
                    f"No backup history found for service '{service_name}'"
                )

            return timestamp

        except Exception as e:
            error_msg = f"Failed to query backup time for service '{service_name}': {e}"
            self.logger.error(error_msg)
            raise StateError(error_msg) from e

    def get_backup_status(self, service_name: str) -> Optional[str]:
        """
        Get status of last backup attempt for a service.

        Args:
            service_name: Service name

        Returns:
            "success", "failed", or None if never attempted

        Example:
            >>> status = engine.get_backup_status("nextcloud")
            >>> print(f"Last backup status: {status}")
        """
        raise NotImplementedError

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _get_backup_directory(self, service_name: str) -> Path:
        """
        Get backup directory for service, creating it if needed.

        Creates directory structure: {backup_root}/{service_name}/

        Args:
            service_name: Service name

        Returns:
            Path to service backup directory

        Raises:
            BackupError: If directory cannot be created or is inaccessible

        Example:
            >>> backup_dir = engine._get_backup_directory("nextcloud")
            >>> print(backup_dir)  # /mnt/backups/homelab/nextcloud/
        """
        # Get backup root from config
        try:
            backup_config = self._get_backup_config()
            backup_root = backup_config["root"]
        except Exception as e:
            raise BackupError(
                f"Failed to get backup configuration for service '{service_name}': {e}"
            ) from e

        # Create service-specific subdirectory
        backup_dir = backup_root / service_name

        # Create directory if it doesn't exist (mkdir -p behavior)
        try:
            backup_dir.mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"Backup directory ready: {backup_dir}")
        except OSError as e:
            error_msg = (
                f"Failed to create backup directory {backup_dir}: {e}. "
                f"Check directory permissions and disk space."
            )
            self.logger.error(error_msg)
            raise BackupError(error_msg) from e

        return backup_dir

    def _generate_backup_filename(
        self, service_name: str, service_type: str, extension: str = "tar.gz"
    ) -> str:
        """
        Generate backup filename with timestamp.

        Format: {service_name}_{timestamp}_{type}.{extension}
        Timestamp format: YYYYMMDD_HHMMSS (sortable, filesystem-safe)

        Args:
            service_name: Service name
            service_type: Service type (vm, lxc, docker, etc.)
            extension: File extension (default: tar.gz)

        Returns:
            Formatted filename

        Example:
            >>> filename = engine._generate_backup_filename("nextcloud", "vm")
            >>> print(filename)  # nextcloud_20250124_120000_vm.tar.gz
        """
        # Generate timestamp in sortable format: YYYYMMDD_HHMMSS
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Sanitize service name (replace spaces/special chars with underscores)
        safe_service_name = service_name.replace(" ", "_").replace("/", "_")

        # Build filename
        filename = f"{safe_service_name}_{timestamp}_{service_type}.{extension}"

        return filename

    def _send_backup_summary(self, results: Dict[str, bool]) -> None:
        """
        Send summary notification after backup run.

        Sends a single notification with overview of all backup results.

        Args:
            results: Dict of service_name -> success status

        Example:
            >>> results = {"nextcloud": True, "adguard": False, "plex": True}
            >>> engine._send_backup_summary(results)
        """
        raise NotImplementedError

    def _get_backup_config(self) -> Dict[str, Any]:
        """
        Get backup configuration from global config.

        Returns cached result on subsequent calls since config doesn't
        change during runtime.

        Returns:
            Dict containing backup settings (root, retention_days, etc.)
            Converts Pydantic models to dicts for easier access.

        Raises:
            BackupError: If backup configuration is invalid or inaccessible

        Example:
            >>> backup_config = engine._get_backup_config()
            >>> print(backup_config['root'])
            >>> print(backup_config.get('proxmox_backup_server'))
        """
        # Return cached version if available
        if self._backup_config_cache is not None:
            return self._backup_config_cache

        try:
            # Get BackupConfig Pydantic model from ConfigLoader
            # Validation already done in __init__, so this should succeed
            backup_config = self.config.get("global.backup")

            if backup_config is None:
                raise BackupError(
                    "Backup configuration section 'global.backup' is missing. "
                    "Please add backup configuration to your config file."
                )

            # Convert Pydantic model to dict
            config_dict = {
                "enabled": backup_config.enabled,
                "root": backup_config.root,
                "retention_days": backup_config.retention_days,
                "compression": backup_config.compression,
            }

            # Handle optional PBS config (also a Pydantic model)
            if backup_config.proxmox_backup_server is not None:
                pbs = backup_config.proxmox_backup_server
                config_dict["proxmox_backup_server"] = {
                    "enabled": pbs.enabled,
                    "server": pbs.server,
                    "port": pbs.port,
                    "datastore": pbs.datastore,
                    "username": pbs.username,
                    "password": pbs.password,
                    "password_command": pbs.password_command,
                    "verify_ssl": pbs.verify_ssl,
                }
            else:
                config_dict["proxmox_backup_server"] = None

            # Handle optional direct storage config (also a Pydantic model)
            if backup_config.direct_storage is not None:
                ds = backup_config.direct_storage
                config_dict["direct_storage"] = {
                    "enabled": ds.enabled,
                    "path": ds.path,
                    "format": ds.format,
                }
            else:
                config_dict["direct_storage"] = None

            # Cache and return
            self._backup_config_cache = config_dict
            return config_dict

        except Exception as e:
            if isinstance(e, BackupError):
                raise
            raise BackupError(
                f"Failed to load backup configuration: {e}. "
                "Check your configuration file for errors."
            ) from e
