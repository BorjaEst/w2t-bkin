"""Unit tests for data_manager module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from w2t_bkin.data.manager import (
    ExperimentConfig,
    SessionConfig,
    SubjectConfig,
    ValidationResult,
    add_session,
    add_subject,
    detect_file_patterns,
    init_experiment,
    validate_experiment_structure,
)


class TestExperimentInitialization:
    """Tests for experiment initialization."""

    def test_init_experiment_creates_structure(self, tmp_path):
        """Test that init_experiment creates correct directory structure."""
        root = tmp_path / "test-experiment"

        success = init_experiment(
            root_path=root,
            lab="Test Lab",
            institution="Test University",
            experimenters=["Alice", "Bob"],
            protocol="TEST-001",
            experiment_description="Test experiment",
            interactive=False,
        )

        assert success is True
        assert (root / "data" / "raw").exists()
        assert (root / "data" / "interim").exists()
        assert (root / "data" / "processed").exists()
        assert (root / "data" / "external").exists()
        assert (root / "models").exists()
        assert (root / "data" / "raw" / "metadata.toml").exists()
        assert (root / "configuration.toml").exists()

    def test_init_experiment_with_existing_directory(self, tmp_path):
        """Test that init_experiment handles existing non-empty directory."""
        root = tmp_path / "test-experiment"
        root.mkdir()
        (root / "existing.txt").touch()

        # With interactive=True, should prompt (we skip by setting interactive=False and accepting existing)
        success = init_experiment(
            root_path=root,
            lab="Test Lab",
            institution="Test University",
            experimenters=["Alice"],
            interactive=False,  # Bypass prompt
        )

        assert success is True


class TestSubjectManagement:
    """Tests for subject management."""

    def test_add_subject_creates_structure(self, tmp_path):
        """Test that add_subject creates correct structure."""
        root = tmp_path / "experiment"
        raw_root = root / "data" / "raw"
        raw_root.mkdir(parents=True)

        subject_config = SubjectConfig(
            subject_id="subject-001",
            species="Mus musculus",
            sex="M",
            age="P90D",
        )

        success = add_subject(
            experiment_root=root,
            subject_config=subject_config,
            interactive=False,
        )

        assert success is True
        assert (raw_root / "subject-001").exists()
        assert (raw_root / "subject-001" / "subject.toml").exists()

    def test_add_subject_invalid_id(self, tmp_path):
        """Test that add_subject rejects invalid subject ID."""
        root = tmp_path / "experiment"
        raw_root = root / "data" / "raw"
        raw_root.mkdir(parents=True)

        subject_config = SubjectConfig(
            subject_id="subject 001",  # Invalid: contains space
            species="Mus musculus",
            sex="M",
        )

        success = add_subject(
            experiment_root=root,
            subject_config=subject_config,
            interactive=False,
        )

        assert success is False

    def test_add_subject_without_experiment(self, tmp_path):
        """Test that add_subject fails if experiment not initialized."""
        root = tmp_path / "nonexistent"

        subject_config = SubjectConfig(
            subject_id="subject-001",
            species="Mus musculus",
            sex="M",
        )

        success = add_subject(
            experiment_root=root,
            subject_config=subject_config,
            interactive=False,
        )

        assert success is False


class TestSessionManagement:
    """Tests for session management."""

    def test_add_session_creates_structure(self, tmp_path):
        """Test that add_session creates correct structure."""
        root = tmp_path / "experiment"
        subject_dir = root / "data" / "raw" / "subject-001"
        subject_dir.mkdir(parents=True)

        session_config = SessionConfig(
            session_id="session-001",
            session_date="2024-01-15",
            session_description="Test session",
            experimenter="Alice",
        )

        success = add_session(
            experiment_root=root,
            subject_id="subject-001",
            session_config=session_config,
            create_subdirs=True,
            interactive=False,
        )

        assert success is True
        session_dir = subject_dir / "session-001"
        assert session_dir.exists()
        assert (session_dir / "session.toml").exists()
        assert (session_dir / "Video").exists()
        assert (session_dir / "TTLs").exists()
        assert (session_dir / "Bpod").exists()

    def test_add_session_without_subdirs(self, tmp_path):
        """Test that add_session respects no-subdirs flag."""
        root = tmp_path / "experiment"
        subject_dir = root / "data" / "raw" / "subject-001"
        subject_dir.mkdir(parents=True)

        session_config = SessionConfig(
            session_id="session-001",
            session_date="2024-01-15",
            session_description="Test session",
            experimenter="Alice",
        )

        success = add_session(
            experiment_root=root,
            subject_id="subject-001",
            session_config=session_config,
            create_subdirs=False,
            interactive=False,
        )

        assert success is True
        session_dir = subject_dir / "session-001"
        assert session_dir.exists()
        assert (session_dir / "session.toml").exists()
        assert not (session_dir / "Video").exists()
        assert not (session_dir / "TTLs").exists()
        assert not (session_dir / "Bpod").exists()

    def test_add_session_invalid_id(self, tmp_path):
        """Test that add_session rejects invalid session ID."""
        root = tmp_path / "experiment"
        subject_dir = root / "data" / "raw" / "subject-001"
        subject_dir.mkdir(parents=True)

        session_config = SessionConfig(
            session_id="session 001",  # Invalid: contains space
            session_date="2024-01-15",
            session_description="Test session",
            experimenter="Alice",
        )

        success = add_session(
            experiment_root=root,
            subject_id="subject-001",
            session_config=session_config,
            interactive=False,
        )

        assert success is False

    def test_add_session_without_subject(self, tmp_path):
        """Test that add_session fails if subject doesn't exist."""
        root = tmp_path / "experiment"
        (root / "data" / "raw").mkdir(parents=True)

        session_config = SessionConfig(
            session_id="session-001",
            session_date="2024-01-15",
            session_description="Test session",
            experimenter="Alice",
        )

        success = add_session(
            experiment_root=root,
            subject_id="nonexistent",
            session_config=session_config,
            interactive=False,
        )

        assert success is False


