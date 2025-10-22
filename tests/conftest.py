"""
Shared pytest fixtures and configuration for Homelab Autopilot tests.

This module provides common fixtures used across multiple test files.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import pytest

# Mock ServiceConfig for tests that don't need full config_loader


@pytest.fixture
def mock_service_vm():
    """Mock Proxmox VM service configuration."""

    class MockServiceConfig:
        name = "test-vm"
        type = "vm"
        vmid = 100
        node = "pve1"
        enabled = True
        backup = True
        update = True
        monitor = True

    return MockServiceConfig()


@pytest.fixture
def mock_service_lxc():
    """Mock Proxmox LXC service configuration."""

    class MockServiceConfig:
        name = "test-lxc"
        type = "lxc"
        vmid = 101
        node = "pve1"
        enabled = True
        backup = True
        update = True
        monitor = True

    return MockServiceConfig()


@pytest.fixture
def mock_service_docker():
    """Mock Docker service configuration."""

    class MockServiceConfig:
        name = "test-docker"
        type = "docker"
        container_name = "test-container"
        enabled = True
        backup = True
        update = True
        monitor = True

    return MockServiceConfig()


# Sample configuration data


@pytest.fixture
def sample_hypervisor_config():
    """Sample hypervisor configuration dictionary."""
    return {
        "type": "proxmox",
        "host": "pve.local",
        "username": "root@pam",
        "password": "test-password",
        "verify_ssl": True,
    }


@pytest.fixture
def sample_notification_config():
    """Sample notification configuration dictionary."""
    return {
        "enabled": True,
        "type": "email",
        "settings": {
            "to": "admin@example.com",
            "smtp_server": "smtp.example.com",
            "smtp_port": 587,
        },
    }


# Temporary directories with specific purposes


@pytest.fixture
def temp_backup_dir(tmp_path):
    """Temporary directory for backup tests."""
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    return backup_dir


@pytest.fixture
def temp_state_db(tmp_path):
    """Temporary database path for state manager tests."""
    return tmp_path / "test_state.db"


@pytest.fixture
def temp_log_dir(tmp_path):
    """Temporary directory for log files."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    return log_dir


# Time-related fixtures


@pytest.fixture
def fixed_timestamp():
    """Fixed timestamp for reproducible tests."""
    return datetime(2024, 1, 15, 10, 30, 45)


@pytest.fixture
def iso_timestamp(fixed_timestamp):
    """Fixed timestamp in ISO format."""
    return fixed_timestamp.isoformat()


# Plugin configuration fixtures


@pytest.fixture
def plugin_config():
    """Generic plugin configuration."""
    return {"enabled": True, "timeout": 300, "retries": 3}


# Test data helpers


@pytest.fixture
def sample_vmids():
    """Sample valid Proxmox VMIDs for testing."""
    return [100, 101, 102, 200, 500, 999999]


@pytest.fixture
def sample_hostnames():
    """Sample valid hostnames for testing."""
    return [
        "server01",
        "pve.local",
        "my-server.example.com",
        "test_host",
        "192.168.1.10",
    ]


# Pytest configuration


def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "unit: marks tests as unit tests")
