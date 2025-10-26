# Homelab Autopilot

**The safety net your homelab deserves—unified backup, monitoring, and updates that actually work**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Test Coverage](https://img.shields.io/badge/coverage-95%25-brightgreen.svg)](https://github.com/bryanfree66/homelab-autopilot)
[![Tests](https://img.shields.io/badge/tests-424%20passing-success.svg)](https://github.com/bryanfree66/homelab-autopilot)

> ⚠️ **Alpha Software**: Phase 2 nearly complete, moving to Phase 3. Not yet ready for production use, but alpha testing starting soon!

## 🎯 What is Homelab Autopilot?

**The problem**: You spent weeks building the perfect homelab—Proxmox VMs, LXC containers, Docker stacks, carefully configured services. Then disaster strikes: a failed update, corrupted storage, or accidental deletion. Do your backups actually work? When did you last test them? Can you restore your infrastructure in hours instead of days?

**Homelab Autopilot** is an open-source automation framework that acts as your homelab's safety net, catching problems before they become disasters. We provide **unified backup management, automated restore testing, and safe updates** across VMs, LXC containers, Docker services, and bare-metal systems—with intelligent application-aware orchestration that actually understands your infrastructure.

### The Critical Gap Nobody Else Fills

Existing tools force you to choose between incomplete coverage and overwhelming complexity:

| Feature | PBS | Veeam | Manual Scripts | **Homelab Autopilot** |
|---------|-----|-------|----------------|----------------------|
| VM/LXC Backups | ✅ Excellent | ✅ VMs only | ⚠️ Fragile | ✅ **Unified** |
| Docker Intelligence | ❌ No | ❌ No | ⚠️ Basic | ✅ **Application-aware** |
| Automated Restore Testing | ❌ No | ⚠️ Manual | ❌ No | ✅ **Monthly verification** |
| Host Config Backups | ⚠️ CLI only | ❌ No | ✅ Yes | ✅ **GUI + automation** |
| PBS Integration | N/A | ❌ No | ⚠️ DIY | ✅ **Native support** |
| Free for Homelab | ✅ Yes | ❌ Per-VM cost | ✅ Yes | ✅ **Always free** |

**The truth nobody talks about**: Most homelab operators discover their backups are corrupted or incomplete during disasters, not before. We solve this with automated restore testing and RTO tracking.

## ✨ Core Features

### 🔒 Safety-First Automation
- **Pre-change snapshots**: Never risk data loss from updates or changes
- **Automatic rollback**: Failed updates revert instantly, no manual intervention
- **Backup verification**: Test integrity after every backup—catch corruption early
- **Restore testing**: Monthly automated tests ensure your backups actually work
- **RTO tracking**: Know exactly how long recovery takes for each service

### 🐳 Docker-Native Intelligence
- **Application-aware backups**: Understands databases need proper dumps, not just volume copies
- **Maintenance mode**: Automatically gracefully stop services before backup
- **Volume intelligence**: Knows which volumes matter and which are cache
- **Dependency ordering**: Restores services in the right sequence
- **Health validation**: Verifies services are actually working after restore

### 🎯 Unified Multi-Workload Support
- **VMs**: Full disk backups via Proxmox API, PBS integration
- **LXC containers**: Native support (unlike Veeam)
- **Docker services**: Application-aware with compose integration
- **Host configs**: Backup Proxmox host settings, network configs, scripts
- **Bare-metal**: Generic file/directory backup support

### 💾 Flexible Storage Strategy
Choose the right backend for your homelab size and complexity:

1. **Compression-Only** (2-3x reduction)
   - Perfect for: Small homelabs, getting started, NFS to NAS
   - Simple setup, no additional infrastructure
   
2. **PBS Integration** (10-50x deduplication) ⭐ Recommended
   - Perfect for: Multi-VM homelabs, production-like setups
   - Leverage proven Proxmox Backup Server technology
   - Client-side encryption, verification jobs, incremental backups
   
3. **Native Chunking** (Phase 5+)
   - Perfect for: PBS-less setups wanting better deduplication
   - Lightweight content-addressable storage (5-15x reduction)

### 🎮 Cluster-Ready from Day One
Unlike tools that bolt on cluster support later (breaking everything), we designed for clusters from the start:
- **Query-based design**: Always check actual VM location via API, never assume
- **Shared storage aware**: PBS works cluster-wide, paths are configurable
- **No hardcoded nodes**: Service configs include node hints, but code queries dynamically
- **Future-proof**: Rolling updates, HA awareness, multi-node failover (Phase 3-6)

Even in Phase 2, your single-node config will work unchanged when you add cluster nodes later.

## 🌟 What Makes Homelab Autopilot Different

### vs. Proxmox Backup Server (PBS)
**We complement PBS, not replace it:**
- ✅ **Native PBS integration**—leverage its proven 10-50x deduplication when you want it
- ✅ **Docker-native backups**—PBS doesn't understand containers at all
- ✅ **Automated restore testing**—PBS stores backups, we verify they work
- ✅ **Host config GUI**—PBS requires command-line for host backups
- ✅ **Compression-only option**—use simple NFS storage if PBS is overkill

### vs. Veeam
**Homelab-first design, not enterprise compromises:**
- ✅ **LXC container support**—Veeam doesn't, forcing you to run dual systems
- ✅ **Always free**—no per-VM licensing, no feature tiers
- ✅ **Unified Docker + VM backups**—single tool, single workflow
- ✅ **Linux-native**—no Windows server required
- ✅ **Application-aware for homelabs**—understands common self-hosted apps

### vs. Manual Scripts
**Production patterns for homelab reliability:**
- ✅ **Application-aware**—understands databases, volumes, dependencies
- ✅ **Automated restore testing**—monthly verification with RTO tracking
- ✅ **Safety-first design**—snapshots, rollback, error handling built-in
- ✅ **Centralized observability**—structured logs, SQLite state, email notifications
- ✅ **Production-grade quality**—95% test coverage, 10.0/10 pylint, comprehensive CI/CD

### vs. Community Helper Scripts
**Ongoing lifecycle management, not just deployment:**
- ✅ **Complete automation**—backup + monitoring + updates in one framework
- ✅ **Plugin architecture**—extend without forking the codebase
- ✅ **Restore testing**—catch backup problems before disasters
- ✅ **Professional development**—Git workflow, semantic versioning, release notes
- ✅ **Active development**—regular updates, roadmap, community engagement

## 🚀 Quick Start

### Prerequisites

- **Python 3.12+** (uses modern type hints and features)
- **Linux-based system** (Ubuntu 22.04+ or Debian 12+ recommended)
- **Proxmox VE access** (API token with backup privileges)
- **Storage** (NFS mount, local storage, or PBS)

### Installation (Development/Alpha)

```bash
# Clone the repository
git clone https://github.com/bryanfree66/homelab-autopilot.git
cd homelab-autopilot

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements-dev.txt

# Install in editable mode
pip install -e .

# Run quality checks
make check  # Runs black, isort, pylint, pytest

# View test coverage
pytest tests/ -v --cov --cov-report=html
open htmlcov/index.html
```

### Configuration

**Coming with Phase 3 (CLI implementation):**

```yaml
# config/homelab-autopilot.yaml
global:
  backup:
    enabled: true
    root: /mnt/backups/homelab
    retention_days: 30
    compression: true
    
    # Optional: PBS integration
    proxmox_backup_server:
      enabled: true
      server: pbs.local
      datastore: homelab
      username: root@pam

services:
  - name: nextcloud
    type: vm
    vmid: 200
    node: pve  # Hint only - actual location queried via API
    backup: true
    
  - name: home-assistant
    type: lxc
    vmid: 201
    backup: true
    
  - name: immich
    type: docker
    compose_file: /opt/immich/docker-compose.yml
    backup: true
```

**Basic usage (coming soon):**
```bash
# Test configuration
homelab-autopilot validate

# Dry-run backup
homelab-autopilot backup --all --dry-run

# Backup single service
homelab-autopilot backup --service nextcloud

# Backup all services
homelab-autopilot backup --all

# Test restore (isolated environment)
homelab-autopilot restore-test --service nextcloud
```

## 📊 Current Status

**Version**: 0.3.0-alpha  
**Phase**: Phase 2 → Phase 3 transition (79% complete)

### Phase 1: Foundation ✅ COMPLETE
**195 tests passing, 98% coverage, 10/10 pylint score**

- ✅ **ConfigLoader**: YAML + Pydantic validation, PBS/DirectStorage models (50 tests, 95%)
- ✅ **Logger**: Structured logging with loguru, rotation, compression (25 tests, 100%)
- ✅ **StateManager**: SQLite key-value store, thread-safe (35 tests, 99%)
- ✅ **Plugin Base Classes**: Abstract classes for all plugin types (32 tests, 91%)
- ✅ **Utilities**: Path validation, file ops, common validators (53 tests, 99%)
- ✅ **Test Infrastructure**: Fixtures, CI/CD, comprehensive coverage

### Phase 2: Backup System 🔄 79% COMPLETE
**424 tests passing, 95% coverage**

**BackupEngine Core** (15/19 methods complete):
- ✅ Configuration retrieval and caching
- ✅ Timestamped backup filename generation  
- ✅ Service backup directory management
- ✅ Backup file listing and sorting
- ✅ Retention policy enforcement
- ✅ Backup destination routing (PBS → direct → local with validation)
- ✅ RTO-ready metadata generation
- ✅ Core backup command execution with duration tracking
- ✅ Plugin routing and caching
- ✅ Backup state queries (last time, status)
- ✅ State updates after backup operations
- ✅ Backup integrity verification
- ✅ Old backup rotation and cleanup
- ✅ Backup summary notifications
- ✅ Plugin cache management with tests
- 🔄 **In Progress**: Final orchestration methods (`backup_service`, `backup_all_services`)

**Next**: Plugin implementations (Proxmox, Generic Service, Email)

### Phase 3: Plugin Implementation 📅 STARTING SOON
- 📅 **ProxmoxPlugin**: VM/LXC backup via Proxmox API, PBS integration
- 📅 **GenericServicePlugin**: Docker/config backups, application-aware
- 📅 **EmailPlugin**: SMTP notifications, severity routing
- 📅 **CLI**: Command-line interface (click-based)
- 📅 **Alpha Testing**: Real-world validation on production homelab

### Phase 4+: Future Roadmap 🔮
- **Phase 4**: Safe update system with rollback
- **Phase 5**: Health monitoring and automated recovery  
- **Phase 6**: Scheduling, web dashboard, advanced features
- **Phase 7**: Full cluster support, cloud backends, multi-hypervisor

## 🛠️ Development Approach

### Technology Stack

- **Language**: Python 3.12+ with full type hints and modern features
- **Configuration**: PyYAML + Pydantic v2 for validation
- **State**: SQLite for persistence
- **Logging**: loguru for structured logging
- **Testing**: pytest with pytest-cov, pytest-mock (424 tests, 95% coverage)
- **Code Quality**: black, isort, pylint (10/10 score), mypy
- **API Integration**: proxmoxer for Proxmox VE

### Development Philosophy

**Quality Over Speed**:
- 🎯 **Test-driven**: Write tests first when possible, 95%+ coverage target
- 📝 **Type-safe**: Full type hints with mypy validation
- 📚 **Well-documented**: Google-style docstrings, comprehensive README
- 🔍 **Code quality**: 10/10 pylint score maintained across entire codebase
- 🔒 **Safety-first**: Cluster-aware design from day one, no breaking changes later

**Incremental Development**:
- Build one component at a time with full tests before moving on
- Each method implemented with comprehensive test coverage
- Regular `make check` ensures quality standards maintained
- Git commits after each working component

### Built with Claude AI Assistance

This project showcases an efficient AI-assisted development workflow:

**🤖 Workflow**: Chat (Claude) → Design → Code (Claude Code CLI) → Test → Review
- **Claude Chat** for architecture, design decisions, and planning
- **Claude Code CLI** for implementation and comprehensive test suites
- **Separate token pools** = token-efficient, no burnout on large conversations
- **Result**: Implemented 15 BackupEngine methods with 424 tests in focused sessions

**Why This Works**:
1. **Architecture in chat** uses minimal tokens for high-level design
2. **Implementation in Claude Code** uses its own token pool for the heavy lifting
3. **Quality maintained** through comprehensive tests and `make check` validation
4. **Fast iteration** while maintaining professional code standards

This approach lets us maintain 95% test coverage, 10/10 pylint scores, and comprehensive documentation while building complex features efficiently. If you're interested in AI-assisted development workflows, this repo demonstrates production-quality patterns.

**Tools Used**:
- [Claude Chat](https://claude.ai) for architectural planning and design review
- [Claude Code CLI](https://docs.claude.com/en/docs/claude-code) for implementation
- Both by [Anthropic](https://www.anthropic.com)

## 🤝 Contributing

We welcome contributions! This project is in active alpha development.

**Areas where we need help**:
- 🧪 **Alpha testing**: Test on real Proxmox environments, report issues
- 📚 **Documentation**: Improve setup guides, add examples
- 🐛 **Bug reports**: Detailed reproduction steps help us fix issues fast
- 💡 **Feature ideas**: What's missing for your homelab use case?

**Contributing Guidelines**:
- **Python-first**: Use Python where possible, bash only when necessary
- **Type hints**: Full type coverage required, mypy validation
- **Tests**: Comprehensive pytest coverage (95%+ target)
- **Documentation**: Google-style docstrings for all public methods
- **Code quality**: `make check` must pass (black, isort, pylint, pytest)

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

## 🎯 Project Goals

### Short Term (Phase 2-3)
- ✅ Complete BackupEngine orchestration methods
- 📅 Implement core plugins (Proxmox, GenericService, Email)
- 📅 Build CLI for alpha testing
- 📅 Alpha test on real homelab infrastructure
- 📅 Document real-world backup strategies

### Medium Term (Phase 4-5)
- 📅 Safe update system with rollback
- 📅 Health monitoring with automated recovery
- 📅 Automated restore testing (monthly verification)
- 📅 Scheduling and cron integration
- 📅 Configuration discovery wizard

### Long Term (Phase 6+)
- 📅 Full Proxmox cluster support
- 📅 Web dashboard for monitoring
- 📅 Additional hypervisors (ESXi, KVM)
- 📅 Cloud storage backends (S3, B2, etc.)
- 📅 Advanced notifications (Discord, Slack, webhooks)

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

**TL;DR**: Free for personal and commercial use. Do whatever you want with it.

## 🙏 Acknowledgments

- **Homelab Community**: For sharing real-world pain points and use cases
- **Proxmox Team**: For building excellent open-source virtualization
- **Python Community**: For maintaining incredible libraries and tools
- **Anthropic**: For Claude AI that accelerates development without sacrificing quality

Special thanks to everyone who shares their homelab experiences—your war stories and lessons learned shape better automation for everyone.

## 📞 Contact & Support

- **Issues**: [GitHub Issues](https://github.com/bryanfree66/homelab-autopilot/issues)
- **Discussions**: [GitHub Discussions](https://github.com/bryanfree66/homelab-autopilot/discussions)
- **Repository**: [github.com/bryanfree66/homelab-autopilot](https://github.com/bryanfree66/homelab-autopilot)

**Getting Started?**
1. ⭐ Star this repo to follow development
2. 👀 Watch for alpha release announcements
3. 💬 Join discussions to share your homelab use case
4. 🐛 Report issues if you're testing early

## 🎉 Why You'll Love This Project

**If you're tired of**:
- 😰 Fragile backup scripts that break mysteriously
- 🤷 Not knowing if your backups actually work until disaster strikes
- 🔧 Juggling multiple tools for VMs, containers, and Docker
- ⏰ Spending weekends manually testing restore procedures
- 💸 Enterprise backup software that costs more than your homelab hardware

**You'll appreciate**:
- ✅ One tool that handles everything
- ✅ Automated testing that verifies backups work
- ✅ Safety-first design that won't wreck your infrastructure
- ✅ Professional code quality you can trust
- ✅ Free forever, MIT licensed

---

**⭐ Star this repo if you believe homelabs deserve production-grade automation!**

*Built by homelab enthusiasts, for homelab enthusiasts. Because your side projects deserve the same reliability as your day job.*
