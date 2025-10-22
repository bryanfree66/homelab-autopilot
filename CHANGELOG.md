# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Utility Functions (lib/utils.py)**: Common helper functions for the project
  - Path operations: validate_path(), ensure_directory(), safe_remove()
  - Date/time utilities: get_timestamp(), parse_timestamp(), human_readable_duration()
  - Format helpers: format_bytes(), sanitize_filename()
  - Validators: is_valid_vmid(), is_valid_hostname()
  - 53 comprehensive tests with 99% coverage
  - All functions with type hints and Google-style docstrings

- **Plugin Base Classes (plugins/base.py)**: Foundation for the plugin system
  - PluginBase: Abstract base class for all plugins
  - HypervisorPlugin: For managing VMs/LXCs (Proxmox, ESXi, KVM)
  - ServicePlugin: For application-level operations (Docker, systemd, generic)
  - NotificationPlugin: For sending alerts (Email, Slack, Discord, webhooks)
  - Helper methods for message formatting and emoji indicators
  - 32 comprehensive tests with 76% coverage
  
- **Code Quality Infrastructure**: Pylint configuration and CI/CD improvements
  - .pylintrc configuration file optimized for black compatibility
  - Automated code formatting with black (88 character line length)
  - GitHub Actions workflow for code quality checks
  - All code now passes pylint with 10.0/10.0 score

- **Logger Setup (lib/logger.py)**: Centralized logging with loguru
  - Multiple log levels with colorized console output
  - File logging with rotation, retention, and compression
  - Structured logging with context binding
  - 25 comprehensive tests with 100% coverage
  - Functions: setup_logger(), get_logger(), log_context(), set_log_level()

- **State Manager (lib/state_manager.py)**: SQLite-based state persistence
  - Thread-safe key-value store
  - Support for multiple data types (str, int, float, bool, datetime, dict, list)
  - Automatic JSON serialization for complex types
  - Methods: get(), set(), delete(), exists(), get_all(), clear(), get_keys()
  - 35 comprehensive tests with 99% coverage
  - Use cases: track backup times, update checks, notification cooldowns

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
  - Updated architecture documentation with plugin system details

### Changed
- Updated test fixtures to include required Proxmox fields
- ConfigLoader now appends services during merge instead of replacing
- README.md updated with Phase 1 progress (80% complete)
- Test coverage increased from 35% to 92% overall

### Phase 1 Progress
- ✅ Configuration Loader (Complete) - 50 tests, 95% coverage
- ✅ Logger Setup (Complete) - 25 tests, 100% coverage
- ✅ State Manager (Complete) - 35 tests, 99% coverage
- ✅ Plugin Base Classes (Complete) - 32 tests, 91% coverage
- ✅ Utility Functions (Complete) - 53 tests, 99% coverage
- ✅ Test Infrastructure (Complete)
- **Phase 1 Status: 6/6 components complete (100%)** ✅
- **Total Tests: 195 passing**
- **Overall Coverage: 98%**

## [0.1.0-alpha] - 2024-01-XX

### Added
- **Configuration Loader (core/config_loader.py)**: Initial implementation
  - YAML configuration loading with PyYAML
  - Pydantic v2 validation for type safety
  - Dot notation access for nested values
  - Configuration merging support
  - Comprehensive error messages
  - 50 tests with 95% coverage

- **Project Foundation**:
  - MIT License
  - README.md with project vision and quick start
  - CONTRIBUTING.md with development guidelines
  - Basic project structure (core/, lib/, plugins/, tests/)
  - Python packaging configuration (pyproject.toml)
  - Development dependencies (pytest, black, pylint, mypy)

### Phase 0: Foundation
- ✅ Project structure established
- ✅ Documentation framework created
- ✅ Development guidelines defined
- ✅ Dependency management configured
- **Phase 0: Complete**

---

## Version History

- **0.1.0-alpha**: Initial alpha release with Phase 0 and Phase 1 foundations
- **Unreleased**: Active Phase 1 development

## Upgrade Notes

### From Earlier Versions
This is the first alpha release. No upgrade path needed.

### Breaking Changes
None yet - alpha software, expect breaking changes between versions.

## Contributors

- Bryan Free - Initial development and architecture

---

For more details on upcoming features, see the [README.md](README.md) roadmap section.
