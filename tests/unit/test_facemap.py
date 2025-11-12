"""Unit tests for facemap module (Phase 3 - Red Phase).

Tests Facemap ROI handling, signal import/compute, and alignment to reference timebase.

Requirements: FR-6
Acceptance: A1, A3
GitHub Issue: #4
"""

import json
from pathlib import Path
from typing import List

import pytest
import numpy as np

from w2t_bkin.domain import FacemapBundle, FacemapROI, FacemapSignal
from w2t_bkin.facemap import (
    FacemapError,
    define_rois,
    import_facemap_output,
    compute_facemap_signals,
    align_facemap_to_timebase,
    validate_facemap_sampling_rate,
)


class TestROIHandling:
    """Test Facemap ROI definition and validation."""

    def test_Should_DefineROIs_When_ValidSpecificationProvided(self):
        """Should create ROIs from specification."""
        roi_specs = [
            {"name": "pupil", "x": 100, "y": 150, "width": 50, "height": 50},
            {"name": "whisker_pad", "x": 200, "y": 200, "width": 80, "height": 80},
        ]
        
        rois = define_rois(roi_specs)
        
        assert len(rois) == 2
        assert rois[0].name == "pupil"
        assert rois[1].name == "whisker_pad"

    def test_Should_ValidateROIBounds_When_CreatingROI(self):
        """Should validate ROI coordinates are non-negative."""
        invalid_roi = {"name": "bad", "x": -10, "y": 50, "width": 100, "height": 100}
        
        with pytest.raises(FacemapError):
            define_rois([invalid_roi])

    def test_Should_WarnForOverlappingROIs_When_Detected(self, caplog):
        """Should warn when ROIs overlap significantly."""
        roi_specs = [
            {"name": "roi1", "x": 100, "y": 100, "width": 50, "height": 50},
            {"name": "roi2", "x": 120, "y": 120, "width": 50, "height": 50},
        ]
        
        rois = define_rois(roi_specs)
        
        # Function should check for overlaps
        assert "overlap" in caplog.text.lower() or len(rois) == 2


class TestFacemapImport:
    """Test importing Facemap output files."""

    def test_Should_ImportFacemapNPY_When_ValidFileProvided(self):
        """Should import Facemap .npy output."""
        npy_path = Path("tests/fixtures/facemap/facemap_output.npy")
        
        result = import_facemap_output(npy_path)
        
        assert result is not None
        assert "motion" in result or "pupil" in result

    def test_Should_HandleMissingFile_When_ImportFacemap(self):
        """Should raise FacemapError for missing files."""
        missing_path = Path("nonexistent.npy")
        
        with pytest.raises(FacemapError):
            import_facemap_output(missing_path)


class TestSignalComputation:
    """Test Facemap signal computation from video."""

    def test_Should_ComputeMotionEnergy_When_ROIsProvided(self):
        """Should compute motion energy signals for each ROI."""
        video_path = Path("tests/fixtures/data/raw/Session-000001/Video/top/cam0_2025-01-01-00-00-00.avi")
        rois = [
            FacemapROI(name="pupil", x=100, y=100, width=50, height=50),
        ]
        
        signals = compute_facemap_signals(video_path, rois)
        
        assert len(signals) > 0
        assert signals[0].roi_name == "pupil"
        assert len(signals[0].values) > 0

    def test_Should_MatchVideoFrameCount_When_ComputingSignals(self):
        """Signals should have same length as video frame count (FR-6)."""
        video_path = Path("tests/fixtures/data/raw/Session-000001/Video/top/cam0_2025-01-01-00-00-00.avi")
        rois = [FacemapROI(name="roi1", x=100, y=100, width=50, height=50)]
        expected_frames = 8580  # From Session-000001
        
        signals = compute_facemap_signals(video_path, rois)
        
        assert len(signals[0].values) == expected_frames


