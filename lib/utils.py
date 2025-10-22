"""
Utility functions for Homelab Autopilot.

This module provides common helper functions used throughout the project
for path operations, date/time handling, formatting, and validation.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

# Path Operations


def validate_path(
    path: Union[str, Path], must_exist: bool = False, must_be_absolute: bool = False
) -> Path:
    """
    Validate and sanitize a filesystem path.

    Args:
        path: Path to validate (string or Path object)
        must_exist: If True, raise error if path doesn't exist
        must_be_absolute: If True, raise error if path is not absolute

    Returns:
        Validated Path object

    Raises:
        ValueError: If path is invalid or doesn't meet requirements
        FileNotFoundError: If must_exist=True and path doesn't exist
    """
    if not path:
        raise ValueError("Path cannot be empty")

    path_obj = Path(path)

    if must_be_absolute and not path_obj.is_absolute():
        raise ValueError(f"Path must be absolute: {path}")

    if must_exist and not path_obj.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")

    return path_obj


def ensure_directory(path: Union[str, Path], mode: int = 0o755) -> Path:
    """
    Create directory if it doesn't exist.

    Args:
        path: Directory path to create
        mode: Directory permissions (default: 0o755)

    Returns:
        Path object of the directory

    Raises:
        ValueError: If path is empty
        OSError: If directory creation fails
    """
    path_obj = validate_path(path)
    path_obj.mkdir(parents=True, exist_ok=True, mode=mode)
    return path_obj


def safe_remove(path: Union[str, Path], missing_ok: bool = True) -> bool:
    """
    Safely remove a file or directory.

    Args:
        path: Path to remove
        missing_ok: If True, don't raise error if path doesn't exist

    Returns:
        True if path was removed, False if it didn't exist

    Raises:
        FileNotFoundError: If missing_ok=False and path doesn't exist
        OSError: If removal fails for other reasons
    """
    path_obj = Path(path)

    if not path_obj.exists():
        if missing_ok:
            return False
        raise FileNotFoundError(f"Path does not exist: {path}")

    if path_obj.is_file():
        path_obj.unlink()
    elif path_obj.is_dir():
        import shutil

        shutil.rmtree(path_obj)

    return True


# Date/Time Utilities


def get_timestamp() -> str:
    """
    Get current timestamp in ISO 8601 format.

    Returns:
        ISO format timestamp string (e.g., "2024-01-15T10:30:45")
    """
    return datetime.now().isoformat()


def parse_timestamp(timestamp_str: str) -> datetime:
    """
    Parse ISO 8601 timestamp string to datetime object.

    Args:
        timestamp_str: ISO format timestamp string

    Returns:
        datetime object

    Raises:
        ValueError: If timestamp string is invalid
    """
    try:
        return datetime.fromisoformat(timestamp_str)
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid timestamp format: {timestamp_str}") from e


def human_readable_duration(seconds: Union[int, float]) -> str:
    """
    Convert seconds to human-readable duration.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted duration string (e.g., "2h 30m 15s", "45s", "1d 3h")

    Example:
        >>> human_readable_duration(3665)
        '1h 1m 5s'
        >>> human_readable_duration(45)
        '45s'
    """
    if seconds < 0:
        raise ValueError("Duration cannot be negative")

    seconds = int(seconds)

    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")

    return " ".join(parts)


# Format Helpers


def format_bytes(bytes_value: Union[int, float], precision: int = 2) -> str:
    """
    Convert bytes to human-readable size.

    Args:
        bytes_value: Size in bytes
        precision: Number of decimal places (default: 2)

    Returns:
        Formatted size string (e.g., "1.50 GB", "512.00 MB")

    Example:
        >>> format_bytes(1536)
        '1.50 KB'
        >>> format_bytes(1073741824)
        '1.00 GB'
    """
    if bytes_value < 0:
        raise ValueError("Bytes value cannot be negative")

    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    size = float(bytes_value)
    unit_index = 0

    while size >= 1024.0 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1

    return f"{size:.{precision}f} {units[unit_index]}"


def sanitize_filename(name: str, replacement: str = "_") -> str:
    """
    Remove invalid characters from filename.

    Args:
        name: Original filename
        replacement: Character to replace invalid characters with (default: "_")

    Returns:
        Sanitized filename safe for use on most filesystems

    Example:
        >>> sanitize_filename("my:file/name?.txt")
        'my_file_name_.txt'
    """
    if not name:
        raise ValueError("Filename cannot be empty")

    # Remove invalid characters for Windows/Linux filesystems
    invalid_chars = r'[<>:"/\\|?*\x00-\x1f]'
    sanitized = re.sub(invalid_chars, replacement, name)

    # Remove leading/trailing spaces and dots
    sanitized = sanitized.strip(". ")

    # Ensure not empty after sanitization
    if not sanitized:
        sanitized = "unnamed"

    return sanitized


# Validators


def is_valid_vmid(vmid: int) -> bool:
    """
    Check if Proxmox VMID is in valid range.

    Args:
        vmid: Proxmox VM/LXC ID

    Returns:
        True if VMID is valid (100-999999), False otherwise

    Example:
        >>> is_valid_vmid(100)
        True
        >>> is_valid_vmid(50)
        False
    """
    return isinstance(vmid, int) and 100 <= vmid <= 999999


def is_valid_hostname(hostname: str) -> bool:
    """
    Basic hostname validation.

    Args:
        hostname: Hostname or FQDN to validate

    Returns:
        True if hostname appears valid, False otherwise

    Example:
        >>> is_valid_hostname("server01")
        True
        >>> is_valid_hostname("server_01.local")
        True
        >>> is_valid_hostname("invalid..hostname")
        False
    """
    if not hostname or len(hostname) > 253:
        return False

    # Allow alphanumeric, hyphens, dots, underscores
    # Each label between dots should be valid
    pattern = r"^[a-zA-Z0-9]([a-zA-Z0-9\-_]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-_]{0,61}[a-zA-Z0-9])?)*$"
    return bool(re.match(pattern, hostname))