class TestFilePatternDetection:
    """Tests for file pattern detection."""

    def test_detect_video_files(self, tmp_path):
        """Test detection of video files."""
        (tmp_path / "camera_0.avi").touch()
        (tmp_path / "camera_1.mp4").touch()

        patterns = detect_file_patterns(tmp_path)

        assert "camera_0" in patterns
        assert "camera_1" in patterns
        assert patterns["camera_0"].category == "video"
        assert len(patterns["camera_0"].files) == 1

    def test_detect_ttl_files(self, tmp_path):
        """Test detection of TTL files."""
        (tmp_path / "ttl_camera.txt").touch()
        (tmp_path / "pulse_sync.txt").touch()

        patterns = detect_file_patterns(tmp_path)

        assert "ttl_camera" in patterns
        assert patterns["ttl_camera"].category == "ttl"

    def test_detect_bpod_files(self, tmp_path):
        """Test detection of Bpod files."""
        (tmp_path / "session_data.mat").touch()

        patterns = detect_file_patterns(tmp_path)

        assert "bpod" in patterns
        assert patterns["bpod"].category == "bpod"

    def test_detect_mixed_files(self, tmp_path):
        """Test detection of mixed file types."""
        (tmp_path / "camera_0.avi").touch()
        (tmp_path / "ttl_camera.txt").touch()
        (tmp_path / "data.mat").touch()
        (tmp_path / "notes.txt").touch()  # Should go to "other"

        patterns = detect_file_patterns(tmp_path)

        assert "camera_0" in patterns
        assert "ttl_camera" in patterns
        assert "bpod" in patterns
        # Note: notes.txt won't trigger TTL detection (no ttl/pulse/sync in name)


class TestValidation:
    """Tests for structure validation."""

    def test_validate_minimal_structure(self, tmp_path):
        """Test validation of minimal valid structure."""
        root = tmp_path / "experiment"
        (root / "data" / "raw").mkdir(parents=True)
        (root / "data" / "interim").mkdir(parents=True)
        (root / "data" / "processed").mkdir(parents=True)

        result = validate_experiment_structure(root)

        # Should pass basic checks but have warnings about missing metadata
        assert len(result.errors) == 0
        assert len(result.warnings) >= 1  # Missing root metadata

    def test_validate_missing_folders(self, tmp_path):
        """Test validation detects missing required folders."""
        root = tmp_path / "experiment"
        root.mkdir()

        result = validate_experiment_structure(root)

        assert not result.valid
        assert len(result.errors) >= 3  # Missing raw, interim, processed

    def test_validate_with_sessions(self, tmp_path):
        """Test validation with complete session structure."""
        root = tmp_path / "experiment"
        (root / "data" / "raw").mkdir(parents=True)
        (root / "data" / "interim").mkdir(parents=True)
        (root / "data" / "processed").mkdir(parents=True)

        # Add subject
        subject_dir = root / "data" / "raw" / "subject-001"
        subject_dir.mkdir()

        # Add session with metadata
        session_dir = subject_dir / "session-001"
        session_dir.mkdir()

        import tomli_w

        session_data = {
            "session_description": "Test session",
            "identifier": "subject-001-session-001",
            "session_start_time": "2024-01-15T14:30:00Z",
        }

        with open(session_dir / "session.toml", "wb") as f:
            tomli_w.dump(session_data, f)

        result = validate_experiment_structure(root)

        # Should have no errors for session structure
        session_errors = [e for e in result.errors if "session-001" in e]
        assert len(session_errors) == 0
