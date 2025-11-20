# DeepLabCut 2.3.0 Inference API Research Report

**Date**: 2025-11-20  
**DLC Version**: 2.3.11 (compatible with 2.3.0 API)  
**Purpose**: Implement efficient batch video inference with GPU support for w2t-bkin pipeline

---

## Executive Summary

DeepLabCut provides `deeplabcut.analyze_videos()` as the primary inference function. The current codebase only implements **pose data import** (reading existing H5 outputs) but does not yet implement **inference execution**. This report provides implementation guidance for adding batch video inference capabilities.

**Key Findings**:

- DLC natively supports batch processing via list of video paths
- GPU can be specified via `gputouse` parameter (integer or None for CPU)
- Output H5 files are deterministically named and placed in video directory by default
- Model requires a project-level `config.yaml` (not just checkpoint files)
- No parallelization needed - DLC handles batch processing efficiently

---

## 1. DLC Inference API

### 1.1 Primary Function: `deeplabcut.analyze_videos()`

**Function Signature** (DLC 2.3.x):

```python
deeplabcut.analyze_videos(
    config,                    # str: Full path to config.yaml (REQUIRED)
    videos,                    # list[str] or str: Video paths or directory (REQUIRED)
    videotype='',             # str: Filter by extension if videos is directory
    shuffle=1,                # int: Training shuffle index
    trainingsetindex=0,       # int: TrainingsetFraction index
    gputouse=None,            # int or None: GPU index (0, 1, ...) or None for CPU
    save_as_csv=False,        # bool: Also save as CSV
    in_random_order=True,     # bool: Randomize video order
    destfolder=None,          # str or None: Output directory override
    batchsize=None,           # int or None: Batch size override
    cropping=None,            # list or None: [x1, x2, y1, y2] crop coordinates
    TFGPUinference=True,      # bool: Use TensorFlow GPU inference
    dynamic=(False, 0.5, 10), # tuple: Dynamic cropping settings
    modelprefix='',           # str: Model prefix if non-standard
    robust_nframes=False,     # bool: Robust frame counting
    allow_growth=False,       # bool: Allow GPU memory growth
    use_shelve=False,         # bool: Use shelve for temp storage
    auto_track=True,          # bool: Auto-tracking for multi-animal
    n_tracks=None,            # int or None: Number of tracks (multi-animal)
    calibrate=False,          # bool: Calibration mode
    identity_only=False,      # bool: Identity tracking only
    use_openvino=None         # bool or None: Use OpenVINO backend
)
```

**Returns**: None (writes H5/CSV files to disk)

### 1.2 Critical Parameters for w2t-bkin

| Parameter          | Type      | Default  | Purpose                         | w2t-bkin Usage                    |
| ------------------ | --------- | -------- | ------------------------------- | --------------------------------- |
| `config`           | str       | REQUIRED | Path to DLC project config.yaml | From `config.labels.dlc.model`    |
| `videos`           | list[str] | REQUIRED | List of video file paths        | Camera video files from Manifest  |
| `gputouse`         | int/None  | None     | GPU device index (nvidia-smi)   | Configurable, default None (CPU)  |
| `shuffle`          | int       | 1        | Training shuffle index          | Default 1 (matches trained model) |
| `trainingsetindex` | int       | 0        | Training set fraction index     | Default 0                         |
| `save_as_csv`      | bool      | False    | Also output CSV                 | False (H5 is canonical)           |
| `destfolder`       | str/None  | None     | Override output directory       | None (use video directory)        |
| `batchsize`        | int/None  | None     | Inference batch size            | None (use model default)          |
| `allow_growth`     | bool      | False    | GPU memory growth               | True (for stability)              |

---

## 2. Model Structure and Validation

### 2.1 DLC Project Structure

A DLC project consists of:

```
project-root/
├── config.yaml                          # PROJECT CONFIG (required for inference)
├── dlc-models/
│   └── iteration-X/
│       └── <project>-trainset95shuffle1/
│           ├── train/
│           │   ├── pose_cfg.yaml        # Training config
│           │   ├── checkpoint           # Checkpoint manifest
│           │   ├── snapshot-150000.data-00000-of-00001
│           │   ├── snapshot-150000.index
│           │   └── snapshot-150000.meta
│           └── test/
│               └── pose_cfg.yaml
├── labeled-data/
├── training-datasets/
└── videos/
```

**Critical**: `analyze_videos()` requires the **project-level `config.yaml`**, NOT the `pose_cfg.yaml` or checkpoint files directly.

### 2.2 Current Model Location in w2t-bkin

```
models/
└── iteration-1/
    └── BA_W2T_cam0.newOct30-trainset95shuffle1/
        ├── train/
        │   ├── pose_cfg.yaml       # Training config only
        │   ├── snapshot-150000.*   # Checkpoint files (94MB)
        │   └── checkpoint
        └── test/
            └── pose_cfg.yaml
```

