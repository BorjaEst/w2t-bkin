# Synthetic Data Generation Package

**Purpose**: Generate synthetic test data for the W2T-BKIN pipeline without requiring real experimental recordings.

## Overview

The `synthetic` package provides tools to create minimal, deterministic, and valid data files that conform to the W2T-BKIN pipeline's expectations. This enables:

- **Fast local testing** without large datasets
- **Reproducible integration tests** with controlled scenarios
- **CI/CD testing** without external data dependencies
- **Scenario-based testing** for edge cases and error handling

## Key Features

- ✅ **Deterministic**: Same seed → identical outputs
- ✅ **Minimal Size**: Small files optimized for speed
- ✅ **Valid by Design**: Conforms to pipeline contracts
- ✅ **Modular**: Generate individual modalities or complete sessions
- ✅ **Scenario Support**: Pre-built test patterns

## Quick Start

### Generate a Complete Synthetic Session

```python
from pathlib import Path
from synthetic.scenarios import happy_path

# Generate a complete session
session = happy_path.make_session(
    root=Path("temp/test_sessions"),
    n_frames=100,
    seed=42
)

# Use in tests
from w2t_bkin.config import load_config, load_session
config = load_config(session.config_path)
session_data = load_session(session.session_path)

# Run pipeline
from w2t_bkin.ingest import build_and_count_manifest
manifest = build_and_count_manifest(config, session_data)
```

### Use in Pytest Fixtures

```python
import pytest
from pathlib import Path
from synthetic.scenarios import happy_path

@pytest.fixture
def synthetic_session(tmp_path):
    """Create a synthetic session for testing."""
    return happy_path.make_session(
        root=tmp_path / "synthetic",
        n_frames=64,
        seed=42
    )

def test_ingest_phase(synthetic_session):
    from w2t_bkin.config import load_config, load_session
    from w2t_bkin.ingest import build_and_count_manifest, verify_manifest

    config = load_config(synthetic_session.config_path)
    session = load_session(synthetic_session.session_path)

    manifest = build_and_count_manifest(config, session)
    result = verify_manifest(manifest, tolerance=5)

    assert result.status == "success"
```

## Package Structure

```
synthetic/
├── __init__.py              # Package exports
├── models.py                # Pydantic models for parameters and outputs
├── config_synth.py          # Generate config.toml and session.toml
├── session_synth.py         # Orchestrate complete session generation
├── video_synth.py           # Create synthetic video files
├── ttl_synth.py             # Create synthetic TTL pulse files
├── bpod_synth.py            # Create synthetic Bpod .mat files
├── pose_synth.py            # Create synthetic pose outputs (DeepLabCut CSV)
├── facemap_synth.py         # Create synthetic facemap outputs (.npy)
└── scenarios/               # Pre-built test scenarios
    ├── __init__.py
    ├── happy_path.py        # Complete valid session
    ├── mismatch_counts.py   # Frame/TTL mismatch
    ├── jitter_exceeds_budget.py  # Excessive jitter
    ├── no_ttl.py            # Nominal rate timebase
    └── multi_camera.py      # Multiple cameras
```

## Available Scenarios

### 1. Happy Path (`happy_path`)

Complete session that should pass all validation:

- Single camera with matching TTL
- Exact frame/TTL count match
- Minimal jitter within budget

```python
from synthetic.scenarios import happy_path
session = happy_path.make_session(Path("temp/test"), n_frames=100)
```

### 2. Mismatch Counts (`mismatch_counts`)

Frame/TTL count mismatch beyond tolerance:

- Video has 100 frames
- TTL has 95 pulses
- Mismatch = 5 (exceeds typical tolerance)

```python
from synthetic.scenarios import mismatch_counts
session = mismatch_counts.make_session(
    Path("temp/test"),
    n_frames=100,
    n_pulses=95
)
```

### 3. Jitter Exceeds Budget (`jitter_exceeds_budget`)

TTL jitter exceeds configured budget:

- TTL jitter: 10ms
- Budget: 5ms
- Should trigger JitterExceedsBudgetError

```python
from synthetic.scenarios import jitter_exceeds_budget
session = jitter_exceeds_budget.make_session(
    Path("temp/test"),
    jitter_s=0.010,
    budget_s=0.005
)
```

### 4. No TTL (`no_ttl`)

Session without TTL synchronization:

- Uses nominal_rate timebase
- Single camera, no TTL channels

```python
from synthetic.scenarios import no_ttl
session = no_ttl.make_session(Path("temp/test"))
```

### 5. Multi-Camera (`multi_camera`)

Multiple cameras with separate or shared TTL:

- 3 cameras by default
- Each with own TTL (or shared)

