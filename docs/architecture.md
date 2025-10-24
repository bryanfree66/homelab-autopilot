# Homelab Autopilot Architecture

This document describes the technical architecture of Homelab Autopilot - how components interact, design decisions, and extension points.

## Design Philosophy

Homelab Autopilot is built on these core principles:

1. **Configuration-Driven** - Users define what they want, not how to do it
2. **Plugin Architecture** - Easy to extend for new platforms and services
3. **Safety First** - Always backup before changes, easy rollback
4. **Modular Design** - Use what you need, skip what you don't
5. **Python + Bash** - Python for heavy lifting (config, logic, plugins), Bash for system orchestration

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     User Configuration                      │
│              homelab-autopilot.yaml (YAML)                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Core Framework                         │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐   │
│  │   Config    │  │    Logger    │  │  Notification   │   │
│  │   Loader    │  │              │  │     Engine      │   │
│  └─────────────┘  └──────────────┘  └─────────────────┘   │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐   │
│  │   Backup    │  │    Update    │  │    Monitor      │   │
│  │   Engine    │  │    Engine    │  │    Engine       │   │
│  └─────────────┘  └──────────────┘  └─────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Plugin Layer                           │
├─────────────────────────────────────────────────────────────┤
│  Hypervisors      │   Services          │  Notifications   │
│  ─────────────    │   ────────────      │  ──────────────  │
│  • Proxmox        │   • Generic         │  • Email         │
│  • ESXi           │   • Caddy           │  • Slack         │
│  • Libvirt        │   • Docker Compose  │  • Discord       │
│  • Docker         │   • NPM             │  • Custom        │
│  • Unraid         │   • Custom          │                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Target Infrastructure                     │
│       (Proxmox, Docker, VMs, Containers, Services)         │
└─────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
/opt/homelab-autopilot/          # Application installation
├── bin/
│   └── homelab-autopilot        # Main CLI entry point (bash wrapper)
├── core/                        # Core engines (Python)
│   ├── __init__.py
│   ├── config_loader.py         # Parse and validate config
│   ├── backup_engine.py         # Backup orchestration
│   ├── update_engine.py         # Update orchestration
│   ├── monitor_engine.py        # Health monitoring
│   └── notification_engine.py   # Alert sending
├── lib/                         # Shared libraries (Python)
│   ├── __init__.py
│   ├── utils.py                 # Common helper functions
│   ├── validators.py            # Input validation
│   ├── state_manager.py         # State persistence
│   └── logger.py                # Logging configuration
├── plugins/                     # Plugin ecosystem (Python)
│   ├── __init__.py
│   ├── hypervisors/
│   │   ├── __init__.py
│   │   ├── proxmox.py
│   │   ├── esxi.py
│   │   └── docker.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── generic_container.py
│   │   ├── caddy.py
│   │   ├── docker_compose.py
│   │   └── nginx_proxy_manager.py
│   └── notifications/
│       ├── __init__.py
│       ├── email.py
│       ├── slack.py
│       └── discord.py
└── templates/                   # Configuration templates
    ├── systemd/
    └── cron/

/etc/homelab-autopilot/          # Configuration
├── homelab-autopilot.yaml       # Main config
├── services.d/                  # Optional: per-service configs
├── plugins.d/                   # Optional: custom user plugins
└── secrets/                     # Credentials (git-ignored)

/var/lib/homelab-autopilot/      # State data
├── state.db                     # Runtime state (SQLite)
└── backups/                     # Local backup staging

/var/log/homelab-autopilot/      # Logs
├── main.log
├── backup.log
└── update.log
```

## Core Components

### 1. Configuration Loader (`core/config_loader.py`)

**Purpose**: Parse, validate, and provide access to configuration

**Responsibilities**:
- Load YAML configuration using PyYAML
- Validate configuration schema
- Merge multiple config files (main + services.d/)
- Provide accessor functions for other components
- Handle configuration defaults

**Key Functions**:
```python
class ConfigLoader:
    """Loads and manages YAML configuration"""
    
    def __init__(self, config_path: Path):
        """Initialize with config file path"""
        
    def get(self, key: str, default: Any = None) -> Any:
        """Get single config value using dot notation"""
        
    def get_array(self, key: str) -> List[Any]:
        """Get array of values"""
        
    def validate(self) -> bool:
        """Validate configuration schema"""
        
    def get_service_config(self, service_name: str) -> Dict:
        """Get specific service configuration"""
```

**Example Usage**:
```python
from pathlib import Path
from core.config_loader import ConfigLoader

