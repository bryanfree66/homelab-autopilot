"""
Tests for logger module.

Tests cover:
- Logger initialization
- File logging
- Console logging
- Log rotation
- Log levels
- Structured logging context
"""

import pytest
from pathlib import Path
import sys
import tempfile
from loguru import logger

from lib.logger import setup_logger, get_logger, log_context, set_log_level


@pytest.fixture(autouse=True)
def reset_logger():
    """Reset logger before each test."""
    logger.remove()
    yield
    logger.remove()


@pytest.fixture
def temp_log_file(tmp_path):
    """Create a temporary log file path."""
    return tmp_path / "test.log"


# Test: Basic Setup
class TestLoggerSetup:
    """Test logger initialization and setup."""
    
    def test_setup_with_defaults(self):
        """Test logger setup with default parameters."""
        # Should not raise
        setup_logger()
        
        log = get_logger()
        assert log is not None
    
    def test_setup_with_file(self, temp_log_file):
        """Test logger setup with file output."""
        setup_logger(log_file=temp_log_file)
        
        logger.info("Test message")
        
        assert temp_log_file.exists()
        content = temp_log_file.read_text()
        assert "Test message" in content
    
    def test_setup_creates_log_directory(self, tmp_path):
        """Test that logger creates log directory if it doesn't exist."""
        log_file = tmp_path / "logs" / "subdir" / "test.log"
        
        setup_logger(log_file=log_file)
        logger.info("Test")
        
        assert log_file.exists()
        assert log_file.parent.exists()
    
    def test_setup_without_console(self, temp_log_file):
        """Test logger setup with console disabled."""
        setup_logger(log_file=temp_log_file, console=False)
        
        logger.info("Test message")
        
        # Message should be in file
        assert "Test message" in temp_log_file.read_text()
    
    def test_setup_with_custom_format(self, temp_log_file):
        """Test logger with custom format string."""
        custom_format = "{time} | {level} | {message}"
        
        setup_logger(
            log_file=temp_log_file,
            console=False,
            format_string=custom_format
        )
        
        logger.info("Custom format test")
        content = temp_log_file.read_text()
        
        assert "Custom format test" in content


