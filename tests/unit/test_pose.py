"""Unit tests for the pose module.

Tests pose estimation import and harmonization as specified in
requirements.md FR-5 and design.md.

All tests follow TDD Red Phase principles with clear EARS requirements.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


# ============================================================================
# Test: Pose File Parsing (FR-5)
# ============================================================================


class TestPoseFileParsing:
    """Test pose file import from DLC and SLEAP (FR-5)."""

    def test_Should_ParseDLCH5File_When_ValidFormat_Issue_Pose_FR5(self, tmp_path: Path):
        """THE SYSTEM SHALL parse DeepLabCut H5 files for pose data.

        Requirements: FR-5 (Import DLC outputs)
        Issue: Pose module - DLC file parsing
        """
        # Arrange
        from w2t_bkin.pose import harmonize_pose

        dlc_file = tmp_path / "pose_dlc.h5"
        dlc_file.write_text("mock DLC h5 data")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Act
        summary = harmonize_pose(dlc_file, format="dlc", output_dir=output_dir)

        # Assert - Should successfully parse DLC file
        assert summary is not None
        assert hasattr(summary, "source_format")
        assert summary.source_format == "dlc"

    def test_Should_ParseSLEAPFile_When_ValidFormat_Issue_Pose_FR5(self, tmp_path: Path):
        """THE SYSTEM SHALL parse SLEAP files for pose data.

        Requirements: FR-5 (Import SLEAP outputs)
        Issue: Pose module - SLEAP file parsing
        """
        # Arrange
        from w2t_bkin.pose import harmonize_pose

        sleap_file = tmp_path / "pose.slp"
        sleap_file.write_text("mock SLEAP data")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Act
        summary = harmonize_pose(sleap_file, format="sleap", output_dir=output_dir)

        # Assert - Should successfully parse SLEAP file
        assert summary is not None
        assert hasattr(summary, "source_format")
        assert summary.source_format == "sleap"

    def test_Should_RaiseMissingInputError_When_FileNotFound_Issue_Pose_NFR8(self, tmp_path: Path):
        """THE SYSTEM SHALL fail fast when pose file is missing.

        Requirements: NFR-8 (Data integrity)
        Issue: Pose module - Input validation
        """
        # Arrange
        from w2t_bkin.pose import harmonize_pose

        missing_file = tmp_path / "nonexistent.h5"
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Act & Assert - Should raise MissingInputError
        with pytest.raises(Exception):  # MissingInputError
            harmonize_pose(missing_file, format="dlc", output_dir=output_dir)

    def test_Should_RaisePoseFormatError_When_InvalidFormat_Issue_Pose_Design(self, tmp_path: Path):
        """THE SYSTEM SHALL reject invalid pose file formats.

        Requirements: Design - Error handling
        Issue: Pose module - Format validation
        """
        # Arrange
        from w2t_bkin.pose import harmonize_pose

        invalid_file = tmp_path / "invalid.txt"
        invalid_file.write_text("not a valid pose file")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Act & Assert - Should raise PoseFormatError
        with pytest.raises(Exception):  # PoseFormatError
            harmonize_pose(invalid_file, format="dlc", output_dir=output_dir)


# ============================================================================
# Test: Skeleton Harmonization (FR-5)
# ============================================================================


class TestSkeletonHarmonization:
    """Test keypoint name mapping to canonical schema (FR-5)."""

    def test_Should_MapKeypointNames_When_MappingProvided_Issue_Pose_FR5(self, tmp_path: Path):
        """THE SYSTEM SHALL map heterogeneous keypoint names to canonical skeleton.

        Requirements: FR-5 (Harmonize to canonical skeleton)
        Issue: Pose module - Keypoint mapping
        """
        # Arrange
        from w2t_bkin.pose import harmonize_pose

        dlc_file = tmp_path / "pose.h5"
        dlc_file.write_text("mock DLC data")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        skeleton_map = {"bodypart1": "snout", "bodypart2": "ear_L", "bodypart3": "ear_R"}

        # Act
        summary = harmonize_pose(dlc_file, format="dlc", output_dir=output_dir, skeleton_map=skeleton_map)

        # Assert - Should apply skeleton mapping
        assert hasattr(summary, "skeleton")
        assert summary.skeleton["mapping_applied"] is True
        assert "snout" in summary.skeleton["canonical_keypoints"]

    def test_Should_PreserveOriginalNames_When_Harmonizing_Issue_Pose_NFR11(self, tmp_path: Path):
        """THE SYSTEM SHALL preserve original keypoint names for provenance.

        Requirements: NFR-11 (Provenance)
        Issue: Pose module - Metadata preservation
        """
        # Arrange
        from w2t_bkin.pose import harmonize_pose

        dlc_file = tmp_path / "pose.h5"
        dlc_file.write_text("mock DLC data")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Act
        summary = harmonize_pose(dlc_file, format="dlc", output_dir=output_dir)

        # Assert - Should preserve original names in metadata
        assert hasattr(summary, "metadata")
        assert "original_keypoint_names" in summary.metadata

    def test_Should_RaiseSkeletonMappingError_When_UnmappedKeypoints_Issue_Pose_Design(self, tmp_path: Path):
        """THE SYSTEM SHALL detect unmapped keypoints and fail or warn.

        Requirements: Design - Error handling
        Issue: Pose module - Skeleton validation
        """
        # Arrange
        from w2t_bkin.pose import harmonize_pose

        dlc_file = tmp_path / "pose.h5"
        dlc_file.write_text("mock DLC data with extra keypoints")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        incomplete_map = {"bodypart1": "snout"}  # Missing mappings

        # Act & Assert - Should raise SkeletonMappingError
        with pytest.raises(Exception):  # SkeletonMappingError or warning
            harmonize_pose(dlc_file, format="dlc", output_dir=output_dir, skeleton_map=incomplete_map)


# ============================================================================
# Test: Confidence Score Handling (FR-5)
# ============================================================================


class TestConfidenceScores:
    """Test confidence score preservation and validation (FR-5)."""

    def test_Should_PreserveConfidenceScores_When_Importing_Issue_Pose_FR5(self, tmp_path: Path):
        """THE SYSTEM SHALL preserve confidence scores from pose outputs.

        Requirements: FR-5 (Preserving confidence scores)
        Issue: Pose module - Confidence preservation
        """
        # Arrange
        from w2t_bkin.pose import harmonize_pose

        dlc_file = tmp_path / "pose.h5"
        dlc_file.write_text("mock DLC data with confidence")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Act
        summary = harmonize_pose(dlc_file, format="dlc", output_dir=output_dir)

        # Assert - Should include confidence statistics
        assert hasattr(summary, "statistics")
        assert "mean_confidence" in summary.statistics
        assert "median_confidence" in summary.statistics
        assert 0.0 <= summary.statistics["mean_confidence"] <= 1.0

    def test_Should_ValidateConfidenceRange_When_Importing_Issue_Pose_NFR8(self, tmp_path: Path):
        """THE SYSTEM SHALL validate confidence scores are in [0,1] range.

        Requirements: NFR-8 (Data integrity)
        Issue: Pose module - Confidence validation
        """
        # Arrange
        from w2t_bkin.pose import _validate_confidence_range

        valid_scores = [0.0, 0.5, 0.99, 1.0]
        invalid_scores = [-0.1, 1.5, 2.0]

        # Act & Assert - Should accept valid scores
        assert _validate_confidence_range(valid_scores) is True

        # Should reject invalid scores
        with pytest.raises(Exception):  # ConfidenceRangeError
            _validate_confidence_range(invalid_scores)

    def test_Should_FlagLowConfidence_When_BelowThreshold_Issue_Pose_NFR3(self, tmp_path: Path):
        """THE SYSTEM SHALL flag frames with low confidence for QC.

        Requirements: NFR-3 (Observability), FR-8 (QC report)
        Issue: Pose module - Quality flagging
        """
        # Arrange
        from w2t_bkin.pose import harmonize_pose

        dlc_file = tmp_path / "pose.h5"
        dlc_file.write_text("mock DLC data with low confidence frames")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Act
        summary = harmonize_pose(dlc_file, format="dlc", output_dir=output_dir)

        # Assert - Should report low confidence frames
        assert hasattr(summary, "statistics")
        assert "low_confidence_frames" in summary.statistics


# ============================================================================
# Test: Timebase Alignment (FR-5)
# ============================================================================


class TestTimebaseAlignment:
    """Test alignment to session timebase (FR-5)."""

    def test_Should_AlignToSessionTimebase_When_TimestampsProvided_Issue_Pose_FR5(self, tmp_path: Path):
        """THE SYSTEM SHALL align pose timestamps to session timebase.

        Requirements: FR-5 (Align to session timebase)
        Issue: Pose module - Timestamp alignment
        """
        # Arrange
        from w2t_bkin.pose import harmonize_pose

        dlc_file = tmp_path / "pose.h5"
        dlc_file.write_text("mock DLC data")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        timestamps_dir = tmp_path / "sync"
        timestamps_dir.mkdir()
        # Create mock timestamp CSV
        (timestamps_dir / "timestamps_cam0.csv").write_text("frame_index,timestamp\n0,0.0\n1,0.033\n2,0.066\n")

        # Act
        summary = harmonize_pose(dlc_file, format="dlc", output_dir=output_dir, timestamps_dir=timestamps_dir)

        # Assert - Should apply timebase alignment
        assert hasattr(summary, "timebase_alignment")
        assert summary.timebase_alignment["sync_applied"] is True

    def test_Should_HandleDroppedFrames_When_Aligning_Issue_Pose_FR3(self, tmp_path: Path):
        """THE SYSTEM SHALL handle dropped frames during timebase alignment.

        Requirements: FR-3 (Detect dropped frames)
        Issue: Pose module - Dropped frame handling
        """
        # Arrange
        from w2t_bkin.pose import harmonize_pose

        dlc_file = tmp_path / "pose.h5"
        dlc_file.write_text("mock DLC data")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        timestamps_dir = tmp_path / "sync"
        timestamps_dir.mkdir()
        # Mock timestamps with gaps
        (timestamps_dir / "timestamps_cam0.csv").write_text("frame_index,timestamp\n0,0.0\n2,0.066\n3,0.099\n")

        # Act
        summary = harmonize_pose(dlc_file, format="dlc", output_dir=output_dir, timestamps_dir=timestamps_dir)

        # Assert - Should report dropped frames handled
        assert hasattr(summary, "timebase_alignment")
        assert "dropped_frames_handled" in summary.timebase_alignment

    def test_Should_RaiseTimestampAlignmentError_When_FrameCountMismatch_Issue_Pose_Design(self, tmp_path: Path):
        """THE SYSTEM SHALL detect frame count mismatches with sync data.

        Requirements: Design - Error handling
        Issue: Pose module - Alignment validation
        """
        # Arrange
        from w2t_bkin.pose import harmonize_pose

        dlc_file = tmp_path / "pose.h5"
        dlc_file.write_text("mock DLC data with 1000 frames")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        timestamps_dir = tmp_path / "sync"
        timestamps_dir.mkdir()
        # Timestamps for only 500 frames
        (timestamps_dir / "timestamps_cam0.csv").write_text("frame_index,timestamp\n0,0.0\n1,0.033\n")

        # Act & Assert - Should raise TimestampAlignmentError
        with pytest.raises(Exception):  # TimestampAlignmentError
            harmonize_pose(dlc_file, format="dlc", output_dir=output_dir, timestamps_dir=timestamps_dir)


# ============================================================================
# Test: Output Generation (FR-5, NFR-3)
# ============================================================================


class TestOutputGeneration:
    """Test harmonized output generation (FR-5, NFR-3)."""

    def test_Should_GenerateParquetOutput_When_Harmonizing_Issue_Pose_FR5(self, tmp_path: Path):
        """THE SYSTEM SHALL generate harmonized pose table in Parquet format.

        Requirements: FR-5 (Harmonize outputs), Design §3.3 (Parquet format)
        Issue: Pose module - Output generation
        """
        # Arrange
        from w2t_bkin.pose import harmonize_pose

        dlc_file = tmp_path / "pose.h5"
        dlc_file.write_text("mock DLC data")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Act
        summary = harmonize_pose(dlc_file, format="dlc", output_dir=output_dir)

        # Assert - Should create Parquet output
        parquet_file = output_dir / "pose_harmonized.parquet"
        assert parquet_file.exists() or hasattr(summary, "output_path")

    def test_Should_GeneratePoseSummary_When_Harmonizing_Issue_Pose_NFR3(self, tmp_path: Path):
        """THE SYSTEM SHALL generate pose summary JSON with statistics.

        Requirements: NFR-3 (Observability)
        Issue: Pose module - Summary generation
        """
        # Arrange
        from w2t_bkin.pose import harmonize_pose

        dlc_file = tmp_path / "pose.h5"
        dlc_file.write_text("mock DLC data")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Act
        summary = harmonize_pose(dlc_file, format="dlc", output_dir=output_dir)

        # Assert - Should contain required summary fields
        assert hasattr(summary, "session_id")
        assert hasattr(summary, "source_format")
        assert hasattr(summary, "statistics")
        assert hasattr(summary, "skeleton")

    def test_Should_IncludeStatistics_When_Summarizing_Issue_Pose_FR8(self, tmp_path: Path):
        """THE SYSTEM SHALL include pose statistics for QC reporting.

        Requirements: FR-8 (QC report with pose confidence distributions)
        Issue: Pose module - Statistics computation
        """
        # Arrange
        from w2t_bkin.pose import harmonize_pose

        dlc_file = tmp_path / "pose.h5"
        dlc_file.write_text("mock DLC data")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Act
        summary = harmonize_pose(dlc_file, format="dlc", output_dir=output_dir)

        # Assert - Should include comprehensive statistics
        assert "total_frames" in summary.statistics
        assert "keypoints_per_frame" in summary.statistics
        assert "mean_confidence" in summary.statistics
        assert "coverage_by_keypoint" in summary.statistics


# ============================================================================
# Test: Provenance Capture (NFR-11)
# ============================================================================


class TestProvenance:
    """Test provenance metadata capture (NFR-11)."""

    def test_Should_RecordModelHash_When_Importing_Issue_Pose_NFR11(self, tmp_path: Path):
        """THE SYSTEM SHALL record model hash for provenance.

        Requirements: NFR-11 (Provenance)
        Issue: Pose module - Model tracking
        """
        # Arrange
        from w2t_bkin.pose import harmonize_pose

        dlc_file = tmp_path / "pose.h5"
        dlc_file.write_text("mock DLC data")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Act
        summary = harmonize_pose(dlc_file, format="dlc", output_dir=output_dir)

        # Assert - Should include model hash
        assert hasattr(summary, "model_hash")
        assert summary.model_hash is not None

    def test_Should_RecordSourceToolVersion_When_Importing_Issue_Pose_NFR11(self, tmp_path: Path):
        """THE SYSTEM SHALL record source tool version.

        Requirements: NFR-11 (Provenance)
        Issue: Pose module - Tool version tracking
        """
        # Arrange
        from w2t_bkin.pose import harmonize_pose

        dlc_file = tmp_path / "pose.h5"
        dlc_file.write_text("mock DLC data")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Act
        summary = harmonize_pose(dlc_file, format="dlc", output_dir=output_dir)

        # Assert - Should include source tool info
        assert hasattr(summary, "metadata")
        assert "source_tool" in summary.metadata
        assert "source_version" in summary.metadata


# ============================================================================
# Test: Idempotence (NFR-2)
# ============================================================================


class TestIdempotence:
    """Test idempotent re-runs (NFR-2)."""

    def test_Should_SkipExisting_When_OutputExists_Issue_Pose_NFR2(self, tmp_path: Path):
        """THE SYSTEM SHALL skip harmonization if output exists and input unchanged.

        Requirements: NFR-2 (Idempotent re-run)
        Issue: Pose module - Idempotence
        """
        # Arrange
        from w2t_bkin.pose import harmonize_pose

        dlc_file = tmp_path / "pose.h5"
        dlc_file.write_text("mock DLC data")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Act - First run
        summary1 = harmonize_pose(dlc_file, format="dlc", output_dir=output_dir)

        # Act - Second run without changes
        summary2 = harmonize_pose(dlc_file, format="dlc", output_dir=output_dir)

        # Assert - Should skip re-harmonization
        assert hasattr(summary2, "skipped") and summary2.skipped is True

    def test_Should_ForceReharmonize_When_FlagSet_Issue_Pose_NFR2(self, tmp_path: Path):
        """THE SYSTEM SHALL re-harmonize when forced, even if output exists.

        Requirements: NFR-2
        Issue: Pose module - Force re-run
        """
        # Arrange
        from w2t_bkin.pose import harmonize_pose

        dlc_file = tmp_path / "pose.h5"
        dlc_file.write_text("mock DLC data")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Pre-existing output
        harmonize_pose(dlc_file, format="dlc", output_dir=output_dir)

        # Act - Force re-harmonize
        summary = harmonize_pose(dlc_file, format="dlc", output_dir=output_dir, force=True)

        # Assert - Should re-harmonize
        assert hasattr(summary, "skipped") and summary.skipped is False


# ============================================================================
# Test: Edge Cases and Boundary Conditions
# ============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_Should_HandleEmptyPoseFile_When_Processing_Issue_Pose_Design(self, tmp_path: Path):
        """THE SYSTEM SHALL handle pose files with no detections.

        Requirements: Design - Error handling
        Issue: Pose module - Empty input handling
        """
        # Arrange
        from w2t_bkin.pose import harmonize_pose

        empty_file = tmp_path / "empty_pose.h5"
        empty_file.write_text("mock empty DLC file")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Act
        summary = harmonize_pose(empty_file, format="dlc", output_dir=output_dir)

        # Assert - Should complete with warnings
        assert hasattr(summary, "warnings")
        assert len(summary.warnings) > 0

    def test_Should_HandleMissingKeypoints_When_Sparse_Issue_Pose_NFR3(self, tmp_path: Path):
        """THE SYSTEM SHALL handle sparse detections with missing keypoints.

        Requirements: NFR-3 (Observability)
        Issue: Pose module - Sparse data handling
        """
        # Arrange
        from w2t_bkin.pose import harmonize_pose

        sparse_file = tmp_path / "sparse_pose.h5"
        sparse_file.write_text("mock sparse DLC data")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Act
        summary = harmonize_pose(sparse_file, format="dlc", output_dir=output_dir)

        # Assert - Should report missing keypoints
        assert "missing_keypoints" in summary.statistics

    def test_Should_HandleMultiAnimal_When_DLCMaMode_Issue_Pose_Future(self, tmp_path: Path):
        """THE SYSTEM SHALL handle multi-animal tracking data.

        Requirements: Future enhancement
        Issue: Pose module - Multi-animal support
        """
        pytest.skip("Multi-animal support not yet implemented - future enhancement")


# ============================================================================
# Test: Helper Functions
# ============================================================================


class TestHelperFunctions:
    """Test internal helper functions."""

    def test_Should_ExtractKeypointNames_When_ParsingDLC_Issue_Pose_Internal(self):
        """Internal helper should extract keypoint names from DLC structure.

        Issue: Pose module - DLC parsing helpers
        """
        # Arrange
        from w2t_bkin.pose import _extract_dlc_keypoints

        mock_dlc_data = {"bodyparts": ["bodypart1", "bodypart2", "bodypart3"]}

        # Act
        keypoints = _extract_dlc_keypoints(mock_dlc_data)

        # Assert - Should extract keypoint list
        assert isinstance(keypoints, list)
        assert len(keypoints) == 3

    def test_Should_ComputeCoverage_When_AnalyzingPose_Issue_Pose_Internal(self):
        """Internal helper should compute per-keypoint coverage statistics.

        Issue: Pose module - Coverage computation
        """
        # Arrange
        from w2t_bkin.pose import _compute_keypoint_coverage

        mock_detections = {"snout": [True, True, False, True], "ear_L": [True, False, False, True]}

        # Act
        coverage = _compute_keypoint_coverage(mock_detections)

        # Assert - Should compute coverage ratios
        assert coverage["snout"] == 0.75  # 3/4
        assert coverage["ear_L"] == 0.5  # 2/4