config = ConfigLoader(Path("/etc/homelab-autopilot/homelab-autopilot.yaml"))
hypervisor = config.get("global.hypervisor")
services = config.get_array("services")
service_config = config.get_service_config("nextcloud")
```

### 2. Backup Engine (`core/backup_engine.py`)

**Purpose**: Orchestrate backups across all services

**Responsibilities**:
- Coordinate backups for all configured services
- Call appropriate hypervisor/service plugins
- Handle multiple backup destinations
- Verify backup integrity
- Manage retention policies
- Send notifications on success/failure

**Key Functions**:
```python
class BackupEngine:
    """Manages backup operations"""
    
    def backup_all_services(self) -> bool:
        """Backup all configured services"""
        
    def backup_service(self, service_name: str) -> bool:
        """Backup specific service"""
        
    def verify_backup(self, backup_path: Path) -> bool:
        """Verify backup integrity"""
        
    def apply_retention_policy(self) -> None:
        """Clean old backups based on retention policy"""
        
    def sync_to_destinations(self, backup_path: Path) -> bool:
        """Copy backup to all configured destinations"""
```

**Workflow**:
```
1. Load service configuration
2. For each service:
   a. Call hypervisor plugin to prepare
   b. Call service plugin to backup configs
   c. Create compressed archive
   d. Verify archive integrity
3. Sync to all destinations (local, NFS, cloud)
4. Apply retention policy
5. Send notification
```

### Backup Strategy Design (Phase 2)

**Philosophy**: Integrate with existing backup tools rather than replace them. Support multiple backup strategies to accommodate different homelab configurations.

#### Supported Backup Methods

Homelab Autopilot supports flexible backup strategies based on user configuration:

**1. Proxmox Backup Server (PBS) Integration**
- For users with PBS configured (VM/standalone)
- Uses Proxmox API to trigger backups to PBS datastore
- Leverages PBS's deduplication, encryption, and verification features
- Recommended for production homelabs

**2. Direct Storage Backup**
- Uses Proxmox's native `vzdump` to backup directly to NFS/local storage
- Simple, no additional services required
- Good for smaller setups or testing

**3. Hybrid Approach**
- Host configs → Direct storage (fast, small files)
- VMs/LXCs → PBS (advanced features)
- Common in production homelabs

#### Configuration Schema

```yaml
global:
  backup:
    enabled: true
    root: /mnt/backups/homelab  # Fallback/config backup location
    retention_days: 30
    compression: true
    
    # Optional: Proxmox Backup Server
    proxmox_backup_server:
      enabled: true
      server: 192.168.1.100
      port: 8007
      datastore: proxmox-backups
      username: root@pam
      password_command: "cat /etc/homelab-autopilot/secrets/pbs_password"
      verify_ssl: true
      
    # Optional: Direct storage
    direct_storage:
      enabled: true
      path: /mnt/nfs/backups
      format: vma  # vma (default) or tar

services:
  - name: nextcloud
    type: vm
    vmid: 200
    node: pve1
    backup: true  # Respects global backup strategy
```

#### Backup Decision Logic

```
For VM/LXC services:
  IF proxmox_backup_server.enabled == true:
    → Trigger vzdump backup to PBS datastore
  ELIF direct_storage.enabled == true:
    → Trigger vzdump backup to direct_storage.path
  ELSE:
    → Trigger vzdump backup to global.backup.root

For Docker/Systemd/Generic services:
  → Backup configs/volumes to global.backup.root
  
For Proxmox host configs:
  → Always backup to global.backup.root
  → Include: /etc/pve/, /var/lib/pve-cluster/config.db, 
             /etc/network/interfaces, /etc/hosts, /etc/hostname
```

#### Implementation Details

**ProxmoxPlugin Backup Methods:**
1. `_backup_to_pbs()` - Uses Proxmox API: `nodes(node).vzdump.create(storage='pbs-id')`
2. `_backup_to_storage()` - Uses Proxmox API: `nodes(node).vzdump.create(dumpdir='/path')`
3. Plugin determines method based on global configuration

**Retention Policy:**
- PBS-managed backups: Use PBS's native retention settings
- Direct storage backups: BackupEngine manages retention via `apply_retention_policy()`
- Host config backups: Always managed by BackupEngine

**Verification:**
- PBS backups: PBS handles verification internally
- Direct storage backups: BackupEngine verifies file existence, size, and optional extraction test

#### Proxmox Host Backup

Proxmox host configuration backup is supported via a special `host` service type:

```yaml
services:
  - name: proxmox-host-config
    type: host
    enabled: true
    backup: true
    backup_paths:  # Optional: customize what to backup
      - /etc/pve/
      - /var/lib/pve-cluster/config.db
      - /etc/network/interfaces
      - /etc/hosts
      - /etc/hostname
      - /root/custom-scripts/  # User's custom additions
