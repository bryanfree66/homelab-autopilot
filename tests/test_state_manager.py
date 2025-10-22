"""
Tests for StateManager.

Tests cover:
- Database creation and initialization
- Basic operations (get, set, delete, exists)
- Type serialization/deserialization
- Thread safety
- Edge cases and error handling
"""

import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from lib.state_manager import StateManager


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary database path."""
    return tmp_path / "test_state.db"


@pytest.fixture
def state_manager(temp_db):
    """Create a StateManager instance."""
    return StateManager(temp_db)


# Test: Initialization
class TestInitialization:
    """Test state manager initialization."""

    def test_creates_database_file(self, temp_db):
        """Test that database file is created."""
        assert not temp_db.exists()

        StateManager(temp_db)

        assert temp_db.exists()

    def test_creates_parent_directory(self, tmp_path):
        """Test that parent directories are created."""
        db_path = tmp_path / "subdir" / "another" / "state.db"

        StateManager(db_path)

        assert db_path.exists()
        assert db_path.parent.exists()

    def test_multiple_instances_same_db(self, temp_db):
        """Test that multiple instances can use same database."""
        state1 = StateManager(temp_db)
        state1.set("key1", "value1")

        state2 = StateManager(temp_db)
        assert state2.get("key1") == "value1"


# Test: Basic Operations
class TestBasicOperations:
    """Test basic get, set, delete, exists operations."""

    def test_set_and_get_string(self, state_manager):
        """Test setting and getting string value."""
        state_manager.set("test.key", "test_value")
        assert state_manager.get("test.key") == "test_value"

    def test_set_and_get_integer(self, state_manager):
        """Test setting and getting integer value."""
        state_manager.set("test.count", 42)
        assert state_manager.get("test.count") == 42

    def test_set_and_get_float(self, state_manager):
        """Test setting and getting float value."""
        state_manager.set("test.ratio", 3.14159)
        assert state_manager.get("test.ratio") == pytest.approx(3.14159)

    def test_set_and_get_boolean(self, state_manager):
        """Test setting and getting boolean value."""
        state_manager.set("test.enabled", True)
        assert state_manager.get("test.enabled") is True

        state_manager.set("test.disabled", False)
        assert state_manager.get("test.disabled") is False

    def test_set_and_get_none(self, state_manager):
        """Test setting and getting None value."""
        state_manager.set("test.none", None)
        assert state_manager.get("test.none") is None

    def test_set_and_get_datetime(self, state_manager):
        """Test setting and getting datetime value."""
        now = datetime.now()
        state_manager.set("test.timestamp", now)

        retrieved = state_manager.get("test.timestamp")
        assert isinstance(retrieved, datetime)
        # Compare with microsecond precision
        assert abs((retrieved - now).total_seconds()) < 0.001

    def test_set_and_get_dict(self, state_manager):
        """Test setting and getting dictionary value."""
        data = {"name": "plex", "vmid": 100, "enabled": True}
        state_manager.set("test.config", data)

        assert state_manager.get("test.config") == data

    def test_set_and_get_list(self, state_manager):
        """Test setting and getting list value."""
        data = ["item1", "item2", "item3"]
        state_manager.set("test.list", data)

        assert state_manager.get("test.list") == data

    def test_get_nonexistent_key_returns_none(self, state_manager):
        """Test that getting nonexistent key returns None."""
        assert state_manager.get("nonexistent.key") is None

    def test_get_with_default(self, state_manager):
        """Test getting with default value."""
        assert state_manager.get("nonexistent.key", "default") == "default"

    def test_update_existing_key(self, state_manager):
        """Test updating an existing key."""
        state_manager.set("test.key", "value1")
        assert state_manager.get("test.key") == "value1"

        state_manager.set("test.key", "value2")
        assert state_manager.get("test.key") == "value2"

    def test_delete_existing_key(self, state_manager):
        """Test deleting an existing key."""
        state_manager.set("test.key", "value")
        assert state_manager.exists("test.key")

        state_manager.delete("test.key")
        assert not state_manager.exists("test.key")

    def test_delete_nonexistent_key(self, state_manager):
        """Test that deleting nonexistent key doesn't error."""
        # Should not raise
        state_manager.delete("nonexistent.key")

    def test_exists_returns_true_for_existing_key(self, state_manager):
        """Test exists returns True for existing key."""
        state_manager.set("test.key", "value")
        assert state_manager.exists("test.key") is True

    def test_exists_returns_false_for_nonexistent_key(self, state_manager):
        """Test exists returns False for nonexistent key."""
        assert state_manager.exists("nonexistent.key") is False


# Test: Get All and Clear
class TestBulkOperations:
    """Test bulk operations like get_all and clear."""

    def test_get_all_empty_state(self, state_manager):
        """Test get_all on empty state."""
        assert state_manager.get_all() == {}

    def test_get_all_with_data(self, state_manager):
        """Test get_all with multiple keys."""
        state_manager.set("key1", "value1")
        state_manager.set("key2", 42)
        state_manager.set("key3", True)

        all_state = state_manager.get_all()

        assert len(all_state) == 3
        assert all_state["key1"] == "value1"
        assert all_state["key2"] == 42
        assert all_state["key3"] is True

    def test_clear_removes_all_keys(self, state_manager):
        """Test clear removes all state."""
        state_manager.set("key1", "value1")
        state_manager.set("key2", "value2")
        assert len(state_manager.get_all()) == 2

        state_manager.clear()

        assert len(state_manager.get_all()) == 0
        assert not state_manager.exists("key1")
        assert not state_manager.exists("key2")


