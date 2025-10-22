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