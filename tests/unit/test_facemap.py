"""Unit tests for the facemap module.

Tests facial metrics import and computation as specified in
requirements.md FR-6 and design.md.

All tests follow TDD Red Phase principles with clear EARS requirements.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


# ============================================================================
# Test: Facemap File Import (FR-6)
# ============================================================================


class TestFacemapImport:
    """Test Facemap metrics import from .npy files (FR-6)."""

    def test_Should_ImportFacemapFile_When_ValidNpy_Issue_Facemap_FR6(self, tmp_path: Path):
        """THE SYSTEM SHALL import Facemap .npy outputs.

        Requirements: FR-6 (Import facial metrics)
        Issue: Facemap module - NPY file import
        """
        # Arrange
        from w2t_bkin.facemap import import_facemap_metrics

        facemap_file = tmp_path / "facemap_output.npy"
        facemap_file.write_bytes(b"mock npy data")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Act
        summary = import_facemap_metrics(facemap_file, output_dir=output_dir)

        # Assert - Should successfully import
        assert summary is not None
        assert hasattr(summary, "source_type")
        assert summary.source_type == "imported"

    def test_Should_RaiseMissingInputError_When_FileNotFound_Issue_Facemap_NFR8(self, tmp_path: Path):
        """THE SYSTEM SHALL fail fast when Facemap file is missing.

        Requirements: NFR-8 (Data integrity)
        Issue: Facemap module - Input validation
        """
        # Arrange
        from w2t_bkin.facemap import import_facemap_metrics

        missing_file = tmp_path / "nonexistent.npy"
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Act & Assert - Should raise MissingInputError
        with pytest.raises(Exception):  # MissingInputError
            import_facemap_metrics(missing_file, output_dir=output_dir)

    def test_Should_RaiseFacemapFormatError_When_InvalidNpy_Issue_Facemap_Design(self, tmp_path: Path):
        """THE SYSTEM SHALL reject invalid .npy file formats.

        Requirements: Design - Error handling
        Issue: Facemap module - Format validation
        """
        # Arrange
        from w2t_bkin.facemap import import_facemap_metrics

        invalid_file = tmp_path / "invalid.txt"
        invalid_file.write_text("not a valid npy file")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Act & Assert - Should raise FacemapFormatError
        with pytest.raises(Exception):  # FacemapFormatError
            import_facemap_metrics(invalid_file, output_dir=output_dir)


# ============================================================================
# Test: Metrics Computation (FR-6)
# ============================================================================


class TestMetricsComputation:
    """Test Facemap metrics computation from video (FR-6)."""

    def test_Should_ComputeMetrics_When_VideoProvided_Issue_Facemap_FR6(self, tmp_path: Path):
        """THE SYSTEM SHALL compute facial metrics from face video.

        Requirements: FR-6 (Compute facial metrics)
        Issue: Facemap module - Metrics computation
        """
        # Arrange
        from w2t_bkin.facemap import compute_facemap

        face_video = tmp_path / "cam_face.mp4"
        face_video.write_text("mock video data")
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        
        roi = {"x": 100, "y": 100, "width": 400, "height": 300}

        # Act
        summary = compute_facemap(face_video, output_dir=output_dir, roi=roi)

        # Assert - Should successfully compute metrics
        assert summary is not None
        assert hasattr(summary, "source_type")
        assert summary.source_type == "computed"

    def test_Should_UseDefaultROI_When_NotProvided_Issue_Facemap_Config(self, tmp_path: Path):
        """THE SYSTEM SHALL use default ROI when not specified.

        Requirements: Configuration defaults
        Issue: Facemap module - ROI handling
        """
        # Arrange
        from w2t_bkin.facemap import compute_facemap

        face_video = tmp_path / "cam_face.mp4"
        face_video.write_text("mock video data")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Act
        summary = compute_facemap(face_video, output_dir=output_dir)

        # Assert - Should use default ROI
        assert hasattr(summary, "model_info")
        assert "roi" in summary.model_info


# ============================================================================
# Test: Metrics Validation (NFR-8)
# ============================================================================


class TestMetricsValidation:
    """Test facial metrics range validation (NFR-8)."""

    def test_Should_ValidatePupilArea_When_Importing_Issue_Facemap_NFR8(self):
        """THE SYSTEM SHALL validate pupil area is non-negative.

        Requirements: NFR-8 (Data integrity)
        Issue: Facemap module - Pupil area validation
        """
        # Arrange
        from w2t_bkin.facemap import _validate_pupil_area

        valid_areas = [0.0, 100.5, 200.0]
        invalid_areas = [-10.0, -1.0]

        # Act & Assert - Should accept valid areas
        assert _validate_pupil_area(valid_areas) is True

        # Should reject negative areas
        with pytest.raises(Exception):  # MetricsRangeError
            _validate_pupil_area(invalid_areas)

    def test_Should_ValidateMotionEnergy_When_Importing_Issue_Facemap_NFR8(self):
        """THE SYSTEM SHALL validate motion energy is in [0,1] range.

        Requirements: NFR-8 (Data integrity)
        Issue: Facemap module - Motion energy validation
        """
        # Arrange
        from w2t_bkin.facemap import _validate_motion_energy

        valid_energy = [0.0, 0.5, 0.99, 1.0]
        invalid_energy = [-0.1, 1.5, 2.0]

        # Act & Assert - Should accept valid energy
        assert _validate_motion_energy(valid_energy) is True

        # Should reject out-of-range energy
        with pytest.raises(Exception):  # MetricsRangeError
            _validate_motion_energy(invalid_energy)

    def test_Should_HandleNaNValues_When_MissingSamples_Issue_Facemap_Design(self, tmp_path: Path):
        """THE SYSTEM SHALL preserve NaN for missing samples.

        Requirements: Design §3.4 (Missing samples as NaN)
        Issue: Facemap module - Missing data handling
        """
        # Arrange
        from w2t_bkin.facemap import import_facemap_metrics

        facemap_file = tmp_path / "sparse_facemap.npy"
        facemap_file.write_bytes(b"mock npy with missing data")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Act
        summary = import_facemap_metrics(facemap_file, output_dir=output_dir)

        # Assert - Should report missing samples
        assert "missing_samples" in summary.statistics
        assert summary.statistics["missing_samples"] >= 0


# ============================================================================
# Test: Timebase Alignment (FR-6)
# ============================================================================


class TestTimebaseAlignment:
    """Test alignment to session timebase (FR-6)."""

    def test_Should_AlignToSessionTimebase_When_TimestampsProvided_Issue_Facemap_FR6(self, tmp_path: Path):
        """THE SYSTEM SHALL align metrics to session timebase.

        Requirements: FR-6 (Align to session timebase)
        Issue: Facemap module - Timestamp alignment
        """
        # Arrange
        from w2t_bkin.facemap import import_facemap_metrics

        facemap_file = tmp_path / "facemap.npy"
        facemap_file.write_bytes(b"mock npy data")
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        
        timestamps_dir = tmp_path / "sync"
        timestamps_dir.mkdir()
        (timestamps_dir / "timestamps_cam_face.csv").write_text(
            "frame_index,timestamp\n0,0.0\n1,0.033\n2,0.066\n"
        )

        # Act
        summary = import_facemap_metrics(
            facemap_file, output_dir=output_dir, timestamps_dir=timestamps_dir
        )

        # Assert - Should apply timebase alignment
        assert hasattr(summary, "timebase_alignment")
        assert summary.timebase_alignment["sync_applied"] is True

    def test_Should_RaiseTimestampAlignmentError_When_FrameCountMismatch_Issue_Facemap_Design(self, tmp_path: Path):
        """THE SYSTEM SHALL detect frame count mismatches with sync data.

        Requirements: Design - Error handling
        Issue: Facemap module - Alignment validation
        """
        # Arrange
        from w2t_bkin.facemap import import_facemap_metrics

        facemap_file = tmp_path / "facemap.npy"
        facemap_file.write_bytes(b"mock npy data with 1000 frames")
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        
        timestamps_dir = tmp_path / "sync"
        timestamps_dir.mkdir()
        # Timestamps for only 2 frames
        (timestamps_dir / "timestamps_cam_face.csv").write_text(
            "frame_index,timestamp\n0,0.0\n1,0.033\n"
        )

        # Act & Assert - Should raise TimestampAlignmentError
        with pytest.raises(Exception):  # TimestampAlignmentError
            import_facemap_metrics(
                facemap_file, output_dir=output_dir, timestamps_dir=timestamps_dir
            )


# ============================================================================
# Test: Output Generation (FR-6, NFR-3)
# ============================================================================


class TestOutputGeneration:
    """Test metrics output generation (FR-6, NFR-3)."""

    def test_Should_GenerateParquetOutput_When_Importing_Issue_Facemap_FR6(self, tmp_path: Path):
        """THE SYSTEM SHALL generate metrics table in Parquet format.

        Requirements: FR-6, Design §3.4 (Wide table format)
        Issue: Facemap module - Output generation
        """
        # Arrange
        from w2t_bkin.facemap import import_facemap_metrics

        facemap_file = tmp_path / "facemap.npy"
        facemap_file.write_bytes(b"mock npy data")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Act
        summary = import_facemap_metrics(facemap_file, output_dir=output_dir)

        # Assert - Should create Parquet output
        parquet_file = output_dir / "facemap_metrics.parquet"
        assert parquet_file.exists() or hasattr(summary, "output_path")

    def test_Should_GenerateSummary_When_Importing_Issue_Facemap_NFR3(self, tmp_path: Path):
        """THE SYSTEM SHALL generate facemap summary JSON with statistics.

        Requirements: NFR-3 (Observability)
        Issue: Facemap module - Summary generation
        """
        # Arrange
        from w2t_bkin.facemap import import_facemap_metrics

        facemap_file = tmp_path / "facemap.npy"
        facemap_file.write_bytes(b"mock npy data")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Act
        summary = import_facemap_metrics(facemap_file, output_dir=output_dir)

        # Assert - Should contain required summary fields
        assert hasattr(summary, "session_id")
        assert hasattr(summary, "source_type")
        assert hasattr(summary, "statistics")
        assert hasattr(summary, "model_info")

    def test_Should_IncludeStatistics_When_Summarizing_Issue_Facemap_FR8(self, tmp_path: Path):
        """THE SYSTEM SHALL include metrics statistics for QC reporting.

        Requirements: FR-8 (QC report)
        Issue: Facemap module - Statistics computation
        """
        # Arrange
        from w2t_bkin.facemap import import_facemap_metrics

        facemap_file = tmp_path / "facemap.npy"
        facemap_file.write_bytes(b"mock npy data")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Act
        summary = import_facemap_metrics(facemap_file, output_dir=output_dir)

        # Assert - Should include comprehensive statistics
        assert "total_samples" in summary.statistics
        assert "missing_samples" in summary.statistics
        assert "coverage_ratio" in summary.statistics
        assert "metrics" in summary.statistics


# ============================================================================
# Test: Provenance Capture (NFR-11)
# ============================================================================


class TestProvenance:
    """Test provenance metadata capture (NFR-11)."""

    def test_Should_RecordFacemapVersion_When_Importing_Issue_Facemap_NFR11(self, tmp_path: Path):
        """THE SYSTEM SHALL record Facemap version for provenance.

        Requirements: NFR-11 (Provenance)
        Issue: Facemap module - Version tracking
        """
        # Arrange
        from w2t_bkin.facemap import import_facemap_metrics

        facemap_file = tmp_path / "facemap.npy"
        facemap_file.write_bytes(b"mock npy data")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Act
        summary = import_facemap_metrics(facemap_file, output_dir=output_dir)

        # Assert - Should include Facemap version
        assert hasattr(summary, "model_info")
        assert "facemap_version" in summary.model_info

    def test_Should_RecordModelHash_When_Computed_Issue_Facemap_NFR11(self, tmp_path: Path):
        """THE SYSTEM SHALL record model hash when computed.

        Requirements: NFR-11 (Provenance)
        Issue: Facemap module - Model tracking
        """
        # Arrange
        from w2t_bkin.facemap import compute_facemap

        face_video = tmp_path / "cam_face.mp4"
        face_video.write_text("mock video")
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        
        model_path = tmp_path / "model.pt"
        model_path.write_bytes(b"mock model")

        # Act
        summary = compute_facemap(
            face_video, output_dir=output_dir, model_path=model_path
        )

        # Assert - Should include model hash
        assert hasattr(summary, "model_info")
        assert "model_hash" in summary.model_info


# ============================================================================
# Test: Idempotence (NFR-2)
# ============================================================================


class TestIdempotence:
    """Test idempotent re-runs (NFR-2)."""

    def test_Should_SkipExisting_When_OutputExists_Issue_Facemap_NFR2(self, tmp_path: Path):
        """THE SYSTEM SHALL skip import if output exists and input unchanged.

        Requirements: NFR-2 (Idempotent re-run)
        Issue: Facemap module - Idempotence
        """
        # Arrange
        from w2t_bkin.facemap import import_facemap_metrics

        facemap_file = tmp_path / "facemap.npy"
        facemap_file.write_bytes(b"mock npy data")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Act - First run
        summary1 = import_facemap_metrics(facemap_file, output_dir=output_dir)

        # Act - Second run without changes
        summary2 = import_facemap_metrics(facemap_file, output_dir=output_dir)

        # Assert - Should skip re-import
        assert hasattr(summary2, "skipped") and summary2.skipped is True

    def test_Should_ForceReimport_When_FlagSet_Issue_Facemap_NFR2(self, tmp_path: Path):
        """THE SYSTEM SHALL re-import when forced, even if output exists.

        Requirements: NFR-2
        Issue: Facemap module - Force re-run
        """
        # Arrange
        from w2t_bkin.facemap import import_facemap_metrics

        facemap_file = tmp_path / "facemap.npy"
        facemap_file.write_bytes(b"mock npy data")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Pre-existing output
        import_facemap_metrics(facemap_file, output_dir=output_dir)

        # Act - Force re-import
        summary = import_facemap_metrics(facemap_file, output_dir=output_dir, force=True)

        # Assert - Should re-import
        assert hasattr(summary, "skipped") and summary.skipped is False


# ============================================================================
# Test: Edge Cases and Boundary Conditions
# ============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_Should_HandleEmptyMetrics_When_NoDetections_Issue_Facemap_Design(self, tmp_path: Path):
        """THE SYSTEM SHALL handle facemap outputs with no detections.

        Requirements: Design - Error handling
        Issue: Facemap module - Empty output handling
        """
        # Arrange
        from w2t_bkin.facemap import import_facemap_metrics

        empty_file = tmp_path / "empty_facemap.npy"
        empty_file.write_bytes(b"mock empty npy")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Act
        summary = import_facemap_metrics(empty_file, output_dir=output_dir)

        # Assert - Should complete with warnings
        assert hasattr(summary, "warnings")
        assert len(summary.warnings) > 0

    def test_Should_HandleHighMissingRate_When_PoorTracking_Issue_Facemap_NFR3(self, tmp_path: Path):
        """THE SYSTEM SHALL flag high missing data rates.

        Requirements: NFR-3 (Observability)
        Issue: Facemap module - Quality flagging
        """
        # Arrange
        from w2t_bkin.facemap import import_facemap_metrics

        poor_tracking = tmp_path / "poor_tracking.npy"
        poor_tracking.write_bytes(b"mock sparse tracking data")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Act
        summary = import_facemap_metrics(poor_tracking, output_dir=output_dir)

        # Assert - Should report high missing rate
        assert "coverage_ratio" in summary.statistics
        coverage = summary.statistics["coverage_ratio"]
        assert 0.0 <= coverage <= 1.0


# ============================================================================
# Test: Helper Functions
# ============================================================================


class TestHelperFunctions:
    """Test internal helper functions."""

    def test_Should_ExtractMetrics_When_ParsingNpy_Issue_Facemap_Internal(self):
        """Internal helper should extract metric arrays from .npy structure.

        Issue: Facemap module - NPY parsing helpers
        """
        # Arrange
        from w2t_bkin.facemap import _extract_facemap_metrics

        mock_npy_data = {
            "pupil": [100.0, 105.0, 102.0],
            "motion": [0.5, 0.6, 0.55],
            "blink": [0, 0, 1]
        }

        # Act
        metrics = _extract_facemap_metrics(mock_npy_data)

        # Assert - Should extract metric dict
        assert isinstance(metrics, dict)
        assert "pupil_area" in metrics or "pupil" in metrics

    def test_Should_ComputeCoverage_When_AnalyzingMetrics_Issue_Facemap_Internal(self):
        """Internal helper should compute coverage statistics.

        Issue: Facemap module - Coverage computation
        """
        # Arrange
        from w2t_bkin.facemap import _compute_coverage

        metrics_with_nan = {
            "pupil_area": [100.0, float('nan'), 102.0, 105.0],
            "motion_energy": [0.5, 0.6, float('nan'), 0.55]
        }

        # Act
        coverage = _compute_coverage(metrics_with_nan)

        # Assert - Should compute coverage ratios
        assert coverage["pupil_area"] == 0.75  # 3/4
        assert coverage["motion_energy"] == 0.75  # 3/4
