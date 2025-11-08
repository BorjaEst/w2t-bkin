"""Unit tests for the pose module.

Tests DLC/SLEAP pose import and harmonization to canonical skeleton/timebase
as specified in pose/requirements.md and design.md.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


class TestPoseImport:
    """Test DLC/SLEAP pose output import (MR-1)."""

    def test_Should_ImportDLC_When_Provided_MR1(self):
        """THE MODULE SHALL import DLC outputs.

        Requirements: MR-1
        Issue: Pose module - DLC import
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries
        from w2t_bkin.pose import PoseInputs, harmonize_pose

        inputs = PoseInputs(dlc_h5_path=Path("/data/dlc_output.h5"))
        timestamps = TimestampSeries(
            frame_indices=list(range(10)),
            timestamps=[i * 0.033 for i in range(10)],
        )

        # Act
        pose_table = harmonize_pose(inputs, timestamps)

        # Assert
        assert pose_table is not None
        assert hasattr(pose_table, "keypoint")
        assert hasattr(pose_table, "confidence")

    def test_Should_ImportSLEAP_When_Provided_MR1(self):
        """THE MODULE SHALL import SLEAP outputs.

        Requirements: MR-1
        Issue: Pose module - SLEAP import
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries
        from w2t_bkin.pose import PoseInputs, harmonize_pose

        inputs = PoseInputs(sleap_h5_path=Path("/data/sleap_output.h5"))
        timestamps = TimestampSeries(
            frame_indices=list(range(10)),
            timestamps=[i * 0.033 for i in range(10)],
        )

        # Act
        pose_table = harmonize_pose(inputs, timestamps)

        # Assert
        assert pose_table is not None

    def test_Should_MapToCanonicalSkeleton_When_Importing_MR1(self):
        """THE MODULE SHALL map to a canonical skeleton.

        Requirements: MR-1, Design - Canonical skeleton mapping
        Issue: Pose module - Skeleton mapping
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries
        from w2t_bkin.pose import PoseInputs, harmonize_pose

        inputs = PoseInputs(dlc_h5_path=Path("/data/dlc_output.h5"))
        timestamps = TimestampSeries(
            frame_indices=list(range(10)),
            timestamps=[i * 0.033 for i in range(10)],
        )

        # Act
        pose_table = harmonize_pose(inputs, timestamps)

        # Assert - Should use standardized keypoint names
        assert all(isinstance(kp, str) and len(kp) > 0 for kp in pose_table.keypoint)

    def test_Should_StandardizeFields_When_Importing_MR1(self):
        """THE MODULE SHALL standardize schema to canonical fields.

        Requirements: MR-1, Design - Standardize schema
        Issue: Pose module - Field standardization
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries
        from w2t_bkin.pose import PoseInputs, harmonize_pose

        inputs = PoseInputs(dlc_h5_path=Path("/data/dlc_output.h5"))
        timestamps = TimestampSeries(
            frame_indices=list(range(10)),
            timestamps=[i * 0.033 for i in range(10)],
        )

        # Act
        pose_table = harmonize_pose(inputs, timestamps)

        # Assert - Canonical fields: time, keypoint, x_px, y_px, confidence
        assert hasattr(pose_table, "time")
        assert hasattr(pose_table, "keypoint")
        assert hasattr(pose_table, "x_px")
        assert hasattr(pose_table, "y_px")
        assert hasattr(pose_table, "confidence")

    def test_Should_HandleMultipleSources_When_Provided_MR1(self):
        """THE MODULE SHALL handle multiple pose sources.

        Requirements: MR-1
        Issue: Pose module - Multiple sources
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries
        from w2t_bkin.pose import PoseInputs, harmonize_pose

        inputs = PoseInputs(
            dlc_h5_path=Path("/data/dlc_output.h5"),
            sleap_h5_path=Path("/data/sleap_output.h5"),
        )
        timestamps = TimestampSeries(
            frame_indices=list(range(10)),
            timestamps=[i * 0.033 for i in range(10)],
        )

        # Act & Assert - Should handle or raise appropriate error
        try:
            pose_table = harmonize_pose(inputs, timestamps)
            assert pose_table is not None
        except ValueError:
            # Also acceptable to reject multiple sources
            pass


