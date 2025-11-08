"""End-to-end integration tests for multi-stage pipeline execution.

These tests validate that stages can be composed correctly and produce
expected artifacts when chained together.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


class TestIngestToSyncFlow:
    """Test ingest → sync integration flow (FR-1, FR-2)."""

    def test_Should_ProduceValidManifest_When_IngestRunsOnSyntheticSession_FR1(self, synthetic_session: Path, temp_workdir: Path, mock_config_toml: Path):
        """THE SYSTEM SHALL ingest five camera video files and discover sync files.

        Requirements: FR-1
        Issue: Design phase - Acceptance Criterion A1
        """
        # Arrange
        from w2t_bkin.ingest import build_manifest

        # Act
        manifest_path = build_manifest(
            session_dir=synthetic_session,
            config_path=mock_config_toml,
            output_dir=temp_workdir,
        )

        # Assert
        assert manifest_path.exists(), "Manifest file should be created"
        manifest = json.loads(manifest_path.read_text())
        assert manifest["session_id"] == "session_synthetic_001"
        assert len(manifest["videos"]) == 5, "Should discover 5 camera videos"
        assert len(manifest["sync"]) > 0, "Should discover sync files"
        assert all(Path(v["path"]).is_absolute() for v in manifest["videos"]), "All paths must be absolute"

    def test_Should_GenerateTimestampsPerCamera_When_SyncConsumesManifest_FR2(self, synthetic_session: Path, temp_workdir: Path, mock_config_toml: Path):
        """THE SYSTEM SHALL compute per-frame timestamps for each camera.

        Requirements: FR-2
        Issue: Design phase - Acceptance Criterion A1
        """
        # Arrange
        from w2t_bkin.ingest import build_manifest
        from w2t_bkin.sync import compute_timestamps

        manifest_path = build_manifest(synthetic_session, mock_config_toml, temp_workdir)

        # Act
        timestamps_dir, sync_summary = compute_timestamps(
            manifest_path=manifest_path,
            output_dir=temp_workdir / "sync",
        )

        # Assert
        assert timestamps_dir.exists(), "Timestamps directory should be created"
        timestamp_files = list(timestamps_dir.glob("timestamps_cam*.csv"))
        assert len(timestamp_files) == 5, "Should produce timestamps for 5 cameras"

        # Verify CSV structure (Design §3.2)
        first_ts = timestamp_files[0].read_text().splitlines()
        header = first_ts[0]
        assert header == "frame_index,timestamp", "CSV must have correct headers"

    def test_Should_DetectDriftAndDrops_When_TimestampComputationCompletes_FR3(self, synthetic_session: Path, temp_workdir: Path, mock_config_toml: Path):
        """THE SYSTEM SHALL detect dropped frames, duplicates, and inter-camera drift.

        Requirements: FR-3
        Issue: Design phase - Drift detection validation
        """
        # Arrange
        from w2t_bkin.ingest import build_manifest
        from w2t_bkin.sync import compute_timestamps

        manifest_path = build_manifest(synthetic_session, mock_config_toml, temp_workdir)

        # Act
        _, sync_summary_path = compute_timestamps(manifest_path, temp_workdir / "sync")

        # Assert
        assert sync_summary_path.exists(), "Sync summary JSON should be created"
        summary = json.loads(sync_summary_path.read_text())
        assert "drift_stats" in summary, "Summary must include drift statistics"
        assert "dropped_frames" in summary, "Summary must include dropped frame count"
        assert "duplicates" in summary, "Summary must include duplicate frame count"


class TestFullPipelineFlow:
    """Test complete pipeline execution (Acceptance Criterion A1)."""

    def test_Should_CompleteWithoutErrors_When_RunningFullMinimalPipeline_A1(self, synthetic_session: Path, temp_workdir: Path, mock_config_toml: Path):
        """For a sample session, ingest → sync → to-nwb → validate → report completes without errors.

        Requirements: Acceptance Criterion A1
        Issue: Design phase - End-to-end validation
        """
        # Arrange
        from w2t_bkin.cli import app

        # Act - Run full pipeline via CLI
        result = app(
            [
                "ingest",
                str(synthetic_session),
                "--config",
                str(mock_config_toml),
                "--output",
                str(temp_workdir),
            ]
        )

        # Assert
        assert result == 0, "Ingest should complete successfully"

        # Validate artifacts exist
        manifest_path = temp_workdir / "manifest.json"
        assert manifest_path.exists(), "Manifest should be created"

        # Continue with sync
        from w2t_bkin.cli import app as sync_app

        result = sync_app(["sync", str(manifest_path), "--output", str(temp_workdir)])
        assert result == 0, "Sync should complete successfully"

    def test_Should_ProduceValidNWB_When_AssemblingAllStageOutputs_FR7(self, synthetic_session: Path, temp_workdir: Path, mock_config_toml: Path):
        """THE SYSTEM SHALL export one NWB file per session with required structure.

        Requirements: FR-7
        Issue: Design phase - NWB structure validation
        """
        # Arrange
        from w2t_bkin.ingest import build_manifest
        from w2t_bkin.nwb import assemble_nwb
        from w2t_bkin.sync import compute_timestamps

        manifest_path = build_manifest(synthetic_session, mock_config_toml, temp_workdir)
        timestamps_dir, _ = compute_timestamps(manifest_path, temp_workdir / "sync")

        # Act
        nwb_path = assemble_nwb(
            manifest_path=manifest_path,
            timestamps_dir=timestamps_dir,
            output_dir=temp_workdir / "processed",
        )

        # Assert
        assert nwb_path.exists(), "NWB file should be created"
        assert nwb_path.suffix == ".nwb", "Output should have .nwb extension"

        # Validate NWB structure (requires pynwb)
        from pynwb import NWBHDF5IO

        with NWBHDF5IO(str(nwb_path), "r") as io:
            nwb_file = io.read()
            assert len(nwb_file.devices) == 5, "Should have 5 camera devices"
            assert len(nwb_file.acquisition) >= 5, "Should have at least 5 ImageSeries"

    def test_Should_PassNWBInspector_When_ValidatingOutput_FR9_A2(self, synthetic_session: Path, temp_workdir: Path, mock_config_toml: Path):
        """THE SYSTEM SHALL validate NWB output with nwbinspector.

        Requirements: FR-9, Acceptance Criterion A2
        Issue: Design phase - NWB compliance validation
        """
        # Arrange
        from w2t_bkin.ingest import build_manifest
        from w2t_bkin.nwb import assemble_nwb
        from w2t_bkin.sync import compute_timestamps
        from w2t_bkin.validation import validate_nwb

        manifest_path = build_manifest(synthetic_session, mock_config_toml, temp_workdir)
        timestamps_dir, _ = compute_timestamps(manifest_path, temp_workdir / "sync")
        nwb_path = assemble_nwb(manifest_path, timestamps_dir, temp_workdir / "processed")

        # Act
        validation_report_path = validate_nwb(nwb_path, output_dir=temp_workdir / "processed")

        # Assert
        assert validation_report_path.exists(), "Validation report should be created"
        report = json.loads(validation_report_path.read_text())
        critical_issues = [issue for issue in report.get("issues", []) if issue["severity"] == "CRITICAL"]
        assert len(critical_issues) == 0, "No critical issues should be present (A2)"

    def test_Should_GenerateQCReport_When_PipelineCompletes_FR8_A3(self, synthetic_session: Path, temp_workdir: Path, mock_config_toml: Path):
        """THE SYSTEM SHALL generate QC HTML report with drift plots and pose confidence.

        Requirements: FR-8, Acceptance Criterion A3
        Issue: Design phase - QC report generation
        """
        # Arrange
        from w2t_bkin.ingest import build_manifest
        from w2t_bkin.nwb import assemble_nwb
        from w2t_bkin.qc import generate_report
        from w2t_bkin.sync import compute_timestamps

        manifest_path = build_manifest(synthetic_session, mock_config_toml, temp_workdir)
        timestamps_dir, sync_summary = compute_timestamps(manifest_path, temp_workdir / "sync")
        nwb_path = assemble_nwb(manifest_path, timestamps_dir, temp_workdir / "processed")

        # Act
        qc_report_path = generate_report(
            sync_summary=sync_summary,
            nwb_path=nwb_path,
            output_dir=temp_workdir / "qc",
        )

        # Assert
        assert qc_report_path.exists(), "QC report HTML should be created"
        assert qc_report_path.name == "index.html", "Report should be named index.html"
        html_content = qc_report_path.read_text()
        assert "drift" in html_content.lower(), "Report must include drift plot (A3)"


class TestOptionalStagesIntegration:
    """Test pipeline with optional pose, facemap, and events stages (FR-5, FR-6, FR-11)."""

    def test_Should_HarmonizePoseData_When_DLCOrSLEAPSupplied_FR5(self, synthetic_session: Path, temp_workdir: Path, mock_config_toml: Path):
        """THE SYSTEM SHALL import and harmonize pose results to canonical skeleton.

        Requirements: FR-5
        Issue: Design phase - Pose harmonization
        """
        # Arrange
        from w2t_bkin.pose import harmonize_pose

        # Create mock DLC output
        dlc_output = synthetic_session / "pose_dlc.h5"
        # Mock DLC file creation would go here

        # Act
        harmonized_pose_path = harmonize_pose(
            pose_file=dlc_output,
            format="dlc",
            output_dir=temp_workdir / "pose",
        )

        # Assert
        assert harmonized_pose_path.exists(), "Harmonized pose table should be created"
        assert harmonized_pose_path.suffix == ".parquet", "Should use Parquet format (Design §3.3)"

        # Validate structure
        import pandas as pd

        pose_df = pd.read_parquet(harmonized_pose_path)
        required_columns = ["time", "keypoint", "x_px", "y_px", "confidence"]
        assert all(col in pose_df.columns for col in required_columns), "Must have required columns"

    def test_Should_ImportFacialMetrics_When_FacemapEnabled_FR6(self, synthetic_session: Path, temp_workdir: Path, mock_config_toml: Path):
        """THE SYSTEM SHALL import or compute facial metrics aligned to session timebase.

        Requirements: FR-6
        Issue: Design phase - Facemap integration
        """
        # Arrange
        from w2t_bkin.facemap import import_facemap_metrics

        # Create mock Facemap output
        facemap_output = synthetic_session / "facemap_output.npy"
        # Mock Facemap file creation would go here

        # Act
        metrics_path = import_facemap_metrics(
            facemap_file=facemap_output,
            output_dir=temp_workdir / "facemap",
        )

        # Assert
        assert metrics_path.exists(), "Facemap metrics table should be created"

        # Validate structure (Design §3.4)
        import pandas as pd

        metrics_df = pd.read_parquet(metrics_path)
        assert "time" in metrics_df.columns, "Must have time column"
        assert "pupil_area" in metrics_df.columns or "motion_energy" in metrics_df.columns, "Must have metric columns"

    def test_Should_ImportTrialsAndEvents_When_NDJSONLogsPresent_FR11(self, synthetic_session: Path, temp_workdir: Path, mock_config_toml: Path):
        """THE SYSTEM SHALL import NDJSON logs as Trials table and BehavioralEvents.

        Requirements: FR-11
        Issue: Design phase - Events integration
        """
        # Arrange
        from w2t_bkin.events import import_events

        # Use existing synthetic_session NDJSON logs
        training_log = synthetic_session / "behavior_training.ndjson"

        # Act
        trials_path, events_path = import_events(
            event_logs=[training_log],
            output_dir=temp_workdir / "events",
        )

        # Assert
        assert trials_path.exists(), "Trials table should be created"
        assert events_path.exists(), "Events table should be created"

        # Validate Trials structure (Design §3.5)
        import pandas as pd

        trials_df = pd.read_csv(trials_path)
        required_columns = ["trial_id", "start_time", "stop_time", "qc_flags"]
        assert all(col in trials_df.columns for col in required_columns), "Must have required trial columns"

    def test_Should_IncludeOptionalData_When_AssemblingNWBWithAllStages_FR7(self, synthetic_session: Path, temp_workdir: Path, mock_config_toml: Path):
        """THE SYSTEM SHALL include pose, facemap, and events in NWB when present.

        Requirements: FR-7 (complete)
        Issue: Design phase - Full NWB assembly
        """
        # Arrange
        from w2t_bkin.events import import_events
        from w2t_bkin.facemap import import_facemap_metrics
        from w2t_bkin.ingest import build_manifest
        from w2t_bkin.nwb import assemble_nwb
        from w2t_bkin.pose import harmonize_pose
        from w2t_bkin.sync import compute_timestamps

        # Run all stages (mocked data)
        manifest_path = build_manifest(synthetic_session, mock_config_toml, temp_workdir)
        timestamps_dir, _ = compute_timestamps(manifest_path, temp_workdir / "sync")
        # pose_path = harmonize_pose(...)  # Would be called if pose files exist
        # facemap_path = import_facemap_metrics(...)
        # trials_path, events_path = import_events(...)

        # Act
        nwb_path = assemble_nwb(
            manifest_path=manifest_path,
            timestamps_dir=timestamps_dir,
            pose_dir=temp_workdir / "pose",  # Optional
            facemap_dir=temp_workdir / "facemap",  # Optional
            events_dir=temp_workdir / "events",  # Optional
            output_dir=temp_workdir / "processed",
        )

        # Assert
        from pynwb import NWBHDF5IO

        with NWBHDF5IO(str(nwb_path), "r") as io:
            nwb_file = io.read()
            # Should warn but not fail when optional data missing
            assert nwb_file is not None, "NWB should assemble even without optional data"


class TestIdempotenceAndErrorHandling:
    """Test NFR-2 (idempotence) and error handling requirements."""

    def test_Should_ProduceSameOutput_When_RerunningStageWithoutChanges_NFR2(self, synthetic_session: Path, temp_workdir: Path, mock_config_toml: Path):
        """Re-running a stage without input changes SHALL be a no-op unless forced.

        Requirements: NFR-2 (Idempotence)
        Issue: Design phase - Idempotence validation
        """
        # Arrange
        from w2t_bkin.ingest import build_manifest

        # Act - First run
        manifest_path_1 = build_manifest(synthetic_session, mock_config_toml, temp_workdir)
        content_1 = manifest_path_1.read_text()
        mtime_1 = manifest_path_1.stat().st_mtime

        # Act - Second run (should detect no changes)
        manifest_path_2 = build_manifest(synthetic_session, mock_config_toml, temp_workdir)
        content_2 = manifest_path_2.read_text()
        mtime_2 = manifest_path_2.stat().st_mtime

        # Assert
        assert content_1 == content_2, "Output content must be identical"
        assert mtime_2 == mtime_1, "File should not be rewritten if unchanged (idempotent)"

    def test_Should_FailFast_When_RequiredFileMissing_ErrorHandling(self, temp_workdir: Path, mock_config_toml: Path):
        """THE SYSTEM SHALL fail fast when required files are missing.

        Requirements: Design §6 - MissingInputError
        Issue: Design phase - Error handling validation
        """
        # Arrange
        from w2t_bkin.ingest import build_manifest

        non_existent_session = temp_workdir / "does_not_exist"

        # Act & Assert
        with pytest.raises(Exception) as exc_info:  # Should raise MissingInputError
            build_manifest(non_existent_session, mock_config_toml, temp_workdir)

        assert "missing" in str(exc_info.value).lower() or "not found" in str(exc_info.value).lower()

    def test_Should_ExitNonZero_When_DriftExceedsThreshold_ErrorHandling(self, synthetic_session: Path, temp_workdir: Path, mock_config_toml: Path):
        """THE SYSTEM SHALL abort sync when drift exceeds tolerance.

        Requirements: Design §6 - DriftThresholdExceeded
        Issue: Design phase - Sync error handling
        """
        # Arrange
        from w2t_bkin.ingest import build_manifest
        from w2t_bkin.sync import compute_timestamps

        manifest_path = build_manifest(synthetic_session, mock_config_toml, temp_workdir)

        # Modify config to set very strict tolerance
        import toml

        config = toml.load(mock_config_toml)
        config["sync"]["tolerance_ms"] = 0.001  # Unrealistically strict
        strict_config = temp_workdir / "strict_config.toml"
        strict_config.write_text(toml.dumps(config))

        # Act & Assert
        with pytest.raises(Exception) as exc_info:  # Should raise DriftThresholdExceeded
            compute_timestamps(manifest_path, temp_workdir / "sync", config_path=strict_config)

        assert "drift" in str(exc_info.value).lower() or "threshold" in str(exc_info.value).lower()
