# Configuration Discovery Tool

**Status**: Planned for Phase 5 or 6  
**Priority**: Medium  
**Complexity**: Medium

## Overview

The Configuration Discovery Tool automatically scans your Proxmox infrastructure and generates an initial `homelab-autopilot.yaml` configuration file. This eliminates manual configuration entry and reduces setup errors.

## User Experience

### Basic Usage
````bash
# Interactive discovery
homelab-autopilot discover

# Non-interactive with credentials
homelab-autopilot discover \
  --host pve.homelab.local \
  --user root@pam \
  --password-file ~/.proxmox-password

# Output to specific file
homelab-autopilot discover --output custom-config.yaml

# Dry-run mode (preview without saving)
homelab-autopilot discover --dry-run
````

### Expected Output
````
┌─────────────────────────────────────────────────┐
│  Homelab Autopilot - Configuration Discovery   │
└─────────────────────────────────────────────────┘

Connecting to Proxmox...
✓ Connected to Proxmox VE 8.2.0
✓ Authenticated as root@pam

Scanning infrastructure...
✓ Found 2 nodes: pve, pve2
✓ Discovered 5 VMs
✓ Discovered 8 LXC containers
✓ Detected backup storage: /mnt/backups

Generating configuration...
✓ Created global configuration
✓ Added 13 services with smart defaults
✓ Detected TrueNAS VM (disabled auto-updates)
✓ Detected Proxmox Backup Server (special handling)

Configuration saved to: homelab-autopilot.yaml

Next steps:
1. Review the generated configuration
2. Set your notification settings (email/slack)
3. Add/remove any unwanted services
4. Validate: homelab-autopilot validate config
5. Test: homelab-autopilot backup --dry-run

Note: Password/tokens not included - add manually
````

## Generated Configuration Example
````yaml
# Auto-discovered from pve.homelab.local on 2025-10-22 14:35:00
# Homelab Autopilot v0.3.0
#
# IMPORTANT: Review and edit this configuration before use
# - Add your password or API token
# - Configure notification settings
# - Adjust backup/update/monitor flags as needed

global:
  hypervisor:
    type: proxmox
    host: pve.homelab.local
    username: root@pam
    # TODO: Add password or API token
    # password: your_secure_password
    # OR use API token (recommended):
    # token_id: automation@pve!autopilot
    # token_secret: your-token-secret
    verify_ssl: false
  
  backup:
    enabled: true
    root: /mnt/backups/homelab-autopilot
    retention_days: 30
    compression: true
  
  update:
    enabled: true
    auto_update: false  # Set to true to enable automatic updates
    check_interval_hours: 24
  
  monitoring:
    enabled: true
    check_interval_minutes: 5
  
  notification:
    enabled: false  # TODO: Configure notification settings
    type: email
    settings:
      smtp_host: smtp.gmail.com
      smtp_port: 587
      # from_addr: TODO
      # to_addr: TODO

# Services discovered: 13 total (5 VMs, 8 LXC)
services:
  # Node: pve | LXC Container | Ubuntu 22.04 | Running | 2GB RAM
  - name: proxmox-backup-server
    type: lxc
    vmid: 101
    node: pve
    enabled: true
    backup: true
    update: true
    monitor: true
  
  # Node: pve | VM | TrueNAS-13.0-U6.2 | Running | 16GB RAM | 6 disks
  # Note: Auto-updates disabled - TrueNAS manages its own updates
  - name: truenas
    type: vm
    vmid: 102
    node: pve
    enabled: true
    backup: true
    update: false  # TrueNAS self-managed
    monitor: true
  
  # Node: pve | LXC Container | Ubuntu 24.04 | Running | 4GB RAM
  - name: nextcloud
    type: lxc
    vmid: 103
    node: pve
    enabled: true
    backup: true
    update: true
    monitor: true
  
  # ... more services ...
````

## Technical Design

### Architecture
````
┌─────────────────┐
│   CLI Command   │
│  discover.py    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Discovery Core  │
│ - Scan infra    │
│ - Smart defaults│
│ - Config gen    │
└────────┬────────┘
         │
         ├──────────────┬──────────────┬──────────────┐
         ▼              ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│   Proxmox    │ │   VM/LXC     │ │   Template   │ │   Validator  │
│   API        │ │   Analyzer   │ │   Engine     │ │              │
│   Client     │ │              │ │              │ │              │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
````

### Core Components

#### 1. Discovery Engine (`lib/discovery.py`)
````python
class DiscoveryEngine:
    """Main discovery orchestrator."""
    
    def __init__(self, hypervisor_client):
        self.client = hypervisor_client
        self.analyzer = ServiceAnalyzer()
        self.template = ConfigTemplate()
    
    def discover(self) -> ConfigStructure:
        """Run full discovery process."""
        # 1. Gather infrastructure data
        nodes = self.client.get_nodes()
        services = self._discover_services(nodes)
        storage = self._discover_storage()
        
        # 2. Analyze and classify
        analyzed = [self.analyzer.analyze(s) for s in services]
        
        # 3. Generate config
        return self.template.generate(
            nodes=nodes,
            services=analyzed,
            storage=storage
        )