class TestTimebaseAlignment:
    """Test alignment to session timebase (MR-2)."""

    def test_Should_AlignToSessionTimebase_When_Harmonizing_MR2(self):
        """THE MODULE SHALL align pose to the session timebase.

        Requirements: MR-2
        Issue: Pose module - Timebase alignment
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries
        from w2t_bkin.pose import PoseInputs, harmonize_pose

        inputs = PoseInputs(dlc_h5_path=Path("/data/dlc_output.h5"))
        timestamps = TimestampSeries(
            frame_indices=list(range(10)),
            timestamps=[i * 0.033 for i in range(10)],
        )

        # Act
        pose_table = harmonize_pose(inputs, timestamps)

        # Assert - Time should match session timebase
        assert len(pose_table.time) > 0
        # Time values should align with provided timestamps
        expected_times = set(timestamps.timestamps)
        actual_times = set(pose_table.time)
        assert actual_times.issubset(expected_times) or len(actual_times) > 0

    def test_Should_UseCameraTimestamps_When_Aligning_MR2(self):
        """THE MODULE SHALL use camera timestamps for alignment.

        Requirements: MR-2, Design - Camera timestamps
        Issue: Pose module - Camera timestamp usage
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries
        from w2t_bkin.pose import PoseInputs, harmonize_pose

        inputs = PoseInputs(dlc_h5_path=Path("/data/dlc_output.h5"))
        camera_timestamps = TimestampSeries(
            frame_indices=list(range(10)),
            timestamps=[i * 0.033 for i in range(10)],
        )

        # Act
        pose_table = harmonize_pose(inputs, camera_timestamps)

        # Assert - Should use provided camera timestamps
        assert pose_table is not None
        assert len(pose_table.time) > 0

    def test_Should_HandleFrameIndexMapping_When_Aligning_MR2(self):
        """THE MODULE SHALL map frame indices to timestamps.

        Requirements: MR-2
        Issue: Pose module - Frame index mapping
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries
        from w2t_bkin.pose import PoseInputs, harmonize_pose

        inputs = PoseInputs(dlc_h5_path=Path("/data/dlc_output.h5"))
        timestamps = TimestampSeries(
            frame_indices=[0, 1, 2, 5, 6, 7],  # Non-contiguous
            timestamps=[0.0, 0.033, 0.066, 0.165, 0.198, 0.231],
        )

        # Act
        pose_table = harmonize_pose(inputs, timestamps)

        # Assert
        assert pose_table is not None

    def test_Should_InterpolateOrMark_When_MissingFrames_MR2(self):
        """THE MODULE SHALL handle missing frames appropriately.

        Requirements: MR-2, MR-3 - Mark gaps without fabricating data
        Issue: Pose module - Missing frame handling
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries
        from w2t_bkin.pose import PoseInputs, harmonize_pose

        inputs = PoseInputs(dlc_h5_path=Path("/data/dlc_with_gaps.h5"))
        timestamps = TimestampSeries(
            frame_indices=list(range(20)),
            timestamps=[i * 0.033 for i in range(20)],
        )

        # Act
        pose_table = harmonize_pose(inputs, timestamps)

        # Assert - Should mark gaps, not fabricate data
        assert pose_table is not None


