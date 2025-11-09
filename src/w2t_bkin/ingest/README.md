# Ingest Module

Discover session assets, extract video metadata, and build manifest for the W2T BKin pipeline.

## Overview

Layer 2 module providing session ingestion with:
- Video file discovery and metadata extraction
- Synchronization file detection
- Optional asset discovery (pose, facemap, events)
- Manifest JSON generation

## Purpose

1. **Discover Assets**: Find videos, sync files, and optional data files
2. **Extract Metadata**: Use ffprobe to get video properties (codec, fps, duration, resolution)
3. **Validate Inputs**: Ensure minimum requirements met (videos + sync)
4. **Build Manifest**: Create structured JSON manifest with absolute paths and provenance

## Public API

### Main Function

```python
from w2t_bkin.ingest import build_manifest
from w2t_bkin.config import load_settings

# Load configuration
settings = load_settings("config.toml")

# Build manifest
manifest_path = build_manifest(
    session_dir="data/raw/session_001",
    settings=settings,
    output_dir="data/interim/session_001"
)
```

### Discovery Functions

```python
from w2t_bkin.ingest import (
    discover_videos,
    discover_sync_files,
    discover_events,
    discover_pose,
    discover_facemap,
    extract_video_metadata,
)

# Discover specific assets
videos = discover_videos(session_dir, settings)
sync_files = discover_sync_files(session_dir, settings)
events = discover_events(session_dir, settings)

# Extract metadata from single video
metadata = extract_video_metadata("video.mp4", camera_id=0)
```

## Design Constraints

**Requirements**: FR-1 (Ingest five camera videos), NFR-8 (Data integrity)

**Layer 2 Dependencies**:
- May import: `config`, `domain`, `utils`
- No imports from: other stages (sync, pose, etc.), nwb, qc, cli

**Validation Rules**:
- Session directory must exist
- At least one video must be found matching pattern
- At least one sync file must be found
- All video paths must be absolute
- All discovered paths resolved to absolute

## Examples

### Basic Ingestion

```python
from w2t_bkin.config import Settings
from w2t_bkin.ingest import build_manifest

settings = Settings(
    session={"id": "session_001"},
    video={"pattern": "**/*.mp4"},
)

manifest_path = build_manifest(
    session_dir="data/raw/session_001",
    settings=settings,
)

# Manifest written to: data/raw/session_001/manifest.json
```

### With Custom Output Directory

```python
manifest_path = build_manifest(
    session_dir="data/raw/session_001",
    settings=settings,
    output_dir="data/interim/session_001",
)

# Manifest written to: data/interim/session_001/manifest.json
```

### Manifest Structure

```json
{
  "session_id": "session_001",
  "videos": [
    {
      "camera_id": 0,
      "path": "/absolute/path/to/cam0.mp4",
      "codec": "h264",
      "fps": 30.0,
      "duration": 60.5,
      "resolution": [1920, 1080]
    }
  ],
  "sync": [
    {
      "path": "/absolute/path/to/sync.bin",
      "type": "ttl",
      "name": "frame_trigger",
      "polarity": "rising"
    }
  ],
  "events": [],
  "pose": [],
  "facemap": [],
  "config_snapshot": {
    "project": {"name": "w2t-bkin-pipeline", "n_cameras": 5},
    "video": {"pattern": "**/*.mp4", "fps": 30.0}
  },
  "provenance": {
    "git_commit": "abc1234",
    "session_dir": "/absolute/path/to/session",
    "output_dir": "/absolute/path/to/output"
  }
}
```

## Testing

### Unit Tests

```bash
pytest tests/unit/test_ingest.py -v
```

### Test Coverage

- build_manifest (valid session, missing directory, no videos, no sync)
- discover_videos (multiple videos, no videos, pattern matching)
- extract_video_metadata (valid extraction, missing file, ffprobe failure)
- discover_sync_files (configured channels, fallback detection, none found)
- discover_events/pose/facemap (found when configured, empty when not)
- Edge cases (empty directory, relative paths, session ID determination)

## Usage Patterns

### CLI Integration

```python
def ingest_command(session_dir: str, config_path: str):
    """CLI entry point for ingest subcommand."""
    settings = load_settings(config_path)
    
    try:
        manifest_path = build_manifest(session_dir, settings)
        print(f"✓ Manifest created: {manifest_path}")
    except ValueError as e:
        print(f"✗ Ingestion failed: {e}")
        sys.exit(1)
```

