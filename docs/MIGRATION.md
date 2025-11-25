# Migration Guide: NWB-First Architecture

## Overview

The w2t-bkin pipeline has completed migration to an **NWB-first architecture** where NWBFile serves as the primary orchestration artifact throughout the entire pipeline.

## Migration Phases

### Phase 1: Pose Module ✅ (Completed 2025-11-21)

Eliminated PoseBundle/PoseFrame/PoseKeypoint intermediate models; use ndx-pose PoseEstimation throughout.

### Phase 2: Behavior Module ✅ (Completed 2025-11-24)

Implemented ndx-structured-behavior integration for NWB-first behavior data (TaskRecording, TrialsTable).

### Phase 3: NWB-First Refactoring ✅ (Completed 2025-11-25)

Replaced Manifest-centric architecture with NWB-first; eliminated ingest/nwb modules.

## Phase 3 Breaking Changes (2025-11-25)

### Removed Modules

The following modules have been **permanently removed**:

- `w2t_bkin.ingest` (775 lines) - File discovery, manifest building, verification
- `w2t_bkin.nwb` (636 lines) - NWB assembly from manifest
- `w2t_bkin.domain.manifest` (223 lines) - Manifest domain models

### Removed Types

- `Manifest`, `ManifestCamera`, `ManifestTTL`
- `VerificationResult`, `VerificationSummary`, `CameraVerificationResult`

### Removed Functions

- `ingest.build_and_count_manifest()` → Functionality inlined in `pipeline.run_session()`
- `ingest.verify_manifest()` → Verification inlined in `pipeline.run_session()`
- `ingest.discover_files()` → Moved to `utils.discover_files()` (already existed)
- `nwb.assemble_nwb()` → Replaced by `session.write_nwb_file()`
- `nwb.create_device()` → Use `session.create_device()` (already existed)
- `nwb.create_image_series()` → Use `session.add_video_acquisition()`

### New Functions (Added)

**In `utils.py`:**

- `count_video_frames(video_path: Path) -> int` - Video frame counting (moved from ingest)
- `count_ttl_pulses(ttl_path: Path) -> int` - TTL pulse counting (moved from ingest)

**In `session.py`:**

- `add_video_acquisition(nwbfile, camera_id, video_files, ...) -> NWBFile` - Add ImageSeries to NWBFile
- `write_nwb_file(nwbfile: NWBFile, output_path: Path) -> Path` - Write NWBFile to disk

### Updated API: pipeline.run_session()

**Before (Manifest-centric):**

```python
from w2t_bkin.pipeline import run_session

result = run_session(config_path, session_id)
manifest = result['manifest']  # Manifest object
nwb_path = result['nwb_path']
```

**After (NWB-first):**

```python
from w2t_bkin.pipeline import run_session

result = run_session(config_path, session_id)
nwbfile = result['nwbfile']  # In-memory NWBFile
nwb_path = result['nwb_path']
```

### Architecture Change

**Before (Manifest-centric):**

```text
Config + Session → discover_files() → Manifest
Manifest → populate_counts() → Manifest (with counts)
Manifest → verify_manifest() → VerificationResult
Manifest + processing → assemble_nwb() → NWBFile → write()
```

**After (NWB-first):**

```text
Session → create_nwb_file() → NWBFile (early, in memory)
Config + Session → inline discovery → file_dict + verify inline
NWBFile + files → add_video_acquisition() → NWBFile (with ImageSeries)
NWBFile + processing → add behavior/pose → NWBFile (complete)
NWBFile → write_nwb_file() → disk
```

### Migration Steps for Phase 3

If your code used the old ingest/nwb modules:

1. **Replace manifest-based workflows:**

   ```python
   # OLD - No longer works
   from w2t_bkin.ingest import build_and_count_manifest, verify_manifest
   from w2t_bkin.nwb import assemble_nwb

   manifest = build_and_count_manifest(config, session)
   verify_manifest(manifest, tolerance=10)
   nwb_path = assemble_nwb(manifest, config, provenance, output_dir)

   # NEW - Use pipeline.run_session()
   from w2t_bkin.pipeline import run_session

   result = run_session(config_path, session_id)
   nwbfile = result['nwbfile']
   nwb_path = result['nwb_path']
   ```