```

**What Gets Backed Up:**
- **Default paths**: Essential Proxmox configs for quick rebuild after reinstall
- **Custom paths**: User can add additional directories (scripts, configs)
- **Format**: Compressed tar archive
- **Naming**: `proxmox-host-config_YYYYMMDD_HHMMSS.tar.gz`

**What Does NOT Get Backed Up:**
- VM/LXC disk images (use VM/LXC backups instead)
- System disk block-level backup (use Clonezilla/dd if needed)
- PBS datastore contents (handle separately)

**Restore Process:**
1. Fresh Proxmox install
2. Extract config backup
3. Restore configs to original locations
4. Reboot
5. VMs/LXCs appear in GUI, restore their data from backups

### 3. Update Engine (`core/update_engine.py`)

**Purpose**: Safely update services with automatic rollback

**Responsibilities**:
- Orchestrate updates for all configured services
- Create snapshots before updates (if supported)
- Call appropriate update plugins
- Validate services after updates
- Automatic rollback on failure
- Send notifications

**Key Functions**:
```python
class UpdateEngine:
    """Manages update operations"""
    
    def update_all_services(self) -> bool:
        """Update all configured services"""
        
    def update_service(self, service_name: str) -> bool:
        """Update specific service"""
        
    def create_snapshot(self, service_name: str) -> str:
        """Create pre-update snapshot, returns snapshot ID"""
        
    def validate_service(self, service_name: str) -> bool:
        """Test service after update"""
        
    def rollback_service(self, service_name: str, snapshot_id: str) -> bool:
        """Rollback service to snapshot"""
```

**Workflow**:
```
1. Load service configuration
2. Run pre-update safety checks
3. For each service:
   a. Create snapshot (if supported)
   b. Call service plugin to perform update
   c. Validate service is functional
   d. If validation fails:
      - Rollback to snapshot
      - Send alert
   e. If validation succeeds:
      - Clean up old snapshot
      - Send success notification
4. Generate update report
```

### 4. Monitor Engine (`core/monitor_engine.py`)

**Purpose**: Continuous health monitoring and alerting

**Responsibilities**:
- Periodic health checks for all services
- External access validation
- Resource monitoring (disk, memory)
- Alert on failures (with cooldown)
- Track service uptime

**Key Functions**:
```python
class MonitorEngine:
    """Manages monitoring and health checks"""
    
    def monitor_all_services(self) -> Dict[str, bool]:
        """Check all services, returns status dict"""
        
    def check_service_health(self, service_name: str) -> bool:
        """Check specific service health"""
        
    def check_external_access(self, url: str) -> bool:
        """Validate external URL is accessible"""
        
    def check_resources(self) -> Dict[str, float]:
        """Check system resources (disk, memory)"""
        
    def send_alert(self, alert_type: str, message: str) -> bool:
        """Send alert (with cooldown checking)"""
```

**Workflow**:
```
1. Load monitoring configuration
2. For each service:
   a. Perform health check (HTTP, process, etc.)
   b. Check external access (if configured)
   c. Record status
3. Check system resources
4. If issues detected:
   a. Check alert cooldown
   b. Send notification if cooldown expired
5. Update state database
```

### 5. Notification Engine (`core/notification_engine.py`)

**Purpose**: Send alerts via multiple channels

**Responsibilities**:
- Send notifications via email, Slack, Discord, etc.
- Manage notification cooldown (prevent spam)
- Format messages appropriately per channel
- Track notification history

**Key Functions**:
```python
class NotificationEngine:
    """Manages notifications across multiple channels"""
    
    def send_notification(
        self,
        alert_type: str,
        message: str,
        channels: Optional[List[str]] = None
    ) -> bool:
        """Send to specified channels (or all enabled)"""
        
    def send_email(self, subject: str, body: str) -> bool:
        """Send email notification"""
        
    def send_slack(self, message: str, channel: str) -> bool:
        """Send Slack message"""
        
    def send_discord(self, message: str) -> bool:
        """Send Discord message"""
        
    def check_cooldown(self, alert_type: str) -> bool:
        """Check if cooldown period has expired"""
