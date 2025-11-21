# Implementation Tasks: NWB-First Architecture Migration

Detailed task breakdown for Phase 1 (Pose Module). Focus on incremental, testable changes.

## Current Phase: Pose Module Migration

**Goal**: Eliminate PoseBundle intermediate model; use ndx-pose PoseEstimation throughout.

**Strategy**: Work backwards from NWB assembly to data import, removing conversion at each step.

---

## Task Checklist

### 0. Add build_pose_estimation() Function ✅ COMPLETED

**File**: `src/w2t_bkin/pose/core.py`

**Changes**:

- ✅ Added `build_pose_estimation()` function that converts harmonized pose data to PoseEstimation
- ✅ Updated imports to include ndx-pose types
- ✅ Updated `pose/__init__.py` to export `build_pose_estimation`
- ✅ Wrote 7 comprehensive tests in `test_pose.py::TestBuildPoseEstimation`
- ✅ All tests passing (20 passed, 2 skipped)

**Function Signature**:

```python
def build_pose_estimation(
    data: List[Dict],
    reference_times: List[float],
    camera_id: str,
    bodyparts: List[str],
    skeleton_edges: Optional[List[List[int]]] = None,
    source: str = "dlc",
    model_name: str = "unknown",
) -> PoseEstimation
```

**Completed**: 2025-11-21  
**Time Spent**: 2.5 hours  
**Status**: Production-ready, fully tested

---

### 1. Pose Models Cleanup 🔲

**File**: `src/w2t_bkin/pose/models.py`

- [ ] Remove `PoseKeypoint` class definition
- [ ] Remove `PoseFrame` class definition
- [ ] Remove `PoseBundle` class definition
- [ ] Add imports: `from ndx_pose import PoseEstimation, PoseEstimationSeries, Skeleton`
- [ ] Update `__all__` to re-export ndx-pose types
- [ ] Add module docstring explaining NWB-native approach

**Estimated Time**: 15 minutes  
**Testing**: Verify imports work, no tests should break yet (nothing uses models.py directly)

---

### 1.5. Update align_pose_to_timebase() ✅ COMPLETED

**File**: `src/w2t_bkin/pose/core.py`  
**Function**: `align_pose_to_timebase()`

**Changes**:

- ✅ Added optional parameters: `camera_id`, `bodyparts`, `skeleton_edges`, `model_name`
- ✅ Supports two modes:
  - Legacy mode (camera_id=None): Returns `List[PoseFrame]` for backward compatibility
  - NWB-first mode (camera_id provided): Returns `PoseEstimation` directly
- ✅ Calls `build_pose_estimation()` internally when in NWB-first mode
- ✅ Updated function signature and comprehensive docstring
- ✅ Added 5 comprehensive tests in `test_pose.py::TestAlignPoseToTimebaseNWBFirst`

**Function Signature**:

```python
def align_pose_to_timebase(
    data: List[Dict],
    reference_times: List[float],
    mapping: str = "nearest",
    source: str = "dlc",
    camera_id: Optional[str] = None,
    bodyparts: Optional[List[str]] = None,
    skeleton_edges: Optional[List[List[int]]] = None,
    model_name: Optional[str] = None,
) -> List  # Returns PoseEstimation if camera_id provided, else List[PoseFrame]
```

**Completed**: 2025-11-21  
**Time Spent**: 1.5 hours  
**Status**: Production-ready, fully tested, backward compatible

---

### 2. Update DLC Import Function 🔲

**File**: `src/w2t_bkin/pose/core.py`  
**Function**: `import_dlc_pose()`

**Changes**:

- [ ] Parse DLC H5 into NumPy arrays (keypoint-major format immediately)
- [ ] Create one `PoseEstimationSeries` per bodypart:
  - data: `np.array([[x1, y1], [x2, y2], ...])` shape `(n_frames, 2)`
  - confidence: `np.array([c1, c2, ...])` shape `(n_frames,)`
  - timestamps: Empty for now (will be added during alignment)
  - reference_frame: `"(0, 0) is top-left corner"`
- [ ] Return `List[PoseEstimationSeries]` instead of `List[Dict]`
- [ ] Update function signature and docstring
- [ ] Update type hints

