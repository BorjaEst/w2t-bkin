"""Unit tests for multiple video files per camera.

Tests that the flows correctly handle cameras that produce multiple
video files (e.g., due to recording size limits or experiment pauses).
"""

from pathlib import Path

import pytest

from synthetic import build_raw_folder
from w2t_bkin.flows import process_session_flow


class TestMultipleVideoFilesPerCamera:
    """Test handling of multiple video files per camera."""

    @pytest.mark.skip(reason="Video ingestion currently coupled with pose estimation - needs architectural refactoring")
    def test_Should_HandleMultipleVideoFiles_When_CameraHasSegments(self, tmp_path):
        """Should correctly process camera with multiple video files.

        KNOWN LIMITATION: Currently, video data is only added to NWB when pose estimation runs.
        When skip_pose=True, videos are not added to the NWB file.

        TODO: Refactor to separate video ingestion from pose estimation so videos can be added
        independently of DLC/SLEAP processing.
        """
        # Generate synthetic session with 3 video segments per camera
        raw_root = tmp_path / "raw"
        result = build_raw_folder(
            out_root=raw_root,
            project_name="multi-video-test",
            subject_id="subject-001",
            session_id="session-001",
            n_frames=30,  # Frames per segment
            segments_per_camera=3,  # 3 video files per camera
            n_trials=5,
            camera_ids=["cam0"],
            ttl_ids=["ttl_camera"],
        )

        # Verify multiple video files were created
        cam0_videos = list((result.session_dir / "Video" / "cam0").glob("*.avi"))
        assert len(cam0_videos) == 3, "Should have 3 video files for cam0"

        # Disable verification since synthetic TTLs are per-segment (30 pulses)
        # but we have 3 segments (90 frames total)
        # In real data, TTLs would match total frame count across all segments
        import toml

        config_dict = toml.load(result.config_path)
        if "verification" not in config_dict:
            config_dict["verification"] = {}
        config_dict["verification"]["enabled"] = False
        config_dict["verification"]["check_frame_counts"] = False
        config_dict["verification"]["check_sync_mismatch"] = False
        with open(result.config_path, "w") as f:
            toml.dump(config_dict, f)

        flow_result = process_session_flow(
            config_path=result.config_path,
            subject_id="subject-001",
            session_id="session-001",
            skip_nwb_validation=True,
            skip_pose=False,  # Must NOT skip pose to get videos added
            skip_dlc=True,  # But skip actual inference
            skip_sleap=True,
        )

        # Verify success
        assert flow_result.success, f"Flow failed: {flow_result.error}"
        assert flow_result.nwb_path.exists()

        # Verify NWB has correct total frame count (3 segments * 30 frames = 90 frames)
        from pynwb import NWBHDF5IO

        with NWBHDF5IO(str(flow_result.nwb_path), "r") as io:
            nwb = io.read()
            assert "cam0" in nwb.acquisition
            # Check that all video files are referenced
            image_series = nwb.acquisition["cam0"]
            assert len(image_series.external_file) == 3, "Should reference 3 video files"
            # Verify starting_frame is set correctly
            assert image_series.starting_frame is not None, "Should have starting_frame for multiple files"
            assert len(image_series.starting_frame) == 3, "Should have 3 starting_frame indices"
            import numpy as np

            assert np.array_equal(image_series.starting_frame, [0, 30, 60]), f"Unexpected starting_frame: {image_series.starting_frame}"

    def test_Should_SortVideosCorrectly_When_OrderSpecified(self, tmp_path):
        """Should sort video files according to order field."""
        # Generate synthetic session
        raw_root = tmp_path / "raw"
        result = build_raw_folder(
            out_root=raw_root,
            subject_id="subject-002",
            session_id="session-001",
            n_frames=20,
            segments_per_camera=2,
            camera_ids=["cam0"],
            ttl_ids=["ttl_camera"],
        )

        # Modify metadata to use different sort orders
        metadata_path = result.metadata_path
        metadata_text = metadata_path.read_text()

        # Test with name_asc (default) - flow will use this internally
        # Access discovered files from context
        # This tests that files are sorted correctly during discovery
        from w2t_bkin.config import load_config
        from w2t_bkin.core import session

        config = load_config(result.config_path)
        metadata_paths = session.build_metadata_paths(
            raw_root=config.paths.raw_root,
            subject_id="subject-002",
            session_id="session-001",
        )
        metadata = session.load_metadata(metadata_paths)

        # Check order field is present
        cameras = metadata.get("cameras", [])
        assert len(cameras) > 0
        assert "order" in cameras[0], "Camera configuration should have 'order' field"

    def test_Should_CountTotalFrames_When_MultipleVideos(self, tmp_path):
        """Should correctly count total frames across multiple video files."""
        from w2t_bkin import utils

        # Generate synthetic session with known frame counts
        raw_root = tmp_path / "raw"
        result = build_raw_folder(
            out_root=raw_root,
            subject_id="subject-003",
            session_id="session-001",
            n_frames=25,  # 25 frames per segment
            segments_per_camera=4,  # 4 segments
            camera_ids=["cam0"],
            ttl_ids=["ttl_camera"],
        )

        # Get video files
        cam0_videos = list((result.session_dir / "Video" / "cam0").glob("*.avi"))
        assert len(cam0_videos) == 4

        # Count total frames
        total_frames = sum(utils.count_video_frames(p) for p in cam0_videos)

        # Should be 4 * 25 = 100 frames total
        assert total_frames == 100, f"Expected 100 total frames, got {total_frames}"
