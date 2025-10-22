"""
State Manager for Homelab Autopilot using SQLite.

This module provides a simple key-value store for persisting application state
such as last backup times, update times, and notification cooldowns.
"""

import sqlite3
import json
import threading
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime


class StateManager:
    """
    Thread-safe state manager using SQLite for persistence.
    
    Provides a simple key-value store interface for tracking application state
    across runs. Supports multiple data types including strings, numbers,
    booleans, datetime objects, and complex types via JSON serialization.
    
    Example:
        >>> from pathlib import Path
        >>> state = StateManager(Path("/var/lib/homelab-autopilot/state.db"))
        >>> state.set("backup.last_run.plex", datetime.now())
        >>> last_run = state.get("backup.last_run.plex")
        >>> if state.exists("update.last_check.nginx"):
        ...     print("Already checked")
    """
    
    def __init__(self, db_path: Path):
        """
        Initialize state manager with database path.
        
        Creates the database and schema if they don't exist. The database
        will be created in the parent directory if it doesn't exist.
        
        Args:
            db_path: Path to SQLite database file
            
        Raises:
            OSError: If database directory cannot be created
            sqlite3.Error: If database initialization fails
        """
        self.db_path = db_path
        self._lock = threading.Lock()
        
        # Ensure database directory exists
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_database()
    
    def _init_database(self) -> None:
        """Create database schema if it doesn't exist."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS state (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        type TEXT NOT NULL,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
            finally:
                conn.close()
    
    def _serialize_value(self, value: Any) -> tuple[str, str]:
        """
        Serialize value to string and determine type.
        
        Args:
            value: Value to serialize
            
        Returns:
            Tuple of (serialized_value, type_name)
            
        Raises:
            TypeError: If value type is not supported
        """
        if value is None:
            return ("null", "none")
        elif isinstance(value, bool):
            # Must check bool before int (bool is subclass of int)
            return (str(value), "bool")
        elif isinstance(value, int):
            return (str(value), "int")
        elif isinstance(value, float):
            return (str(value), "float")
        elif isinstance(value, str):
            return (value, "str")
        elif isinstance(value, datetime):
            return (value.isoformat(), "datetime")
        elif isinstance(value, (dict, list)):
            return (json.dumps(value), "json")
        else:
            raise TypeError(f"Unsupported type for state value: {type(value)}")
    
    def _deserialize_value(self, value_str: str, type_name: str) -> Any:
        """
        Deserialize value from string based on type.
        
        Args:
            value_str: Serialized value string
            type_name: Type identifier
            
        Returns:
            Deserialized value
            
        Raises:
            ValueError: If deserialization fails
        """
        if type_name == "none":
            return None
        elif type_name == "bool":
            return value_str == "True"
        elif type_name == "int":
            return int(value_str)
        elif type_name == "float":
            return float(value_str)
        elif type_name == "str":
            return value_str
        elif type_name == "datetime":
            return datetime.fromisoformat(value_str)
        elif type_name == "json":
            return json.loads(value_str)
        else:
            raise ValueError(f"Unknown type in database: {type_name}")
    
    def get(self, key: str, default: Optional[Any] = None) -> Optional[Any]:
        """
        Get value for key.
        
        Args:
            key: Key to retrieve
            default: Default value if key doesn't exist
            
        Returns:
            Value for key, or default if not found
            
        Example:
            >>> state.get("backup.last_run.plex")
            datetime.datetime(2025, 10, 22, 10, 30, 0)
            >>> state.get("nonexistent.key", "default_value")
            'default_value'
        """
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.execute(
                    "SELECT value, type FROM state WHERE key = ?",
                    (key,)
                )
                row = cursor.fetchone()
                
                if row is None:
                    return default
                
                value_str, type_name = row
                return self._deserialize_value(value_str, type_name)
            finally:
                conn.close()
    
    def set(self, key: str, value: Any) -> None:
        """
        Set value for key.
        
        If the key already exists, it will be updated. The updated_at
        timestamp is automatically set to the current time.
        
        Args:
            key: Key to set
            value: Value to store (must be serializable)
            
        Raises:
            TypeError: If value type is not supported
            
        Example:
            >>> state.set("backup.last_run.plex", datetime.now())
            >>> state.set("update.count", 42)
            >>> state.set("config.settings", {"enabled": True, "retries": 3})
        """
        value_str, type_name = self._serialize_value(value)
        
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO state (key, value, type, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (key, value_str, type_name)
                )
                conn.commit()
            finally:
                conn.close()
    
    def delete(self, key: str) -> None:
        """
        Delete key from state.
        
        Does not raise an error if key doesn't exist.
        
        Args:
            key: Key to delete
            
        Example:
            >>> state.delete("backup.last_run.plex")
        """
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                conn.execute("DELETE FROM state WHERE key = ?", (key,))
                conn.commit()
            finally:
                conn.close()
    
    def exists(self, key: str) -> bool:
        """
        Check if key exists in state.
        
        Args:
            key: Key to check
            
        Returns:
            True if key exists, False otherwise
            
        Example:
            >>> if state.exists("backup.last_run.plex"):
            ...     print("Backup has run before")
        """
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.execute(
                    "SELECT 1 FROM state WHERE key = ? LIMIT 1",
                    (key,)
                )
                return cursor.fetchone() is not None
            finally:
                conn.close()
    
    def get_all(self) -> Dict[str, Any]:
        """
        Get all key-value pairs from state.
        
        Returns:
            Dictionary of all keys and their values
            
        Example:
            >>> all_state = state.get_all()
            >>> for key, value in all_state.items():
            ...     print(f"{key}: {value}")
        """
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.execute("SELECT key, value, type FROM state")
                result = {}
                for key, value_str, type_name in cursor.fetchall():
                    result[key] = self._deserialize_value(value_str, type_name)
                return result
            finally:
                conn.close()
    
    def clear(self) -> None:
        """
        Clear all state (delete all keys).
        
        Useful for testing or resetting application state.
        
        Example:
            >>> state.clear()  # Remove all state
        """
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                conn.execute("DELETE FROM state")
                conn.commit()
            finally:
                conn.close()
    
    def get_keys(self, prefix: Optional[str] = None) -> list[str]:
        """
        Get all keys, optionally filtered by prefix.
        
        Args:
            prefix: Optional prefix to filter keys (e.g., "backup.")
            
        Returns:
            List of keys matching the prefix
            
        Example:
            >>> backup_keys = state.get_keys("backup.")
            >>> # Returns: ['backup.last_run.plex', 'backup.last_run.nginx', ...]
        """
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                if prefix:
                    cursor = conn.execute(
                        "SELECT key FROM state WHERE key LIKE ?",
                        (f"{prefix}%",)
                    )
                else:
                    cursor = conn.execute("SELECT key FROM state")
                
                return [row[0] for row in cursor.fetchall()]
            finally:
                conn.close()