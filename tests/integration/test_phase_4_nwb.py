"""Integration tests for Phase 4 — NWB Assembly.

Tests end-to-end NWB file creation from ingest through assembly,
including external video links, rate-based ImageSeries, optional modalities,
and provenance embedding.

Requirements: FR-7, NFR-6, NFR-1, NFR-2, NFR-11
Acceptance: A1, A12
GitHub Issue: #5
"""

import json
from pathlib import Path

from pynwb import NWBHDF5IO, NWBFile
import pytest

from w2t_bkin.config import Config
from w2t_bkin.core.session import add_video_acquisition, create_nwb_file, load_metadata, write_nwb_file


class TestBasicNWBAssembly:
    """Test basic NWB assembly from metadata."""

    def test_Should_CreateNWB_When_MetadataProvided_Issue5(
        self,
        fixture_session_path,
        fixture_session_toml,
        tmp_work_dir,
    ):
        """Should create basic NWB file from Session-000001 metadata (FR-7, A1)."""

        # Load metadata
        metadata = load_metadata(fixture_session_toml)

        # Create NWBFile
        nwbfile = create_nwb_file(metadata)

        # Write NWB
        output_dir = tmp_work_dir / "processed" / "Session-000001"
        output_dir.mkdir(parents=True, exist_ok=True)
        nwb_path = output_dir / "Session-000001.nwb"

        write_nwb_file(nwbfile, nwb_path)

        # Verify NWB file created
        assert nwb_path.exists()
        assert nwb_path.suffix == ".nwb"

        # Verify content
        with NWBHDF5IO(str(nwb_path), "r") as io:
            read_nwb = io.read()
            assert read_nwb.identifier == "Session-000001"
            assert read_nwb.subject.subject_id == "mouse_001"

    def test_Should_IncludeAllCameras_When_MultipleInMetadata_Issue5(
        self,
        fixture_session_path,
        fixture_session_toml,
        tmp_work_dir,
    ):
        """Should include ImageSeries for all cameras (FR-7)."""

        # Load metadata
        metadata = load_metadata(fixture_session_toml)
        nwbfile = create_nwb_file(metadata)

        # Add cameras manually (simulating pipeline)
        cameras = metadata.get("cameras", [])
        for camera in cameras:
            # Mock video files
            video_files = [str(fixture_session_path / "Video" / "top" / "cam0_2025-01-01.avi")]
            add_video_acquisition(nwbfile, camera_id=camera["id"], video_files=video_files, frame_rate=camera.get("fps", 30.0))

        # Write NWB
        output_dir = tmp_work_dir / "processed" / "Session-000001"
        output_dir.mkdir(parents=True, exist_ok=True)
        nwb_path = output_dir / "Session-000001_cameras.nwb"
        write_nwb_file(nwbfile, nwb_path)

        # Read and verify
        with NWBHDF5IO(str(nwb_path), "r") as io:
            read_nwb = io.read()
            assert len(read_nwb.acquisition) >= len(cameras)
            assert "cam0" in read_nwb.acquisition
            assert "cam1" in read_nwb.acquisition


class TestRateBasedTiming:
    """Test rate-based ImageSeries timing (no per-frame timestamps)."""

    def test_Should_UseRateTiming_When_NominalRateTimebase_Issue5(
        self,
        fixture_session_path,
        fixture_session_toml,
        tmp_work_dir,
    ):
        """Should use rate-based timing for ImageSeries (FR-7, NFR-6, A12)."""

        metadata = load_metadata(fixture_session_toml)
        nwbfile = create_nwb_file(metadata)

        # Add camera with rate
        add_video_acquisition(nwbfile, camera_id="cam0_top", video_files=["dummy.avi"], frame_rate=30.0)

        output_dir = tmp_work_dir / "processed" / "Session-000001"
        output_dir.mkdir(parents=True, exist_ok=True)
        nwb_path = output_dir / "Session-000001_rate.nwb"
        write_nwb_file(nwbfile, nwb_path)

        # Verify rate-based timing
        with NWBHDF5IO(str(nwb_path), "r") as io:
            read_nwb = io.read()
            image_series = read_nwb.acquisition["cam0_top"]

            # Should have rate, not timestamps array
            assert hasattr(image_series, "rate")
            assert image_series.rate == 30.0
            assert hasattr(image_series, "starting_time")


