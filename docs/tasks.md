# Implementation Tasks: DLC Inference Module

## Phase 3: DLC Inference Integration

**Objective**: Add DeepLabCut model inference capability as optional pipeline stage, following 3-tier architecture with batch processing for optimal GPU utilization.

**Requirements**: See `docs/requirements_dlc_inference.md`  
**Design**: See `docs/design_dlc_inference.md`

---

## Task Breakdown

### T1: Create DLC Module Structure ✅ **[Day 1, 2h]**

**Objective**: Establish module skeleton with models and exceptions.

**Steps**:

1. Create `src/w2t_bkin/dlc/` directory
2. Create `src/w2t_bkin/dlc/__init__.py` with public API surface
3. Create `src/w2t_bkin/dlc/models.py` with:
   - `DLCInferenceOptions` dataclass
   - `DLCInferenceResult` dataclass
   - `DLCModelInfo` dataclass
4. Create `src/w2t_bkin/dlc/core.py` with:
   - `DLCInferenceError` exception
   - Stub functions: `run_dlc_inference_batch()`, `validate_dlc_model()`, `predict_output_paths()`

**Acceptance**:

- [ ] Module structure matches pose/transcode pattern
- [ ] All models are frozen dataclasses
- [ ] Public API documented in `__init__.py`
- [ ] Zero imports of `config`, `Session`, `Manifest`

**Validation**:

```bash
python -c "from w2t_bkin.dlc import DLCInferenceOptions, DLCInferenceResult, run_dlc_inference_batch"
pytest tests/unit/test_dlc.py::TestModuleStructure -v
```

---

### T2: Implement Model Validation ✅ **[Day 1, 2h]**

**Objective**: Validate DLC model structure before inference.

**Steps**:

1. Implement `validate_dlc_model(config_path)` in `core.py`:
   - Check `config.yaml` exists
   - Parse YAML with `ruamel.yaml` or `yaml`
   - Extract `Task`, `scorer`, `bodyparts`, `project_path`
   - Verify snapshot directory exists
   - Return `DLCModelInfo`
2. Add error handling for missing/invalid models
3. Add unit tests with fixture model configs

**Acceptance**:

- [ ] Validates config.yaml structure
- [ ] Extracts all required metadata
- [ ] Raises `DLCInferenceError` for invalid models
- [ ] Unit tests cover: valid model, missing file, invalid YAML, missing fields

**Validation**:

```bash
pytest tests/unit/test_dlc.py::TestModelValidation -v
```

---

### T3: Implement Output Path Prediction ✅ **[Day 1, 1h]**

**Objective**: Predict DLC output paths following naming convention.

**Steps**:

1. Implement `predict_output_paths()` in `core.py`:
   - DLC naming: `{video_stem}DLC_{scorer}.h5`
   - Optional CSV: `{video_stem}DLC_{scorer}.csv`
   - Return dict with 'h5' and optionally 'csv' keys
2. Add unit tests with various video names

**Acceptance**:

- [ ] Correctly predicts H5 path
- [ ] Correctly predicts CSV path when requested
- [ ] Handles video names with dots, underscores, spaces
- [ ] Unit tests verify naming convention

**Validation**:

```bash
pytest tests/unit/test_dlc.py::TestOutputPaths -v
```

---

### T4: Implement GPU Auto-detection ✅ **[Day 2, 2h]**

**Objective**: Auto-detect GPU availability and selection logic.

**Steps**:

1. Implement `auto_detect_gpu()` in `core.py`:
   - Use `tensorflow.config.list_physical_devices('GPU')`
   - Return 0 if GPUs available, None for CPU
   - Handle TensorFlow import errors
2. Implement `resolve_gpu_selection()` logic:
   - Priority: function arg > config value > auto-detect
   - Validate GPU index exists
   - Return final GPU selection
3. Add unit tests with mocked TensorFlow

**Acceptance**:

- [ ] Auto-detects GPU when available
- [ ] Returns None for CPU-only systems
- [ ] Respects priority order (arg > config > auto)
- [ ] Validates GPU index bounds
- [ ] Unit tests cover: GPU available, CPU only, explicit selection, invalid index

**Validation**:

```bash
pytest tests/unit/test_dlc.py::TestGPUSelection -v
```

---

### T5: Implement Core Batch Inference ✅ **[Day 2-3, 6h]**

**Objective**: Implement batch DLC inference with error handling.

**Steps**:

