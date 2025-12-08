# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2025-01-XX

### Added

- **Phase-Level Execution Mode**: New `process_session_with_phases` flow for granular observability
  - 7 phase tasks: initialization, discovery, preprocessing, ingestion, synchronization, assembly, finalization
  - Individual retry policies per phase (1-2 retries, 10-30s delays)
  - Full visibility in Prefect UI for debugging and monitoring
- **Dual Container Deployments**:
  - `batch-processing`: Production monolithic mode (fast, single task per session)
  - `batch-processing-debug`: Debug phase mode (observable, 7 tasks per session)
- **New Public API** in `w2t_bkin.prefect`:
  - `batch_process_sessions()` flow with `use_phases` parameter
  - `process_session_with_phases()` flow for phase-level execution
  - `process_session_monolithic()` flow for backward compatibility
  - Individual phase task wrappers in `prefect.tasks` module

### Changed

- **Module Reorganization** (backward compatible):
  - Renamed `w2t_bkin.tasks/` → `w2t_bkin.preprocessing/`
  - Renamed `w2t_bkin.orchestration/` → `w2t_bkin.prefect/`
  - Split `prefect/flows.py` into cleaner structure
  - Created dedicated `prefect/tasks.py` for task wrappers
- **API Simplification**:
  - `batch_process_sessions_prefect` → `batch_process_sessions`
  - `process_single_session` → `process_session_monolithic`
- **Container Deployment Version**: 1.0.0 → 2.0.0
  - Updated deployment script for dual-mode operation
  - Separate work queues: `default` (production), `debug` (debugging)

### Deprecated

- `w2t_bkin.tasks` module → Use `w2t_bkin.preprocessing` instead
- `w2t_bkin.orchestration` module → Use `w2t_bkin.prefect` instead
- Old flow names (`batch_process_sessions_prefect`, `process_single_session`)
- **Timeline**: Backward compatibility will be removed in v3.0.0

### Documentation

- Added comprehensive refactoring documentation in `docs/refactoring/`:
  - `MIGRATION.md`: Step-by-step migration guide
  - `DESIGN.md`: Technical architecture and decisions
  - `REQUIREMENTS.md`: Structured requirements in EARS notation
  - `TASKS.md`: Detailed implementation checklist
  - `TESTING.md`: Testing strategy and validation
- Updated container deployment documentation
- Added phase-level execution examples

### Technical Details

- **Zero Breaking Changes**: All existing code continues to work
- **Deprecation Warnings**: Clear guidance for migration
- **Performance**: Expected <5% overhead in monolithic mode, <10% in phase mode
- **Test Coverage**: Core integration tests passing (test_pipeline.py: 3/3)

### Migration Guide

See [docs/refactoring/MIGRATION.md](docs/refactoring/MIGRATION.md) for detailed migration instructions.

**Quick Start**:

```python
# Old (still works with deprecation warning)
from w2t_bkin.tasks import DLCPoseTask
from w2t_bkin.orchestration import batch_process_sessions_prefect

# New (recommended)
from w2t_bkin.preprocessing import DLCPoseTask
from w2t_bkin.prefect import batch_process_sessions

# New: Phase-level execution
from w2t_bkin.prefect import batch_process_sessions

result = batch_process_sessions(
    "config.toml",
    use_phases=True,  # Enable phase-level observability
    max_workers=2
)
```

### Git History

- [Phase 1] Directory renames and backward compatibility shims
- [Phase 2-3] Split prefect modules and add phase-level execution
- [Phase 4] Update container deployments for dual modes

### Contributors

- Refactoring led by AI pair programming (GitHub Copilot)
- Based on user request: "I would like to make it more prefect friendly"

---

## [1.x.x] - Previous Versions

(Add previous changelog entries here if they exist)