````

#### 2. Service Analyzer (`lib/discovery/analyzer.py`)
````python
class ServiceAnalyzer:
    """Analyzes services and suggests smart defaults."""
    
    def analyze(self, service: ProxmoxService) -> AnalyzedService:
        """Analyze service and recommend settings."""
        suggestions = {
            'backup': True,  # Default to backing up
            'update': self._should_auto_update(service),
            'monitor': True,
        }
        
        return AnalyzedService(
            service=service,
            suggestions=suggestions,
            metadata=self._extract_metadata(service)
        )
    
    def _should_auto_update(self, service: ProxmoxService) -> bool:
        """Determine if service should auto-update."""
        # Detect special cases
        os_name = service.os_type.lower()
        
        # Don't auto-update these
        no_auto_update = [
            'truenas', 'freenas',  # Self-managed
            'opnsense', 'pfsense',  # Critical router
            'windows',  # Different update mechanism
        ]
        
        return not any(x in os_name for x in no_auto_update)
````

#### 3. Config Template Engine (`lib/discovery/template.py`)
````python
class ConfigTemplate:
    """Generates YAML configuration from discovered data."""
    
    def generate(self, nodes, services, storage) -> Dict[str, Any]:
        """Generate complete config structure."""
        return {
            'global': self._generate_global(nodes, storage),
            'services': self._generate_services(services)
        }
    
    def _generate_global(self, nodes, storage) -> Dict[str, Any]:
        """Generate global configuration section."""
        return {
            'hypervisor': {
                'type': 'proxmox',
                'host': nodes[0].hostname,
                'username': 'root@pam',
                # Leave password blank for manual entry
                'verify_ssl': False
            },
            'backup': {
                'enabled': True,
                'root': self._suggest_backup_root(storage),
                'retention_days': 30,
                'compression': True
            },
            # ... other sections
        }
    
    def _generate_services(self, analyzed_services) -> List[Dict]:
        """Generate services section with metadata comments."""
        services = []
        
        for analyzed in analyzed_services:
            service_dict = {
                'name': analyzed.service.name,
                'type': analyzed.service.type,
                'vmid': analyzed.service.vmid,
                'node': analyzed.service.node,
                'enabled': True,
                'backup': analyzed.suggestions['backup'],
                'update': analyzed.suggestions['update'],
                'monitor': analyzed.suggestions['monitor'],
            }
            
            # Add metadata as comment (handled by YAML generator)
            service_dict['_metadata'] = analyzed.metadata
            
            services.append(service_dict)
        
        return services
````

#### 4. YAML Generator with Comments (`lib/discovery/yaml_gen.py`)
````python
class CommentedYAMLGenerator:
    """Generate YAML with inline comments."""
    
    def generate(self, config: Dict[str, Any]) -> str:
        """Generate YAML string with metadata comments."""
        lines = []
        
        # Header comment
        lines.append(f"# Auto-discovered on {datetime.now()}")
        lines.append("# Review and edit before use\n")
        
        # Global section
        lines.extend(self._format_global(config['global']))
        
        # Services section with comments
        lines.append("\nservices:")
        for service in config['services']:
            # Add metadata comment
            if '_metadata' in service:
                lines.append(f"  # {service['_metadata']}")
            
            # Add service config
            lines.extend(self._format_service(service))
        
        return '\n'.join(lines)
````

### Smart Defaults Logic

The discovery tool should apply intelligent defaults based on detected characteristics:

| Detected OS/Service | Auto-Update | Backup | Notes |
|---------------------|-------------|--------|-------|
| Ubuntu/Debian LXC   | ✅ True     | ✅ True | Standard case |
| TrueNAS VM          | ❌ False    | ✅ True | Self-managed updates |
| pfSense/OPNsense    | ❌ False    | ✅ True | Critical, manual updates |
| Windows VM          | ❌ False    | ✅ True | Different mechanism |
| Proxmox Backup      | ✅ True     | ✅ True | Special handling |
| Home Assistant      | ⚠️ Suggest   | ✅ True | Prompt user |

### Edge Cases to Handle

1. **Multi-node clusters**: Discover all nodes, let user choose which to manage
2. **Templates**: Exclude VM/LXC templates from services list
3. **Stopped containers**: Include but add comment about status
4. **Unknown OS**: Default to safe settings (backup yes, update no)
5. **Large environments**: Pagination, progress indicators
6. **No backup storage**: Prompt user for location
7. **API permissions**: Graceful degradation with partial discovery

## CLI Implementation

### Command Structure
````python
# cli/commands/discover.py