# Test: Get Keys with Prefix
class TestGetKeys:
    """Test get_keys functionality."""

    def test_get_keys_all(self, state_manager):
        """Test getting all keys without prefix."""
        state_manager.set("backup.plex", "value1")
        state_manager.set("backup.nginx", "value2")
        state_manager.set("update.plex", "value3")

        keys = state_manager.get_keys()

        assert len(keys) == 3
        assert "backup.plex" in keys
        assert "backup.nginx" in keys
        assert "update.plex" in keys

    def test_get_keys_with_prefix(self, state_manager):
        """Test getting keys filtered by prefix."""
        state_manager.set("backup.plex", "value1")
        state_manager.set("backup.nginx", "value2")
        state_manager.set("update.plex", "value3")

        backup_keys = state_manager.get_keys("backup.")

        assert len(backup_keys) == 2
        assert "backup.plex" in backup_keys
        assert "backup.nginx" in backup_keys
        assert "update.plex" not in backup_keys

    def test_get_keys_no_matches(self, state_manager):
        """Test get_keys with no matching prefix."""
        state_manager.set("key1", "value1")

        keys = state_manager.get_keys("nonexistent.")

        assert keys == []


# Test: Thread Safety
class TestThreadSafety:
    """Test thread-safe concurrent access."""

    def test_concurrent_writes(self, state_manager):
        """Test multiple threads writing simultaneously."""

        def write_values(thread_id):
            for i in range(100):
                state_manager.set(f"thread.{thread_id}.{i}", f"value_{i}")

        threads = []
        for i in range(5):
            t = threading.Thread(target=write_values, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Verify all values written
        all_keys = state_manager.get_keys("thread.")
        assert len(all_keys) == 500  # 5 threads * 100 values each

    def test_concurrent_read_write(self, state_manager):
        """Test concurrent reads and writes."""
        state_manager.set("counter", 0)

        def increment():
            for _ in range(100):
                current = state_manager.get("counter", 0)
                state_manager.set("counter", current + 1)

        threads = []
        for _ in range(5):
            t = threading.Thread(target=increment)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Note: Without proper locking in increment(), final value might not be 500
        # But the state manager itself should not corrupt data
        final_value = state_manager.get("counter")
        assert isinstance(final_value, int)
        assert final_value > 0


# Test: Edge Cases
class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_key(self, state_manager):
        """Test operations with empty string key."""
        state_manager.set("", "value")
        assert state_manager.get("") == "value"

    def test_very_long_key(self, state_manager):
        """Test with very long key name."""
        long_key = "a" * 1000
        state_manager.set(long_key, "value")
        assert state_manager.get(long_key) == "value"

    def test_very_long_value(self, state_manager):
        """Test with very long value."""
        long_value = "x" * 10000
        state_manager.set("test.long", long_value)
        assert state_manager.get("test.long") == long_value

    def test_special_characters_in_key(self, state_manager):
        """Test keys with special characters."""
        special_key = "test.key-with_special/characters@123"
        state_manager.set(special_key, "value")
        assert state_manager.get(special_key) == "value"

    def test_unicode_in_value(self, state_manager):
        """Test unicode characters in values."""
        unicode_value = "Hello 世界 🎉"
        state_manager.set("test.unicode", unicode_value)
        assert state_manager.get("test.unicode") == unicode_value

    def test_complex_nested_dict(self, state_manager):
        """Test deeply nested dictionary."""
        complex_data = {
            "level1": {"level2": {"level3": {"values": [1, 2, 3], "enabled": True}}}
        }
        state_manager.set("test.nested", complex_data)
        assert state_manager.get("test.nested") == complex_data

    def test_unsupported_type_raises_error(self, state_manager):
        """Test that unsupported types raise TypeError."""

        class CustomClass:
            pass

        with pytest.raises(TypeError) as exc_info:
            state_manager.set("test.custom", CustomClass())

        assert "Unsupported type" in str(exc_info.value)


# Test: Persistence
class TestPersistence:
    """Test that state persists across instances."""

    def test_state_persists_across_instances(self, temp_db):
        """Test that state persists when creating new instance."""
        # First instance
        state1 = StateManager(temp_db)
        state1.set("persistent.key", "persistent_value")
        state1.set("persistent.number", 42)

        # Create new instance with same database
        state2 = StateManager(temp_db)

        assert state2.get("persistent.key") == "persistent_value"
        assert state2.get("persistent.number") == 42

    def test_updates_visible_across_instances(self, temp_db):
        """Test that updates are visible to other instances."""
        state1 = StateManager(temp_db)
        state2 = StateManager(temp_db)

        state1.set("shared.key", "value1")
        assert state2.get("shared.key") == "value1"

        state2.set("shared.key", "value2")
        assert state1.get("shared.key") == "value2"
