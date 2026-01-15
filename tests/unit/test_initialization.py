"""Unit tests for tasks.initialization module.

Tests the session initialization task and its helper functions,
including environment variable handling, path construction, and
metadata loading.
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from w2t_bkin.config import SessionConfig
from w2t_bkin.models import SessionInfo
from w2t_bkin.tasks.initialization import (
    build_session_paths,
    load_session_metadata,
    read_required_env_paths,
    setup_flow_session_task,
)


class TestReadRequiredEnvPaths:
    """Tests for read_required_env_paths helper function."""

    def test_Should_ReturnPaths_When_AllEnvVarsSet(self, monkeypatch, tmp_path):
        """Should return all paths when environment variables are set."""
        # Arrange
        raw_root = tmp_path / "raw"
        interim_root = tmp_path / "interim"
        output_root = tmp_path / "processed"
        models_root = tmp_path / "models"
        root_metadata = tmp_path / "metadata.toml"

        monkeypatch.setenv("W2T_RAW_ROOT", str(raw_root))
        monkeypatch.setenv("W2T_INTERMEDIATE_ROOT", str(interim_root))
        monkeypatch.setenv("W2T_OUTPUT_ROOT", str(output_root))
        monkeypatch.setenv("W2T_MODELS_ROOT", str(models_root))
        monkeypatch.setenv("W2T_ROOT_METADATA", str(root_metadata))

        # Act
        result = read_required_env_paths()

        # Assert
        assert result[0] == raw_root.resolve()
        assert result[1] == interim_root.resolve()
        assert result[2] == output_root.resolve()
        assert result[3] == models_root.resolve()
        assert result[4] == root_metadata.resolve()

    def test_Should_UseDefaultModelsRoot_When_NotSet(self, monkeypatch, tmp_path):
        """Should use default 'models' when W2T_MODELS_ROOT not set."""
        # Arrange
        monkeypatch.setenv("W2T_RAW_ROOT", str(tmp_path / "raw"))
        monkeypatch.setenv("W2T_INTERMEDIATE_ROOT", str(tmp_path / "interim"))
        monkeypatch.setenv("W2T_OUTPUT_ROOT", str(tmp_path / "processed"))
        monkeypatch.delenv("W2T_MODELS_ROOT", raising=False)
        monkeypatch.delenv("W2T_ROOT_METADATA", raising=False)

        # Act
        result = read_required_env_paths()

        # Assert
        assert result[3] == Path("models").resolve()
        assert result[4] is None

    def test_Should_RaiseError_When_RawRootNotSet(self, monkeypatch):
        """Should raise EnvironmentError when W2T_RAW_ROOT not set."""
        # Arrange
        monkeypatch.delenv("W2T_RAW_ROOT", raising=False)

        # Act & Assert
        with pytest.raises(EnvironmentError, match="W2T_RAW_ROOT.*not set"):
            read_required_env_paths()

    def test_Should_RaiseError_When_InterimRootNotSet(self, monkeypatch, tmp_path):
        """Should raise EnvironmentError when W2T_INTERMEDIATE_ROOT not set."""
        # Arrange
        monkeypatch.setenv("W2T_RAW_ROOT", str(tmp_path))
        monkeypatch.delenv("W2T_INTERMEDIATE_ROOT", raising=False)

        # Act & Assert
        with pytest.raises(EnvironmentError, match="W2T_INTERMEDIATE_ROOT.*not set"):
            read_required_env_paths()

    def test_Should_RaiseError_When_OutputRootNotSet(self, monkeypatch, tmp_path):
        """Should raise EnvironmentError when W2T_OUTPUT_ROOT not set."""
        # Arrange
        monkeypatch.setenv("W2T_RAW_ROOT", str(tmp_path))
        monkeypatch.setenv("W2T_INTERMEDIATE_ROOT", str(tmp_path))
        monkeypatch.delenv("W2T_OUTPUT_ROOT", raising=False)

        # Act & Assert
        with pytest.raises(EnvironmentError, match="W2T_OUTPUT_ROOT.*not set"):
            read_required_env_paths()


class TestBuildSessionPaths:
    """Tests for build_session_paths helper function."""

    def test_Should_ReturnPaths_When_RawSessionExists(self, tmp_path):
        """Should return correct paths when raw session directory exists."""
        # Arrange
        raw_root = tmp_path / "raw"
        interim_root = tmp_path / "interim"
        output_root = tmp_path / "processed"

        subject_id = "subject-001"
        session_id = "session-001"

        raw_session = raw_root / subject_id / session_id
        raw_session.mkdir(parents=True)

        # Act
        raw_dir, interim_dir, processed_dir = build_session_paths(
            subject_id=subject_id,
            session_id=session_id,
            raw_root=raw_root,
            interim_root=interim_root,
            output_root=output_root,
        )

        # Assert
        assert raw_dir == raw_session
        assert interim_dir == interim_root / subject_id / session_id
        assert processed_dir == output_root / subject_id / session_id

    def test_Should_RaiseError_When_RawSessionNotExists(self, tmp_path):
        """Should raise FileNotFoundError when raw session directory doesn't exist."""
        # Arrange
        raw_root = tmp_path / "raw"
        interim_root = tmp_path / "interim"
        output_root = tmp_path / "processed"

        # Act & Assert
        with pytest.raises(FileNotFoundError, match="Session directory not found"):
            build_session_paths(
                subject_id="subject-999",
                session_id="session-999",
                raw_root=raw_root,
                interim_root=interim_root,
                output_root=output_root,
            )


