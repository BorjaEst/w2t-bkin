"""Unit tests for utility functions (Phase 0 subset).

Tests utility functions for hashing, path sanitization, and JSON I/O.
Requirements: NFR-1, NFR-2, NFR-3
Acceptance: A18 (deterministic hashing)
"""

import json
from pathlib import Path
import tempfile

import pytest


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
        from w2t_bkin.utils import read_json, write_json

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

            with open(json_path, "r") as f:
                content = f.read()

            # Check that it's properly indented (has newlines and spaces)
            assert "\n" in content
            assert "    " in content

    def test_Should_HandlePathObject_When_WritingJSON(self):
        """Should handle Path objects in JSON serialization."""
        from w2t_bkin.utils import read_json, write_json

        test_data = {"file_path": Path("/some/path/file.txt"), "other_data": "value"}

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
        import logging

        from w2t_bkin.utils import configure_logger

        logger = configure_logger("test_structured", level="INFO", structured=True)

        # Check that handler uses JSON-like formatter
        handler = logger.handlers[0]
        formatter = handler.formatter

        # Formatter should include JSON markers
        test_record = logging.LogRecord(name="test", level=logging.INFO, pathname="", lineno=0, msg="test message", args=(), exc_info=None)

        formatted = formatter.format(test_record)
        assert "{" in formatted and "}" in formatted  # JSON-like structure


class TestFileDiscovery:
    """Test file discovery and sorting utilities."""

    def test_Should_DiscoverFiles_When_GlobPatternProvided(self):
        """Should discover files matching glob pattern."""
        from w2t_bkin.utils import discover_files

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            # Create test files
            (base / "file1.txt").touch()
            (base / "file2.txt").touch()
            (base / "file3.log").touch()

            files = discover_files(base, "*.txt")

            assert len(files) == 2
            assert all(f.suffix == ".txt" for f in files)
            assert all(f.is_absolute() for f in files)

    def test_Should_SortFiles_When_SortEnabled(self):
        """Should sort files by name when sort=True."""
        from w2t_bkin.utils import discover_files

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            # Create files in non-alphabetical order
            (base / "c.txt").touch()
            (base / "a.txt").touch()
            (base / "b.txt").touch()

            files = discover_files(base, "*.txt", sort=True)
            names = [f.name for f in files]

            assert names == ["a.txt", "b.txt", "c.txt"]

    def test_Should_SortByStrategy_When_SortFilesUsed(self):
        """Should sort files according to specified strategy."""
        import time

        from w2t_bkin.utils import sort_files

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            # Create files with different names
            file_c = base / "c.txt"
            file_a = base / "a.txt"
            file_b = base / "b.txt"

            file_a.touch()
            time.sleep(0.01)
            file_c.touch()
            time.sleep(0.01)
            file_b.touch()

            files = [file_c, file_a, file_b]

            # Test name_asc
            sorted_asc = sort_files(files, "name_asc")
            assert [f.name for f in sorted_asc] == ["a.txt", "b.txt", "c.txt"]

            # Test name_desc
            sorted_desc = sort_files(files, "name_desc")
            assert [f.name for f in sorted_desc] == ["c.txt", "b.txt", "a.txt"]

            # Test time_asc (oldest first)
            sorted_time = sort_files(files, "time_asc")
            assert sorted_time[0].name == "a.txt"  # Created first
            assert sorted_time[-1].name == "b.txt"  # Created last


class TestFileValidation:
    """Test file and directory validation utilities."""

    def test_Should_ValidateFile_When_FileExists(self):
        """Should pass validation when file exists."""
        from w2t_bkin.utils import validate_file_exists

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.touch()

            # Should not raise
            validate_file_exists(test_file)

    def test_Should_RaiseError_When_FileDoesNotExist(self):
        """Should raise error when file doesn't exist."""
        from w2t_bkin.utils import validate_file_exists

        with pytest.raises(FileNotFoundError):
            validate_file_exists(Path("/nonexistent/file.txt"))

    def test_Should_RaiseError_When_PathIsDirectory(self):
        """Should raise error when path is directory, not file."""
        from w2t_bkin.utils import validate_file_exists

        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(FileNotFoundError):
                validate_file_exists(Path(tmpdir))

    def test_Should_ValidateDirectory_When_DirExists(self):
        """Should pass validation when directory exists."""
        from w2t_bkin.utils import validate_dir_exists

        with tempfile.TemporaryDirectory() as tmpdir:
            # Should not raise
            validate_dir_exists(Path(tmpdir))

    def test_Should_RaiseError_When_DirDoesNotExist(self):
        """Should raise error when directory doesn't exist."""
        from w2t_bkin.utils import validate_dir_exists

        with pytest.raises(FileNotFoundError):
            validate_dir_exists(Path("/nonexistent/directory"))

    def test_Should_ValidateFileSize_When_WithinLimit(self):
        """Should return file size when within limit."""
        from w2t_bkin.utils import validate_file_size

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("x" * 1000)  # 1 KB

            size_mb = validate_file_size(test_file, max_size_mb=1.0)
            assert 0 < size_mb < 0.01  # Should be ~0.001 MB

    def test_Should_RaiseError_When_FileTooLarge(self):
        """Should raise error when file exceeds size limit."""
        from w2t_bkin.utils import validate_file_size

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("x" * (2 * 1024 * 1024))  # 2 MB

            with pytest.raises(ValueError) as exc_info:
                validate_file_size(test_file, max_size_mb=1.0)

            assert "too large" in str(exc_info.value).lower()


