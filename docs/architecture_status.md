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

### Phase 1: Pose Module 🟡 (In Progress - Complete Migration)

**Target**: Complete removal of PoseBundle/PoseFrame/PoseKeypoint; NWB-first only

**Status**: 🟡 In Progress - Executing complete migration (removing all legacy code)

- [x] Add ndx-pose integration to nwb.py
- [x] Add DLCModelInfo.skeleton field
- [x] Parse skeleton edges from DLC config
- [x] Integration test passes
- [x] **COMPLETED**: Add build_pose_estimation() to pose/core.py (Step 0)
- [x] **COMPLETED**: Update align_pose_to_timebase() to support NWB-first mode (Step 1.5)
- [x] **COMPLETED**: Add comprehensive tests for new functions (27 tests pass)
- [x] **COMPLETED**: Add deprecation warnings to PoseBundle/PoseFrame/PoseKeypoint
- [x] **COMPLETED**: Create MIGRATION.md guide with examples and troubleshooting
- [x] **COMPLETED**: End-to-end NWB-first example verified (pose_camera_nwb.py)
- [ ] **IN PROGRESS**: Update import_dlc_pose() to return PoseEstimationSeries directly
- [ ] **IN PROGRESS**: Update import_sleap_pose() to return PoseEstimationSeries directly
- [ ] **IN PROGRESS**: Update harmonization to work on PoseEstimationSeries
- [ ] **IN PROGRESS**: Remove PoseBundle from pose/models.py completely
- [ ] **IN PROGRESS**: Delete \_pose_bundle_to_ndx_pose() from nwb.py
- [ ] **IN PROGRESS**: Migrate pipeline.py to NWB-first
- [ ] **IN PROGRESS**: Update integration tests to NWB-first
- [ ] **IN PROGRESS**: Remove domain exports of legacy models

**Current Progress (2025-11-21)**:

Phase 1 is transitioning from **dual-mode to NWB-first only**:

**Completed Foundation:**

- ✅ NWB-first workflow: `build_pose_estimation()` → `assemble_nwb(pose_estimations=[...])`
- ✅ Working example in examples/pose_camera_nwb.py
- ✅ 27 unit tests cover NWB-first path (25 pass, 2 skipped for SLEAP)
- ✅ Comprehensive documentation in MIGRATION.md

**In Progress (Complete Migration):**

- 🟡 Removing all legacy models (PoseBundle, PoseFrame, PoseKeypoint)
- 🟡 Updating import functions to return PoseEstimationSeries
- 🟡 Updating harmonization to work on PoseEstimationSeries
- 🟡 Removing conversion function from nwb.py
- 🟡 Migrating pipeline.py to NWB-first
- 🟡 Updating all integration tests
- 🟡 Removing domain exports of legacy models

**Decision**: Changed from incremental dual-mode strategy to complete migration. All legacy code will be removed in this phase.

**Blockers**: None  
**Next Phase**: Phase 2 (Events Module) will begin after Phase 1 complete removal

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
