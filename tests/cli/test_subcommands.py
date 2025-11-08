"""CLI subcommand tests.

Validates all CLI commands as specified in requirements CLI contract.
Tests command invocation, argument handling, and exit codes.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

pytestmark = pytest.mark.cli


class TestIngestCommand:
    """Test ingest CLI subcommand (FR-1, Requirements CLI contract)."""

    def test_Should_CreateManifestWithAbsolutePaths_When_IngestRuns_FR1_CLI(self, synthetic_session: Path, temp_workdir: Path, mock_config_toml: Path):
        """Ingest SHALL build manifest with absolute paths and metadata.

        Requirements: FR-1, CLI contract - ingest subcommand
        Issue: Design phase - Ingest CLI validation
        """
        # Arrange
        output_path = temp_workdir / "manifest.json"

        # Act
        result = subprocess.run(
            [
                "w2t-bkin",
                "ingest",
                str(synthetic_session),
                "--config",
                str(mock_config_toml),
                "--output",
                str(output_path),
            ],
            capture_output=True,
            text=True,
        )

        # Assert
        assert result.returncode == 0, f"Ingest command failed:\n{result.stderr}"
        assert output_path.exists(), "Manifest file should be created"

        manifest = json.loads(output_path.read_text())
        assert all(Path(v["path"]).is_absolute() for v in manifest["videos"]), "All paths must be absolute"

    def test_Should_FailWithNonZeroExit_When_RequiredFilesMissing_CLI(self, temp_workdir: Path, mock_config_toml: Path):
        """Ingest SHALL fail if expected files are missing.

        Requirements: CLI contract - ingest error handling
        Issue: Design phase - Error handling validation
        """
        # Arrange
        non_existent_session = temp_workdir / "does_not_exist"
        output_path = temp_workdir / "manifest.json"

        # Act
        result = subprocess.run(
            [
                "w2t-bkin",
                "ingest",
                str(non_existent_session),
                "--config",
                str(mock_config_toml),
                "--output",
                str(output_path),
            ],
            capture_output=True,
            text=True,
        )

        # Assert
        assert result.returncode != 0, "Should exit with non-zero code when files missing"
        assert "missing" in result.stderr.lower() or "not found" in result.stderr.lower()

    def test_Should_PrintUsage_When_NoArgumentsProvided_CLI(self):
        """Ingest SHALL print usage information when called without arguments.

        Requirements: CLI contract - user experience
        Issue: Design phase - CLI usability
        """
        # Act
        result = subprocess.run(
            ["w2t-bkin", "ingest", "--help"],
            capture_output=True,
            text=True,
        )

        # Assert
        assert result.returncode == 0, "Help should succeed"
        assert "ingest" in result.stdout.lower(), "Help should describe ingest command"
        assert "session" in result.stdout.lower(), "Help should mention session parameter"


class TestSyncCommand:
    """Test sync CLI subcommand (FR-2, FR-3, Requirements CLI contract)."""

    def test_Should_ProduceTimestampsAndSummary_When_SyncRuns_FR2_FR3_CLI(self, synthetic_session: Path, temp_workdir: Path, mock_config_toml: Path):
        """Sync SHALL produce per-camera timestamps and drift/drop summaries.

        Requirements: FR-2, FR-3, CLI contract - sync subcommand
        Issue: Design phase - Sync CLI validation
        """
        # Arrange
        # First run ingest
        manifest_path = temp_workdir / "manifest.json"
        subprocess.run(
            [
                "w2t-bkin",
                "ingest",
                str(synthetic_session),
                "--config",
                str(mock_config_toml),
                "--output",
                str(manifest_path),
            ],
            check=True,
        )

        sync_output_dir = temp_workdir / "sync"

        # Act
        result = subprocess.run(
            ["w2t-bkin", "sync", str(manifest_path), "--output", str(sync_output_dir)],
            capture_output=True,
            text=True,
        )

        # Assert
        assert result.returncode == 0, f"Sync command failed:\n{result.stderr}"
        assert sync_output_dir.exists(), "Sync output directory should be created"

        timestamp_files = list(sync_output_dir.glob("timestamps_cam*.csv"))
        assert len(timestamp_files) == 5, "Should produce 5 timestamp files"

        sync_summary = sync_output_dir / "sync_summary.json"
        assert sync_summary.exists(), "Sync summary should be created"

    def test_Should_ExitNonZero_When_DriftExceedsThreshold_CLI(self, synthetic_session: Path, temp_workdir: Path, mock_config_toml: Path):
        """Sync SHALL exit non-zero on severe drift mismatch.

        Requirements: CLI contract - sync error handling
        Issue: Design phase - Sync failure handling
        """
        # Arrange
        manifest_path = temp_workdir / "manifest.json"
        subprocess.run(
            [
                "w2t-bkin",
                "ingest",
                str(synthetic_session),
                "--config",
                str(mock_config_toml),
                "--output",
                str(manifest_path),
            ],
            check=True,
        )

        # Create strict config
        import toml

        config = toml.load(mock_config_toml)
        config["sync"]["tolerance_ms"] = 0.001
        strict_config = temp_workdir / "strict_config.toml"
        strict_config.write_text(toml.dumps(config))

        sync_output_dir = temp_workdir / "sync"

        # Act
        result = subprocess.run(
            [
                "w2t-bkin",
                "sync",
                str(manifest_path),
                "--config",
                str(strict_config),
                "--output",
                str(sync_output_dir),
            ],
            capture_output=True,
            text=True,
        )

        # Assert
        assert result.returncode != 0, "Should exit non-zero when drift exceeds threshold"


class TestTranscodeCommand:
    """Test transcode CLI subcommand (FR-4, Requirements CLI contract)."""

    def test_Should_TranscodeVideos_When_EnabledInConfig_FR4_CLI(self, synthetic_session: Path, temp_workdir: Path, mock_config_toml: Path):
        """Transcode SHALL transcode videos when enabled.

        Requirements: FR-4, CLI contract - transcode subcommand
        Issue: Design phase - Transcode CLI validation
        """
        # Arrange
        import toml

        config = toml.load(mock_config_toml)
        config["video"] = {"transcode": {"enabled": True, "codec": "h264", "crf": 23}}
        transcode_config = temp_workdir / "transcode_config.toml"
        transcode_config.write_text(toml.dumps(config))

        manifest_path = temp_workdir / "manifest.json"
        subprocess.run(
            [
                "w2t-bkin",
                "ingest",
                str(synthetic_session),
                "--config",
                str(transcode_config),
                "--output",
                str(manifest_path),
            ],
            check=True,
        )

        mezzanine_dir = temp_workdir / "mezzanine"

        # Act
        result = subprocess.run(
            [
                "w2t-bkin",
                "transcode",
                str(manifest_path),
                "--config",
                str(transcode_config),
                "--output",
                str(mezzanine_dir),
            ],
            capture_output=True,
            text=True,
        )

        # Assert
        assert result.returncode == 0, f"Transcode command failed:\n{result.stderr}"
        # Should produce transcoded videos
        assert mezzanine_dir.exists(), "Mezzanine directory should be created"

    def test_Should_NoOp_When_TranscodingDisabled_FR4_CLI(self, synthetic_session: Path, temp_workdir: Path, mock_config_toml: Path):
        """Transcode SHALL no-op with clear logging when disabled.

        Requirements: FR-4, CLI contract - transcode optional behavior
        Issue: Design phase - Transcode skip validation
        """
        # Arrange
        import toml

        config = toml.load(mock_config_toml)
        config["video"] = {"transcode": {"enabled": False}}
        no_transcode_config = temp_workdir / "no_transcode_config.toml"
        no_transcode_config.write_text(toml.dumps(config))

        manifest_path = temp_workdir / "manifest.json"
        subprocess.run(
            [
                "w2t-bkin",
                "ingest",
                str(synthetic_session),
                "--config",
                str(no_transcode_config),
                "--output",
                str(manifest_path),
            ],
            check=True,
        )

        mezzanine_dir = temp_workdir / "mezzanine"

        # Act
        result = subprocess.run(
            [
                "w2t-bkin",
                "transcode",
                str(manifest_path),
                "--config",
                str(no_transcode_config),
                "--output",
                str(mezzanine_dir),
            ],
            capture_output=True,
            text=True,
        )

        # Assert
        assert result.returncode == 0, "Should succeed even when disabled"
        assert "skipped" in result.stdout.lower() or "disabled" in result.stdout.lower()


class TestPoseCommand:
    """Test pose CLI subcommand (FR-5, Requirements CLI contract)."""

    def test_Should_HarmonizePoseData_When_DLCSupplied_FR5_CLI(self, synthetic_session: Path, temp_workdir: Path, mock_config_toml: Path):
        """Pose SHALL import and harmonize DLC/SLEAP outputs.

        Requirements: FR-5, CLI contract - pose subcommand
        Issue: Design phase - Pose CLI validation
        """
        # Arrange
        dlc_output = synthetic_session / "pose_dlc.h5"
        # Mock DLC file would be created here

        pose_output_dir = temp_workdir / "pose"

        # Act
        result = subprocess.run(
            [
                "w2t-bkin",
                "pose",
                str(dlc_output),
                "--format",
                "dlc",
                "--output",
                str(pose_output_dir),
            ],
            capture_output=True,
            text=True,
        )

        # Assert
        assert result.returncode == 0, f"Pose command failed:\n{result.stderr}"
        assert pose_output_dir.exists(), "Pose output directory should be created"

        harmonized_files = list(pose_output_dir.glob("*.parquet"))
        assert len(harmonized_files) > 0, "Should produce harmonized pose table"


class TestFacemapCommand:
    """Test facemap CLI subcommand (FR-6, Requirements CLI contract)."""

    def test_Should_ImportFacialMetrics_When_FacemapEnabled_FR6_CLI(self, synthetic_session: Path, temp_workdir: Path, mock_config_toml: Path):
        """Facemap SHALL import or compute facial metrics.

        Requirements: FR-6, CLI contract - facemap subcommand
        Issue: Design phase - Facemap CLI validation
        """
        # Arrange
        facemap_output = synthetic_session / "facemap_output.npy"
        # Mock Facemap file would be created here

        facemap_output_dir = temp_workdir / "facemap"

        # Act
        result = subprocess.run(
            [
                "w2t-bkin",
                "facemap",
                str(facemap_output),
                "--output",
                str(facemap_output_dir),
            ],
            capture_output=True,
            text=True,
        )

        # Assert
        assert result.returncode == 0, f"Facemap command failed:\n{result.stderr}"
        assert facemap_output_dir.exists(), "Facemap output directory should be created"


class TestToNWBCommand:
    """Test to-nwb CLI subcommand (FR-7, Requirements CLI contract)."""

    def test_Should_AssembleNWBWithAllData_When_AllStagesComplete_FR7_CLI(self, synthetic_session: Path, temp_workdir: Path, mock_config_toml: Path):
        """To-NWB SHALL assemble NWB with all available data.

        Requirements: FR-7, CLI contract - to-nwb subcommand
        Issue: Design phase - NWB assembly CLI validation
        """
        # Arrange
        # Run prerequisite stages
        manifest_path = temp_workdir / "manifest.json"
        subprocess.run(
            [
                "w2t-bkin",
                "ingest",
                str(synthetic_session),
                "--config",
                str(mock_config_toml),
                "--output",
                str(manifest_path),
            ],
            check=True,
        )

        sync_output_dir = temp_workdir / "sync"
        subprocess.run(
            ["w2t-bkin", "sync", str(manifest_path), "--output", str(sync_output_dir)],
            check=True,
        )

        nwb_output_dir = temp_workdir / "nwb"

        # Act
        result = subprocess.run(
            [
                "w2t-bkin",
                "to-nwb",
                str(manifest_path),
                "--timestamps",
                str(sync_output_dir),
                "--output",
                str(nwb_output_dir),
            ],
            capture_output=True,
            text=True,
        )

        # Assert
        assert result.returncode == 0, f"To-NWB command failed:\n{result.stderr}"
        assert nwb_output_dir.exists(), "NWB output directory should be created"

        nwb_files = list(nwb_output_dir.glob("*.nwb"))
        assert len(nwb_files) == 1, "Should produce one NWB file"

    def test_Should_WarnWhenOptionalDataMissing_When_AssemblingNWB_FR7_CLI(self, synthetic_session: Path, temp_workdir: Path, mock_config_toml: Path):
        """To-NWB SHALL warn when optional data are missing.

        Requirements: FR-7, CLI contract - to-nwb optional data handling
        Issue: Design phase - NWB warning validation
        """
        # Arrange
        manifest_path = temp_workdir / "manifest.json"
        subprocess.run(
            [
                "w2t-bkin",
                "ingest",
                str(synthetic_session),
                "--config",
                str(mock_config_toml),
                "--output",
                str(manifest_path),
            ],
            check=True,
        )

        sync_output_dir = temp_workdir / "sync"
        subprocess.run(
            ["w2t-bkin", "sync", str(manifest_path), "--output", str(sync_output_dir)],
            check=True,
        )

        nwb_output_dir = temp_workdir / "nwb"

        # Act - No pose/facemap provided
        result = subprocess.run(
            [
                "w2t-bkin",
                "to-nwb",
                str(manifest_path),
                "--timestamps",
                str(sync_output_dir),
                "--output",
                str(nwb_output_dir),
            ],
            capture_output=True,
            text=True,
        )

        # Assert
        assert result.returncode == 0, "Should succeed even without optional data"
        assert "warn" in result.stdout.lower() or "missing" in result.stdout.lower()


class TestValidateCommand:
    """Test validate CLI subcommand (FR-9, Requirements CLI contract)."""

    def test_Should_RunNWBInspector_When_ValidateExecuted_FR9_CLI(self, synthetic_session: Path, temp_workdir: Path, mock_config_toml: Path):
        """Validate SHALL run nwbinspector and save report.

        Requirements: FR-9, CLI contract - validate subcommand
        Issue: Design phase - Validation CLI execution
        """
        # Arrange
        # Create NWB file first
        manifest_path = temp_workdir / "manifest.json"
        subprocess.run(
            [
                "w2t-bkin",
                "ingest",
                str(synthetic_session),
                "--config",
                str(mock_config_toml),
                "--output",
                str(manifest_path),
            ],
            check=True,
        )

        sync_output_dir = temp_workdir / "sync"
        subprocess.run(
            ["w2t-bkin", "sync", str(manifest_path), "--output", str(sync_output_dir)],
            check=True,
        )

        nwb_output_dir = temp_workdir / "nwb"
        subprocess.run(
            [
                "w2t-bkin",
                "to-nwb",
                str(manifest_path),
                "--timestamps",
                str(sync_output_dir),
                "--output",
                str(nwb_output_dir),
            ],
            check=True,
        )

        nwb_file = list(nwb_output_dir.glob("*.nwb"))[0]
        validation_output = temp_workdir / "validation"

        # Act
        result = subprocess.run(
            ["w2t-bkin", "validate", str(nwb_file), "--output", str(validation_output)],
            capture_output=True,
            text=True,
        )

        # Assert
        assert result.returncode == 0, f"Validate command failed:\n{result.stderr}"
        report_file = validation_output / "nwbinspector_report.json"
        assert report_file.exists(), "Validation report should be created"


class TestReportCommand:
    """Test report CLI subcommand (FR-8, Requirements CLI contract)."""

    def test_Should_GenerateQCHTML_When_ReportExecuted_FR8_CLI(self, synthetic_session: Path, temp_workdir: Path, mock_config_toml: Path):
        """Report SHALL generate QC HTML summary.

        Requirements: FR-8, CLI contract - report subcommand
        Issue: Design phase - QC report CLI validation
        """
        # Arrange
        # Run full pipeline first
        manifest_path = temp_workdir / "manifest.json"
        subprocess.run(
            [
                "w2t-bkin",
                "ingest",
                str(synthetic_session),
                "--config",
                str(mock_config_toml),
                "--output",
                str(manifest_path),
            ],
            check=True,
        )

        sync_output_dir = temp_workdir / "sync"
        subprocess.run(
            ["w2t-bkin", "sync", str(manifest_path), "--output", str(sync_output_dir)],
            check=True,
        )

        nwb_output_dir = temp_workdir / "nwb"
        subprocess.run(
            [
                "w2t-bkin",
                "to-nwb",
                str(manifest_path),
                "--timestamps",
                str(sync_output_dir),
                "--output",
                str(nwb_output_dir),
            ],
            check=True,
        )

        qc_output_dir = temp_workdir / "qc"

        # Act
        result = subprocess.run(
            [
                "w2t-bkin",
                "report",
                "--sync-summary",
                str(sync_output_dir / "sync_summary.json"),
                "--nwb",
                str(list(nwb_output_dir.glob("*.nwb"))[0]),
                "--output",
                str(qc_output_dir),
            ],
            capture_output=True,
            text=True,
        )

        # Assert
        assert result.returncode == 0, f"Report command failed:\n{result.stderr}"
        assert qc_output_dir.exists(), "QC output directory should be created"

        index_html = qc_output_dir / "index.html"
        assert index_html.exists(), "index.html should be created"


class TestEnvironmentOverrides:
    """Test environment variable configuration overrides (NFR-10)."""

    def test_Should_ApplyEnvOverrides_When_EnvironmentVariablesSet_NFR10(
        self, synthetic_session: Path, temp_workdir: Path, mock_config_toml: Path, monkeypatch
    ):
        """CLI SHALL support environment overrides via pydantic-settings.

        Requirements: NFR-10 (Type safety and configurability)
        Issue: Design phase - Environment override validation
        """
        # Arrange
        monkeypatch.setenv("W2T_BKIN_SYNC_TOLERANCE_MS", "5.0")
        monkeypatch.setenv("W2T_BKIN_LOGGING_LEVEL", "DEBUG")

        manifest_path = temp_workdir / "manifest.json"
        subprocess.run(
            [
                "w2t-bkin",
                "ingest",
                str(synthetic_session),
                "--config",
                str(mock_config_toml),
                "--output",
                str(manifest_path),
            ],
            check=True,
        )

        sync_output_dir = temp_workdir / "sync"

        # Act
        result = subprocess.run(
            ["w2t-bkin", "sync", str(manifest_path), "--output", str(sync_output_dir)],
            capture_output=True,
            text=True,
            env={**subprocess.os.environ, "W2T_BKIN_SYNC_TOLERANCE_MS": "5.0"},
        )

        # Assert
        assert result.returncode == 0, "Should apply env overrides"
        # Verify tolerance was applied (would be in summary or logs)
        sync_summary = sync_output_dir / "sync_summary.json"
        if sync_summary.exists():
            summary = json.loads(sync_summary.read_text())
            # Should reflect overridden tolerance
            assert "config" in summary or "tolerance" in str(summary)
