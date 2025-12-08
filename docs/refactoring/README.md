# Refactoring Documentation Index

This directory contains comprehensive documentation for the Prefect-friendly code refactoring project.

## Documents

### 📋 [OVERVIEW.md](./OVERVIEW.md)

**Executive summary and project plan**

- Motivation and goals
- 5-phase implementation plan
- Risk assessment
- Timeline (3-4 weeks, 15-24 hours)
- Success criteria

**Read this first** to understand the refactoring scope and approach.

---

### 🏗️ [DESIGN.md](./DESIGN.md)

**Detailed technical design**

- Current vs target structure
- Module-by-module design
- Code examples for all new modules
- Data flow diagrams
- Performance considerations

**Read this** to understand the technical implementation details.

---

### 📝 [REQUIREMENTS.md](./REQUIREMENTS.md)

**Formal requirements in EARS notation**

- Functional requirements (FR-1 to FR-23)
- Non-functional requirements (NFR-1 to NFR-17)
- Quality attributes (QA-1 to QA-9)
- Constraints and acceptance criteria
- Traceability matrix

**Read this** for testable, unambiguous requirements.

---

### ✅ [TASKS.md](./TASKS.md)

**Implementation task checklist**

- 67 tasks across 5 phases + post-merge
- Estimated time per task
- Dependencies and critical path
- Progress tracking checkboxes

**Use this** to track implementation progress day-by-day.

---

### 🚀 [MIGRATION.md](./MIGRATION.md)

**User migration guide**

- Quick summary of changes
- Before/after code examples
- New features (phase-level execution)
- Backward compatibility details
- Troubleshooting common issues

**Read this** if you're updating existing code to use the new structure.

---

### 🧪 [TESTING.md](./TESTING.md)

**Comprehensive testing strategy**

- 50+ test specifications
- Unit, integration, E2E, and performance tests
- Coverage requirements (>80%)
- CI/CD integration
- Manual validation checklists

**Use this** to ensure quality throughout refactoring.

---

## Quick Navigation

### I want to...

**Understand what's changing:**
→ Start with [OVERVIEW.md](./OVERVIEW.md)

**See technical details:**
→ Read [DESIGN.md](./DESIGN.md)

**Track implementation progress:**
→ Use [TASKS.md](./TASKS.md)

**Update my code:**
→ Follow [MIGRATION.md](./MIGRATION.md)

**Verify requirements:**
→ Check [REQUIREMENTS.md](./REQUIREMENTS.md)

**Plan testing:**
→ Review [TESTING.md](./TESTING.md)

---

## Document Status

| Document        | Status      | Last Updated |
| --------------- | ----------- | ------------ |
| OVERVIEW.md     | ✅ Complete | 2025-12-05   |
| DESIGN.md       | ✅ Complete | 2025-12-05   |
| REQUIREMENTS.md | ✅ Complete | 2025-12-05   |
| TASKS.md        | ✅ Complete | 2025-12-05   |
| MIGRATION.md    | ✅ Complete | 2025-12-05   |
| TESTING.md      | ✅ Complete | 2025-12-05   |

---

## Project Phases

### Phase 1: Rename Directories ✅ Low Risk

- Estimated: 2-4 hours
- Tasks: 14
- Status: ⏳ Not Started

### Phase 2: Split Modules ⚠️ Medium Risk

- Estimated: 4-6 hours
- Tasks: 13
- Status: ⏳ Not Started

### Phase 3: Add Phase-Level Tasks ✅ High Value

- Estimated: 3-5 hours
- Tasks: 11
- Status: ⏳ Not Started

### Phase 4: Update Deployments 🔧 Medium Value

- Estimated: 2-3 hours
- Tasks: 10
- Status: ⏳ Not Started

### Phase 5: Documentation & Testing 📝 Critical

- Estimated: 4-6 hours
- Tasks: 14
- Status: ⏳ Not Started

**Total**: 17-27 hours over 3-4 weeks

---

## Key Changes Summary

### Directory Renames

```
tasks/ → preprocessing/        (Avoid confusion with @task)
orchestration/ → prefect/      (Clear Prefect separation)
```

### API Renames

```python
# Old → New
batch_process_sessions_prefect → batch_process_sessions
process_single_session → process_session_monolithic
```

### New Features

- **Phase-level execution**: Expose 7 pipeline phases as individual Prefect tasks
- **Dual modes**: Choose monolithic (fast) or phase-level (observable)
- **Declarative deployments**: Version-controlled deployment configs
- **Better observability**: Per-phase metrics, logs, and retry logic

---

## Related Documentation

### Project Documentation

- [../README.md](../README.md) - Main project README
- [../deployment-guide.md](../deployment-guide.md) - Container deployment guide
- [../quick-start-batch.md](../quick-start-batch.md) - Batch processing quick start

### Code Documentation

- [../../src/w2t_bkin/](../../src/w2t_bkin/) - Source code
- [../../tests/](../../tests/) - Test suite
- [../../examples/](../../examples/) - Usage examples

---

## Questions & Support

### Before Implementation

- Review [OVERVIEW.md](./OVERVIEW.md) for high-level plan
- Check [REQUIREMENTS.md](./REQUIREMENTS.md) for specific requirements
- Verify [DESIGN.md](./DESIGN.md) matches expectations

### During Implementation

- Follow [TASKS.md](./TASKS.md) task-by-task
- Reference [DESIGN.md](./DESIGN.md) for code examples
- Use [TESTING.md](./TESTING.md) to validate each phase

### After Implementation

- Share [MIGRATION.md](./MIGRATION.md) with users
- Keep [TASKS.md](./TASKS.md) updated for historical record
- Update this README with final status

---

## Contributing

When updating these documents:

1. **Maintain consistency** - Changes in one doc may affect others
2. **Update "Last Updated"** - Keep status table current
3. **Version control** - Commit docs with related code changes
4. **Link properly** - Ensure all cross-references work

---

## Archive

After refactoring is complete and merged:

1. Move this directory to `docs/archive/refactoring-2025-12/`
2. Keep as historical reference
3. Link from main docs: "See refactoring archive for details"

---

**Last Updated**: December 5, 2025  
**Status**: Planning Phase  
**Next Action**: Review and approve plan, then begin Phase 1