**ISSUE**: Missing project-level `config.yaml` - this must be created or obtained from the original DLC project.

### 2.3 Model Validation

**Pre-flight checks before inference**:

```python
def validate_dlc_model(model_path: Path) -> bool:
    """Validate DLC model exists and is properly configured.

    Args:
        model_path: Path to DLC project config.yaml

    Returns:
        True if valid

    Raises:
        InferenceError: If model invalid or missing files
    """
    # Check config.yaml exists
    if not model_path.exists():
        raise InferenceError(f"DLC config.yaml not found: {model_path}")

    # Check it's a file (not directory)
    if not model_path.is_file():
        raise InferenceError(f"DLC model path must be config.yaml file: {model_path}")

    # Validate YAML structure
    try:
        import yaml
        with open(model_path) as f:
            config = yaml.safe_load(f)
    except Exception as e:
        raise InferenceError(f"Failed to parse DLC config: {e}")

    # Check required fields
    required_fields = ['project_path', 'Task', 'bodyparts', 'TrainingFraction']
    missing = [f for f in required_fields if f not in config]
    if missing:
        raise InferenceError(f"DLC config missing required fields: {missing}")

    # Check snapshot exists (verify trained model)
    project_path = Path(config['project_path'])
    snapshot_path = project_path / 'dlc-models' / f"iteration-{config.get('iteration', 0)}"

    if not snapshot_path.exists():
        logger.warning(f"Snapshot directory not found: {snapshot_path}")

    return True
```

---

## 3. Batch Processing Strategy

### 3.1 Native Batch Support

**DLC supports batch processing natively** - passing a list of videos is MORE efficient than N individual calls:

```python
# ✅ RECOMMENDED: Single call with list
videos = [
    "/path/to/cam0_video.mp4",
    "/path/to/cam1_video.mp4",
    "/path/to/cam2_video.mp4",
]
deeplabcut.analyze_videos(config_path, videos, gputouse=0)

# ❌ INEFFICIENT: Multiple individual calls
for video in videos:
    deeplabcut.analyze_videos(config_path, [video], gputouse=0)
```

**Why batch is better**:

1. **Model loading overhead**: Model loaded once, amortized across all videos
2. **GPU context**: Single GPU context initialization
3. **Batch inference**: DLC can potentially batch frames across videos
4. **I/O efficiency**: Better disk/memory management

### 3.2 Performance Comparison

| Strategy             | Model Loads | GPU Contexts | Relative Speed     |
| -------------------- | ----------- | ------------ | ------------------ |
| Batch (N videos)     | 1           | 1            | 1.0x (baseline)    |
| Sequential (N calls) | N           | N            | ~0.3-0.5x (slower) |

### 3.3 Memory Considerations

**GPU Memory Usage**:

- **Model**: ~500MB-2GB (ResNet50)
- **Batch buffer**: ~100-500MB per video (depends on resolution)
- **Total**: Model + (batchsize × frame_buffer)

**Recommendations**:

- For **5 cameras @ 1280×720**: Use batch processing (total ~3-5GB VRAM)
- For **high-res or limited VRAM**: Process cameras in chunks
- Set `allow_growth=True` to prevent OOM crashes
- Monitor with `nvidia-smi` during inference

### 3.4 Recommended Implementation

```python
def run_dlc_inference(
    config_path: Path,
    video_paths: List[Path],
    gpu_id: Optional[int] = None,
    output_dir: Optional[Path] = None,
    chunk_size: Optional[int] = None
) -> List[Path]:
    """Run DLC inference on batch of videos.

    Args:
        config_path: Path to DLC project config.yaml
        video_paths: List of video files to analyze
        gpu_id: GPU index (0, 1, ...) or None for CPU
        output_dir: Override output directory (None = video directory)
        chunk_size: Process videos in chunks (None = all at once)

    Returns:
        List of output H5 file paths

    Raises:
        InferenceError: If inference fails
    """
    import deeplabcut

    # Validate model
    validate_dlc_model(config_path)

    # Validate videos exist
    for vp in video_paths:
        if not vp.exists():
            raise InferenceError(f"Video not found: {vp}")

    # Convert to strings (DLC expects str paths)
    video_strs = [str(vp.resolve()) for vp in video_paths]
    config_str = str(config_path.resolve())

    # Chunk processing if requested
    if chunk_size is not None:
        chunks = [video_strs[i:i+chunk_size]
                  for i in range(0, len(video_strs), chunk_size)]
    else:
        chunks = [video_strs]

    logger.info(f"Running DLC inference on {len(video_strs)} videos "
                f"in {len(chunks)} chunk(s)")

    # Process each chunk
    for i, chunk in enumerate(chunks):
        logger.info(f"Processing chunk {i+1}/{len(chunks)} "
                    f"({len(chunk)} videos)")

        try:
            deeplabcut.analyze_videos(
                config_str,
                chunk,
                gputouse=gpu_id,
                save_as_csv=False,
                destfolder=str(output_dir) if output_dir else None,
                allow_growth=True,  # Prevent GPU OOM
                TFGPUinference=(gpu_id is not None),
            )
        except Exception as e:
            raise InferenceError(f"DLC inference failed on chunk {i+1}: {e}")

    # Collect output paths
    output_paths = []
    for video_path in video_paths:
        output_h5 = predict_dlc_output_path(video_path, config_path)
        if output_h5.exists():
            output_paths.append(output_h5)
        else:
            logger.warning(f"Expected output not found: {output_h5}")

    return output_paths
```