**Estimated Time**: 2-3 hours  
**Testing**: Update `test_import_dlc_pose()` to assert PoseEstimationSeries properties

**Code Pattern**:

```python
from ndx_pose import PoseEstimationSeries
import numpy as np

series_list = []
for bodypart in bodyparts:
    xy_data = np.array([[x, y] for frame in frames])  # shape: (n_frames, 2)
    conf_data = np.array([c for frame in frames])     # shape: (n_frames,)

    series = PoseEstimationSeries(
        name=bodypart,
        data=xy_data,
        reference_frame="(0, 0) is top-left corner",
        confidence=conf_data,
        unit="pixels",
        timestamps=None,  # Will be set during alignment
    )
    series_list.append(series)

return series_list
```

---

### 3. Update SLEAP Import Function 🔲

**File**: `src/w2t_bkin/pose/core.py`  
**Function**: `import_sleap_pose()`

**Changes**: Same pattern as DLC import

- [ ] Parse SLEAP H5 into NumPy arrays (keypoint-major)
- [ ] Create `PoseEstimationSeries` per bodypart
- [ ] Return `List[PoseEstimationSeries]`
- [ ] Update function signature and docstring

**Estimated Time**: 2-3 hours  
**Testing**: Update `test_import_sleap_pose()`

---

### 4. Update Harmonization Functions 🔲

**File**: `src/w2t_bkin/pose/core.py`  
**Functions**: `harmonize_dlc_to_canonical()`, `harmonize_sleap_to_canonical()`

**Current**: Accept `List[Dict]`, return `List[Dict]`  
**Target**: Accept `List[PoseEstimationSeries]`, return `List[PoseEstimationSeries]`

**Changes**:

- [ ] Update signature to accept/return `List[PoseEstimationSeries]`
- [ ] Map keypoint names by creating new PoseEstimationSeries with canonical names
- [ ] Copy data, confidence, timestamps from source series
- [ ] Filter out unmapped keypoints
- [ ] Update docstrings

**Estimated Time**: 2 hours  
**Testing**: Update harmonization tests

**Code Pattern**:

```python
def harmonize_dlc_to_canonical(
    series_list: List[PoseEstimationSeries],
    skeleton_map: Dict[str, str]
) -> List[PoseEstimationSeries]:
    """Map DLC keypoint names to canonical skeleton names."""
    harmonized = []
    for series in series_list:
        if series.name in skeleton_map:
            canonical_name = skeleton_map[series.name]
            new_series = PoseEstimationSeries(
                name=canonical_name,
                data=series.data,
                reference_frame=series.reference_frame,
                confidence=series.confidence,
                unit=series.unit,
                timestamps=series.timestamps,
            )
            harmonized.append(new_series)
    return harmonized
```

---

### 5. Update Alignment Function 🔲

**File**: `src/w2t_bkin/pose/core.py`  
**Function**: `align_pose_to_timebase()`

**Current**: Returns `PoseBundle`  
**Target**: Returns `PoseEstimation`

**Changes**:

- [ ] Accept `List[PoseEstimationSeries]` (pre-built, no timestamps)
- [ ] Accept `TimebaseProvider` and alignment strategy
- [ ] Compute timestamps array
- [ ] Add timestamps to each PoseEstimationSeries (or create new ones)
- [ ] Create `Skeleton` object with nodes (bodypart names) and edges
- [ ] Create `PoseEstimation` container with all series
- [ ] Return `PoseEstimation` object
- [ ] Update function signature and docstring

**Estimated Time**: 2-3 hours  
**Testing**: Update `test_align_pose_to_timebase()`

**Code Pattern**:

```python
from ndx_pose import PoseEstimation, Skeleton

def align_pose_to_timebase(
    series_list: List[PoseEstimationSeries],
    timebase_provider: TimebaseProvider,
    skeleton_edges: Optional[List[List[int]]] = None,
    ...
) -> PoseEstimation:
    """Align pose series to reference timebase."""

    # Compute timestamps
    n_frames = len(series_list[0].data)
    timestamps = timebase_provider.get_timestamps(n_samples=n_frames)

    # Add timestamps to each series (or create new series with timestamps)
    aligned_series = []
    for series in series_list:
        new_series = PoseEstimationSeries(
            name=series.name,
            data=series.data,
            reference_frame=series.reference_frame,
            confidence=series.confidence,
            unit=series.unit,
            timestamps=timestamps,
        )
        aligned_series.append(new_series)

    # Create skeleton
    nodes = [s.name for s in aligned_series]
    skeleton = Skeleton(
        name="subject",
        nodes=nodes,
        edges=skeleton_edges or [],
    )

    # Create PoseEstimation container
    pose_estimation = PoseEstimation(
        name=f"PoseEstimation_{camera_id}",
        pose_estimation_series=aligned_series,
        skeleton=skeleton,
        source_software="DeepLabCut",  # or "SLEAP"
        source_software_version="2.3.x",
        scorer=model_name,
    )

    return pose_estimation
```

---

### 6. Update Sync Module 🔲

**File**: `src/w2t_bkin/sync/pose.py`  
**Function**: `sync_pose_to_timebase()`

**Changes**:

- [ ] Update signature: accept `List[PoseEstimationSeries]`, return `PoseEstimation`
- [ ] Call `align_pose_to_timebase()` which now returns PoseEstimation
- [ ] Update docstring

**Estimated Time**: 30 minutes  
**Testing**: Update sync tests

---

### 7. Remove NWB Conversion Function 🔲

**File**: `src/w2t_bkin/nwb.py`  
**Function**: `_pose_bundle_to_ndx_pose()`

**Changes**:

- [ ] Delete entire `_pose_bundle_to_ndx_pose()` function (~80 lines)
- [ ] Update `_build_nwb_file()` signature: accept `Optional[PoseEstimation]` instead of `Optional[PoseBundle]`
- [ ] Remove PoseBundle import
- [ ] Update function to add PoseEstimation directly to behavior module
- [ ] Update docstrings

**Estimated Time**: 1 hour  
**Testing**: Update integration tests

**Code Pattern**:

```python
def _build_nwb_file(
    session_id: str,
    ...
    pose_estimation: Optional[PoseEstimation] = None,  # Changed from PoseBundle
    ...
) -> NWBFile:
    """Assemble NWB file from pre-built NWB objects."""

    # ... existing code ...

    if pose_estimation is not None:
        # Add Skeleton to Skeletons container (if not already added)
        if pose_estimation.skeleton is not None:
            skeletons = Skeletons(name="skeletons")
            skeletons.add_skeleton(pose_estimation.skeleton)
            behavior_module.add(skeletons)

        # Add PoseEstimation directly (no conversion needed!)
        behavior_module.add(pose_estimation)
```

---

### 8. Update Pipeline Orchestration 🔲

**File**: `src/w2t_bkin/pipeline.py`  
**Function**: `run_session()`

**Changes**:

- [ ] Update to expect `PoseEstimation` from pose processing
- [ ] Pass `PoseEstimation` directly to `assemble_nwb()`
- [ ] Update type hints
- [ ] Update comments

**Estimated Time**: 30 minutes  
**Testing**: Integration tests should pass

---

### 9. Update Tests 🔲

**Files**: `tests/unit/test_pose.py`, `tests/integration/test_phase_4_nwb.py`

**Changes**:

- [ ] Replace PoseBundle fixtures with PoseEstimation fixtures
- [ ] Update assertions to check PoseEstimationSeries properties
- [ ] Use pynwb testing utilities if needed
- [ ] Verify all tests pass

**Estimated Time**: 2-3 hours  
**Testing**: `pytest tests/unit/test_pose.py tests/integration/test_phase_4_nwb.py -xvs`

---

## Summary

**Total Estimated Time**: 15-20 hours for complete pose module migration

**Critical Path**:

1. Models cleanup (15 min)
2. Import functions (4-6 hrs)
3. Harmonization (2 hrs)
4. Alignment (2-3 hrs)
5. Remove conversion (1 hr)
6. Update tests (2-3 hrs)

**Success Criteria**:

- [ ] All tests pass
- [ ] No PoseBundle references remain in pose module
- [ ] No conversion function in nwb.py for pose
- [ ] PoseEstimation flows end-to-end from import to NWB file

**Ready to Start**: Task 1 (Pose Models Cleanup)