1. Implement `run_dlc_inference_batch()` in `core.py`:
   - Validate model with `validate_dlc_model()`
   - Resolve GPU selection
   - Prepare DLC config and video list
   - Call `deeplabcut.analyze_videos()` with:
     - `videos=[str(p) for p in video_paths]`
     - `destfolder=str(output_dir)`
     - `gputouse=gpu_index`
     - `save_as_csv=options.save_as_csv`
     - `allow_growth=options.allow_growth`
   - Handle TensorFlow OOM with CPU fallback
   - Track timing and frame counts
   - Return `List[DLCInferenceResult]`
2. Implement per-video error handling:
   - Catch individual video failures
   - Continue batch processing
   - Mark failed results with error message
3. Add extensive logging
4. Create unit tests with mocked `deeplabcut.analyze_videos`

**Acceptance**:

- [ ] Calls DLC API with correct parameters
- [ ] Processes all videos in single batch
- [ ] Handles partial failures gracefully
- [ ] Returns result for each video (success + failure)
- [ ] GPU OOM triggers CPU fallback when enabled
- [ ] Detailed logging for progress and errors
- [ ] Unit tests cover: all success, partial failure, GPU OOM, model invalid

**Validation**:

```bash
pytest tests/unit/test_dlc.py::TestBatchInference -v
```

---

### T6: Update Config Schema ✅ **[Day 3, 1h]**

**Objective**: Add optional `gputouse` field to DLC config.

**Steps**:

1. Update `DLCConfig` in `src/w2t_bkin/domain/config.py`:
   - Add `gputouse: Optional[int] = Field(None, ...)`
   - Add field description and validation
2. Update `synthetic/config_synth.py` to include `gputouse`
3. Update test fixtures in `tests/conftest.py`
4. Add config validation tests

**Acceptance**:

- [ ] `gputouse` field is optional (None default)
- [ ] Accepts int values: 0, 1, ..., -1 (CPU)
- [ ] Config validation tests pass
- [ ] Synthetic configs include new field

**Validation**:

```bash
pytest tests/unit/test_config.py::TestDLCConfig -v
```

---

### T7: Integrate with Pipeline Orchestration ✅ **[Day 4, 4h]**

**Objective**: Wire DLC inference into pipeline before pose import.

**Steps**:

1. Update `src/w2t_bkin/pipeline.py` `run_session()`:
   - Check `config.labels.dlc.run_inference`
   - Extract primitives:
     - `model_config_path = models_root / model_name / "config.yaml"`
     - `gputouse` from config (optional)
     - `all_videos` from manifest
   - Create `DLCInferenceOptions`
   - Call `run_dlc_inference_batch()`
   - Map results back to cameras
   - Pass H5 paths to `import_dlc_pose()`
2. Update `RunResult` dataclass:
   - Add `dlc_inference_results: Optional[List[DLCInferenceResult]]`
3. Add provenance tracking for DLC inference
4. Update integration tests

**Acceptance**:

- [ ] Pipeline checks `run_inference` flag
- [ ] Extracts all primitives correctly
- [ ] Calls low-level function with primitives only
- [ ] Maps H5 outputs back to cameras
- [ ] Continues with pose import using H5 files
- [ ] RunResult includes DLC provenance
- [ ] Integration tests verify end-to-end flow

**Validation**:

```bash
pytest tests/integration/test_pipeline.py::test_dlc_inference_integration -v
```

---

### T8: Create Test Fixtures ✅ **[Day 4, 2h]**

**Objective**: Create DLC model fixtures for testing.

**Steps**:

1. Create `tests/fixtures/models/dlc/` directory
2. Create minimal `config.yaml` fixture:
   - Basic DLC project structure
   - Small model (or stub for unit tests)
   - Valid bodyparts list
3. Create synthetic test videos in `tests/fixtures/videos/dlc/`
4. Update `tests/conftest.py` with DLC fixtures

**Acceptance**:

- [ ] Fixture model has valid config.yaml
- [ ] Model can be used for integration tests
- [ ] Test videos are small (<1MB)
- [ ] Fixtures accessible via pytest

**Validation**:

```bash
pytest tests/unit/test_dlc.py::TestFixtures -v
```

---

### T9: Create Unit Tests ✅ **[Day 1-3, 4h]**

**Objective**: Comprehensive unit test coverage with mocked DLC.

**Steps**:

1. Create `tests/unit/test_dlc.py` with test classes:
   - `TestModuleStructure`: Import tests
   - `TestModelValidation`: Model validation tests
   - `TestOutputPaths`: Path prediction tests
   - `TestGPUSelection`: GPU detection tests
   - `TestBatchInference`: Core inference tests (mocked)
2. Mock `deeplabcut.analyze_videos` for fast tests
3. Mock TensorFlow GPU detection
4. Test error conditions and edge cases

**Test Cases**:

- [ ] Valid batch inference (all success)
- [ ] Partial failure (one video fails)
- [ ] Model validation (valid, missing, invalid)
- [ ] GPU selection (auto, explicit, fallback)
- [ ] Output path prediction (various names)
- [ ] Error handling (OOM, corrupt video, disk full)

**Acceptance**:

- [ ] > 90% code coverage for dlc module
- [ ] All tests pass in <5s (mocked)
- [ ] Clear test names and assertions

**Validation**:

```bash
pytest tests/unit/test_dlc.py -v --cov=src/w2t_bkin/dlc
```

---

### T10: Create Integration Tests ✅ **[Day 4, 2h]**

**Objective**: End-to-end tests with real/fixture DLC model.

**Steps**:

1. Create `tests/integration/test_dlc_integration.py`:
   - Test with fixture DLC model
   - Test on synthetic videos
   - Verify H5 output format
   - Verify integration with pose import
2. Test pipeline orchestration end-to-end

**Test Cases**:

- [ ] End-to-end: synthetic videos → DLC inference → H5 → pose import
- [ ] GPU selection in pipeline
- [ ] Partial failures propagate correctly
- [ ] Provenance tracking complete

**Acceptance**:

- [ ] Integration tests pass with fixture model
- [ ] H5 outputs match DLC format
- [ ] Pose import works with generated H5

**Validation**:

```bash
pytest tests/integration/test_dlc_integration.py -v
```

---

### T11: Update Documentation ✅ **[Day 5, 3h]**

**Objective**: Update design docs and create examples.

**Steps**:

1. Update `docs/design.md`:
   - Add `dlc` row to Low-level tools table
   - Add description of batch processing strategy
2. Update `docs/architecture_status.md`:
   - Add Phase 3 section
   - Document DLC inference implementation
   - List completed features
3. Create `examples/dlc_inference_example.py`:
   - Demonstrate low-level API usage
   - Show batch processing
   - Show GPU selection
4. Update `README.md` with DLC capabilities

**Acceptance**:

- [ ] design.md includes dlc module
- [ ] architecture_status.md Phase 3 complete
- [ ] Example script runnable
- [ ] README mentions DLC inference

**Validation**:

```bash
python examples/dlc_inference_example.py --help
```

---

### T12: Create Example Scripts ✅ **[Day 5, 2h]**

**Objective**: Provide runnable examples for users.

**Steps**:

1. Create `examples/dlc_inference_example.py`:
   - Low-level API usage
   - Batch processing demonstration
   - GPU selection examples
2. Create `examples/pipeline_with_dlc.py`:
   - Full pipeline with DLC inference enabled
   - Config TOML example
   - Session TOML example
3. Add docstrings and comments

**Acceptance**:

- [ ] Examples are self-contained
- [ ] Examples have clear usage instructions
- [ ] Examples demonstrate key features

**Validation**:

```bash
python examples/dlc_inference_example.py
python examples/pipeline_with_dlc.py
```

---

## Success Criteria

**Overall Phase 3 Complete When**:

- [ ] All 12 tasks completed and validated
- [ ] Unit tests: >90% coverage, all passing
- [ ] Integration tests: all passing
- [ ] Documentation: design.md, architecture_status.md, examples updated
- [ ] Lint checks: all passing
- [ ] Performance: Batch processing 2-3x faster than sequential
- [ ] Architecture: Zero Session/Config imports in low-level module
- [ ] Idempotency: Same inputs produce same outputs

**Performance Targets**:

- Batch processing: 2-3x faster than sequential (5-camera setup)
- GPU memory: <5GB VRAM for 5 × 720p videos
- Unit tests: <10s total runtime
- Integration tests: <60s with fixture model

**Quality Gates**:

- No lint errors
- No type checking errors (if using mypy)
- All existing tests still pass
- New tests achieve >90% coverage
- Documentation complete and accurate

---

## Timeline Estimate

**Total**: 5 days (40 hours)

| Day | Tasks                    | Hours | Focus                                             |
| --- | ------------------------ | ----- | ------------------------------------------------- |
| 1   | T1, T2, T3, T9 (part)    | 7h    | Module structure, validation, tests               |
| 2   | T4, T5 (part), T9 (part) | 8h    | GPU detection, inference core, tests              |
| 3   | T5 (cont), T6, T9 (cont) | 8h    | Inference completion, config, tests               |
| 4   | T7, T8, T10              | 8h    | Pipeline integration, fixtures, integration tests |
| 5   | T11, T12                 | 5h    | Documentation, examples                           |

**Contingency**: +2 days for debugging, model fixture issues, performance tuning