---

## 4. Output Handling

### 4.1 Output File Naming Convention

DLC generates output H5 files with **deterministic naming**:

```
<video_stem><DLC_scorer_name>.h5
```

**Example**:

- Input: `/data/Session-001/Video/cam0/video_000.mp4`
- Output: `/data/Session-001/Video/cam0/video_000DLC_resnet50_BA_W2T_cam0shuffle1_150000.h5`

**Scorer name format**: `DLC_<network>_<project>shuffle<N>_<iteration>`

### 4.2 Output Path Prediction

```python
def predict_dlc_output_path(
    video_path: Path,
    config_path: Path,
    shuffle: int = 1,
    trainingsetindex: int = 0
) -> Path:
    """Predict output H5 path for a video.

    Args:
        video_path: Input video file path
        config_path: DLC project config.yaml
        shuffle: Training shuffle index
        trainingsetindex: Training set fraction index

    Returns:
        Predicted H5 output path
    """
    import yaml

    # Load config to get scorer name components
    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Extract scorer name components
    task = config['Task']
    date = config['date']
    iteration = config.get('snapshotindex', 'unknown')
    net_type = config.get('net_type', 'resnet_50').replace('_', '')

    # Build scorer name (matches DLC convention)
    scorer = f"DLC_{net_type}_{task}{date}shuffle{shuffle}_{iteration}"

    # Build output path
    video_stem = video_path.stem  # filename without extension
    output_name = f"{video_stem}{scorer}.h5"
    output_path = video_path.parent / output_name

    return output_path


def get_dlc_output_path(
    video_path: Path,
    config_path: Path
) -> Optional[Path]:
    """Find existing DLC output for a video.

    Args:
        video_path: Input video file path
        config_path: DLC project config.yaml

    Returns:
        Path to H5 file if exists, None otherwise
    """
    # Try predicted path
    predicted = predict_dlc_output_path(video_path, config_path)
    if predicted.exists():
        return predicted

    # Fallback: search for any H5 with matching video stem
    video_stem = video_path.stem
    h5_files = list(video_path.parent.glob(f"{video_stem}*.h5"))

    if len(h5_files) == 1:
        return h5_files[0]
    elif len(h5_files) > 1:
        logger.warning(f"Multiple H5 files found for {video_path.name}, "
                      f"using first: {h5_files[0]}")
        return h5_files[0]

    return None
```

### 4.3 Output Directory Control

**Default behavior**: Outputs written to same directory as input video

**Override with `destfolder`**:

```python
deeplabcut.analyze_videos(
    config_path,
    videos,
    destfolder="/path/to/output/dir"
)
# Output: /path/to/output/dir/video_000DLC_....h5
```

**Recommendation for w2t-bkin**:

- Use **default behavior** (output in video directory)
- Keeps outputs co-located with source data
- Simplifies path resolution in downstream stages
- Alternative: Use `intermediate_root/pose/` with `destfolder`

### 4.4 Output Format (H5)

**Structure** (pandas DataFrame with MultiIndex):

```python
# Read DLC output
import pandas as pd
df = pd.read_hdf("output.h5", "df_with_missing")

# Column structure (3-level MultiIndex)
# Level 0: scorer (e.g., "DLC_resnet50_BA_W2T_cam0shuffle1_150000")
# Level 1: bodypart (e.g., "nose", "left_ear", "trial_light")
# Level 2: coordinate (e.g., "x", "y", "likelihood")

# Access specific bodypart
nose_x = df[(scorer, "nose", "x")]
nose_y = df[(scorer, "nose", "y")]
nose_likelihood = df[(scorer, "nose", "likelihood")]

# Frame index is the DataFrame index (0, 1, 2, ...)
# Shape: (n_frames, n_bodyparts × 3)
```

**Existing import function** (already implemented):

```python
from w2t_bkin.pose import import_dlc_pose

pose_data = import_dlc_pose(Path("output.h5"))
# Returns: List[Dict] with frame_index and keypoints
```

---

