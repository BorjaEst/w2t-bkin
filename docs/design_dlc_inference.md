# Design: DLC Inference Module

## Architecture Overview

New low-level module `dlc` for DeepLabCut model inference, following established 3-tier architecture pattern.

### Module Structure

```
src/w2t_bkin/dlc/
├── __init__.py       # Public API: run_dlc_inference_batch, models, exception
├── core.py           # Low-level inference logic
├── models.py         # DLCInferenceOptions, DLCInferenceResult, DLCModelInfo
```

### Layering Compliance

- **Low-level**: `dlc/core.py` accepts primitives only (Path, int, bool, str, List)
- **High-level**: `pipeline.py` extracts primitives from Config/Session
- **Zero imports**: No `config`, `Session`, `Manifest` in dlc module
- **Module-local models**: All models owned by `dlc/models.py`

## Data Models

### DLCInferenceOptions

```python
@dataclass(frozen=True)
class DLCInferenceOptions:
    """Options for DLC inference (immutable)."""

    gputouse: Optional[int] = None  # None = auto-detect, int = specific GPU, -1 = CPU
    save_as_csv: bool = False
    allow_growth: bool = True  # TensorFlow GPU memory growth
    allow_fallback: bool = True  # Fallback to CPU on GPU OOM
    batch_size: int = 1  # TensorFlow batch size
```

### DLCInferenceResult

```python
@dataclass(frozen=True)
class DLCInferenceResult:
    """Result of DLC inference on a single video."""

    video_path: Path
    h5_output_path: Optional[Path]  # None if failed
    csv_output_path: Optional[Path]  # None if not requested or failed
    model_config_path: Path
    frame_count: int
    inference_time_s: float
    gpu_used: Optional[int]  # None if CPU
    success: bool
    error_message: Optional[str] = None
```

### DLCModelInfo

```python
@dataclass(frozen=True)
class DLCModelInfo:
    """Validated DLC model metadata."""

    config_path: Path  # Path to config.yaml
    project_path: Path  # Parent directory of config.yaml
    scorer: str  # Extracted from config
    bodyparts: List[str]  # Extracted from config
    num_outputs: int  # len(bodyparts) * 3 (x, y, likelihood)
```

## Core Functions

### run_dlc_inference_batch

```python
def run_dlc_inference_batch(
    video_paths: List[Path],
    model_config_path: Path,
    output_dir: Path,
    options: Optional[DLCInferenceOptions] = None,
) -> List[DLCInferenceResult]:
    """
    Run DLC inference on multiple videos in a single batch.

    Low-level function accepting primitives only.

    Args:
        video_paths: List of video file paths
        model_config_path: Path to DLC project config.yaml
        output_dir: Directory for H5/CSV outputs
        options: Inference options (None = defaults)

    Returns:
        List of results (one per video, ordered)

    Raises:
        DLCInferenceError: If model invalid or critical failure

    Implementation:
        1. Validate model (check config.yaml exists, parse scorer)
        2. Auto-detect GPU if options.gputouse is None
        3. Call deeplabcut.analyze_videos with video list
        4. Handle partial failures gracefully
        5. Return results for all videos (success + failures)
    """
```

### validate_dlc_model

```python
def validate_dlc_model(config_path: Path) -> DLCModelInfo:
    """
    Validate DLC model structure and extract metadata.

    Args:
        config_path: Path to config.yaml

    Returns:
        DLCModelInfo with validated metadata

    Raises:
        DLCInferenceError: If model invalid

    Checks:
        - config.yaml exists and is readable
        - Required fields present (Task, scorer, bodyparts)
        - Snapshot directory exists with checkpoints
    """
```

### predict_output_paths

