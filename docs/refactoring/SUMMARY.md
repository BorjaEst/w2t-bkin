# Refactoring Plan - Quick Reference

## 📊 Project Status

**Status**: 📝 Planning Complete  
**Created**: December 5, 2025  
**Next Step**: Review and approve, then begin implementation

## 📚 Documentation Suite

| Document | Purpose | Status |
|----------|---------|--------|
| [README.md](./README.md) | Index & navigation | ✅ Complete |
| [OVERVIEW.md](./OVERVIEW.md) | Executive summary, timeline, phases | ✅ Complete |
| [DESIGN.md](./DESIGN.md) | Technical design, code examples | ✅ Complete |
| [REQUIREMENTS.md](./REQUIREMENTS.md) | EARS notation requirements | ✅ Complete |
| [TASKS.md](./TASKS.md) | 67-task implementation checklist | ✅ Complete |
| [MIGRATION.md](./MIGRATION.md) | User migration guide | ✅ Complete |
| [TESTING.md](./TESTING.md) | 50+ test specifications | ✅ Complete |
| [DECISIONS.md](./DECISIONS.md) | 10 major decision records | ✅ Complete |

**Total**: 8 comprehensive documents, ~15,000 words

---

## 🎯 Goals

1. ✅ **Clear naming** - No confusion between preprocessing tasks and Prefect tasks
2. ✅ **Phase-level observability** - 7 pipeline phases as individual Prefect tasks
3. ✅ **Organized Prefect code** - Separate flows, tasks, deployments
4. ✅ **User choice** - Monolithic (fast) vs phase-level (observable) modes
5. ✅ **Backward compatible** - Existing imports continue to work

---

## 🗂️ Changes Summary

### Directory Renames

```
src/w2t_bkin/
├── tasks/          → preprocessing/     ✨ Avoid confusion with @task
└── orchestration/  → prefect/           ✨ Clear Prefect separation
```

### API Renames

```python
# Old → New
batch_process_sessions_prefect  →  batch_process_sessions
process_single_session          →  process_session_monolithic
```

### New Features

- **Phase-level execution**: 7 phases exposed as individual Prefect tasks
- **Dual execution modes**: Choose fast (monolithic) or observable (phases)
- **Declarative deployments**: Version-controlled deployment configs
- **Per-phase observability**: Duration, logs, retry logic visible in Prefect UI

---

## 📅 Timeline

### Implementation Phases

| Phase | Description | Tasks | Time | Risk |
|-------|-------------|-------|------|------|
| 1 | Rename directories | 14 | 2-4h | Low |
| 2 | Split modules | 13 | 4-6h | Medium |
| 3 | Add phase tasks | 11 | 3-5h | Low |
| 4 | Update deployments | 10 | 2-3h | Medium |
| 5 | Documentation & testing | 14 | 4-6h | Low |
| **Total** | | **67** | **17-27h** | |

**Calendar**: 3-4 weeks with buffer

---

## ✅ Success Criteria

- [ ] All 67 tasks completed
- [ ] All tests pass (100%)
- [ ] Coverage >80%
- [ ] Backward compatibility verified
- [ ] Both execution modes functional
- [ ] Container deployments working
- [ ] Performance within limits (<5% overhead monolithic, <10% phase)
- [ ] Documentation complete
- [ ] Migration guide available

---

## 🎨 Before & After

### Before: Current Structure

```python
from w2t_bkin.tasks import DLCPoseTask                    # ❌ Confusing
from w2t_bkin.orchestration.flows import batch_process_sessions_prefect

# Only session-level observability (black box)
result = batch_process_sessions_prefect(
    config_path="config.toml",
    subject_filter="subject-001",
)
```

### After: Refactored Structure

```python
from w2t_bkin.preprocessing import DLCPoseTask            # ✅ Clear
from w2t_bkin.prefect import batch_process_sessions, process_session_with_phases

# Option 1: Fast (monolithic)
result = batch_process_sessions(
    config_path="config.toml",
    subject_filter="subject-001",
    use_phases=False,  # Entire session as one task
)

# Option 2: Observable (phase-level)
result = batch_process_sessions(
    config_path="config.toml",
    subject_filter="subject-001",
    use_phases=True,   # 7 tasks per session, full visibility
)
```