## 5. Error Handling

### 5.1 Common Failure Modes

| Error Type             | Cause                        | Detection                | Recovery                          |
| ---------------------- | ---------------------------- | ------------------------ | --------------------------------- |
| **Missing Model**      | config.yaml not found        | Pre-flight check         | User error: fix config path       |
| **Missing Checkpoint** | Snapshot files missing       | DLC error during loading | User error: provide trained model |
| **Corrupt Video**      | Video file unreadable        | DLC warning/error        | Skip video, log error             |
| **GPU OOM**            | Insufficient VRAM            | CUDA OOM error           | Retry with smaller batch or CPU   |
| **Invalid Format**     | Unsupported video codec      | DLC error                | User error: transcode first       |
| **Disk Full**          | No space for output          | IOError                  | Fatal: user must free space       |
| **Wrong Config**       | Config for different project | Mismatched bodyparts     | Pre-flight validation             |

### 5.2 Exception Types

DLC uses standard Python exceptions:

- **FileNotFoundError**: Missing config or video
- **RuntimeError**: Inference errors, GPU errors
- **ValueError**: Invalid parameters
- **KeyError**: Missing config fields
- **MemoryError**: OOM (rare, usually CUDA exception)

### 5.3 Recommended Error Handling Pattern

```python
class InferenceError(Exception):
    """Base exception for inference errors."""
    pass


def safe_run_inference(
    config_path: Path,
    video_paths: List[Path],
    gpu_id: Optional[int] = None,
    fail_fast: bool = False
) -> Tuple[List[Path], List[Tuple[Path, Exception]]]:
    """Run inference with error handling.

    Args:
        config_path: DLC config.yaml path
        video_paths: Videos to analyze
        gpu_id: GPU index or None
        fail_fast: Abort on first error

    Returns:
        Tuple of (successful_outputs, failed_videos_with_errors)
    """
    import deeplabcut

    successful = []
    failed = []

    # Pre-flight validation
    try:
        validate_dlc_model(config_path)
    except InferenceError as e:
        logger.error(f"Model validation failed: {e}")
        raise

    # Process videos individually for granular error handling
    for video_path in video_paths:
        try:
            logger.info(f"Analyzing {video_path.name}...")

            deeplabcut.analyze_videos(
                str(config_path),
                [str(video_path)],
                gputouse=gpu_id,
                save_as_csv=False,
                allow_growth=True,
            )

            # Verify output
            output_path = predict_dlc_output_path(video_path, config_path)
            if output_path.exists():
                successful.append(output_path)
                logger.info(f"✓ Success: {output_path.name}")
            else:
                raise InferenceError(f"Output not found: {output_path}")

        except Exception as e:
            logger.error(f"✗ Failed: {video_path.name} - {e}")
            failed.append((video_path, e))

            if fail_fast:
                raise InferenceError(f"Inference failed on {video_path}: {e}")

    # Summary
    logger.info(f"Inference complete: {len(successful)} succeeded, "
                f"{len(failed)} failed")

    return successful, failed
```

### 5.4 Partial Failure Handling

**Strategies**:

1. **Fail-fast mode** (`fail_fast=True`): Abort on first error
2. **Best-effort mode** (`fail_fast=False`): Process all, report failures
3. **Retry with CPU**: If GPU fails, retry on CPU
4. **Chunk splitting**: If OOM, reduce chunk size

**Example**:

```python
# Try GPU first
try:
    outputs = run_dlc_inference(videos, gpu_id=0)
except InferenceError as e:
    if "CUDA out of memory" in str(e):
        logger.warning("GPU OOM, retrying on CPU...")
        outputs = run_dlc_inference(videos, gpu_id=None)
    else:
        raise
```

---

## 6. GPU Handling Best Practices

### 6.1 GPU Selection

**Check available GPUs**:

```bash
nvidia-smi --query-gpu=index,name,memory.free --format=csv
```

**Configuration**:

```python
def select_gpu(min_free_memory_mb: int = 3000) -> Optional[int]:
    """Select best available GPU.

    Args:
        min_free_memory_mb: Minimum free VRAM required

    Returns:
        GPU index or None if no suitable GPU
    """
    try:
        import subprocess
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=index,memory.free',
             '--format=csv,noheader,nounits'],
            capture_output=True, text=True, check=True
        )

        # Parse output
        gpus = []
        for line in result.stdout.strip().split('\n'):
            idx, free_mb = line.split(',')
            gpus.append((int(idx), int(free_mb)))

        # Find GPU with most free memory
        suitable = [(idx, free) for idx, free in gpus
                   if free >= min_free_memory_mb]

        if suitable:
            best_gpu = max(suitable, key=lambda x: x[1])
            logger.info(f"Selected GPU {best_gpu[0]} "
                       f"({best_gpu[1]} MB free)")
            return best_gpu[0]

        logger.warning("No GPU with sufficient memory found")
        return None

    except (subprocess.SubprocessError, FileNotFoundError):
        logger.warning("nvidia-smi not available, using CPU")
        return None
```