```python
from synthetic.scenarios import multi_camera

# Separate TTLs
session = multi_camera.make_session(Path("temp/test"), n_cameras=3)

# Shared TTL
session = multi_camera.make_session_shared_ttl(Path("temp/test"), n_cameras=3)
```

## Data Models

### `SyntheticCamera`

Parameters for camera generation:

```python
from synthetic.models import SyntheticCamera

camera = SyntheticCamera(
    camera_id="cam0",
    ttl_id="cam0_ttl",      # Optional
    frame_count=100,
    fps=30.0,
    resolution=(320, 240)
)
```

### `SyntheticTTL`

Parameters for TTL generation:

```python
from synthetic.models import SyntheticTTL

ttl = SyntheticTTL(
    ttl_id="cam0_ttl",
    pulse_count=100,
    start_time_s=0.0,
    period_s=0.033,         # 30 Hz
    jitter_s=0.001          # 1ms jitter
)
```

### `SyntheticSessionParams`

Parameters for complete session:

```python
from synthetic.models import SyntheticSessionParams, SyntheticCamera, SyntheticTTL

params = SyntheticSessionParams(
    session_id="test-001",
    subject_id="test-subject",
    experimenter="test-experimenter",
    cameras=[...],
    ttls=[...],
    with_bpod=False,
    seed=42
)
```

### `SyntheticSession`

Output paths from generation:

```python
# Returned by create_session()
session = create_session(root, params)

print(session.config_path)              # Path to config.toml
print(session.session_path)             # Path to session.toml
print(session.camera_video_paths)       # Dict[str, List[Path]]
print(session.ttl_paths)                # Dict[str, Path]
```

## Video Generation

The package supports two video generation modes:

### 1. FFmpeg (Recommended for Integration Tests)

Creates valid video files that can be counted with ffprobe:

```python
from synthetic.video_synth import create_video_file, check_ffmpeg_available
from synthetic.models import SyntheticCamera

if check_ffmpeg_available():
    camera = SyntheticCamera(camera_id="cam0", frame_count=100)
    video_path = create_video_file(Path("test.mp4"), camera)
```

### 2. Stub Files (Fast for Unit Tests)

Creates placeholder files with embedded frame counts. These are NOT valid video files
but can be read by the pipeline's `count_video_frames()` function via synthetic stub
detection:

```python
from synthetic.video_synth import create_stub_video_file, is_synthetic_stub, count_stub_frames

# Create stub
stub_path = create_stub_video_file(Path("test.mp4"), frame_count=100)

# Detect and read
if is_synthetic_stub(stub_path):
    frames = count_stub_frames(stub_path)  # Returns 100
```

**Note**: The W2T-BKIN ingest module automatically detects and handles synthetic stubs,
so you can use them transparently in tests.

The package auto-detects ffmpeg availability. Set `use_ffmpeg=False` to force stub mode:

```python
session = happy_path.make_session(root, use_ffmpeg=False)
```

## TTL Generation

Create TTL pulse timing files:

```python
from pathlib import Path
from synthetic.ttl_synth import create_ttl_file
from synthetic.models import SyntheticTTL

ttl = SyntheticTTL(
    ttl_id="cam0_ttl",
    pulse_count=100,
    period_s=0.033,
    jitter_s=0.001
)

ttl_path = create_ttl_file(Path("test.ttl"), ttl, seed=42)
```

### Specialized TTL Generators

```python
from synthetic.ttl_synth import (
    create_ttl_file_with_mismatch,
    create_ttl_file_with_jitter
)

# Deliberate mismatch
create_ttl_file_with_mismatch(
    Path("mismatch.ttl"),
    expected_count=100,
    actual_count=95
)

# High jitter
create_ttl_file_with_jitter(
    Path("jitter.ttl"),
    pulse_count=100,
    jitter_s=0.010
)
```

## Pose Generation

Create synthetic pose tracking data in DeepLabCut CSV format:

```python
from pathlib import Path
from synthetic.pose_synth import create_dlc_pose_csv, PoseParams

# Create pose data with custom keypoints
params = PoseParams(
    keypoints=["nose", "left_ear", "right_ear", "left_eye", "right_eye"],
    n_frames=100,
    image_width=640,
    image_height=480,
    confidence_mean=0.95,
    confidence_std=0.03,
    motion_smoothness=5.0,
    dropout_rate=0.05  # 5% missing data
)

pose_path = create_dlc_pose_csv(Path("pose.csv"), params, seed=42)
```

### Simple Pose Generation

```python
from synthetic.pose_synth import create_simple_pose_csv

# Quick generation with defaults
pose_path = create_simple_pose_csv(
    Path("pose.csv"),
    n_frames=100,
    keypoints=["nose", "left_ear", "right_ear"],
    seed=42
)
```

