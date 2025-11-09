# Configuration Module

Load and validate TOML configuration with Pydantic models and environment overrides for the W2T BKin pipeline.

## Overview

Layer 1 module providing configuration management with:
- TOML file parsing
- Pydantic validation
- Environment variable overrides
- Type-safe settings

## Purpose

1. **Load Configuration**: Parse TOML files with tomllib
2. **Validate Settings**: Enforce constraints via Pydantic
3. **Environment Overrides**: Support W2T_* environment variables
4. **Type Safety**: Provide strongly-typed configuration objects

## Public API

### Settings Class

```python
from w2t_bkin.config import Settings, load_settings

# Load from TOML
settings = load_settings("config.toml")

# Access typed configuration
print(settings.project.name)
print(settings.paths.raw_root)
print(settings.video.fps)
```

### Configuration Structure

- `project`: Project metadata (name, n_cameras)
- `paths`: Directory paths (raw_root, intermediate_root, output_root, models_root)
- `session`: Session metadata (id, subject_id, date, experimenter, description, sex, age, genotype)
- `video`: Video processing (pattern, fps, transcode)
- `sync`: Synchronization (ttl_channels, tolerance_ms, drop_frame_max_gap_ms, primary_clock)
- `labels`: Pose labeling (dlc, sleap)
- `facemap`: Facemap configuration (run, roi)
- `nwb`: NWB export (link_external_video, file_name, session_description, lab, institution)
- `qc`: Quality control (generate_report, out)
- `logging`: Logging (level, structured)
- `events`: Events configuration (patterns, format)

## Design Constraints

**Requirements**: FR-10 (Configuration-driven), NFR-10 (Type safety)

**Layer 1 Dependencies**:
- May import: `domain`, `utils`
- No imports from: processing stages, cli

**Validation Rules**:
- `n_cameras`: 1-10
- `video.fps`: > 0
- `video.transcode.crf`: 0-51
- `sync.tolerance_ms`: >= 0
- `ttl_channels.polarity`: "rising" or "falling"
- `logging.level`: DEBUG, INFO, WARNING, ERROR, CRITICAL
- `paths`: Automatically expand ~ and environment variables

## Examples

### Basic TOML Configuration

```toml
[project]
name = "my-experiment"
n_cameras = 5

[paths]
raw_root = "~/data/raw"
output_root = "/mnt/storage/processed"

[video]
fps = 30.0
pattern = "**/*.mp4"

[video.transcode]
enabled = true
codec = "libx264"
crf = 18

[sync]
tolerance_ms = 2.0
primary_clock = "cam0"

[[sync.ttl_channels]]
path = "nidaq/sync.bin"
name = "frame_trigger"
polarity = "rising"

[nwb]
link_external_video = true
session_description = "Behavioral session"
lab = "My Lab"
institution = "My Institution"

[logging]
level = "INFO"
structured = false
```

### Environment Variable Overrides

```bash
# Override project name
export W2T_PROJECT__NAME="override-experiment"

# Override video FPS
export W2T_VIDEO__FPS=60.0

# Override logging level
export W2T_LOGGING__LEVEL=DEBUG

# Override paths
export W2T_PATHS__RAW_ROOT="/custom/path"
```

```python
# Environment variables take precedence
settings = load_settings("config.toml")
assert settings.project.name == "override-experiment"
assert settings.video.fps == 60.0
```

### Programmatic Usage

```python
from w2t_bkin.config import Settings, ProjectConfig, PathsConfig

# Create settings programmatically
settings = Settings(
    project=ProjectConfig(name="test", n_cameras=3),
    paths=PathsConfig(raw_root="data/raw"),
)

# Access with type safety
assert settings.project.n_cameras == 3
assert isinstance(settings.paths.raw_root, Path)
```

### Validation Errors

```python
from pydantic import ValidationError

try:
    # Invalid n_cameras (must be 1-10)
    settings = Settings(project={"n_cameras": 15})
except ValidationError as e:
    print(e)

try:
    # Invalid polarity
    settings = Settings(
        sync={"ttl_channels": [{"polarity": "invalid"}]}
    )
except ValidationError as e:
    print(e)
```

## Testing

### Unit Tests

```bash
pytest tests/unit/test_config.py -v
```

### Test Coverage

- TOML loading (valid/invalid files)
- Environment variable overrides
- Validation rules (n_cameras, fps, polarity, log level)
- Default values
- Path expansion (~ and environment variables)
- Nested configuration access
- Unknown keys rejection

## Usage Patterns

### CLI Integration

```python
def main(config_path: str):
    """CLI entry point."""
    settings = load_settings(config_path)
    
    # Configure logging from settings
    setup_logging(settings.logging.level)
    
    # Use settings in pipeline
    run_pipeline(settings)
```

### Configuration Precedence

1. **Defaults**: Defined in Pydantic models
2. **TOML File**: Overrides defaults
3. **Environment Variables**: Overrides TOML

### Error Handling

```python
from pathlib import Path
from pydantic import ValidationError

def load_with_fallback(config_path: str | None) -> Settings:
    """Load settings with fallback to defaults."""
    try:
        if config_path and Path(config_path).exists():
            return load_settings(config_path)
    except (FileNotFoundError, ValidationError) as e:
        logger.warning(f"Config load failed: {e}, using defaults")
    
    return Settings()  # Use all defaults
```

## Validation Rules Reference

### ProjectConfig

- `name`: str (default: "w2t-bkin-pipeline")
- `n_cameras`: int, 1 <= n <= 10 (default: 5)

### PathsConfig

- `raw_root`: Path (default: "data/raw")
- `intermediate_root`: Path (default: "data/interim")
- `output_root`: Path (default: "data/processed")
- `models_root`: Path (default: "models")
- All paths: Expand ~ and environment variables

### VideoConfig

- `pattern`: str (default: "**/*.mp4")
- `fps`: float, > 0 (default: 30.0)
- `transcode.enabled`: bool (default: False)
- `transcode.codec`: str (default: "libx264")
- `transcode.crf`: int, 0 <= crf <= 51 (default: 18)
- `transcode.preset`: str (default: "medium")
- `transcode.keyint`: int, >= 1 (default: 30)

### SyncConfig

- `ttl_channels`: list[TTLChannelConfig] (default: [])
- `tolerance_ms`: float, >= 0 (default: 2.0)
- `drop_frame_max_gap_ms`: float, >= 0 (default: 100.0)
- `primary_clock`: str (default: "cam0")

### TTLChannelConfig

- `path`: str (default: "")
- `name`: str (default: "")
- `polarity`: "rising" or "falling" (default: "rising")

### LoggingConfig

- `level`: "DEBUG", "INFO", "WARNING", "ERROR", or "CRITICAL" (default: "INFO")
- `structured`: bool (default: False)

## Dependencies

**Internal (Layer 0)**:
- None (config is self-contained)

**External**:
- `pydantic`: Configuration validation
- `tomli` (Python < 3.11) or `tomllib` (Python >= 3.11): TOML parsing

## See Also

- `requirements.md`: Configuration keys specification
- `design.md`: Module breakdown and dependency tree
- `api.md §3.3`: Configuration API