### 6.2 Memory Management

**Key parameters**:

```python
deeplabcut.analyze_videos(
    config,
    videos,
    gputouse=0,
    allow_growth=True,  # ✅ CRITICAL: Prevent OOM crashes
    batchsize=1,        # Reduce if OOM persists
)
```

**Monitoring**:

```python
import GPUtil

def monitor_gpu_usage():
    """Log GPU memory usage during inference."""
    gpus = GPUtil.getGPUs()
    for gpu in gpus:
        logger.info(f"GPU {gpu.id}: {gpu.memoryUsed}/{gpu.memoryTotal} MB "
                   f"({gpu.memoryUtil*100:.1f}%)")
```

### 6.3 CPU Fallback

**Always provide CPU fallback**:

```python
def run_inference_with_fallback(
    config_path: Path,
    videos: List[Path],
    prefer_gpu: bool = True
) -> List[Path]:
    """Run inference with automatic CPU fallback."""

    gpu_id = select_gpu() if prefer_gpu else None

    try:
        return run_dlc_inference(config_path, videos, gpu_id=gpu_id)
    except Exception as e:
        if gpu_id is not None and "CUDA" in str(e):
            logger.warning(f"GPU inference failed: {e}")
            logger.info("Retrying on CPU...")
            return run_dlc_inference(config_path, videos, gpu_id=None)
        raise
```

---

## 7. Integration with w2t-bkin Pipeline

### 7.1 Configuration Schema Extension

**Add to `w2t_bkin/domain/config.py`**:

```python
class DLCConfig(BaseModel):
    """DeepLabCut configuration."""

    model_config = {"frozen": True, "extra": "forbid"}

    run_inference: bool = Field(..., description="Enable DeepLabCut pose inference")
    model: str = Field(..., description="Path to DeepLabCut project config.yaml")
    gpu_id: Optional[int] = Field(None, description="GPU index (0, 1, ...) or None for CPU")
    chunk_size: Optional[int] = Field(None, description="Process videos in chunks (None = all at once)")
    allow_growth: bool = Field(True, description="Allow GPU memory growth to prevent OOM")
```

**config.toml**:

```toml
[labels.dlc]
run_inference = true
model = "models/BA_W2T_project-2024-10-30/config.yaml"  # Must be config.yaml!
gpu_id = 0          # 0, 1, ... for GPU, null for CPU
chunk_size = null   # Process all videos at once
allow_growth = true # Prevent GPU OOM
```

### 7.2 Pipeline Integration Point

**Where to integrate**: Between Phase 2 (Sync) and Phase 4 (NWB)

```python
# In pipeline.py or new pose/infer.py module

def run_dlc_inference_phase(
    config: Config,
    manifest: Manifest,
    session: Session
) -> Dict[str, Path]:
    """Run DLC inference on session videos (optional Phase 3).

    Args:
        config: Pipeline configuration
        manifest: Discovered files
        session: Session metadata

    Returns:
        Dict mapping camera_id to H5 output path
    """
    if not config.labels.dlc.run_inference:
        logger.info("DLC inference disabled, skipping")
        return {}

    # Collect video paths
    video_paths = []
    camera_ids = []
    for camera in manifest.cameras:
        # Use first video file per camera (or all if multi-segment)
        video_paths.append(Path(camera.video_files[0]))
        camera_ids.append(camera.camera_id)

    logger.info(f"Running DLC inference on {len(video_paths)} videos")

    # Run inference
    model_path = Path(config.paths.models_root) / config.labels.dlc.model

    output_paths = run_dlc_inference(
        config_path=model_path,
        video_paths=video_paths,
        gpu_id=config.labels.dlc.gpu_id,
        chunk_size=config.labels.dlc.chunk_size,
    )

    # Map outputs to camera IDs
    camera_outputs = {}
    for camera_id, output_path in zip(camera_ids, output_paths):
        camera_outputs[camera_id] = output_path
        logger.info(f"  {camera_id}: {output_path}")

    return camera_outputs
```

### 7.3 CLI Integration

**Add CLI command** (`w2t_bkin/cli.py`):

