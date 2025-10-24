# Homelab Autopilot

**Safe, automated maintenance for your homelab infrastructure**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

> ⚠️ **Alpha Software**: Currently in active development (Phase 1). Not yet ready for production use.

## 🎯 What is Homelab Autopilot?

Homelab Autopilot is an open-source automation framework that **unifies backup management across VMs, LXC containers, Docker, and bare-metal** with intelligent application-aware orchestration. We solve the critical gap that no existing tool addresses: comprehensive homelab automation that treats Docker as a first-class citizen.

### Why Homelab Autopilot?

**Existing tools fall short for homelabs:**
- **Proxmox Backup Server**: Excellent VM/LXC backups, but no Docker intelligence or host config GUI
- **Veeam**: Doesn't support LXC containers, forcing you to run dual backup systems
- **Community Scripts**: Focus on deployment, not ongoing backup and update management
- **Manual Solutions**: Fragile, error-prone, and time-consuming

**Homelab Autopilot fills the gaps:**
- ✅ **Docker-Native Backups**: Application-aware backups that understand your containers (databases, volumes, configs)
- ✅ **Unified Multi-Workload**: Single tool for VMs + LXC + Docker + host configs
- ✅ **PBS Integration**: Leverage Proxmox Backup Server's proven deduplication (10-50x) when you want it
- ✅ **Flexible Storage**: Compression-only, PBS, or future native deduplication—your choice
- ✅ **Automated Restore Testing**: Monthly verification that your backups actually work (most find out they don't during disasters)
- ✅ **Safety-First Design**: Snapshots before changes, automatic rollback, production patterns for homelabs

### Core Philosophy

- **Safety First**: Always backup before making changes, verify restores actually work
- **Fail Gracefully**: Automatic rollback on failures with RTO tracking
- **Integration Over Replacement**: Extend PBS and Proxmox, don't compete with them
- **Docker Intelligence**: Application-aware backups with database dumps, maintenance mode
- **Keep It Simple**: Single binary deployment, 5-minute setup, Python-first
- **Stay Informed**: Smart notifications only when needed

## ✨ Features

### Current (Phase 1 - In Development)

- ✅ **Configuration Management**
  - YAML-based configuration with Pydantic validation
  - Type-safe configuration models
  - Dot notation access and config merging
  - Comprehensive validation and error reporting

- ✅ **Logging System**
  - Centralized logging with loguru
  - Multiple log levels with colorized console output
  - File logging with rotation, retention, and compression
  - Structured logging with context binding

- ✅ **State Management**
  - SQLite-based persistent state storage
  - Thread-safe key-value store
  - Support for multiple data types
  - State persistence across runs

- ✅ **Plugin System Foundation**
  - Abstract base classes for all plugin types
  - HypervisorPlugin for VM/LXC management
  - ServicePlugin for application-level operations
  - NotificationPlugin for alerts and notifications

### Planned Features

- 🔄 **Automated Backups** (Phase 2 - ACTIVE)
  - **Unified multi-workload**: VMs, LXC, Docker, host configs in one tool
  - **Docker-native intelligence**: Application-aware with database dumps, volume management
  - **Flexible storage backends**: Compression-only, PBS integration (10-50x deduplication), or future native chunking
  - **Automated restore testing**: Monthly verification with RTO tracking (Tier 1-3 validation)
  - **PBS integration**: Leverage Proxmox Backup Server when available, fallback to direct storage
  - Configurable retention policies with automatic cleanup
  - Production-grade verification and integrity checking

- 🔄 **Safe Updates** (Phase 3)
  - Pre-update snapshots with automatic rollback on failure
  - Application-aware update orchestration
  - Service validation after updates (health checks)
  - Update scheduling with maintenance windows
  - Dry-run mode for testing changes

- 🔄 **Health Monitoring** (Phase 4)
  - Service health checks (HTTP, TCP, process, custom)
  - Resource monitoring (CPU, memory, disk, network)
  - Automated recovery actions on failures
  - Historical metrics and trend analysis
  - Integration with Prometheus/Grafana

- 📬 **Smart Notifications** (Phase 2+)
  - Multiple channels: Email, Slack, Discord, webhooks
  - Severity-based routing (INFO, WARNING, ERROR, CRITICAL)
  - Configurable alert thresholds and cooldowns
  - Digest summaries for non-urgent updates
  - RTO metrics in backup reports

## 🌟 What Makes Us Different

### vs. Proxmox Backup Server (PBS)
- ✅ **We integrate with PBS**, not replace it—leverage PBS's 10-50x deduplication when you want it
- ✅ **Docker-native backups**—PBS doesn't understand containers
- ✅ **Host config GUI**—PBS requires command-line for host backups
- ✅ **Automated restore testing**—verify backups actually work
- ✅ **Flexible storage**—compression-only option for small homelabs without PBS complexity

### vs. Veeam
- ✅ **LXC container support**—Veeam doesn't, forcing dual backup systems
- ✅ **Free for all homelab sizes**—no per-VM licensing
- ✅ **Unified Docker + VM backups**—single tool, single workflow
- ✅ **Linux-native**—no Windows server required

### vs. Manual Scripts
- ✅ **Application-aware**—understands databases, volumes, dependencies
- ✅ **Automated restore testing**—monthly verification with RTO tracking
- ✅ **Safety-first design**—snapshots, rollback, error handling built-in
- ✅ **Centralized logging and state**—know what happened and when
- ✅ **Production patterns**—retry logic, circuit breakers, graceful degradation

### vs. Community Helper Scripts
- ✅ **Ongoing management**—not just deployment
- ✅ **Backup + monitoring + updates**—complete lifecycle automation
- ✅ **Plugin architecture**—extend without forking
- ✅ **Production-grade testing**—98% coverage, 10.0/10 pylint score

## 🚀 Quick Start

### Prerequisites

- Python 3.10 or higher
- Linux-based system (Ubuntu 22.04+ recommended)
- Hypervisor access (Proxmox VE supported, others coming soon)

### Installation (Development)
```bash
# Clone the repository
git clone https://github.com/bryanfree66/homelab-autopilot.git
cd homelab-autopilot

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements-dev.txt

# Install in editable mode
pip install -e .

# Run tests
pytest tests/ -v --cov
```

### Configuration (Coming Soon)
```bash
# Copy example configuration
cp config/homelab-autopilot.yaml.example config/homelab-autopilot.yaml

# Edit configuration
nano config/homelab-autopilot.yaml

# Validate configuration (coming soon)
homelab-autopilot validate
```

## 📖 Documentation

- **[Architecture Overview](docs/architecture.md)** - System design and components
- **[Contributing Guide](CONTRIBUTING.md)** - Development guidelines
- **[Changelog](CHANGELOG.md)** - Version history

More documentation coming as features are implemented!

## 🛠️ Development Roadmap

### Phase 0: Foundation ✅ COMPLETE
- [x] Project structure
- [x] Documentation framework
- [x] Development guidelines
- [x] Dependency management

### Phase 1: Core Framework ✅ COMPLETE
- [x] **Configuration Loader** ✅ COMPLETE
  - YAML parsing with PyYAML
  - Pydantic v2 validation
  - Dot notation access (max 5 levels)
  - Config merging with service appending
  - Proxmox-specific field validation
  - 50 tests, 95% coverage

- [x] **Logger Setup** ✅ COMPLETE
  - loguru configuration
  - File and console output
  - Log rotation with retention
  - Structured logging with context
  - 25 tests, 100% coverage

- [x] **State Manager** ✅ COMPLETE
  - SQLite key-value store
  - Thread-safe operations
  - Multiple data type support
  - State persistence across runs
  - 35 tests, 99% coverage

- [x] **Plugin Base Classes** ✅ COMPLETE
  - Abstract base classes (PluginBase)
  - HypervisorPlugin for VMs/LXCs
  - ServicePlugin for applications
  - NotificationPlugin for alerts
  - 32 tests, 91% coverage

- [x] **Utility Functions** ✅ COMPLETE
  - Path validation and sanitization
  - File operations helpers (ensure_directory, safe_remove)
  - Common validators (VMID, hostname)
  - Date/time utilities (timestamps, duration formatting)
  - Format helpers (bytes, filename sanitization)
  - 53 tests, 99% coverage

- [x] **Test Infrastructure** ✅ COMPLETE
  - Comprehensive test fixtures
  - VS Code test discovery configured
  - Makefile for automated checks
  - Pre-commit workflow established
  - CI/CD pipeline with pylint, black, pytest

### Phase 2: Backup System 📅 ACTIVE

**Goal**: Production-grade backup system with PBS integration and restore verification

- [ ] **Backup Engine** (Core Orchestration)
  - Backup routing logic (PBS → direct storage → local fallback)
  - Service-level backup orchestration
  - Plugin integration for hypervisors and services
  - Retention policy enforcement
  - State tracking and notification integration

- [ ] **Storage Backend Architecture** ⭐ NEW
  - **Tier 1: Compression Only** (Phase 2 baseline)
    - zstd compression (2-3x reduction)
    - Simple setup, good for small homelabs (<5 VMs)
  - **Tier 2: PBS Integration** (Phase 2 recommended)
    - Leverage PBS 10-50x deduplication
    - Client-side encryption, verification jobs
    - Production-ready for multi-VM homelabs
  - **Tier 3: Native Chunking** (Phase 5+)
    - Lightweight content-addressable storage
    - 5-15x deduplication without PBS complexity

- [ ] **Automated Restore Testing** ⭐ NEW
  - **Tier 1**: Integrity checks after every backup (checksum, extract test)
  - **Tier 2**: Monthly functional restore tests
    - Random service selection with RTO tracking
    - Isolated test environment (separate VLAN/namespace)
    - Application-aware health validation
  - **Tier 3**: Quarterly full DR drills (guided workflow)
  - Critical insight: "Many discover backups are corrupted only during disasters"

- [ ] **Proxmox Hypervisor Plugin**
  - PBS integration via proxmoxer
  - Direct storage backup via vzdump
  - VM/LXC snapshot management
  - Status monitoring

- [ ] **Generic Service Plugin**
  - Docker container backup (volume-aware)
  - Config file backup
  - Application-aware orchestration (maintenance mode, DB dumps)
  - Restore with dependency ordering

- [ ] **Email Notification Plugin**
  - SMTP integration
  - Severity-based routing
  - Backup status reports with RTO metrics
  - Failure alerts

**Documentation Deliverables**:
- Storage strategy decision flowchart
- PBS setup guide
- Restore testing runbook
- Real-world storage examples with calculations

### Phase 3: Update System 📅 PLANNED
- [ ] Update engine with rollback
- [ ] Service-specific update plugins
- [ ] External validation

### Phase 4: Monitoring System 📅 PLANNED
- [ ] Health check engine
- [ ] Multiple check types
- [ ] Recovery actions

### Phase 5: CLI & Scheduling 📅 PLANNED
- [ ] Command-line interface (click-based)
- [ ] **Configuration discovery tool** ⭐ NEW
  - Auto-scan Proxmox infrastructure
  - Generate initial config with smart defaults
  - Interactive setup wizard
  - See [design document](docs/discovery-tool.md)
- [ ] Cron/systemd integration
- [ ] Interactive configuration
- [ ] Dry-run mode for all operations

### Phase 6: Advanced Features 📅 PLANNED
- [ ] Web dashboard
- [ ] Additional hypervisors (ESXi, KVM)
- [ ] Multi-hypervisor discovery support
- [ ] Cloud storage backends (S3, B2, etc.)
- [ ] Advanced notifications (Discord, webhooks)
- [ ] Config diff and merge tools

## 🛠️ Technology Stack

- **Language**: Python 3.10+ (primary), Bash (system operations only)
- **Configuration**: PyYAML + Pydantic v2 for validation
- **State**: SQLite
- **Logging**: loguru
- **CLI**: click
- **Testing**: pytest with pytest-cov and pytest-mock
- **Code Quality**: black, pylint, mypy, isort

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

Key principles:
- **Python-first**: Use Python where possible, bash where necessary
- **Type hints**: Full type coverage with mypy
- **Tests**: Comprehensive pytest coverage (80%+ target)
- **Documentation**: Google-style docstrings

## 📊 Project Status

**Current Version**: 0.1.0-alpha
**Development Phase**: Phase 1 ✅ COMPLETE
**Test Coverage**:
- ConfigLoader: 95% (50 tests)
- Logger: 100% (25 tests)
- StateManager: 99% (35 tests)
- Plugin Base Classes: 91% (32 tests)
- Utility Functions: 99% (53 tests)
- **Overall: 98%** (195 tests passing)

**Production Ready**: No - Moving to Phase 2

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Inspired by the homelab community
- Built with modern Python best practices
- Designed for safety and reliability

## 📞 Contact & Support

- **Issues**: [GitHub Issues](https://github.com/bryanfree66/homelab-autopilot/issues)
- **Discussions**: [GitHub Discussions](https://github.com/bryanfree66/homelab-autopilot/discussions)
- **Repository**: [github.com/bryanfree66/homelab-autopilot](https://github.com/bryanfree66/homelab-autopilot)

---

**⭐ Star this repo if you find it useful!**
