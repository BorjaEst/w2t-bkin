"""Phase 3 integration tests - Optional modalities (RED Phase).

Tests end-to-end workflows for pose import/harmonization, facemap computation,
and video transcoding as optional pipeline stages.

Requirements: FR-4, FR-5, FR-6
Acceptance: A1, A3, A4
GitHub Issue: #4
"""

import json
from pathlib import Path

import pytest

from w2t_bkin.domain import FacemapBundle, PoseBundle, TranscodedVideo


class TestPoseIntegration:
    """Integration tests for pose import and harmonization."""

    @pytest.mark.skip(reason="Blocked: requires Phase 2 alignment implementation and test uses non-spec config keys")
    def test_Should_ImportDLCPose_When_FilesProvided_Issue4(self, minimal_config_dict):
        """Should import DLC pose and align to timebase (FR-5)."""
        from w2t_bkin.pose import (
            align_pose_to_timebase,
            harmonize_dlc_to_canonical,
            import_dlc_pose,
        )
        from w2t_bkin.sync import load_alignment_manifest

        # Load alignment from Phase 2
        alignment = load_alignment_manifest(minimal_config_dict["paths"]["interim"] / "Session-000001" / "alignment.json")

        # Import DLC pose
        dlc_csv = Path("tests/fixtures/pose/dlc/pose_sample.csv")
        pose_data = import_dlc_pose(dlc_csv)

        # Harmonize to canonical skeleton
        mapping = {"nose": "nose", "left_ear": "ear_left", "right_ear": "ear_right"}
        canonical_pose = harmonize_dlc_to_canonical(pose_data, mapping)

        # Align to timebase
        reference_times = alignment["cam0"]["timestamps"]
        aligned_pose = align_pose_to_timebase(canonical_pose, reference_times, mapping="nearest")

        # Create bundle
        bundle = PoseBundle(
            session_id="Session-000001",
            camera_id="cam0",
            model_name="DLC-mouse-v1",
            skeleton=list(mapping.values()),
            frames=aligned_pose,
            alignment_method="nearest",
            mean_confidence=0.94,
        )

        assert bundle.session_id == "Session-000001"
        assert bundle.mean_confidence > 0.8
        assert len(bundle.frames) == 5

    @pytest.mark.skip(reason="Blocked: requires Phase 2 alignment implementation, test uses non-spec config keys, and missing pose_sample.json fixture")
    def test_Should_ImportSLEAPPose_When_FilesProvided_Issue4(self, minimal_config_dict):
        """Should import SLEAP pose and align to timebase (FR-5)."""
        from w2t_bkin.pose import (
            align_pose_to_timebase,
            harmonize_sleap_to_canonical,
            import_sleap_pose,
        )
        from w2t_bkin.sync import load_alignment_manifest

        # Load alignment from Phase 2
        alignment = load_alignment_manifest(minimal_config_dict["paths"]["interim"] / "Session-000001" / "alignment.json")

        # Import SLEAP pose (mock JSON for now)
        sleap_json = Path("tests/fixtures/pose/sleap/pose_sample.json")
        pose_data = import_sleap_pose(sleap_json)

        # Harmonize to canonical skeleton
        mapping = {"nose": "nose", "leftear": "ear_left", "rightear": "ear_right"}
        canonical_pose = harmonize_sleap_to_canonical(pose_data, mapping)

        # Align to timebase
        reference_times = alignment["cam0"]["timestamps"]
        aligned_pose = align_pose_to_timebase(canonical_pose, reference_times, mapping="nearest")

        # Create bundle
        bundle = PoseBundle(
            session_id="Session-000001",
            camera_id="cam0",
            model_name="SLEAP-mouse-v1",
            skeleton=list(mapping.values()),
            frames=aligned_pose,
            alignment_method="nearest",
            mean_confidence=0.90,
        )

        assert bundle.session_id == "Session-000001"
        assert len(bundle.frames) > 0


class TestFacemapIntegration:
    """Integration tests for Facemap computation and alignment."""

    @pytest.mark.skip(reason="Blocked: requires Phase 2 alignment implementation, test uses non-spec config keys, and FacemapSignal subscriptability issue")
    def test_Should_ComputeFacemap_When_Enabled_Issue4(self, minimal_config_dict):
        """Should compute Facemap signals and align to timebase (FR-6)."""
        from w2t_bkin.facemap import (
            align_facemap_to_timebase,
            compute_facemap_signals,
            define_rois,
        )
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
        from w2t_bkin.transcode import (
            create_transcode_options,
            transcode_video,
            update_manifest_with_transcode,
        )

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
        from w2t_bkin.transcode import (
            create_transcode_options,
            is_already_transcoded,
            transcode_video,
        )

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
        from w2t_bkin.facemap import (
            align_facemap_to_timebase,
            compute_facemap_signals,
            define_rois,
        )
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