```python
def predict_output_paths(
    video_path: Path,
    model_info: DLCModelInfo,
    output_dir: Path,
    save_csv: bool = False,
) -> Dict[str, Path]:
    """
    Predict DLC output file paths before inference.

    DLC naming convention: {video_stem}DLC_{scorer}.h5

    Args:
        video_path: Input video path
        model_info: Validated model metadata
        output_dir: Output directory
        save_csv: Whether CSV will be generated

    Returns:
        Dict with 'h5' and optionally 'csv' keys
    """
```

## Data Flow

### Orchestration Level (pipeline.py)

```python
def run_session(config_path, session_id, options):
    # 1. Load Config/Session
    config = load_config(config_path)
    session = load_session(session_path)

    # 2. Extract DLC primitives
    if config.labels.dlc.run_inference:
        model_config_path = Path(config.paths.models_root) / config.labels.dlc.model / "config.yaml"
        gputouse = getattr(config.labels.dlc, 'gputouse', None)  # Optional field

        # 3. Collect all camera videos for batch processing
        all_videos = []
        for camera in manifest.cameras.values():
            all_videos.extend([Path(p) for p in camera.video_files])

        # 4. Run batch inference (single DLC call)
        dlc_options = DLCInferenceOptions(
            gputouse=gputouse,
            save_as_csv=False,
            allow_growth=True,
            allow_fallback=True,
        )

        inference_results = run_dlc_inference_batch(
            video_paths=all_videos,
            model_config_path=model_config_path,
            output_dir=output_dir / "dlc",
            options=dlc_options,
        )

        # 5. Map H5 outputs back to cameras
        video_to_h5 = {
            r.video_path: r.h5_output_path
            for r in inference_results
            if r.success
        }

        # 6. Import pose data from H5 files
        for camera_id, camera_manifest in manifest.cameras.items():
            for video_path in camera_manifest.video_files:
                h5_path = video_to_h5.get(Path(video_path))
                if h5_path:
                    pose_data = import_dlc_pose(h5_path)
                    # ... continue with harmonization and alignment
```

## GPU Handling Strategy

### Auto-detection (gputouse=None)

```python
import tensorflow as tf

def auto_detect_gpu() -> Optional[int]:
    """Auto-detect first available GPU."""
    gpus = tf.config.list_physical_devices('GPU')
    if gpus:
        return 0  # Use first GPU
    return None  # Use CPU
```

### Priority Order

1. **Function argument** (`options.gputouse`) - highest priority
2. **Config TOML** (`config.labels.dlc.gputouse`) - medium priority
3. **Auto-detection** - lowest priority (default)

### Configuration Schema Update

```toml
[labels.dlc]
run_inference = true
model = "BA_W2T_cam0"  # Model directory name (contains config.yaml)
gputouse = 0  # Optional: 0, 1, ... (GPU index), -1 (CPU), or omit for auto-detect
```

## Error Handling

### Pre-flight Validation

- Check model config.yaml exists
- Check all video files exist
- Check output directory writable
- Validate GPU index if specified

### Batch Processing Failures

- **Critical**: Model invalid → raise DLCInferenceError immediately
- **Per-video**: Corrupt video → log error, continue batch, mark result as failed
- **GPU OOM**: Catch TensorFlow OOM → retry with CPU if `allow_fallback=True`

### Partial Success Handling

```python
results = run_dlc_inference_batch(videos, model, output_dir)

success_count = sum(1 for r in results if r.success)
failure_count = len(results) - success_count

if failure_count > 0:
    logger.warning(f"DLC inference: {success_count}/{len(results)} succeeded")
    for result in results:
        if not result.success:
            logger.error(f"Failed: {result.video_path} - {result.error_message}")

# Continue pipeline with successful results only
```

## Performance Optimization

### Batch Processing Benefits

- **Single model load**: ~3-5s overhead (once per batch vs per video)
- **GPU context initialization**: ~2-3s overhead (once per batch)
- **Inference**: ~0.1-0.5s per frame (same per-frame cost)
- **Expected speedup**: 2-3x for 5-camera setup vs sequential

### Memory Management

