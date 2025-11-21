"""Unit tests for pose module (Phase 3 - Red Phase).

Tests pose import, harmonization, confidence preservation, and alignment
for both DeepLabCut and SLEAP formats.

Requirements: FR-5
Acceptance: A1, A3
GitHub Issue: #4
"""

import json
from pathlib import Path
from typing import List

from ndx_pose import PoseEstimation
import numpy as np
import pytest

from w2t_bkin.domain import PoseBundle, PoseFrame, PoseKeypoint
from w2t_bkin.pose import (
    PoseError,
    align_pose_to_timebase,
    build_pose_estimation,
    harmonize_dlc_to_canonical,
    harmonize_sleap_to_canonical,
    import_dlc_pose,
    import_sleap_pose,
    validate_pose_confidence,
)


class TestDLCImport:
    """Test DeepLabCut pose import."""

    def test_Should_ImportDLCH5_When_ValidFormatProvided(self):
        """Should successfully parse DLC H5 format."""
        h5_path = Path("tests/fixtures/pose/dlc/pose_sample.h5")

        result = import_dlc_pose(h5_path)

        assert result is not None
        assert len(result) > 0
        # Check that we have some keypoints
        assert len(result[0]["keypoints"]) > 0

    def test_Should_PreserveConfidence_When_ImportingDLC(self):
        """Should preserve likelihood scores as confidence (FR-5)."""
        h5_path = Path("tests/fixtures/pose/dlc/pose_sample.h5")

        result = import_dlc_pose(h5_path)

        for frame in result:
            for kp in frame["keypoints"]:
                assert "confidence" in kp
                assert 0.0 <= kp["confidence"] <= 1.0

    def test_Should_FailGracefully_When_DLCFileInvalid(self):
        """Should raise PoseError for invalid DLC files."""
        invalid_path = Path("nonexistent.h5")

        with pytest.raises(PoseError):
            import_dlc_pose(invalid_path)


class TestSLEAPImport:
    """Test SLEAP pose import."""

    @pytest.mark.skip(reason="SLEAP H5 fixture needs to be created with proper structure")
    def test_Should_ImportSLEAPH5_When_ValidFormatProvided(self):
        """Should successfully parse SLEAP H5 format."""
        h5_path = Path("tests/fixtures/pose/sleap/analysis.h5")

        result = import_sleap_pose(h5_path)

        assert result is not None
        assert len(result) > 0

    @pytest.mark.skip(reason="SLEAP H5 fixture needs to be created with proper structure")
    def test_Should_PreserveConfidence_When_ImportingSLEAP(self):
        """Should preserve instance scores as confidence (FR-5)."""
        h5_path = Path("tests/fixtures/pose/sleap/analysis.h5")

        result = import_sleap_pose(h5_path)

        for frame in result:
            for kp in frame["keypoints"]:
                assert "confidence" in kp
                assert 0.0 <= kp["confidence"] <= 1.0


class TestHarmonization:
    """Test pose harmonization to canonical skeleton."""

    def test_Should_HarmonizeDLCToCanonical_When_MappingProvided(self):
        """Should map DLC keypoints to canonical skeleton."""
        dlc_data = [
            {
                "frame_index": 0,
                "keypoints": {
                    "nose": {"x": 100.0, "y": 200.0, "confidence": 0.95},
                    "left_ear": {"x": 80.0, "y": 180.0, "confidence": 0.92},
                },
            }
        ]
        mapping = {"nose": "snout", "left_ear": "ear_left"}

        result = harmonize_dlc_to_canonical(dlc_data, mapping)

        assert "snout" in result[0]["keypoints"]
        assert "ear_left" in result[0]["keypoints"]
        assert result[0]["keypoints"]["snout"]["confidence"] == 0.95

    def test_Should_HarmonizeSLEAPToCanonical_When_MappingProvided(self):
        """Should map SLEAP keypoints to canonical skeleton."""
        sleap_data = [
            {
                "frame_index": 0,
                "keypoints": {
                    "nose": {"x": 100.0, "y": 200.0, "confidence": 0.96},
                },
            }
        ]
        mapping = {"nose": "snout"}

        result = harmonize_sleap_to_canonical(sleap_data, mapping)

        assert "snout" in result[0]["keypoints"]

    def test_Should_WarnForMissingKeypoints_When_NotAllMapped(self, caplog):
        """Should warn when keypoints can't be mapped."""
        dlc_data = [
            {
                "frame_index": 0,
                "keypoints": {
                    "unknown_part": {"x": 100.0, "y": 200.0, "confidence": 0.95},
                },
            }
        ]
        mapping = {"nose": "snout"}  # Doesn't include unknown_part

        result = harmonize_dlc_to_canonical(dlc_data, mapping)

        assert "unknown_part" in caplog.text or "not mapped" in caplog.text.lower()


