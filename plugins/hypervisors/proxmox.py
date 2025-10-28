"""
Proxmox hypervisor plugin for VM and LXC operations.

This plugin handles backup, snapshot, and status operations for Proxmox VMs
and containers via the Proxmox VE API. Supports both Proxmox Backup Server (PBS)
integration and direct storage backups.
"""

import time
from pathlib import Path
from typing import Any, Dict, Optional

from proxmoxer import ProxmoxAPI
from proxmoxer.core import ResourceException

from core.config_loader import ConfigLoader, ServiceConfig
from lib.logger import get_logger
from lib.state_manager import StateManager
from plugins.base import HypervisorPlugin


class ProxmoxPlugin(HypervisorPlugin):
    """
    Proxmox hypervisor plugin for VM and LXC operations.

    Handles backup, snapshot, and status operations for Proxmox VMs and containers.
    Cluster-aware: automatically determines actual node location for VMs/LXCs.

    Attributes:
        config_loader: Configuration loader instance
        state_manager: State manager instance
        logger: Logger instance
        _api_client: Cached Proxmox API client
    """

    def __init__(self, config: ConfigLoader, state: StateManager):
        """
        Initialize Proxmox plugin.

        Args:
            config: Configuration loader instance
            state: State manager instance
        """
        # Store full config and state for later use
        self.config_loader = config
        self.state_manager = state
        self.logger = get_logger()
        self._api_client: Optional[ProxmoxAPI] = None

        # Call parent with empty dict for now (base class expects dict)
        super().__init__({})

    @property
    def name(self) -> str:
        """
        Return the plugin name.

        Returns:
            Plugin name string
        """
        return "ProxmoxPlugin"

    def matches(self, target: Dict[str, Any]) -> bool:
        """
        Check if this plugin handles the given service.

        Args:
            target: Service configuration (dict or ServiceConfig object)

        Returns:
            True if service type is 'vm' or 'lxc', False otherwise
        """
        # Handle both dict and ServiceConfig objects
        if isinstance(target, dict):
            service_type = target.get("type", "").lower()
        else:
            service_type = getattr(target, "type", "").lower()

        return service_type in ["vm", "lxc"]

    def _get_api_client(self) -> ProxmoxAPI:
        """
        Get or create Proxmox API client.

        Creates a new client on first call and caches it for reuse.
        Retrieves connection parameters from global hypervisor config.

        Returns:
            Proxmox API client instance

        Raises:
            ConnectionError: If unable to connect to Proxmox API
        """
        if self._api_client is not None:
            return self._api_client

        try:
            # Get hypervisor config from ConfigLoader
            host = self.config_loader.get("global.hypervisor.host", required=True)
            username = self.config_loader.get(
                "global.hypervisor.username", required=True
            )
            password = self.config_loader.get(
                "global.hypervisor.password", required=True
            )
            verify_ssl = self.config_loader.get("global.hypervisor.verify_ssl", True)

            self.logger.debug(f"Connecting to Proxmox API at {host}")

            # Create and cache the API client
            self._api_client = ProxmoxAPI(
                host=host,
                user=username,
                password=password,
                verify_ssl=verify_ssl,
            )

            self.logger.debug("Proxmox API client initialized successfully")
            return self._api_client

        except Exception as e:
            error_msg = f"Failed to connect to Proxmox API: {e}"
            self.logger.error(error_msg)
            raise ConnectionError(error_msg) from e

    def _validate_service(self, service: ServiceConfig) -> None:
        """
        Validate that service has required Proxmox fields.

        Args:
            service: Service configuration to validate

        Raises:
            ValueError: If service is missing required fields
        """
        if service.type not in ["vm", "lxc"]:
            raise ValueError(
                f"Service '{service.name}' has invalid type '{service.type}'. "
                "ProxmoxPlugin only handles 'vm' or 'lxc' types."
            )

        if service.vmid is None:
            raise ValueError(
                f"Service '{service.name}' is missing required 'vmid' field"
            )

        if not isinstance(service.vmid, int):
            raise ValueError(
                f"Service '{service.name}' has invalid vmid: "
                f"must be integer, got {type(service.vmid).__name__}"
            )

        if service.node is None:
            raise ValueError(
                f"Service '{service.name}' is missing required 'node' field"
            )

    def _get_vm_type(self, service: ServiceConfig) -> str:
        """
        Get Proxmox API VM type string.

        Args:
            service: Service configuration

        Returns:
            'qemu' for VMs, 'lxc' for containers
        """
        return "qemu" if service.type == "vm" else "lxc"

    def _get_actual_node(self, service: ServiceConfig) -> str:
        """
        Get actual node location for VM/LXC (cluster-aware).

        CRITICAL: Never trust service.node in clustered environments.
        VMs can be migrated between nodes. This method queries the Proxmox
        cluster API to find the actual current location.

        Args:
            service: Service configuration

        Returns:
            Actual node name where VM/LXC is currently located

        Raises:
            ValueError: If VM/LXC not found in cluster
            ConnectionError: If unable to query cluster API
        """
        try:
            api = self._get_api_client()

            # Query cluster resources to find VM/LXC
            vm_type = "vm" if service.type == "vm" else "lxc"
            self.logger.debug(f"Querying cluster for {vm_type}/{service.vmid} location")

            resources = api.cluster.resources.get(type=vm_type)

            # Find matching resource by VMID
            for resource in resources:
                if resource.get("vmid") == service.vmid:
                    actual_node = resource.get("node")
                    if actual_node != service.node:
                        self.logger.info(
                            f"VM/LXC {service.vmid} found on node '{actual_node}' "
                            f"(config says '{service.node}')"
                        )
                    else:
                        self.logger.debug(
                            f"VM/LXC {service.vmid} confirmed on node '{actual_node}'"
                        )
                    return actual_node

            # VM not found in cluster resources
            self.logger.warning(
                f"VM/LXC {service.vmid} not found in cluster resources, "
                f"falling back to configured node '{service.node}'"
            )
            return service.node

        except ConnectionError:
            # Re-raise connection errors
            raise
        except Exception as e:
            # For single-node setups or other errors, fall back to config
            self.logger.debug(
                f"Unable to query cluster resources ({e}), "
                f"using configured node '{service.node}'"
            )
            return service.node

    def _wait_for_task(
        self, node: str, upid: str, timeout: int = 3600
    ) -> bool:  # pylint: disable=too-many-return-statements
        """
        Wait for Proxmox task to complete.

        Polls task status every 2 seconds until completion or timeout.
        Logs progress periodically.

        Args:
            node: Node name where task is running
            upid: Proxmox task UPID
            timeout: Maximum seconds to wait (default: 3600 = 1 hour)

        Returns:
            True if task completed successfully (exitstatus == 'OK')
            False if task failed or timed out

        Raises:
            ConnectionError: If unable to query task status
        """
        api = self._get_api_client()
        start_time = time.time()
        last_log_time = start_time

        self.logger.info(f"Waiting for task {upid} on node {node}")

        try:
            while True:
                # Check timeout
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    self.logger.error(f"Task {upid} timed out after {timeout} seconds")
                    return False

                # Get task status
                status = api.nodes(node).tasks(upid).status.get()

                # Check if task is still running
                if status.get("status") == "running":
                    # Log progress every 30 seconds
                    if time.time() - last_log_time >= 30:
                        self.logger.debug(
                            f"Task {upid} still running... ({int(elapsed)}s elapsed)"
                        )
                        last_log_time = time.time()

                    time.sleep(2)
                    continue

                # Task completed - check exit status
                if status.get("status") == "stopped":
                    exit_status = status.get("exitstatus")
                    if exit_status == "OK":
                        self.logger.info(
                            f"Task {upid} completed successfully in {int(elapsed)}s"
                        )
                        return True

                    # Task failed - extract error
                    error_msg = self._parse_task_log(node, upid)
                    self.logger.error(
                        f"Task {upid} failed with status '{exit_status}': {error_msg}"
                    )
                    return False

                # Unknown status
                self.logger.warning(
                    f"Task {upid} has unexpected status: {status.get('status')}"
                )
                return False

        except Exception as e:
            self.logger.error(f"Error waiting for task {upid}: {e}")
            return False

    def _parse_task_log(self, node: str, upid: str) -> Optional[str]:
        """
        Parse task log to extract error message.

        Args:
            node: Node name where task ran
            upid: Proxmox task UPID

        Returns:
            Error message string, or None if unable to parse
        """
        try:
            api = self._get_api_client()
            log_entries = api.nodes(node).tasks(upid).log.get()

            # Extract error lines from log
            error_lines = []
            for entry in log_entries:
                line = entry.get("t", "")
                if "error" in line.lower() or "fail" in line.lower():
                    error_lines.append(line)

            if error_lines:
                return " | ".join(error_lines[-3:])  # Last 3 error lines

            # No specific errors found, return last line
            if log_entries:
                return log_entries[-1].get("t", "Unknown error")

            return None

        except Exception as e:
            self.logger.debug(f"Unable to parse task log: {e}")
            return None

    def _backup_to_pbs(
        self, service: ServiceConfig, node: str, metadata: Dict[str, Any]
    ) -> bool:
        """
        Backup VM/LXC to Proxmox Backup Server.

        Args:
            service: Service configuration
            node: Actual node where VM/LXC is located
            metadata: Backup metadata containing PBS config

        Returns:
            True if backup succeeded, False otherwise
        """
        try:
            api = self._get_api_client()
            vm_type = self._get_vm_type(service)

            # Extract PBS config from metadata
            pbs_config = metadata.get("pbs_config", {})
            datastore = pbs_config.get("datastore")
            if not datastore:
                self.logger.error("PBS datastore not specified in metadata")
                return False

            # Get compression mode
            compression = metadata.get("compression", "zstd")

            self.logger.info(
                f"Starting PBS backup of {vm_type}/{service.vmid} "
                f"to datastore '{datastore}'"
            )

            # Create vzdump backup task
            result = api.nodes(node).vzdump.create(
                vmid=service.vmid,
                storage=datastore,
                mode="snapshot",
                compress=compression,
                remove=0,  # Don't auto-remove old backups (we manage retention)
            )

            # Extract UPID from result
            upid = result

            # Wait for task to complete
            success = self._wait_for_task(node, upid, timeout=3600)

            if success:
                self.logger.info(
                    f"PBS backup of {vm_type}/{service.vmid} completed successfully"
                )
            else:
                self.logger.error(f"PBS backup of {vm_type}/{service.vmid} failed")

            return success

        except ResourceException as e:
            self.logger.error(f"Proxmox API error during PBS backup: {e}")
            return False
        except ConnectionError as e:
            self.logger.error(f"Connection error during PBS backup: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during PBS backup: {e}")
            return False

    def _backup_to_storage(
        self, service: ServiceConfig, node: str, destination: Path
    ) -> bool:
        """
        Backup VM/LXC to direct storage.

        Args:
            service: Service configuration
            node: Actual node where VM/LXC is located
            destination: Backup destination path

        Returns:
            True if backup succeeded, False otherwise
        """
        try:
            api = self._get_api_client()
            vm_type = self._get_vm_type(service)

            # Ensure destination directory exists
            dumpdir = destination.parent
            self.logger.info(
                f"Starting direct storage backup of {vm_type}/{service.vmid} "
                f"to {dumpdir}"
            )

            # Create vzdump backup task
            result = api.nodes(node).vzdump.create(
                vmid=service.vmid,
                dumpdir=str(dumpdir),
                mode="snapshot",
                compress="zstd",
                remove=0,
            )

            # Extract UPID from result
            upid = result

            # Wait for task to complete
            success = self._wait_for_task(node, upid, timeout=3600)

            if success:
                self.logger.info(
                    f"Direct storage backup of {vm_type}/{service.vmid} "
                    "completed successfully"
                )
            else:
                self.logger.error(
                    f"Direct storage backup of {vm_type}/{service.vmid} failed"
                )

            return success

        except ResourceException as e:
            self.logger.error(f"Proxmox API error during direct backup: {e}")
            return False
        except ConnectionError as e:
            self.logger.error(f"Connection error during direct backup: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during direct backup: {e}")
            return False

    def backup(
        self,
        service: ServiceConfig,
        destination: Path,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Backup a VM or container.

        Determines backup type (PBS vs direct storage) from metadata and
        delegates to appropriate backup method. Cluster-aware: automatically
        finds actual node location.

        Args:
            service: Service configuration
            destination: Backup destination path (used for direct storage)
            metadata: Optional metadata dict containing:
                - use_pbs: bool - Use PBS if True, direct storage if False
                - pbs_config: dict - PBS configuration
                - compression: str - Compression algorithm

        Returns:
            True if backup succeeded, False otherwise
        """
        try:
            # Validate service configuration
            self._validate_service(service)

            # Get actual node location (cluster-aware!)
            node = self._get_actual_node(service)

            # Determine backup type
            metadata = metadata or {}
            use_pbs = metadata.get("use_pbs", False)

            if use_pbs:
                return self._backup_to_pbs(service, node, metadata)
            else:
                return self._backup_to_storage(service, node, destination)

        except ValueError as e:
            self.logger.error(f"Service validation error: {e}")
            return False
        except ConnectionError as e:
            self.logger.error(f"Connection error: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during backup: {e}")
            return False

    def create_snapshot(self, service: ServiceConfig, snapshot_name: str) -> bool:
        """
        Create a snapshot of a VM or container.

        Args:
            service: Service configuration
            snapshot_name: Name for the snapshot

        Returns:
            True if snapshot created successfully, False otherwise
        """
        try:
            # Validate service
            self._validate_service(service)

            # Get actual node
            node = self._get_actual_node(service)
            vm_type = self._get_vm_type(service)

            self.logger.info(
                f"Creating snapshot '{snapshot_name}' for {vm_type}/{service.vmid}"
            )

            # Get API client and create snapshot
            api = self._get_api_client()

            if service.type == "vm":
                result = (
                    api.nodes(node)
                    .qemu(service.vmid)
                    .snapshot.create(
                        snapname=snapshot_name, description="Homelab Autopilot snapshot"
                    )
                )
            else:  # lxc
                result = (
                    api.nodes(node)
                    .lxc(service.vmid)
                    .snapshot.create(
                        snapname=snapshot_name, description="Homelab Autopilot snapshot"
                    )
                )

            # Check if result is a task UPID
            if isinstance(result, str) and result.startswith("UPID:"):
                success = self._wait_for_task(node, result, timeout=600)
            else:
                # Snapshot created synchronously
                success = True

            if success:
                self.logger.info(
                    f"Snapshot '{snapshot_name}' created for {vm_type}/{service.vmid}"
                )
            else:
                self.logger.error(
                    f"Failed to create snapshot '{snapshot_name}' "
                    f"for {vm_type}/{service.vmid}"
                )

            return success

        except ResourceException as e:
            self.logger.error(f"Proxmox API error creating snapshot: {e}")
            return False
        except ValueError as e:
            self.logger.error(f"Service validation error: {e}")
            return False
        except ConnectionError as e:
            self.logger.error(f"Connection error: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error creating snapshot: {e}")
            return False

    def restore_snapshot(self, service: ServiceConfig, snapshot_name: str) -> bool:
        """
        Restore a VM or container from a snapshot.

        Args:
            service: Service configuration
            snapshot_name: Name of the snapshot to restore

        Returns:
            True if restore succeeded, False otherwise
        """
        try:
            # Validate service
            self._validate_service(service)

            # Get actual node
            node = self._get_actual_node(service)
            vm_type = self._get_vm_type(service)

            self.logger.info(
                f"Restoring {vm_type}/{service.vmid} from snapshot '{snapshot_name}'"
            )

            # Get API client and restore snapshot (rollback)
            api = self._get_api_client()

            if service.type == "vm":
                result = (
                    api.nodes(node)
                    .qemu(service.vmid)
                    .snapshot(snapshot_name)
                    .rollback.post()
                )
            else:  # lxc
                result = (
                    api.nodes(node)
                    .lxc(service.vmid)
                    .snapshot(snapshot_name)
                    .rollback.post()
                )

            # Check if result is a task UPID
            if isinstance(result, str) and result.startswith("UPID:"):
                success = self._wait_for_task(node, result, timeout=600)
            else:
                success = True

            if success:
                self.logger.info(
                    f"Restored {vm_type}/{service.vmid} from snapshot '{snapshot_name}'"
                )
            else:
                self.logger.error(
                    f"Failed to restore {vm_type}/{service.vmid} "
                    f"from snapshot '{snapshot_name}'"
                )

            return success

        except ResourceException as e:
            self.logger.error(f"Proxmox API error restoring snapshot: {e}")
            return False
        except ValueError as e:
            self.logger.error(f"Service validation error: {e}")
            return False
        except ConnectionError as e:
            self.logger.error(f"Connection error: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error restoring snapshot: {e}")
            return False

    def delete_snapshot(self, service: ServiceConfig, snapshot_name: str) -> bool:
        """
        Delete a snapshot.

        Args:
            service: Service configuration
            snapshot_name: Name of the snapshot to delete

        Returns:
            True if deletion succeeded, False otherwise
        """
        try:
            # Validate service
            self._validate_service(service)

            # Get actual node
            node = self._get_actual_node(service)
            vm_type = self._get_vm_type(service)

            self.logger.info(
                f"Deleting snapshot '{snapshot_name}' from {vm_type}/{service.vmid}"
            )

            # Get API client and delete snapshot
            api = self._get_api_client()

            if service.type == "vm":
                result = (
                    api.nodes(node).qemu(service.vmid).snapshot(snapshot_name).delete()
                )
            else:  # lxc
                result = (
                    api.nodes(node).lxc(service.vmid).snapshot(snapshot_name).delete()
                )

            # Check if result is a task UPID
            if isinstance(result, str) and result.startswith("UPID:"):
                success = self._wait_for_task(node, result, timeout=600)
            else:
                success = True

            if success:
                self.logger.info(
                    f"Deleted snapshot '{snapshot_name}' from {vm_type}/{service.vmid}"
                )
            else:
                self.logger.error(
                    f"Failed to delete snapshot '{snapshot_name}' "
                    f"from {vm_type}/{service.vmid}"
                )

            return success

        except ResourceException as e:
            self.logger.error(f"Proxmox API error deleting snapshot: {e}")
            return False
        except ValueError as e:
            self.logger.error(f"Service validation error: {e}")
            return False
        except ConnectionError as e:
            self.logger.error(f"Connection error: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error deleting snapshot: {e}")
            return False

    def get_status(self, service: ServiceConfig) -> Dict[str, Any]:
        """
        Get the current status of a VM or container.

        Args:
            service: Service configuration

        Returns:
            Dictionary with status information:
            - status: 'running' or 'stopped'
            - node: actual node name
            - vmid: VM/LXC ID
            - cpu: CPU usage (0.0-1.0)
            - memory: Memory usage in bytes
            - uptime: Uptime in seconds
            - type: service type ('vm' or 'lxc')
            Returns empty dict on error
        """
        try:
            # Validate service
            self._validate_service(service)

            # Get actual node
            node = self._get_actual_node(service)

            # Get API client and query status
            api = self._get_api_client()

            if service.type == "vm":
                status_data = api.nodes(node).qemu(service.vmid).status.current.get()
            else:  # lxc
                status_data = api.nodes(node).lxc(service.vmid).status.current.get()

            # Extract relevant fields
            result = {
                "status": status_data.get("status", "unknown"),
                "node": node,
                "vmid": service.vmid,
                "type": service.type,
            }

            # Add optional fields if available
            if "cpu" in status_data:
                result["cpu"] = status_data["cpu"]
            if "mem" in status_data:
                result["memory"] = status_data["mem"]
            if "uptime" in status_data:
                result["uptime"] = status_data["uptime"]

            return result

        except ResourceException as e:
            self.logger.error(f"Proxmox API error getting status: {e}")
            return {}
        except ValueError as e:
            self.logger.error(f"Service validation error: {e}")
            return {}
        except ConnectionError as e:
            self.logger.error(f"Connection error: {e}")
            return {}
        except Exception as e:
            self.logger.error(f"Unexpected error getting status: {e}")
            return {}
