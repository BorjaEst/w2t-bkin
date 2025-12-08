# Refactoring Implementation Tasks

## Task Status Legend

- ⏳ Not Started
- 🔄 In Progress
- ✅ Complete
- ❌ Blocked
- 🧪 Testing

---

## Phase 1: Rename Directories & Update Imports

**Goal**: Rename `tasks/` → `preprocessing/`, `orchestration/` → `prefect/`  
**Risk**: Low  
**Estimated Time**: 2-4 hours

### Tasks

- [ ] **1.1** Create backup branch
  - Command: `git checkout -b backup/pre-refactor`
  - Command: `git push origin backup/pre-refactor`

- [ ] **1.2** Create feature branch
  - Command: `git checkout dev`
  - Command: `git checkout -b feature/prefect-refactoring`

- [ ] **1.3** Rename `tasks/` → `preprocessing/`
  - Command: `git mv src/w2t_bkin/tasks src/w2t_bkin/preprocessing`
  - Verify: `ls -la src/w2t_bkin/preprocessing/`

- [ ] **1.4** Rename `orchestration/` → `prefect/`
  - Command: `git mv src/w2t_bkin/orchestration src/w2t_bkin/prefect`
  - Verify: `ls -la src/w2t_bkin/prefect/`

- [ ] **1.5** Update imports in `preprocessing/` module
  - Files: `preprocessing/*.py`
  - Find: `from w2t_bkin.tasks`
  - Replace: `from w2t_bkin.preprocessing`

- [ ] **1.6** Update imports in `prefect/` module
  - Files: `prefect/*.py`
  - Find: `from w2t_bkin.orchestration`
  - Replace: `from w2t_bkin.prefect`

- [ ] **1.7** Update imports in `core/` module
  - Search: `grep -r "from w2t_bkin.tasks" src/w2t_bkin/core/`
  - Search: `grep -r "from w2t_bkin.orchestration" src/w2t_bkin/core/`
  - Update all matches

- [ ] **1.8** Update imports in `processors/` module
  - Search: `grep -r "from w2t_bkin.tasks" src/w2t_bkin/processors/`
  - Update all matches

- [ ] **1.9** Update imports in `ingest/` module
  - Search: `grep -r "from w2t_bkin.tasks" src/w2t_bkin/ingest/`
  - Update all matches

- [ ] **1.10** Update imports in test files
  - Search: `grep -r "from w2t_bkin.tasks" tests/`
  - Search: `grep -r "from w2t_bkin.orchestration" tests/`
  - Update all matches

- [ ] **1.11** Update imports in examples
  - Search: `grep -r "from w2t_bkin" examples/`
  - Update all matches

- [ ] **1.12** Update imports in CLI
  - File: `src/w2t_bkin/cli.py`
  - Check for any references to old paths

- [ ] **1.13** Run test suite
  - Command: `pytest tests/ -v`
  - Expected: All tests pass

- [ ] **1.14** Commit changes
  - Command: `git add -A`
  - Command: `git commit -m "refactor: rename tasks/ to preprocessing/, orchestration/ to prefect/"`

---

## Phase 2: Split `prefect/flows.py` Into Modules

**Goal**: Extract tasks, deployments, infrastructure into separate files  
**Risk**: Medium  
**Estimated Time**: 4-6 hours

### Tasks

- [ ] **2.1** Create `prefect/tasks.py` file
  - Touch: `src/w2t_bkin/prefect/tasks.py`
  - Add module docstring

- [ ] **2.2** Implement phase task wrappers
  - [ ] 2.2.1: Import phase functions from `core.pipeline.phases`
  - [ ] 2.2.2: Create `initialization_task()` with @task decorator
  - [ ] 2.2.3: Create `discovery_task()` with @task decorator
  - [ ] 2.2.4: Create `preprocessing_task()` with @task decorator
  - [ ] 2.2.5: Create `ingestion_task()` with @task decorator
  - [ ] 2.2.6: Create `synchronization_task()` with @task decorator
  - [ ] 2.2.7: Create `assembly_task()` with @task decorator
  - [ ] 2.2.8: Create `finalization_task()` with @task decorator
  - [ ] 2.2.9: Create `process_session_monolithic_task()` wrapper

