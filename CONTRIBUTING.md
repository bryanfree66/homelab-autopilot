# Contributing to Homelab Autopilot

# Contributing to Homelab Autopilot

Thank you for your interest in contributing to Homelab Autopilot! This project thrives on community contributions, whether you're fixing bugs, adding features, improving documentation, or sharing your homelab setup.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How Can I Contribute?](#how-can-i-contribute)
- [Development Setup](#development-setup)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)
- [Plugin Development](#plugin-development)
- [Testing](#testing)
- [Documentation](#documentation)

## Code of Conduct

This project follows a simple code of conduct: **Be excellent to each other.** 

- Be respectful and constructive
- Welcome newcomers and help them learn
- Focus on what's best for the community
- Show empathy towards other community members

## How Can I Contribute?

### 🐛 Reporting Bugs

Before creating a bug report, please check existing issues to avoid duplicates.

**When reporting a bug, include:**
- Your homelab setup (hypervisor, OS, services)
- Steps to reproduce the issue
- Expected behavior vs. actual behavior
- Relevant logs (redact any sensitive information!)
- Configuration file (redacted)

**Use this template:**
```markdown
**Environment:**
- Homelab Autopilot version: v0.1.0
- Hypervisor: Proxmox VE 8.1
- OS: Debian 12
- Python version: 3.11

**Description:**
Brief description of the issue

**Steps to Reproduce:**
1. Step one
2. Step two
3. See error

**Expected Behavior:**
What should happen

**Actual Behavior:**
What actually happens

**Logs:**
```
Relevant log excerpts (redacted)
```

**Configuration:**
```yaml
Relevant config (redacted)
```
```

### 💡 Suggesting Features

Feature suggestions are welcome! Please:

1. Check if the feature is already requested
2. Clearly describe the use case
3. Explain why this would be useful to the community
4. Consider implementation complexity

### 📝 Improving Documentation

Documentation improvements are always appreciated:

- Fix typos or clarify confusing sections
- Add examples or use cases
- Improve installation guides
- Write tutorials or blog posts

### 🔌 Writing Plugins

Plugins are the heart of Homelab Autopilot's extensibility:

- **Hypervisor plugins**: Add support for new platforms (ESXi, Unraid, etc.)
- **Service plugins**: Add specialized handling for specific services
- **Notification plugins**: Add new notification channels

See [Plugin Development](#plugin-development) below for details.

### 🧪 Testing & Feedback

Even if you don't write code, you can help by:

- Testing alpha/beta releases
- Reporting what works (and what doesn't)
- Sharing your homelab configuration
- Suggesting improvements based on real usage

## Development Setup

### Prerequisites

- Linux development environment (or VM)
- **Python 3.8+** (primary language)
- **Bash 4.0+** (for system orchestration)
- Git
- A homelab for testing (or test VMs)

### Getting Started

1. **Fork the repository** on GitHub

2. **Clone your fork:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/homelab-autopilot.git
   cd homelab-autopilot
   ```

3. **Set up Python environment:**
   ```bash
   # Create virtual environment
   python3 -m venv venv
   source venv/bin/activate
   
   # Install dependencies
   pip install -r requirements.txt
   pip install -r requirements-dev.txt  # For development/testing
   ```

4. **Create a feature branch:**
   ```bash
   git checkout -b feature/your-feature-name
   ```

5. **Make your changes**

6. **Test thoroughly** (see [Testing](#testing))

7. **Commit with clear messages:**
   ```bash
   git commit -m "Add support for ESXi hypervisor"
   ```

8. **Push to your fork:**
   ```bash
   git push origin feature/your-feature-name
   ```

9. **Create a Pull Request** on GitHub

### Development Workflow

We use a Git-based workflow:

- **main branch**: Always stable, production-ready
- **feature branches**: New features or fixes
- **Pull requests**: All changes via PR with review

## Pull Request Process

1. **Update documentation** if you're adding features
2. **Add tests** if applicable
3. **Follow coding standards** (see below)
4. **Write clear commit messages**
5. **Reference issues** if fixing bugs (`Fixes #123`)
6. **Be responsive** to feedback during review

### PR Checklist

Before submitting:

- [ ] Code follows project conventions (Python PEP 8, bash best practices)
- [ ] Type hints added for Python code
- [ ] Documentation updated
- [ ] Tests added/updated
- [ ] Tested on real homelab (or test environment)
- [ ] No sensitive data in commits
- [ ] Commit messages are clear
- [ ] Code passes linting (pylint, black, shellcheck)

## Coding Standards

### Language Usage Philosophy

**Use Python where possible, bash where necessary:**

- ✅ **Python for**: Config parsing, data processing, business logic, plugins, API interactions
- ✅ **Bash for**: System orchestration, calling system commands, simple wrappers, installation scripts

### Python Style Guide

We follow **PEP 8** with these specific conventions:

**File Structure:**
```python
#!/usr/bin/env python3
"""
Brief description of module purpose

This module handles [specific functionality]

Author: Your Name
License: MIT
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional

# Constants
CONFIG_DIR = Path("/etc/homelab-autopilot")
DEFAULT_CONFIG = CONFIG_DIR / "homelab-autopilot.yaml"


class MyClass:
    """Class docstring"""
    
    def __init__(self, name: str):
        """Initialize with name"""
        self.name = name


def main() -> int:
    """Main entry point"""
    # Implementation
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**Naming Conventions:**
- **Functions/variables**: `lowercase_with_underscores`
- **Classes**: `PascalCase`
- **Constants**: `UPPERCASE_WITH_UNDERSCORES`
- **Private functions/methods**: `_leading_underscore`
- **Module-level "dunder"**: `__double_leading_trailing__`

**Type Hints (Required):**
```python
from typing import Dict, List, Optional, Union, Any

def backup_service(
    service_name: str,
    destination: Path,
    compress: bool = True
) -> bool:
    """Type hints for all parameters and return values"""
    pass

# Use Optional for nullable values
def get_config(key: str, default: Optional[str] = None) -> Optional[str]:
    pass

# Use Union for multiple types
def process_value(value: Union[str, int, float]) -> str:
    pass
```

**Error Handling:**
```python
# Use specific exceptions
try:
    config = load_config(path)
except FileNotFoundError:
    logger.error(f"Config not found: {path}")
    return 1
except yaml.YAMLError as e:
    logger.error(f"Invalid YAML: {e}")
    return 1
except Exception as e:
    logger.exception(f"Unexpected error: {e}")
    return 1

# Don't use bare except
# Bad:
try:
    something()
except:  # DON'T DO THIS
    pass

# Good:
try:
    something()
except Exception as e:
    logger.error(f"Error: {e}")
```

**Documentation (Required for all public functions):**
```python
def backup_service(
    service_name: str,
    destination: Path,
    compress: bool = True,
    verify: bool = True
) -> bool:
    """
    Backup a service configuration to the specified destination
    
    This function creates a backup of the service's configuration files
    and optionally compresses and verifies the backup.
    
    Args:
        service_name: Name of the service to backup (e.g., "nextcloud")
        destination: Path to backup destination directory
        compress: Whether to compress the backup (default: True)
        verify: Whether to verify backup integrity (default: True)
        
    Returns:
        True if backup succeeded, False otherwise
        
    Raises:
        ValueError: If service_name is empty or invalid
        IOError: If destination is not writable
        BackupError: If backup operation fails
        
    Example:
        >>> backup_service("nextcloud", Path("/mnt/backup"))
        True
    """
    # Implementation
```

**Imports:**
```python
# Standard library imports first
import os
import sys
from pathlib import Path

# Third-party imports second
import yaml
from loguru import logger

# Local imports third
from core.config_loader import ConfigLoader
from lib.utils import validate_path
```

**String Formatting:**
```python
# Prefer f-strings (Python 3.6+)
name = "nextcloud"
message = f"Backing up {name} service"

# Use format() for complex formatting
message = "Service: {}, Status: {}".format(name, status)

# Avoid old % formatting
message = "Service: %s" % name  # Don't use this
```

**Path Handling:**
```python
# Use pathlib.Path, not string concatenation
from pathlib import Path

config_dir = Path("/etc/homelab-autopilot")
config_file = config_dir / "homelab-autopilot.yaml"

# Check if path exists
if config_file.exists():
    pass

# Read/write with Path
content = config_file.read_text()
config_file.write_text(content)
```

**Logging:**
```python
# Use loguru or standard logging
from loguru import logger

logger.debug("Detailed diagnostic information")
logger.info("Normal informational message")
logger.warning("Warning - something might be wrong")
logger.error("Error - operation failed")
logger.exception("Error with traceback")

# Include context in logs
logger.info(f"Backing up service: {service_name}")
logger.error(f"Failed to backup {service_name}: {error}")
```

**Code Formatting:**
```python
# Use black for automatic formatting
black .

# Line length: 88 characters (black default)
# Use parentheses for line continuation
result = some_function(
    argument1,
    argument2,
    argument3,
)
```

### Bash Style Guide

**When to use Bash:**
- Installation scripts
- System-level orchestration
- Calling system commands (systemctl, cron, etc.)
- Simple wrapper scripts

**File Structure:**
```bash
#!/usr/bin/env bash
# Brief description of script purpose
# 
# Author: Your Name
# License: MIT

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# Constants
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PYTHON_BIN="${SCRIPT_DIR}/venv/bin/python3"

# Main function
main() {
    # Call Python for heavy lifting
    "${PYTHON_BIN}" -m homelab_autopilot.cli "$@"
}

# Call main if script is executed (not sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
```

**Naming Conventions:**
- Functions: `lowercase_with_underscores()`
- Constants: `UPPERCASE_WITH_UNDERSCORES`
- Local variables: `lowercase_with_underscores`

**Error Handling:**
```bash
# Always check command success
if ! some_command; then
    echo "Error: Command failed" >&2
    return 1
fi

# Use shellcheck to validate scripts
shellcheck script.sh
```

## Plugin Development

### Plugin Structure (Python)

**Plugins should be Python classes implementing a standard interface:**

```python
#!/usr/bin/env python3
"""
Plugin: My Custom Service
Type: service
Description: Handles my-custom-service backup and updates
"""

from pathlib import Path
from typing import Dict, List, Optional
from loguru import logger

from core.plugin_base import ServicePlugin


class MyServicePlugin(ServicePlugin):
    """Plugin for managing my-custom-service"""
    
    def __init__(self, config: Dict):
        """Initialize plugin with configuration"""
        super().__init__(config)
        self.service_name = "my-service"
    
    def matches(self, service_config: Dict) -> bool:
        """
        Check if this plugin handles the given service
        
        Args:
            service_config: Service configuration dictionary
            
        Returns:
            True if this plugin handles the service
        """
        return service_config.get("type") == "my-service"
    
    def backup(self, destination: Path) -> bool:
        """
        Backup service configuration
        
        Args:
            destination: Path to backup destination
            
        Returns:
            True if backup succeeded
            
        Raises:
            BackupError: If backup fails
        """
        logger.info(f"Backing up {self.service_name}")
        # Implementation
        return True
    
    def update(self) -> bool:
        """
        Update the service
        
        Returns:
            True if update succeeded
            
        Raises:
            UpdateError: If update fails
        """
        logger.info(f"Updating {self.service_name}")
        # Implementation
        return True
    
    def validate(self) -> bool:
        """
        Validate service is working after update
        
        Returns:
            True if service is healthy
        """
        logger.info(f"Validating {self.service_name}")
        # Implementation
        return True
    
    def rollback(self) -> bool:
        """
        Rollback service to previous state
        
        Returns:
            True if rollback succeeded
        """
        logger.info(f"Rolling back {self.service_name}")
        # Implementation
        return True
```

### Testing Plugins

```python
# Write unit tests for your plugin
import pytest
from plugins.services.my_service import MyServicePlugin

def test_plugin_matches():
    """Test plugin matching logic"""
    config = {"type": "my-service"}
    plugin = MyServicePlugin(config)
    assert plugin.matches(config) is True

def test_backup_success():
    """Test successful backup"""
    plugin = MyServicePlugin({})
    result = plugin.backup(Path("/tmp/backup"))
    assert result is True
```

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=homelab_autopilot --cov-report=html

# Run specific test file
pytest tests/test_config_loader.py

# Run specific test
pytest tests/test_config_loader.py::test_load_valid_config
```

### Writing Tests

```python
import pytest
from pathlib import Path
from homelab_autopilot.core.config_loader import ConfigLoader

def test_load_valid_config():
    """Test loading a valid configuration"""
    config_path = Path("tests/fixtures/valid_config.yaml")
    loader = ConfigLoader(config_path)
    assert loader.get("global.hypervisor") == "proxmox"

def test_invalid_config_raises_error():
    """Test that invalid config raises appropriate error"""
    with pytest.raises(ValueError):
        ConfigLoader(Path("tests/fixtures/invalid_config.yaml"))
```

### Manual Testing

1. **Use dry-run mode:**
   ```bash
   homelab-autopilot --dry-run backup --all
   ```

2. **Test on non-production services first**

3. **Test failure scenarios**

4. **Verify rollback works**

## Code Quality Tools

### Required Tools

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Python linting and formatting
black .                    # Auto-format code
pylint homelab_autopilot/  # Check code quality
mypy homelab_autopilot/    # Type checking

# Bash linting
shellcheck scripts/*.sh
```

### Pre-commit Hooks (Recommended)

```bash
# Install pre-commit
pip install pre-commit

# Install git hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

## Documentation

### Documentation Standards

- **Clear purpose**: What does this do?
- **Prerequisites**: What's needed?
- **Step-by-step instructions**: How to use it?
- **Code examples**: Show real usage
- **Troubleshooting**: Common issues and solutions

### Docstring Requirements

All public modules, classes, and functions must have docstrings following Google style:

```python
def example_function(param1: str, param2: int = 0) -> bool:
    """
    Brief one-line summary
    
    Longer description if needed. Explain what the function does,
    why it exists, and any important details.
    
    Args:
        param1: Description of param1
        param2: Description of param2 (default: 0)
        
    Returns:
        Description of return value
        
    Raises:
        ValueError: When param1 is invalid
        IOError: When file operations fail
        
    Example:
        >>> example_function("test", 42)
        True
    """
    pass
```

## Questions?

- **GitHub Discussions**: Ask questions, share setups
- **GitHub Issues**: Bug reports and feature requests
- **Pull Requests**: Code contributions

---

**Thank you for contributing to Homelab Autopilot!** 🚀

Together we're making homelab automation accessible to everyone.