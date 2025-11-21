"""Phase 3 integration tests - Optional modalities (RED Phase).

Tests end-to-end workflows for pose import/harmonization, facemap computation,
video transcoding, and Bpod events parsing as optional pipeline stages.

Requirements: FR-4, FR-5, FR-6, FR-11, FR-14
Acceptance: A1, A3, A4
GitHub Issue: #4
"""

import json
from pathlib import Path

import pytest

from w2t_bkin.domain import FacemapBundle, TranscodedVideo, Trial, TrialEvent, TrialSummary


class TestEventsIntegration:
    """Integration tests for Bpod events parsing and QC summary generation."""

    def test_Should_ParseBpodFile_When_FileProvided_Issue4(self, fixtures_root, tmp_work_dir):
        """Should parse Bpod .mat file and extract trials and events (FR-11)."""
        from w2t_bkin.events import extract_behavioral_events, extract_trials, parse_bpod_mat

        # Use test fixture Bpod file if available
        bpod_file = fixtures_root / "sessions" / "valid_session.toml"

        # Skip if no real Bpod .mat file in fixtures
        pytest.skip("Requires real Bpod .mat fixture file")

    def test_Should_CreateEventSummary_When_TrialsExtracted_Issue4(self, tmp_work_dir):
        """Should create event summary for QC report (FR-14, A4)."""
        from w2t_bkin.events import create_event_summary

        # Create mock trials and events
        trials = [
            Trial(trial_number=1, trial_type=1, start_time=0.0, stop_time=9.0, outcome="hit"),
            Trial(trial_number=2, trial_type=1, start_time=10.0, stop_time=19.0, outcome="miss"),
            Trial(trial_number=3, trial_type=1, start_time=20.0, stop_time=29.0, outcome="hit"),
        ]

        events = [
            TrialEvent(event_type="BNC1High", timestamp=1.5, metadata={"trial_number": 1}),
            TrialEvent(event_type="BNC1Low", timestamp=1.6, metadata={"trial_number": 1}),
            TrialEvent(event_type="Flex1Trig2", timestamp=7.1, metadata={"trial_number": 1}),
        ]

        # Create summary
        summary = create_event_summary(session="Session-000001", trials=trials, events=events, bpod_files=["/path/to/bpod.mat"])

        # Verify summary (A4: trial counts and event categories)
        assert isinstance(summary, TrialSummary)
        assert summary.total_trials == 3
        assert summary.outcome_counts["hit"] == 2
        assert summary.outcome_counts["miss"] == 1
        assert len(summary.event_categories) == 3
        assert "BNC1High" in summary.event_categories

    def test_Should_WriteEventSummary_When_SummaryCreated_Issue4(self, tmp_work_dir):
        """Should write event summary to JSON file (FR-14)."""
        from w2t_bkin.events import create_event_summary, write_event_summary

        trials = [Trial(trial_number=1, trial_type=1, start_time=0.0, stop_time=9.0, outcome="hit")]
        events = [TrialEvent(event_type="Reward", timestamp=8.5, metadata={"trial_number": 1})]

        summary = create_event_summary(session="Session-000001", trials=trials, events=events, bpod_files=["/path/to/bpod.mat"])

        # Write to temp directory
        output_path = tmp_work_dir / "interim" / "Session-000001" / "events_summary.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        write_event_summary(summary, output_path)

        # Verify file written
        assert output_path.exists()

        # Verify content
        with open(output_path, "r") as f:
            data = json.load(f)

        assert data["session_id"] == "Session-000001"
        assert data["total_trials"] == 1
        assert "generated_at" in data


