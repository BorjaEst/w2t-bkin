"""Facemap ROI computation and facial motion signal extraction (Phase 3 - Optional).

Defines Regions of Interest (ROIs) on facial videos, computes motion energy
or SVD-based signals within each ROI, and aligns the resulting time series
to the reference timebase for integration into NWB files.

The module supports multiple motion metrics (absolute difference, SVD components),
handles multi-camera setups, and produces signals compatible with NWB TimeSeries
for behavioral neuroscience analysis.

Key Features:
-------------
- **ROI Definition**: Rectangular or polygonal regions on facial videos
- **Motion Metrics**: Absolute difference, SVD components, optical flow (planned)
- **Multi-Camera Support**: Process multiple facial views independently
- **Temporal Alignment**: Sync signals to reference timebase
- **NWB Integration**: Produces FacemapBundle for NWB TimeSeries

Main Functions:
---------------
- define_rois: Create ROI specifications from config
- compute_motion_energy: Calculate per-ROI motion signals
- compute_svd_components: Extract principal motion components (planned)
- align_signals_to_timebase: Sync signals to reference timestamps
- create_facemap_bundle: Package signals for NWB

Requirements:
-------------
- FR-6: Compute facial motion signals
- FR-FACE-1: Define ROIs from configuration
- FR-FACE-2: Compute motion energy per ROI
- FR-FACE-3: Align signals to reference timebase

Acceptance Criteria:
-------------------
- A-FACE-1: Define ROIs from config specs
- A-FACE-2: Compute motion energy for each ROI
- A-FACE-3: Align signals to reference timebase
- A-FACE-4: Create FacemapBundle for NWB

Data Flow:
----------
1. define_rois → ROI specifications
2. compute_motion_energy / compute_svd_components → Raw signals
3. align_signals_to_timebase → Sync to reference
4. create_facemap_bundle → Package for NWB

Example:
--------
>>> from w2t_bkin.facemap import define_rois, compute_motion_energy
>>> from w2t_bkin.sync import create_timebase_provider
>>>
>>> # Define ROIs
>>> roi_specs = [
...     {"name": "left_whisker", "x": 100, "y": 200, "w": 50, "h": 50},
...     {"name": "right_whisker", "x": 300, "y": 200, "w": 50, "h": 50}
... ]
>>> rois = define_rois(roi_specs)
>>>
>>> # Compute motion energy
>>> signals = compute_motion_energy("facial_video.avi", rois)
>>> print(f"Computed {len(signals)} ROI signals")
>>>
>>> # Align to reference timebase
>>> from w2t_bkin.facemap import align_signals_to_timebase
>>> aligned = align_signals_to_timebase(
...     signals,
...     reference_times=timebase_provider.get_timestamps(len(signals[0].values))
... )
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

import cv2
import numpy as np

from w2t_bkin.domain import FacemapBundle, FacemapROI, FacemapSignal

logger = logging.getLogger(__name__)


class FacemapError(Exception):
    """Base exception for facemap-related errors."""

    pass


def define_rois(roi_specs: List[Dict]) -> List[FacemapROI]:
    """Create FacemapROI objects from specifications.

    Args:
        roi_specs: List of ROI specification dicts

    Returns:
        List of FacemapROI objects

    Raises:
        FacemapError: If ROI coordinates are invalid
    """
    rois = []

    for spec in roi_specs:
        # Validate coordinates are non-negative
        if spec["x"] < 0 or spec["y"] < 0:
            raise FacemapError(f"ROI coordinates must be non-negative: {spec}")

        if spec["width"] <= 0 or spec["height"] <= 0:
            raise FacemapError(f"ROI dimensions must be positive: {spec}")

        roi = FacemapROI(name=spec["name"], x=spec["x"], y=spec["y"], width=spec["width"], height=spec["height"])
        rois.append(roi)

    # Check for overlaps
    for i in range(len(rois)):
        for j in range(i + 1, len(rois)):
            if _rois_overlap(rois[i], rois[j]):
                logger.warning(f"ROIs overlap: {rois[i].name} and {rois[j].name}")

    return rois


def _rois_overlap(roi1: FacemapROI, roi2: FacemapROI) -> bool:
    """Check if two ROIs overlap significantly."""
    # Simple bounding box overlap check
    x1_min, x1_max = roi1.x, roi1.x + roi1.width
    y1_min, y1_max = roi1.y, roi1.y + roi1.height
    x2_min, x2_max = roi2.x, roi2.x + roi2.width
    y2_min, y2_max = roi2.y, roi2.y + roi2.height

    # Check if rectangles overlap
    overlap_x = max(0, min(x1_max, x2_max) - max(x1_min, x2_min))
    overlap_y = max(0, min(y1_max, y2_max) - max(y1_min, y2_min))

    if overlap_x > 0 and overlap_y > 0:
        overlap_area = overlap_x * overlap_y
        area1 = roi1.width * roi1.height
        area2 = roi2.width * roi2.height

        # Consider significant if overlap > 20% of smaller ROI
        min_area = min(area1, area2)
        if overlap_area / min_area > 0.2:
            return True

    return False


def import_facemap_output(npy_path: Path) -> Dict:
    """Import precomputed Facemap .npy output.

    Args:
        npy_path: Path to Facemap .npy file

    Returns:
        Dict containing Facemap data

    Raises:
        FacemapError: If file doesn't exist or format is invalid
    """
    if not npy_path.exists():
        raise FacemapError(f"Facemap file not found: {npy_path}")

    try:
        data = np.load(npy_path, allow_pickle=True).item()
        return data
    except Exception as e:
        raise FacemapError(f"Failed to load Facemap file: {e}")


def compute_facemap_signals(video_path: Path, rois: List[FacemapROI]) -> List[FacemapSignal]:
    """Compute motion energy signals for each ROI.

    Args:
        video_path: Path to video file
        rois: List of ROIs to compute signals for

    Returns:
        List of FacemapSignal objects

    Raises:
        FacemapError: If video cannot be read
    """
    if not video_path.exists():
        raise FacemapError(f"Video file not found: {video_path}")

    try:
        cap = cv2.VideoCapture(str(video_path))

        if not cap.isOpened():
            raise FacemapError(f"Cannot open video: {video_path}")

        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # Initialize signal storage
        roi_signals = {roi.name: [] for roi in rois}

        # Read frames and compute motion energy
        prev_frame = None
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Convert to grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            if prev_frame is not None:
                # Compute motion for each ROI
                for roi in rois:
                    # Extract ROI regions
                    roi_prev = prev_frame[roi.y : roi.y + roi.height, roi.x : roi.x + roi.width]
                    roi_curr = gray[roi.y : roi.y + roi.height, roi.x : roi.x + roi.width]

                    # Compute absolute difference (motion energy)
                    diff = cv2.absdiff(roi_curr, roi_prev)
                    motion_energy = float(np.mean(diff))

                    roi_signals[roi.name].append(motion_energy)
            else:
                # First frame - no motion
                for roi in rois:
                    roi_signals[roi.name].append(0.0)

            prev_frame = gray
            frame_idx += 1

        cap.release()

        # Create FacemapSignal objects
        signals = []
        for roi in rois:
            # Generate timestamps based on frame rate
            timestamps = [i / fps for i in range(len(roi_signals[roi.name]))]

            signal = FacemapSignal(roi_name=roi.name, timestamps=timestamps, values=roi_signals[roi.name], sampling_rate=fps)
            signals.append(signal)

        return signals

    except Exception as e:
        raise FacemapError(f"Failed to compute Facemap signals: {e}")


def align_facemap_to_timebase(signals: List[Dict], reference_times: List[float], mapping: str = "nearest") -> List[Dict]:
    """Align facemap signal timestamps to reference timebase.

    Args:
        signals: List of signal dicts with frame_indices and values
        reference_times: Reference timestamps from sync
        mapping: Alignment strategy ("nearest" or "linear")

    Returns:
        List of aligned signal dicts with timestamps

    Raises:
        FacemapError: If alignment fails
    """
    aligned_signals = []

    for signal in signals:
        frame_indices = signal["frame_indices"]
        values = signal["values"]

        # Validate lengths match
        if len(frame_indices) != len(values):
            raise FacemapError(f"Frame indices length ({len(frame_indices)}) != values length ({len(values)})")

        # Map frame indices to timestamps
        timestamps = []
        for frame_idx in frame_indices:
            if mapping == "nearest":
                if frame_idx < len(reference_times):
                    timestamp = reference_times[frame_idx]
                else:
                    timestamp = reference_times[-1]
            elif mapping == "linear":
                if frame_idx < len(reference_times):
                    timestamp = reference_times[frame_idx]
                else:
                    # Linear extrapolation
                    if len(reference_times) >= 2:
                        dt = reference_times[-1] - reference_times[-2]
                        timestamp = reference_times[-1] + dt * (frame_idx - len(reference_times) + 1)
                    else:
                        timestamp = reference_times[-1]
            else:
                raise FacemapError(f"Unknown mapping strategy: {mapping}")

            timestamps.append(timestamp)

        aligned_signals.append({"roi_name": signal["roi_name"], "timestamps": timestamps, "values": values})

    return aligned_signals


def validate_facemap_sampling_rate(signal: FacemapSignal, expected_rate: float, tolerance: float = 0.1) -> bool:
    """Validate that signal sampling rate matches expected rate.

    Args:
        signal: FacemapSignal to validate
        expected_rate: Expected sampling rate in Hz
        tolerance: Tolerance for rate mismatch (fraction)

    Returns:
        True if sampling rate is within tolerance, False otherwise
    """
    if len(signal.timestamps) < 2:
        return True

    # Compute actual rate from timestamps
    total_time = signal.timestamps[-1] - signal.timestamps[0]
    num_samples = len(signal.timestamps)
    actual_rate = (num_samples - 1) / total_time if total_time > 0 else 0

    # Check if within tolerance
    rate_diff = abs(actual_rate - expected_rate)
    relative_diff = rate_diff / expected_rate if expected_rate > 0 else 0

    if relative_diff > tolerance:
        logger.warning(f"Sampling rate mismatch: actual={actual_rate:.2f} Hz, " f"expected={expected_rate:.2f} Hz (diff={relative_diff:.1%})")
        return False

    return True


if __name__ == "__main__":
    """Usage examples for facemap module."""
    from pathlib import Path

    import numpy as np

    print("=" * 70)
    print("W2T-BKIN Facemap Module - Usage Examples")
    print("=" * 70)
    print()

    print("Example 1: Define ROI (Region of Interest)")
    print("-" * 50)

    # Define a rectangular ROI for whisker region
    whisker_roi = {"name": "whiskers_right", "type": "rectangle", "x": 100, "y": 150, "width": 80, "height": 60, "description": "Right whisker region"}

    print(f"ROI: {whisker_roi['name']}")
    print(f"Type: {whisker_roi['type']}")
    print(f"Bounds: ({whisker_roi['x']}, {whisker_roi['y']}) " f"{whisker_roi['width']}x{whisker_roi['height']}")
    print()

    # Example 2: Simulate motion energy signal
    print("Example 2: Simulate Facemap Signal")
    print("-" * 50)

    # Create synthetic motion energy signal (30 fps, 10 seconds)
    timestamps = np.linspace(0, 10, 300)
    motion_energy = np.abs(np.sin(timestamps * 2) + np.random.randn(300) * 0.1)

    signal = {
        "roi_name": "whiskers_right",
        "signal_type": "motion_energy",
        "timestamps": timestamps.tolist(),
        "values": motion_energy.tolist(),
        "sampling_rate": 30.0,
    }

    print(f"Signal type: {signal['signal_type']}")
    print(f"ROI: {signal['roi_name']}")
    print(f"Duration: {timestamps[-1]:.1f} seconds")
    print(f"Samples: {len(signal['values'])}")
    print(f"Mean motion energy: {np.mean(motion_energy):.3f}")
    print()

    # Example 3: Validate sampling rate
    print("Example 3: Validate Sampling Rate")
    print("-" * 50)

    actual_rate = 30.0
    expected_rate = 30.0
    is_valid = validate_facemap_sampling_rate(actual_rate, expected_rate, tolerance=0.01)

    print(f"Actual rate: {actual_rate} Hz")
    print(f"Expected rate: {expected_rate} Hz")
    print(f"Valid: {is_valid}")
    print()

    print("Production usage:")
    print("  from w2t_bkin.facemap import define_rois, compute_facemap_signals")
    print("  rois = define_rois(video_path, roi_definitions)")
    print("  signals = compute_facemap_signals(video_path, rois)")
    print()

    print("=" * 70)
    print("Examples completed. See module docstring for API details.")
    print("=" * 70)