```python
@app.command()
def infer(
    config_path: Path = typer.Argument(..., help="Path to config.toml"),
    session_id: str = typer.Argument(..., help="Session ID to process"),
    gpu: Optional[int] = typer.Option(None, help="GPU index (overrides config)"),
    force: bool = typer.Option(False, help="Overwrite existing outputs"),
):
    """Run pose inference on session videos."""

    config = load_config(config_path)
    session_dir = Path(config.paths.raw_root) / session_id
    session = load_session(session_dir / config.paths.metadata_file)

    # Override GPU if specified
    if gpu is not None:
        config = config.model_copy(
            update={"labels": config.labels.model_copy(
                update={"dlc": config.labels.dlc.model_copy(
                    update={"gpu_id": gpu}
                )}
            )}
        )

    # Discover videos
    manifest = discover_files(config, session)

    # Run inference
    outputs = run_dlc_inference_phase(config, manifest, session)

    print(f"✓ Inference complete: {len(outputs)} cameras processed")
    for camera_id, output_path in outputs.items():
        print(f"  {camera_id}: {output_path}")
```

**Usage**:

```bash
# Use config GPU setting
w2t-bkin infer config.toml Session-001

# Override GPU
w2t-bkin infer config.toml Session-001 --gpu 1

# Force CPU
w2t-bkin infer config.toml Session-001 --gpu -1
```

---

## 8. Testing Strategy

### 8.1 Unit Tests

```python
# tests/unit/test_pose_inference.py

def test_predict_dlc_output_path():
    """Should predict correct H5 output path."""
    video_path = Path("data/cam0.mp4")
    config_path = Path("models/config.yaml")

    output = predict_dlc_output_path(video_path, config_path)

    assert output.parent == video_path.parent
    assert output.stem.startswith(video_path.stem)
    assert output.suffix == ".h5"


def test_validate_dlc_model_missing():
    """Should raise error for missing model."""
    with pytest.raises(InferenceError):
        validate_dlc_model(Path("nonexistent.yaml"))
```

### 8.2 Integration Tests

```python
# tests/integration/test_dlc_inference.py

@pytest.mark.slow
@pytest.mark.gpu
def test_run_dlc_inference(tmp_path):
    """Should run inference and produce H5 output."""
    # Use fixture data
    config_path = Path("tests/fixtures/models/test_config.yaml")
    video_path = Path("tests/fixtures/videos/test_video.mp4")

    # Run inference
    outputs = run_dlc_inference(
        config_path,
        [video_path],
        gpu_id=None  # CPU only for tests
    )

    assert len(outputs) == 1
    assert outputs[0].exists()

    # Validate output
    pose_data = import_dlc_pose(outputs[0])
    assert len(pose_data) > 0
```

### 8.3 Mock Testing

```python
@pytest.fixture
def mock_dlc_analyze_videos(monkeypatch):
    """Mock DLC inference for fast tests."""
    def mock_analyze(config, videos, **kwargs):
        # Create fake H5 outputs
        for video in videos:
            video_path = Path(video)
            output_path = video_path.parent / f"{video_path.stem}DLC_mock.h5"

            # Create minimal H5 file
            import pandas as pd
            df = pd.DataFrame({
                ("scorer", "nose", "x"): [100.0],
                ("scorer", "nose", "y"): [200.0],
                ("scorer", "nose", "likelihood"): [0.99],
            })
            df.to_hdf(output_path, key="df_with_missing")

    monkeypatch.setattr("deeplabcut.analyze_videos", mock_analyze)
```

---

## 9. Current Codebase Status

### 9.1 What's Implemented

✅ **Import existing H5 outputs**:

- `import_dlc_pose()`: Parse DLC H5 files
- `harmonize_dlc_to_canonical()`: Map to canonical skeleton
- `align_pose_to_timebase()`: Sync to reference timebase

✅ **Configuration schema**:

- `DLCConfig` with `run_inference` and `model` fields
- TOML parsing

✅ **Test fixtures**:

- `tests/fixtures/pose/dlc/pose_sample.h5`: Real DLC output

### 9.2 What's Missing

❌ **Inference execution**:

- No `deeplabcut.analyze_videos()` wrapper
- No GPU handling logic
- No output path prediction
- No error handling for inference failures

❌ **Model validation**:

- No config.yaml validation
- No checkpoint existence checks

❌ **CLI integration**:

- No `infer` command
- No pipeline orchestration for inference phase

❌ **Documentation**:

- No inference usage examples
- No model setup guide

---

## 10. Recommendations

### 10.1 Implementation Priority

**Phase 1: Core Inference** (1-2 days)

1. Create `src/w2t_bkin/pose/infer.py` module
2. Implement `run_dlc_inference()` with batch support
3. Add `validate_dlc_model()` and `predict_dlc_output_path()`
4. Write unit tests

**Phase 2: Error Handling** (1 day) 5. Implement `InferenceError` exception hierarchy 6. Add GPU OOM recovery 7. Add partial failure handling 8. Test error cases

**Phase 3: Integration** (1-2 days) 9. Add `run_dlc_inference_phase()` to pipeline 10. Create CLI `infer` command 11. Update configuration schema 12. Write integration tests

**Phase 4: Documentation** (1 day) 13. Write inference usage guide 14. Document model setup process 15. Add examples to README 16. Create troubleshooting guide

