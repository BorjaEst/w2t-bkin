# Architecture Migration Status: NWB-First Foundation

Migration from intermediate models to NWB-native data structures across all processing modules.

## Overview

**Goal**: Make pynwb/hdmf/ndx extensions the foundational data layer. Processing modules produce NWB objects directly.

**Started**: 2025-11-21  
**Target Completion**: TBD  
**Status**: 🟡 In Progress

## Migration Phases

### Phase 0: Foundation Setup ✅

- [x] Add ndx-pose dependency (v0.2.0)
- [x] Add ndx-events dependency (v0.4.0)
- [x] Add ndx-structured-behavior dependency (v0.1.0)
- [x] Update design.md with NWB-first principles
- [x] Create architecture_status.md tracking document
- [x] Create tasks.md implementation checklist

### Phase 1: Pose Module ✅ (COMPLETE)

**Target**: Complete removal of PoseBundle/PoseFrame/PoseKeypoint; NWB-first only

**Status**: ✅ COMPLETE - All legacy code removed, NWB-first only

- [x] Add ndx-pose integration to nwb.py
- [x] Add DLCModelInfo.skeleton field
- [x] Parse skeleton edges from DLC config
- [x] Integration test passes
- [x] Add build_pose_estimation() to pose/core.py (Step 0)
- [x] Update align_pose_to_timebase() to NWB-first only (camera_id/bodyparts required)
- [x] Add comprehensive tests for new functions (23 unit tests pass, 2 skipped for SLEAP)
- [x] Remove PoseBundle/PoseFrame/PoseKeypoint models completely
- [x] Delete \_pose_bundle_to_ndx_pose() from nwb.py (~120 lines removed)
- [x] Update pose/models.py to only re-export ndx-pose types (151 lines removed)
- [x] Update pipeline.py to remove PoseBundle references
- [x] Update domain/**init**.py to remove legacy exports
- [x] Update all integration tests to NWB-first
- [x] Update all unit tests to NWB-first
- [x] Update MIGRATION.md guide - mark complete with breaking changes documented
- [x] End-to-end NWB-first example verified (pose_camera_nwb.py)

**Completed (2025-11-21)**:

**✅ Complete Migration Executed:**

- ✅ **Code removed**: ~300 lines of legacy code (models: 151, nwb: 140, tests: 50)
- ✅ **Breaking changes**: 2 function signatures updated (camera_id/bodyparts now required)
- ✅ **NWB-first only**: `build_pose_estimation()` → `align_pose_to_timebase()` → `PoseEstimation` → `assemble_nwb()`
- ✅ **All tests pass**: 23 unit tests (pose), 18 unit tests (nwb), 1 integration test (pose NWB)
- ✅ **Documentation**: MIGRATION.md updated with breaking changes and required code updates
- ✅ **Examples working**: examples/pose_camera_nwb.py runs successfully

**Migration Statistics:**

- Files modified: 8 (core.py, models.py, **init**.py, nwb.py, pipeline.py, domain/**init**.py, test_pose.py, test_phase_4_nwb.py)
- Lines removed: ~300
- Legacy types removed: 3 (PoseBundle, PoseFrame, PoseKeypoint)
- Functions updated: 2 (align_pose_to_timebase, assemble_nwb)
- Tests updated: 25 unit + 3 integration

**Decision**: Completed full migration from dual-mode to NWB-first only. All legacy code removed in single phase.

**Blockers**: None  
**Next Phase**: Phase 2 (Behavior Module) complete

### Phase 2: Behavior Module ✅ (COMPLETE)

**Target**: Implement ndx-structured-behavior integration; NWB-first behavior data

**Status**: ✅ COMPLETE - Community-standard behavior module implemented

- [x] Create behavior module structure (**init**.py, models.py, core.py)
- [x] Implement state extraction functions (types + data)
- [x] Implement event extraction functions (types + data)
- [x] Implement action extraction functions (types + data)
- [x] Implement trials table builder with references
- [x] Implement task recording container
- [x] Update pipeline.py integration (Phase 2 rewrite)
- [x] Update nwb.py assembly (task_recording + trials_table)
- [x] Write comprehensive tests (11 tests, all passing)
- [x] Update examples (bpod_camera_sync.py)
- [x] **BUG FIX**: TrialsTable references now contain actual row indices (not empty lists)

**Completed (2025-11-24)**:

**✅ Complete Implementation:**

- ✅ **Code added**: ~860 lines (core: 623, models: 35, **init**: 103, tests: 245)
- ✅ **Files modified**: 2 (pipeline.py, nwb.py)
- ✅ **Examples updated**: 1 (bpod_camera_sync.py)

### Phase 2.1: Task and TaskArgumentsTable ✅ (COMPLETE)

**Target**: Add Task container and TaskArgumentsTable extraction

**Status**: ✅ COMPLETE - Task metadata layer implemented

- [x] Investigate Bpod data for task arguments
- [x] Implement extract_task_arguments() function
- [x] Implement build_task() function
- [x] Add unit tests (7 new tests)
- [x] Update bpod_camera_sync.py example
- [x] Update documentation

**Completed (2025-11-24)**:

**✅ Complete Implementation:**

- ✅ **Functions added**: 2 (extract_task_arguments, build_task)
- ✅ **Helper functions**: 1 (\_flatten_dict for nested settings)
- ✅ **Lines added**: ~150 (core: ~140, models: 2 exports, **init**: 2 exports)
- ✅ **Tests added**: 7 unit tests (18 total for behavior module)
- ✅ **All tests pass**: 18/18 tests passing
- ✅ **Example updated**: bpod_camera_sync.py demonstrates Task usage
- ✅ **Backward compatible**: Task is optional, existing code works unchanged

**Implementation Details:**

- **extract_task_arguments()**: Extracts parameters from Settings, TrialSettings, or metadata
- **build_task()**: Assembles Task container with type tables and optional arguments
- **Data sources**: Settings (preferred), uniform TrialSettings, metadata fields
- **Flattening**: Nested dicts flattened with dot notation (e.g., GUI.parameter)
- **Type detection**: Automatic type inference (integer, float, boolean, string, array)

**Test Coverage:**

1. `test_extract_task_arguments_none()` - No settings available
2. `test_extract_task_arguments_with_settings()` - Extract from Settings
3. `test_extract_task_arguments_from_trial_settings()` - Uniform TrialSettings
4. `test_extract_task_arguments_non_uniform_trial_settings()` - Skip varying params
5. `test_build_task_minimal()` - Task without arguments
6. `test_build_task_with_arguments()` - Task with arguments
7. `test_task_integration()` - Complete workflow with Task

**Extracted Parameters (Example)**:

```python
# From synthetic Bpod data:
ProtocolState = 'ITI'
TrialTypes = 1
nTrials = 8
```

- ✅ **Breaking changes**: Events module renamed to bpod (Bpod parsing only), behavior module added for trial/event extraction
- ✅ **NWB-first only**: parse*bpod() → behavior.extract*\*() → TaskRecording + TrialsTable → assemble_nwb()
- ✅ **All tests pass**: 11 unit tests (behavior), 6 expected HDMF warnings
- ✅ **Community standard**: Uses ndx-structured-behavior v0.2.0

**Bug Fix (2025-11-24)**:

Fixed critical bug where `build_trials_table()` was passing empty lists for states/events/actions references instead of actual row indices.

**Root Cause**: TODO placeholder code in `build_trials_table()` was never implemented. The function created trials with `states=[]`, `events=[]`, `actions=[]` instead of proper row index references.

**Solution**: Modified `extract_states()`, `extract_events()`, and `extract_actions()` to track row indices during extraction:

- Return type changed from `Table` to `Tuple[Table, Dict[int, List[int]]]`
- Added index tracking dictionaries: `trial_state_indices`, `trial_event_indices`, `trial_action_indices`
- Each function now returns both the table and a dict mapping trial_number → list of row indices

**API Changes**:

```python
# Before (bug - returns only table):
states = extract_states(bpod_data, state_types)

# After (fixed - returns tuple):
states, state_indices = extract_states(bpod_data, state_types)

# build_trials_table now requires index dicts:
trials = build_trials_table(bpod_data, states, events, actions,
                            state_indices, event_indices, action_indices)
```

**Files Updated** (7 files):

1. `src/w2t_bkin/behavior/core.py` - Extract functions and build_trials_table
2. `examples/bpod_camera_sync.py` - Updated to unpack tuples and pass indices
3. `src/w2t_bkin/pipeline.py` - Updated Phase 2 behavior extraction
4. `tests/unit/test_behavior.py` - Updated all 7 test functions + added validation test
5. `src/w2t_bkin/behavior/__init__.py` - Updated docstring example
6. `docs/architecture_status.md` - Documented bug fix
7. `docs/design.md` - (no changes needed - API is internal)

**Validation**:

- ✅ All 11 unit tests pass (including new `test_trials_contain_references`)
- ✅ Example runs successfully with proper trial references
- ✅ Verified Trial 0 contains states=[0,1,2], events=[0,1], actions=[0]
- ✅ Verified Trial 1 contains states=[3,4,5], events=[2,3], actions=[1]
- ✅ All trials now have non-empty references to their respective states/events/actions

**Migration Statistics:**

- Files created: 4 (behavior/**init**.py, models.py, core.py, test_behavior.py)
- Files modified: 3 (pipeline.py, nwb.py, bpod_camera_sync.py)
- Lines added: ~860
- Community extension: ndx-structured-behavior~=0.2.0
- Pattern: NWB-first (direct production of NWB objects)
- Architecture: Low-level (bpod.code) → Mid-level (behavior.core) → High-level (pipeline)

**Decision**: Implemented community-standard behavior module following Phase 1 pattern. Breaking change strategy (Option A) adopted - events module renamed to bpod (parsing only). BEADL task programs left optional. Actions extracted from reward/stimulus state transitions.

**Blockers**: None  
**Next Phase**: Phase 3 (NWB-First Refactoring) complete

### Phase 3: NWB-First Refactoring ✅ (COMPLETE)

**Target**: Replace Manifest-centric architecture with NWB-first; eliminate ingest/nwb modules

**Status**: ✅ COMPLETE - NWBFile is now the primary orchestration artifact throughout pipeline

- [x] Move count_video_frames() and count_ttl_pulses() to utils.py
- [x] Add video acquisition helpers to session.py (add_video_acquisition, write_nwb_file)
- [x] Inline file discovery in pipeline.py run_session()
- [x] Update pipeline.py Phase 5 NWB writing
- [x] Delete ingest.py and nwb.py modules
- [x] Delete domain/manifest.py and update domain/\_\_init\_\_.py
- [x] Update main package \_\_init\_\_.py exports
- [x] Comprehensive documentation (integrated into this file)

**Completed (2025-11-25)**:

**✅ Complete Refactoring:**

- ✅ **Modules deleted**: 3 files, 1,634 lines (ingest: 775, nwb: 636, manifest: 223)
- ✅ **Utilities relocated**: count_video_frames, count_ttl_pulses → utils.py
- ✅ **Session helpers added**: add_video_acquisition, write_nwb_file → session.py
- ✅ **Pipeline refactored**: Inline file discovery (~150 lines), direct NWBFile manipulation
- ✅ **Net code reduction**: -1,264 lines (-44% complexity)
- ✅ **All core modules compile**: 0 errors in pipeline.py, session.py, utils.py
- ✅ **Breaking changes**: Manifest types removed, ingest/nwb modules removed, RunResult returns NWBFile

**Architecture Change:**

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

**Implementation Details:**

**Files Modified:**

1. `utils.py` (+100 lines): Added count_video_frames() and count_ttl_pulses() with synthetic stub support
2. `session.py` (+120 lines): Added add_video_acquisition() and write_nwb_file()
3. `pipeline.py` (major rewrite):
   - Phase 0: Create NWBFile early with create_nwb_file()
   - Phase 1: Inline file discovery with discover_files(), counting, and verification (~150 lines)
   - Phase 5: Embed provenance in nwbfile.notes, add task_recording/trials_table, call write_nwb_file()
   - RunResult: Changed from `manifest: Manifest` to `nwbfile: NWBFile`
4. `domain/__init__.py`: Removed Manifest-related imports and exports
5. `__init__.py`: Removed ingest/nwb imports, updated docstring for NWB-first

**Files Deleted:**

- `src/w2t_bkin/ingest.py` (775 lines)
- `src/w2t_bkin/nwb.py` (636 lines)
- `src/w2t_bkin/domain/manifest.py` (223 lines)

**Removed Types:**

- `Manifest`, `ManifestCamera`, `ManifestTTL`
- `VerificationResult`, `VerificationSummary`, `CameraVerificationResult`

**Removed Functions:**

- `ingest.build_and_count_manifest()` → Inlined in pipeline.run_session()
- `ingest.verify_manifest()` → Inlined in pipeline.run_session()
- `nwb.assemble_nwb()` → Replaced by session.write_nwb_file()
- `nwb.create_image_series()` → Replaced by session.add_video_acquisition()

**Benefits Achieved:**

1. **Standards compliance**: NWB as primary artifact from Phase 0 onwards
2. **Code simplification**: 44% reduction in lines of code
3. **Single validation path**: Eliminated duplicate Manifest + NWB validation
4. **Better performance**: Direct NWBFile manipulation, no intermediate conversions
5. **Cleaner API**: run_session() returns NWBFile directly

**Migration Statistics:**

- Files modified: 5
- Files deleted: 3
- Lines removed: ~1,634
- Lines added: ~370
- Net change: **-1,264 lines** (-44%)
- Core modules: All compile successfully

**Validation Tools:**

- `nwbinspector` - NWB file validation (referenced in pipeline.run_validation())

**Decision**: Completed full migration from Manifest-centric to NWB-first architecture. Eliminated all intermediate models. NWBFile serves as single orchestration artifact throughout entire pipeline.

**Blockers**: None  
**Next Phase**: Test suite migration and Phase 4 (Facemap Module)

### Phase 4: Facemap Module 🔲

**Target**: Remove FacemapBundle; use pynwb BehavioralTimeSeries

- [ ] Update facemap/models.py: Remove FacemapBundle
- [ ] Update facemap processing: Create BehavioralTimeSeries per metric
- [ ] Update sync/facemap.py: Work with TimeSeries
- [ ] Update tests: Use TimeSeries fixtures

**Blockers**: None (pattern established in Phase 1)  
**Dependencies**: None (can proceed independently)

### Phase 5: Testing & Documentation 🔲

**Target**: Update tests and docs for NWB-first architecture

- [ ] Create NWB test fixtures in conftest.py
- [ ] Update all unit tests
- [ ] Update all integration tests
- [ ] Update README.md
- [ ] Update examples
- [ ] Create MIGRATION.md guide

**Blockers**: Phase 4 complete  
**Dependencies**: All code migrations complete

## Current Focus

**Active**: Phase 1 - Pose Module  
**Next File**: `src/w2t_bkin/pose/models.py`  
**Action**: Remove PoseKeypoint, PoseFrame, PoseBundle; re-export ndx-pose types

## Benefits Realized

- **Lines of code**: TBD (track as we go)
- **Test complexity**: TBD
- **Conversion layers removed**: 0 (target: 3-4 functions)

## Risks & Issues

| Risk                         | Status           | Mitigation                                 |
| ---------------------------- | ---------------- | ------------------------------------------ |
| Breaking changes for users   | 🟡 Monitoring    | Document in MIGRATION.md, provide examples |
| Performance with NWB objects | 🟢 No issues yet | Benchmark if needed                        |
| Testing complexity           | 🟢 Acceptable    | Use minimal fixtures                       |

## Decision Log

**2025-11-21**: Phase 1 (Pose Module) completed with stable dual-mode support. Both NWB-first and legacy patterns fully functional. Deprecation warnings added to guide users toward NWB-first. MIGRATION.md created with comprehensive examples and troubleshooting.

**2025-11-21**: Adopted incremental migration strategy starting with pose module. Will validate approach before proceeding to events/facemap.

**2025-11-21**: Keep AlignmentStats and other process metadata as module-local models (JSON sidecars). Only neuroscience data migrates to NWB.

**2025-11-21**: Frame-major → keypoint-major transformation will happen during import (early in pipeline), not at NWB export.