- [ ] **2.3** Configure retry policies
  - [ ] 2.3.1: initialization_task (retries=1, delay=10s)
  - [ ] 2.3.2: discovery_task (retries=2, delay=15s)
  - [ ] 2.3.3: preprocessing_task (retries=2, delay=30s)
  - [ ] 2.3.4: ingestion_task (retries=1, delay=10s)
  - [ ] 2.3.5: synchronization_task (retries=2, delay=20s)
  - [ ] 2.3.6: assembly_task (retries=1, delay=10s)
  - [ ] 2.3.7: finalization_task (retries=1, delay=10s)

- [ ] **2.4** Add task tags and names
  - Use descriptive names: `phase-0-initialization`, etc.
  - Add relevant tags: `["pipeline", "initialization"]`, etc.

- [ ] **2.5** Create new `prefect/flows.py`
  - Keep only flow functions
  - Remove task definitions (moved to tasks.py)
  - Import tasks from `prefect.tasks`

- [ ] **2.6** Implement `process_session_monolithic` flow
  - Use `process_session_monolithic_task`
  - Keep current behavior for backward compatibility

- [ ] **2.7** Create `prefect/deployments.py`
  - Touch: `src/w2t_bkin/prefect/deployments.py`
  - Move deployment definitions from flows.py

- [ ] **2.8** Define deployments
  - [ ] 2.8.1: `batch_prod_deployment` (monolithic mode)
  - [ ] 2.8.2: `batch_debug_deployment` (phase mode)
  - [ ] 2.8.3: `single_session_deployment` (phase mode)

- [ ] **2.9** Create `prefect/__init__.py` with public API
  - Export all flows
  - Export all tasks
  - Add backward compatibility layer
  - Add deprecation warnings

- [ ] **2.10** Update `prefect/__init__.py` with deprecation logic
  - Implement `__getattr__` for old names
  - Map `batch_process_sessions_prefect` → `batch_process_sessions`
  - Map `process_single_session` → `process_session_monolithic_task`

- [ ] **2.11** Run test suite
  - Command: `pytest tests/ -v`
  - Expected: All tests pass

- [ ] **2.12** Test backward compatibility
  - Import old names: `from w2t_bkin.prefect import batch_process_sessions_prefect`
  - Verify deprecation warning shown
  - Verify functionality works

- [ ] **2.13** Commit changes
  - Command: `git add -A`
  - Command: `git commit -m "refactor: split prefect/flows.py into tasks, flows, deployments modules"`

---

## Phase 3: Add Phase-Level Execution Flow

**Goal**: Implement `process_session_with_phases` flow  
**Risk**: Low  
**Estimated Time**: 3-5 hours

### Tasks

- [ ] **3.1** Implement `process_session_with_phases` flow
  - File: `src/w2t_bkin/prefect/flows.py`
  - Create flow function with @flow decorator
  - Chain all 7 phase tasks sequentially

- [ ] **3.2** Initialize PipelineContext
  - Accept config_path, subject_id, session_id, options
  - Create PipelineContext object
  - Pass to first phase task

- [ ] **3.3** Chain phase tasks
  - [ ] 3.3.1: Call `initialization_task(context)`
  - [ ] 3.3.2: Call `discovery_task(context)` with result from 3.3.1
  - [ ] 3.3.3: Call `preprocessing_task(context)` with result from 3.3.2
  - [ ] 3.3.4: Call `ingestion_task(context)` with result from 3.3.3
  - [ ] 3.3.5: Call `synchronization_task(context)` with result from 3.3.4
  - [ ] 3.3.6: Call `assembly_task(context)` with result from 3.3.5
  - [ ] 3.3.7: Call `finalization_task(context)` with result from 3.3.6

- [ ] **3.4** Return result dictionary
  - Include: success, subject_id, session_id, phases_completed

- [ ] **3.5** Update `batch_process_sessions` to support dual modes
  - Add `use_phases: bool = False` parameter
  - Choose flow based on parameter:
    - `use_phases=False` → `process_session_monolithic`
    - `use_phases=True` → `process_session_with_phases`

- [ ] **3.6** Update batch flow to submit parallel sub-flows
  - Use `.submit()` for parallel execution
  - Collect futures
  - Wait for all with `.result()`

