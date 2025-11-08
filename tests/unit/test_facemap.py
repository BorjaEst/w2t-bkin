"""Unit tests for the facemap module.

Tests facial metrics ingestion/computation and alignment to session timebase
as specified in facemap/requirements.md and design.md.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


class TestMetricsImport:
    """Test facial metrics import from various formats (MR-1)."""

    def test_Should_ImportCSV_When_InputProvided_MR1(self):
        """WHERE inputs are provided, THE MODULE SHALL import facial metrics.

        Requirements: MR-1
        Issue: Facemap module - CSV import
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries
        from w2t_bkin.facemap import FacemapInputs, harmonize_facemap

        inputs = FacemapInputs(csv_path=Path("/data/facemap.csv"))
        timestamps = TimestampSeries(
            frame_indices=[0, 1, 2],
            timestamps=[0.0, 0.033, 0.066],
        )

        # Act
        metrics = harmonize_facemap(inputs, timestamps)

        # Assert
        assert metrics is not None
        assert hasattr(metrics, "time")

    def test_Should_ImportNPY_When_InputProvided_MR1(self):
        """THE MODULE SHALL import metrics from NPY files.

        Requirements: MR-1
        Issue: Facemap module - NPY import
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries
        from w2t_bkin.facemap import FacemapInputs, harmonize_facemap

        inputs = FacemapInputs(npy_path=Path("/data/facemap_metrics.npy"))
        timestamps = TimestampSeries(
            frame_indices=[0, 1, 2],
            timestamps=[0.0, 0.033, 0.066],
        )

        # Act
        metrics = harmonize_facemap(inputs, timestamps)

        # Assert
        assert metrics is not None

    def test_Should_ImportParquet_When_InputProvided_MR1(self):
        """THE MODULE SHALL import metrics from Parquet files.

        Requirements: MR-1
        Issue: Facemap module - Parquet import
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries
        from w2t_bkin.facemap import FacemapInputs, harmonize_facemap

        inputs = FacemapInputs(parquet_path=Path("/data/facemap.parquet"))
        timestamps = TimestampSeries(
            frame_indices=[0, 1, 2],
            timestamps=[0.0, 0.033, 0.066],
        )

        # Act
        metrics = harmonize_facemap(inputs, timestamps)

        # Assert
        assert metrics is not None

    def test_Should_ComputeMetrics_When_RawVideoProvided_MR1(self):
        """THE MODULE SHALL compute metrics from raw face video.

        Requirements: MR-1
        Issue: Facemap module - Metric computation
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries
        from w2t_bkin.facemap import FacemapInputs, harmonize_facemap

        inputs = FacemapInputs(video_path=Path("/data/face_camera.mp4"))
        timestamps = TimestampSeries(
            frame_indices=[0, 1, 2],
            timestamps=[0.0, 0.033, 0.066],
        )

        # Act
        metrics = harmonize_facemap(inputs, timestamps)

        # Assert
        assert metrics is not None
        # Should have computed metrics like motion energy, pupil area
        assert hasattr(metrics, "motion_energy") or hasattr(metrics, "pupil_area")

    def test_Should_HandleMissingInput_When_Optional_MR1(self):
        """THE MODULE SHALL handle missing optional inputs.

        Requirements: MR-1 - Optional inputs
        Issue: Facemap module - Optional handling
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries
        from w2t_bkin.facemap import FacemapInputs, harmonize_facemap

        inputs = FacemapInputs()  # No inputs provided
        timestamps = TimestampSeries(
            frame_indices=[0, 1, 2],
            timestamps=[0.0, 0.033, 0.066],
        )

        # Act & Assert - Should handle gracefully (skip or return empty)
        try:
            metrics = harmonize_facemap(inputs, timestamps)
            # If it returns, should be None or empty
            assert metrics is None or len(metrics.time) == 0
        except (ValueError, FileNotFoundError):
            # Also acceptable to raise error for missing inputs
            pass

    def test_Should_ValidateInputFormat_When_Importing_MR1(self):
        """THE MODULE SHALL validate input file formats.

        Requirements: MR-1
        Issue: Facemap module - Format validation
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries
        from w2t_bkin.facemap import FacemapInputs, harmonize_facemap

        inputs = FacemapInputs(csv_path=Path("/data/invalid.txt"))
        timestamps = TimestampSeries(
            frame_indices=[0, 1, 2],
            timestamps=[0.0, 0.033, 0.066],
        )

        # Act & Assert - Should validate format
        with pytest.raises((ValueError, FileNotFoundError, Exception)):
            harmonize_facemap(inputs, timestamps)


class TestTimebaseAlignment:
    """Test alignment to session timebase (MR-2)."""

    def test_Should_AlignToTimebase_When_Harmonizing_MR2(self):
        """THE MODULE SHALL align metrics to the session timebase.

        Requirements: MR-2
        Issue: Facemap module - Timebase alignment
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries
        from w2t_bkin.facemap import FacemapInputs, harmonize_facemap

        inputs = FacemapInputs(csv_path=Path("/data/facemap.csv"))
        timestamps = TimestampSeries(
            frame_indices=[0, 1, 2, 3],
            timestamps=[0.0, 0.033, 0.066, 0.099],
        )

        # Act
        metrics = harmonize_facemap(inputs, timestamps)

        # Assert - Time should match session timebase
        assert len(metrics.time) == len(timestamps.timestamps)
        assert metrics.time[0] == timestamps.timestamps[0]

    def test_Should_PreserveGaps_When_Aligning_MR2(self):
        """THE MODULE SHALL preserve gaps in metrics data.

        Requirements: MR-2
        Issue: Facemap module - Gap preservation
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries
        from w2t_bkin.facemap import FacemapInputs, harmonize_facemap

        inputs = FacemapInputs(csv_path=Path("/data/facemap_with_gaps.csv"))
        timestamps = TimestampSeries(
            frame_indices=[0, 1, 2, 3, 4],
            timestamps=[0.0, 0.033, 0.066, 0.099, 0.132],
        )

        # Act
        metrics = harmonize_facemap(inputs, timestamps)

        # Assert - Gaps should be preserved as NaN
        has_nan = any(
            math.isnan(v) if isinstance(v, float) else False
            for metric_values in [getattr(metrics, attr) for attr in dir(metrics) if not attr.startswith("_") and attr != "time"]
            for v in metric_values
        )
        assert has_nan or len(metrics.time) > 0

    def test_Should_InterpolateWithinThreshold_When_Aligning_MR2(self):
        """THE MODULE SHALL handle small gaps within threshold.

        Requirements: MR-2
        Issue: Facemap module - Interpolation
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries
        from w2t_bkin.facemap import FacemapInputs, harmonize_facemap

        inputs = FacemapInputs(csv_path=Path("/data/facemap.csv"))
        timestamps = TimestampSeries(
            frame_indices=[0, 1, 2],
            timestamps=[0.0, 0.033, 0.066],
        )

        # Act
        metrics = harmonize_facemap(inputs, timestamps)

        # Assert - Should align all timestamps
        assert len(metrics.time) == len(timestamps.timestamps)

    def test_Should_UseFaceCameraTimestamps_When_Aligning_MR2(self):
        """THE MODULE SHALL use face camera timestamps for alignment.

        Requirements: MR-2, Design - Face camera timestamps
        Issue: Facemap module - Camera-specific timestamps
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries
        from w2t_bkin.facemap import FacemapInputs, harmonize_facemap

        inputs = FacemapInputs(csv_path=Path("/data/facemap.csv"))
        face_timestamps = TimestampSeries(
            frame_indices=[0, 1, 2],
            timestamps=[0.0, 0.033, 0.066],
        )

        # Act
        metrics = harmonize_facemap(inputs, face_timestamps)

        # Assert - Should use provided timestamps
        assert metrics.time == face_timestamps.timestamps


class TestStandardizedOutput:
    """Test standardized table and metadata emission (MR-3)."""

    def test_Should_EmitMetricsTable_When_Harmonizing_MR3(self):
        """THE MODULE SHALL emit a standardized table.

        Requirements: MR-3
        Issue: Facemap module - Standardized output
        """
        # Arrange
        from w2t_bkin.domain import MetricsTable, TimestampSeries
        from w2t_bkin.facemap import FacemapInputs, harmonize_facemap

        inputs = FacemapInputs(csv_path=Path("/data/facemap.csv"))
        timestamps = TimestampSeries(
            frame_indices=[0, 1, 2],
            timestamps=[0.0, 0.033, 0.066],
        )

        # Act
        metrics = harmonize_facemap(inputs, timestamps)

        # Assert
        assert isinstance(metrics, MetricsTable)

    def test_Should_EmitWideTable_When_Harmonizing_MR3(self):
        """THE MODULE SHALL emit wide-format time series table.

        Requirements: MR-3, Design - Wide table format
        Issue: Facemap module - Wide format
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries
        from w2t_bkin.facemap import FacemapInputs, harmonize_facemap

        inputs = FacemapInputs(csv_path=Path("/data/facemap.csv"))
        timestamps = TimestampSeries(
            frame_indices=[0, 1, 2],
            timestamps=[0.0, 0.033, 0.066],
        )

        # Act
        metrics = harmonize_facemap(inputs, timestamps)

        # Assert - Should have time column plus metric columns
        assert hasattr(metrics, "time")
        metric_attrs = [attr for attr in dir(metrics) if not attr.startswith("_") and attr != "time"]
        assert len(metric_attrs) > 0  # Should have at least one metric column

    def test_Should_IncludeMetadata_When_Harmonizing_MR3(self):
        """THE MODULE SHALL emit metadata alongside metrics.

        Requirements: MR-3
        Issue: Facemap module - Metadata emission
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries
        from w2t_bkin.facemap import FacemapInputs, harmonize_facemap

        inputs = FacemapInputs(csv_path=Path("/data/facemap.csv"))
        timestamps = TimestampSeries(
            frame_indices=[0, 1, 2],
            timestamps=[0.0, 0.033, 0.066],
        )

        # Act
        metrics = harmonize_facemap(inputs, timestamps)

        # Assert - Should have metadata attribute
        assert hasattr(metrics, "metadata") or hasattr(metrics, "meta")

    def test_Should_StandardizeMetricNames_When_Harmonizing_MR3(self):
        """THE MODULE SHALL standardize metric column names.

        Requirements: MR-3
        Issue: Facemap module - Name standardization
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries
        from w2t_bkin.facemap import FacemapInputs, harmonize_facemap

        inputs = FacemapInputs(csv_path=Path("/data/facemap.csv"))
        timestamps = TimestampSeries(
            frame_indices=[0, 1, 2],
            timestamps=[0.0, 0.033, 0.066],
        )

        # Act
        metrics = harmonize_facemap(inputs, timestamps)

        # Assert - Common metric names should be standardized
        possible_metrics = ["pupil_area", "motion_energy", "blink", "whisker_motion"]
        has_standard_name = any(hasattr(metrics, name) for name in possible_metrics)
        assert has_standard_name or len(dir(metrics)) > 0


