# 🚀 Homelab Autopilot

**Safe, automated maintenance for your homelab infrastructure**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status: Alpha](https://img.shields.io/badge/Status-Alpha-orange.svg)]()
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)]()

> **Project Status**: 🚧 Active Development - Not yet ready for production use

---

## The Problem

You've built an amazing homelab. You're running Home Assistant, Nextcloud, Immich, and a dozen other services that you and your family rely on daily. But maintenance is a nightmare:

- **Manual updates** are tedious and risky - what if something breaks?
- **Backups** require remembering to run scripts, checking if they worked
- **Monitoring** means SSH'ing in to check if services are still running
- **Rollback** after a failed update? Good luck remembering what you changed
- **Documentation?** What documentation? It's all tribal knowledge in your head

You know automation is the answer, but building it from scratch is daunting. Copy-pasting scripts from the internet feels sketchy. You want something **proven, safe, and actually designed for homelabs**.

## The Solution

**Homelab Autopilot** is an open-source automation framework that handles the boring, repetitive, and risky parts of homelab maintenance so you can focus on the fun stuff.

```yaml
# homelab-autopilot.yaml
services:
  - name: nextcloud
    type: generic-container
    hypervisor_id: 105
    config_paths:
      - /var/www/nextcloud/config/config.php
    auto_update: true
    snapshot_before_update: true
```

That's it. Homelab Autopilot now:
- ✅ **Backs up** your Nextcloud config daily (local + NFS + cloud)
- ✅ **Monitors** if Nextcloud is responding
- ✅ **Updates** Nextcloud safely with automatic snapshots
- ✅ **Rolls back** if the update fails validation
- ✅ **Alerts you** via email/Slack when something needs attention

## Key Features

### 🛡️ Safety First

- **Automatic snapshots** before any changes (rollback if things go wrong)
- **Validation testing** after updates (services must respond before considering update successful)
- **Dry-run mode** for everything (see what would happen without actually doing it)
- **Smart defaults** that never auto-reboot your host without asking

### 🔧 Flexible & Extensible

- **Configuration-driven** - Edit YAML, not bash scripts
- **Plugin architecture** - Easy to add support for new platforms and services
- **Works with what you have** - Proxmox, Docker, LXC, VMs (more platforms coming)
- **Modular design** - Use only the features you need

### 📊 Comprehensive Automation

- **Automated backups** with 3-2-1 strategy (local, NFS, cloud)
- **Health monitoring** with configurable check intervals
- **Safe updates** with validation and rollback
- **Smart notifications** with cooldown to prevent spam
- **External access validation** for reverse proxies and tunnels

### 🌟 Built for the Community

- **Open source** - MIT license, no vendor lock-in
- **Well documented** - Clear guides for beginners and advanced users
- **Community plugins** - Share your custom service integrations
- **Production tested** - Born from real-world homelab automation running 24/7

## Quick Start

> **Note**: Installation instructions coming soon! The project is in early development.

### Prerequisites

- Linux-based hypervisor (Proxmox VE, ESXi, Unraid, or bare metal)
- Python 3.10+
- Bash 4.0+ (for system operations)
- Root or sudo access

### Installation (Coming Soon)

```bash
# Clone the repository
git clone https://github.com/bryanfree66/homelab-autopilot.git
cd homelab-autopilot

# Run the installer
sudo ./install.sh

# Configure your services
sudo cp /etc/homelab-autopilot/homelab-autopilot.yaml.example \
        /etc/homelab-autopilot/homelab-autopilot.yaml
sudo nano /etc/homelab-autopilot/homelab-autopilot.yaml

# Test your configuration
homelab-autopilot validate

# Run your first backup (dry-run)
homelab-autopilot backup --all --dry-run

# If everything looks good, enable automation
homelab-autopilot setup-cron
```

## Example Use Cases

### Daily Automated Backups

```yaml
backup:
  schedule: "0 2 * * *"  # Daily at 2 AM
  retention_days: 30
  destinations:
    - local: /mnt/backups
    - nfs: 10.0.20.50:/mnt/backups
    - cloud: backblaze-b2
```

### Safe Weekend Updates

```yaml
updates:
  schedule: "0 3 * * 0"  # Sunday at 3 AM
  snapshot_before_update: true
  validate_after_update: true
  auto_rollback: true
  notification_email: admin@example.com
```

### Continuous Health Monitoring

```yaml
monitoring:
  check_interval: 300  # 5 minutes
  alert_on: ["service_down", "backup_failed", "update_failed"]
  alert_cooldown: 3600  # Don't spam - 1 alert per hour max
```

## Architecture

Homelab Autopilot is built with a modular architecture:

```
Core Engines          Plugins              Configuration
├─ Backup Engine  →  ├─ Proxmox       →   homelab-autopilot.yaml
├─ Update Engine  →  ├─ ESXi          →   (YAML-driven)
├─ Monitor Engine →  ├─ Docker        →
└─ Notify Engine  →  └─ Custom...     →
```

- **Core Engines** provide universal logic (backup, update, monitor, notify)
- **Plugins** extend functionality for specific platforms and services
- **Configuration** drives everything - no code changes needed

See [docs/architecture.md](docs/architecture.md) for detailed design.

## Current Status & Roadmap

### ✅ Completed

- [x] Project vision and architecture defined
- [x] Repository structure created
- [x] Initial documentation

### 🚧 In Progress (Phase 0-1)

- [ ] Core configuration loader
- [ ] Backup engine (generic)
- [ ] Proxmox hypervisor plugin
- [ ] Email notification plugin
- [ ] Installation script

### 📋 Planned (Phase 2-3)

- [ ] Update engine with rollback
- [ ] Monitoring engine
- [ ] Service plugins (Caddy, Nginx Proxy Manager, Docker Compose)
- [ ] Web dashboard (stretch goal)

### 🔮 Future Ideas

- [ ] ESXi and Unraid support
- [ ] Slack/Discord notifications
- [ ] Prometheus metrics integration
- [ ] Security scanning integration
- [ ] Mobile app for notifications

## Contributing

We welcome contributions! Whether you're:

- 🐛 Reporting bugs
- 💡 Suggesting features
- 📝 Improving documentation
- 🔌 Writing plugins for new platforms/services
- 🧪 Testing and providing feedback

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Ways to Help Right Now

Even though the project is early, you can help by:

1. **⭐ Star the repo** - Shows interest and helps others discover it
2. **💬 Join discussions** - Share your homelab setup and automation needs
3. **📣 Spread the word** - Tell other homelab enthusiasts
4. **🧪 Early testing** - Try it out and report issues (when alpha is ready)

## Philosophy

Homelab Autopilot is built on these principles:

1. **Safety First** - Never break your homelab. Always have a way back.
2. **Configuration Over Code** - Users edit YAML, not bash scripts.
3. **Sensible Defaults** - Works out of the box, customize if needed.
4. **Modular Design** - Use what you need, skip what you don't.
5. **Community Driven** - Built by homelab enthusiasts, for homelab enthusiasts.

## Inspiration

This project was born from a production homelab automation system that's been running reliably for over a year. The goal is to extract those proven patterns and make them accessible to everyone in the homelab community.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Support & Community

- **Issues**: [GitHub Issues](https://github.com/bryanfree66/homelab-autopilot/issues)
- **Discussions**: [GitHub Discussions](https://github.com/bryanfree66/homelab-autopilot/discussions)
- **Reddit**: r/homelab, r/selfhosted

---

**Built with ❤️ by the homelab community**

*Homelab Autopilot - Because your infrastructure should maintain itself*