## Facemap Generation

Create synthetic facemap motion tracking data:

```python
from pathlib import Path
from synthetic.facemap_synth import create_facemap_output, FacemapParams

# Create facemap data
params = FacemapParams(
    n_frames=100,
    motion_frequency=2.0,  # 2 Hz dominant frequency
    motion_amplitude=50.0,
    pupil_size_range=(50.0, 150.0),
    pupil_motion_speed=5.0,
    sample_rate=30.0
)

facemap_path = create_facemap_output(Path("facemap.npy"), params, seed=42)
```

### Simple Facemap Generation

```python
from synthetic.facemap_synth import create_simple_facemap

# Quick generation with defaults
facemap_path = create_simple_facemap(
    Path("facemap.npy"),
    n_frames=100,
    seed=42
)
```

## Configuration Generation

Generate config.toml and session.toml files:

```python
from pathlib import Path
from synthetic.config_synth import create_config_toml, create_session_toml

# Create config.toml
config_path = create_config_toml(
    Path("config.toml"),
    raw_root=Path("data/raw"),
    processed_root=Path("data/processed"),
    temp_root=Path("temp"),
    timebase_source="ttl",
    timebase_ttl_id="cam0_ttl"
)

# Create session.toml
session_path = create_session_toml(
    Path("session.toml"),
    params=params,
    cameras=cameras,
    ttls=ttls
)
```

## Custom Scenarios

Create your own scenarios by combining modalities:

```python
from pathlib import Path
from synthetic.models import (
    SyntheticSessionParams,
    SyntheticCamera,
    SyntheticTTL
)
from synthetic.session_synth import create_session

def make_custom_scenario(root: Path):
    """Custom scenario with specific requirements."""
    params = SyntheticSessionParams(
        session_id="custom-001",
        cameras=[
            SyntheticCamera(
                camera_id="cam0",
                ttl_id="cam0_ttl",
                frame_count=150,
                fps=60.0,
                resolution=(1280, 720)
            )
        ],
        ttls=[
            SyntheticTTL(
                ttl_id="cam0_ttl",
                pulse_count=150,
                period_s=1.0/60.0,
                jitter_s=0.002
            )
        ],
        with_bpod=True,
        bpod_trial_count=20,
        seed=42
    )

    return create_session(root, params)
```

## Testing Best Practices

### 1. Use `tmp_path` for Isolation

```python
def test_something(tmp_path):
    session = happy_path.make_session(tmp_path, seed=42)
    # tmp_path is automatically cleaned up
```

### 2. Set Seeds for Reproducibility

```python
# Same seed = same output
session1 = happy_path.make_session(Path("test"), seed=42)
session2 = happy_path.make_session(Path("test"), seed=42)
# session1 and session2 are identical
```

### 3. Use Minimal Frame Counts

```python
# Fast tests with small data
session = happy_path.make_session(Path("test"), n_frames=32)
```

### 4. Test Multiple Scenarios

```python
@pytest.mark.parametrize("scenario", [
    "happy_path",
    "mismatch_counts",
    "no_ttl"
])
def test_all_scenarios(tmp_path, scenario):
    from synthetic.scenarios import (
        happy_path, mismatch_counts, no_ttl
    )
    scenarios = {
        "happy_path": happy_path,
        "mismatch_counts": mismatch_counts,
        "no_ttl": no_ttl
    }
    session = scenarios[scenario].make_session(tmp_path)
    # Test logic...
```

## Future Enhancements

- [ ] **Bpod .mat generation**: Full scipy-based .mat file creation
- [ ] **Pose output generation**: DeepLabCut-style CSV/HDF5 files
- [ ] **Facemap generation**: Facemap output files
- [ ] **NWB stub generation**: Minimal NWB files for validation testing
- [ ] **Parallel generation**: Speed up multi-file creation
- [ ] **CLI tool**: Command-line interface for generating datasets

## Requirements Coverage

This package supports testing of:

- **FR-1/2/3**: Config/session loading and file discovery
- **FR-13/15/16**: Frame/TTL counting and verification
- **FR-TB-\***: Timebase alignment scenarios
- **NFR-1/2**: Deterministic processing validation
- **NFR-4**: Fast verification testing

## Contributing

When adding new scenarios:

1. Create a new file in `synthetic/scenarios/`
2. Follow the existing pattern (accept `root`, `session_id`, `seed`)
3. Return `SyntheticSession`
4. Add docstring with usage example
5. Update `scenarios/__init__.py`
6. Update this README

## License

Same as parent project (W2T-BKIN).
