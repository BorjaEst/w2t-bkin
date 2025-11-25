# Facemap Module NWB-First Migration Plan (Phase 4)

## Status: PLANNED (Not Started)

## Goal

Migrate facemap module from intermediate models (FacemapBundle/FacemapSignal/FacemapROI) to NWB-first architecture, following the successful pattern established in Phase 1 (Pose Module).

## Current Architecture (Phase 3)

```python
# Current flow
roi_specs = define_rois([...])  # Returns List[FacemapROI]
signals = compute_facemap_signals(video, rois)  # Returns List[FacemapSignal]
aligned = align_facemap_to_timebase(signals, times)  # Returns List[Dict]
bundle = FacemapBundle(rois=rois, signals=signals, ...)  # Intermediate model
# Later: Convert bundle to NWB TimeSeries in nwb.py
```

**Problems:**

- Intermediate FacemapBundle model adds complexity
- Conversion layer between FacemapSignal and pynwb.TimeSeries
- Duplicates NWB functionality with custom models

## Target Architecture (Phase 4)

```python
# NWB-first flow
from pynwb.behavior import BehavioralTimeSeries, TimeSeries

roi_specs = [{"name": "eye", "x": 100, "y": 200, "width": 50, "height": 50}]
signals = compute_facemap_signals(video, roi_specs)  # Returns List[TimeSeries]
aligned = align_facemap_to_timebase(signals, times)  # Returns List[TimeSeries]

# Direct NWB usage
behavioral_ts = BehavioralTimeSeries(name="FacialMotion")
for signal in aligned:
    behavioral_ts.add_timeseries(signal)
nwbfile.add_acquisition(behavioral_ts)
```

**Benefits:**

- ~135 lines of intermediate model code removed
- Direct pynwb.TimeSeries usage throughout
- No conversion layer needed
- Consistent with Pose Module pattern

## Implementation Tasks

### Task 1: Update models.py (15 minutes)

**File**: `src/w2t_bkin/facemap/models.py`

**Changes:**

```python
"""Facemap module models - NWB-first architecture.

MIGRATION NOTE (Phase 4):
This module has been migrated to NWB-first architecture.
Intermediate models (FacemapBundle, FacemapSignal, FacemapROI) have been removed.

The facemap module now produces pynwb.behavior.TimeSeries objects directly.
"""

from pynwb.base import TimeSeries
from pynwb.behavior import BehavioralTimeSeries

__all__ = [
    "TimeSeries",           # Base time series for individual ROI signals
    "BehavioralTimeSeries", # Container for multiple ROI signals
]
```

**Lines Removed:** ~135 (3 classes: FacemapROI, FacemapSignal, FacemapBundle)

### Task 2: Update core.py Functions (3-4 hours)

**File**: `src/w2t_bkin/facemap/core.py`

#### 2a. Update `define_rois()` (30 min)

**Current:**

```python
def define_rois(roi_specs: List[Dict]) -> List[FacemapROI]:
    """Returns list of FacemapROI objects."""
    return [FacemapROI(**spec) for spec in roi_specs]
```

**New:**

```python
def define_rois(roi_specs: List[Dict]) -> List[Dict]:
    """Validate and return ROI specifications as dicts.

    Args:
        roi_specs: List of ROI specifications with keys:
            - name: ROI identifier (e.g., "eye", "whisker")
            - x, y: Top-left coordinates (pixels)
            - width, height: ROI dimensions (pixels)

    Returns:
        Validated ROI specification dicts

    Raises:
        ValueError: If ROI specs are invalid or overlap
    """
    # Validate required fields
    for spec in roi_specs:
        if not all(k in spec for k in ["name", "x", "y", "width", "height"]):
            raise ValueError(f"ROI spec missing required fields: {spec}")
        if spec["width"] <= 0 or spec["height"] <= 0:
            raise ValueError(f"ROI dimensions must be positive: {spec}")

    # Check for overlaps (keep existing logic)
    for i, roi1 in enumerate(roi_specs):
        for roi2 in roi_specs[i+1:]:
            if _rois_overlap_dict(roi1, roi2):
                raise ValueError(f"ROIs overlap: {roi1['name']} and {roi2['name']}")

    return roi_specs
```

#### 2b. Update `compute_facemap_signals()` (2 hours)

**Current:**

```python
def compute_facemap_signals(
    video_path: Path,
    rois: List[FacemapROI]
) -> List[FacemapSignal]:
    """Compute motion energy, returns FacemapSignal objects."""
```

**New:**

