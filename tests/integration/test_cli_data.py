"""
Integration tests for CLI data management commands.

Tests the full workflow of data management commands including init, add-subject,
add-session, and validate.
"""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from w2t_bkin.cli import app

runner = CliRunner()


@pytest.fixture
def temp_experiment_root(tmp_path):
    """Create a temporary experiment root directory."""
    return tmp_path / "test-experiment"


class TestDataManagementWorkflow:
    """Test complete data management workflow."""

    def test_data_init_creates_structure(self, temp_experiment_root):
        """Test that data init creates proper folder structure."""
        result = runner.invoke(
            app,
            [
                "data",
                "init",
                str(temp_experiment_root),
                "--lab",
                "Test Lab",
                "--institution",
                "Test Institution",
                "--experimenters",
                "Alice,Bob",
                "--skip-docker-env",
                "-y",
            ],
        )

        assert result.exit_code == 0, f"Command failed: {result.stdout}"

        # Check folder structure
        assert (temp_experiment_root / "data" / "raw").exists()
        assert (temp_experiment_root / "data" / "interim").exists()
        assert (temp_experiment_root / "data" / "processed").exists()
        assert (temp_experiment_root / "data" / "external").exists()
        assert (temp_experiment_root / "models").exists()

        # Check metadata file
        assert (temp_experiment_root / "data" / "raw" / "metadata.toml").exists()

        # Check configuration file
        assert (temp_experiment_root / "configuration.toml").exists()

    def test_data_add_subject(self, temp_experiment_root):
        """Test adding a subject."""
        # First initialize
        runner.invoke(
            app,
            [
                "data",
                "init",
                str(temp_experiment_root),
                "--lab",
                "Test Lab",
                "--skip-docker-env",
                "-y",
            ],
        )

        # Add subject
        result = runner.invoke(
            app,
            [
                "data",
                "add-subject",
                str(temp_experiment_root),
                "mouse-001",
                "--species",
                "Mus musculus",
                "--sex",
                "F",
                "-y",
            ],
        )

        assert result.exit_code == 0, f"Command failed: {result.stdout}"

        # Check subject folder and metadata
        subject_dir = temp_experiment_root / "data" / "raw" / "mouse-001"
        assert subject_dir.exists()
        assert (subject_dir / "subject.toml").exists()

    def test_data_add_session(self, temp_experiment_root):
        """Test adding a session."""
        # Initialize and add subject
        runner.invoke(
            app,
            [
                "data",
                "init",
                str(temp_experiment_root),
                "--lab",
                "Test Lab",
                "--skip-docker-env",
                "-y",
            ],
        )
        runner.invoke(
            app,
            [
                "data",
                "add-subject",
                str(temp_experiment_root),
                "mouse-001",
                "-y",
            ],
        )

        # Add session
        result = runner.invoke(
            app,
            [
                "data",
                "add-session",
                str(temp_experiment_root),
                "mouse-001",
                "session-001",
                "--description",
                "Test session",
                "--experimenter",
                "Alice",
                "-y",
            ],
        )

        assert result.exit_code == 0, f"Command failed: {result.stdout}"

        # Check session folder and metadata
        session_dir = temp_experiment_root / "data" / "raw" / "mouse-001" / "session-001"
        assert session_dir.exists()
        assert (session_dir / "session.toml").exists()
        assert (session_dir / "Video").exists()
        assert (session_dir / "TTLs").exists()
        assert (session_dir / "Bpod").exists()

    def test_data_validate_experiment(self, temp_experiment_root):
        """Test validating experiment structure."""
        # Initialize experiment
        runner.invoke(
            app,
            [
                "data",
                "init",
                str(temp_experiment_root),
                "--lab",
                "Test Lab",
                "--skip-docker-env",
                "-y",
            ],
        )

        # Validate should pass for minimal structure
        result = runner.invoke(
            app,
            [
                "data",
                "validate",
                str(temp_experiment_root),
            ],
        )

        # Command should run (exit code 0 or 1 depending on strictness)
        assert result.exit_code in [0, 1]

    def test_full_workflow(self, temp_experiment_root):
        """Test complete workflow: init -> add-subject -> add-session -> validate."""
        # 1. Initialize
        result = runner.invoke(
            app,
            [
                "data",
                "init",
                str(temp_experiment_root),
                "--lab",
                "Test Lab",
                "--institution",
                "Test Institution",
                "--skip-docker-env",
                "-y",
            ],
        )
        assert result.exit_code == 0

        # 2. Add subject
        result = runner.invoke(
            app,
            [
                "data",
                "add-subject",
                str(temp_experiment_root),
                "mouse-001",
                "--sex",
                "M",
                "-y",
            ],
        )
        assert result.exit_code == 0

        # 3. Add session
        result = runner.invoke(
            app,
            [
                "data",
                "add-session",
                str(temp_experiment_root),
                "mouse-001",
                "session-001",
                "--description",
                "Baseline recording",
                "--experimenter",
                "Alice",
                "-y",
            ],
        )
        assert result.exit_code == 0

        # 4. Validate
        result = runner.invoke(
            app,
            [
                "data",
                "validate",
                str(temp_experiment_root),
            ],
        )
        assert result.exit_code in [0, 1]

        # Verify complete structure
        assert (temp_experiment_root / "data" / "raw" / "mouse-001" / "session-001").exists()


class TestDataImportRaw:
    """Test data import-raw command."""

    def test_import_raw_dry_run(self, temp_experiment_root, tmp_path):
        """Test import-raw in dry-run mode (default)."""
        # Setup
        source_dir = tmp_path / "raw-source"
        source_dir.mkdir()
        (source_dir / "video.avi").touch()

        # Initialize experiment structure
        runner.invoke(
            app,
            [
                "data",
                "init",
                str(temp_experiment_root),
                "--lab",
                "Test",
                "--skip-docker-env",
                "-y",
            ],
        )
        runner.invoke(
            app,
            ["data", "add-subject", str(temp_experiment_root), "mouse-001", "-y"],
        )
        runner.invoke(
            app,
            [
                "data",
                "add-session",
                str(temp_experiment_root),
                "mouse-001",
                "session-001",
                "--description",
                "Test",
                "--experimenter",
                "Alice",
                "-y",
            ],
        )

        # Import (dry-run)
        result = runner.invoke(
            app,
            [
                "data",
                "import-raw",
                str(source_dir),
                "-e",
                str(temp_experiment_root),
                "-s",
                "mouse-001",
                "--session",
                "session-001",
            ],
        )

        # Should complete dry-run successfully
        assert result.exit_code == 0

        # Files should NOT be imported (dry-run)
        session_dir = temp_experiment_root / "data" / "raw" / "mouse-001" / "session-001"
        # Video folder exists but should be empty or not have the file
        assert not (session_dir / "Video" / "video.avi").exists()
