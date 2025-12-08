# Refactoring Testing Plan

## Overview

This document outlines the comprehensive testing strategy for the Prefect-friendly refactoring. Testing ensures backward compatibility, functional correctness, and performance requirements are met.

## Test Pyramid

```
                    /\
                   /  \
                  / E2E \          5 tests
                 /______\
                /        \
               / Integration \     15 tests
              /______________\
             /                \
            /   Unit Tests     \   30 tests
           /____________________\
```

## Unit Tests (30 tests)

### Module: `tests/unit/test_preprocessing.py`

**Purpose**: Verify preprocessing module (renamed from tasks) works correctly

**Tests:**

1. `test_pipeline_task_import` - Verify PipelineTask can be imported from preprocessing
2. `test_dlc_pose_task_import` - Verify DLCPoseTask can be imported
3. `test_sleap_pose_task_import` - Verify SLEAPPoseTask can be imported
4. `test_pipeline_task_interface` - Verify abstract methods enforced
5. `test_dlc_pose_task_execution` - Mock DLC execution
6. `test_sleap_pose_task_execution` - Mock SLEAP execution

**Status**: ⏳ Not Started

---

### Module: `tests/unit/test_prefect_tasks.py`

**Purpose**: Verify Prefect task wrappers function correctly

**Tests:**

1. `test_initialization_task_wrapper` - Verify wraps run_phase_0 correctly
2. `test_discovery_task_wrapper` - Verify wraps run_phase_1 correctly
3. `test_preprocessing_task_wrapper` - Verify wraps run_phase_2 correctly
4. `test_ingestion_task_wrapper` - Verify wraps run_phase_3 correctly
5. `test_synchronization_task_wrapper` - Verify wraps run_phase_4 correctly
6. `test_assembly_task_wrapper` - Verify wraps run_phase_5 correctly
7. `test_finalization_task_wrapper` - Verify wraps run_phase_6 correctly
8. `test_monolithic_task_wrapper` - Verify monolithic task wrapper
9. `test_task_retry_configuration` - Verify retry policies set correctly
10. `test_task_tags` - Verify task tags present
11. `test_task_names` - Verify descriptive task names
12. `test_context_passing` - Verify PipelineContext passed through correctly

**Status**: ⏳ Not Started

---

### Module: `tests/unit/test_prefect_flows.py`

**Purpose**: Verify flow definitions are correct

**Tests:**

1. `test_process_session_monolithic_flow` - Verify monolithic flow defined
2. `test_process_session_with_phases_flow` - Verify phase flow defined
3. `test_batch_process_sessions_flow` - Verify batch flow defined
4. `test_flow_parameters` - Verify required parameters defined
5. `test_flow_return_types` - Verify flows return expected dict structure

**Status**: ⏳ Not Started

---

### Module: `tests/unit/test_backward_compatibility.py`

**Purpose**: Verify backward compatibility layer works

**Tests:**

1. `test_old_tasks_import` - `from w2t_bkin.tasks` still works
2. `test_old_orchestration_import` - `from w2t_bkin.orchestration` still works
3. `test_old_flow_name_import` - `batch_process_sessions_prefect` importable
4. `test_old_task_name_import` - `process_single_session` importable
5. `test_deprecation_warning_tasks` - Warning emitted for old tasks import
6. `test_deprecation_warning_orchestration` - Warning emitted for old orchestration import
7. `test_deprecation_warning_flow_name` - Warning emitted for old flow name

**Status**: ⏳ Not Started

---

## Integration Tests (15 tests)

### Module: `tests/integration/test_execution_modes.py`

**Purpose**: Verify both execution modes work end-to-end

**Tests:**

1. `test_monolithic_mode_execution` - Run session in monolithic mode
2. `test_phase_mode_execution` - Run session in phase mode
3. `test_monolithic_mode_with_batch` - Batch with monolithic mode
4. `test_phase_mode_with_batch` - Batch with phase mode
5. `test_mode_parameter_switches_correctly` - use_phases parameter works
6. `test_phase_mode_shows_all_phases` - Verify 7 tasks created in Prefect
7. `test_monolithic_mode_shows_single_task` - Verify 1 task created

**Status**: ⏳ Not Started

---

### Module: `tests/integration/test_output_equivalence.py`

**Purpose**: Verify both modes produce identical output

**Tests:**

1. `test_nwb_files_identical` - NWB output byte-identical between modes
2. `test_metadata_identical` - Metadata files identical
3. `test_validation_results_identical` - Validation CSV identical
4. `test_timing_within_tolerance` - Phase mode <10% slower than monolithic

**Status**: ⏳ Not Started

---

### Module: `tests/integration/test_deployments.py`

**Purpose**: Verify deployments work in containers

**Tests:**

1. `test_batch_prod_deployment_exists` - batch-processing deployment created
2. `test_batch_debug_deployment_exists` - batch-processing-debug deployment created
3. `test_single_session_deployment_exists` - process-single-session deployment created
4. `test_prod_deployment_uses_monolithic` - Prod deployment uses monolithic mode