class TestTimebaseAlignment:
    """Test pose alignment to reference timebase."""

    def test_Should_AlignPoseTimestamps_When_TimebaseProvided(self):
        """Should align pose frame indices to timebase timestamps (FR-5)."""
        pose_data = [
            {"frame_index": 0, "keypoints": {}},
            {"frame_index": 10, "keypoints": {}},
            {"frame_index": 20, "keypoints": {}},
        ]
        reference_times = [i * 0.033 for i in range(100)]  # 30 Hz

        result = align_pose_to_timebase(pose_data, reference_times, mapping="nearest")

        assert len(result) == len(pose_data)
        assert all("timestamp" in frame for frame in result)
        assert result[0]["timestamp"] == pytest.approx(0.0, abs=0.001)

    def test_Should_UseLinearMapping_When_Configured(self):
        """Should support linear interpolation for alignment."""
        pose_data = [
            {"frame_index": 5, "keypoints": {}},
        ]
        reference_times = [i * 0.033 for i in range(100)]

        result = align_pose_to_timebase(pose_data, reference_times, mapping="linear")

        assert result[0]["timestamp"] == pytest.approx(5 * 0.033, abs=0.001)

    def test_Should_FailAlignment_When_FrameIndexOutOfBounds(self):
        """Should raise error when pose frame index exceeds timebase length."""
        pose_data = [{"frame_index": 200, "keypoints": {}}]
        reference_times = [i * 0.033 for i in range(100)]

        with pytest.raises(PoseError):
            align_pose_to_timebase(pose_data, reference_times, mapping="nearest")


class TestConfidenceValidation:
    """Test pose confidence validation."""

    def test_Should_ComputeMeanConfidence_When_PoseDataProvided(self):
        """Should compute mean confidence across all keypoints."""
        pose_frames = [
            PoseFrame(
                frame_index=0,
                timestamp=0.0,
                keypoints=[
                    PoseKeypoint(name="nose", x=100.0, y=200.0, confidence=0.95),
                    PoseKeypoint(name="ear", x=80.0, y=180.0, confidence=0.90),
                ],
                source="dlc",
            )
        ]

        mean_conf = validate_pose_confidence(pose_frames)

        assert mean_conf == pytest.approx(0.925, abs=0.001)

    def test_Should_WarnForLowConfidence_When_BelowThreshold(self, caplog):
        """Should warn when confidence is below threshold."""
        pose_frames = [
            PoseFrame(
                frame_index=0,
                timestamp=0.0,
                keypoints=[
                    PoseKeypoint(name="nose", x=100.0, y=200.0, confidence=0.3),
                ],
                source="dlc",
            )
        ]

        mean_conf = validate_pose_confidence(pose_frames, threshold=0.8)

        assert mean_conf < 0.8
        assert "low confidence" in caplog.text.lower()


