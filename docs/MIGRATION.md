# Migration Guide: Legacy to NWB-First Architecture

## Overview

The w2t-bkin pipeline is transitioning from intermediate data models (PoseBundle, PoseFrame, PoseKeypoint) to an **NWB-first architecture** where processing modules produce NWB objects directly. This guide helps you migrate existing code to the new pattern.

## Status: Dual-Mode Support (Stable)

**Current State**: The pose module supports both legacy and NWB-first workflows during the transition period.

- ✅ **Legacy path**: Still functional, uses PoseBundle → nwb.py conversion
- ✅ **NWB-first path**: Preferred, creates ndx_pose.PoseEstimation directly
- ⚠️ **Deprecation warnings**: PoseBundle/PoseFrame/PoseKeypoint emit warnings when instantiated

## Why Migrate?

### Benefits of NWB-First

1. **Standards-compliant**: Uses ndx-pose (community standard for pose data in NWB)
2. **Reduced complexity**: Eliminates intermediate models and conversion steps
3. **Better performance**: Direct NWB object creation is more efficient
4. **Future-proof**: Aligns with NWB ecosystem and best practices
5. **Cleaner architecture**: Each module produces NWB objects it owns

### Legacy Pattern Problems

- Intermediate models (PoseBundle) duplicate NWB functionality
- Conversion overhead: Dict → PoseBundle → NWB
- Harder to maintain: Two representations of same data
- Not standards-aligned: Custom models vs community standards

---

## Quick Migration Checklist

For existing code using PoseBundle:

- [ ] Replace `PoseBundle` creation with `build_pose_estimation()` calls
- [ ] Update `align_pose_to_timebase()` calls to use NWB-first mode
- [ ] Pass `PoseEstimation` objects to `assemble_nwb(pose_estimations=[...])`
- [ ] Remove imports of `PoseBundle`, `PoseFrame`, `PoseKeypoint`
- [ ] Test end-to-end workflow

---

## Migration Examples

### Example 1: Basic Pose Import and Alignment

#### Legacy Pattern (DEPRECATED)

```python
from w2t_bkin.pose import (
    import_dlc_pose,
    harmonize_dlc_to_canonical,
    align_pose_to_timebase,
    PoseBundle  # ⚠️ DEPRECATED
)
from w2t_bkin.nwb import assemble_nwb

# Import and harmonize
raw_data = import_dlc_pose(dlc_file)
harmonized = harmonize_dlc_to_canonical(raw_data, skeleton_name="mouse_12pt")

# Align to timebase (returns PoseBundle)
bundle = align_pose_to_timebase(
    harmonized_data=harmonized,
    session_id="Session-001",
    camera_id="cam0",
    model_name="dlc_mouse_v1",
    timebase=timebase,
    alignment_method="nearest"
)

# Assemble NWB (implicit conversion from PoseBundle)
nwb_file = assemble_nwb(
    session_id="Session-001",
    session_start_time=datetime.now(),
    subject_id="Mouse-001",
    pose_bundles=[bundle],  # ⚠️ Legacy parameter
    devices=devices,
    cameras=cameras
)
```

#### NWB-First Pattern (PREFERRED)

```python
from w2t_bkin.pose import (
    import_dlc_pose,
    harmonize_dlc_to_canonical,
    align_pose_to_timebase,
    build_pose_estimation  # ✅ NEW
)
from w2t_bkin.nwb import assemble_nwb

# Import and harmonize (same as legacy)
raw_data = import_dlc_pose(dlc_file)
harmonized = harmonize_dlc_to_canonical(raw_data, skeleton_name="mouse_12pt")

# Align to timebase (NWB-first mode with camera_id)
pose_estimation = align_pose_to_timebase(
    harmonized_data=harmonized,
    timebase=timebase,
    alignment_method="nearest",
    camera_id="cam0",  # ✅ Triggers NWB-first mode
    bodyparts=["nose", "left_ear", "right_ear"],  # ✅ Required for NWB-first
    camera_device=camera_device,  # ✅ Device reference
    model_name="dlc_mouse_v1",
    skeleton_name="mouse_12pt"
)

# Assemble NWB (direct PoseEstimation)
nwb_file = assemble_nwb(
    session_id="Session-001",
    session_start_time=datetime.now(),
    subject_id="Mouse-001",
    pose_estimations=[pose_estimation],  # ✅ NWB-first parameter
    devices=devices,
    cameras=cameras
)
```

### Example 2: Manual PoseEstimation Creation

If you have harmonized data (list of dicts) and don't need alignment:

```python
from w2t_bkin.pose import build_pose_estimation
from ndx_pose import Skeleton
from pynwb import NWBFile
from datetime import datetime

# Create skeleton
skeleton = Skeleton(
    name="mouse_12pt",
    nodes=["nose", "left_ear", "right_ear"],
    edges=[[0, 1], [0, 2]]  # nose connects to ears
)

# Harmonized data (from import_dlc_pose + harmonize_dlc_to_canonical)
harmonized_data = [
    {
        "frame_index": 0,
        "timestamp": 0.0333,
        "bodyparts": {
            "nose": {"x": 100.5, "y": 200.3, "confidence": 0.95},
            "left_ear": {"x": 90.2, "y": 195.1, "confidence": 0.88},
            "right_ear": {"x": 110.8, "y": 195.3, "confidence": 0.91}
        }
    },
    # ... more frames
]

# Build PoseEstimation directly
pose_estimation = build_pose_estimation(
    harmonized_data=harmonized_data,
    camera_id="cam0",
    skeleton=skeleton,
    camera_device=camera_device,
    model_name="dlc_mouse_v1",
    bodypart_names=["nose", "left_ear", "right_ear"]
)

# Add to NWB file
nwbfile = NWBFile(
    session_description="Mouse behavior session",
    identifier="Session-001",
    session_start_time=datetime.now()
)
nwbfile.add_device(camera_device)
nwbfile.add_acquisition(camera_video)
nwbfile.processing["behavior"].add(pose_estimation)
```

---

## API Reference: Key Functions

### `build_pose_estimation()`

Creates ndx_pose.PoseEstimation from harmonized data.

**Parameters:**

- `harmonized_data`: List[Dict] - Frame data with bodypart coordinates
- `camera_id`: str - Camera identifier
- `skeleton`: Skeleton - ndx_pose Skeleton object
- `camera_device`: Device - NWB Device reference
- `model_name`: str - Pose model identifier (e.g., "dlc_mouse_v1")
- `bodypart_names`: List[str] - Ordered list of bodypart names

**Returns:** `PoseEstimation` (from ndx_pose)

**Example:**

```python
pose_est = build_pose_estimation(
    harmonized_data=harmonized,
    camera_id="cam0",
    skeleton=skeleton,
    camera_device=device,
    model_name="dlc_mouse_v1",
    bodypart_names=["nose", "left_ear", "right_ear"]
)
```

### `align_pose_to_timebase()` - Dual Mode

Aligns pose timestamps to reference timebase. **Supports both legacy and NWB-first modes.**

**NWB-First Mode (when `camera_id` provided):**

```python
pose_estimation = align_pose_to_timebase(
    harmonized_data=harmonized,
    timebase=timebase,
    alignment_method="nearest",
    camera_id="cam0",           # ✅ Triggers NWB-first
    bodyparts=["nose", "..."],  # ✅ Required
    camera_device=device,       # ✅ Required
    model_name="dlc_mouse_v1",
    skeleton_name="mouse_12pt"
)
```

**Legacy Mode (when `camera_id` is None):**

```python
bundle = align_pose_to_timebase(
    harmonized_data=harmonized,
    session_id="Session-001",
    camera_id_legacy="cam0",  # Note: different param name
    model_name="dlc_mouse_v1",
    timebase=timebase,
    alignment_method="nearest"
)
```

**Migration Tip:** Check function signature - if you see `camera_id=None` in your call, add the required NWB-first parameters.

### `assemble_nwb()` - Dual Mode

Assembles NWB file. **Supports both legacy and NWB-first inputs.**

**NWB-First Mode:**

```python
nwbfile = assemble_nwb(
    session_id="Session-001",
    session_start_time=datetime.now(),
    subject_id="Mouse-001",
    pose_estimations=[pose_est1, pose_est2],  # ✅ List[PoseEstimation]
    devices=devices,
    cameras=cameras
)
```

**Legacy Mode:**

```python
nwbfile = assemble_nwb(
    session_id="Session-001",
    session_start_time=datetime.now(),
    subject_id="Mouse-001",
    pose_bundles=[bundle1, bundle2],  # ⚠️ List[PoseBundle] - deprecated
    devices=devices,
    cameras=cameras
)
```

---

## Common Migration Scenarios

### Scenario 1: You Have a Working Script Using PoseBundle

**Steps:**

1. Identify all PoseBundle creation points
2. Replace with `build_pose_estimation()` or NWB-first `align_pose_to_timebase()`
3. Update `assemble_nwb()` call to use `pose_estimations` parameter
4. Remove PoseBundle imports
5. Test end-to-end

### Scenario 2: You're Writing New Code

**Recommendation:** Start with NWB-first from the beginning.

1. Use `import_dlc_pose()` + `harmonize_dlc_to_canonical()` for data import
2. Use `align_pose_to_timebase()` with `camera_id` for alignment
3. Pass `PoseEstimation` directly to `assemble_nwb(pose_estimations=[...])`

### Scenario 3: You Have Integration Tests Using PoseBundle

**Options:**

- **Quick fix**: Suppress deprecation warnings in tests (`warnings.filterwarnings("ignore", category=DeprecationWarning)`)
- **Proper fix**: Update test fixtures to use NWB-first pattern (recommended)

