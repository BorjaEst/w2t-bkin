"""Unit tests for NWB module (RED PHASE).

Test the NWB assembly module following TDD methodology.
All tests should FAIL initially (Red Phase) before implementation.

Requirements: FR-7, FR-9, NFR-1, NFR-2, NFR-3, NFR-6, NFR-11
Design: design.md §2 (NWB module), §3 (Data Contracts), §11 (Provenance)
API: api.md §3.10
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

# Module under test (will be implemented)
# from w2t_bkin.nwb import assemble_nwb, NWBSummary, NWBBuildError

# Dependencies
from w2t_bkin.domain import (
    Event,
    FacemapMetrics,
    Manifest,
    MissingInputError,
    NWBAssemblyOptions,
    PoseSample,
    PoseTable,
    Trial,
    VideoMetadata,
)
from w2t_bkin.utils import read_json, write_json, write_csv


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_manifest(tmp_path: Path) -> Path:
    """Create a sample manifest.json for testing."""
    manifest_data = {
        "session_id": "test_session_001",
        "videos": [
            {
                "camera_id": i,
                "path": str(tmp_path / f"cam{i}.mp4"),
                "codec": "h264",
                "fps": 30.0,
                "duration": 60.0,
                "resolution": [1920, 1080],
            }
            for i in range(5)
        ],
        "sync": [{"path": str(tmp_path / "sync.csv"), "type": "ttl"}],
        "config_snapshot": {
            "project": {"name": "test", "n_cameras": 5},
            "nwb": {
                "session_description": "Test session",
                "lab": "Test Lab",
                "institution": "Test University",
            },
            "session": {
                "experimenter": "Test User",
                "subject_id": "mouse001",
                "sex": "M",
                "age": "P90",
            },
        },
        "provenance": {"git_commit": "abc1234"},
    }

    manifest_path = tmp_path / "manifest.json"
    write_json(manifest_path, manifest_data)
    return manifest_path


@pytest.fixture
def sample_timestamps(tmp_path: Path) -> Path:
    """Create sample timestamp CSVs for 5 cameras."""
    timestamps_dir = tmp_path / "timestamps"
    timestamps_dir.mkdir()

    for cam_id in range(5):
        rows = [
            {"frame_index": i, "timestamp": i * 0.0333}  # ~30 fps
            for i in range(100)
        ]
        write_csv(timestamps_dir / f"timestamps_cam{cam_id}.csv", rows)

    return timestamps_dir


@pytest.fixture
def sample_pose(tmp_path: Path) -> Path:
    """Create sample pose data."""
    pose_dir = tmp_path / "pose"
    pose_dir.mkdir()

    # Create pose table (simplified - would be Parquet in real implementation)
    pose_data = {
        "records": [
            {
                "time": i * 0.0333,
                "keypoint": "nose",
                "x_px": 100.0 + i,
                "y_px": 200.0 + i * 0.5,
                "confidence": 0.95,
            }
            for i in range(100)
        ],
        "skeleton_meta": {"keypoints": ["nose", "left_ear", "right_ear"]},
    }

    write_json(pose_dir / "pose_table.json", pose_data)
    return pose_dir


@pytest.fixture
def sample_facemap(tmp_path: Path) -> Path:
    """Create sample facemap metrics."""
    facemap_dir = tmp_path / "facemap"
    facemap_dir.mkdir()

    facemap_data = {
        "time": [i * 0.0333 for i in range(100)],
        "metric_columns": {
            "pupil_area": [50.0 + i * 0.1 for i in range(100)],
            "motion_energy": [10.0 + i * 0.05 for i in range(100)],
        },
    }

    write_json(facemap_dir / "facemap_metrics.json", facemap_data)
    return facemap_dir


@pytest.fixture
def sample_events(tmp_path: Path) -> Path:
    """Create sample trials and events."""
    events_dir = tmp_path / "events"
    events_dir.mkdir()

    # Trials
    trials_data = [
        {
            "trial_id": 1,
            "start_time": 0.0,
            "stop_time": 1.5,
            "phase_first": "init",
            "phase_last": "reward",
            "qc_flags": [],
        },
        {
            "trial_id": 2,
            "start_time": 2.0,
            "stop_time": 3.5,
            "phase_first": "init",
            "phase_last": "timeout",
            "qc_flags": ["inferred_end"],
        },
    ]
    write_csv(events_dir / "trials.csv", trials_data)

    # Events
    events_data = [
        {"time": 0.0, "kind": "trial_start", "payload": "{}"},
        {"time": 0.5, "kind": "stimulus_on", "payload": '{"intensity": 0.8}'},
        {"time": 1.0, "kind": "response", "payload": '{"correct": true}'},
        {"time": 1.5, "kind": "trial_end", "payload": "{}"},
    ]
    write_csv(events_dir / "events.csv", events_data)

    return events_dir


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    """Create output directory."""
    out_dir = tmp_path / "output"
    out_dir.mkdir()
    return out_dir


# ============================================================================
# Test Class: NWB Creation
# ============================================================================


class TestNWBCreation:
    """Test basic NWB file creation (FR-7)."""

    def test_Should_CreateNWBFile_When_VideosProvided_MR1(
        self, sample_manifest: Path, sample_timestamps: Path, output_dir: Path
    ):
        """THE SYSTEM SHALL export one NWB file per session.

        Requirements: FR-7 (Export NWB)
        Issue: NWB creation with minimal inputs
        """
        from w2t_bkin.nwb import assemble_nwb

        # Act
        nwb_path = assemble_nwb(
            manifest_path=sample_manifest,
            timestamps_dir=sample_timestamps,
            output_dir=output_dir,
        )

        # Assert
        assert nwb_path.exists(), "NWB file should be created"
        assert nwb_path.suffix == ".nwb", "File should have .nwb extension"
        assert nwb_path.name == "test_session_001.nwb", "File name should match session_id"

    def test_Should_CreateDevices_When_Building_MR1(
        self, sample_manifest: Path, sample_timestamps: Path, output_dir: Path
    ):
        """THE SYSTEM SHALL create Devices for five cameras.

        Requirements: FR-7 (Export NWB with devices)
        Issue: Device creation for cameras
        """
        from w2t_bkin.nwb import assemble_nwb

        # Act
        nwb_path = assemble_nwb(
            manifest_path=sample_manifest,
            timestamps_dir=sample_timestamps,
            output_dir=output_dir,
        )

        # Assert - verify with pynwb
        from pynwb import NWBHDF5IO

        with NWBHDF5IO(str(nwb_path), "r") as io:
            nwb_file = io.read()
            assert len(nwb_file.devices) == 5, "Should have 5 camera devices"
            
            for i in range(5):
                device_name = f"Camera_{i}"
                assert device_name in nwb_file.devices, f"Device {device_name} should exist"

    def test_Should_CreateImageSeries_When_Building_MR1(
        self, sample_manifest: Path, sample_timestamps: Path, output_dir: Path
    ):
        """THE SYSTEM SHALL create one ImageSeries per camera with external_file links.

        Requirements: FR-7 (ImageSeries with external links)
        Issue: ImageSeries creation
        """
        from w2t_bkin.nwb import assemble_nwb

        # Act
        nwb_path = assemble_nwb(
            manifest_path=sample_manifest,
            timestamps_dir=sample_timestamps,
            output_dir=output_dir,
        )

        # Assert
        from pynwb import NWBHDF5IO

        with NWBHDF5IO(str(nwb_path), "r") as io:
            nwb_file = io.read()
            
            # Check acquisition contains ImageSeries
            assert len(nwb_file.acquisition) >= 5, "Should have at least 5 ImageSeries"
            
            for i in range(5):
                series_name = f"VideoCamera{i}"
                assert series_name in nwb_file.acquisition, f"{series_name} should exist"
                
                series = nwb_file.acquisition[series_name]
                assert series.format == "external", "Format should be external"
                assert series.external_file is not None, "Should have external_file"
                assert series.device is not None, "Should link to device"

    def test_Should_SetSessionMetadata_When_Building_FR7(
        self, sample_manifest: Path, sample_timestamps: Path, output_dir: Path
    ):
        """THE SYSTEM SHALL populate NWB session metadata from config.

        Requirements: FR-7 (NWB metadata), FR-10 (Configuration-driven)
        Issue: Session metadata population
        """
        from w2t_bkin.nwb import assemble_nwb

        # Act
        nwb_path = assemble_nwb(
            manifest_path=sample_manifest,
            timestamps_dir=sample_timestamps,
            output_dir=output_dir,
        )

        # Assert
        from pynwb import NWBHDF5IO

        with NWBHDF5IO(str(nwb_path), "r") as io:
            nwb_file = io.read()
            
            assert nwb_file.session_id == "test_session_001"
            assert nwb_file.session_description == "Test session"
            assert nwb_file.lab == "Test Lab"
            assert nwb_file.institution == "Test University"
            assert "Test User" in nwb_file.experimenter
            assert nwb_file.subject is not None
            assert nwb_file.subject.subject_id == "mouse001"


# ============================================================================
# Test Class: Timestamps
# ============================================================================


class TestTimestamps:
    """Test timestamp embedding (FR-2, FR-3)."""

    def test_Should_EmbedTimestamps_When_AssemblingNWB_FR2(
        self, sample_manifest: Path, sample_timestamps: Path, output_dir: Path
    ):
        """THE SYSTEM SHALL embed per-frame timestamps for each camera.

        Requirements: FR-2 (Per-frame timestamps)
        Issue: Timestamp embedding in ImageSeries
        """
        from w2t_bkin.nwb import assemble_nwb

        # Act
        nwb_path = assemble_nwb(
            manifest_path=sample_manifest,
            timestamps_dir=sample_timestamps,
            output_dir=output_dir,
        )

        # Assert
        from pynwb import NWBHDF5IO

        with NWBHDF5IO(str(nwb_path), "r") as io:
            nwb_file = io.read()
            
            for i in range(5):
                series = nwb_file.acquisition[f"VideoCamera{i}"]
                assert series.timestamps is not None, f"Camera {i} should have timestamps"
                assert len(series.timestamps) == 100, f"Camera {i} should have 100 timestamps"
                
                # Verify monotonic
                timestamps = series.timestamps[:]
                for j in range(1, len(timestamps)):
                    assert timestamps[j] > timestamps[j-1], "Timestamps should be monotonic"

    def test_Should_CreateSyncTimeSeries_When_Assembling_FR3(
        self, sample_manifest: Path, sample_timestamps: Path, output_dir: Path
    ):
        """THE SYSTEM SHALL create sync TimeSeries in processing module.

        Requirements: FR-3 (Sync data), FR-7 (Sync TimeSeries)
        Issue: Sync data storage
        """
        from w2t_bkin.nwb import assemble_nwb

        # Act
        nwb_path = assemble_nwb(
            manifest_path=sample_manifest,
            timestamps_dir=sample_timestamps,
            output_dir=output_dir,
        )

        # Assert
        from pynwb import NWBHDF5IO

        with NWBHDF5IO(str(nwb_path), "r") as io:
            nwb_file = io.read()
            
            assert "sync" in nwb_file.processing, "Should have sync processing module"
            sync_module = nwb_file.processing["sync"]
            assert "SyncTimestamps" in sync_module.data_interfaces

    def test_Should_ValidateMonotonicTimestamps_When_Loading_FR2(
        self, sample_manifest: Path, tmp_path: Path, output_dir: Path
    ):
        """THE SYSTEM SHALL detect non-monotonic timestamps.

        Requirements: FR-2 (Valid timestamps), NFR-8 (Data integrity)
        Issue: Timestamp validation
        """
        from w2t_bkin.nwb import assemble_nwb

        # Arrange - create bad timestamps
        timestamps_dir = tmp_path / "bad_timestamps"
        timestamps_dir.mkdir()
        
        bad_rows = [
            {"frame_index": 0, "timestamp": 0.0},
            {"frame_index": 1, "timestamp": 0.033},
            {"frame_index": 2, "timestamp": 0.020},  # Goes backward!
        ]
        write_csv(timestamps_dir / "timestamps_cam0.csv", bad_rows)

        # Act & Assert
        with pytest.raises((ValueError, AssertionError), match="monotonic|backward"):
            assemble_nwb(
                manifest_path=sample_manifest,
                timestamps_dir=timestamps_dir,
                output_dir=output_dir,
            )

    def test_Should_HandleTimestampLengthMismatch_When_DifferentCameras_FR3(
        self, sample_manifest: Path, tmp_path: Path, output_dir: Path
    ):
        """THE SYSTEM SHALL detect timestamp length mismatches across cameras.

        Requirements: FR-3 (Detect drops/duplicates)
        Issue: Cross-camera validation
        """
        from w2t_bkin.nwb import assemble_nwb

        # Arrange - create mismatched timestamps
        timestamps_dir = tmp_path / "mismatched_timestamps"
        timestamps_dir.mkdir()
        
        for cam_id in range(5):
            n_frames = 100 if cam_id < 4 else 95  # Camera 4 has fewer frames
            rows = [
                {"frame_index": i, "timestamp": i * 0.0333}
                for i in range(n_frames)
            ]
            write_csv(timestamps_dir / f"timestamps_cam{cam_id}.csv", rows)

        # Act - should warn but not fail
        nwb_path = assemble_nwb(
            manifest_path=sample_manifest,
            timestamps_dir=timestamps_dir,
            output_dir=output_dir,
        )

        # Assert - check summary for warning
        summary_path = output_dir / "nwb_summary.json"
        assert summary_path.exists()
        summary = read_json(summary_path)
        assert any("mismatch" in w.lower() for w in summary["warnings"])


# ============================================================================
# Test Class: Optional Data
# ============================================================================


class TestOptionalData:
    """Test optional stages integration (FR-5, FR-6, FR-11)."""

    def test_Should_IncludePoseData_When_PoseDirProvided_FR5(
        self,
        sample_manifest: Path,
        sample_timestamps: Path,
        sample_pose: Path,
        output_dir: Path,
    ):
        """THE SYSTEM SHALL include pose data when provided.

        Requirements: FR-5 (Import pose), FR-7 (ndx-pose containers)
        Issue: Pose integration
        """
        from w2t_bkin.nwb import assemble_nwb

        # Act
        nwb_path = assemble_nwb(
            manifest_path=sample_manifest,
            timestamps_dir=sample_timestamps,
            output_dir=output_dir,
            pose_dir=sample_pose,
        )

        # Assert
        from pynwb import NWBHDF5IO

        with NWBHDF5IO(str(nwb_path), "r") as io:
            nwb_file = io.read()
            
            # Check for behavior processing module with pose
            assert "behavior" in nwb_file.processing, "Should have behavior module"
            # Note: Exact structure depends on ndx-pose implementation

    def test_Should_IncludeFacemapMetrics_When_FacemapDirProvided_FR6(
        self,
        sample_manifest: Path,
        sample_timestamps: Path,
        sample_facemap: Path,
        output_dir: Path,
    ):
        """THE SYSTEM SHALL include facemap metrics when provided.

        Requirements: FR-6 (Import facemap), FR-7 (BehavioralTimeSeries)
        Issue: Facemap integration
        """
        from w2t_bkin.nwb import assemble_nwb

        # Act
        nwb_path = assemble_nwb(
            manifest_path=sample_manifest,
            timestamps_dir=sample_timestamps,
            output_dir=output_dir,
            facemap_dir=sample_facemap,
        )

        # Assert
        from pynwb import NWBHDF5IO

        with NWBHDF5IO(str(nwb_path), "r") as io:
            nwb_file = io.read()
            
            assert "behavior" in nwb_file.processing, "Should have behavior module"
            behavior = nwb_file.processing["behavior"]
            
            # Check for facemap metrics
            assert any("pupil" in name.lower() or "motion" in name.lower() 
                      for name in behavior.data_interfaces.keys())

    def test_Should_IncludeTrialsAndEvents_When_EventsDirProvided_FR11(
        self,
        sample_manifest: Path,
        sample_timestamps: Path,
        sample_events: Path,
        output_dir: Path,
    ):
        """THE SYSTEM SHALL include trials and events when provided.

        Requirements: FR-11 (Import trials/events), FR-7 (TimeIntervals table)
        Issue: Events integration
        """
        from w2t_bkin.nwb import assemble_nwb

        # Act
        nwb_path = assemble_nwb(
            manifest_path=sample_manifest,
            timestamps_dir=sample_timestamps,
            output_dir=output_dir,
            events_dir=sample_events,
        )

        # Assert
        from pynwb import NWBHDF5IO

        with NWBHDF5IO(str(nwb_path), "r") as io:
            nwb_file = io.read()
            
            # Check for trials
            assert nwb_file.trials is not None, "Should have trials table"
            assert len(nwb_file.trials) == 2, "Should have 2 trials"
            
            # Check trials columns
            assert "trial_id" in nwb_file.trials.colnames
            assert "start_time" in nwb_file.trials.colnames
            assert "stop_time" in nwb_file.trials.colnames

    def test_Should_SkipOptionalData_When_NotProvided_NFR7(
        self, sample_manifest: Path, sample_timestamps: Path, output_dir: Path
    ):
        """THE SYSTEM SHALL skip optional data gracefully when not provided.

        Requirements: NFR-7 (Modularity - optional stages)
        Issue: Optional data handling
        """
        from w2t_bkin.nwb import assemble_nwb

        # Act - no optional directories
        nwb_path = assemble_nwb(
            manifest_path=sample_manifest,
            timestamps_dir=sample_timestamps,
            output_dir=output_dir,
            pose_dir=None,
            facemap_dir=None,
            events_dir=None,
        )

        # Assert - should succeed
        assert nwb_path.exists(), "NWB should be created without optional data"
        
        # Check summary
        summary_path = output_dir / "nwb_summary.json"
        summary = read_json(summary_path)
        assert summary["pose_included"] is False
        assert summary["facemap_included"] is False
        assert summary["trials_included"] is False

    def test_Should_WarnWhenOptionalDataMissing_When_DirEmpty_NFR3(
        self, sample_manifest: Path, sample_timestamps: Path, tmp_path: Path, output_dir: Path
    ):
        """THE SYSTEM SHALL warn when optional directories are empty.

        Requirements: NFR-3 (Observability)
        Issue: Missing optional data warnings
        """
        from w2t_bkin.nwb import assemble_nwb

        # Arrange - create empty optional directories
        empty_pose = tmp_path / "empty_pose"
        empty_pose.mkdir()

        # Act
        nwb_path = assemble_nwb(
            manifest_path=sample_manifest,
            timestamps_dir=sample_timestamps,
            output_dir=output_dir,
            pose_dir=empty_pose,
        )

        # Assert
        summary_path = output_dir / "nwb_summary.json"
        summary = read_json(summary_path)
        assert any("pose" in w.lower() and ("not found" in w.lower() or "missing" in w.lower()) 
                  for w in summary["warnings"])


# ============================================================================
# Test Class: Provenance
# ============================================================================


class TestProvenance:
    """Test provenance capture (NFR-11)."""

    def test_Should_EmbedConfigSnapshot_When_Assembling_NFR11(
        self, sample_manifest: Path, sample_timestamps: Path, output_dir: Path
    ):
        """THE SYSTEM SHALL embed config snapshot in NWB.

        Requirements: NFR-11 (Provenance)
        Issue: Config provenance
        """
        from w2t_bkin.nwb import assemble_nwb

        # Act
        nwb_path = assemble_nwb(
            manifest_path=sample_manifest,
            timestamps_dir=sample_timestamps,
            output_dir=output_dir,
        )

        # Assert
        from pynwb import NWBHDF5IO

        with NWBHDF5IO(str(nwb_path), "r") as io:
            nwb_file = io.read()
            
            # Config should be in notes or processing/provenance
            assert nwb_file.notes is not None or "provenance" in nwb_file.processing
            
            # Check notes contains config
            if nwb_file.notes:
                assert "config_snapshot" in nwb_file.notes or "project" in nwb_file.notes

    def test_Should_RecordGitCommit_When_Assembling_NFR11(
        self, sample_manifest: Path, sample_timestamps: Path, output_dir: Path
    ):
        """THE SYSTEM SHALL record git commit hash.

        Requirements: NFR-11 (Provenance - git commit)
        Issue: Git commit provenance
        """
        from w2t_bkin.nwb import assemble_nwb

        # Act
        nwb_path = assemble_nwb(
            manifest_path=sample_manifest,
            timestamps_dir=sample_timestamps,
            output_dir=output_dir,
        )

        # Assert
        summary_path = output_dir / "nwb_summary.json"
        summary = read_json(summary_path)
        assert "provenance" in summary
        assert "git_commit" in summary["provenance"]
        assert len(summary["provenance"]["git_commit"]) > 0

    def test_Should_RecordSoftwareVersions_When_Assembling_NFR11(
        self, sample_manifest: Path, sample_timestamps: Path, output_dir: Path
    ):
        """THE SYSTEM SHALL record software versions.

        Requirements: NFR-11 (Provenance - software versions)
        Issue: Software version provenance
        """
        from w2t_bkin.nwb import assemble_nwb

        # Act
        nwb_path = assemble_nwb(
            manifest_path=sample_manifest,
            timestamps_dir=sample_timestamps,
            output_dir=output_dir,
        )

        # Assert
        summary_path = output_dir / "nwb_summary.json"
        summary = read_json(summary_path)
        assert "provenance" in summary
        assert "software_versions" in summary["provenance"]
        
        versions = summary["provenance"]["software_versions"]
        assert "pynwb" in versions
        assert "python" in versions

    def test_Should_ComputeArtifactHashes_When_Assembling_NFR11(
        self, sample_manifest: Path, sample_timestamps: Path, output_dir: Path
    ):
        """THE SYSTEM SHALL compute hashes of input artifacts.

        Requirements: NFR-11 (Provenance), NFR-1 (Reproducibility)
        Issue: Artifact hash provenance
        """
        from w2t_bkin.nwb import assemble_nwb

        # Act
        nwb_path = assemble_nwb(
            manifest_path=sample_manifest,
            timestamps_dir=sample_timestamps,
            output_dir=output_dir,
        )

        # Assert
        summary_path = output_dir / "nwb_summary.json"
        summary = read_json(summary_path)
        assert "provenance" in summary
        assert "stage_artifacts" in summary["provenance"]
        
        artifacts = summary["provenance"]["stage_artifacts"]
        assert "manifest_hash" in artifacts
        assert artifacts["manifest_hash"].startswith("sha256:")


# ============================================================================
# Test Class: Idempotence
# ============================================================================


class TestIdempotence:
    """Test idempotent re-runs (NFR-2)."""

    def test_Should_SkipProcessing_When_UnchangedInputs_NFR2(
        self, sample_manifest: Path, sample_timestamps: Path, output_dir: Path
    ):
        """THE SYSTEM SHALL skip processing when inputs unchanged.

        Requirements: NFR-2 (Idempotence)
        Issue: Idempotent NWB assembly
        """
        from w2t_bkin.nwb import assemble_nwb

        # First run
        nwb_path1 = assemble_nwb(
            manifest_path=sample_manifest,
            timestamps_dir=sample_timestamps,
            output_dir=output_dir,
        )
        
        first_mtime = nwb_path1.stat().st_mtime

        # Second run - should skip
        nwb_path2 = assemble_nwb(
            manifest_path=sample_manifest,
            timestamps_dir=sample_timestamps,
            output_dir=output_dir,
        )

        # Assert
        assert nwb_path1 == nwb_path2
        
        # Check summary indicates skip
        summary_path = output_dir / "nwb_summary.json"
        summary = read_json(summary_path)
        assert summary["skipped"] is True

    def test_Should_Reprocess_When_ForceFlag_NFR2(
        self, sample_manifest: Path, sample_timestamps: Path, output_dir: Path
    ):
        """THE SYSTEM SHALL reprocess when force=True.

        Requirements: NFR-2 (Idempotence with force)
        Issue: Force rebuild
        """
        from w2t_bkin.nwb import assemble_nwb

        # First run
        nwb_path1 = assemble_nwb(
            manifest_path=sample_manifest,
            timestamps_dir=sample_timestamps,
            output_dir=output_dir,
        )

        # Second run with force
        nwb_path2 = assemble_nwb(
            manifest_path=sample_manifest,
            timestamps_dir=sample_timestamps,
            output_dir=output_dir,
            force=True,
        )

        # Assert - should rebuild
        summary_path = output_dir / "nwb_summary.json"
        summary = read_json(summary_path)
        assert summary["skipped"] is False

    def test_Should_Reprocess_When_InputChanged_NFR2(
        self, sample_manifest: Path, sample_timestamps: Path, output_dir: Path
    ):
        """THE SYSTEM SHALL reprocess when inputs change.

        Requirements: NFR-2 (Idempotence), NFR-1 (Reproducibility)
        Issue: Input change detection
        """
        from w2t_bkin.nwb import assemble_nwb

        # First run
        nwb_path1 = assemble_nwb(
            manifest_path=sample_manifest,
            timestamps_dir=sample_timestamps,
            output_dir=output_dir,
        )

        # Modify manifest
        manifest_data = read_json(sample_manifest)
        manifest_data["config_snapshot"]["nwb"]["session_description"] = "Modified"
        write_json(sample_manifest, manifest_data)

        # Second run - should reprocess
        nwb_path2 = assemble_nwb(
            manifest_path=sample_manifest,
            timestamps_dir=sample_timestamps,
            output_dir=output_dir,
        )

        # Assert
        summary_path = output_dir / "nwb_summary.json"
        summary = read_json(summary_path)
        assert summary["skipped"] is False


# ============================================================================
# Test Class: Options
# ============================================================================


class TestOptions:
    """Test configuration overrides (FR-10)."""

    def test_Should_UseManifestConfig_When_NoOptionsProvided_FR10(
        self, sample_manifest: Path, sample_timestamps: Path, output_dir: Path
    ):
        """THE SYSTEM SHALL use manifest config by default.

        Requirements: FR-10 (Configuration-driven)
        Issue: Default config usage
        """
        from w2t_bkin.nwb import assemble_nwb

        # Act - no options provided
        nwb_path = assemble_nwb(
            manifest_path=sample_manifest,
            timestamps_dir=sample_timestamps,
            output_dir=output_dir,
        )

        # Assert
        from pynwb import NWBHDF5IO

        with NWBHDF5IO(str(nwb_path), "r") as io:
            nwb_file = io.read()
            assert nwb_file.session_description == "Test session"
            assert nwb_file.lab == "Test Lab"

    def test_Should_OverrideConfig_When_OptionsProvided_FR10(
        self, sample_manifest: Path, sample_timestamps: Path, output_dir: Path
    ):
        """THE SYSTEM SHALL override config with NWBAssemblyOptions.

        Requirements: FR-10 (Configuration overrides)
        Issue: Options override
        """
        from w2t_bkin.nwb import assemble_nwb

        # Act - with custom options
        custom_options = NWBAssemblyOptions(
            session_description="Custom description",
            lab="Custom Lab",
            institution="Custom University",
            link_external_video=False,
        )

        nwb_path = assemble_nwb(
            manifest_path=sample_manifest,
            timestamps_dir=sample_timestamps,
            output_dir=output_dir,
            options=custom_options,
        )

        # Assert
        from pynwb import NWBHDF5IO

        with NWBHDF5IO(str(nwb_path), "r") as io:
            nwb_file = io.read()
            assert nwb_file.session_description == "Custom description"
            assert nwb_file.lab == "Custom Lab"
            assert nwb_file.institution == "Custom University"

    def test_Should_GenerateFileName_When_EmptyInOptions_FR7(
        self, sample_manifest: Path, sample_timestamps: Path, output_dir: Path
    ):
        """THE SYSTEM SHALL generate file name from session_id when empty.

        Requirements: FR-7 (NWB file naming)
        Issue: Auto-generate file name
        """
        from w2t_bkin.nwb import assemble_nwb

        # Act
        nwb_path = assemble_nwb(
            manifest_path=sample_manifest,
            timestamps_dir=sample_timestamps,
            output_dir=output_dir,
        )

        # Assert
        assert nwb_path.name == "test_session_001.nwb"

    def test_Should_UseCustomFileName_When_ProvidedInOptions_FR10(
        self, sample_manifest: Path, sample_timestamps: Path, output_dir: Path
    ):
        """THE SYSTEM SHALL use custom file name when provided.

        Requirements: FR-10 (Configuration)
        Issue: Custom file name
        """
        from w2t_bkin.nwb import assemble_nwb

        # Act
        custom_options = NWBAssemblyOptions(file_name="custom_output.nwb")

        nwb_path = assemble_nwb(
            manifest_path=sample_manifest,
            timestamps_dir=sample_timestamps,
            output_dir=output_dir,
            options=custom_options,
        )

        # Assert
        assert nwb_path.name == "custom_output.nwb"


# ============================================================================
# Test Class: Error Handling
# ============================================================================


class TestErrorHandling:
    """Test error scenarios (Design §6)."""

    def test_Should_RaiseMissingInputError_When_ManifestNotFound_Design(
        self, sample_timestamps: Path, output_dir: Path
    ):
        """THE SYSTEM SHALL raise MissingInputError for missing manifest.

        Requirements: Design §6 (Error handling)
        Issue: Missing manifest error
        """
        from w2t_bkin.nwb import assemble_nwb

        # Act & Assert
        with pytest.raises(MissingInputError, match="manifest"):
            assemble_nwb(
                manifest_path=Path("/nonexistent/manifest.json"),
                timestamps_dir=sample_timestamps,
                output_dir=output_dir,
            )

    def test_Should_RaiseMissingInputError_When_TimestampsNotFound_Design(
        self, sample_manifest: Path, output_dir: Path
    ):
        """THE SYSTEM SHALL raise MissingInputError for missing timestamps.

        Requirements: Design §6 (Error handling)
        Issue: Missing timestamps error
        """
        from w2t_bkin.nwb import assemble_nwb

        # Act & Assert
        with pytest.raises(MissingInputError, match="timestamp"):
            assemble_nwb(
                manifest_path=sample_manifest,
                timestamps_dir=Path("/nonexistent/timestamps"),
                output_dir=output_dir,
            )

    def test_Should_RaiseNwbBuildError_When_InputsMalformed_Design(
        self, tmp_path: Path, sample_timestamps: Path, output_dir: Path
    ):
        """THE SYSTEM SHALL raise NWBBuildError for construction errors.

        Requirements: Design §6 (Error handling)
        Issue: NWB build error
        """
        from w2t_bkin.nwb import assemble_nwb, NWBBuildError

        # Arrange - create malformed manifest
        bad_manifest = tmp_path / "bad_manifest.json"
        write_json(bad_manifest, {"invalid": "structure"})

        # Act & Assert
        with pytest.raises((NWBBuildError, ValueError, KeyError)):
            assemble_nwb(
                manifest_path=bad_manifest,
                timestamps_dir=sample_timestamps,
                output_dir=output_dir,
            )

    def test_Should_ProvideContext_When_ErrorRaised_Design(
        self, sample_manifest: Path, output_dir: Path
    ):
        """THE SYSTEM SHALL provide diagnostic context in errors.

        Requirements: Design §6 (Error handling), NFR-3 (Observability)
        Issue: Error context
        """
        from w2t_bkin.nwb import assemble_nwb

        # Act & Assert
        try:
            assemble_nwb(
                manifest_path=sample_manifest,
                timestamps_dir=Path("/nonexistent"),
                output_dir=output_dir,
            )
            pytest.fail("Should have raised error")
        except Exception as e:
            # Error message should contain helpful context
            error_msg = str(e).lower()
            assert "timestamp" in error_msg or "not found" in error_msg


# ============================================================================
# Test Class: Output Generation
# ============================================================================


class TestOutputGeneration:
    """Test output files (NFR-3)."""

    def test_Should_WriteNWBSummary_When_Assembling_NFR3(
        self, sample_manifest: Path, sample_timestamps: Path, output_dir: Path
    ):
        """THE SYSTEM SHALL write nwb_summary.json.

        Requirements: NFR-3 (Observability)
        Issue: Summary JSON output
        """
        from w2t_bkin.nwb import assemble_nwb

        # Act
        nwb_path = assemble_nwb(
            manifest_path=sample_manifest,
            timestamps_dir=sample_timestamps,
            output_dir=output_dir,
        )

        # Assert
        summary_path = output_dir / "nwb_summary.json"
        assert summary_path.exists(), "Summary JSON should be created"
        
        summary = read_json(summary_path)
        assert "session_id" in summary
        assert "nwb_path" in summary
        assert "file_size_mb" in summary
        assert "provenance" in summary

    def test_Should_ComputeFileSize_When_Creating_NFR3(
        self, sample_manifest: Path, sample_timestamps: Path, output_dir: Path
    ):
        """THE SYSTEM SHALL compute NWB file size.

        Requirements: NFR-3 (Observability)
        Issue: File size metadata
        """
        from w2t_bkin.nwb import assemble_nwb

        # Act
        nwb_path = assemble_nwb(
            manifest_path=sample_manifest,
            timestamps_dir=sample_timestamps,
            output_dir=output_dir,
        )

        # Assert
        summary_path = output_dir / "nwb_summary.json"
        summary = read_json(summary_path)
        
        assert summary["file_size_mb"] > 0
        
        # Verify matches actual file size
        actual_size_mb = nwb_path.stat().st_size / (1024 * 1024)
        assert abs(summary["file_size_mb"] - actual_size_mb) < 0.01

    def test_Should_ReturnNWBPath_When_Assembling_API(
        self, sample_manifest: Path, sample_timestamps: Path, output_dir: Path
    ):
        """THE SYSTEM SHALL return Path to created NWB file.

        Requirements: API §3.10
        Issue: Return value
        """
        from w2t_bkin.nwb import assemble_nwb

        # Act
        nwb_path = assemble_nwb(
            manifest_path=sample_manifest,
            timestamps_dir=sample_timestamps,
            output_dir=output_dir,
        )

        # Assert
        assert isinstance(nwb_path, Path)
        assert nwb_path.exists()
        assert nwb_path.suffix == ".nwb"

    def test_Should_IncludeStatistics_When_GeneratingSummary_NFR3(
        self, sample_manifest: Path, sample_timestamps: Path, output_dir: Path
    ):
        """THE SYSTEM SHALL include statistics in summary.

        Requirements: NFR-3 (Observability)
        Issue: Summary statistics
        """
        from w2t_bkin.nwb import assemble_nwb

        # Act
        nwb_path = assemble_nwb(
            manifest_path=sample_manifest,
            timestamps_dir=sample_timestamps,
            output_dir=output_dir,
        )

        # Assert
        summary_path = output_dir / "nwb_summary.json"
        summary = read_json(summary_path)
        
        assert "n_devices" in summary
        assert summary["n_devices"] == 5
        assert "n_image_series" in summary
        assert summary["n_image_series"] == 5
        assert "n_timestamps" in summary
        assert summary["n_timestamps"] == 500  # 100 frames * 5 cameras


# ============================================================================
# Test Class: Helper Functions
# ============================================================================


class TestHelperFunctions:
    """Test internal helpers."""

    def test_Should_LoadManifest_When_Valid_API(self, sample_manifest: Path):
        """Helper SHALL load manifest correctly.

        Requirements: API §3.10
        Issue: Manifest loading
        """
        from w2t_bkin.nwb import _load_manifest

        # Act
        manifest = _load_manifest(sample_manifest)

        # Assert
        assert manifest.session_id == "test_session_001"
        assert len(manifest.videos) == 5

    def test_Should_LoadTimestamps_When_Valid_API(self, sample_timestamps: Path):
        """Helper SHALL load timestamps correctly.

        Requirements: API §3.10
        Issue: Timestamp loading
        """
        from w2t_bkin.nwb import _load_timestamps

        # Act
        timestamps_list = _load_timestamps(sample_timestamps, n_cameras=5)

        # Assert
        assert len(timestamps_list) == 5
        assert all(len(ts.frame_index) == 100 for ts in timestamps_list)

    def test_Should_LoadPoseData_When_Valid_API(self, sample_pose: Path):
        """Helper SHALL load pose data correctly.

        Requirements: API §3.10, FR-5
        Issue: Pose loading
        """
        from w2t_bkin.nwb import _load_pose_data

        # Act
        pose_table = _load_pose_data(sample_pose)

        # Assert
        assert pose_table is not None
        assert len(pose_table.records) > 0

    def test_Should_ComputeProvenance_When_Called_NFR11(
        self, sample_manifest: Path, sample_timestamps: Path
    ):
        """Helper SHALL compute provenance metadata.

        Requirements: NFR-11 (Provenance)
        Issue: Provenance computation
        """
        from w2t_bkin.nwb import _compute_provenance

        # Act
        provenance = _compute_provenance(
            manifest_path=sample_manifest,
            timestamps_dir=sample_timestamps,
        )

        # Assert
        assert "git_commit" in provenance
        assert "software_versions" in provenance
        assert "stage_artifacts" in provenance
        assert "manifest_hash" in provenance["stage_artifacts"]