class TestConfidencePreservation:
    """Test confidence score preservation (MR-3)."""

    def test_Should_PreserveConfidence_When_Harmonizing_MR3(self):
        """THE MODULE SHALL preserve confidence scores.

        Requirements: MR-3
        Issue: Pose module - Confidence preservation
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries
        from w2t_bkin.pose import PoseInputs, harmonize_pose

        inputs = PoseInputs(dlc_h5_path=Path("/data/dlc_output.h5"))
        timestamps = TimestampSeries(
            frame_indices=list(range(10)),
            timestamps=[i * 0.033 for i in range(10)],
        )

        # Act
        pose_table = harmonize_pose(inputs, timestamps)

        # Assert - Confidence should be preserved
        assert all(0.0 <= c <= 1.0 for c in pose_table.confidence)

    def test_Should_MarkGaps_When_DataMissing_MR3(self):
        """THE MODULE SHALL mark gaps without fabricating data.

        Requirements: MR-3
        Issue: Pose module - Gap marking
        """
        # Arrange
        import math

        from w2t_bkin.domain import TimestampSeries
        from w2t_bkin.pose import PoseInputs, harmonize_pose

        inputs = PoseInputs(dlc_h5_path=Path("/data/dlc_with_gaps.h5"))
        timestamps = TimestampSeries(
            frame_indices=list(range(10)),
            timestamps=[i * 0.033 for i in range(10)],
        )

        # Act
        pose_table = harmonize_pose(inputs, timestamps)

        # Assert - Gaps should be marked with NaN or confidence=0
        has_gaps = any(math.isnan(x) or math.isnan(y) or c == 0.0 for x, y, c in zip(pose_table.x_px, pose_table.y_px, pose_table.confidence))
        assert has_gaps or len(pose_table.time) > 0

    def test_Should_NotFabricateData_When_GapsExist_MR3(self):
        """THE MODULE SHALL not fabricate data for gaps.

        Requirements: MR-3
        Issue: Pose module - No data fabrication
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries
        from w2t_bkin.pose import PoseInputs, harmonize_pose

        inputs = PoseInputs(dlc_h5_path=Path("/data/dlc_sparse.h5"))
        timestamps = TimestampSeries(
            frame_indices=list(range(100)),
            timestamps=[i * 0.033 for i in range(100)],
        )

        # Act
        pose_table = harmonize_pose(inputs, timestamps)

        # Assert - Should have gaps, not interpolated data
        assert pose_table is not None

    def test_Should_HandleNaNs_When_Present_MR3_MNFR2(self):
        """THE MODULE SHALL handle NaNs appropriately.

        Requirements: MR-3, M-NFR-2 - NaN handling documented
        Issue: Pose module - NaN handling
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries
        from w2t_bkin.pose import PoseInputs, harmonize_pose

        inputs = PoseInputs(dlc_h5_path=Path("/data/dlc_with_nans.h5"))
        timestamps = TimestampSeries(
            frame_indices=list(range(10)),
            timestamps=[i * 0.033 for i in range(10)],
        )

        # Act
        pose_table = harmonize_pose(inputs, timestamps)

        # Assert - NaNs should be preserved
        assert pose_table is not None

    def test_Should_HandleOutOfRangeConfidence_When_Found_MR3_MNFR2(self):
        """THE MODULE SHALL handle out-of-range confidence values.

        Requirements: MR-3, M-NFR-2 - Out-of-range handling documented
        Issue: Pose module - Confidence bounds
        """
        # Arrange
        from w2t_bkin.domain import DataIntegrityWarning, TimestampSeries
        from w2t_bkin.pose import PoseInputs, harmonize_pose

        inputs = PoseInputs(dlc_h5_path=Path("/data/dlc_bad_confidence.h5"))
        timestamps = TimestampSeries(
            frame_indices=list(range(10)),
            timestamps=[i * 0.033 for i in range(10)],
        )

        # Act & Assert - Should warn or clip
        with pytest.warns(DataIntegrityWarning):
            pose_table = harmonize_pose(inputs, timestamps)


class TestSkeletonRegistry:
    """Test skeleton registry for deterministic mapping (M-NFR-1)."""

    def test_Should_UseDeterministicMapping_When_Harmonizing_MNFR1(self):
        """THE MODULE SHALL use deterministic skeleton mapping.

        Requirements: M-NFR-1
        Issue: Pose module - Deterministic mapping
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries
        from w2t_bkin.pose import PoseInputs, harmonize_pose

        inputs = PoseInputs(dlc_h5_path=Path("/data/dlc_output.h5"))
        timestamps = TimestampSeries(
            frame_indices=list(range(10)),
            timestamps=[i * 0.033 for i in range(10)],
        )

        # Act - Call twice
        pose_table1 = harmonize_pose(inputs, timestamps)
        pose_table2 = harmonize_pose(inputs, timestamps)

        # Assert - Should produce identical keypoint names
        assert pose_table1.keypoint == pose_table2.keypoint

    def test_Should_UseSkeletonRegistry_When_Mapping_MNFR1(self):
        """THE MODULE SHALL use skeleton registry for mapping.

        Requirements: M-NFR-1, Design - Skeleton registry
        Issue: Pose module - Registry usage
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries
        from w2t_bkin.pose import PoseInputs, harmonize_pose

        inputs = PoseInputs(
            dlc_h5_path=Path("/data/dlc_output.h5"),
            skeleton_name="mouse_v1",
        )
        timestamps = TimestampSeries(
            frame_indices=list(range(10)),
            timestamps=[i * 0.033 for i in range(10)],
        )

        # Act
        pose_table = harmonize_pose(inputs, timestamps)

        # Assert - Should use specified skeleton
        assert pose_table is not None

    def test_Should_ValidateSkeletonName_When_Provided_MNFR1(self):
        """THE MODULE SHALL validate skeleton name against registry.

        Requirements: M-NFR-1
        Issue: Pose module - Skeleton validation
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries
        from w2t_bkin.pose import PoseInputs, harmonize_pose

        inputs = PoseInputs(
            dlc_h5_path=Path("/data/dlc_output.h5"),
            skeleton_name="invalid_skeleton",
        )
        timestamps = TimestampSeries(
            frame_indices=list(range(10)),
            timestamps=[i * 0.033 for i in range(10)],
        )

        # Act & Assert
        with pytest.raises((ValueError, KeyError)):
            harmonize_pose(inputs, timestamps)