- [ ] **3.7** Write unit tests for phase tasks
  - File: `tests/unit/test_prefect_tasks.py`
  - Test each phase task wrapper
  - Mock phase functions
  - Verify context passed correctly

- [ ] **3.8** Write integration test for phase flow
  - File: `tests/integration/test_execution_modes.py`
  - Test `process_session_with_phases` end-to-end
  - Use fixture data

- [ ] **3.9** Write integration test comparing modes
  - File: `tests/integration/test_output_equivalence.py`
  - Run same session in both modes
  - Compare NWB output files
  - Assert identical results

- [ ] **3.10** Run full test suite
  - Command: `pytest tests/ -v --cov=src/w2t_bkin`
  - Expected: All tests pass, >80% coverage

- [ ] **3.11** Commit changes
  - Command: `git add -A`
  - Command: `git commit -m "feat: add phase-level execution flow for granular observability"`

---

## Phase 4: Update Container Deployments

**Goal**: Deploy both monolithic and phase-level modes  
**Risk**: Medium  
**Estimated Time**: 2-3 hours

### Tasks

- [ ] **4.1** Update `docker/deploy_flows.py`
  - Import from new `prefect` module structure
  - Update to use new flow names

- [ ] **4.2** Deploy production deployment (monolithic)
  - Name: `batch-processing`
  - Mode: `use_phases=False`
  - Work pool: `docker-pool`
  - Parameters: `/configs/container.toml`, max_workers=4

- [ ] **4.3** Deploy debug deployment (phase-level)
  - Name: `batch-processing-debug`
  - Mode: `use_phases=True`
  - Work pool: `docker-pool`
  - Parameters: `/configs/container.toml`, max_workers=2

- [ ] **4.4** Deploy single session deployment
  - Name: `process-single-session`
  - Flow: `process_session_with_phases`
  - Parameters: config_path, subject_id, session_id

- [ ] **4.5** Test container build
  - Command: `docker build --target server -t w2t-bkin:server .`
  - Expected: Build succeeds

- [ ] **4.6** Test container deployment
  - Command: `docker compose up -d`
  - Command: `docker exec w2t-bkin-server prefect deployment ls`
  - Expected: See 3 deployments

- [ ] **4.7** Test monolithic deployment
  - Trigger: `batch-processing` deployment
  - Verify: Session processes successfully
  - Check: Prefect UI shows single task per session

- [ ] **4.8** Test phase deployment
  - Trigger: `batch-processing-debug` deployment
  - Verify: Session processes successfully
  - Check: Prefect UI shows 7 phase tasks per session

- [ ] **4.9** Update deployment documentation
  - File: `docs/deployment-guide.md`
  - Document both deployment options
  - Explain when to use each mode

- [ ] **4.10** Commit changes
  - Command: `git add -A`
  - Command: `git commit -m "ci: update container deployments for dual execution modes"`

---

## Phase 5: Documentation & Testing

**Goal**: Update all documentation and verify everything works  
**Risk**: Low  
**Estimated Time**: 4-6 hours

### Tasks

- [ ] **5.1** Create migration guide
  - File: `docs/refactoring/MIGRATION.md`
  - Document import changes
  - Provide examples for old → new API
  - Explain deprecation timeline

- [ ] **5.2** Update main README.md
  - Update module structure diagram
  - Add links to refactoring docs
  - Update examples to use new imports

- [ ] **5.3** Update deployment guide
  - File: `docs/deployment-guide.md`
  - Document monolithic vs phase modes
  - Add trade-off comparison table
  - Update deployment commands

- [ ] **5.4** Update quick-start guide
  - File: `docs/quick-start-batch.md`
  - Update import statements
  - Add examples for both modes

- [ ] **5.5** Update API documentation
  - Generate: `sphinx-build docs/source docs/build`
  - Verify: New module structure documented
  - Check: Docstrings are complete

- [ ] **5.6** Update examples
  - [ ] 5.6.1: `examples/bpod_camera_sync.py`
  - [ ] 5.6.2: `examples/pose_camera_nwb.py`
  - [ ] 5.6.3: `examples/sync_recovery_demo.py`
  - Update imports to new paths

- [ ] **5.7** Update notebooks
  - [ ] 5.7.1: `notebooks/example_1.ipynb`
  - [ ] 5.7.2: `notebooks/example_2.ipynb`
  - Update imports and examples