```python
from pynwb.base import TimeSeries
import numpy as np

def compute_facemap_signals(
    video_path: Path,
    roi_specs: List[Dict],
    reference_frame: str = "(0, 0) is top-left corner"
) -> List[TimeSeries]:
    """Compute motion energy signals as pynwb TimeSeries.

    Args:
        video_path: Path to facial video file
        roi_specs: List of ROI specification dicts
        reference_frame: Coordinate system description

    Returns:
        List of pynwb.TimeSeries objects, one per ROI

    Example:
        >>> roi_specs = [
        ...     {"name": "eye", "x": 100, "y": 200, "width": 50, "height": 50},
        ...     {"name": "whisker", "x": 300, "y": 200, "width": 50, "height": 50}
        ... ]
        >>> signals = compute_facemap_signals("video.avi", roi_specs)
        >>> len(signals)
        2
        >>> signals[0].name
        'eye_motion_energy'
    """
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    time_series_list = []

    for roi_spec in roi_specs:
        # Extract ROI motion energy
        motion_values = []
        prev_frame_roi = None

        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # Reset to start

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Extract ROI
            x, y, w, h = roi_spec["x"], roi_spec["y"], roi_spec["width"], roi_spec["height"]
            roi_frame = frame[y:y+h, x:x+w]
            gray = cv2.cvtColor(roi_frame, cv2.COLOR_BGR2GRAY)

            # Compute motion energy (frame difference)
            if prev_frame_roi is not None:
                diff = cv2.absdiff(gray, prev_frame_roi)
                motion = np.mean(diff) / 255.0  # Normalize to 0-1
                motion_values.append(motion)
            else:
                motion_values.append(0.0)  # First frame has no motion

            prev_frame_roi = gray

        # Create TimeSeries
        ts = TimeSeries(
            name=f"{roi_spec['name']}_motion_energy",
            data=np.array(motion_values),
            unit="a.u.",  # arbitrary units (normalized motion energy)
            rate=fps,
            description=f"Motion energy from ROI '{roi_spec['name']}' at ({roi_spec['x']}, {roi_spec['y']}), {roi_spec['width']}x{roi_spec['height']} pixels",
            comments=f"reference_frame={reference_frame}",
        )
        time_series_list.append(ts)

    cap.release()
    return time_series_list
```

#### 2c. Update `align_facemap_to_timebase()` (1 hour)

**Current:**

```python
def align_facemap_to_timebase(
    signals: List[Dict],
    reference_times: List[float],
    mapping: str = "nearest"
) -> List[Dict]:
    """Align signals to timebase, returns list of dicts."""
```

**New:**

```python
from pynwb.base import TimeSeries

def align_facemap_to_timebase(
    signals: List[TimeSeries],
    reference_times: List[float],
    mapping: str = "nearest"
) -> List[TimeSeries]:
    """Align TimeSeries to reference timebase.

    Args:
        signals: List of TimeSeries objects from compute_facemap_signals()
        reference_times: Reference timestamps to align to (seconds)
        mapping: Alignment strategy ("nearest" or "linear")

    Returns:
        List of TimeSeries with aligned timestamps

    Note:
        Creates new TimeSeries objects with aligned timestamps.
        Original rate information is preserved in description.
    """
    aligned_series = []

    for ts in signals:
        # Get original data and timestamps
        original_data = ts.data[:]
        if hasattr(ts, 'timestamps') and ts.timestamps is not None:
            original_times = ts.timestamps[:]
        else:
            # Reconstruct from rate
            original_times = np.arange(len(original_data)) / ts.rate

        # Align data to reference times
        if mapping == "nearest":
            aligned_data = _align_nearest(original_data, original_times, reference_times)
        elif mapping == "linear":
            aligned_data = _align_linear(original_data, original_times, reference_times)
        else:
            raise ValueError(f"Unknown mapping strategy: {mapping}")

        # Create new TimeSeries with aligned timestamps
        aligned_ts = TimeSeries(
            name=ts.name,
            data=aligned_data,
            timestamps=reference_times,
            unit=ts.unit,
            description=f"{ts.description} | Aligned using {mapping} mapping from original rate {ts.rate} Hz",
            comments=ts.comments if hasattr(ts, 'comments') else "",
        )
        aligned_series.append(aligned_ts)

    return aligned_series
```

### Task 3: Update **init**.py (10 minutes)

**File**: `src/w2t_bkin/facemap/__init__.py`

**Changes:**

```python
"""Facemap motion energy computation - NWB-first architecture (Phase 4).

The facemap module now produces pynwb.behavior.TimeSeries objects directly.

Public API:
-----------
    from w2t_bkin.facemap import (
        TimeSeries,
        BehavioralTimeSeries,
        define_rois,
        compute_facemap_signals,       # Returns List[TimeSeries]
        align_facemap_to_timebase,     # Returns List[TimeSeries]
    )
"""

from .core import (
    FacemapError,
    align_facemap_to_timebase,
    compute_facemap_signals,
    define_rois,
    import_facemap_output,
    validate_facemap_sampling_rate,
)
from .models import BehavioralTimeSeries, TimeSeries

__all__ = [
    "TimeSeries",
    "BehavioralTimeSeries",
    "FacemapError",
    "define_rois",
    "import_facemap_output",
    "compute_facemap_signals",
    "align_facemap_to_timebase",
    "validate_facemap_sampling_rate",
]
```