- Set `allow_growth=True` to prevent TensorFlow from allocating all GPU memory
- Typical memory: ~3-5GB VRAM for 5 × 720p videos
- Fallback to CPU if GPU OOM occurs

### Content Addressing (Idempotency)

```python
def should_skip_inference(video_path: Path, h5_path: Path) -> bool:
    """Check if inference can be skipped (idempotency)."""
    if not h5_path.exists():
        return False

    # Compare video checksum with cached value in sidecar
    video_hash = compute_file_checksum(video_path)
    cached_hash = read_inference_metadata(h5_path.with_suffix('.json'))

    return video_hash == cached_hash
```

## Integration Points

### Config Schema Extension

Add optional `gputouse` field to `DLCConfig`:

```python
class DLCConfig(BaseModel):
    run_inference: bool
    model: str
    gputouse: Optional[int] = Field(None, description="GPU index (0, 1, ...), -1 for CPU, None for auto-detect")
```

### Pipeline Integration

1. **Phase**: After video discovery, before pose import
2. **Condition**: `config.labels.dlc.run_inference == True`
3. **Input**: All camera video paths from manifest
4. **Output**: H5 files in `output_dir/dlc/`
5. **Continuation**: Pass H5 paths to `import_dlc_pose()`

### Provenance Tracking

Add to `RunResult`:

```python
@dataclass
class RunResult:
    # ... existing fields
    dlc_inference_results: Optional[List[DLCInferenceResult]] = None
```

## Testing Strategy

### Unit Tests (Mock DLC)

```python
@pytest.fixture
def mock_analyze_videos(monkeypatch):
    """Mock deeplabcut.analyze_videos for fast testing."""
    def mock_impl(config, videos, **kwargs):
        # Create fake H5 files
        for video in videos:
            h5_path = Path(kwargs['destfolder']) / f"{video.stem}DLC_test.h5"
            # Write minimal valid H5
            df = pd.DataFrame(...)
            df.to_hdf(h5_path, 'df_with_missing')

    monkeypatch.setattr('deeplabcut.analyze_videos', mock_impl)
```

### Integration Tests (Real/Fixture Model)

- Use small DLC model on synthetic videos
- Test GPU selection, batch processing, error handling
- Verify H5 output format matches expectations

### Test Cases

1. **Valid batch**: All videos succeed
2. **Partial failure**: One video corrupted, others succeed
3. **GPU selection**: Auto-detect, explicit GPU, CPU fallback
4. **Model validation**: Missing config.yaml, invalid format
5. **Idempotency**: Skip inference if H5 exists with matching hash
6. **Output naming**: Verify DLC naming convention
7. **Provenance**: Verify metadata tracking

## Migration Path

### Phase 1: Module Skeleton (Day 1)

- Create `src/w2t_bkin/dlc/` structure
- Define models in `models.py`
- Implement model validation
- Unit tests with mocks

### Phase 2: Core Implementation (Day 2-3)

- Implement `run_dlc_inference_batch()`
- GPU auto-detection
- Error handling and partial failures
- Integration tests

### Phase 3: Pipeline Integration (Day 4)

- Update `Config` schema with optional `gputouse`
- Extract primitives in `pipeline.py`
- Wire DLC inference before pose import
- Update `RunResult` with provenance

### Phase 4: Documentation (Day 5)

- Update `design.md` low-level tools table
- Update `architecture_status.md` Phase 3
- Create example script
- Update README

## Open Questions (Resolved)

1. **GPU config**: ✅ Optional field, auto-detect default, function arg override
2. **Output naming**: ✅ Use DLC naming convention (content-addressing in metadata sidecar)
3. **Batch processing**: ✅ Single `analyze_videos` call with video list for optimal performance
4. **Model path**: ✅ Config stores model directory name, pipeline resolves from `models_root/model/config.yaml`
5. **Partial failures**: ✅ Continue batch, return results for all videos with success flags