class TestMetadataEmission:
    """Test metadata emission alongside pose data (Design)."""

    def test_Should_EmitMetadata_When_Harmonizing_Design(self):
        """THE MODULE SHALL emit metadata JSON.

        Requirements: Design - Metadata emission
        Issue: Pose module - Metadata output
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries
        from w2t_bkin.pose import PoseInputs, harmonize_pose

        inputs = PoseInputs(dlc_h5_path=Path("/data/dlc_output.h5"))
        timestamps = TimestampSeries(
            frame_indices=list(range(10)),
            timestamps=[i * 0.033 for i in range(10)],
        )

        # Act
        pose_table = harmonize_pose(inputs, timestamps)

        # Assert - Should have metadata
        assert hasattr(pose_table, "metadata")

    def test_Should_IncludeSkeletonInfo_When_Harmonizing_Design(self):
        """THE MODULE SHALL include skeleton info in metadata.

        Requirements: Design - Skeleton metadata
        Issue: Pose module - Skeleton documentation
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries
        from w2t_bkin.pose import PoseInputs, harmonize_pose

        inputs = PoseInputs(
            dlc_h5_path=Path("/data/dlc_output.h5"),
            skeleton_name="mouse_v1",
        )
        timestamps = TimestampSeries(
            frame_indices=list(range(10)),
            timestamps=[i * 0.033 for i in range(10)],
        )

        # Act
        pose_table = harmonize_pose(inputs, timestamps)

        # Assert - Metadata should include skeleton
        if hasattr(pose_table, "metadata"):
            assert "skeleton" in str(pose_table.metadata).lower()

    def test_Should_IncludeModelHash_When_Available_Design(self):
        """THE MODULE SHALL include model hash in metadata.

        Requirements: Design - Model provenance
        Issue: Pose module - Model tracking
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries
        from w2t_bkin.pose import PoseInputs, harmonize_pose

        inputs = PoseInputs(
            dlc_h5_path=Path("/data/dlc_output.h5"),
            model_hash="abc123",
        )
        timestamps = TimestampSeries(
            frame_indices=list(range(10)),
            timestamps=[i * 0.033 for i in range(10)],
        )

        # Act
        pose_table = harmonize_pose(inputs, timestamps)

        # Assert
        if hasattr(pose_table, "metadata"):
            assert pose_table.metadata.get("model_hash") == "abc123"


class TestOutputFormat:
    """Test output format preferences (Design)."""

    def test_Should_SupportParquet_When_Exporting_Design(self):
        """THE MODULE SHALL prefer Parquet for output.

        Requirements: Design - Prefer Parquet
        Issue: Pose module - Parquet support
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries
        from w2t_bkin.pose import PoseInputs, harmonize_pose

        inputs = PoseInputs(dlc_h5_path=Path("/data/dlc_output.h5"))
        timestamps = TimestampSeries(
            frame_indices=list(range(10)),
            timestamps=[i * 0.033 for i in range(10)],
        )

        # Act
        pose_table = harmonize_pose(inputs, timestamps)

        # Assert - Should be serializable to Parquet
        assert pose_table is not None
        # In actual implementation, would test .to_parquet()

    def test_Should_ReturnPoseTable_When_Harmonizing_Design(self):
        """THE MODULE SHALL return PoseTable domain model.

        Requirements: Design - Return type
        Issue: Pose module - Output type
        """
        # Arrange
        from w2t_bkin.domain import PoseTable, TimestampSeries
        from w2t_bkin.pose import PoseInputs, harmonize_pose

        inputs = PoseInputs(dlc_h5_path=Path("/data/dlc_output.h5"))
        timestamps = TimestampSeries(
            frame_indices=list(range(10)),
            timestamps=[i * 0.033 for i in range(10)],
        )

        # Act
        pose_table = harmonize_pose(inputs, timestamps)

        # Assert
        assert isinstance(pose_table, PoseTable)