class TestPoseBundleCreation:
    """Test creation of PoseBundle artifacts."""

    def test_Should_CreatePoseBundle_When_AllDataProvided(self):
        """Should create valid PoseBundle with all required fields."""
        frames = [
            PoseFrame(
                frame_index=0,
                timestamp=0.0,
                keypoints=[
                    PoseKeypoint(name="nose", x=100.0, y=200.0, confidence=0.95),
                ],
                source="dlc",
            )
        ]

        bundle = PoseBundle(
            session_id="Session-000001",
            camera_id="cam0",
            model_name="DLC_model_v1",
            skeleton="canonical_mouse",
            frames=frames,
            alignment_method="nearest",
            mean_confidence=0.95,
            generated_at="2025-11-12T12:00:00Z",
        )

        assert bundle.session_id == "Session-000001"
        assert len(bundle.frames) == 1
        assert bundle.mean_confidence == 0.95

    def test_Should_EnforceFrozen_When_PoseBundleCreated(self):
        """PoseBundle should be immutable (NFR-7)."""
        bundle = PoseBundle(
            session_id="Session-000001",
            camera_id="cam0",
            model_name="DLC_model_v1",
            skeleton="canonical_mouse",
            frames=[],
            alignment_method="nearest",
            mean_confidence=0.95,
            generated_at="2025-11-12T12:00:00Z",
        )

        with pytest.raises(Exception):  # Pydantic frozen model error
            bundle.session_id = "modified"