---

## 🔍 Phase-Level Benefits

### Prefect UI View

**Monolithic Mode**:
```
Session-001 ──► [Process Session] (12m 34s)
Session-002 ──► [Process Session] (11m 58s)
```

**Phase Mode**:
```
Session-001:
  ├─► [Phase 0: Initialization]    (12s)
  ├─► [Phase 1: Discovery]         (8s)
  ├─► [Phase 2: Preprocessing]     (9m 15s) ❌ FAILED
  ├─► [Phase 3: Ingestion]         (skipped)
  ├─► [Phase 4: Synchronization]   (skipped)
  ├─► [Phase 5: Assembly]          (skipped)
  └─► [Phase 6: Finalization]      (skipped)
```

🎯 **Immediately see**: Phase 2 (Preprocessing) failed after 9m 15s

---

## 📊 Trade-offs

| Aspect | Monolithic | Phase-Level |
|--------|------------|-------------|
| **Speed** | ✅ Faster | ⚠️ +5-10% overhead |
| **Observability** | ❌ Limited | ✅ Excellent |
| **Debugging** | ❌ Difficult | ✅ Easy |
| **Retry Logic** | ⚠️ Session-level | ✅ Per-phase |
| **Best For** | Production | Development/Debug |

---

## 🚀 Quick Start (After Implementation)

### For Users: Updating Your Code

```bash
# 1. Update imports
sed -i 's/from w2t_bkin.tasks/from w2t_bkin.preprocessing/g' *.py
sed -i 's/from w2t_bkin.orchestration/from w2t_bkin.prefect/g' *.py

# 2. Update flow names
sed -i 's/batch_process_sessions_prefect/batch_process_sessions/g' *.py

# 3. Run tests
pytest tests/ -v
```

### For Developers: Implementation

```bash
# 1. Create feature branch
git checkout dev
git checkout -b feature/prefect-refactoring

# 2. Follow TASKS.md checklist
# Start with Phase 1, Task 1.1

# 3. Run tests after each phase
pytest tests/ -v --cov=src/w2t_bkin

# 4. Update documentation incrementally
```

---

## 📞 Getting Started

### Read These First (In Order)

1. **[OVERVIEW.md](./OVERVIEW.md)** - Understand the big picture (5-10 min read)
2. **[DESIGN.md](./DESIGN.md)** - See technical details (15-20 min read)
3. **[TASKS.md](./TASKS.md)** - Review implementation plan (10-15 min read)

### Before Implementation

- [ ] Review all documentation
- [ ] Discuss with team
- [ ] Approve approach
- [ ] Schedule implementation time
- [ ] Assign tasks (if team effort)

### During Implementation

- [ ] Follow [TASKS.md](./TASKS.md) sequentially
- [ ] Update task checkboxes as you go
- [ ] Run tests after each phase
- [ ] Commit frequently with clear messages
- [ ] Update [DECISIONS.md](./DECISIONS.md) if new decisions made

### After Implementation

- [ ] Share [MIGRATION.md](./MIGRATION.md) with users
- [ ] Update main [README.md](../../README.md)
- [ ] Create changelog entry
- [ ] Announce changes to team
- [ ] Monitor for issues

---

## 📈 Metrics & KPIs

### Code Quality

- **Test Coverage**: Target >80%, stretch >90%
- **Module Size**: All files <300 lines
- **Import Errors**: 0 after refactoring
- **Breaking Changes**: 0 (backward compatibility)

### Performance

- **Monolithic Overhead**: <5% vs baseline
- **Phase Overhead**: <10% vs baseline
- **Task Creation**: <100ms per task
- **Memory Impact**: <15% increase (phase mode)

### Process

- **Implementation Time**: 17-27 hours estimated
- **Test Pass Rate**: 100% after each phase
- **Documentation Coverage**: 100% of public API
- **User Adoption**: Track via deprecation warning logs

