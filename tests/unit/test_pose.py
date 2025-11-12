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

import pytest

from w2t_bkin.domain import PoseBundle, PoseFrame, PoseKeypoint
from w2t_bkin.pose import (
    PoseError,
    harmonize_dlc_to_canonical,
    harmonize_sleap_to_canonical,
    import_dlc_pose,
    import_sleap_pose,
    align_pose_to_timebase,
    validate_pose_confidence,
)


class TestDLCImport:
    """Test DeepLabCut pose import."""

    def test_Should_ImportDLCCSV_When_ValidFormatProvided(self):
        """Should successfully parse DLC CSV format."""
        # This test will fail because pose module doesn't exist yet
        csv_path = Path("tests/fixtures/pose/dlc/pose_sample.csv")
        
        result = import_dlc_pose(csv_path)
        
        assert result is not None
        assert len(result) > 0
        assert "nose" in result[0]["keypoints"]

    def test_Should_PreserveConfidence_When_ImportingDLC(self):
        """Should preserve likelihood scores as confidence (FR-5)."""
        csv_path = Path("tests/fixtures/pose/dlc/pose_sample.csv")
        
        result = import_dlc_pose(csv_path)
        
        for frame in result:
            for kp in frame["keypoints"]:
                assert "confidence" in kp
                assert 0.0 <= kp["confidence"] <= 1.0

    def test_Should_FailGracefully_When_DLCFileInvalid(self):
        """Should raise PoseError for invalid DLC files."""
        invalid_path = Path("nonexistent.csv")
        
        with pytest.raises(PoseError):
            import_dlc_pose(invalid_path)


class TestSLEAPImport:
    """Test SLEAP pose import."""

    def test_Should_ImportSLEAPH5_When_ValidFormatProvided(self):
        """Should successfully parse SLEAP H5 format."""
        h5_path = Path("tests/fixtures/pose/sleap/analysis.h5")
        
        result = import_sleap_pose(h5_path)
        
        assert result is not None
        assert len(result) > 0

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
                }
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
                }
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
                }
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