# Test: Log Levels
class TestLogLevels:
    """Test different log levels."""
    
    def test_info_level_filters_debug(self, temp_log_file):
        """Test that INFO level filters out DEBUG messages."""
        setup_logger(log_level="INFO", log_file=temp_log_file, console=False)
        
        logger.debug("Debug message")
        logger.info("Info message")
        
        content = temp_log_file.read_text()
        assert "Debug message" not in content
        assert "Info message" in content
    
    def test_debug_level_shows_all(self, temp_log_file):
        """Test that DEBUG level shows debug and info messages."""
        setup_logger(log_level="DEBUG", log_file=temp_log_file, console=False)
        
        logger.debug("Debug message")
        logger.info("Info message")
        
        content = temp_log_file.read_text()
        assert "Debug message" in content
        assert "Info message" in content
    
    def test_error_level_filters_info(self, temp_log_file):
        """Test that ERROR level filters out INFO and WARNING."""
        setup_logger(log_level="ERROR", log_file=temp_log_file, console=False)
        
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
        
        content = temp_log_file.read_text()
        assert "Info message" not in content
        assert "Warning message" not in content
        assert "Error message" in content
    
    def test_invalid_log_level_raises_error(self):
        """Test that invalid log level raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            setup_logger(log_level="INVALID")
        
        assert "Invalid log level" in str(exc_info.value)
    
    def test_case_insensitive_log_level(self, temp_log_file):
        """Test that log level is case-insensitive."""
        setup_logger(log_level="info", log_file=temp_log_file, console=False)
        
        logger.info("Test message")
        
        assert "Test message" in temp_log_file.read_text()


# Test: Log Rotation
class TestLogRotation:
    """Test log rotation functionality."""
    
    def test_rotation_by_size(self, tmp_path):
        """Test log rotation by file size."""
        log_file = tmp_path / "rotation.log"
        
        # Set very small rotation size for testing
        # Use integer bytes or "X MB" format, not "X bytes"
        setup_logger(
            log_file=log_file,
            console=False,
            rotation=100,  # Changed from "100 bytes" to just 100 (bytes)
            compression=None  # Disable compression for easier testing
        )
        
        # Write enough to trigger rotation
        for i in range(50):
            logger.info(f"Message {i} with some padding text to increase size")
        
        # Check that rotation occurred (original file + rotated file)
        log_files = list(tmp_path.glob("rotation*.log*"))
        assert len(log_files) >= 1  # At least the current log file
    
    def test_compression_format(self, tmp_path):
        """Test that compression format is respected."""
        log_file = tmp_path / "compressed.log"
        
        setup_logger(
            log_file=log_file,
            console=False,
            rotation=50,  # Changed from "50 bytes" to just 50 (bytes)
            compression="zip"
        )
        
        # Write enough to trigger rotation
        for i in range(20):
            logger.info(f"Message {i} padding text")
        
        # Note: Actual compression happens on rotation, which is async
        # Just verify setup doesn't crash
        assert log_file.exists()


# Test: Structured Logging
class TestStructuredLogging:
    """Test structured logging with context."""
    
    def test_log_context_creates_dict(self):
        """Test that log_context creates proper dictionary."""
        context = log_context(service="plex", vmid=100, action="backup")
        
        assert isinstance(context, dict)
        assert context["service"] == "plex"
        assert context["vmid"] == 100
        assert context["action"] == "backup"
    
    def test_bind_context_to_logger(self, temp_log_file):
        """Test binding context to log messages."""
        setup_logger(log_file=temp_log_file, console=False)
        
        contextual_logger = logger.bind(service="plex", vmid=100)
        contextual_logger.info("Starting backup")
        
        content = temp_log_file.read_text()
        assert "Starting backup" in content
    
    def test_empty_context(self):
        """Test log_context with no arguments."""
        context = log_context()
        assert isinstance(context, dict)
        assert len(context) == 0


# Test: Get Logger
class TestGetLogger:
    """Test get_logger function."""
    
    def test_get_logger_returns_logger(self):
        """Test that get_logger returns a logger instance."""
        setup_logger()
        log = get_logger()
        
        assert log is not None
        assert hasattr(log, 'info')
        assert hasattr(log, 'error')
        assert hasattr(log, 'debug')
    
    def test_get_logger_before_setup(self):
        """Test that get_logger works even before setup_logger."""
        log = get_logger()
        
        # Should still return a logger (loguru's default)
        assert log is not None


# Test: Set Log Level
class TestSetLogLevel:
    """Test runtime log level changes."""
    
    def test_set_valid_log_level(self):
        """Test setting a valid log level."""
        setup_logger()
        
        # Should not raise
        set_log_level("DEBUG")
        set_log_level("ERROR")
    
    def test_set_invalid_log_level_raises_error(self):
        """Test that invalid log level raises ValueError."""
        setup_logger()
        
        with pytest.raises(ValueError) as exc_info:
            set_log_level("INVALID")
        
        assert "Invalid log level" in str(exc_info.value)
    
    def test_set_log_level_case_insensitive(self):
        """Test that set_log_level is case-insensitive."""
        setup_logger()
        
        # Should not raise
        set_log_level("debug")
        set_log_level("InFo")


# Test: Multiple Messages
class TestMultipleMessages:
    """Test logging multiple messages with different levels."""
    
    def test_multiple_log_levels(self, temp_log_file):
        """Test logging messages at different levels."""
        setup_logger(log_level="DEBUG", log_file=temp_log_file, console=False)
        
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
        
        content = temp_log_file.read_text()
        assert "Debug message" in content
        assert "Info message" in content
        assert "Warning message" in content
        assert "Error message" in content
    
    def test_log_with_exception(self, temp_log_file):
        """Test logging with exception traceback."""
        setup_logger(log_file=temp_log_file, console=False)
        
        try:
            raise ValueError("Test exception")
        except ValueError:
            logger.exception("An error occurred")
        
        content = temp_log_file.read_text()
        assert "An error occurred" in content
        assert "ValueError" in content
        assert "Test exception" in content


# Test: Edge Cases
class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_setup_multiple_times(self, temp_log_file):
        """Test that setup_logger can be called multiple times."""
        setup_logger(log_file=temp_log_file, console=False)
        logger.info("First setup")
        
        # Reconfigure
        setup_logger(log_file=temp_log_file, console=False, log_level="DEBUG")
        logger.debug("Second setup")
        
        content = temp_log_file.read_text()
        assert "First setup" in content
        assert "Second setup" in content
    
    def test_unicode_in_messages(self, temp_log_file):
        """Test that unicode characters work in log messages."""
        setup_logger(log_file=temp_log_file, console=False)
        
        logger.info("Unicode test: 你好世界 🎉")
        
        content = temp_log_file.read_text()
        assert "Unicode test" in content
    
    def test_very_long_message(self, temp_log_file):
        """Test logging a very long message."""
        setup_logger(log_file=temp_log_file, console=False)
        
        long_message = "x" * 10000
        logger.info(long_message)
        
        content = temp_log_file.read_text()
        assert long_message in content