2. **Update utility imports:**

   ```python
   # OLD - No longer works
   from w2t_bkin.ingest import count_video_frames, count_ttl_pulses

   # NEW
   from w2t_bkin.utils import count_video_frames, count_ttl_pulses
   ```

3. **Update session operations:**

   ```python
   # OLD - No longer works
   from w2t_bkin.nwb import create_image_series

   # NEW
   from w2t_bkin.session import add_video_acquisition

   add_video_acquisition(nwbfile, camera_id="cam0", video_files=[...])
   ```

---

## Phase 1 Breaking Changes (2025-11-21)

### Pose Module: Removed Types

The following types have been **permanently removed** from the codebase:

- `PoseBundle` (was in `w2t_bkin.domain` and `w2t_bkin.pose.models`)
- `PoseFrame` (was in `w2t_bkin.pose.models`)
- `PoseKeypoint` (was in `w2t_bkin.pose.models`)

Any code importing these types will fail with `ImportError`.

### Updated Function Signatures

#### `align_pose_to_timebase()` - Now Requires camera_id and bodyparts

**Before (REMOVED):**

```python
# This no longer works
result = align_pose_to_timebase(data, reference_times, mapping="nearest")
# Returns: List[PoseFrame]
```

**After (REQUIRED):**

```python
# camera_id and bodyparts are now REQUIRED parameters
result = align_pose_to_timebase(
    data=data,
    reference_times=reference_times,
    camera_id="cam0",           # REQUIRED
    bodyparts=["nose", "ear"],  # REQUIRED
    mapping="nearest",
    source="dlc",
)
# Returns: PoseEstimation (ndx-pose native)
```

#### `assemble_nwb()` - Removed pose_bundles Parameter

**Before (REMOVED):**

```python
# This no longer works
nwb_path = assemble_nwb(
    manifest=manifest,
    config=config,
    provenance=provenance,
    pose_bundles=[bundle],  # REMOVED
    output_dir=output_dir,
)
```

**After (REQUIRED):**

````python
# Use pose_estimations instead
nwb_path = assemble_nwb(
    manifest=manifest,
    config=config,
    provenance=provenance,
    pose_estimations=[pose_est],  # PoseEstimation objects
    output_dir=output_dir,
)

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

For code previously using PoseBundle:

- [x] Replace `PoseBundle` creation with `build_pose_estimation()` calls
- [x] Update `align_pose_to_timebase()` calls to include required `camera_id` and `bodyparts`
- [x] Pass `PoseEstimation` objects to `assemble_nwb(pose_estimations=[...])`
- [x] Remove imports of `PoseBundle`, `PoseFrame`, `PoseKeypoint` (they no longer exist)
- [x] Update all tests to use NWB-first patterns

**Migration is COMPLETE. All legacy code has been removed.**

---

## Why Migrate?

### Benefits of NWB-First

1. **Standards-compliant**: Uses ndx-pose (community standard for pose data in NWB)
2. **Reduced complexity**: Eliminates intermediate models and conversion steps (~300 lines removed)
3. **Better performance**: Direct NWB object creation is more efficient
4. **Future-proof**: Aligns with NWB ecosystem and best practices
5. **Cleaner architecture**: Each module produces NWB objects it owns

### Legacy Pattern Problems (NOW RESOLVED)

- ❌ Intermediate models (PoseBundle) duplicated NWB functionality → **REMOVED**
- ❌ Conversion overhead: Dict → PoseBundle → NWB → **ELIMINATED**
- ❌ Harder to maintain: Two representations of same data → **UNIFIED**
- ❌ Not standards-aligned: Custom models vs community standards → **FIXED**

---

## Migration Examples

### Example 1: Basic Pose Import and Alignment

#### OLD Pattern (NO LONGER WORKS)

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
````

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
   warnings.filterwarnings("ignore", category=DeprecationWarning)
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

## Phase 2: Behavior Module Migration (NEW)

### Behavior Module Overview

The w2t-bkin pipeline has implemented a **behavior module** using the community-standard `ndx-structured-behavior` extension for NWB. This replaces the legacy events extraction workflow with a more structured, standards-compliant approach.

### Status: New Implementation ✅

**Current State**: Behavior module fully implemented and tested.

- ✅ **New module**: `w2t_bkin.behavior` - complete implementation
- ⚠️ **Module renamed**: `w2t_bkin.events` → `w2t_bkin.bpod` (parsing only), extraction moved to `w2t_bkin.behavior`
- 🔴 **Breaking changes**: See below for migration path