class TestStringSanitization:
    """Test string sanitization utilities."""

    def test_Should_SanitizeString_When_ValidInput(self):
        """Should sanitize string with alphanumeric and hyphens."""
        from w2t_bkin.utils import sanitize_string

        result = sanitize_string("Session-001", allowed_pattern="alphanumeric_-")
        assert result == "Session-001"

    def test_Should_RemoveInvalidChars_When_Sanitizing(self):
        """Should remove invalid characters based on pattern."""
        from w2t_bkin.utils import sanitize_string

        result = sanitize_string("Test@#$%123", allowed_pattern="alphanumeric")
        assert result == "Test123"

    def test_Should_LimitLength_When_TooLong(self):
        """Should limit string length to max_length."""
        from w2t_bkin.utils import sanitize_string

        long_string = "a" * 200
        result = sanitize_string(long_string, max_length=50)
        assert len(result) == 50

    def test_Should_ReturnDefault_When_ResultEmpty(self):
        """Should return default value when sanitized string is empty."""
        from w2t_bkin.utils import sanitize_string

        result = sanitize_string("@#$%^&", allowed_pattern="alphanumeric", default="unknown")
        assert result == "unknown"

    def test_Should_HandleNonString_When_InvalidType(self):
        """Should return default when input is not a string."""
        from w2t_bkin.utils import sanitize_string

        result = sanitize_string(12345, default="unknown")  # type: ignore
        assert result == "unknown"


class TestDirectoryUtils:
    """Test directory creation and validation utilities."""

    def test_Should_CreateDirectory_When_EnsureCalled(self):
        """Should create directory if it doesn't exist."""
        from w2t_bkin.utils import ensure_directory

        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = Path(tmpdir) / "subdir" / "nested"

            result = ensure_directory(new_dir)

            assert new_dir.exists()
            assert new_dir.is_dir()
            assert result == new_dir

    def test_Should_CheckWritable_When_Requested(self):
        """Should verify directory is writable when check_writable=True."""
        from w2t_bkin.utils import ensure_directory

        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir) / "writable"

            # Should not raise
            ensure_directory(test_dir, check_writable=True)
            assert test_dir.exists()

    def test_Should_RaiseError_When_PathIsFile(self):
        """Should raise error when path exists but is a file."""
        from w2t_bkin.utils import ensure_directory

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "file.txt"
            test_file.touch()

            with pytest.raises(OSError):
                ensure_directory(test_file)


class TestFileChecksum:
    """Test file checksum computation."""

    def test_Should_ComputeChecksum_When_FileProvided(self):
        """Should compute SHA256 checksum of file."""
        from w2t_bkin.utils import compute_file_checksum

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test content")

            checksum = compute_file_checksum(test_file)

            assert len(checksum) == 64  # SHA256 hex length
            assert isinstance(checksum, str)

    def test_Should_ProduceSameChecksum_When_SameContent(self):
        """Should produce same checksum for same content."""
        from w2t_bkin.utils import compute_file_checksum

        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = Path(tmpdir) / "file1.txt"
            file2 = Path(tmpdir) / "file2.txt"

            content = "identical content"
            file1.write_text(content)
            file2.write_text(content)

            checksum1 = compute_file_checksum(file1)
            checksum2 = compute_file_checksum(file2)

            assert checksum1 == checksum2

    def test_Should_SupportAlgorithms_When_Specified(self):
        """Should support different hash algorithms."""
        from w2t_bkin.utils import compute_file_checksum

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test")

            sha256 = compute_file_checksum(test_file, algorithm="sha256")
            sha1 = compute_file_checksum(test_file, algorithm="sha1")
            md5 = compute_file_checksum(test_file, algorithm="md5")

            assert len(sha256) == 64
            assert len(sha1) == 40
            assert len(md5) == 32


class TestTOMLReading:
    """Test TOML file reading utility."""

    def test_Should_ReadTOML_When_ValidFile(self):
        """Should read and parse TOML file."""
        from w2t_bkin.utils import read_toml

        with tempfile.TemporaryDirectory() as tmpdir:
            toml_file = Path(tmpdir) / "test.toml"
            toml_file.write_text('[section]\nkey = "value"\nnumber = 42\n')

            data = read_toml(toml_file)

            assert data["section"]["key"] == "value"
            assert data["section"]["number"] == 42

    def test_Should_HandleStrPath_When_ReadingTOML(self):
        """Should handle string path in read_toml."""
        from w2t_bkin.utils import read_toml

        with tempfile.TemporaryDirectory() as tmpdir:
            toml_file = Path(tmpdir) / "test.toml"
            toml_file.write_text('[section]\nkey = "value"\n')

            data = read_toml(str(toml_file))

            assert data["section"]["key"] == "value"

    def test_Should_RaiseError_When_TOMLNotFound(self):
        """Should raise error when TOML file doesn't exist."""
        from w2t_bkin.utils import read_toml

        with pytest.raises(FileNotFoundError):
            read_toml("/nonexistent/file.toml")