class TestExternalFileLinks:
    """Test external video file linking."""

    def test_Should_LinkExternalFile_When_Enabled_Issue5(
        self,
        fixture_session_path,
        fixture_session_toml,
        tmp_work_dir,
    ):
        """Should create external_file links instead of embedding (FR-7)."""

        metadata = load_metadata(fixture_session_toml)
        nwbfile = create_nwb_file(metadata)

        video_path = str(fixture_session_path / "Video" / "top" / "cam0.avi")

        add_video_acquisition(nwbfile, camera_id="cam0_top", video_files=[video_path], frame_rate=30.0)

        output_dir = tmp_work_dir / "processed" / "Session-000001"
        output_dir.mkdir(parents=True, exist_ok=True)
        nwb_path = output_dir / "Session-000001_link.nwb"
        write_nwb_file(nwbfile, nwb_path)

        # Verify external file link
        with NWBHDF5IO(str(nwb_path), "r") as io:
            read_nwb = io.read()
            image_series = read_nwb.acquisition["cam0_top"]

            # Should have external_file attribute
            assert hasattr(image_series, "external_file")
            assert video_path in image_series.external_file[0]


class TestOptionalModalitiesIntegration:
    """Test integration of optional pose/facemap/bpod data."""

    def test_Should_IncludePose_When_DataProvided_Issue5(
        self,
        fixture_session_path,
        fixture_session_toml,
        tmp_work_dir,
    ):
        """Should include ndx-pose PoseEstimation when pose estimation provided (FR-7, FR-5)."""
        import numpy as np

        from w2t_bkin.ingest.pose import PoseMetadata, build_pose_estimation, create_skeleton

        metadata = load_metadata(fixture_session_toml)
        nwbfile = create_nwb_file(metadata)

        # Create harmonized pose data
        harmonized_data = [
            {
                "frame_index": 0,
                "keypoints": {
                    "nose": {"name": "nose", "x": 100.0, "y": 200.0, "confidence": 0.95},
                    "ear_left": {"name": "ear_left", "x": 90.0, "y": 190.0, "confidence": 0.92},
                    "ear_right": {"name": "ear_right", "x": 110.0, "y": 190.0, "confidence": 0.93},
                },
            },
            {
                "frame_index": 1,
                "keypoints": {
                    "nose": {"name": "nose", "x": 101.0, "y": 201.0, "confidence": 0.94},
                    "ear_left": {"name": "ear_left", "x": 91.0, "y": 191.0, "confidence": 0.91},
                    "ear_right": {"name": "ear_right", "x": 111.0, "y": 191.0, "confidence": 0.92},
                },
            },
        ]

        # Create metadata
        bodyparts = ["nose", "ear_left", "ear_right"]
        pose_meta = PoseMetadata(
            confidence_definition="Likelihood score",
            scorer="DLC_test_model",
            source_software="DeepLabCut",
            source_software_version="2.3.0",
            bodyparts=bodyparts,
        )

        # Build PoseEstimation
        camera_id = "cam0_top"
        skeleton = create_skeleton(camera_id, bodyparts, edges=[[0, 1], [0, 2]])

        pose_estimation = build_pose_estimation(
            data=(harmonized_data, pose_meta),
            reference_times=np.array([0.0, 0.033]),
            skeleton=skeleton,
        )

        # Add to NWBFile (requires creating processing module first)
        behavior_pm = nwbfile.create_processing_module(name="behavior", description="Behavioral data")
        behavior_pm.add(skeleton)
        behavior_pm.add(pose_estimation)

        output_dir = tmp_work_dir / "processed" / "Session-000001"
        output_dir.mkdir(parents=True, exist_ok=True)
        nwb_path = output_dir / "Session-000001_pose.nwb"
        write_nwb_file(nwbfile, nwb_path)

        # Verify pose included
        with NWBHDF5IO(str(nwb_path), "r", load_namespaces=True) as io:
            read_nwb = io.read()

            assert "behavior" in read_nwb.processing
            behavior_pm = read_nwb.processing["behavior"]

            pose_est_name = f"PoseEstimation_{camera_id}"
            assert pose_est_name in behavior_pm.data_interfaces
            pose_read = behavior_pm.data_interfaces[pose_est_name]

            assert "nose" in pose_read.pose_estimation_series


class TestProvenanceEmbedding:
    """Test provenance metadata embedding in NWB."""

    def test_Should_EmbedProvenance_When_Assembling_Issue5(
        self,
        fixture_session_toml,
        tmp_work_dir,
    ):
        """Should embed provenance metadata in NWB (NFR-11, A5)."""

        metadata = load_metadata(fixture_session_toml)

        # Add provenance to metadata notes or similar field before creation
        # Or modify NWBFile after creation
        provenance = {"config_hash": "abc123def456", "pipeline_version": "0.1.0"}
        metadata["notes"] = json.dumps(provenance)

        nwbfile = create_nwb_file(metadata)

        output_dir = tmp_work_dir / "processed" / "Session-000001"
        output_dir.mkdir(parents=True, exist_ok=True)
        nwb_path = output_dir / "Session-000001_prov.nwb"
        write_nwb_file(nwbfile, nwb_path)

        # Verify provenance embedded
        with NWBHDF5IO(str(nwb_path), "r") as io:
            read_nwb = io.read()
            assert read_nwb.notes is not None
            read_prov = json.loads(read_nwb.notes)
            assert read_prov["config_hash"] == "abc123def456"