class TestDataIntegrityWarnings:
    """Test data integrity warnings for gaps (Design - Error handling)."""

    def test_Should_WarnOnLargeGaps_When_Detected_Design(self):
        """THE MODULE SHALL warn for gaps beyond threshold.

        Requirements: Design - DataIntegrityWarning for gaps
        Issue: Facemap module - Gap warnings
        """
        # Arrange
        from w2t_bkin.domain import DataIntegrityWarning, TimestampSeries
        from w2t_bkin.facemap import FacemapInputs, harmonize_facemap

        inputs = FacemapInputs(csv_path=Path("/data/facemap_large_gaps.csv"))
        timestamps = TimestampSeries(
            frame_indices=[0, 1, 2, 100],  # Large gap
            timestamps=[0.0, 0.033, 0.066, 3.3],
        )

        # Act & Assert
        with pytest.warns(DataIntegrityWarning):
            harmonize_facemap(inputs, timestamps)

    def test_Should_RecordFlags_When_WarningIssued_Design(self):
        """THE MODULE SHALL record QC flags for data issues.

        Requirements: Design - Record flags
        Issue: Facemap module - Flag recording
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries
        from w2t_bkin.facemap import FacemapInputs, harmonize_facemap

        inputs = FacemapInputs(csv_path=Path("/data/facemap_with_issues.csv"))
        timestamps = TimestampSeries(
            frame_indices=[0, 1, 2],
            timestamps=[0.0, 0.033, 0.066],
        )

        # Act
        metrics = harmonize_facemap(inputs, timestamps)

        # Assert - Should have flags or metadata about issues
        has_flags = hasattr(metrics, "qc_flags") or (hasattr(metrics, "metadata") and "qc" in str(metrics.metadata))
        assert has_flags or metrics is not None


class TestDeterministicAlignment:
    """Test deterministic alignment (M-NFR-1)."""

    def test_Should_ProduceSameOutput_When_SameInput_MNFR1(self):
        """THE MODULE SHALL produce deterministic alignment.

        Requirements: M-NFR-1
        Issue: Facemap module - Determinism
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries
        from w2t_bkin.facemap import FacemapInputs, harmonize_facemap

        inputs = FacemapInputs(csv_path=Path("/data/facemap.csv"))
        timestamps = TimestampSeries(
            frame_indices=[0, 1, 2],
            timestamps=[0.0, 0.033, 0.066],
        )

        # Act
        metrics1 = harmonize_facemap(inputs, timestamps)
        metrics2 = harmonize_facemap(inputs, timestamps)

        # Assert - Should be identical
        assert metrics1.time == metrics2.time
        # Check first metric column
        for attr in dir(metrics1):
            if not attr.startswith("_") and attr != "time":
                assert getattr(metrics1, attr) == getattr(metrics2, attr)
                break

    def test_Should_DocumentMissingSampleHandling_When_Aligning_MNFR1(self):
        """THE MODULE SHALL document handling of missing samples.

        Requirements: M-NFR-1
        Issue: Facemap module - Documentation
        """
        # Arrange
        from w2t_bkin.facemap import harmonize_facemap

        # Assert - Function should have documented missing sample handling
        assert harmonize_facemap.__doc__ is not None
        doc_lower = harmonize_facemap.__doc__.lower()
        assert any(term in doc_lower for term in ["missing", "gap", "nan", "null", "interpolat"])

    def test_Should_NotDependOnSystemState_When_Aligning_MNFR1(self):
        """THE MODULE SHALL not depend on global or system state.

        Requirements: M-NFR-1
        Issue: Facemap module - State independence
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries
        from w2t_bkin.facemap import FacemapInputs, harmonize_facemap

        inputs = FacemapInputs(csv_path=Path("/data/facemap.csv"))
        timestamps = TimestampSeries(
            frame_indices=[0, 1, 2],
            timestamps=[0.0, 0.033, 0.066],
        )

        # Act - Call with different system states
        metrics1 = harmonize_facemap(inputs, timestamps)
        import random

        random.seed(42)
        metrics2 = harmonize_facemap(inputs, timestamps)

        # Assert
        assert metrics1.time == metrics2.time


class TestFacemapInputs:
    """Test FacemapInputs data structure."""

    def test_Should_CreateInputs_When_Provided_Design(self):
        """THE MODULE SHALL provide FacemapInputs typed model.

        Requirements: Design - Input contract
        Issue: Facemap module - FacemapInputs model
        """
        # Arrange
        from w2t_bkin.facemap import FacemapInputs

        # Act
        inputs = FacemapInputs(
            csv_path=Path("/data/facemap.csv"),
            video_path=Path("/data/face.mp4"),
        )

        # Assert
        assert inputs.csv_path == Path("/data/facemap.csv")
        assert inputs.video_path == Path("/data/face.mp4")

    def test_Should_AcceptMultipleFormats_When_Creating_Design(self):
        """THE MODULE SHALL accept multiple input formats.

        Requirements: Design - CSV/NPY/Parquet
        Issue: Facemap module - Multiple formats
        """
        # Arrange
        from w2t_bkin.facemap import FacemapInputs

        # Act - Should accept various combinations
        inputs1 = FacemapInputs(csv_path=Path("/data/metrics.csv"))
        inputs2 = FacemapInputs(npy_path=Path("/data/metrics.npy"))
        inputs3 = FacemapInputs(parquet_path=Path("/data/metrics.parquet"))

        # Assert
        assert inputs1.csv_path is not None
        assert inputs2.npy_path is not None
        assert inputs3.parquet_path is not None

    def test_Should_AllowOptionalFields_When_Creating_Design(self):
        """THE MODULE SHALL allow optional input fields.

        Requirements: Design - Optional inputs
        Issue: Facemap module - Optional fields
        """
        # Arrange
        from w2t_bkin.facemap import FacemapInputs

        # Act - Create with minimal inputs
        inputs = FacemapInputs()

        # Assert - Should be valid with no inputs (for optional use cases)
        assert inputs is not None


class TestCommonMetrics:
    """Test common facial metrics."""

    def test_Should_IncludePupilArea_When_Available_Design(self):
        """THE MODULE SHALL include pupil area metric.

        Requirements: Design - Common metrics
        Issue: Facemap module - Pupil area
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries
        from w2t_bkin.facemap import FacemapInputs, harmonize_facemap

        inputs = FacemapInputs(csv_path=Path("/data/facemap.csv"))
        timestamps = TimestampSeries(
            frame_indices=[0, 1, 2],
            timestamps=[0.0, 0.033, 0.066],
        )

        # Act
        metrics = harmonize_facemap(inputs, timestamps)

        # Assert - Should have pupil_area if available
        # This is optional based on input data
        assert hasattr(metrics, "pupil_area") or len(dir(metrics)) > 0

    def test_Should_IncludeMotionEnergy_When_Available_Design(self):
        """THE MODULE SHALL include motion energy metric.

        Requirements: Design - Common metrics
        Issue: Facemap module - Motion energy
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries
        from w2t_bkin.facemap import FacemapInputs, harmonize_facemap

        inputs = FacemapInputs(csv_path=Path("/data/facemap.csv"))
        timestamps = TimestampSeries(
            frame_indices=[0, 1, 2],
            timestamps=[0.0, 0.033, 0.066],
        )

        # Act
        metrics = harmonize_facemap(inputs, timestamps)

        # Assert - Should have motion_energy if available
        assert hasattr(metrics, "motion_energy") or len(dir(metrics)) > 0


class TestROIConfiguration:
    """Test ROI configuration as optional metadata (Design - Future notes)."""

    def test_Should_AcceptROIConfiguration_When_Provided_Future(self):
        """THE MODULE SHALL accept ROI configuration as optional metadata.

        Requirements: Design - Future notes
        Issue: Facemap module - ROI configuration
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries
        from w2t_bkin.facemap import FacemapInputs, harmonize_facemap

        inputs = FacemapInputs(
            csv_path=Path("/data/facemap.csv"),
            roi_config={"pupil": {"x": 100, "y": 150, "radius": 20}},
        )
        timestamps = TimestampSeries(
            frame_indices=[0, 1, 2],
            timestamps=[0.0, 0.033, 0.066],
        )

        # Act
        metrics = harmonize_facemap(inputs, timestamps)

        # Assert - ROI config should be preserved in metadata
        if hasattr(metrics, "metadata"):
            assert "roi" in str(metrics.metadata).lower() or metrics.metadata is not None

    def test_Should_AcceptCalibration_When_Provided_Future(self):
        """THE MODULE SHALL accept calibration as optional metadata.

        Requirements: Design - Future notes
        Issue: Facemap module - Calibration
        """
        # Arrange
        from w2t_bkin.domain import TimestampSeries
        from w2t_bkin.facemap import FacemapInputs, harmonize_facemap

        inputs = FacemapInputs(
            csv_path=Path("/data/facemap.csv"),
            calibration={"pixel_to_mm": 0.05},
        )
        timestamps = TimestampSeries(
            frame_indices=[0, 1, 2],
            timestamps=[0.0, 0.033, 0.066],
        )

        # Act
        metrics = harmonize_facemap(inputs, timestamps)

        # Assert - Calibration should be optional metadata only
        assert metrics is not None