### What Changed

#### Removed Functions (from old events module)

The following functions from `w2t_bkin.events` have been **removed** (use `w2t_bkin.behavior` instead):

- `extract_trials()` - Use behavior module workflow instead
- `extract_behavioral_events()` - Use behavior module workflow instead
- `create_event_summary()` - Compute statistics from NWB tables directly

#### New Behavior Module Workflow

**File**: `w2t_bkin.behavior`

Core transformation functions (all produce ndx-structured-behavior NWB objects):

1. **Type extraction** (metadata):

   - `extract_state_types()` → `StateTypesTable`
   - `extract_event_types()` → `EventTypesTable`
   - `extract_action_types()` → `ActionTypesTable`

2. **Data extraction** (temporal sequences):

   - `extract_states()` → `StatesTable`
   - `extract_events()` → `EventsTable`
   - `extract_actions()` → `ActionsTable`

3. **Assembly**:
   - `build_trials_table()` → `TrialsTable`
   - `build_task_recording()` → `TaskRecording`

### Migration Example

#### OLD Pattern (DEPRECATED)

```python
from w2t_bkin.events import extract_trials, extract_behavioral_events  # REMOVED
from w2t_bkin.events.summary import create_event_summary  # REMOVED
from w2t_bkin.events.bpod import parse_bpod  # NOW: w2t_bkin.bpod.code

# Parse Bpod data
bpod_data = parse_bpod(session_dir, pattern, order)

# Extract trials and events
trials = extract_trials(bpod_data, trial_offsets=offsets)
events = extract_behavioral_events(bpod_data)

# Create summary
summary = create_event_summary(
    session_id="Session-001",
    trials=trials,
    events=events,
)
```

#### NEW Pattern (RECOMMENDED)

```python
from w2t_bkin.bpod.code import parse_bpod
from w2t_bkin.behavior import (
    extract_state_types, extract_states,
    extract_event_types, extract_events,
    extract_action_types, extract_actions,
    build_trials_table, build_task_recording,
)

# Parse Bpod data (same as before)
bpod_data = parse_bpod(session_dir, pattern, order)

# Step 1: Extract type tables (metadata)
state_types = extract_state_types(bpod_data)
event_types = extract_event_types(bpod_data)
action_types = extract_action_types(bpod_data)

# Step 2: Extract data tables (with alignment)
states = extract_states(bpod_data, state_types, trial_offsets=offsets)
events = extract_events(bpod_data, event_types, trial_offsets=offsets)
actions = extract_actions(bpod_data, action_types, trial_offsets=offsets)

# Step 3: Build trials and recording
trials_table = build_trials_table(bpod_data, states, events, actions,
                                   trial_offsets=offsets)
task_recording = build_task_recording(states, events, actions)

# Step 4: Add to NWB
nwbfile.add_acquisition(task_recording)
nwbfile.trials = trials_table
```

### Benefits of New Behavior Module

1. **Standards-compliant**: Uses ndx-structured-behavior (community standard)
2. **NWB-native**: All outputs are NWB objects ready for integration
3. **Structured data**: Clear separation of states, events, actions, and trials
4. **Better interoperability**: Compatible with NWB ecosystem tools
5. **Follows established pattern**: Same NWB-first approach as pose module

### Updated Examples

The `examples/bpod_camera_sync.py` example has been updated to demonstrate the new behavior module workflow. Run it to see the complete pattern:

```bash
python examples/bpod_camera_sync.py
```

### Quick Migration Checklist

For code using the legacy events extraction:

- [ ] Replace `extract_trials()` with behavior module workflow (see pattern above)
- [ ] Replace `extract_behavioral_events()` with `extract_states/events/actions()`
- [ ] Replace `create_event_summary()` with direct computation from NWB tables
- [ ] Update imports: `w2t_bkin.events` → `w2t_bkin.behavior` (extraction) or `w2t_bkin.bpod` (parsing)
- [ ] Update pipeline/orchestration to use new workflow
- [ ] Test with your data to ensure compatibility

### Timeline

- **Current Phase**: Both patterns work (legacy events still available)
- **Recommendation**: Migrate new code to behavior module immediately
- **Future**: Legacy events extraction may be removed in future version (TBD)

---

_Last updated: 2025-11-24_  
_Migration guide version: 1.1_
