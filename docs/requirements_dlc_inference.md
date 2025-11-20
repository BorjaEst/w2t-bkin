# Requirements: DLC Inference Module

## EARS Requirements

### Ubiquitous Requirements

**REQ-DLC-1**: THE SYSTEM SHALL provide a low-level `dlc` module that accepts primitive arguments only (Path objects, int, bool, str).

**REQ-DLC-2**: THE SYSTEM SHALL never import `config`, `Session`, or `Manifest` in the low-level `dlc` module.

**REQ-DLC-3**: THE SYSTEM SHALL support batch inference with a single call to `deeplabcut.analyze_videos()` for optimal GPU utilization.

**REQ-DLC-4**: THE SYSTEM SHALL return deterministic H5 output paths following DLC naming convention.

**REQ-DLC-5**: THE SYSTEM SHALL validate model existence and structure before inference.

### Event-driven Requirements

**REQ-DLC-6**: WHEN `config.labels.dlc.run_inference` is true, THE SYSTEM SHALL execute DLC inference on all camera videos before pose import.

**REQ-DLC-7**: WHEN GPU is available and `gputouse` is not specified, THE SYSTEM SHALL auto-detect and use the first available GPU.

**REQ-DLC-8**: WHEN `gputouse` is specified via function argument, THE SYSTEM SHALL override auto-detection and use the specified GPU.

**REQ-DLC-9**: WHEN DLC model config.yaml is missing, THE SYSTEM SHALL raise `DLCInferenceError` with clear error message.

**REQ-DLC-10**: WHEN a video file is corrupted or unreadable, THE SYSTEM SHALL fail that video but continue processing remaining videos in batch.

### State-driven Requirements

**REQ-DLC-11**: WHILE inference is running, THE SYSTEM SHALL track progress and provide logging for each video processed.

**REQ-DLC-12**: WHILE GPU memory is insufficient, THE SYSTEM SHALL retry with CPU if `allow_fallback=True`.

### Unwanted Behavior Requirements

**REQ-DLC-13**: IF batch inference encounters a single video failure, THEN THE SYSTEM SHALL log the error, continue processing remaining videos, and report partial success.

**REQ-DLC-14**: IF output H5 file already exists with matching content hash, THEN THE SYSTEM SHALL skip inference (idempotency).

**REQ-DLC-15**: IF model path is relative, THEN THE SYSTEM SHALL resolve it from `config.paths.models_root` at orchestration level only.

### Optional Requirements

**REQ-DLC-16**: WHERE `config.labels.dlc.gputouse` is configured, THE SYSTEM SHALL use that GPU by default unless overridden by function argument.

**REQ-DLC-17**: WHERE `save_as_csv` is true, THE SYSTEM SHALL also generate CSV output in addition to H5.

## Acceptance Criteria

**AC-1**: Low-level function `run_dlc_inference_batch(video_paths, model_config_path, output_dir, gputouse, save_as_csv)` accepts only primitives.

**AC-2**: Function returns `List[DLCInferenceResult]` with H5 paths, frame counts, inference times, and any errors.

**AC-3**: Pipeline orchestration extracts primitives from Config/Session and calls low-level function.

**AC-4**: Batch processing uses single `deeplabcut.analyze_videos()` call for all camera videos.

**AC-5**: GPU auto-detection uses `tensorflow.config.list_physical_devices('GPU')` when `gputouse=None`.

**AC-6**: Model validation checks for `config.yaml` existence before inference.

**AC-7**: Partial failures are gracefully handled with detailed error reporting per video.

**AC-8**: Output H5 files follow DLC naming: `{video_stem}DLC_{scorer}.h5`.

**AC-9**: Unit tests mock `deeplabcut.analyze_videos` for fast testing.

**AC-10**: Integration tests use real (or fixture) DLC model on synthetic videos.

## Traceability

- **FR-5**: Optional pose estimation (DLC inference as optional pipeline stage)
- **NFR-1**: Determinism (idempotent outputs via content hashing)
- **NFR-2**: Performance (batch processing for optimal GPU utilization)
- **NFR-3**: Observability (detailed logging and error reporting)
- **Architecture**: Low-level primitives pattern (REQ-DLC-1, REQ-DLC-2)
- **Architecture**: Module-local models (DLCInferenceResult, DLCInferenceOptions)