```

**Notification Types**:
- `backup_success` / `backup_failed`
- `update_success` / `update_failed`
- `service_down` / `service_recovered`
- `external_access_failed`
- `rollback_executed`
- `disk_space_warning`

## Plugin Architecture

Plugins extend Homelab Autopilot's functionality for specific platforms and services.

### Plugin Types

1. **Hypervisor Plugins** - Platform-specific operations (Proxmox, ESXi, Docker)
2. **Service Plugins** - Service-specific handling (Caddy, Nginx, Docker Compose)
3. **Notification Plugins** - Alert channels (Email, Slack, Discord)

### Plugin Interface

All plugins must implement a standard interface:

```python
"""
Plugin: plugin-name
Type: hypervisor|service|notification
Description: Brief description
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any

class PluginBase(ABC):
    """Base class for all plugins"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize plugin with configuration"""
        self.config = config
    
    @abstractmethod
    def matches(self, target: Dict[str, Any]) -> bool:
        """
        Check if this plugin handles the target
        
        Args:
            target: Service or hypervisor configuration
            
        Returns:
            True if this plugin handles the target
        """
        pass

class ServicePlugin(PluginBase):
    """Base class for service plugins"""
    
    @abstractmethod
    def backup(self, destination: Path) -> bool:
        """Backup service configuration"""
        pass
    
    @abstractmethod
    def update(self) -> bool:
        """Update the service"""
        pass
    
    @abstractmethod
    def validate(self) -> bool:
        """Validate service after update"""
        pass
    
    def rollback(self) -> bool:
        """Rollback service (optional, default implementation)"""
        return True
```

### Plugin Discovery

Plugins are loaded from:
1. `/opt/homelab-autopilot/plugins/` (built-in)
2. `/etc/homelab-autopilot/plugins.d/` (custom user plugins)

**Loading Process**:
```python
import importlib
from pathlib import Path
from typing import List

def load_plugins(plugin_dir: Path) -> List[PluginBase]:
    """
    Dynamically load all plugins from directory
    
    Args:
        plugin_dir: Directory containing plugin modules
        
    Returns:
        List of instantiated plugin objects
    """
    plugins = []
    
    for plugin_file in plugin_dir.glob("**/*.py"):
        if plugin_file.name.startswith("_"):
            continue
            
        module_path = str(plugin_file.relative_to(plugin_dir).with_suffix(""))
        module_name = module_path.replace("/", ".")
        
        try:
            module = importlib.import_module(f"plugins.{module_name}")
            
            # Find plugin classes in module
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and 
                    issubclass(attr, PluginBase) and 
                    attr is not PluginBase):
                    plugins.append(attr)
                    
        except ImportError as e:
            logger.error(f"Failed to load plugin {module_name}: {e}")
    
    return plugins

# Find matching plugin for service
def find_plugin(service_config: Dict, plugins: List[PluginBase]) -> Optional[PluginBase]:
    """Find plugin that matches service configuration"""
    for plugin_class in plugins:
        plugin = plugin_class(service_config)
        if plugin.matches(service_config):
            return plugin
    return None
```

### Example: Proxmox Hypervisor Plugin

```python
"""
Plugin: proxmox
Type: hypervisor
Description: Proxmox VE LXC and VM management
"""

import subprocess
from pathlib import Path
from typing import Dict, Optional
from loguru import logger

from core.plugin_base import HypervisorPlugin


class ProxmoxPlugin(HypervisorPlugin):
    """Proxmox VE hypervisor plugin"""
    
    def __init__(self, config: Dict):
        super().__init__(config)
        self.host = config.get("global", {}).get("hypervisor_host")
    
    def matches(self, target: Dict) -> bool:
        """Check if this plugin handles Proxmox"""
        return self.config.get("global", {}).get("hypervisor") == "proxmox"
    
    def snapshot_create(self, container_id: int, snapshot_name: str) -> bool:
        """
        Create snapshot for LXC container
        
        Args:
            container_id: Proxmox container ID
            snapshot_name: Name for the snapshot
            
        Returns:
            True if snapshot created successfully
        """
        logger.info(f"Creating snapshot for CT {container_id}")
        
        try:
            result = subprocess.run(
                ["pct", "snapshot", str(container_id), snapshot_name],
                capture_output=True,
                text=True,
                check=True
            )
            logger.info(f"Snapshot created successfully: {snapshot_name}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create snapshot: {e.stderr}")
            return False
    
    def snapshot_rollback(self, container_id: int, snapshot_name: str) -> bool:
        """
        Rollback LXC container to snapshot
        
        Args:
            container_id: Proxmox container ID
            snapshot_name: Snapshot to rollback to
            
        Returns:
            True if rollback successful
        """
        logger.info(f"Rolling back CT {container_id} to snapshot {snapshot_name}")
        
        try:
            result = subprocess.run(
                ["pct", "rollback", str(container_id), snapshot_name],
                capture_output=True,
                text=True,
                check=True
            )
            logger.info("Rollback successful")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Rollback failed: {e.stderr}")
            return False
    
    def container_start(self, container_id: int) -> bool:
        """Start LXC container"""
        try:
            subprocess.run(
                ["pct", "start", str(container_id)],
                capture_output=True,
                check=True
            )
            return True
        except subprocess.CalledProcessError:
            return False
    
    def container_stop(self, container_id: int) -> bool:
        """Stop LXC container"""
        try:
            subprocess.run(
                ["pct", "stop", str(container_id)],
                capture_output=True,
                check=True
            )
            return True
        except subprocess.CalledProcessError:
            return False
    
    def container_status(self, container_id: int) -> bool:
        """
        Check if container is running
        
        Returns:
            True if running, False otherwise
        """
        try:
            result = subprocess.run(
                ["pct", "status", str(container_id)],
                capture_output=True,
                text=True,
                check=True
            )
            return "running" in result.stdout.lower()
        except subprocess.CalledProcessError:
            return False
