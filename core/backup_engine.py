"""
Backup Engine for Homelab Autopilot.

This module orchestrates backup operations across all configured services,
supporting multiple backup strategies including Proxmox Backup Server (PBS),
direct storage, and file-based backups.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union

from core.config_loader import ConfigLoader, ServiceConfig
from lib.logger import get_logger
from lib.state_manager import StateManager
from plugins.base import HypervisorPlugin, ServicePlugin


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

        if self.dry_run:
            self.logger.info("BackupEngine initialized in DRY RUN mode")
        else:
            self.logger.info("BackupEngine initialized")

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
        raise NotImplementedError

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

    def _determine_backup_destination(
        self, service: ServiceConfig
    ) -> Dict[str, Any]:
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
                    'storage_id': PBS storage ID (if method='pbs'),
                    ...
                }

        Example:
            >>> service = config.get_service_config("nextcloud")
            >>> dest = engine._determine_backup_destination(service)
            >>> print(dest['method'])  # 'pbs' or 'direct' or 'local'
        """
        raise NotImplementedError

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
            self.logger.warning(
                f"Backup directory does not exist: {backup_dir}"
            )
            return []

        # Get all files (not directories) in backup directory
        try:
            files = [f for f in backup_dir.iterdir() if f.is_file()]
        except OSError as e:
            self.logger.error(
                f"Error reading backup directory {backup_dir}: {e}"
            )
            return []

        # Sort by modification time (oldest first)
        files.sort(key=lambda f: f.stat().st_mtime)

        self.logger.debug(
            f"Found {len(files)} backup files for {service_name}"
        )

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

    def get_last_backup_time(self, service_name: str) -> Optional[datetime]:
        """
        Get timestamp of last successful backup for a service.

        Args:
            service_name: Service name

        Returns:
            Datetime of last backup, or None if never backed up

        Example:
            >>> last_backup = engine.get_last_backup_time("nextcloud")
            >>> if last_backup:
            ...     print(f"Last backup: {last_backup.isoformat()}")
        """
        raise NotImplementedError

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
            OSError: If directory cannot be created

        Example:
            >>> backup_dir = engine._get_backup_directory("nextcloud")
            >>> print(backup_dir)  # /mnt/backups/homelab/nextcloud/
        """
        # Get backup root from config
        backup_config = self._get_backup_config()
        backup_root = backup_config["root"]

        # Create service-specific subdirectory
        backup_dir = backup_root / service_name

        # Create directory if it doesn't exist (mkdir -p behavior)
        try:
            backup_dir.mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"Backup directory ready: {backup_dir}")
        except OSError as e:
            self.logger.error(
                f"Failed to create backup directory {backup_dir}: {e}"
            )
            raise

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

        Example:
            >>> backup_config = engine._get_backup_config()
            >>> print(backup_config['root'])
            >>> print(backup_config.get('proxmox_backup_server'))
        """
        # Return cached version if available
        if self._backup_config_cache is not None:
            return self._backup_config_cache

        # Get BackupConfig Pydantic model from ConfigLoader
        backup_config = self.config.get("global.backup")

        if backup_config is None:
            # This shouldn't happen if config validation passed, but handle gracefully
            self.logger.warning("No backup configuration found, using defaults")
            self._backup_config_cache = {
                "enabled": True,
                "root": Path("/var/lib/homelab-autopilot/backups"),
                "retention_days": 30,
                "compression": True,
                "proxmox_backup_server": None,
                "direct_storage": None,
            }
            return self._backup_config_cache

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