class TestLoadSessionMetadata:
    """Tests for load_session_metadata helper function."""

    def test_Should_LoadMetadata_When_SessionTomlExists(self, tmp_path):
        """Should load metadata from session.toml."""
        # Arrange
        raw_root = tmp_path / "raw"
        subject_id = "subject-001"
        session_id = "session-001"

        session_dir = raw_root / subject_id / session_id
        session_dir.mkdir(parents=True)

        session_toml = session_dir / "session.toml"
        session_toml.write_text(
            """
identifier = "test-session"
session_description = "Test session"
        """
        )

        # Act
        metadata = load_session_metadata(
            raw_root=raw_root,
            subject_id=subject_id,
            session_id=session_id,
        )

        # Assert
        assert metadata["identifier"] == "test-session"
        assert metadata["session_description"] == "Test session"

    def test_Should_MergeMetadata_When_MultipleFilesExist(self, tmp_path):
        """Should merge metadata hierarchically from multiple TOML files."""
        # Arrange
        raw_root = tmp_path / "raw"
        subject_id = "subject-001"
        session_id = "session-001"

        # Global metadata
        global_toml = raw_root / "metadata.toml"
        global_toml.parent.mkdir(parents=True, exist_ok=True)
        global_toml.write_text(
            """
institution = "Test University"
        """
        )

        # Subject metadata
        subject_dir = raw_root / subject_id
        subject_toml = subject_dir / "subject.toml"
        subject_toml.parent.mkdir(parents=True, exist_ok=True)
        subject_toml.write_text(
            """
[subject]
subject_id = "subject-001"
        """
        )

        # Session metadata
        session_dir = subject_dir / session_id
        session_toml = session_dir / "session.toml"
        session_toml.parent.mkdir(parents=True, exist_ok=True)
        session_toml.write_text(
            """
identifier = "session-001"
session_description = "Test session"
        """
        )

        # Act
        metadata = load_session_metadata(
            raw_root=raw_root,
            subject_id=subject_id,
            session_id=session_id,
        )

        # Assert - all levels merged
        assert metadata["institution"] == "Test University"
        assert metadata["subject"]["subject_id"] == "subject-001"
        assert metadata["identifier"] == "session-001"
        assert metadata["session_description"] == "Test session"

    def test_Should_RaiseError_When_NoMetadataFilesFound(self, tmp_path):
        """Should raise ValueError when no metadata files are found."""
        # Arrange
        raw_root = tmp_path / "raw"

        # Act & Assert
        with pytest.raises(ValueError, match="No metadata files found"):
            load_session_metadata(
                raw_root=raw_root,
                subject_id="subject-999",
                session_id="session-999",
            )