### Task 4: Update Tests (2-3 hours)

**File**: `tests/unit/test_facemap.py`

**Changes:**

1. Remove fixtures for FacemapBundle/FacemapSignal/FacemapROI
2. Add pynwb TimeSeries fixtures
3. Update test assertions to check TimeSeries properties
4. Verify alignment functions work with TimeSeries

**Example Test:**

```python
def test_compute_facemap_signals_returns_timeseries(tmp_video):
    """Should return pynwb TimeSeries objects."""
    from pynwb.base import TimeSeries
    from w2t_bkin.facemap import compute_facemap_signals

    roi_specs = [
        {"name": "eye", "x": 10, "y": 10, "width": 20, "height": 20}
    ]

    signals = compute_facemap_signals(tmp_video, roi_specs)

    assert len(signals) == 1
    assert isinstance(signals[0], TimeSeries)
    assert signals[0].name == "eye_motion_energy"
    assert signals[0].unit == "a.u."
    assert len(signals[0].data) > 0
```

### Task 5: Update Pipeline Integration (1 hour)

**File**: `src/w2t_bkin/pipeline.py`

**Current:**

```python
# Phase 4.3: Facemap (if enabled)
if config.facemap and config.facemap.enabled:
    facemap_bundle = ...  # Returns FacemapBundle
    # Later converted to NWB in nwb.py
```

**New:**

```python
# Phase 4.3: Facemap (if enabled)
if config.facemap and config.facemap.enabled:
    from pynwb.behavior import BehavioralTimeSeries

    roi_specs = [...]  # From config
    signals = compute_facemap_signals(video_path, roi_specs)
    aligned = align_facemap_to_timebase(signals, reference_times)

    # Add directly to NWBFile
    behavioral_ts = BehavioralTimeSeries(name="FacialMotion")
    for signal in aligned:
        behavioral_ts.add_timeseries(signal)
    nwbfile.add_acquisition(behavioral_ts)
```

## Breaking Changes

### Removed Types

- `FacemapROI` class
- `FacemapSignal` class
- `FacemapBundle` class

### Changed Function Signatures

#### `define_rois()`

- **Before:** Returns `List[FacemapROI]`
- **After:** Returns `List[Dict]` (validated ROI specs)

#### `compute_facemap_signals()`

- **Before:** `compute_facemap_signals(video, rois: List[FacemapROI]) -> List[FacemapSignal]`
- **After:** `compute_facemap_signals(video, roi_specs: List[Dict]) -> List[TimeSeries]`

#### `align_facemap_to_timebase()`

- **Before:** `align_facemap_to_timebase(signals: List[Dict], ...) -> List[Dict]`
- **After:** `align_facemap_to_timebase(signals: List[TimeSeries], ...) -> List[TimeSeries]`

## Migration Guide for Users

### Old Code (Phase 3)

```python
from w2t_bkin.facemap import FacemapBundle, FacemapROI, define_rois, compute_facemap_signals

roi_specs = [{"name": "eye", "x": 100, "y": 200, "width": 50, "height": 50}]
rois = define_rois(roi_specs)  # Returns List[FacemapROI]
signals = compute_facemap_signals(video, rois)  # Returns List[FacemapSignal]
bundle = FacemapBundle(rois=rois, signals=signals, ...)
```

### New Code (Phase 4)

```python
from w2t_bkin.facemap import compute_facemap_signals, BehavioralTimeSeries

roi_specs = [{"name": "eye", "x": 100, "y": 200, "width": 50, "height": 50}]
signals = compute_facemap_signals(video, roi_specs)  # Returns List[TimeSeries]

# Direct NWB usage
behavioral_ts = BehavioralTimeSeries(name="FacialMotion")
for signal in signals:
    behavioral_ts.add_timeseries(signal)
nwbfile.add_acquisition(behavioral_ts)
```

## Estimated Effort

- **Total Time**: 6-8 hours
- **Lines Removed**: ~135 (models) + ~50 (conversion logic) = ~185 lines
- **Lines Modified**: ~200 (core.py functions)
- **Net Code Change**: -185 lines + 200 modified ≈ slight reduction with cleaner architecture

## Success Criteria

- ✅ All facemap tests pass with new TimeSeries-based API
- ✅ No FacemapBundle/FacemapSignal/FacemapROI references remain
- ✅ Pipeline integration uses TimeSeries directly
- ✅ Documentation updated (MIGRATION.md, architecture docs)
- ✅ Consistent with Pose Module NWB-first pattern

## Next Steps

1. Review this plan with maintainers
2. Create feature branch: `feature/phase4-facemap-nwb-first`
3. Implement tasks 1-5 sequentially
4. Run full test suite after each task
5. Update documentation
6. Create pull request with migration guide

## References

- Phase 1 (Pose Module) migration: Successful pattern to follow
- `docs/architecture_status.md`: Phase 1 completion details
- `docs/MIGRATION.md`: Existing pose migration guide