**Status**: ⏳ Not Started

---

## End-to-End Tests (5 tests)

### Module: `tests/e2e/test_container_workflows.py`

**Purpose**: Verify complete workflows in containerized environment

**Tests:**

1. `test_deploy_and_run_batch_prod` - Deploy + run batch-processing
2. `test_deploy_and_run_batch_debug` - Deploy + run batch-processing-debug
3. `test_deploy_and_run_single_session` - Deploy + run single session
4. `test_parallel_session_processing` - Multiple sessions in parallel
5. `test_failure_handling` - Verify phase failures handled correctly

**Status**: ⏳ Not Started

---

## Performance Tests

### Module: `tests/performance/test_overhead.py`

**Purpose**: Measure and verify performance characteristics

**Tests:**

1. `test_monolithic_baseline` - Establish baseline timing
2. `test_monolithic_overhead` - Verify <5% overhead vs baseline
3. `test_phase_overhead` - Verify <10% overhead vs baseline
4. `test_task_creation_overhead` - Measure per-task overhead (<100ms)
5. `test_memory_usage_monolithic` - Memory usage in monolithic mode
6. `test_memory_usage_phase` - Memory usage in phase mode

**Expected Results:**

| Metric        | Monolithic | Phase         |
| ------------- | ---------- | ------------- |
| Overhead      | <5%        | <10%          |
| Task Creation | N/A        | <100ms/task   |
| Memory        | Baseline   | <15% increase |

**Status**: ⏳ Not Started

---

## Smoke Tests (Quick Validation)

### Purpose

Fast tests to run after each phase to catch major breakages.

### Tests

1. **Import Smoke Test**

   ```bash
   python -c "from w2t_bkin.preprocessing import PipelineTask; print('OK')"
   python -c "from w2t_bkin.prefect import batch_process_sessions; print('OK')"
   ```

2. **Backward Compatibility Smoke Test**

   ```bash
   python -c "from w2t_bkin.tasks import PipelineTask; print('OK')"
   python -c "from w2t_bkin.orchestration.flows import batch_process_sessions_prefect; print('OK')"
   ```

3. **Container Build Smoke Test**

   ```bash
   docker build --target server -t w2t-bkin:test .
   ```

4. **Deployment Smoke Test**
   ```bash
   docker compose up -d
   docker exec w2t-bkin-server prefect deployment ls
   docker compose down
   ```

---

## Test Fixtures

### Shared Fixtures (`tests/conftest.py`)

**Required Fixtures:**

1. `mock_config` - Mock configuration TOML
2. `mock_pipeline_context` - Mock PipelineContext with test data
3. `mock_phase_functions` - Mocked phase functions (run_phase_0, etc.)
4. `test_session_data` - Minimal test session with all required files
5. `temp_output_dir` - Temporary directory for test outputs
6. `prefect_test_mode` - Configure Prefect for testing (ephemeral mode)

**Example:**

```python
@pytest.fixture
def mock_pipeline_context(tmp_path):
    """Create mock PipelineContext for testing."""
    return PipelineContext(
        config_path=tmp_path / "config.toml",
        subject_id="test-subject",
        session_id="test-session",
        options=RunOptions(),
    )

@pytest.fixture
def prefect_test_mode():
    """Configure Prefect for ephemeral testing."""
    from prefect.testing.utilities import prefect_test_harness
    with prefect_test_harness():
        yield
```

---

## Coverage Requirements

### Overall Coverage: >80%

**By Module:**

| Module                   | Target Coverage            |
| ------------------------ | -------------------------- |
| `preprocessing/`         | >90% (minimal changes)     |
| `prefect/tasks.py`       | >95% (new, critical)       |
| `prefect/flows.py`       | >90% (new, critical)       |
| `prefect/deployments.py` | >80% (mostly declarative)  |
| `prefect/__init__.py`    | >95% (compatibility layer) |

### Coverage Commands

```bash
# Run with coverage
pytest tests/ --cov=src/w2t_bkin --cov-report=html --cov-report=term

# View report
open htmlcov/index.html

# Check coverage thresholds
pytest tests/ --cov=src/w2t_bkin --cov-fail-under=80
```

---

## Test Execution Strategy

### Phase 1: After Directory Rename

**Run:**

- All unit tests
- Import smoke tests
- Backward compatibility tests

**Expected:** 100% pass rate

```bash
pytest tests/unit/ -v
pytest tests/unit/test_backward_compatibility.py -v
```

### Phase 2: After Module Split

**Run:**

- All unit tests
- New prefect module tests
- Backward compatibility tests
- Import smoke tests

**Expected:** 100% pass rate

```bash
pytest tests/unit/ -v
pytest tests/unit/test_prefect_tasks.py -v
pytest tests/unit/test_prefect_flows.py -v
```