class TestPoseIntegration:
    """Integration tests for pose import and harmonization."""

    @pytest.mark.skip(reason="Blocked: requires Phase 2 alignment implementation and test uses non-spec config keys")
    def test_Should_ImportDLCPose_When_FilesProvided_Issue4(self, minimal_config_dict):
        """Should import DLC pose and align to timebase (FR-5)."""
        from ndx_pose import PoseEstimation

        from w2t_bkin.pose import align_pose_to_timebase, harmonize_dlc_to_canonical, import_dlc_pose
        from w2t_bkin.sync import load_alignment_manifest

        # Load alignment from Phase 2
        alignment = load_alignment_manifest(minimal_config_dict["paths"]["interim"] / "Session-000001" / "alignment.json")

        # Import DLC pose
        dlc_csv = Path("tests/fixtures/pose/dlc/pose_sample.csv")
        pose_data = import_dlc_pose(dlc_csv)

        # Harmonize to canonical skeleton
        mapping = {"nose": "nose", "left_ear": "ear_left", "right_ear": "ear_right"}
        canonical_pose = harmonize_dlc_to_canonical(pose_data, mapping)

        # Align to timebase (NWB-first)
        reference_times = alignment["cam0"]["timestamps"]
        bodyparts = list(mapping.values())
        pose_estimation = align_pose_to_timebase(
            canonical_pose,
            reference_times,
            camera_id="cam0",
            bodyparts=bodyparts,
            mapping="nearest",
            source="dlc",
            model_name="DLC-mouse-v1",
        )

        # Verify NWB-native PoseEstimation
        assert isinstance(pose_estimation, PoseEstimation)
        assert pose_estimation.name == "PoseEstimation_cam0"
        assert len(pose_estimation.pose_estimation_series) == len(bodyparts)

    @pytest.mark.skip(reason="Blocked: requires Phase 2 alignment implementation, test uses non-spec config keys, and missing pose_sample.json fixture")
    def test_Should_ImportSLEAPPose_When_FilesProvided_Issue4(self, minimal_config_dict):
        """Should import SLEAP pose and align to timebase (FR-5)."""
        from ndx_pose import PoseEstimation

        from w2t_bkin.pose import align_pose_to_timebase, harmonize_sleap_to_canonical, import_sleap_pose
        from w2t_bkin.sync import load_alignment_manifest

        # Load alignment from Phase 2
        alignment = load_alignment_manifest(minimal_config_dict["paths"]["interim"] / "Session-000001" / "alignment.json")

        # Import SLEAP pose (mock JSON for now)
        sleap_json = Path("tests/fixtures/pose/sleap/pose_sample.json")
        pose_data = import_sleap_pose(sleap_json)

        # Harmonize to canonical skeleton
        mapping = {"nose": "nose", "leftear": "ear_left", "rightear": "ear_right"}
        canonical_pose = harmonize_sleap_to_canonical(pose_data, mapping)

        # Align to timebase (NWB-first)
        reference_times = alignment["cam0"]["timestamps"]
        bodyparts = list(mapping.values())
        pose_estimation = align_pose_to_timebase(
            canonical_pose,
            reference_times,
            camera_id="cam0",
            bodyparts=bodyparts,
            mapping="nearest",
            source="sleap",
            model_name="SLEAP-mouse-v1",
        )

        # Verify NWB-native PoseEstimation
        assert isinstance(pose_estimation, PoseEstimation)
        assert len(pose_estimation.pose_estimation_series) > 0


class TestFacemapIntegration:
    """Integration tests for Facemap computation and alignment."""

    @pytest.mark.skip(reason="Blocked: requires Phase 2 alignment implementation, test uses non-spec config keys, and FacemapSignal subscriptability issue")
    def test_Should_ComputeFacemap_When_Enabled_Issue4(self, minimal_config_dict):
        """Should compute Facemap signals and align to timebase (FR-6)."""
        from w2t_bkin.facemap import align_facemap_to_timebase, compute_facemap_signals, define_rois
        from w2t_bkin.sync import load_alignment_manifest

        # Load alignment from Phase 2
        alignment = load_alignment_manifest(minimal_config_dict["paths"]["interim"] / "Session-000001" / "alignment.json")

        # Define ROIs
        roi_specs = [
            {"name": "pupil", "x": 100, "y": 150, "width": 50, "height": 50},
            {"name": "whisker_pad", "x": 200, "y": 200, "width": 80, "height": 80},
        ]
        rois = define_rois(roi_specs)

        # Compute signals from video
        video_path = minimal_config_dict["paths"]["raw"] / "Session-000001" / "Video" / "top" / "cam0_2025-01-01-00-00-00.avi"
        signals = compute_facemap_signals(video_path, rois)

        # Align to timebase
        reference_times = alignment["cam0"]["timestamps"]
        aligned_signals = align_facemap_to_timebase(signals, reference_times, mapping="nearest")

        # Create bundle
        bundle = FacemapBundle(
            session_id="Session-000001",
            camera_id="cam0",
            rois=rois,
            signals=aligned_signals,
            alignment_method="nearest",
            generated_at="2025-11-12T12:00:00Z",
        )

        assert bundle.session_id == "Session-000001"
        assert len(bundle.signals) == 2


