# Homelab Autopilot

**Safe, automated maintenance for your homelab infrastructure**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

> ⚠️ **Alpha Software**: Currently in active development (Phase 1). Not yet ready for production use.

## 🎯 What is Homelab Autopilot?

Homelab Autopilot is an open-source automation framework that helps homelab enthusiasts safely maintain their infrastructure with automated backups, monitoring, and updates. Think of it as a safety net that catches problems before they become disasters.

### Core Philosophy

- **Safety First**: Always backup before making changes
- **Fail Gracefully**: Automatic rollback on failures
- **Keep It Simple**: Python-first, minimal dependencies
- **Stay Informed**: Smart notifications only when needed

## ✨ Features

### Current (Phase 1 - In Development)

- ✅ **Configuration Management**
  - YAML-based configuration with Pydantic validation
  - Type-safe configuration models
  - Dot notation access and config merging
  - Comprehensive validation and error reporting

### Planned Features

- 🔄 **Automated Backups** (Phase 2)
  - VM/LXC backups via hypervisor APIs
  - Service configuration backups
  - Configurable retention policies
  - Compression and deduplication

- 🔄 **Safe Updates** (Phase 3)
  - Pre-update backups
  - Automated updates with rollback
  - Service validation after updates
  - Update scheduling and batching

- 🔄 **Health Monitoring** (Phase 4)
  - Service health checks
  - Resource monitoring
  - Automated recovery actions
  - Historical metrics

- 📬 **Smart Notifications** (Phase 2+)
  - Email, Slack, Discord, webhooks
  - Configurable alert levels
  - Notification cooldowns
  - Digest summaries

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

## ��️ Development Roadmap

### Phase 0: Foundation ✅ COMPLETE
- [x] Project structure
- [x] Documentation framework
- [x] Development guidelines
- [x] Dependency management

### Phase 1: Core Framework 🚧 IN PROGRESS (33% Complete)
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
  
- [ ] **State Manager** - Issue #TBD
  - SQLite key-value store
  - Track backup/update times
  - Thread-safe operations
  
- [ ] **Plugin Base Classes** - Issue #TBD
  - Abstract base classes
  - HypervisorPlugin, ServicePlugin, NotificationPlugin
  
- [ ] **Utility Functions** - Issue #TBD
  - Path validation
  - File operations
  - Common helpers
  
- [ ] **Test Infrastructure** - Issue #TBD
  - conftest.py setup
  - Shared fixtures
  - Test organization

### Phase 2: Backup System 📅 PLANNED
- [ ] Backup engine
- [ ] Proxmox hypervisor plugin
- [ ] Generic service plugin
- [ ] Email notification plugin

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
**Development Phase**: Phase 1 (Core Framework)  
**Test Coverage**: 95%+ (ConfigLoader: 95%, Logger: 100%)  
**Total Tests**: 75 passing (50 config + 25 logger)  
**Production Ready**: No - Active development

## �� License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Inspired by the homelab community
- Built with modern Python best practices
- Designed for safety and reliability

## �� Contact & Support

- **Issues**: [GitHub Issues](https://github.com/bryanfree66/homelab-autopilot/issues)
- **Discussions**: [GitHub Discussions](https://github.com/bryanfree66/homelab-autopilot/discussions)
- **Repository**: [github.com/bryanfree66/homelab-autopilot](https://github.com/bryanfree66/homelab-autopilot)

---

**⭐ Star this repo if you find it useful!**
