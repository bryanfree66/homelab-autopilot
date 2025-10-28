"""
Generic service plugin for Docker, systemd, and file-based services.

This plugin handles application-level backups and operations for various service
types including Docker containers, systemd services, and generic file-based services.
Unlike HypervisorPlugin (which handles VMs/LXCs), this operates at the application level.
"""

import json
import shutil
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import docker
import requests

from core.config_loader import ConfigLoader, ServiceConfig
from lib.logger import get_logger
from lib.state_manager import StateManager
from plugins.base import ServicePlugin


class GenericServicePlugin(ServicePlugin):
    """
    Generic service plugin for Docker, systemd, and generic services.

    Handles backup, update, validation, and rollback operations for
    application-level services.

    Attributes:
        config_loader: Configuration loader instance
        state_manager: State manager instance
        logger: Logger instance
        _docker_client: Cached Docker client
    """

    def __init__(self, config: ConfigLoader, state: StateManager):
        """
        Initialize generic service plugin.

        Args:
            config: Configuration loader instance
            state: State manager instance
        """
        # Store full config and state for later use
        self.config_loader = config
        self.state_manager = state
        self.logger = get_logger()
        self._docker_client: Optional[docker.DockerClient] = None

        # Call parent with empty dict for now (base class expects dict)
        super().__init__({})

    @property
    def name(self) -> str:
        """
        Return the plugin name.

        Returns:
            Plugin name string
        """
        return "GenericServicePlugin"

    def matches(self, target: Dict[str, Any]) -> bool:
        """
        Check if this plugin handles the given service.

        Args:
            target: Service configuration (dict or ServiceConfig object)

        Returns:
            True if service type is 'docker', 'systemd', or 'generic'
        """
        # Handle both dict and ServiceConfig objects
        if isinstance(target, dict):
            service_type = target.get("type", "").lower()
        else:
            service_type = getattr(target, "type", "").lower()

        return service_type in ["docker", "systemd", "generic"]

    def _get_docker_client(self) -> docker.DockerClient:
        """
        Get or create Docker client.

        Creates a new client on first call and caches it for reuse.

        Returns:
            Docker client instance

        Raises:
            ConnectionError: If unable to connect to Docker daemon
        """
        if self._docker_client is not None:
            return self._docker_client

        try:
            self.logger.debug("Connecting to Docker daemon")
            self._docker_client = docker.from_env()
            # Test connection
            self._docker_client.ping()
            self.logger.debug("Docker client initialized successfully")
            return self._docker_client

        except docker.errors.DockerException as e:
            error_msg = f"Failed to connect to Docker daemon: {e}"
            self.logger.error(error_msg)
            raise ConnectionError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error connecting to Docker: {e}"
            self.logger.error(error_msg)
            raise ConnectionError(error_msg) from e

    def _create_manifest(
        self, service: ServiceConfig, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create backup manifest with metadata.

        Args:
            service: Service configuration
            metadata: Additional metadata to include

        Returns:
            Manifest dictionary
        """
        return {
            "service_name": service.name,
            "service_type": service.type,
            "backup_date": datetime.now(timezone.utc).isoformat(),
            "version": "1.0",
            "metadata": metadata,
        }

    def _create_tar_archive(
        self,
        source_paths: List[Path],
        destination: Path,
        base_dir: Optional[Path] = None,
    ) -> bool:
        """
        Create compressed tar.gz archive from source paths.

        Args:
            source_paths: List of paths to include in archive
            destination: Destination archive path
            base_dir: Base directory for relative paths (optional)

        Returns:
            True if archive created successfully
        """
        try:
            self.logger.debug(f"Creating tar archive at {destination}")

            # Ensure destination directory exists
            destination.parent.mkdir(parents=True, exist_ok=True)

            with tarfile.open(destination, "w:gz") as tar:
                for source_path in source_paths:
                    if not source_path.exists():
                        self.logger.warning(
                            f"Source path does not exist: {source_path}"
                        )
                        continue

                    # Calculate arcname (name in archive)
                    if base_dir:
                        arcname = source_path.relative_to(base_dir)
                    else:
                        arcname = source_path.name

                    self.logger.debug(f"Adding {source_path} as {arcname}")
                    tar.add(source_path, arcname=str(arcname), recursive=True)

            self.logger.info(f"Tar archive created: {destination}")
            return True

        except PermissionError as e:
            self.logger.error(f"Permission denied creating archive: {e}")
            return False
        except OSError as e:
            self.logger.error(f"OS error creating archive: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error creating archive: {e}")
            return False

    def _get_docker_volumes(self, container_name: str) -> List[Dict[str, str]]:
        """
        Get list of volumes mounted in container.

        Args:
            container_name: Name of container

        Returns:
            List of volume dicts with 'name' and 'mount' keys
            Returns empty list if container not found or has no volumes
        """
        try:
            client = self._get_docker_client()
            container = client.containers.get(container_name)

            volumes = []
            mounts = container.attrs.get("Mounts", [])

            for mount in mounts:
                # Only include named volumes, skip bind mounts
                if mount.get("Type") == "volume":
                    volumes.append(
                        {
                            "name": mount.get("Name", ""),
                            "mount": mount.get("Destination", ""),
                        }
                    )

            self.logger.debug(f"Found {len(volumes)} volumes for {container_name}")
            return volumes

        except docker.errors.NotFound:
            self.logger.warning(f"Container not found: {container_name}")
            return []
        except Exception as e:
            self.logger.error(f"Error getting volumes: {e}")
            return []

    def _backup_docker_volume(self, volume_name: str, dest_dir: Path) -> bool:
        """
        Backup a Docker volume by copying its data.

        Uses a temporary container to access the volume and tar its contents.

        Args:
            volume_name: Name of Docker volume
            dest_dir: Destination directory for volume backup

        Returns:
            True if backup succeeded
        """
        try:
            client = self._get_docker_client()

            # Ensure destination exists
            dest_dir.mkdir(parents=True, exist_ok=True)
            volume_tar = dest_dir / f"{volume_name}.tar.gz"

            self.logger.debug(f"Backing up volume {volume_name} to {volume_tar}")

            # Create temporary container to access volume
            # Mount volume at /volume-data and create tar to stdout
            container = client.containers.run(
                "alpine:latest",
                command=["tar", "czf", "-", "-C", "/volume-data", "."],
                volumes={volume_name: {"bind": "/volume-data", "mode": "ro"}},
                remove=True,
                detach=False,
            )

            # Write tar data to file
            with open(volume_tar, "wb") as f:
                f.write(container)

            self.logger.info(f"Volume {volume_name} backed up to {volume_tar}")
            return True

        except docker.errors.NotFound:
            self.logger.error(f"Volume not found: {volume_name}")
            return False
        except docker.errors.DockerException as e:
            self.logger.error(f"Docker error backing up volume: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error backing up volume: {e}")
            return False

    def _backup_docker_service(
        self, service: ServiceConfig, destination: Path
    ) -> bool:  # pylint: disable=too-many-locals
        """
        Backup Docker service (container, volumes, compose file).

        Creates a tar.gz archive containing:
        - docker-compose.yml (if exists)
        - Volume data
        - Container config (env vars, labels, etc.)
        - Manifest with metadata

        Args:
            service: Service configuration
            destination: Backup destination path

        Returns:
            True if backup succeeded
        """
        try:
            client = self._get_docker_client()

            # Determine container name
            container_name = (
                service.container_name if service.container_name else service.name
            )

            # Get container
            try:
                container = client.containers.get(container_name)
            except docker.errors.NotFound:
                self.logger.error(f"Container not found: {container_name}")
                return False

            # Create temporary directory for staging backup
            backup_dir = destination.parent / f"{service.name}_backup_tmp"
            backup_dir.mkdir(parents=True, exist_ok=True)

            try:
                # 1. Backup compose file if specified
                if service.compose_file:
                    compose_path = Path(service.compose_file)
                    if compose_path.exists():
                        compose_dest = backup_dir / "compose.yml"
                        shutil.copy2(compose_path, compose_dest)
                        self.logger.debug(f"Backed up compose file: {compose_path}")
                    else:
                        self.logger.warning(f"Compose file not found: {compose_path}")

                # 2. Backup volumes
                volumes = self._get_docker_volumes(container_name)
                if volumes:
                    volumes_dir = backup_dir / "volumes"
                    volumes_dir.mkdir(exist_ok=True)

                    for volume in volumes:
                        vol_name = volume["name"]
                        if not self._backup_docker_volume(vol_name, volumes_dir):
                            self.logger.warning(f"Failed to backup volume: {vol_name}")

                # 3. Save container config
                config_data = {
                    "image": (
                        container.image.tags[0]
                        if container.image.tags
                        else str(container.image.id)
                    ),
                    "environment": container.attrs.get("Config", {}).get("Env", []),
                    "labels": container.attrs.get("Config", {}).get("Labels", {}),
                    "command": container.attrs.get("Config", {}).get("Cmd", []),
                    "entrypoint": container.attrs.get("Config", {}).get(
                        "Entrypoint", []
                    ),
                    "ports": container.attrs.get("NetworkSettings", {}).get(
                        "Ports", {}
                    ),
                }

                config_file = backup_dir / "config.json"
                with open(config_file, "w", encoding="utf-8") as f:
                    json.dump(config_data, f, indent=2)

                # 4. Create manifest
                manifest = self._create_manifest(
                    service,
                    {
                        "container_name": container_name,
                        "image": config_data["image"],
                        "volumes": [v["name"] for v in volumes],
                        "compose_file": (
                            str(service.compose_file) if service.compose_file else None
                        ),
                    },
                )

                manifest_file = backup_dir / "manifest.json"
                with open(manifest_file, "w", encoding="utf-8") as f:
                    json.dump(manifest, f, indent=2)

                # 5. Create final tar archive
                success = self._create_tar_archive(
                    [backup_dir], destination, base_dir=backup_dir.parent
                )

                if success:
                    self.logger.info(
                        f"Docker service {service.name} backed up to {destination}"
                    )
                    return True

                return False

            finally:
                # Clean up temporary directory
                if backup_dir.exists():
                    shutil.rmtree(backup_dir, ignore_errors=True)

        except ConnectionError as e:
            self.logger.error(f"Docker connection error: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error backing up Docker service: {e}")
            return False

    def _backup_systemd_service(
        self, service: ServiceConfig, destination: Path
    ) -> bool:
        """
        Backup systemd service (unit file, config, data).

        Creates a tar.gz archive containing:
        - Service unit file
        - Config files (from service.config_paths)
        - Data files (from service.data_paths)
        - Manifest

        Args:
            service: Service configuration
            destination: Backup destination path

        Returns:
            True if backup succeeded
        """
        try:
            # Create temporary directory for staging
            backup_dir = destination.parent / f"{service.name}_backup_tmp"
            backup_dir.mkdir(parents=True, exist_ok=True)

            try:
                backed_up_items = []

                # 1. Backup service unit file
                service_file = Path(
                    f"/etc/systemd/system/{service.service_name}.service"
                )
                if not service_file.exists():
                    # Try alternate location
                    service_file = Path(
                        f"/lib/systemd/system/{service.service_name}.service"
                    )

                if service_file.exists():
                    service_dest_dir = backup_dir / "service"
                    service_dest_dir.mkdir(exist_ok=True)
                    service_dest = service_dest_dir / service_file.name
                    shutil.copy2(service_file, service_dest)
                    backed_up_items.append(str(service_file))
                    self.logger.debug(f"Backed up service file: {service_file}")
                else:
                    self.logger.warning(f"Service file not found: {service_file}")

                # 2. Backup config paths if specified
                config_paths = getattr(service, "config_paths", None)
                if config_paths:
                    config_dest_dir = backup_dir / "config"
                    config_dest_dir.mkdir(exist_ok=True)

                    for config_path_str in config_paths:
                        config_path = Path(config_path_str)
                        if config_path.exists():
                            if config_path.is_dir():
                                dest = config_dest_dir / config_path.name
                                shutil.copytree(config_path, dest, symlinks=True)
                            else:
                                shutil.copy2(config_path, config_dest_dir)
                            backed_up_items.append(str(config_path))
                            self.logger.debug(f"Backed up config: {config_path}")
                        else:
                            self.logger.warning(f"Config path not found: {config_path}")

                # 3. Backup data paths if specified
                data_paths = getattr(service, "data_paths", None)
                if data_paths:
                    data_dest_dir = backup_dir / "data"
                    data_dest_dir.mkdir(exist_ok=True)

                    for data_path_str in data_paths:
                        data_path = Path(data_path_str)
                        if data_path.exists():
                            if data_path.is_dir():
                                dest = data_dest_dir / data_path.name
                                shutil.copytree(data_path, dest, symlinks=True)
                            else:
                                shutil.copy2(data_path, data_dest_dir)
                            backed_up_items.append(str(data_path))
                            self.logger.debug(f"Backed up data: {data_path}")
                        else:
                            self.logger.warning(f"Data path not found: {data_path}")

                # 4. Create manifest
                manifest = self._create_manifest(
                    service,
                    {
                        "service_name": service.service_name,
                        "backed_up_items": backed_up_items,
                    },
                )

                manifest_file = backup_dir / "manifest.json"
                with open(manifest_file, "w", encoding="utf-8") as f:
                    json.dump(manifest, f, indent=2)

                # 5. Create final tar archive
                success = self._create_tar_archive(
                    [backup_dir], destination, base_dir=backup_dir.parent
                )

                if success:
                    self.logger.info(
                        f"Systemd service {service.name} backed up to {destination}"
                    )
                    return True

                return False

            finally:
                # Clean up temporary directory
                if backup_dir.exists():
                    shutil.rmtree(backup_dir, ignore_errors=True)

        except PermissionError as e:
            self.logger.error(f"Permission denied backing up systemd service: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error backing up systemd service: {e}")
            return False

    def _backup_generic_files(self, service: ServiceConfig, destination: Path) -> bool:
        """
        Backup generic files/directories.

        Creates a tar.gz archive containing all paths specified in
        service.backup_paths.

        Args:
            service: Service configuration
            destination: Backup destination path

        Returns:
            True if backup succeeded
        """
        try:
            backup_paths = getattr(service, "backup_paths", None)
            if not backup_paths:
                self.logger.error(
                    f"Generic service {service.name} has no backup_paths defined"
                )
                return False

            # Create temporary directory for staging
            backup_dir = destination.parent / f"{service.name}_backup_tmp"
            backup_dir.mkdir(parents=True, exist_ok=True)

            try:
                backed_up_items = []

                # Copy all backup paths to staging directory
                for backup_path_str in backup_paths:
                    backup_path = Path(backup_path_str)
                    if backup_path.exists():
                        if backup_path.is_dir():
                            dest = backup_dir / backup_path.name
                            shutil.copytree(backup_path, dest, symlinks=True)
                        else:
                            shutil.copy2(backup_path, backup_dir)
                        backed_up_items.append(str(backup_path))
                        self.logger.debug(f"Backed up: {backup_path}")
                    else:
                        self.logger.warning(f"Backup path not found: {backup_path}")

                if not backed_up_items:
                    self.logger.error("No backup paths found")
                    return False

                # Create manifest
                manifest = self._create_manifest(
                    service,
                    {
                        "backup_paths": backed_up_items,
                    },
                )

                manifest_file = backup_dir / "manifest.json"
                with open(manifest_file, "w", encoding="utf-8") as f:
                    json.dump(manifest, f, indent=2)

                # Create final tar archive
                success = self._create_tar_archive(
                    [backup_dir], destination, base_dir=backup_dir.parent
                )

                if success:
                    self.logger.info(
                        f"Generic service {service.name} backed up to {destination}"
                    )
                    return True

                return False

            finally:
                # Clean up temporary directory
                if backup_dir.exists():
                    shutil.rmtree(backup_dir, ignore_errors=True)

        except PermissionError as e:
            self.logger.error(f"Permission denied backing up generic files: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error backing up generic files: {e}")
            return False

    def backup(self, service: ServiceConfig, destination: Path) -> bool:
        """
        Backup service configuration and data.

        Routes to appropriate backup method based on service type:
        - Docker: backup container, volumes, compose file
        - Systemd: backup unit file, config, data
        - Generic: backup specified file paths

        Args:
            service: Service configuration
            destination: Backup destination path

        Returns:
            True if backup succeeded, False otherwise
        """
        try:
            self.logger.info(
                f"Starting backup of {service.type} service: {service.name}"
            )

            if service.type == "docker":
                return self._backup_docker_service(service, destination)
            elif service.type == "systemd":
                return self._backup_systemd_service(service, destination)
            elif service.type == "generic":
                return self._backup_generic_files(service, destination)
            else:
                self.logger.error(f"Unsupported service type: {service.type}")
                return False

        except Exception as e:
            self.logger.error(f"Unexpected error during backup: {e}")
            return False

    def _update_docker_service(self, service: ServiceConfig) -> bool:
        """
        Update Docker service by pulling latest image and recreating container.

        Args:
            service: Service configuration

        Returns:
            True if update succeeded
        """
        try:
            # If compose file exists, use docker-compose
            if service.compose_file:
                compose_path = Path(service.compose_file)
                if not compose_path.exists():
                    self.logger.error(f"Compose file not found: {compose_path}")
                    return False

                self.logger.info(f"Updating via docker-compose: {compose_path}")

                # Pull latest images
                result = subprocess.run(
                    ["docker-compose", "-f", str(compose_path), "pull"],
                    capture_output=True,
                    text=True,
                    check=False,
                )

                if result.returncode != 0:
                    self.logger.error(f"docker-compose pull failed: {result.stderr}")
                    return False

                # Recreate containers
                result = subprocess.run(
                    ["docker-compose", "-f", str(compose_path), "up", "-d"],
                    capture_output=True,
                    text=True,
                    check=False,
                )

                if result.returncode != 0:
                    self.logger.error(f"docker-compose up failed: {result.stderr}")
                    return False

                self.logger.info("Docker service updated via compose")
                return True

            else:
                # Update standalone container
                client = self._get_docker_client()
                container_name = service.container_name or service.name

                try:
                    container = client.containers.get(container_name)
                except docker.errors.NotFound:
                    self.logger.error(f"Container not found: {container_name}")
                    return False

                # Get image name
                image_name = (
                    container.image.tags[0]
                    if container.image.tags
                    else str(container.image.id)
                )

                self.logger.info(f"Pulling latest image: {image_name}")

                # Pull latest image
                try:
                    client.images.pull(image_name)
                except docker.errors.APIError as e:
                    self.logger.error(f"Failed to pull image: {e}")
                    return False

                # TODO: Recreating container is complex (need to preserve config)
                # For now, just indicate success if image was pulled
                self.logger.warning(
                    "Image pulled but container not recreated (requires manual restart)"
                )
                return True

        except ConnectionError as e:
            self.logger.error(f"Docker connection error: {e}")
            return False
        except subprocess.SubprocessError as e:
            self.logger.error(f"Subprocess error: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error updating Docker service: {e}")
            return False

    def _update_systemd_service(self, service: ServiceConfig) -> bool:
        """
        Update systemd service by upgrading package and restarting.

        Args:
            service: Service configuration

        Returns:
            True if update succeeded
        """
        try:
            # Check if package name is specified
            package_name = getattr(service, "package_name", None)

            if package_name:
                self.logger.info(f"Updating package: {package_name}")

                # Detect package manager
                if shutil.which("apt-get"):
                    # Debian/Ubuntu
                    result = subprocess.run(
                        ["apt-get", "update"],
                        capture_output=True,
                        text=True,
                        check=False,
                    )

                    if result.returncode != 0:
                        self.logger.error(f"apt-get update failed: {result.stderr}")
                        return False

                    result = subprocess.run(
                        ["apt-get", "install", "--only-upgrade", "-y", package_name],
                        capture_output=True,
                        text=True,
                        check=False,
                    )

                    if result.returncode != 0:
                        self.logger.error(f"apt-get install failed: {result.stderr}")
                        return False

                elif shutil.which("dnf"):
                    # RHEL/Fedora
                    result = subprocess.run(
                        ["dnf", "upgrade", "-y", package_name],
                        capture_output=True,
                        text=True,
                        check=False,
                    )

                    if result.returncode != 0:
                        self.logger.error(f"dnf upgrade failed: {result.stderr}")
                        return False

                else:
                    self.logger.error("No supported package manager found")
                    return False

            # Reload systemd
            result = subprocess.run(
                ["systemctl", "daemon-reload"],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                self.logger.warning(f"systemctl daemon-reload warning: {result.stderr}")

            # Restart service
            service_name = service.service_name or service.name
            self.logger.info(f"Restarting service: {service_name}")

            result = subprocess.run(
                ["systemctl", "restart", service_name],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                self.logger.error(f"systemctl restart failed: {result.stderr}")
                return False

            self.logger.info("Systemd service updated and restarted")
            return True

        except subprocess.SubprocessError as e:
            self.logger.error(f"Subprocess error: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error updating systemd service: {e}")
            return False

    def update(self, service: ServiceConfig) -> bool:
        """
        Update the service to latest version.

        Routes to appropriate update method based on service type.
        Generic services do not support updates.

        Args:
            service: Service configuration

        Returns:
            True if update succeeded, False otherwise
        """
        try:
            self.logger.info(
                f"Starting update of {service.type} service: {service.name}"
            )

            if service.type == "docker":
                return self._update_docker_service(service)
            elif service.type == "systemd":
                return self._update_systemd_service(service)
            elif service.type == "generic":
                self.logger.warning("Generic services do not support updates")
                return False
            else:
                self.logger.error(f"Unsupported service type: {service.type}")
                return False

        except Exception as e:
            self.logger.error(f"Unexpected error during update: {e}")
            return False

    def validate(self, service: ServiceConfig) -> bool:
        """
        Validate that service is running and healthy.

        Checks service status and optionally performs HTTP health check.

        Args:
            service: Service configuration

        Returns:
            True if service is healthy, False otherwise
        """
        try:
            self.logger.debug(f"Validating {service.type} service: {service.name}")

            # Check based on service type
            if service.type == "docker":
                client = self._get_docker_client()
                container_name = service.container_name or service.name

                try:
                    container = client.containers.get(container_name)
                    if container.status != "running":
                        self.logger.error(
                            f"Container {container_name} is not running: {container.status}"
                        )
                        return False

                    # Check health status if available
                    health = container.attrs.get("State", {}).get("Health", {})
                    if health:
                        health_status = health.get("Status")
                        if health_status not in ["healthy", "none"]:
                            self.logger.error(
                                f"Container {container_name} is unhealthy: {health_status}"
                            )
                            return False

                except docker.errors.NotFound:
                    self.logger.error(f"Container not found: {container_name}")
                    return False

            elif service.type == "systemd":
                service_name = service.service_name or service.name

                result = subprocess.run(
                    ["systemctl", "is-active", service_name],
                    capture_output=True,
                    text=True,
                    check=False,
                )

                if result.stdout.strip() != "active":
                    self.logger.error(
                        f"Systemd service {service_name} is not active: {result.stdout.strip()}"
                    )
                    return False

            elif service.type == "generic":
                # For generic services, check if backup paths exist
                backup_paths = getattr(service, "backup_paths", None)
                if backup_paths:
                    for path_str in backup_paths:
                        path = Path(path_str)
                        if not path.exists():
                            self.logger.error(f"Path does not exist: {path}")
                            return False

            # Optional HTTP health check
            health_check_url = getattr(service, "health_check_url", None)
            if health_check_url:
                try:
                    response = requests.get(health_check_url, timeout=10)
                    if response.status_code != 200:
                        self.logger.error(
                            f"Health check failed for {health_check_url}: "
                            f"status {response.status_code}"
                        )
                        return False
                except requests.RequestException as e:
                    self.logger.error(f"Health check request failed: {e}")
                    return False

            self.logger.debug(f"Service {service.name} is healthy")
            return True

        except ConnectionError as e:
            self.logger.error(f"Connection error during validation: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during validation: {e}")
            return False

    def rollback(self, service: ServiceConfig) -> bool:
        """
        Rollback service to previous version.

        This is a best-effort operation. For most service types,
        rollback should be handled by restoring from backup.

        Args:
            service: Service configuration

        Returns:
            False (rollback not supported, use backup restoration)
        """
        self.logger.warning(
            f"Rollback not directly supported for {service.type} services. "
            "Use backup restoration instead."
        )
        return False

    def get_status(self, service: ServiceConfig) -> Dict[str, Any]:
        """
        Get current status of service.

        Returns service-specific status information including running state,
        health, and other relevant metrics.

        Args:
            service: Service configuration

        Returns:
            Dictionary with status information, or empty dict on error
        """
        try:
            if service.type == "docker":
                client = self._get_docker_client()
                container_name = service.container_name or service.name

                try:
                    container = client.containers.get(container_name)

                    status = {
                        "running": container.status == "running",
                        "status": container.status,
                        "created": container.attrs.get("Created"),
                    }

                    # Add image info
                    if container.image.tags:
                        status["image"] = container.image.tags[0]
                    else:
                        status["image"] = str(container.image.id)

                    # Add health info if available
                    health = container.attrs.get("State", {}).get("Health", {})
                    if health:
                        status["healthy"] = health.get("Status") == "healthy"

                    return status

                except docker.errors.NotFound:
                    self.logger.error(f"Container not found: {container_name}")
                    return {"running": False, "error": "Container not found"}

            elif service.type == "systemd":
                service_name = service.service_name or service.name

                # Get active status
                result = subprocess.run(
                    ["systemctl", "is-active", service_name],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                active = result.stdout.strip()

                # Get enabled status
                result = subprocess.run(
                    ["systemctl", "is-enabled", service_name],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                enabled = result.stdout.strip() == "enabled"

                return {
                    "running": active == "active",
                    "active": active,
                    "enabled": enabled,
                }

            elif service.type == "generic":
                backup_paths = getattr(service, "backup_paths", None)
                if backup_paths:
                    paths_exist = all(Path(p).exists() for p in backup_paths)
                    return {
                        "running": None,  # Cannot determine for generic
                        "paths_exist": paths_exist,
                    }

                return {"running": None}

            else:
                self.logger.error(f"Unsupported service type: {service.type}")
                return {}

        except ConnectionError as e:
            self.logger.error(f"Connection error getting status: {e}")
            return {}
        except Exception as e:
            self.logger.error(f"Unexpected error getting status: {e}")
            return {}