class TestSetupFlowSessionTask:
    """Tests for setup_flow_session_task (main Prefect task)."""

    def test_Should_ReturnSessionInfo_When_ValidEnvironment(self, monkeypatch, tmp_path):
        """Should return SessionInfo with all paths when environment is valid."""
        # Arrange
        raw_root = tmp_path / "raw"
        interim_root = tmp_path / "interim"
        output_root = tmp_path / "processed"
        models_root = tmp_path / "models"

        subject_id = "subject-001"
        session_id = "session-001"

        # Create raw session directory with metadata
        session_dir = raw_root / subject_id / session_id
        session_dir.mkdir(parents=True)
        session_toml = session_dir / "session.toml"
        session_toml.write_text(
            """
identifier = "test-session"
session_description = "Test session"
        """
        )

        # Set environment
        monkeypatch.setenv("W2T_RAW_ROOT", str(raw_root))
        monkeypatch.setenv("W2T_INTERMEDIATE_ROOT", str(interim_root))
        monkeypatch.setenv("W2T_OUTPUT_ROOT", str(output_root))
        monkeypatch.setenv("W2T_MODELS_ROOT", str(models_root))

        # Create minimal config
        config = SessionConfig()

        # Act
        result = setup_flow_session_task(
            subject_id=subject_id,
            session_id=session_id,
            session_config=config,
        )

        # Assert
        assert isinstance(result, SessionInfo)
        assert result.subject_id == subject_id
        assert result.session_id == session_id
        assert result.raw_dir == session_dir
        assert result.interim_dir == interim_root / subject_id / session_id
        assert result.processed_dir == output_root / subject_id / session_id
        assert result.models_dir == models_root.resolve()
        assert result.metadata["identifier"] == "test-session"

    def test_Should_CreateDirectories_When_TheyDontExist(self, monkeypatch, tmp_path):
        """Should create interim and processed directories if they don't exist."""
        # Arrange
        raw_root = tmp_path / "raw"
        interim_root = tmp_path / "interim"
        output_root = tmp_path / "processed"

        subject_id = "subject-001"
        session_id = "session-001"

        # Create raw session directory only
        session_dir = raw_root / subject_id / session_id
        session_dir.mkdir(parents=True)
        session_toml = session_dir / "session.toml"
        session_toml.write_text('identifier = "test"')

        monkeypatch.setenv("W2T_RAW_ROOT", str(raw_root))
        monkeypatch.setenv("W2T_INTERMEDIATE_ROOT", str(interim_root))
        monkeypatch.setenv("W2T_OUTPUT_ROOT", str(output_root))

        config = SessionConfig()

        # Act
        result = setup_flow_session_task(
            subject_id=subject_id,
            session_id=session_id,
            session_config=config,
        )

        # Assert
        assert result.interim_dir.exists()
        assert result.processed_dir.exists()

    def test_Should_ApplyLoggingConfig_When_Specified(self, monkeypatch, tmp_path):
        """Should apply logging configuration from SessionConfig."""
        # Arrange
        import logging

        raw_root = tmp_path / "raw"
        interim_root = tmp_path / "interim"
        output_root = tmp_path / "processed"

        subject_id = "subject-001"
        session_id = "session-001"

        session_dir = raw_root / subject_id / session_id
        session_dir.mkdir(parents=True)
        (session_dir / "session.toml").write_text('identifier = "test"')

        monkeypatch.setenv("W2T_RAW_ROOT", str(raw_root))
        monkeypatch.setenv("W2T_INTERMEDIATE_ROOT", str(interim_root))
        monkeypatch.setenv("W2T_OUTPUT_ROOT", str(output_root))

        # Create config with DEBUG level
        config = SessionConfig()
        config.logging.level = "DEBUG"

        # Act
        setup_flow_session_task(
            subject_id=subject_id,
            session_id=session_id,
            session_config=config,
        )

        # Assert
        logger = logging.getLogger("w2t_bkin")
        assert logger.level == logging.DEBUG