### 10.2 Configuration Changes Required

**Add to config.toml**:

```toml
[labels.dlc]
run_inference = true
model = "models/BA_W2T_project/config.yaml"  # NOTE: Must be project config.yaml!
gpu_id = 0              # GPU index or null for CPU
chunk_size = null       # Process all videos at once
allow_growth = true     # Prevent GPU OOM
fail_fast = false       # Continue on individual video failures
```

### 10.3 Model Setup Required

**Current state**: Model checkpoints exist but **missing project config.yaml**

**Action required**:

1. Obtain original DLC project `config.yaml` from training
2. Place in `models/BA_W2T_project/config.yaml`
3. Update config.toml to point to this file

**Alternative**: Create minimal config.yaml:

```yaml
Task: BA_W2T_cam0
date: newOct30
project_path: /home/borja/w2t-bkin/models/BA_W2T_project
bodyparts:
  - sensor_top
  - sensor_bottom
  - nose
  - C1_start
  # ... (complete list from pose_cfg.yaml)
TrainingFraction: [0.95]
iteration: 0
snapshotindex: 150000
net_type: resnet_50
```

### 10.4 Best Practices Summary

1. **Always use batch processing** - single call with list of videos
2. **Set `allow_growth=True`** - prevents GPU OOM crashes
3. **Validate model before inference** - catch config errors early
4. **Provide CPU fallback** - automatic retry on GPU failure
5. **Use deterministic output paths** - simplifies downstream processing
6. **Handle partial failures gracefully** - don't abort entire session
7. **Monitor GPU memory** - log usage for debugging
8. **Keep outputs co-located** - use default output directory

---

## 11. Code Examples

### 11.1 Complete Inference Module

See Appendix A for full implementation of `src/w2t_bkin/pose/infer.py`

### 11.2 Usage Example

```python
from pathlib import Path
from w2t_bkin.config import load_config, load_session
from w2t_bkin.ingest import discover_files
from w2t_bkin.pose.infer import run_dlc_inference_phase

# Load configuration
config = load_config("config.toml")
session = load_session("data/raw/Session-001/session.toml")

# Check if inference enabled
if config.labels.dlc.run_inference:
    # Discover videos
    manifest = discover_files(config, session)

    # Run inference
    outputs = run_dlc_inference_phase(config, manifest, session)

    # Process outputs
    for camera_id, h5_path in outputs.items():
        pose_data = import_dlc_pose(h5_path)
        print(f"{camera_id}: {len(pose_data)} frames analyzed")
```

---

## 12. Appendix A: Reference Implementation

**File**: `src/w2t_bkin/pose/infer.py`