### Phase 3: After Phase-Level Flow Added

**Run:**

- All unit tests
- All integration tests
- Smoke tests
- Coverage report

**Expected:** >80% coverage, 100% pass rate

```bash
pytest tests/ --cov=src/w2t_bkin --cov-report=term
```

### Phase 4: After Container Deployment Update

**Run:**

- Integration tests (deployments)
- E2E tests (container workflows)
- Deployment smoke tests

**Expected:** All deployments exist and runnable

```bash
pytest tests/integration/test_deployments.py -v
pytest tests/e2e/test_container_workflows.py -v
```

### Phase 5: Final Validation

**Run:**

- Full test suite
- Performance tests
- Coverage report
- Manual verification in Prefect UI

**Expected:** >80% coverage, all tests pass, performance within limits

```bash
pytest tests/ -v --cov=src/w2t_bkin --cov-report=html
pytest tests/performance/ -v
```

---

## Continuous Integration

### GitHub Actions Workflow

**File:** `.github/workflows/test-refactoring.yml`

```yaml
name: Refactoring Tests

on:
  push:
    branches: [feature/prefect-refactoring]
  pull_request:
    branches: [dev]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: "3.10"

      - name: Install dependencies
        run: |
          pip install -e ".[dev,test]"

      - name: Run unit tests
        run: pytest tests/unit/ -v --cov=src/w2t_bkin

      - name: Run integration tests
        run: pytest tests/integration/ -v

      - name: Check coverage
        run: pytest --cov=src/w2t_bkin --cov-fail-under=80

      - name: Upload coverage
        uses: codecov/codecov-action@v3

  container-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Build containers
        run: docker compose build

      - name: Run deployment tests
        run: |
          docker compose up -d
          docker exec w2t-bkin-server prefect deployment ls
          docker compose down
```

---

## Manual Testing Checklist

### Prefect UI Validation

After deploying, verify in Prefect UI:

- [ ] Monolithic mode shows 1 task per session
- [ ] Phase mode shows 7 tasks per session
- [ ] Task names are descriptive (phase-0-initialization, etc.)
- [ ] Tags are present and accurate
- [ ] Logs organized by task
- [ ] Duration metrics captured
- [ ] Flow runs show correct mode in parameters

### Container Validation

- [ ] Containers build successfully
- [ ] Server starts and is accessible at http://localhost:4200
- [ ] Workers register with server
- [ ] Deployments created successfully
- [ ] Can trigger deployments from UI
- [ ] Can view flow run details
- [ ] Logs stream to UI correctly

### Output Validation

- [ ] NWB files created correctly (both modes)
- [ ] NWB files pass validation
- [ ] Metadata files generated
- [ ] Sidecar files generated
- [ ] No data corruption
- [ ] Outputs byte-identical between modes

---

## Regression Testing

### Baseline Comparison

**Capture baseline before refactoring:**

```bash
# Run current code
python -m w2t_bkin.cli run config.toml subject-001 session_20251201

# Save outputs
cp output/subject-001/session_20251201.nwb tests/baseline/
cp output/subject-001/*_metadata.json tests/baseline/
```

**After refactoring, compare:**

```bash
# Run new code (monolithic)
pytest tests/integration/test_output_equivalence.py::test_nwb_files_identical

# Run new code (phase)
pytest tests/integration/test_output_equivalence.py::test_nwb_files_identical
```

---

## Test Data Requirements

### Minimal Test Session

Located in `tests/fixtures/data/test-session/`:

- `bpod/` - Minimal Bpod session data
- `videos/` - 10-second test video
- `ttls/` - Test TTL data
- `pose/` - Pre-computed pose estimates (DLC format)
- `metadata.toml` - Session metadata

### Synthetic Test Generation

Use synthetic data generators:

```bash
# Generate test session
python synthetic/session_synth.py --duration=10 --output=tests/fixtures/data/
```

---

## Success Criteria

### Must Pass

- [ ] All unit tests pass (100%)
- [ ] All integration tests pass (100%)
- [ ] Coverage >80%
- [ ] Backward compatibility verified
- [ ] Both execution modes work
- [ ] Container deployments work
- [ ] Performance within limits

### Should Pass

- [ ] E2E tests pass
- [ ] Manual UI verification complete
- [ ] Regression tests show no differences
- [ ] Documentation tests pass

### Nice to Have

- [ ] Performance tests show <5% overhead (monolithic)
- [ ] Coverage >90%
- [ ] Zero linting errors
- [ ] All docstrings present

---

## Test Maintenance

### After Refactoring Complete

1. Archive baseline test data
2. Update test fixtures to use new imports
3. Remove temporary backward compatibility tests
4. Keep performance benchmarks for future comparisons

### Ongoing

1. Add tests for new features
2. Update performance baselines periodically
3. Maintain test fixtures as schema evolves
4. Keep CI/CD pipelines updated