```

## Data Flow

### Backup Flow

```
User Config → Backup Engine → Service Plugin → Hypervisor Plugin
                    ↓
              Compress/Archive
                    ↓
            Sync to Destinations
                    ↓
         Apply Retention Policy
                    ↓
          Send Notification
```

### Update Flow

```
User Config → Update Engine → Pre-Update Check
                    ↓
           Create Snapshot (Hypervisor Plugin)
                    ↓
           Perform Update (Service Plugin)
                    ↓
           Validate Service
                    ↓
    ┌───────────────┴───────────────┐
    │                               │
Success                         Failure
    │                               │
Clean Snapshot              Rollback Snapshot
    │                               │
    └───────────────┬───────────────┘
                    ↓
          Send Notification
```

## State Management

State is persisted in `/var/lib/homelab-autopilot/state.db` (SQLite database for structured data):

**State Functions**:
```python
from datetime import datetime
from pathlib import Path
from typing import Optional, Any
import sqlite3

class StateManager:
    """Manages persistent state"""
    
    def __init__(self, db_path: Path):
        """Initialize state manager with database path"""
        self.db_path = db_path
        self._init_db()
    
    def get(self, key: str, default: Optional[Any] = None) -> Optional[Any]:
        """Get value for key"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT value FROM state WHERE key = ?",
                (key,)
            )
            result = cursor.fetchone()
            return result[0] if result else default
    
    def set(self, key: str, value: Any) -> None:
        """Set value for key"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO state (key, value, updated_at) VALUES (?, ?, ?)",
                (key, str(value), datetime.now().isoformat())
            )
    
    def delete(self, key: str) -> None:
        """Delete key"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM state WHERE key = ?", (key,))
    
    def exists(self, key: str) -> bool:
        """Check if key exists"""
        return self.get(key) is not None

# Usage examples:
state = StateManager(Path("/var/lib/homelab-autopilot/state.db"))
state.set("last_backup.nextcloud", datetime.now().isoformat())
last_backup = state.get("last_backup.nextcloud")
```

## Configuration Schema

See [homelab-autopilot.yaml.example](../homelab-autopilot.yaml.example) for complete schema.

**Key Sections**:
- `global` - System-wide settings
- `notifications` - Alert configuration
- `backup` - Backup policies
- `monitoring` - Health check settings
- `updates` - Update policies
- `services` - Service definitions

## Security Considerations

### Credentials Management

- **Never commit credentials** to git
- Store sensitive data in `/etc/homelab-autopilot/secrets/`
- Use `*_command` config options to read credentials from files
- Restrict permissions: `chmod 600 /etc/homelab-autopilot/secrets/*`

### Execution Privileges

- Runs as root (required for container/VM management)
- Uses `nice` and `ionice` for lower priority
- Respects file permissions
- Validates all inputs

### Network Security

- External access validation uses HTTPS
- Supports authentication for external services
- Respects firewall rules

## Performance Considerations

- **Sequential by default** - Updates run one at a time
- **Configurable parallelism** - Can enable parallel backups
- **Resource limits** - Uses nice/ionice for lower priority
- **Timeout protection** - All operations have timeouts

## Testing Strategy

### Unit Tests

- Test individual functions in isolation
- Mock external dependencies
- Test error conditions

### Integration Tests

- Test plugin interactions
- Test complete workflows (backup, update, monitor)
- Test on real (non-production) services

### Dry-Run Mode

- Simulate all operations without making changes
- Log what would be done
- Validate configuration

## Extension Points

### Adding a New Hypervisor

1. Create `plugins/hypervisors/my_hypervisor.py`
2. Implement plugin interface (inherit from `HypervisorPlugin`)
3. Add documentation
4. Submit PR

### Adding a New Service

1. Create `plugins/services/my_service.py`
2. Implement service-specific logic (inherit from `ServicePlugin`)
3. Add example configuration
4. Submit PR

### Adding a Notification Channel

1. Create `plugins/notifications/my_channel.py`
2. Implement notification interface (inherit from `NotificationPlugin`)
3. Add configuration options
4. Submit PR

## Automated Restore Testing Architecture

### Philosophy

**Critical Insight from Research**: "Many organizations discover their backups are corrupted only during actual disaster recovery—the only reliable test is periodic restoration."

Homelab Autopilot implements multi-tier backup verification to ensure backups are actually restorable:

### Three-Tier Verification Strategy

#### Tier 1: Integrity Checks (Phase 2)
**Fast checks run after every backup**:
- File exists and has expected size
- Archive extracts without errors
- Checksums/signatures validate
- Metadata is complete

**Implementation**: Already part of `BackupEngine.verify_backup()`

#### Tier 2: Functional Restore Testing (Phase 3)
**Monthly automated restore testing**:
- Randomly select services for restore testing
- Restore to isolated test environment (separate VLAN/namespace)
- Start service and verify functionality
- Run application-specific health checks
- Measure and track RTO (Recovery Time Objective)
- Cleanup test environment automatically
- Alert on failures

**Implementation**: New `RestoreEngine` component

```python
class RestoreEngine:
    """Automated restore testing and disaster recovery orchestration"""
    
    def __init__(self, config: ConfigLoader, state: StateManager):
        """Initialize restore engine"""
        self.config = config
        self.state = state
        self.logger = get_logger()
    
    def test_restore_service(
        self, 
        service_name: str, 
        test_environment: str = None
    ) -> RestoreTestResult:
        """
        Restore service to isolated test environment and validate
        
        Process:
        1. Select backup (latest or specific version)
        2. Provision test environment (isolated VLAN/namespace)
        3. Restore service to test environment
        4. Start service
        5. Run plugin-defined health checks
        6. Measure RTO
        7. Cleanup test environment
        8. Record results in state database
        
        Returns:
            RestoreTestResult with success status, RTO, and validation results
        """
        
    def schedule_random_restore_tests(self, count: int = 3) -> List[RestoreTestResult]:
        """
        Randomly select services for monthly restore testing
        
        Selection strategy:
        - Prioritize services not tested recently
        - Weight by service criticality (from config)
        - Ensure diverse service types (VM, LXC, Docker)
        
        Args:
            count: Number of services to test this cycle
            
        Returns:
            List of restore test results
        """
        
    def validate_service_health(self, service: ServiceConfig) -> HealthCheckResult:
        """
        Run application-specific health validation
        
        Delegates to service plugin for custom checks:
        - Database: Can connect, query system tables
        - Web server: HTTP response, expected content
        - Container: Process running, ports listening
        
        Returns:
            Health check results with detailed diagnostics
        """
        
    def full_disaster_recovery_drill(self, restore_plan: str) -> DRDrillResult:
        """
        Execute full disaster recovery drill (quarterly/annual)
        
        This is a guided workflow with manual verification steps:
        1. Display pre-checks and preparation steps
        2. Orchestrate restore of all critical services
        3. Validate inter-service dependencies
        4. Generate DR report with lessons learned
        5. Update runbooks based on findings
        
        Args:
            restore_plan: Path to DR plan YAML
            
        Returns:
            Detailed drill results and recommendations
        """
```

**Configuration Schema**:

```yaml
global:
  backup:
    restore_testing:
      enabled: true
      schedule: "monthly"  # or cron expression
      random_services: 3
      test_environment:
        type: "isolated_vlan"  # or "namespace", "separate_node"
        vlan_id: 999
        network: "10.99.0.0/24"
      rto_target_minutes: 15  # Alert if restore takes longer
      cleanup_after_test: true
      cleanup_delay_minutes: 5  # Time to inspect before cleanup
      notifications:
        on_success: false
        on_failure: true
        include_rto_metrics: true

services:
  - name: nextcloud
    type: vm
    # ... other config ...
    restore_testing:
      priority: high  # Test more frequently
      health_checks:
        - type: http
          url: "http://localhost/status.php"
          expected_status: 200
        - type: database
          command: "mysql -e 'SELECT 1'"
        - type: custom
          script: "/opt/homelab-autopilot/checks/nextcloud_health.sh"
```

**RTO Metrics Tracking**:

```python
# State database schema for restore test results
{
    "restore_tests": {
        "nextcloud_20250123_143022": {
            "service": "nextcloud",
            "test_timestamp": "2025-01-23T14:30:22Z",
            "backup_used": "nextcloud_20250122_020000_vm.tar.gz",
            "success": true,
            "rto_seconds": 847,
            "health_checks_passed": 3,
            "health_checks_failed": 0,
            "test_environment": "vlan-999",
            "cleaned_up": true
        }
    }
}
```

#### Tier 3: Full DR Drills (Phase 4)
**Quarterly or annual full infrastructure restore**:
- Guided workflow with runbook automation
- Restore all critical services in dependency order
- Manual verification steps at key points
- Generate comprehensive DR report
- Update runbooks based on findings
- Executive summary for stakeholders

### Benefits

1. **Confidence**: Know backups work before you need them
2. **RTO Visibility**: Understand how long recovery actually takes
3. **Runbook Validation**: Keep DR procedures current
4. **Continuous Improvement**: Learn from test failures safely
5. **Compliance**: Document restore capability for audits

## Deduplication Strategy Architecture

### The Storage Efficiency Spectrum

Homelab Autopilot supports three deduplication strategies, each with different trade-offs:

### Strategy Comparison

| Strategy | Complexity | Storage Efficiency | Speed | Best For |
|----------|-----------|-------------------|-------|----------|
| **Compression Only** | Low | 2-3x | Fast | Small homelabs (<5 VMs), testing |
| **PBS Integration** | Medium | 10-50x | Medium | Production homelabs, multiple VMs/LXCs |
| **Native Chunking** | High | 5-15x | Medium | Users wanting dedup without PBS |

### Tier 1: Compression Only (Phase 2 - Available Now)

**How It Works**:
- Create tar archives of backups
- Compress with zstd (level 3 default, configurable)
- Store as individual files

**Storage Efficiency**:
- ~2-3x reduction for typical VM disk images
- ~3-5x reduction for text configs and logs
- No deduplication between backups

**Configuration**:
```yaml
global:
  backup:
    root: /mnt/backups/homelab
    compression: true
    compression_algorithm: zstd  # or gzip, lz4
    compression_level: 3  # 1-19 for zstd
```

**Storage Growth Example**:
```
Service: nextcloud (32GB VM)
Daily backups, 30-day retention:

Without compression: 32GB × 30 = 960GB
With zstd compression: 12GB × 30 = 360GB (2.7x reduction)
With PBS deduplication: ~25GB total (37x reduction)
```

**When to Use**:
- Getting started with Homelab Autopilot
- Small homelab (1-5 VMs)
- Testing and development
- Budget storage (don't mind larger sizes)

### Tier 2: PBS Integration (Phase 2 - Recommended)

**How It Works**:
- Proxmox Backup Server uses content-addressable storage
- 4 MiB fixed chunks for VMs (block devices)
- Dynamic chunks for file systems (buzhash rolling hash)
- SHA-256 fingerprinting for deduplication
- Client-side encryption (AES-256-GCM)

**Storage Efficiency**:
- 10-50x deduplication for typical workloads
- Production users report 42TB restored data from 170GB stored
- Incremental backups transfer only changed chunks
- First backup: 85 seconds for 32GB
- Subsequent backups: 4 seconds for 1.2GB changes

**Configuration**:
```yaml
global:
  backup:
    root: /mnt/backups/homelab  # Fallback for host configs
    
    proxmox_backup_server:
      enabled: true
      server: 192.168.1.100
      port: 8007
      datastore: main-backups
      username: root@pam
      password_command: "cat /etc/homelab-autopilot/secrets/pbs_password"
      verify_ssl: true
      
      # Optional: Sync to second PBS for redundancy
      sync_jobs:
        - target_server: 192.168.2.100
          target_datastore: offsite-backups
          schedule: "daily"
```

**Storage Growth Example**:
```
Environment: 10 VMs, 300GB total, daily backups, 30-day retention

Without PBS: 300GB × 30 = 9TB
With PBS: ~800GB total (11x deduplication)
  - Day 1: 300GB (full)
  - Days 2-30: ~20GB/day (incrementals)
```

**PBS Setup Requirements**:
- Dedicated VM or physical machine
- 4GB+ RAM recommended
- SSD for datastore (HDD acceptable for archival)
- Network bandwidth for backup traffic

**When to Use**:
- Production homelab
- Multiple VMs/LXCs (5+)
- Limited storage budget
- Want verification and encryption features
- Already using Proxmox VE

### Tier 3: Native Chunk-Based Storage (Phase 5+ - Future)

**Planned Features**:
- Lightweight content-addressable storage
- Inspired by PBS but simpler implementation
- SQLite for chunk metadata
- Filesystem for chunk storage
- Optional client-side encryption

**Target Efficiency**:
- 5-15x deduplication
- Balance between complexity and efficiency
- No separate server required

**Use Case**:
- Users who want deduplication
- Don't want PBS complexity
- Willing to trade some efficiency for simplicity

**Implementation Notes**:
This will be built on the Storage Backend abstraction (see below).

### Storage Backend Abstraction

To support all strategies, Homelab Autopilot uses pluggable storage backends:

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

@dataclass
class StorageMetrics:
    """Storage efficiency metrics"""
    total_backups: int
    logical_size_bytes: int  # Size if not deduplicated
    physical_size_bytes: int  # Actual disk usage
    deduplication_ratio: float  # logical/physical
    compression_ratio: float
    storage_efficiency: float  # Combined dedup+compression

class StorageBackend(ABC):
    """Abstract storage backend for backup data"""
    
    @abstractmethod
    def store_backup(
        self, 
        backup_data: bytes, 
        metadata: BackupMetadata
    ) -> str:
        """
        Store backup data, return unique identifier
        
        Returns:
            Backup identifier (path, PBS snapshot ID, etc.)
        """
        
    @abstractmethod
    def retrieve_backup(self, identifier: str) -> bytes:
        """Retrieve backup data by identifier"""
        
    @abstractmethod
    def list_backups(
        self, 
        service_name: str = None
    ) -> List[BackupMetadata]:
        """List available backups, optionally filtered by service"""
        
    @abstractmethod
    def delete_backup(self, identifier: str) -> bool:
        """Delete backup by identifier"""
        
    @abstractmethod
    def get_storage_metrics(self) -> StorageMetrics:
        """Return storage efficiency metrics"""
        
    @abstractmethod
    def verify_integrity(self, identifier: str) -> bool:
        """Verify backup integrity (checksums, etc.)"""


class CompressedFileBackend(StorageBackend):
    """Simple compressed tar.gz files (Tier 1)"""
    
    def __init__(self, backup_root: Path, compression: str = "zstd"):
        self.backup_root = backup_root
        self.compression = compression


class ProxmoxBackupServerBackend(StorageBackend):
    """PBS integration via proxmoxer (Tier 2)"""
    
    def __init__(self, pbs_config: ProxmoxBackupServerConfig):
        self.pbs_config = pbs_config
        self.client = ProxmoxAPI(...)  # proxmoxer


class ChunkedStorageBackend(StorageBackend):
    """Future: Native chunk-based deduplication (Tier 3)"""
    
    def __init__(self, storage_root: Path, chunk_size: int = 4 * 1024 * 1024):
        self.storage_root = storage_root
        self.chunk_size = chunk_size
        self.metadata_db = SQLite(...)
```

### Decision Flowchart

```
Start: Need to backup homelab?
│
├─ Small homelab (<5 VMs)? ──Yes──> Use Compression Only
│                                     - Simple setup
│                                     - Good enough for small scale
│
├─ Already using Proxmox? ──Yes──> Use PBS Integration
│                                    - Best deduplication
│                                    - Enterprise features
│
├─ Want deduplication but not PBS? ──Yes──> Wait for Native Chunking (Phase 5)
│                                             Or use Compression + larger storage
│
└─ Not sure? ──> Start with Compression Only
                  Migrate to PBS later (easy transition)
```

### Migration Path

Users can transition between strategies:

1. **Compression → PBS**: 
   - Enable PBS in config
   - Run first full backup to PBS
   - Keep compressed backups as archive
   
2. **PBS → Compression**:
   - Disable PBS in config
   - System falls back to compression
   - PBS backups remain accessible

3. **Compression → Native Chunking** (future):
   - Enable chunked storage backend
   - Incremental migration of backups
   - No downtime required

### Documentation Strategy

For users to make informed decisions, we'll provide:

1. **Storage Calculator**: Web tool estimating storage needs
   - Input: VM count, sizes, change rate, retention
   - Output: Storage requirements per strategy

2. **Real-World Examples**: 
   - Small homelab (3 VMs): Compression sufficient
   - Medium homelab (10 VMs): PBS recommended
   - Large homelab (25+ VMs): PBS essential

3. **Cost-Benefit Analysis**:
   - Setup time vs storage savings
   - Operational complexity vs features
   - When to invest in PBS

4. **Best Practices Guide**:
   - PBS hardware recommendations
   - Network design for backup traffic
   - Testing and validation procedures

## Future Architecture Improvements

### Planned Enhancements

- **Web Dashboard** - View status, logs, and configuration
- **API Layer** - RESTful API for external integrations
- **Metrics** - Prometheus exporter for monitoring
- **Database** - SQLite for state management (instead of flat file)
- **Job Queue** - Better handling of long-running operations

### Design Considerations

- Maintain backward compatibility
- Keep core simple and portable
- Optional advanced features (dashboard, API)
- Plugin architecture supports all enhancements

---

## Questions or Suggestions?

This architecture is designed to be extensible and maintainable. If you have questions or suggestions for improvements, please open an issue or discussion on GitHub!