class TestBuildPoseEstimation:
    """Test NWB-first pose estimation building (Step 1 of migration)."""

    def test_Should_BuildPoseEstimation_When_ValidDataProvided(self):
        """Should create ndx-pose PoseEstimation from harmonized data."""
        # Arrange: harmonized pose data (frame-major)
        data = [
            {
                "frame_index": 0,
                "keypoints": {
                    "nose": {"name": "nose", "x": 100.0, "y": 200.0, "confidence": 0.95},
                    "ear_left": {"name": "ear_left", "x": 80.0, "y": 180.0, "confidence": 0.90},
                },
            },
            {
                "frame_index": 1,
                "keypoints": {
                    "nose": {"name": "nose", "x": 102.0, "y": 201.0, "confidence": 0.93},
                    "ear_left": {"name": "ear_left", "x": 81.0, "y": 181.0, "confidence": 0.88},
                },
            },
        ]
        reference_times = [0.0, 0.033]
        bodyparts = ["nose", "ear_left"]

        # Act
        pe = build_pose_estimation(
            data=data,
            reference_times=reference_times,
            camera_id="cam0",
            bodyparts=bodyparts,
            skeleton_edges=[[0, 1]],
            source="dlc",
            model_name="test_model",
        )

        # Assert: PoseEstimation structure
        assert isinstance(pe, PoseEstimation)
        assert pe.name == "PoseEstimation_cam0"
        assert pe.scorer == "test_model"
        assert pe.source_software == "DeepLabCut"
        assert len(pe.pose_estimation_series) == 2

        # Assert: Skeleton
        assert pe.skeleton.nodes == bodyparts
        assert len(pe.skeleton.edges) == 1
        assert list(pe.skeleton.edges[0]) == [0, 1]

        # Assert: PoseEstimationSeries data (keypoint-major)
        nose_series = pe.pose_estimation_series["nose"]
        assert nose_series.name == "nose"
        assert nose_series.data.shape == (2, 2)  # (num_frames, 2) for x,y
        assert nose_series.data[0, 0] == pytest.approx(100.0)
        assert nose_series.data[0, 1] == pytest.approx(200.0)
        assert nose_series.confidence[0] == pytest.approx(0.95)

        # Assert: Timestamps (first series has timestamps, second links to it)
        assert nose_series.timestamps is not None
        assert len(nose_series.timestamps) == 2
        ear_series = pe.pose_estimation_series["ear_left"]
        # Linked series should have equal timestamps (ndx-pose handles the linking internally)
        assert np.array_equal(ear_series.timestamps, nose_series.timestamps)

    def test_Should_HandleMissingKeypoints_When_DataIncomplete(self):
        """Should use NaN for missing keypoints."""
        data = [
            {
                "frame_index": 0,
                "keypoints": {
                    "nose": {"name": "nose", "x": 100.0, "y": 200.0, "confidence": 0.95},
                    # ear_left missing
                },
            },
        ]
        reference_times = [0.0]
        bodyparts = ["nose", "ear_left"]

        pe = build_pose_estimation(
            data=data,
            reference_times=reference_times,
            camera_id="cam0",
            bodyparts=bodyparts,
            source="dlc",
            model_name="test_model",
        )

        # Nose should have valid data
        nose_series = pe.pose_estimation_series["nose"]
        assert nose_series.data[0, 0] == pytest.approx(100.0)

        # Ear should have NaN
        ear_series = pe.pose_estimation_series["ear_left"]
        assert np.isnan(ear_series.data[0, 0])
        assert np.isnan(ear_series.confidence[0])

    def test_Should_RaiseError_When_TimestampMismatch(self):
        """Should raise PoseError when timestamp count mismatches frame count."""
        data = [
            {"frame_index": 0, "keypoints": {}},
            {"frame_index": 1, "keypoints": {}},
        ]
        reference_times = [0.0]  # Only 1 timestamp for 2 frames

        with pytest.raises(PoseError, match="Timestamp count mismatch"):
            build_pose_estimation(
                data=data,
                reference_times=reference_times,
                camera_id="cam0",
                bodyparts=["nose"],
                source="dlc",
                model_name="test_model",
            )

    def test_Should_RaiseError_When_EmptyData(self):
        """Should raise PoseError for empty data."""
        with pytest.raises(PoseError, match="empty data"):
            build_pose_estimation(
                data=[],
                reference_times=[],
                camera_id="cam0",
                bodyparts=["nose"],
                source="dlc",
                model_name="test_model",
            )

    def test_Should_CreateEmptyEdges_When_SkeletonEdgesNone(self):
        """Should handle None skeleton_edges gracefully."""
        data = [
            {
                "frame_index": 0,
                "keypoints": {
                    "nose": {"name": "nose", "x": 100.0, "y": 200.0, "confidence": 0.95},
                },
            },
        ]
        reference_times = [0.0]

        pe = build_pose_estimation(
            data=data,
            reference_times=reference_times,
            camera_id="cam0",
            bodyparts=["nose"],
            skeleton_edges=None,
            source="dlc",
            model_name="test_model",
        )

        assert pe.skeleton.edges.shape == (0, 2)

    def test_Should_SetSLEAPSource_When_SourceIsSLEAP(self):
        """Should set source_software to SLEAP when source is sleap."""
        data = [
            {
                "frame_index": 0,
                "keypoints": {
                    "nose": {"name": "nose", "x": 100.0, "y": 200.0, "confidence": 0.95},
                },
            },
        ]
        reference_times = [0.0]

        pe = build_pose_estimation(
            data=data,
            reference_times=reference_times,
            camera_id="cam0",
            bodyparts=["nose"],
            source="sleap",
            model_name="sleap_model",
        )

        assert pe.source_software == "SLEAP"
        assert pe.source_software_version == "1.3.x"

    def test_Should_IntegrateWithHarmonization_When_ChainedWithDLC(self):
        """Integration: harmonize DLC → build PoseEstimation."""
        # Import real DLC data
        h5_path = Path("tests/fixtures/pose/dlc/pose_sample.h5")
        raw_data = import_dlc_pose(h5_path)

        # Create simple mapping (first bodypart from DLC data)
        # In real usage, this comes from config or mapping file
        first_frame = raw_data[0]
        bodypart_name = list(first_frame["keypoints"].keys())[0]
        mapping = {bodypart_name: bodypart_name}  # Identity mapping for simplicity

        # Harmonize
        harmonized = harmonize_dlc_to_canonical(raw_data, mapping)

        # Build PoseEstimation
        bodyparts = list(mapping.values())
        reference_times = [i * 0.033 for i in range(len(harmonized))]

        pe = build_pose_estimation(
            data=harmonized,
            reference_times=reference_times,
            camera_id="cam0",
            bodyparts=bodyparts,
            source="dlc",
            model_name="dlc_integration_test",
        )

        # Verify structure
        assert isinstance(pe, PoseEstimation)
        assert len(pe.pose_estimation_series) == len(bodyparts)
        assert pe.pose_estimation_series[bodyparts[0]].data.shape[0] == len(harmonized)