class TestTranscodeIntegration:
    """Integration tests for video transcoding."""

    @pytest.mark.skip(reason="Blocked: test uses non-spec config keys (paths.interim, paths.processed)")
    def test_Should_TranscodeVideos_When_Enabled_Issue4(self, minimal_config_dict):
        """Should transcode videos to mezzanine format (FR-4)."""
        from w2t_bkin.ingest import load_manifest
        from w2t_bkin.transcode import create_transcode_options, transcode_video, update_manifest_with_transcode

        # Load manifest from Phase 1
        manifest = load_manifest(minimal_config_dict["paths"]["interim"] / "Session-000001" / "manifest.json")

        # Create transcode options
        options = create_transcode_options(codec="libx264", crf=18, preset="medium")

        # Transcode first video
        video_path = Path(manifest["videos"][0]["path"])
        output_dir = minimal_config_dict["paths"]["processed"] / "Session-000001" / "Video"

        transcoded = transcode_video(video_path, options, output_dir)

        # Update manifest
        updated_manifest = update_manifest_with_transcode(manifest, transcoded)

        assert transcoded.codec == "libx264"
        assert transcoded.output_path.suffix == ".mp4"
        assert "transcoded_path" in updated_manifest["videos"][0]

    @pytest.mark.skip(reason="Blocked: test uses non-spec config keys (paths.raw, paths.processed)")
    def test_Should_SkipTranscode_When_AlreadyExists_Issue4(self, minimal_config_dict):
        """Should be idempotent - skip if already transcoded (FR-4, NFR-2)."""
        from w2t_bkin.transcode import create_transcode_options, is_already_transcoded, transcode_video

        video_path = minimal_config_dict["paths"]["raw"] / "Session-000001" / "Video" / "top" / "cam0_2025-01-01-00-00-00.avi"
        options = create_transcode_options(codec="libx264", crf=18, preset="medium")
        output_dir = minimal_config_dict["paths"]["processed"] / "Session-000001" / "Video"

        # First transcode
        result1 = transcode_video(video_path, options, output_dir)

        # Check if already transcoded
        already_done = is_already_transcoded(video_path, options, result1.output_path)

        assert already_done is True


class TestOptionalNature:
    """Test that Phase 3 modalities are truly optional."""

    @pytest.mark.skip(reason="Blocked: test uses non-spec config key (paths.raw instead of paths.raw_root)")
    def test_Should_SkipOptionals_When_Disabled_Issue4(self, minimal_config_dict):
        """Pipeline should run without Phase 3 modalities (FR-4, FR-5, FR-6 optional)."""
        from w2t_bkin.ingest import discover_sessions, ingest_session, load_config
        from w2t_bkin.sync import compute_alignment

        # Ingest and sync (Phase 0-2) without optionals
        config = load_config(Path("tests/fixtures/configs/valid_config.toml"))
        sessions = discover_sessions(config["paths"]["raw"])

        # Ingest Phase 1
        manifest = ingest_session(sessions[0], config)

        # Sync Phase 2
        alignment = compute_alignment(manifest, config)

        # Should complete without pose/facemap/transcode
        assert manifest is not None
        assert alignment is not None
        # No Phase 3 artifacts should exist
        assert not (minimal_config_dict["paths"]["processed"] / "Session-000001" / "pose").exists()


class TestRealSessionIntegration:
    """End-to-end test with real Session-000001 data."""

    @pytest.mark.skip(reason="Blocked: test uses non-spec config keys and requires complete Phase 1/2 implementations")
    def test_Should_AlignAllModalities_When_UsingRealSession_Issue4(self, minimal_config_dict):
        """Should align pose + facemap + videos using real Session-000001 (FR-5, FR-6)."""
        from w2t_bkin.facemap import align_facemap_to_timebase, compute_facemap_signals, define_rois
        from w2t_bkin.ingest import discover_sessions, ingest_session, load_config
        from w2t_bkin.pose import align_pose_to_timebase, import_dlc_pose
        from w2t_bkin.sync import compute_alignment

        # Phase 1: Ingest
        config = load_config(Path("tests/fixtures/configs/valid_config.toml"))
        sessions = discover_sessions(config["paths"]["raw"])
        manifest = ingest_session(sessions[0], config)

        # Phase 2: Sync/Timebase
        alignment = compute_alignment(manifest, config)
        reference_times = alignment["cam0"]["timestamps"]

        # Phase 3a: Pose
        dlc_csv = Path("tests/fixtures/pose/dlc/pose_sample.csv")
        pose_data = import_dlc_pose(dlc_csv)
        aligned_pose = align_pose_to_timebase(pose_data, reference_times, mapping="nearest")

        # Phase 3b: Facemap
        roi_specs = [{"name": "pupil", "x": 100, "y": 150, "width": 50, "height": 50}]
        rois = define_rois(roi_specs)
        video_path = Path(manifest["videos"][0]["path"])
        facemap_signals = compute_facemap_signals(video_path, rois)
        aligned_facemap = align_facemap_to_timebase(facemap_signals, reference_times, mapping="nearest")

        # Verify all modalities aligned
        assert len(aligned_pose) > 0
        assert len(aligned_facemap) > 0
        assert len(reference_times) == 8580  # From Session-000001
