# Refactoring Requirements (EARS Notation)

## Functional Requirements

### Directory Structure

**FR-1**: `WHEN refactoring begins, THE SYSTEM SHALL rename the tasks/ directory to preprocessing/`

**FR-2**: `WHEN refactoring begins, THE SYSTEM SHALL rename the orchestration/ directory to prefect/`

**FR-3**: `WHEN directories are renamed, THE SYSTEM SHALL maintain all existing module functionality`

### Import Management

**FR-4**: `WHEN directories are renamed, THE SYSTEM SHALL update all import statements throughout the codebase to reference new module paths`

**FR-5**: `WHEN backward compatibility is required, THE SYSTEM SHALL provide compatibility layer in prefect/__init__.py that aliases old names to new implementations`

**FR-6**: `IF deprecated imports are used, THEN THE SYSTEM SHALL emit DeprecationWarning with migration guidance`

### Prefect Task Wrappers

**FR-7**: `THE SYSTEM SHALL create Prefect @task decorator wrappers for each of the 7 pipeline phase functions`

**FR-8**: `WHEN creating phase task wrappers, THE SYSTEM SHALL accept PipelineContext as input parameter`

**FR-9**: `WHEN creating phase task wrappers, THE SYSTEM SHALL return PipelineContext as output for chaining`

**FR-10**: `WHEN creating phase task wrappers, THE SYSTEM SHALL configure appropriate retry policies based on phase characteristics`

**FR-11**: `WHEN creating phase task wrappers, THE SYSTEM SHALL add descriptive name, tags, and documentation`

### Flow Organization

**FR-12**: `THE SYSTEM SHALL split orchestration/flows.py into separate prefect/ modules: flows.py, tasks.py, deployments.py, infrastructure.py`

**FR-13**: `WHEN creating prefect/flows.py, THE SYSTEM SHALL define only flow functions using @flow decorator`

**FR-14**: `WHEN creating prefect/tasks.py, THE SYSTEM SHALL define only task functions using @task decorator`

**FR-15**: `WHEN creating prefect/deployments.py, THE SYSTEM SHALL define declarative deployment configurations`

### Dual Execution Modes

**FR-16**: `THE SYSTEM SHALL provide process_session_monolithic flow that executes entire session as one task`

**FR-17**: `THE SYSTEM SHALL provide process_session_with_phases flow that executes session with individual phase tasks`

**FR-18**: `WHEN batch_process_sessions flow is called, THE SYSTEM SHALL accept use_phases boolean parameter to select execution mode`

**FR-19**: `WHEN use_phases=False, THE SYSTEM SHALL use monolithic execution mode`

**FR-20**: `WHEN use_phases=True, THE SYSTEM SHALL use phase-level execution mode`

### Deployment Configuration

**FR-21**: `THE SYSTEM SHALL create batch-processing deployment using monolithic mode for production use`

**FR-22**: `THE SYSTEM SHALL create batch-processing-debug deployment using phase mode for debugging`

**FR-23**: `WHEN deployments are created, THE SYSTEM SHALL configure appropriate work pools, queues, and parameters`

## Non-Functional Requirements

### Backward Compatibility

**NFR-1**: `THE SYSTEM SHALL maintain backward compatibility for all public API imports during v2.x releases`

**NFR-2**: `WHEN existing code imports from w2t_bkin.tasks, THE SYSTEM SHALL resolve to w2t_bkin.preprocessing modules`

**NFR-3**: `WHEN existing code imports from w2t_bkin.orchestration, THE SYSTEM SHALL resolve to w2t_bkin.prefect modules`

### Performance

**NFR-4**: `WHEN using monolithic mode, THE SYSTEM SHALL complete session processing within 5% of baseline performance`

**NFR-5**: `WHEN using phase mode, THE SYSTEM SHALL complete session processing within 10% of baseline performance`

**NFR-6**: `WHEN phase task wrappers execute, THE SYSTEM SHALL add less than 100ms overhead per task`

### Observability

**NFR-7**: `WHEN phase mode is used, THE SYSTEM SHALL display all 7 phases as separate tasks in Prefect UI`

**NFR-8**: `WHEN phase mode is used, THE SYSTEM SHALL track duration for each individual phase`

**NFR-9**: `WHEN phase fails, THE SYSTEM SHALL log error with phase name and context information`

**NFR-10**: `WHEN phase mode is used, THE SYSTEM SHALL organize logs by phase for easy navigation`

### Testing

**NFR-11**: `THE SYSTEM SHALL pass all existing test suite after refactoring`

**NFR-12**: `WHEN new modules are added, THE SYSTEM SHALL achieve minimum 80% code coverage`

**NFR-13**: `THE SYSTEM SHALL verify both monolithic and phase modes produce identical NWB output`

### Documentation

**NFR-14**: `WHEN refactoring is complete, THE SYSTEM SHALL update all code documentation to reflect new module structure`

**NFR-15**: `WHEN refactoring is complete, THE SYSTEM SHALL provide migration guide for existing users`