- [ ] **5.8** Add architecture diagram
  - File: `docs/refactoring/ARCHITECTURE.md`
  - Create Mermaid diagram showing new structure
  - Show flow relationships
  - Show task dependencies

- [ ] **5.9** Run full test suite
  - Command: `pytest tests/ -v --cov=src/w2t_bkin --cov-report=html`
  - Expected: All tests pass
  - Expected: >80% coverage

- [ ] **5.10** Run integration tests with containers
  - Start containers: `docker compose up -d`
  - Run batch: `docker exec w2t-bkin-server python -m prefect flow-run ...`
  - Verify: Both modes work end-to-end

- [ ] **5.11** Performance benchmarking
  - File: `tests/performance/test_overhead.py`
  - Benchmark monolithic mode
  - Benchmark phase mode
  - Compare to baseline
  - Expected: <5% overhead monolithic, <10% overhead phase

- [ ] **5.12** Create CHANGELOG entry
  - File: `CHANGELOG.md`
  - Document breaking changes (none expected)
  - Document new features (phase-level execution)
  - Document deprecations (old import names)

- [ ] **5.13** Commit documentation
  - Command: `git add -A`
  - Command: `git commit -m "docs: update documentation for refactored structure"`

- [ ] **5.14** Create pull request
  - Title: `Refactor: Prefect-friendly code organization`
  - Description: Link to design docs, overview, requirements
  - Reviewers: Assign team members
  - Labels: `refactoring`, `prefect`, `enhancement`

---

## Post-Merge Tasks

**Goal**: Ensure smooth transition after merge  
**Estimated Time**: 2-3 hours

### Tasks

- [ ] **PM-1** Merge to dev branch
  - Review PR approvals
  - Squash or merge commits as appropriate
  - Delete feature branch

- [ ] **PM-2** Update container images
  - Build new images: `docker build -t w2t-bkin:latest .`
  - Tag: `docker tag w2t-bkin:latest w2t-bkin:v2.0.0`
  - Push to registry (if applicable)

- [ ] **PM-3** Announce changes
  - Send team notification
  - Include link to migration guide
  - Highlight deprecation timeline

- [ ] **PM-4** Monitor for issues
  - Watch for import errors
  - Watch for deployment failures
  - Respond to user questions

- [ ] **PM-5** Plan v3.0 cleanup
  - Schedule removal of backward compatibility layer
  - Schedule removal of deprecated imports
  - Update roadmap

---

## Task Summary

### By Phase

| Phase | Tasks | Estimated Time | Risk |
|-------|-------|----------------|------|
| Phase 1 | 14 | 2-4 hours | Low |
| Phase 2 | 13 | 4-6 hours | Medium |
| Phase 3 | 11 | 3-5 hours | Low |
| Phase 4 | 10 | 2-3 hours | Medium |
| Phase 5 | 14 | 4-6 hours | Low |
| Post-Merge | 5 | 2-3 hours | Low |
| **Total** | **67** | **17-27 hours** | - |

### Critical Path

1. Phase 1.1-1.14 (Rename directories)
2. Phase 2.1-2.13 (Split modules)
3. Phase 3.1-3.11 (Add phase flow)
4. Phase 4.1-4.10 (Update deployments)
5. Phase 5.1-5.14 (Documentation)

### Parallel Opportunities

- Phases 1 and 2 can partially overlap (start 2.1-2.2 while doing 1.5-1.12)
- Documentation (5.1-5.8) can be done in parallel with testing (5.9-5.11)
- Examples and notebooks (5.6-5.7) can be updated independently

### Dependencies

```
Phase 1 (Rename) → Phase 2 (Split) → Phase 3 (Add flow)
                                   ↓
                           Phase 4 (Deployments)
                                   ↓
                           Phase 5 (Documentation)
                                   ↓
                            Post-Merge Tasks
```

---

## Progress Tracking

**Last Updated**: December 5, 2025  
**Current Phase**: Planning  
**Overall Progress**: 0/67 tasks (0%)

### Phase Progress

- Phase 1: 0/14 (0%)
- Phase 2: 0/13 (0%)
- Phase 3: 0/11 (0%)
- Phase 4: 0/10 (0%)
- Phase 5: 0/14 (0%)
- Post-Merge: 0/5 (0%)
