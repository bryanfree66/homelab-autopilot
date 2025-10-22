## [Unreleased]

### Added
- **Logger Setup (lib/logger.py)**: Centralized logging with loguru
  - Multiple log levels with colorized console output
  - File logging with rotation, retention, and compression
  - Structured logging with context binding
  - 25 comprehensive tests with 100% coverage
  - Functions: setup_logger(), get_logger(), log_context(), set_log_level()

- **Proxmox Configuration Enhancements**: Enhanced ServiceConfig validation
  - Proxmox-specific field validation (vmid, node required for vm/lxc)
  - Docker field validation (container_name required)
  - Systemd field validation (service_name required)
  - VMID range validation (100-999999)
  - 10 new validation tests
  
- **Documentation**:
  - Proxmox example configuration (config/homelab-autopilot-proxmox.yaml.example)
  - Discovery tool design document (docs/discovery-tool.md)
  - GitHub issue templates for project management

### Changed
- Updated test fixtures to include required Proxmox fields
- ConfigLoader now appends services during merge instead of replacing

### Phase 1 Progress
- ✅ Configuration Loader (Complete)
- ✅ Logger Setup (Complete)
- ✅  State Manager (Next)
- Components complete: 2/6 (33%)

- **State Manager (lib/state_manager.py)**: SQLite-based state persistence
  - Thread-safe key-value store
  - Support for multiple data types (str, int, float, bool, datetime, dict, list)
  - Automatic JSON serialization for complex types
  - Methods: get(), set(), delete(), exists(), get_all(), clear(), get_keys()
  - 35 comprehensive tests with 99% coverage
  - Use cases: track backup times, update checks, notification cooldowns