**Example Test Update:**

```python
# Legacy fixture
@pytest.fixture
def pose_bundle():
    return PoseBundle(
        session_id="Test-001",
        camera_id="cam0",
        model_name="dlc_test",
        skeleton="mouse_12pt",
        frames=[...],
        alignment_method="nearest",
        mean_confidence=0.9,
        generated_at="2025-11-21T10:00:00Z"
    )

# NWB-first fixture
@pytest.fixture
def pose_estimation(camera_device, skeleton):
    harmonized = [
        {"frame_index": 0, "timestamp": 0.0, "bodyparts": {...}},
        # ...
    ]
    return build_pose_estimation(
        harmonized_data=harmonized,
        camera_id="cam0",
        skeleton=skeleton,
        camera_device=camera_device,
        model_name="dlc_test",
        bodypart_names=["nose", "left_ear", "right_ear"]
    )
```

---

## Troubleshooting

### Issue: DeprecationWarning Spam

**Symptom:** Seeing many deprecation warnings during tests or execution.

**Solutions:**

1. **Recommended**: Migrate to NWB-first pattern (see examples above)
2. **Temporary**: Suppress warnings in tests:
   ```python
   import warnings
   warnings.filterwarnings("ignore", category=DeprecationWarning, module="w2t_bkin.pose.models")
   ```

### Issue: Missing `camera_id` Parameter Error

**Symptom:** `align_pose_to_timebase()` fails with missing parameter error.

**Cause:** You're calling the function in NWB-first mode but missing required parameters.

**Solution:** Provide all required NWB-first parameters:

```python
pose_estimation = align_pose_to_timebase(
    harmonized_data=harmonized,
    timebase=timebase,
    alignment_method="nearest",
    camera_id="cam0",          # ✅ Add this
    bodyparts=bodypart_list,   # ✅ Add this
    camera_device=device,      # ✅ Add this
    model_name="dlc_mouse_v1",
    skeleton_name="mouse_12pt"
)
```

### Issue: NWB File Validation Errors

**Symptom:** NWB file fails validation after migration.

**Cause:** Incorrect PoseEstimation structure or missing required fields.

**Solutions:**

1. Verify skeleton nodes match bodypart names exactly
2. Ensure timestamps are aligned correctly
3. Check camera_device is added to NWBFile before PoseEstimation
4. Use `pynwb.validate()` to get detailed error messages

### Issue: Tests Fail After Migration

**Common causes:**

1. Test fixtures still create PoseBundle objects
2. Assertions check for PoseBundle attributes (`.frames`, `.mean_confidence`)
3. Mock objects not updated for NWB-first pattern

**Solutions:**

1. Update fixtures to use `build_pose_estimation()`
2. Update assertions to check PoseEstimation attributes
3. Update mocks to return PoseEstimation objects

---

## Timeline and Support

### Current Phase: Dual-Mode Support (Stable)

- **Status**: Both legacy and NWB-first patterns supported
- **Timeline**: Indefinite (no removal date set)
- **Recommendation**: Migrate new code to NWB-first, update existing code incrementally

### Future Phase: NWB-First Only

- **When**: To be announced (not before 6 months notice)
- **Changes**: PoseBundle/PoseFrame/PoseKeypoint removed, legacy path removed from nwb.py
- **Migration deadline**: Will be communicated well in advance

### Getting Help

- **Documentation**: See `docs/design.md` for architecture details
- **Examples**: Check `examples/pose_camera_nwb.py` for working NWB-first code
- **Issues**: Report problems on GitHub issue tracker
- **Questions**: Ask in team discussions or project Slack

---

## Complete Working Example

See `examples/pose_camera_nwb.py` for a fully functional NWB-first workflow:

```bash
cd /home/borja/w2t-bkin
python examples/pose_camera_nwb.py
```

This example demonstrates:

- ✅ Importing DLC pose data
- ✅ Harmonizing to canonical skeleton
- ✅ Creating Skeleton and Device objects
- ✅ Aligning pose to timebase (NWB-first mode)
- ✅ Creating ImageSeries for camera
- ✅ Assembling complete NWB file with pose_estimations
- ✅ Validating and saving NWB file

---

## Summary

**Key Takeaways:**

1. **NWB-first is the future** - start using it for new code
2. **Legacy still works** - no urgency to migrate existing code
3. **Dual-mode is stable** - both patterns fully supported
4. **Migration is straightforward** - mostly parameter changes
5. **Examples are available** - see `examples/pose_camera_nwb.py`

**Next Steps:**

1. Review the NWB-first example script
2. Identify code using PoseBundle in your project
3. Plan incremental migration (new code first, then existing)
4. Test thoroughly after each migration step
5. Report any issues or questions

---

_Last updated: 2025-11-21_  
_Migration guide version: 1.0_
