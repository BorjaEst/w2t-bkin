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

### Phase 1: Pose Module ✅ (Stable - Dual Mode)

**Target**: Support both legacy PoseBundle and NWB-first workflows during transition

**Status**: ✅ Stable (dual-mode support complete, both patterns fully functional)

- [x] Add ndx-pose integration to nwb.py
- [x] Create \_pose_bundle_to_ndx_pose() conversion function (legacy path)
- [x] Add DLCModelInfo.skeleton field
- [x] Parse skeleton edges from DLC config
- [x] Integration test passes
- [x] **COMPLETED**: Add build_pose_estimation() to pose/core.py (Step 0)
- [x] **COMPLETED**: Update align_pose_to_timebase() to support NWB-first mode (Step 1.5)
- [x] **COMPLETED**: Add comprehensive tests for new functions (27 tests pass)
- [x] **COMPLETED**: Add deprecation warnings to PoseBundle/PoseFrame/PoseKeypoint
- [x] **COMPLETED**: Create MIGRATION.md guide with examples and troubleshooting
- [x] **COMPLETED**: Update architecture_status.md to reflect stable dual-mode state
- [x] **COMPLETED**: End-to-end NWB-first example verified (pose_camera_nwb.py)
- [ ] **DEFERRED**: Update import_dlc_pose() to build PoseEstimationSeries directly
- [ ] **DEFERRED**: Update import_sleap_pose() to build PoseEstimationSeries directly
- [ ] **DEFERRED**: Update harmonization to work on PoseEstimationSeries
- [ ] **DEFERRED**: Remove PoseBundle from pose/models.py (after full migration)
- [ ] **DEFERRED**: Delete \_pose_bundle_to_ndx_pose() from nwb.py (after all consumers updated)

**Completion Summary (2025-11-21)**:

Phase 1 is now **stable** with full dual-mode support:

- ✅ NWB-first workflow: `build_pose_estimation()` → `assemble_nwb(pose_estimations=[...])`
- ✅ Legacy workflow: `PoseBundle` → `assemble_nwb(pose_bundles=[...])`
- ✅ Deprecation warnings guide users toward NWB-first
- ✅ Comprehensive documentation in MIGRATION.md
- ✅ Working example in examples/pose_camera_nwb.py
- ✅ 27 unit tests cover both paths (25 pass, 2 skipped for SLEAP)

**Implementation Details**:

- `build_pose_estimation()`: 170 lines, creates ndx_pose.PoseEstimation from harmonized data
- `align_pose_to_timebase()`: Dual-mode support via optional `camera_id` parameter
- `assemble_nwb()`: Accepts both `pose_estimations` (NWB-first) and `pose_bundles` (legacy)
- Deprecation: All PoseBundle/PoseFrame/PoseKeypoint classes emit DeprecationWarning on instantiation

**Migration Path**:

Users can migrate incrementally:

1. New code: Use NWB-first from start (see MIGRATION.md examples)
2. Existing code: Continue using legacy path (will work indefinitely)
3. Gradual migration: Update code section-by-section as needed

**Blockers**: None (phase complete)  
**Next Phase**: Phase 2 (Events Module) can proceed using pose module as reference pattern

### Phase 2: Events Module 🔲

**Target**: Remove TrialSummary; use pynwb TimeIntervals directly

- [ ] Update events/models.py: Remove TrialSummary
- [ ] Update Bpod parsing: Create TimeIntervals directly
- [ ] Update trial parsing: Build TimeIntervals
- [ ] Update sync/behavior.py: Work with TimeIntervals
- [ ] Update nwb.py: Receive TimeIntervals directly
- [ ] Update tests: Use TimeIntervals fixtures

**Blockers**: Phase 1 completion provides pattern to follow  
**Dependencies**: None (can proceed in parallel with pose)

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