---

## ❓ FAQ

**Q: Will this break my existing code?**  
A: No! Backward compatibility is maintained in v2.x. Old imports work with deprecation warnings.

**Q: Do I have to use phase-level execution?**  
A: No! Monolithic mode remains available and is still recommended for production.

**Q: When will old imports be removed?**  
A: Not before v3.0 (planned 12+ months after v2.0 release).

**Q: What if I find a bug during refactoring?**  
A: Stop, fix the bug in a separate branch/PR, then resume refactoring.

**Q: Can I implement phases out of order?**  
A: Not recommended. Phases have dependencies. Follow sequential order.

**Q: How do I test both execution modes?**  
A: See [TESTING.md](./TESTING.md) for comprehensive test strategy.

---

## 📝 Decision Summary

10 major decisions documented in [DECISIONS.md](./DECISIONS.md):

1. Rename `tasks/` → `preprocessing/` (avoid confusion)
2. Rename `orchestration/` → `prefect/` (clarity)
3. Dual execution modes (user choice)
4. Backward compatibility layer (smooth migration)
5. Split `flows.py` into modules (organization)
6. Wrap phase functions with `@task` (clean architecture)
7. Per-phase retry policies (optimized reliability)
8. Use `PipelineContext` for state (type-safe)
9. Deploy both modes (user flexibility)
10. Incremental 5-phase approach (risk mitigation)

**Risk Assessment**: 9/10 decisions low risk, 1/10 medium risk, 0/10 high risk

---

## 🎯 Next Actions

### Immediate (Before Starting)

1. [ ] Team reviews all documentation (2-3 hour meeting)
2. [ ] Discuss and approve approach
3. [ ] Identify any concerns or questions
4. [ ] Schedule implementation time blocks
5. [ ] Create feature branch

### Phase 1 (Days 1-2)

1. [ ] Rename `tasks/` → `preprocessing/`
2. [ ] Rename `orchestration/` → `prefect/`
3. [ ] Update all imports
4. [ ] Run test suite
5. [ ] Commit Phase 1

### Continuous

- Monitor test coverage
- Update documentation as code changes
- Log new decisions in DECISIONS.md
- Track progress in TASKS.md

---

## 📚 Document Sizes

| Document | Lines | Words | Estimated Read Time |
|----------|-------|-------|---------------------|
| OVERVIEW.md | ~200 | ~2,000 | 8-10 minutes |
| DESIGN.md | ~900 | ~6,000 | 25-30 minutes |
| REQUIREMENTS.md | ~300 | ~2,500 | 10-12 minutes |
| TASKS.md | ~500 | ~2,000 | 15-20 minutes |
| MIGRATION.md | ~600 | ~4,000 | 20-25 minutes |
| TESTING.md | ~700 | ~4,500 | 25-30 minutes |
| DECISIONS.md | ~500 | ~3,500 | 15-20 minutes |
| README.md | ~250 | ~2,000 | 8-10 minutes |
| **TOTAL** | **~3,950** | **~26,500** | **2.5-3 hours** |

**Recommendation**: Skim all documents (30-45 min), deep dive on OVERVIEW, DESIGN, TASKS (1.5 hours)

---

## 🏆 Success Indicators

### Technical Success

✅ All tests passing  
✅ Coverage >80%  
✅ No breaking changes  
✅ Both modes functional  
✅ Performance within targets

### User Success

✅ Migration guide clear  
✅ Examples working  
✅ Documentation complete  
✅ Smooth transition (no complaints)

### Process Success

✅ Timeline met (±1 week acceptable)  
✅ All phases completed  
✅ Clean git history  
✅ Code review approved

---

**Created**: December 5, 2025  
**Status**: Ready for review and approval  
**Next**: Team review meeting

---

## 📖 Additional Resources

- [Main Project README](../../README.md)
- [Container Deployment Guide](../containerization/deployment-guide.md)
- [Batch Processing Quick Start](../quick-start-batch.md)
- [Pipeline Architecture](../architecture_diagram.mmd)