@click.command()
@click.option('--host', prompt=True, help='Proxmox hostname')
@click.option('--user', default='root@pam', help='Proxmox username')
@click.option('--password', prompt=True, hide_input=True, help='Password')
@click.option('--output', '-o', default='homelab-autopilot.yaml', help='Output file')
@click.option('--dry-run', is_flag=True, help='Preview without saving')
@click.option('--include-templates', is_flag=True, help='Include VM templates')
@click.option('--node', multiple=True, help='Specific nodes to scan')
def discover(host, user, password, output, dry_run, include_templates, node):
    """Discover and generate configuration from Proxmox."""
    
    # Initialize discovery
    client = ProxmoxClient(host, user, password)
    engine = DiscoveryEngine(client)
    
    # Run discovery
    with click.progressbar(label='Scanning infrastructure') as bar:
        config = engine.discover(
            nodes=node if node else None,
            include_templates=include_templates
        )
    
    # Generate YAML
    generator = CommentedYAMLGenerator()
    yaml_content = generator.generate(config)
    
    # Output
    if dry_run:
        click.echo("\n" + yaml_content)
    else:
        with open(output, 'w') as f:
            f.write(yaml_content)
        click.secho(f"✓ Configuration saved to: {output}", fg='green')
        
        # Show next steps
        click.echo("\nNext steps:")
        click.echo("1. Review the generated configuration")
        click.echo("2. Add password/API token")
        click.echo("3. Configure notifications")
        click.echo(f"4. Validate: homelab-autopilot validate {output}")
````

## Dependencies

- **proxmoxer**: Python Proxmox API client
- **ruamel.yaml**: YAML with comment preservation
- **rich**: Beautiful terminal output

## Testing Strategy

### Unit Tests
- Test service analyzer logic
- Test smart defaults for different OS types
- Test YAML generation with comments
- Test error handling for API failures

### Integration Tests
- Mock Proxmox API responses
- Test full discovery flow
- Test multi-node scenarios
- Test edge cases (empty cluster, no permissions, etc.)

### Manual Testing Checklist
- [ ] Single node, simple setup
- [ ] Multi-node cluster
- [ ] Mix of VMs and LXCs
- [ ] Environment with templates
- [ ] Various OS types (Ubuntu, Debian, TrueNAS, etc.)
- [ ] Large environment (50+ VMs/LXCs)
- [ ] Partial API permissions
- [ ] Network interruptions during discovery

## Future Enhancements

### Phase 1 (Initial Release)
- Basic Proxmox discovery
- Smart defaults for common scenarios
- Commented YAML output

### Phase 2 (Enhanced)
- Interactive mode with prompts
- Service grouping suggestions
- Backup schedule recommendations
- Detect existing backup solutions

### Phase 3 (Advanced)
- Multiple hypervisor support (ESXi, KVM)
- Incremental updates (re-scan and merge)
- Backup validation before config generation
- Web UI for discovery and editing

## User Documentation

### Quick Start Guide
````markdown
## Discovering Your Infrastructure

The easiest way to get started is to let Homelab Autopilot discover your
Proxmox infrastructure automatically:

1. Run the discovery tool:
```bash
   homelab-autopilot discover
```

2. Enter your Proxmox credentials when prompted

3. Review the generated `homelab-autopilot.yaml` file

4. Edit as needed:
   - Add your password or API token
   - Configure notification settings
   - Adjust which services to manage

5. Validate your configuration:
```bash
   homelab-autopilot validate
```

6. You're ready to go!
````

## Implementation Checklist

### Core Discovery (Phase 5 or 6)
- [ ] Create `lib/discovery/` module
- [ ] Implement `DiscoveryEngine`
- [ ] Implement `ServiceAnalyzer` with smart defaults
- [ ] Implement `ConfigTemplate`
- [ ] Implement `CommentedYAMLGenerator`
- [ ] Add Proxmox API client wrapper
- [ ] Create CLI command
- [ ] Write unit tests
- [ ] Write integration tests
- [ ] User documentation
- [ ] Example configurations

### Nice-to-Have Features
- [ ] Interactive mode with questions
- [ ] Detect Docker containers inside VMs/LXCs
- [ ] Detect systemd services
- [ ] Backup existing config before overwriting
- [ ] Config diff tool (compare discovered vs current)
- [ ] Scheduled re-discovery to detect changes

## Success Metrics

- **Setup time**: Reduce from 30+ minutes (manual) to <5 minutes
- **Error rate**: Reduce config errors by 80%
- **Adoption**: 60%+ of users use discovery vs manual config
- **User feedback**: Positive sentiment on ease of setup

## Related Documents

- [Architecture Overview](architecture.md)
- [Configuration Schema](config-reference.md) - Coming soon
- [Proxmox Plugin Development](plugin-development.md) - Coming soon

---

**Questions or suggestions?** Open an issue or discussion on GitHub!
