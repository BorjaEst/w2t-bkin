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
- ✅ **Breaking changes**: Events module deprecated in favor of behavior module
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
- Architecture: Low-level (events.bpod) → Mid-level (behavior.core) → High-level (pipeline)

**Decision**: Implemented community-standard behavior module following Phase 1 pattern. Breaking change strategy (Option A) adopted - events module deprecated. BEADL task programs left optional. Actions extracted from reward/stimulus state transitions.

**Blockers**: None  
**Next Phase**: Phase 3 (Facemap Module) can begin

### Phase 3: Facemap Module 🔲

**Target**: Remove FacemapBundle; use pynwb BehavioralTimeSeries

- [ ] Update facemap/models.py: Remove FacemapBundle
- [ ] Update facemap processing: Create BehavioralTimeSeries per metric
- [ ] Update sync/facemap.py: Work with TimeSeries
- [ ] Update nwb.py: Receive TimeSeries directly
- [ ] Update tests: Use TimeSeries fixtures

**Blockers**: Phase 1 completion provides pattern to follow  
**Dependencies**: None (can proceed in parallel with pose/events)

### Phase 4: NWB Assembly Simplification 🔲

**Target**: Simplify nwb.py to aggregation-only (no conversion)

- [ ] Remove all conversion functions
- [ ] Update \_build_nwb_file(): Accept NWB objects only
- [ ] Simplify function signatures
- [ ] Update orchestration: Pass NWB objects
- [ ] Update integration tests: Verify NWB-native flow

**Blockers**: Phases 1, 2, 3 must complete  
**Dependencies**: All processing modules migrated

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
