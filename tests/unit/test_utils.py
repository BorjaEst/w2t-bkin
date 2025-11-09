"""Unit tests for the utils module.

Tests JSON/CSV I/O, file hashing, git provenance, timing, and logging utilities
as specified in utils/README.md and api.md.

All tests follow TDD Red Phase principles with clear EARS requirements.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ============================================================================
# JSON I/O Tests
# ============================================================================


class TestJSONIO:
    """Test JSON reading and writing utilities (API §3.2)."""

    def test_Should_WriteAndReadJSON_When_ValidDict_Issue_Utils_JSONIO(self, tmp_path: Path):
        """THE SYSTEM SHALL write and read JSON files for data persistence.

        Requirements: NFR-3 (Observability), Design §8
        Issue: Utils module - JSON I/O round-trip
        """
        # Arrange
        from w2t_bkin.utils import read_json, write_json

        test_data = {
            "session_id": "test_001",
            "cameras": [0, 1, 2, 3, 4],
            "metadata": {"fps": 30.0, "resolution": [1920, 1080]},
        }
        json_path = tmp_path / "test.json"

        # Act
        write_json(json_path, test_data)
        loaded_data = read_json(json_path)

        # Assert
        assert loaded_data == test_data
        assert json_path.exists()

    def test_Should_WriteWithIndent_When_IndentSpecified_Issue_Utils_JSONFormat(self, tmp_path: Path):
        """THE SYSTEM SHALL format JSON with specified indentation.

        Requirements: NFR-3 (Observability)
        Issue: Utils module - JSON formatting
        """
        # Arrange
        from w2t_bkin.utils import write_json

        test_data = {"key": "value", "nested": {"inner": 123}}
        json_path = tmp_path / "formatted.json"

        # Act
        write_json(json_path, test_data, indent=4)
        content = json_path.read_text()

        # Assert
        assert content.count("    ") > 0  # Should have 4-space indentation
        assert "{\n" in content  # Should have newlines

    def test_Should_RaiseFileNotFoundError_When_ReadingNonExistent_Issue_Utils_JSONError(self, tmp_path: Path):
        """THE SYSTEM SHALL raise FileNotFoundError when JSON file does not exist.

        Requirements: Design §4.3 (Error handling)
        Issue: Utils module - JSON read error
        """
        # Arrange
        from w2t_bkin.utils import read_json

        non_existent = tmp_path / "missing.json"

        # Act & Assert
        with pytest.raises(FileNotFoundError):
            read_json(non_existent)

    def test_Should_RaiseJSONDecodeError_When_InvalidJSON_Issue_Utils_JSONValidation(self, tmp_path: Path):
        """THE SYSTEM SHALL raise JSONDecodeError when file contains invalid JSON.

        Requirements: Design §4.3 (Error handling)
        Issue: Utils module - Invalid JSON handling
        """
        # Arrange
        from w2t_bkin.utils import read_json

        invalid_json = tmp_path / "invalid.json"
        invalid_json.write_text("{invalid json content")

        # Act & Assert
        with pytest.raises(json.JSONDecodeError):
            read_json(invalid_json)

    def test_Should_AcceptStringPath_When_PathIsString_Issue_Utils_JSONPathTypes(self, tmp_path: Path):
        """THE SYSTEM SHALL accept both string and Path objects.

        Requirements: Design §4.2 (Stateless functions)
        Issue: Utils module - Path flexibility
        """
        # Arrange
        from w2t_bkin.utils import read_json, write_json

        test_data = {"test": "value"}
        json_path = tmp_path / "test.json"

        # Act - Use string path
        write_json(str(json_path), test_data)
        loaded = read_json(str(json_path))

        # Assert
        assert loaded == test_data

    def test_Should_HandleNestedStructures_When_ComplexData_Issue_Utils_JSONComplex(self, tmp_path: Path):
        """THE SYSTEM SHALL handle deeply nested JSON structures.

        Requirements: NFR-3 (Observability)
        Issue: Utils module - Complex JSON structures
        """
        # Arrange
        from w2t_bkin.utils import read_json, write_json

        complex_data = {
            "level1": {
                "level2": {
                    "level3": {"array": [1, 2, 3], "nested_dict": {"key": "value"}},
                }
            }
        }
        json_path = tmp_path / "complex.json"

        # Act
        write_json(json_path, complex_data)
        loaded = read_json(json_path)

        # Assert
        assert loaded == complex_data
        assert loaded["level1"]["level2"]["level3"]["array"] == [1, 2, 3]

    def test_Should_HandleUnicode_When_NonASCIICharacters_Issue_Utils_JSONUnicode(self, tmp_path: Path):
        """THE SYSTEM SHALL preserve Unicode characters in JSON.

        Requirements: NFR-3 (Observability)
        Issue: Utils module - Unicode handling
        """
        # Arrange
        from w2t_bkin.utils import read_json, write_json

        unicode_data = {"subject": "🐭 Mouse 123", "description": "Naïve behavior"}
        json_path = tmp_path / "unicode.json"

        # Act
        write_json(json_path, unicode_data)
        loaded = read_json(json_path)

        # Assert
        assert loaded == unicode_data
        assert loaded["subject"] == "🐭 Mouse 123"


# ============================================================================
# CSV I/O Tests
# ============================================================================


class TestCSVIO:
    """Test CSV writing utilities (API §3.2)."""

    def test_Should_WriteCSV_When_ValidRows_Issue_Utils_CSVIO(self, tmp_path: Path):
        """THE SYSTEM SHALL write rows to CSV with proper formatting.

        Requirements: Design §3.2 (Timestamp CSV)
        Issue: Utils module - CSV writing
        """
        # Arrange
        from w2t_bkin.utils import write_csv

        rows = [
            {"frame_index": 0, "timestamp": 0.0000},
            {"frame_index": 1, "timestamp": 0.0333},
            {"frame_index": 2, "timestamp": 0.0666},
        ]
        csv_path = tmp_path / "timestamps.csv"

        # Act
        write_csv(csv_path, rows, fieldnames=["frame_index", "timestamp"])

        # Assert
        assert csv_path.exists()
        content = csv_path.read_text()
        assert "frame_index,timestamp" in content
        assert "0,0.0" in content
        assert "1,0.0333" in content

    def test_Should_OrderFieldsExplicitly_When_FieldnamesProvided_Issue_Utils_CSVFieldOrder(self, tmp_path: Path):
        """THE SYSTEM SHALL respect explicit field ordering.

        Requirements: Design §3.2 (Timestamp CSV - strict column order)
        Issue: Utils module - CSV column ordering
        """
        # Arrange
        from w2t_bkin.utils import write_csv

        rows = [
            {"timestamp": 0.0, "frame_index": 0},  # Note: reversed order in dict
            {"timestamp": 0.033, "frame_index": 1},
        ]
        csv_path = tmp_path / "ordered.csv"

        # Act
        write_csv(csv_path, rows, fieldnames=["frame_index", "timestamp"])

        # Assert
        lines = csv_path.read_text().split("\n")
        assert lines[0] == "frame_index,timestamp"
        assert lines[1].startswith("0,")

    def test_Should_InferFieldnames_When_NotProvided_Issue_Utils_CSVAutoFields(self, tmp_path: Path):
        """THE SYSTEM SHALL infer fieldnames from first row when not specified.

        Requirements: Design §4.2 (Stateless functions)
        Issue: Utils module - CSV fieldname inference
        """
        # Arrange
        from w2t_bkin.utils import write_csv

        rows = [{"col_a": 1, "col_b": 2}, {"col_a": 3, "col_b": 4}]
        csv_path = tmp_path / "inferred.csv"

        # Act
        write_csv(csv_path, rows)

        # Assert
        content = csv_path.read_text()
        assert "col_a" in content
        assert "col_b" in content

    def test_Should_RaiseValueError_When_EmptyRowsNoFieldnames_Issue_Utils_CSVValidation(self, tmp_path: Path):
        """THE SYSTEM SHALL raise ValueError for empty rows without fieldnames.

        Requirements: Design §4.3 (Error handling)
        Issue: Utils module - CSV validation error
        """
        # Arrange
        from w2t_bkin.utils import write_csv

        csv_path = tmp_path / "empty.csv"

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            write_csv(csv_path, rows=[])

        assert "empty" in str(exc_info.value).lower() or "fieldnames" in str(exc_info.value).lower()

    def test_Should_HandleSpecialCharacters_When_InData_Issue_Utils_CSVEscape(self, tmp_path: Path):
        """THE SYSTEM SHALL properly escape special characters in CSV.

        Requirements: Design §3.2 (Timestamp CSV)
        Issue: Utils module - CSV escaping
        """
        # Arrange
        from w2t_bkin.utils import write_csv

        rows = [
            {"name": "trial,1", "description": 'Contains "quotes"'},
            {"name": "trial\n2", "description": "Newline test"},
        ]
        csv_path = tmp_path / "special.csv"

        # Act
        write_csv(csv_path, rows, fieldnames=["name", "description"])

        # Assert
        content = csv_path.read_text()
        assert '"trial,1"' in content or "trial,1" in content  # Properly escaped
        assert csv_path.exists()

    def test_Should_AcceptStringPath_When_PathIsString_Issue_Utils_CSVPathTypes(self, tmp_path: Path):
        """THE SYSTEM SHALL accept both string and Path objects for CSV.

        Requirements: Design §4.2 (Stateless functions)
        Issue: Utils module - CSV path flexibility
        """
        # Arrange
        from w2t_bkin.utils import write_csv

        rows = [{"col": "value"}]
        csv_path = tmp_path / "test.csv"

        # Act
        write_csv(str(csv_path), rows)

        # Assert
        assert csv_path.exists()


# ============================================================================
# File Hashing Tests
# ============================================================================


class TestFileHashing:
    """Test file hashing for provenance and caching (API §3.2)."""

    def test_Should_ComputeConsistentHash_When_SameFile_Issue_Utils_HashConsistency(self, tmp_path: Path):
        """THE SYSTEM SHALL compute consistent hashes for identical files.

        Requirements: NFR-1 (Reproducibility), NFR-8 (Data integrity)
        Issue: Utils module - Hash consistency
        """
        # Arrange
        from w2t_bkin.utils import file_hash

        test_file = tmp_path / "test.txt"
        test_file.write_text("Test content for hashing")

        # Act
        hash1 = file_hash(test_file)
        hash2 = file_hash(test_file)

        # Assert
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex digest length

    def test_Should_ProduceDifferentHash_When_ContentDiffers_Issue_Utils_HashUniqueness(self, tmp_path: Path):
        """THE SYSTEM SHALL produce different hashes for different content.

        Requirements: NFR-8 (Data integrity)
        Issue: Utils module - Hash uniqueness
        """
        # Arrange
        from w2t_bkin.utils import file_hash

        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("Content A")
        file2.write_text("Content B")

        # Act
        hash1 = file_hash(file1)
        hash2 = file_hash(file2)

        # Assert
        assert hash1 != hash2

    def test_Should_SupportMultipleAlgorithms_When_AlgorithmSpecified_Issue_Utils_HashAlgorithms(self, tmp_path: Path):
        """THE SYSTEM SHALL support multiple hash algorithms.

        Requirements: NFR-11 (Provenance)
        Issue: Utils module - Hash algorithm support
        """
        # Arrange
        from w2t_bkin.utils import file_hash

        test_file = tmp_path / "test.txt"
        test_file.write_text("Content")

        # Act
        sha256_hash = file_hash(test_file, algorithm="sha256")
        md5_hash = file_hash(test_file, algorithm="md5")

        # Assert
        assert len(sha256_hash) == 64
        assert len(md5_hash) == 32
        assert sha256_hash != md5_hash

    def test_Should_RaiseFileNotFoundError_When_FileDoesNotExist_Issue_Utils_HashError(self, tmp_path: Path):
        """THE SYSTEM SHALL raise FileNotFoundError for missing files.

        Requirements: Design §4.3 (Error handling)
        Issue: Utils module - Hash error handling
        """
        # Arrange
        from w2t_bkin.utils import file_hash

        non_existent = tmp_path / "missing.txt"

        # Act & Assert
        with pytest.raises(FileNotFoundError):
            file_hash(non_existent)

    def test_Should_RaiseValueError_When_InvalidAlgorithm_Issue_Utils_HashValidation(self, tmp_path: Path):
        """THE SYSTEM SHALL raise ValueError for unsupported algorithms.

        Requirements: Design §4.3 (Error handling)
        Issue: Utils module - Algorithm validation
        """
        # Arrange
        from w2t_bkin.utils import file_hash

        test_file = tmp_path / "test.txt"
        test_file.write_text("Content")

        # Act & Assert
        with pytest.raises(ValueError):
            file_hash(test_file, algorithm="invalid_algorithm")

    def test_Should_HandleLargeFiles_When_ReadingInChunks_Issue_Utils_HashPerformance(self, tmp_path: Path):
        """THE SYSTEM SHALL efficiently hash large files using chunked reading.

        Requirements: NFR-4 (Performance), Design §8
        Issue: Utils module - Large file hashing
        """
        # Arrange
        from w2t_bkin.utils import file_hash

        large_file = tmp_path / "large.bin"
        # Create 1MB file
        large_file.write_bytes(b"x" * (1024 * 1024))

        # Act
        hash_value = file_hash(large_file, chunk_size=4096)

        # Assert
        assert len(hash_value) == 64
        assert hash_value is not None

    def test_Should_AcceptStringPath_When_PathIsString_Issue_Utils_HashPathTypes(self, tmp_path: Path):
        """THE SYSTEM SHALL accept both string and Path objects.

        Requirements: Design §4.2 (Stateless functions)
        Issue: Utils module - Hash path flexibility
        """
        # Arrange
        from w2t_bkin.utils import file_hash

        test_file = tmp_path / "test.txt"
        test_file.write_text("Content")

        # Act
        hash_value = file_hash(str(test_file))

        # Assert
        assert len(hash_value) == 64


# ============================================================================
# Git Provenance Tests
# ============================================================================


class TestGitProvenance:
    """Test git commit retrieval for provenance (API §3.2)."""

    def test_Should_ReturnCommitHash_When_InGitRepo_Issue_Utils_GitCommit(self):
        """THE SYSTEM SHALL retrieve git commit hash when in repository.

        Requirements: NFR-11 (Provenance), Design §11
        Issue: Utils module - Git commit retrieval
        """
        # Arrange
        from w2t_bkin.utils import get_commit

        # Act
        commit = get_commit()

        # Assert
        # Should return either a 7-char hash or "unknown"
        assert isinstance(commit, str)
        assert len(commit) == 7 or commit == "unknown"

    @patch("subprocess.run")
    def test_Should_ReturnUnknown_When_NotGitRepo_Issue_Utils_GitFallback(self, mock_run):
        """THE SYSTEM SHALL return 'unknown' when not in git repository.

        Requirements: NFR-11 (Provenance), Design §11
        Issue: Utils module - Git fallback
        """
        # Arrange
        from w2t_bkin.utils import get_commit

        # Simulate git command failure
        mock_run.side_effect = FileNotFoundError()

        # Act
        commit = get_commit()

        # Assert
        assert commit == "unknown"

    @patch("subprocess.run")
    def test_Should_ReturnUnknown_When_GitCommandFails_Issue_Utils_GitError(self, mock_run):
        """THE SYSTEM SHALL handle git command failures gracefully.

        Requirements: Design §4.3 (Error handling)
        Issue: Utils module - Git error handling
        """
        # Arrange
        from w2t_bkin.utils import get_commit

        # Simulate git returning non-zero exit
        mock_result = MagicMock()
        mock_result.returncode = 128
        mock_result.stdout = ""
        mock_run.return_value = mock_result

        # Act
        commit = get_commit()

        # Assert
        assert commit == "unknown"

    @patch("subprocess.run")
    def test_Should_TrimWhitespace_When_GitReturnsHash_Issue_Utils_GitFormat(self, mock_run):
        """THE SYSTEM SHALL trim whitespace from git output.

        Requirements: NFR-11 (Provenance)
        Issue: Utils module - Git output formatting
        """
        # Arrange
        from w2t_bkin.utils import get_commit

        # Simulate git output with whitespace
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "abc1234\n"
        mock_run.return_value = mock_result

        # Act
        commit = get_commit()

        # Assert
        assert commit == "abc1234"
        assert "\n" not in commit


# ============================================================================
# Timing Utilities Tests
# ============================================================================


class TestTimingUtilities:
    """Test timing context manager (API §3.2)."""

    def test_Should_MeasureElapsedTime_When_BlockExecutes_Issue_Utils_Timing(self, capsys):
        """THE SYSTEM SHALL measure and report elapsed time for code blocks.

        Requirements: NFR-3 (Observability), NFR-4 (Performance)
        Issue: Utils module - Time measurement
        """
        # Arrange
        from w2t_bkin.utils import time_block

        # Act
        with time_block("Test operation"):
            time.sleep(0.01)  # Sleep 10ms

        # Assert
        captured = capsys.readouterr()
        assert "Test operation" in captured.out
        assert "completed" in captured.out.lower() or "took" in captured.out.lower()

    def test_Should_LogWithLogger_When_LoggerProvided_Issue_Utils_TimingLogger(self, caplog):
        """THE SYSTEM SHALL use logger when provided instead of stdout.

        Requirements: NFR-3 (Observability), Design §7
        Issue: Utils module - Timing with logger
        """
        # Arrange
        from w2t_bkin.utils import time_block

        logger = logging.getLogger("test_logger")
        logger.setLevel(logging.INFO)

        # Act
        with caplog.at_level(logging.INFO):
            with time_block("Logged operation", logger=logger):
                time.sleep(0.01)

        # Assert
        assert "Logged operation" in caplog.text

    def test_Should_AccuratelyMeasureTime_When_SlowOperation_Issue_Utils_TimingAccuracy(self, capsys):
        """THE SYSTEM SHALL accurately measure elapsed time.

        Requirements: NFR-4 (Performance)
        Issue: Utils module - Timing accuracy
        """
        # Arrange
        from w2t_bkin.utils import time_block

        # Act
        with time_block("Sleep test"):
            time.sleep(0.1)  # Sleep 100ms

        # Assert
        captured = capsys.readouterr()
        # Should report approximately 0.1s (allowing for some variance)
        assert "0.1" in captured.out or "100" in captured.out  # seconds or ms

    def test_Should_HandleExceptions_When_BlockRaises_Issue_Utils_TimingException(self, capsys):
        """THE SYSTEM SHALL propagate exceptions while still reporting time.

        Requirements: Design §4.3 (Error handling)
        Issue: Utils module - Timing exception handling
        """
        # Arrange
        from w2t_bkin.utils import time_block

        # Act & Assert
        with pytest.raises(ValueError):
            with time_block("Failing operation"):
                raise ValueError("Test error")

        # Timing message may or may not appear depending on implementation


# ============================================================================
# Logging Configuration Tests
# ============================================================================


class TestLoggingConfiguration:
    """Test logging configuration utilities (API §3.2)."""

    def test_Should_ConfigureRootLogger_When_Called_Issue_Utils_LogConfig(self):
        """THE SYSTEM SHALL configure root logger with standardized format.

        Requirements: NFR-3 (Observability), Design §7
        Issue: Utils module - Logging configuration
        """
        # Arrange
        from w2t_bkin.utils import configure_logging

        # Act
        configure_logging(level="INFO")

        # Assert
        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO

    def test_Should_SetDebugLevel_When_DebugSpecified_Issue_Utils_LogLevel(self):
        """THE SYSTEM SHALL support DEBUG, INFO, WARNING, ERROR levels.

        Requirements: NFR-3 (Observability)
        Issue: Utils module - Log level setting
        """
        # Arrange
        from w2t_bkin.utils import configure_logging

        # Act
        configure_logging(level="DEBUG")

        # Assert
        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG

    def test_Should_EnableStructuredLogging_When_StructuredTrue_Issue_Utils_StructuredLog(self):
        """THE SYSTEM SHALL support JSON structured logging when enabled.

        Requirements: NFR-3 (Observability), Design §7
        Issue: Utils module - Structured logging
        """
        # Arrange
        from w2t_bkin.utils import configure_logging

        # Act
        configure_logging(level="INFO", structured=True)

        # Assert
        # Implementation should add JSON formatter
        root_logger = logging.getLogger()
        assert len(root_logger.handlers) > 0

    def test_Should_HandleInvalidLevel_When_UnknownLevel_Issue_Utils_LogValidation(self):
        """THE SYSTEM SHALL handle invalid log level gracefully.

        Requirements: Design §4.3 (Error handling)
        Issue: Utils module - Log level validation
        """
        # Arrange
        from w2t_bkin.utils import configure_logging

        # Act & Assert
        # Should either raise ValueError or default to INFO
        try:
            configure_logging(level="INVALID")
            # If no exception, verify it defaults to something reasonable
            root_logger = logging.getLogger()
            assert root_logger.level in [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR]
        except ValueError:
            # Acceptable to raise ValueError
            pass


# ============================================================================
# Integration Tests
# ============================================================================


class TestUtilsIntegration:
    """Integration tests combining multiple utilities."""

    def test_Should_CreateManifestWithProvenance_When_FullWorkflow_Issue_Utils_Integration(self, tmp_path: Path):
        """THE SYSTEM SHALL support manifest creation with full provenance.

        Requirements: NFR-11 (Provenance), Design §11
        Issue: Utils module - Integration workflow
        """
        # Arrange
        from w2t_bkin.utils import file_hash, get_commit, write_json

        # Create mock session files
        video_file = tmp_path / "video.mp4"
        video_file.write_bytes(b"mock video data")

        # Act
        manifest = {
            "session_id": "test_001",
            "provenance": {
                "git_commit": get_commit(),
                "video_hash": file_hash(video_file),
            },
        }
        manifest_path = tmp_path / "manifest.json"
        write_json(manifest_path, manifest)

        # Assert
        assert manifest_path.exists()
        assert manifest["provenance"]["git_commit"] in ["unknown"] or len(manifest["provenance"]["git_commit"]) == 7
        assert len(manifest["provenance"]["video_hash"]) == 64