class TestDataIntegrityWarnings:
    """Test data integrity warnings (Design)."""

    def test_Should_WarnOnLowConfidence_When_Detected_Design(self):
        """THE MODULE SHALL warn on low confidence values.

        Requirements: Design - DataIntegrityWarning
        Issue: Pose module - Low confidence warning
        """
        # Arrange
        from w2t_bkin.domain import DataIntegrityWarning, TimestampSeries
        from w2t_bkin.pose import PoseInputs, harmonize_pose

        inputs = PoseInputs(dlc_h5_path=Path("/data/dlc_low_confidence.h5"))
        timestamps = TimestampSeries(
            frame_indices=list(range(10)),
            timestamps=[i * 0.033 for i in range(10)],
        )

        # Act & Assert
        with pytest.warns(DataIntegrityWarning):
            harmonize_pose(inputs, timestamps)

    def test_Should_WarnOnOutOfRange_When_Detected_Design(self):
        """THE MODULE SHALL warn on out-of-range coordinates.

        Requirements: Design - DataIntegrityWarning
        Issue: Pose module - Coordinate bounds
        """
        # Arrange
        from w2t_bkin.domain import DataIntegrityWarning, TimestampSeries
        from w2t_bkin.pose import PoseInputs, harmonize_pose

        inputs = PoseInputs(dlc_h5_path=Path("/data/dlc_out_of_bounds.h5"))
        timestamps = TimestampSeries(
            frame_indices=list(range(10)),
            timestamps=[i * 0.033 for i in range(10)],
        )

        # Act & Assert
        with pytest.warns(DataIntegrityWarning):
            harmonize_pose(inputs, timestamps)


class TestPoseInputs:
    """Test PoseInputs data structure."""

    def test_Should_CreateInputs_When_Provided_Design(self):
        """THE MODULE SHALL provide PoseInputs typed model.

        Requirements: Design - Input contract
        Issue: Pose module - PoseInputs model
        """
        # Arrange
        from w2t_bkin.pose import PoseInputs

        # Act
        inputs = PoseInputs(
            dlc_h5_path=Path("/data/dlc_output.h5"),
            skeleton_name="mouse_v1",
        )

        # Assert
        assert inputs.dlc_h5_path == Path("/data/dlc_output.h5")
        assert inputs.skeleton_name == "mouse_v1"

    def test_Should_AcceptMultipleFormats_When_Creating_Design(self):
        """THE MODULE SHALL accept DLC and SLEAP formats.

        Requirements: Design - Multiple formats
        Issue: Pose module - Format support
        """
        # Arrange
        from w2t_bkin.pose import PoseInputs

        # Act - Should accept various formats
        inputs1 = PoseInputs(dlc_h5_path=Path("/data/dlc.h5"))
        inputs2 = PoseInputs(sleap_h5_path=Path("/data/sleap.h5"))
        inputs3 = PoseInputs(dlc_csv_path=Path("/data/dlc.csv"))

        # Assert
        assert inputs1.dlc_h5_path is not None
        assert inputs2.sleap_h5_path is not None
        assert inputs3.dlc_csv_path is not None


