# Prefect-Friendly Refactoring Overview

## Executive Summary

Reorganize `w2t_bkin` source code structure to follow Prefect best practices, enabling better observability, granular retry logic, and clearer separation of concerns.

**Status**: Planning Phase  
**Start Date**: December 5, 2025  
**Target Completion**: TBD  
**Impact**: Medium (import changes, no breaking API changes with compatibility layer)

## Motivation

### Current Issues

1. **Naming Confusion**: `tasks/` directory contains `PipelineTask` classes (preprocessing), not Prefect `@task` decorators
2. **Limited Granularity**: Only session-level Prefect task, no phase-level observability
3. **Mixed Concerns**: `orchestration/flows.py` mixes multiprocessing and Prefect code
4. **No Declarative Deployments**: Deployments created programmatically instead of version-controlled configs

### Goals

1. ✅ **Clear naming** - No confusion between preprocessing tasks and Prefect tasks
2. ✅ **Phase-level observability** - Expose 7 pipeline phases as individual Prefect tasks
3. ✅ **Organized Prefect code** - Separate flows, tasks, subflows, deployments
4. ✅ **User choice** - Monolithic (fast) vs phase-level (observable) execution modes
5. ✅ **Backward compatible** - Existing imports continue to work

## Scope

### In Scope

- Rename `tasks/` → `preprocessing/`
- Rename `orchestration/` → `prefect/`
- Split `prefect/flows.py` into organized modules
- Create phase-level Prefect task wrappers
- Add declarative deployment definitions
- Update all imports and documentation
- Maintain backward compatibility layer

### Out of Scope

- Changes to core pipeline logic (`core/pipeline/phases/`)
- Changes to business logic (processors, ingest, sync, etc.)
- Performance optimizations
- New features beyond restructuring

## Key Architectural Insight

**The phase functions already exist!** 🎉

```python
# core/pipeline/phases/ already has 7 well-separated functions:
run_phase_0()  # initialization
run_phase_1()  # discovery
run_phase_2()  # preprocessing
run_phase_3()  # ingestion
run_phase_4()  # synchronization
run_phase_5()  # assembly
run_phase_6()  # finalization
```

We just need to **wrap them with `@task` decorators** - minimal changes required!

## Phases

### Phase 1: Rename Directories ✅ Low Risk
- Rename `tasks/` → `preprocessing/`
- Rename `orchestration/` → `prefect/`
- Update all imports
- **Impact**: Import changes only, zero logic changes
- **Estimated effort**: 2-4 hours

### Phase 2: Split `prefect/flows.py` ⚠️ Medium Risk
- Extract phase task wrappers → `prefect/tasks.py`
- Refactor flows → `prefect/flows.py`
- Move deployment code → `prefect/deployments.py`
- Add infrastructure configs → `prefect/infrastructure.py`
- **Impact**: New module structure, backward compatibility maintained
- **Estimated effort**: 4-6 hours

### Phase 3: Add Phase-Level Tasks ✅ High Value
- Create `@task` wrappers for each phase function
- Add `process_session_with_phases` flow
- Update `batch_process_sessions` to support both modes
- **Impact**: New feature, optional usage
- **Estimated effort**: 3-5 hours

### Phase 4: Update Deployments 🔧 Medium Value
- Update `docker/deploy_flows.py` to use new structure
- Add declarative deployment definitions
- Test container deployments
- **Impact**: Deployment workflow changes
- **Estimated effort**: 2-3 hours

### Phase 5: Documentation & Testing 📝 Critical
- Update all documentation
- Update examples
- Add migration guide
- Run full test suite
- **Impact**: User-facing documentation
- **Estimated effort**: 4-6 hours

## Success Criteria

- [ ] All tests pass
- [ ] No breaking changes to public API
- [ ] Backward compatibility verified
- [ ] Container deployments work
- [ ] Documentation updated
- [ ] Migration guide available
- [ ] Both monolithic and phase-level flows functional
- [ ] Prefect UI shows phase-level tasks correctly

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Import errors after rename | Medium | High | Comprehensive search/replace, test suite |
| Breaking existing code | Low | High | Maintain compatibility layer, deprecation warnings |
| Docker build issues | Low | Medium | Test containers after each phase |
| Deployment failures | Medium | Medium | Keep old deployment method working |
| Documentation drift | High | Low | Update docs incrementally with code changes |

## Rollback Plan

- All changes in feature branch
- Can revert individual commits
- Compatibility layer allows gradual migration
- Old import paths continue to work

## Timeline (Estimated)

- **Week 1**: Phase 1 (Rename) + Phase 2 (Split)
- **Week 2**: Phase 3 (Phase tasks) + Phase 4 (Deployments)
- **Week 3**: Phase 5 (Documentation + Testing)
- **Buffer**: 1 week for issues/refinement

**Total estimated time**: 15-24 hours of focused work over 3-4 weeks

## Related Documents

- [Design Document](./DESIGN.md) - Detailed technical design
- [Tasks Checklist](./TASKS.md) - Implementation tasks
- [Requirements](./REQUIREMENTS.md) - Functional requirements
- [Migration Guide](./MIGRATION.md) - For users updating their code
- [Testing Plan](./TESTING.md) - Verification strategy

## Questions for Approval

1. ✅ Proceed with all 5 phases or start with Phase 1-2 only?
2. ✅ Acceptable to have 3-4 week timeline?
3. ✅ OK with backward compatibility layer initially, remove in v2.0?
4. ✅ Deploy both monolithic and phase-level options, or phase-level only?
5. ✅ Update container images immediately or in separate release?