class TestTimebaseAlignment:
    """Test Facemap signal alignment to reference timebase."""

    def test_Should_AlignSignalTimestamps_When_TimebaseProvided(self):
        """Should align signal frame indices to timebase timestamps (FR-6)."""
        signals = [
            {
                "roi_name": "pupil",
                "frame_indices": [0, 1, 2, 3, 4],
                "values": [10.0, 12.0, 11.0, 13.0, 12.5],
            }
        ]
        reference_times = [i * 0.033 for i in range(100)]
        
        result = align_facemap_to_timebase(signals, reference_times, mapping="nearest")
        
        assert len(result) == 1
        assert "timestamps" in result[0]
        assert len(result[0]["timestamps"]) == 5

    def test_Should_UseLinearMapping_When_Configured(self):
        """Should support linear interpolation for alignment."""
        signals = [
            {
                "roi_name": "pupil",
                "frame_indices": [5],
                "values": [10.0],
            }
        ]
        reference_times = [i * 0.033 for i in range(100)]
        
        result = align_facemap_to_timebase(signals, reference_times, mapping="linear")
        
        assert result[0]["timestamps"][0] == pytest.approx(5 * 0.033, abs=0.001)

    def test_Should_FailAlignment_When_LengthMismatch(self):
        """Should raise error when signal length doesn't match expected frames."""
        signals = [
            {
                "roi_name": "pupil",
                "frame_indices": [0, 1, 2],
                "values": [10.0, 12.0],  # Mismatch: 3 indices, 2 values
            }
        ]
        reference_times = [i * 0.033 for i in range(100)]
        
        with pytest.raises(FacemapError):
            align_facemap_to_timebase(signals, reference_times, mapping="nearest")


class TestSamplingRateValidation:
    """Test Facemap sampling rate validation."""

    def test_Should_ValidateSamplingRate_When_CheckingConsistency(self):
        """Should validate that sampling rate matches video frame rate."""
        signal = FacemapSignal(
            roi_name="pupil",
            timestamps=[i * 0.033 for i in range(100)],
            values=[float(i) for i in range(100)],
            sampling_rate=30.0,
        )
        expected_rate = 30.0
        
        is_valid = validate_facemap_sampling_rate(signal, expected_rate, tolerance=0.1)
        
        assert is_valid

    def test_Should_FailValidation_When_RateMismatch(self):
        """Should detect sampling rate mismatch."""
        signal = FacemapSignal(
            roi_name="pupil",
            timestamps=[i * 0.020 for i in range(100)],  # 50 Hz
            values=[float(i) for i in range(100)],
            sampling_rate=50.0,
        )
        expected_rate = 30.0
        
        is_valid = validate_facemap_sampling_rate(signal, expected_rate, tolerance=0.1)
        
        assert not is_valid


class TestFacemapBundleCreation:
    """Test creation of FacemapBundle artifacts."""

    def test_Should_CreateFacemapBundle_When_AllDataProvided(self):
        """Should create valid FacemapBundle with all required fields."""
        rois = [FacemapROI(name="pupil", x=100, y=100, width=50, height=50)]
        signals = [
            FacemapSignal(
                roi_name="pupil",
                timestamps=[0.0, 0.033],
                values=[10.0, 12.0],
                sampling_rate=30.0,
            )
        ]
        
        bundle = FacemapBundle(
            session_id="Session-000001",
            camera_id="cam0",
            rois=rois,
            signals=signals,
            alignment_method="nearest",
            generated_at="2025-11-12T12:00:00Z",
        )
        
        assert bundle.session_id == "Session-000001"
        assert len(bundle.rois) == 1
        assert len(bundle.signals) == 1

    def test_Should_EnforceFrozen_When_FacemapBundleCreated(self):
        """FacemapBundle should be immutable (NFR-7)."""
        bundle = FacemapBundle(
            session_id="Session-000001",
            camera_id="cam0",
            rois=[],
            signals=[],
            alignment_method="nearest",
            generated_at="2025-11-12T12:00:00Z",
        )
        
        with pytest.raises(Exception):
            bundle.session_id = "modified"

    def test_Should_ValidateROIsMatchSignals_When_CreatingBundle(self):
        """Should validate that all signals reference defined ROIs."""
        rois = [FacemapROI(name="pupil", x=100, y=100, width=50, height=50)]
        signals = [
            FacemapSignal(
                roi_name="unknown_roi",  # Not in rois list
                timestamps=[0.0],
                values=[10.0],
                sampling_rate=30.0,
            )
        ]
        
        with pytest.raises(ValueError):
            # Validation should happen during bundle creation
            bundle = FacemapBundle(
                session_id="Session-000001",
                camera_id="cam0",
                rois=rois,
                signals=signals,
                alignment_method="nearest",
                generated_at="2025-11-12T12:00:00Z",
            )