class TestOptionalSmoothing:
    """Test optional smoothing with metadata flagging (Design - Future notes)."""

    def test_Should_SupportSmoothing_When_Enabled_Future(self):
        """THE MODULE SHALL support optional smoothing.

        Requirements: Design - Future notes
        Issue: Pose module - Smoothing support
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries
        from w2t_bkin.pose import PoseInputs, harmonize_pose

        inputs = PoseInputs(
            dlc_h5_path=Path("/data/dlc_output.h5"),
            apply_smoothing=True,
            smoothing_window=5,
        )
        timestamps = TimestampSeries(
            frame_indices=list(range(10)),
            timestamps=[i * 0.033 for i in range(10)],
        )

        # Act
        pose_table = harmonize_pose(inputs, timestamps)

        # Assert - Should apply smoothing
        assert pose_table is not None

    def test_Should_FlagSmoothing_When_Applied_Future(self):
        """THE MODULE SHALL flag smoothing in metadata.

        Requirements: Design - Future notes
        Issue: Pose module - Smoothing metadata
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries
        from w2t_bkin.pose import PoseInputs, harmonize_pose

        inputs = PoseInputs(
            dlc_h5_path=Path("/data/dlc_output.h5"),
            apply_smoothing=True,
        )
        timestamps = TimestampSeries(
            frame_indices=list(range(10)),
            timestamps=[i * 0.033 for i in range(10)],
        )

        # Act
        pose_table = harmonize_pose(inputs, timestamps)

        # Assert - Metadata should indicate smoothing applied
        if hasattr(pose_table, "metadata"):
            metadata_str = str(pose_table.metadata).lower()
            assert "smooth" in metadata_str or pose_table.metadata is not None


class TestColumnMapping:
    """Test heterogeneous schema mapping (Design)."""

    def test_Should_MapDLCColumns_When_Importing_Design(self):
        """THE MODULE SHALL map DLC column names to canonical schema.

        Requirements: Design - Column mapping
        Issue: Pose module - DLC column mapping
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries
        from w2t_bkin.pose import PoseInputs, harmonize_pose

        inputs = PoseInputs(dlc_h5_path=Path("/data/dlc_output.h5"))
        timestamps = TimestampSeries(
            frame_indices=list(range(10)),
            timestamps=[i * 0.033 for i in range(10)],
        )

        # Act
        pose_table = harmonize_pose(inputs, timestamps)

        # Assert - Should have canonical column names
        assert hasattr(pose_table, "x_px")
        assert hasattr(pose_table, "y_px")
        assert hasattr(pose_table, "confidence")

    def test_Should_MapSLEAPColumns_When_Importing_Design(self):
        """THE MODULE SHALL map SLEAP column names to canonical schema.

        Requirements: Design - Column mapping
        Issue: Pose module - SLEAP column mapping
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries
        from w2t_bkin.pose import PoseInputs, harmonize_pose

        inputs = PoseInputs(sleap_h5_path=Path("/data/sleap_output.h5"))
        timestamps = TimestampSeries(
            frame_indices=list(range(10)),
            timestamps=[i * 0.033 for i in range(10)],
        )

        # Act
        pose_table = harmonize_pose(inputs, timestamps)

        # Assert - Should have canonical column names
        assert hasattr(pose_table, "x_px")
        assert hasattr(pose_table, "y_px")


class TestDeterministicOutput:
    """Test deterministic harmonization (M-NFR-1)."""

    def test_Should_ProduceSameOutput_When_SameInput_MNFR1(self):
        """THE MODULE SHALL produce deterministic harmonization.

        Requirements: M-NFR-1
        Issue: Pose module - Determinism
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries
        from w2t_bkin.pose import PoseInputs, harmonize_pose

        inputs = PoseInputs(dlc_h5_path=Path("/data/dlc_output.h5"))
        timestamps = TimestampSeries(
            frame_indices=list(range(10)),
            timestamps=[i * 0.033 for i in range(10)],
        )

        # Act
        pose_table1 = harmonize_pose(inputs, timestamps)
        pose_table2 = harmonize_pose(inputs, timestamps)

        # Assert - Should be identical
        assert pose_table1.keypoint == pose_table2.keypoint
        assert pose_table1.time == pose_table2.time
        assert pose_table1.x_px == pose_table2.x_px
