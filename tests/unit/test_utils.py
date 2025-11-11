"""Unit tests for utility functions (Phase 0 subset).

Tests utility functions for hashing, path sanitization, and JSON I/O.
Requirements: NFR-1, NFR-2, NFR-3
Acceptance: A18 (deterministic hashing)
"""

import pytest
import json
from pathlib import Path
import tempfile


class TestHashingUtils:
    """Test deterministic hashing utilities."""

    def test_Should_ProduceSHA256Hash_When_StringProvided(self):
        """Should produce deterministic SHA256 hash for string input."""
        from w2t_bkin.utils import compute_hash

        input_str = "test_string"
        hash1 = compute_hash(input_str)
        hash2 = compute_hash(input_str)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex digest length
        assert isinstance(hash1, str)

    def test_Should_ProduceDifferentHash_When_InputDiffers(self):
        """Should produce different hashes for different inputs."""
        from w2t_bkin.utils import compute_hash

        hash1 = compute_hash("string_a")
        hash2 = compute_hash("string_b")

        assert hash1 != hash2

    def test_Should_HandleDictInput_When_ComputingHash(self):
        """Should handle dictionary input for hashing (canonicalized)."""
        from w2t_bkin.utils import compute_hash

        test_dict = {"key1": "value1", "key2": "value2"}
        hash_result = compute_hash(test_dict)

        assert len(hash_result) == 64
        assert isinstance(hash_result, str)

    def test_Should_ProduceSameHash_When_DictKeyOrderDiffers(self):
        """Should produce same hash regardless of dict key order (canonicalization)."""
        from w2t_bkin.utils import compute_hash

        dict1 = {"a": 1, "b": 2, "c": 3}
        dict2 = {"c": 3, "a": 1, "b": 2}

        hash1 = compute_hash(dict1)
        hash2 = compute_hash(dict2)

        assert hash1 == hash2


class TestPathSanitization:
    """Test path sanitization for security."""

    def test_Should_SanitizePath_When_ValidPathProvided(self):
        """Should accept and sanitize valid relative path."""
        from w2t_bkin.utils import sanitize_path

        path = "data/raw/session_01"
        sanitized = sanitize_path(path)

        assert sanitized is not None
        assert ".." not in str(sanitized)

    def test_Should_RejectPath_When_DirectoryTraversalAttempted(self):
        """Should reject paths with directory traversal attempts."""
        from w2t_bkin.utils import sanitize_path

        with pytest.raises(ValueError) as exc_info:
            sanitize_path("data/../../../etc/passwd")

        assert "traversal" in str(exc_info.value).lower()

    def test_Should_RejectPath_When_AbsolutePathOutsideRoot(self):
        """Should reject absolute paths outside allowed root."""
        from w2t_bkin.utils import sanitize_path

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            
            with pytest.raises(ValueError) as exc_info:
                sanitize_path("/etc/passwd", base=base)

            assert "outside" in str(exc_info.value).lower()


class TestJSONUtils:
    """Test JSON I/O utilities."""

    def test_Should_RoundtripData_When_WritingAndReading(self):
        """Should preserve data through JSON write and read cycle."""
        from w2t_bkin.utils import write_json, read_json

        test_data = {
            "session_id": "test-123",
            "frame_count": 1000,
            "cameras": ["cam0", "cam1"],
            "metadata": {"fps": 30.0, "enabled": True},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "test.json"
            write_json(test_data, json_path)
            loaded_data = read_json(json_path)

            assert loaded_data == test_data

    def test_Should_WriteReadableJSON_When_IndentProvided(self):
        """Should write human-readable JSON with indentation."""
        from w2t_bkin.utils import write_json

        test_data = {"key": "value", "number": 42}

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "test.json"
            write_json(test_data, json_path, indent=4)

            with open(json_path, 'r') as f:
                content = f.read()
            
            # Check that it's properly indented (has newlines and spaces)
            assert "\n" in content
            assert "    " in content

    def test_Should_HandlePathObject_When_WritingJSON(self):
        """Should handle Path objects in JSON serialization."""
        from w2t_bkin.utils import write_json, read_json

        test_data = {
            "file_path": Path("/some/path/file.txt"),
            "other_data": "value"
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "test.json"
            write_json(test_data, json_path)
            loaded_data = read_json(json_path)

            # Path should be converted to string
            assert loaded_data["file_path"] == "/some/path/file.txt"
            assert isinstance(loaded_data["file_path"], str)


class TestLoggingUtils:
    """Test logging utility configuration."""

    def test_Should_ConfigureLogger_When_SettingsProvided(self):
        """Should configure logger with given settings."""
        from w2t_bkin.utils import configure_logger

        logger = configure_logger("test_logger", level="DEBUG", structured=False)

        assert logger.name == "test_logger"
        assert logger.level == 10  # DEBUG level
        assert len(logger.handlers) > 0

    def test_Should_EmitStructuredLogs_When_StructuredModeEnabled(self):
        """Should emit structured (JSON) logs when structured=True."""
        from w2t_bkin.utils import configure_logger
        import logging

        logger = configure_logger("test_structured", level="INFO", structured=True)

        # Check that handler uses JSON-like formatter
        handler = logger.handlers[0]
        formatter = handler.formatter
        
        # Formatter should include JSON markers
        test_record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test message",
            args=(),
            exc_info=None
        )
        
        formatted = formatter.format(test_record)
        assert "{" in formatted and "}" in formatted  # JSON-like structure