### Programmatic Discovery

```python
from pathlib import Path

# Custom discovery workflow
session_dir = Path("data/raw/session_001")
settings = load_settings()

# Discover assets independently
videos = discover_videos(session_dir, settings)
if not videos:
    raise ValueError("No videos found")

# Extract metadata for each video
for i, video_path in enumerate(videos):
    metadata = extract_video_metadata(video_path, camera_id=i)
    print(f"Camera {i}: {metadata.fps}fps, {metadata.duration}s")
```

### Error Handling

```python
from pathlib import Path

try:
    manifest_path = build_manifest(session_dir, settings)
except FileNotFoundError as e:
    print(f"Session directory not found: {e}")
except ValueError as e:
    print(f"Validation failed: {e}")
except RuntimeError as e:
    print(f"FFprobe error: {e}")
```

## Video Metadata Extraction

### FFprobe Integration

The module uses `ffprobe` to extract video metadata:

```bash
ffprobe -v error \
  -select_streams v:0 \
  -show_entries stream=codec_name,r_frame_rate,duration,width,height \
  -of json \
  video.mp4
```

**Requirements**:
- FFmpeg/FFprobe must be installed and in PATH
- Video files must contain at least one video stream

**Parsed Fields**:
- `codec_name`: Video codec (e.g., "h264", "vp9")
- `r_frame_rate`: Frame rate as fraction (e.g., "30/1" → 30.0 fps)
- `duration`: Video duration in seconds
- `width`, `height`: Video resolution

## Discovery Patterns

### Videos

- Pattern from `settings.video.pattern` (default: `**/*.mp4`)
- Recursive search from session directory
- Sorted alphabetically for deterministic camera ID assignment

### Sync Files

1. **Configured TTL Channels**: From `settings.sync.ttl_channels[].path`
2. **Fallback Auto-Detection**: `**/sync*.bin`, `**/sync*.csv`, `**/ttl*.bin`

### Events (Optional)

- Patterns from `settings.events.patterns`
- Default: `**/*_training.ndjson`, `**/*_trial_stats.ndjson`

### Pose (Optional)

- **DLC**: `**/*DLC*.h5` (if `settings.labels.dlc.model` set)
- **SLEAP**: `**/*.slp` (if `settings.labels.sleap.model` set)

### Facemap (Optional)

- Pattern: `**/*facemap*.npy` (if `settings.facemap.run` enabled)

## Validation Rules Reference

### build_manifest

- `session_dir` must exist
- At least one video must match pattern
- At least one sync file must be found
- All paths converted to absolute
- `session_id` from `settings.session.id` or directory name

### extract_video_metadata

- Video file must exist
- FFprobe must succeed (exit code 0)
- Video must contain at least one video stream
- Frame rate denominator must be non-zero
- Resolution must be positive integers

### VideoMetadata Constraints (from domain)

- `camera_id` >= 0
- `fps` > 0
- `duration` >= 0
- `resolution` = (width > 0, height > 0)

## Dependencies

**Internal (Layer 0-1)**:
- `w2t_bkin.config`: Settings, load_settings
- `w2t_bkin.domain`: Manifest, VideoMetadata
- `w2t_bkin.utils`: write_json, get_commit

**External**:
- `ffprobe`: Video metadata extraction (required)
- Standard library: `subprocess`, `json`, `logging`, `pathlib`

## Error Handling

### FileNotFoundError

- Session directory doesn't exist
- Video file not found during metadata extraction

### ValueError

- No videos found matching pattern
- No sync files found
- Empty session directory

### RuntimeError

- FFprobe execution failure
- FFprobe timeout (30s)
- Invalid FFprobe JSON output
- No video stream in file

## Performance Considerations

- FFprobe runs sequentially for each video (typically <1s per video)
- Glob patterns cached by pathlib
- Manifest written once at end
- No video data loaded into memory (metadata only)

## See Also

- `requirements.md`: FR-1 (Ingest assets), NFR-8 (Data integrity)
- `design.md`: §2 (Module Breakdown), §3.1 (Manifest), §18 (Directory Conventions)
- `api.md §3.4`: Ingest module API specification
- `domain/README.md`: VideoMetadata and Manifest contracts