class TestAlignPoseToTimebaseNWBFirst:
    """Test NWB-first mode of align_pose_to_timebase (Step 2 of migration)."""

    def test_Should_ReturnPoseEstimation_When_CameraIdProvided(self):
        """Should return PoseEstimation instead of List[PoseFrame] when camera_id provided."""
        # Arrange: harmonized data
        data = [
            {
                "frame_index": 0,
                "keypoints": {
                    "nose": {"name": "nose", "x": 100.0, "y": 200.0, "confidence": 0.95},
                },
            },
            {
                "frame_index": 1,
                "keypoints": {
                    "nose": {"name": "nose", "x": 102.0, "y": 201.0, "confidence": 0.93},
                },
            },
        ]
        reference_times = [0.0, 0.033]

        # Act: NWB-first mode
        result = align_pose_to_timebase(
            data=data,
            reference_times=reference_times,
            camera_id="cam0",
            bodyparts=["nose"],
            source="dlc",
            model_name="test_model",
        )

        # Assert: Returns PoseEstimation
        assert isinstance(result, PoseEstimation)
        assert result.name == "PoseEstimation_cam0"
        assert "nose" in result.pose_estimation_series
        assert result.pose_estimation_series["nose"].data.shape[0] == 2

    def test_Should_PreserveBackwardCompatibility_When_CameraIdNotProvided(self):
        """Should return List[PoseFrame] for backward compatibility when camera_id is None."""
        data = [
            {
                "frame_index": 0,
                "keypoints": {
                    "nose": {"name": "nose", "x": 100.0, "y": 200.0, "confidence": 0.95},
                },
            },
        ]
        reference_times = [0.0]

        # Act: Legacy mode (no camera_id)
        result = align_pose_to_timebase(data=data, reference_times=reference_times, source="dlc")

        # Assert: Returns list of PoseFrame
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], PoseFrame)
        assert result[0].timestamp == pytest.approx(0.0)

    def test_Should_RaiseError_When_CameraIdProvidedButBodypartsMissing(self):
        """Should raise ValueError if camera_id provided without bodyparts."""
        data = [{"frame_index": 0, "keypoints": {}}]
        reference_times = [0.0]

        with pytest.raises(ValueError, match="bodyparts parameter required"):
            align_pose_to_timebase(
                data=data,
                reference_times=reference_times,
                camera_id="cam0",
                # bodyparts missing
                source="dlc",
            )

    def test_Should_HandleSkeletonEdges_When_Provided(self):
        """Should pass skeleton edges to PoseEstimation."""
        data = [
            {
                "frame_index": 0,
                "keypoints": {
                    "nose": {"name": "nose", "x": 100.0, "y": 200.0, "confidence": 0.95},
                    "ear": {"name": "ear", "x": 80.0, "y": 180.0, "confidence": 0.90},
                },
            },
        ]
        reference_times = [0.0]

        result = align_pose_to_timebase(
            data=data,
            reference_times=reference_times,
            camera_id="cam0",
            bodyparts=["nose", "ear"],
            skeleton_edges=[[0, 1]],
            source="dlc",
        )

        assert isinstance(result, PoseEstimation)
        assert len(result.skeleton.edges) == 1

    def test_Should_UseLinearMapping_When_MappingIsLinear(self):
        """Should support linear mapping in NWB-first mode."""
        data = [
            {"frame_index": 0, "keypoints": {"nose": {"name": "nose", "x": 100.0, "y": 200.0, "confidence": 0.95}}},
            {"frame_index": 1, "keypoints": {"nose": {"name": "nose", "x": 102.0, "y": 201.0, "confidence": 0.93}}},
        ]
        reference_times = [0.0, 0.033]

        result = align_pose_to_timebase(
            data=data,
            reference_times=reference_times,
            mapping="linear",
            camera_id="cam0",
            bodyparts=["nose"],
            source="dlc",
        )

        assert isinstance(result, PoseEstimation)
        # Verify timestamps are used
        nose_series = result.pose_estimation_series["nose"]
        assert len(nose_series.timestamps) == 2