```python
"""DeepLabCut inference execution for w2t-bkin pipeline (Phase 3 - Optional).

Runs pose estimation inference on videos using trained DeepLabCut models.
Supports batch processing, GPU acceleration, and robust error handling.

Key Features:
-------------
- Batch processing for efficiency
- GPU selection and memory management
- Output path prediction and validation
- Partial failure handling
- CPU fallback on GPU errors

Main Functions:
---------------
- run_dlc_inference: Execute inference on batch of videos
- validate_dlc_model: Pre-flight model validation
- predict_dlc_output_path: Deterministic output path calculation
- get_dlc_output_path: Find existing outputs

Requirements:
-------------
- deeplabcut~=2.3.0
- tensorflow (GPU support optional)
- pyyaml

Example:
--------
>>> from pathlib import Path
>>> from w2t_bkin.pose.infer import run_dlc_inference
>>>
>>> config_path = Path("models/project/config.yaml")
>>> videos = [Path("data/cam0.mp4"), Path("data/cam1.mp4")]
>>>
>>> # Run inference with GPU
>>> outputs = run_dlc_inference(config_path, videos, gpu_id=0)
>>> print(f"Generated {len(outputs)} H5 files")
>>>
>>> # Run inference on CPU
>>> outputs = run_dlc_inference(config_path, videos, gpu_id=None)
"""

import logging
from pathlib import Path
from typing import List, Optional, Tuple

import yaml

logger = logging.getLogger(__name__)


class InferenceError(Exception):
    """Base exception for inference errors."""
    pass


def validate_dlc_model(config_path: Path) -> bool:
    """Validate DLC model configuration exists and is valid.

    Args:
        config_path: Path to DLC project config.yaml

    Returns:
        True if valid

    Raises:
        InferenceError: If model invalid or missing
    """
    if not config_path.exists():
        raise InferenceError(f"DLC config not found: {config_path}")

    if not config_path.is_file():
        raise InferenceError(f"DLC config must be a file: {config_path}")

    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
    except Exception as e:
        raise InferenceError(f"Failed to parse DLC config: {e}")

    # Check required fields
    required = ['project_path', 'Task', 'bodyparts', 'TrainingFraction']
    missing = [f for f in required if f not in config]
    if missing:
        raise InferenceError(f"DLC config missing fields: {missing}")

    logger.debug(f"Validated DLC model: {config['Task']}")
    return True


def predict_dlc_output_path(
    video_path: Path,
    config_path: Path,
    shuffle: int = 1,
) -> Path:
    """Predict output H5 path for a video.

    DLC generates: <video_stem><DLC_scorer_name>.h5

    Args:
        video_path: Input video file path
        config_path: DLC project config.yaml
        shuffle: Training shuffle index

    Returns:
        Predicted H5 output path
    """
    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Build scorer name
    task = config['Task']
    date = config['date']
    iteration = config.get('snapshotindex', '150000')
    net_type = config.get('net_type', 'resnet_50').replace('_', '')

    scorer = f"DLC_{net_type}_{task}{date}shuffle{shuffle}_{iteration}"

    # Build output path
    video_stem = video_path.stem
    output_name = f"{video_stem}{scorer}.h5"
    output_path = video_path.parent / output_name

    return output_path


def get_dlc_output_path(
    video_path: Path,
    config_path: Path
) -> Optional[Path]:
    """Find existing DLC output for a video.

    Args:
        video_path: Input video file path
        config_path: DLC project config.yaml

    Returns:
        Path to H5 file if exists, None otherwise
    """
    # Try predicted path
    predicted = predict_dlc_output_path(video_path, config_path)
    if predicted.exists():
        return predicted

    # Fallback: search for any H5 with matching stem
    video_stem = video_path.stem
    h5_files = list(video_path.parent.glob(f"{video_stem}*.h5"))

    if len(h5_files) == 1:
        return h5_files[0]
    elif len(h5_files) > 1:
        logger.warning(f"Multiple H5 files found for {video_path.name}, "
                      f"using first: {h5_files[0]}")
        return h5_files[0]

    return None


def run_dlc_inference(
    config_path: Path,
    video_paths: List[Path],
    gpu_id: Optional[int] = None,
    output_dir: Optional[Path] = None,
    chunk_size: Optional[int] = None,
    allow_growth: bool = True,
) -> List[Path]:
    """Run DLC inference on batch of videos.

    Args:
        config_path: Path to DLC project config.yaml
        video_paths: List of video files to analyze
        gpu_id: GPU index (0, 1, ...) or None for CPU
        output_dir: Override output directory (None = video directory)
        chunk_size: Process videos in chunks (None = all at once)
        allow_growth: Allow GPU memory growth

    Returns:
        List of output H5 file paths

    Raises:
        InferenceError: If inference fails
    """
    import deeplabcut

    # Validate model
    validate_dlc_model(config_path)

    # Validate videos
    for vp in video_paths:
        if not vp.exists():
            raise InferenceError(f"Video not found: {vp}")

    # Convert to strings
    video_strs = [str(vp.resolve()) for vp in video_paths]
    config_str = str(config_path.resolve())

    # Chunk processing
    if chunk_size is not None:
        chunks = [video_strs[i:i+chunk_size]
                  for i in range(0, len(video_strs), chunk_size)]
    else:
        chunks = [video_strs]

    logger.info(f"Running DLC inference on {len(video_strs)} videos "
                f"in {len(chunks)} chunk(s), GPU={gpu_id}")

    # Process each chunk
    for i, chunk in enumerate(chunks):
        logger.info(f"Processing chunk {i+1}/{len(chunks)} "
                    f"({len(chunk)} videos)")

        try:
            deeplabcut.analyze_videos(
                config_str,
                chunk,
                gputouse=gpu_id,
                save_as_csv=False,
                destfolder=str(output_dir) if output_dir else None,
                allow_growth=allow_growth,
                TFGPUinference=(gpu_id is not None),
            )
        except Exception as e:
            raise InferenceError(f"DLC inference failed on chunk {i+1}: {e}")

    # Collect output paths
    output_paths = []
    for video_path in video_paths:
        output_h5 = predict_dlc_output_path(video_path, config_path)
        if output_h5.exists():
            output_paths.append(output_h5)
            logger.info(f"✓ {video_path.name} -> {output_h5.name}")
        else:
            logger.warning(f"✗ Expected output not found: {output_h5}")

    logger.info(f"Inference complete: {len(output_paths)}/{len(video_paths)} "
                f"outputs generated")

    return output_paths
```

---

## Appendix B: References

- **DeepLabCut Documentation**: https://deeplabcut.github.io/DeepLabCut/
- **DLC GitHub**: https://github.com/DeepLabCut/DeepLabCut
- **Paper**: Mathis et al. (2018), Nature Neuroscience
- **GPU Memory Management**: https://www.tensorflow.org/guide/gpu

---

**End of Report**