**NFR-16**: `WHEN refactoring is complete, THE SYSTEM SHALL update deployment guides with both execution modes`

**NFR-17**: `WHEN refactoring is complete, THE SYSTEM SHALL document trade-offs between monolithic and phase modes`

## Quality Attributes

### Maintainability

**QA-1**: `THE SYSTEM SHALL organize Prefect code in dedicated prefect/ module separate from business logic`

**QA-2**: `THE SYSTEM SHALL limit module size to maximum 300 lines per file`

**QA-3**: `THE SYSTEM SHALL use clear naming conventions that distinguish Prefect tasks from preprocessing tasks`

### Reliability

**QA-4**: `WHEN phase task fails, THE SYSTEM SHALL retry according to configured retry policy`

**QA-5**: `WHEN phase task fails after all retries, THE SYSTEM SHALL propagate failure to flow level`

**QA-6**: `WHEN session processing fails, THE SYSTEM SHALL continue processing remaining sessions in batch`

### Usability

**QA-7**: `THE SYSTEM SHALL provide clear parameter names and documentation for all flows and tasks`

**QA-8**: `THE SYSTEM SHALL emit helpful error messages when configuration is invalid`

**QA-9**: `THE SYSTEM SHALL display execution progress in Prefect UI with meaningful task names`

## Constraints

### Technical Constraints

**C-1**: `THE SYSTEM SHALL maintain compatibility with Prefect 3.6.0+`

**C-2**: `THE SYSTEM SHALL maintain compatibility with Python 3.9+`

**C-3**: `THE SYSTEM SHALL not modify core pipeline logic in core/pipeline/phases/`

**C-4**: `THE SYSTEM SHALL not break container deployment functionality`

### Process Constraints

**C-5**: `THE SYSTEM SHALL complete refactoring in feature branch before merging to dev`

**C-6**: `THE SYSTEM SHALL pass all tests before merging any phase`

**C-7**: `THE SYSTEM SHALL update documentation incrementally with each phase`

## Acceptance Criteria

### Phase 1 Complete

- [ ] `tasks/` renamed to `preprocessing/`
- [ ] `orchestration/` renamed to `prefect/`
- [ ] All imports updated
- [ ] All tests passing
- [ ] No breaking changes

### Phase 2 Complete

- [ ] `prefect/tasks.py` created with phase task wrappers
- [ ] `prefect/flows.py` contains only flow definitions
- [ ] `prefect/deployments.py` created with deployment configs
- [ ] Backward compatibility layer in `prefect/__init__.py`
- [ ] All tests passing

### Phase 3 Complete

- [ ] `process_session_with_phases` flow implemented
- [ ] `process_session_monolithic` flow implemented
- [ ] `batch_process_sessions` supports `use_phases` parameter
- [ ] Both modes produce identical NWB output
- [ ] All tests passing

### Phase 4 Complete

- [ ] `batch-processing` deployment created (monolithic)
- [ ] `batch-processing-debug` deployment created (phase mode)
- [ ] Container deployments working
- [ ] Deployment tested end-to-end

### Phase 5 Complete

- [ ] All documentation updated
- [ ] Migration guide created
- [ ] Examples updated
- [ ] README updated
- [ ] Deployment guide updated

## Traceability Matrix

| Requirement | Design Section | Implementation File | Test File |
|-------------|----------------|---------------------|-----------|
| FR-1, FR-2 | Directory Structure | Phase 1 rename scripts | tests/unit/test_imports.py |
| FR-4, FR-5, FR-6 | Backward Compatibility | prefect/__init__.py | tests/unit/test_compatibility.py |
| FR-7-FR-11 | Phase Task Wrappers | prefect/tasks.py | tests/unit/test_prefect_tasks.py |
| FR-12-FR-15 | Module Organization | prefect/*.py | tests/unit/test_prefect_modules.py |
| FR-16-FR-20 | Dual Execution Modes | prefect/flows.py | tests/integration/test_execution_modes.py |
| FR-21-FR-23 | Deployments | prefect/deployments.py | tests/integration/test_deployments.py |
| NFR-1-NFR-3 | Compatibility Layer | prefect/__init__.py | tests/unit/test_backward_compat.py |
| NFR-4-NFR-6 | Performance | prefect/tasks.py | tests/performance/test_overhead.py |
| NFR-7-NFR-10 | Observability | prefect/tasks.py | tests/integration/test_observability.py |
| NFR-13 | Output Verification | prefect/flows.py | tests/integration/test_output_equivalence.py |

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Test Coverage | >80% | pytest --cov |
| Import Errors | 0 | Static analysis |
| Breaking Changes | 0 | Compatibility tests |
| Performance Overhead (Monolithic) | <5% | Benchmark tests |
| Performance Overhead (Phase) | <10% | Benchmark tests |
| Task Overhead | <100ms/task | Profiling |
| Documentation Pages Updated | 100% | Manual review |
| Deployment Success Rate | 100% | Integration tests |
