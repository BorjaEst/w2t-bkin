# Sync Module — Timestamp Computation & Synchronization

## Layer 2 Processing Stage

Parse TTL edges or frame counters from hardware synchronization logs to derive per-frame timestamps for each camera in a common session timebase. Detect and report dropped frames, duplicates, and inter-camera drift with summary statistics.

## Overview

The `sync` module is responsible for:

1. **Timestamp Derivation** — Parse TTL edges or frame counters from sync hardware logs
2. **Timebase Establishment** — Establish a common session timebase using a primary clock
3. **Frame Mapping** — Map each video frame to a session timestamp
4. **Quality Metrics** — Detect dropped frames, duplicates, and inter-camera drift
5. **Output Generation** — Emit per-camera timestamp CSVs and a sync summary JSON

This module is critical for aligning multi-camera recordings and enabling downstream temporal analysis of pose, facemap, and behavioral events.

## Requirements

- **FR-2**: Compute per-frame timestamps for each camera in a common session timebase
- **FR-3**: Detect and report dropped frames, duplicates, and inter-camera drift with summary statistics
- **Design §3.2**: Timestamp CSV with strict monotonic increase; length equals frame count
- **Design §6**: Raise DriftThresholdExceeded when drift exceeds configured tolerance
- **Design §8**: Use streaming parsing for large TTL logs (avoid loading entire file into memory)

## Public API

### `compute_timestamps`

```python
def compute_timestamps(
    manifest_path: Path | str,
    output_dir: Path | str,
    primary_clock: str | None = None,
) -> tuple[Path, Path]:
    """Compute per-frame timestamps and drift/drop statistics.

    Args:
        manifest_path: Path to manifest.json from ingest stage
        output_dir: Directory for timestamp CSVs and sync summary
        primary_clock: Camera ID for primary clock (default: from config or "cam0")

    Returns:
        Tuple of (timestamps_dir, sync_summary_path)

    Raises:
        FileNotFoundError: If manifest or sync files not found
        TimestampMismatchError: If timestamps non-monotonic or length mismatch
        DriftThresholdExceeded: If inter-camera drift exceeds tolerance
        ValueError: If manifest invalid or sync data corrupted
    """
```

## Design Constraints

### Architecture

- **Layer 2** module (may import: `config`, `domain`, `utils`)
- **No cross-stage imports** (no imports from `ingest`, `pose`, etc.)
- **File-based contracts** — consumes manifest.json, produces CSV + JSON outputs

### Guarantees

- **Strictly monotonic timestamps** — enforced by domain.TimestampSeries validation
- **Absolute paths** — all file paths resolved to absolute
- **Deterministic outputs** — same inputs produce identical timestamps (NFR-1)
- **Idempotent** — re-running with same inputs is a no-op unless forced (NFR-2)

### Performance

- **Streaming parsing** — TTL logs processed with iterators (no full memory load)
- **Parallelizable** — per-camera timestamp derivation can run in parallel
- **Optional caching** — hashed sync files + config snapshot for recomputation skip

## Examples

### Basic Usage

```python
from w2t_bkin.sync import compute_timestamps

# After ingest has created manifest.json
timestamps_dir, summary_path = compute_timestamps(
    manifest_path="data/interim/session_001/manifest.json",
    output_dir="data/interim/session_001/sync",
)

# timestamps_dir contains:
#   timestamps_cam0.csv
#   timestamps_cam1.csv
#   ...
#   timestamps_cam4.csv
# summary_path points to sync_summary.json
```

### Custom Primary Clock

```python
from w2t_bkin.sync import compute_timestamps

# Use cam2 as the session timebase reference
timestamps_dir, summary_path = compute_timestamps(
    manifest_path="data/interim/session_001/manifest.json",
    output_dir="data/interim/session_001/sync",
    primary_clock="cam2",  # Override config default
)
```

### Manifest Consumption

```python
from w2t_bkin.ingest import build_manifest
from w2t_bkin.sync import compute_timestamps
from w2t_bkin.config import load_settings

settings = load_settings("config.toml")

# Stage 1: Discover assets
manifest_path = build_manifest(
    session_dir="data/raw/session_001",
    settings=settings,
    output_dir="data/interim/session_001",
)

# Stage 2: Compute timestamps
timestamps_dir, summary_path = compute_timestamps(
    manifest_path=manifest_path,
    output_dir="data/interim/session_001/sync",
)
```

## Timestamp Computation

### TTL Edge Parsing

TTL (Transistor-Transistor Logic) sync hardware emits digital pulses (edges) that mark frame acquisition events. The module supports:

- **Rising edge detection** (0→1 transition, polarity="rising")
- **Rising edge detection** (1→0 transition, polarity="falling")
- **Configurable polarity** per TTL channel (from config.sync.ttl_channels)

### Frame Counter Parsing

Alternative to TTL edges, some systems emit frame counter logs:

- Monotonically increasing frame numbers
- Timestamps in hardware clock units
- Requires mapping to session timebase

### Timebase Derivation

1. **Primary clock selection** — Identify primary camera/TTL channel (config.sync.primary_clock)
2. **Zero-point establishment** — First TTL edge or frame counter defines t=0
3. **Per-camera mapping** — Align each camera's TTL edges to session timebase
4. **Drift computation** — Measure cumulative deviation between cameras

### Timestamp CSV Format

Each camera gets a dedicated CSV file:

```csv
frame_index,timestamp
0,0.0000
1,0.0333
2,0.0667
3,0.1000
```

- **frame_index**: 0-based frame number (integer)
- **timestamp**: Session time in seconds (float, microsecond precision)
- **Monotonic**: Each timestamp > previous timestamp (strictly increasing)
- **Length**: Row count equals decoded frame count from manifest

## Quality Metrics

### Drift Detection

**Drift** is the cumulative temporal deviation between cameras' timebases.

Computed metrics (in `sync_summary.json`):

- `max_drift_ms`: Maximum drift observed across any camera pair
- `mean_drift_ms`: Average drift across all camera pairs
- `std_drift_ms`: Standard deviation of drift distribution

**Threshold**: If `max_drift_ms > config.sync.tolerance_ms`, raise `DriftThresholdExceeded`

### Dropped Frame Detection

A **dropped frame** is a missing frame in the expected sequence, indicated by:

- TTL edge gap > `config.sync.drop_frame_max_gap_ms`
- Frame counter jump > 1

Counted per camera and reported in `sync_summary.json`.

### Duplicate Frame Detection

A **duplicate frame** occurs when:

- Multiple TTL edges map to same timestamp (within precision tolerance)
- Frame counter repeats

Counted per camera and reported in `sync_summary.json`.

## Output Format

### Timestamp CSV (per camera)

```csv
frame_index,timestamp
0,0.0000
1,0.0333
2,0.0667
```

Filename pattern: `timestamps_cam{camera_id}.csv`

### Sync Summary JSON

```json
{
  "session_id": "session_001",
  "primary_clock": "cam0",
  "per_camera_stats": {
    "cam0": {
      "n_frames": 1000,
      "duration_sec": 33.333,
      "dropped_frames": 0,
      "duplicate_frames": 0,
      "mean_fps": 30.0
    },
    "cam1": { "...": "..." }
  },
  "drift_stats": {
    "max_drift_ms": 1.2,
    "mean_drift_ms": 0.4,
    "std_drift_ms": 0.3
  },
  "drop_counts": {
    "cam0": 0,
    "cam1": 2,
    "cam2": 0,
    "cam3": 1,
    "cam4": 0
  },
  "warnings": [
    "cam1: 2 dropped frames detected",
    "cam3: 1 dropped frame detected"
  ],
  "provenance": {
    "git_commit": "a1b2c3d",
    "timestamp": "2025-11-09T12:34:56Z"
  }
}
```

## Testing

### Unit Test Coverage

The sync module has comprehensive unit tests (`tests/unit/test_sync.py`):

1. **Timestamp Computation** (FR-2, MR-1):

   - Parse TTL edges (rising/falling polarity)
   - Parse frame counters
   - Map frames to timestamps using primary clock
   - Handle multiple cameras (5 cameras)

2. **Drop/Duplicate Detection** (FR-3, MR-2):

   - Detect dropped frames (gaps > threshold)
   - Detect duplicate frames
   - Compute inter-camera drift metrics
   - Drift statistics (max, mean, std)

3. **Output Generation** (MR-3):

   - Emit timestamp CSVs with correct format
   - Emit sync_summary.json with complete stats
   - Validate CSV headers and data types

4. **Monotonic Validation** (M-NFR-1, Design §3.2):

   - Strictly increasing timestamps
   - No negative values
   - Microsecond precision tolerance

5. **Error Handling** (Design §6):

   - `DriftThresholdExceeded` when drift > tolerance
   - `TimestampMismatchError` for non-monotonic timestamps
   - `TimestampMismatchError` for frame count mismatch
   - `MissingInputError` for absent sync files

6. **Edge Cases**:
   - Empty sync files
   - Missing TTL channels (fallback patterns)
   - Primary clock selection (config override)
   - Absolute path resolution
   - Relative input paths converted to absolute

### Property-Based Tests

The module also has property tests (`tests/property/test_invariants.py`):

- **Monotonicity invariant**: All timestamps strictly increasing
- **Non-negativity invariant**: All timestamps >= 0.0
- **Frame count consistency**: Timestamp count matches video frame count

### Integration Tests

End-to-end integration tests (`tests/integration/test_pipeline_e2e.py`):

- **Ingest → Sync flow**: Manifest consumption, timestamp generation
- **Drift threshold enforcement**: Pipeline aborts when drift exceeds tolerance
- **Multi-camera validation**: 5-camera sync quality metrics

## Usage Patterns

### CLI Integration

The sync module is invoked via CLI subcommand:

```bash
# After running ingest
w2t-bkin sync \
  --manifest data/interim/session_001/manifest.json \
  --output data/interim/session_001/sync \
  --primary-clock cam0
```

### Programmatic Discovery

```python
from pathlib import Path
from w2t_bkin.sync import compute_timestamps

# Discover manifest from session directory
session_dir = Path("data/interim/session_001")
manifest_path = session_dir / "manifest.json"

if manifest_path.exists():
    timestamps_dir, summary_path = compute_timestamps(
        manifest_path=manifest_path,
        output_dir=session_dir / "sync",
    )
    print(f"Timestamps written to: {timestamps_dir}")
    print(f"Summary written to: {summary_path}")
else:
    print("Run 'w2t-bkin ingest' first to generate manifest")
```

### Error Handling

```python
from w2t_bkin.sync import compute_timestamps
from w2t_bkin.domain import DriftThresholdExceeded, TimestampMismatchError

try:
    timestamps_dir, summary_path = compute_timestamps(
        manifest_path="data/interim/session_001/manifest.json",
        output_dir="data/interim/session_001/sync",
    )
except DriftThresholdExceeded as e:
    print(f"Sync quality insufficient: {e}")
    print("Consider adjusting config.sync.tolerance_ms")
except TimestampMismatchError as e:
    print(f"Timestamp validation failed: {e}")
    print("Check sync hardware logs for corruption")
except FileNotFoundError as e:
    print(f"Input not found: {e}")
    print("Run 'w2t-bkin ingest' first")
```

## Dependencies

### Config Module

- `Settings`: Complete pipeline configuration
- `SyncConfig`: Sync-specific settings (TTL channels, tolerance, primary clock)
- `TTLChannelConfig`: Per-channel configuration (path, name, polarity)

### Domain Module

- `Manifest`: Session manifest from ingest stage
- `TimestampSeries`: Per-camera frame timestamps (with monotonic validation)
- `SyncSummary`: Drift/drop statistics summary

### Utils Module

- `read_json()`: Load manifest.json
- `write_json()`: Write sync_summary.json
- `write_csv()`: Write timestamp CSVs
- `get_commit()`: Git commit hash for provenance
- `time_block()`: Performance timing

## Error Handling Details

### DriftThresholdExceeded

**Cause**: Inter-camera drift exceeds `config.sync.tolerance_ms`

**Response**: Abort sync stage with diagnostics (Design §6)

**Example**:

```python
DriftThresholdExceeded: Maximum drift 5.2ms exceeds tolerance 2.0ms
  cam0 vs cam1: 5.2ms
  cam0 vs cam2: 1.1ms
```

### TimestampMismatchError

**Cause**: Non-monotonic timestamps or frame count mismatch

**Response**: Abort sync stage with diagnostics (Design §6)

**Examples**:

```python
# Non-monotonic
TimestampMismatchError: Timestamps not strictly monotonic at frame 42
  cam0: 1.3999 -> 1.3998 (violation)

# Length mismatch
TimestampMismatchError: Timestamp count (999) != frame count (1000)
  cam2: expected 1000 frames, got 999 timestamps
```

### MissingInputError

**Cause**: Required sync files absent from manifest

**Response**: Fail fast, log path, suggest config key (Design §6)

**Example**:

```python
MissingInputError: No sync files found in manifest
  Expected: TTL channels configured in config.sync.ttl_channels
  Or: Fallback patterns (sync*.bin, ttl*.bin)
  Suggestion: Check config.sync.ttl_channels[].path
```

## Performance Characteristics

### Streaming Parsing

TTL logs can be very large (hundreds of MB). The module uses **streaming iterators** to parse sync files without loading entire contents into memory:

```python
def parse_ttl_edges(ttl_path: Path) -> Iterator[float]:
    """Stream TTL edges without full memory load (Design §8)."""
    with open(ttl_path, 'rb') as f:
        while chunk := f.read(8192):
            # Parse edges incrementally
            yield from extract_edges(chunk)
```

### Parallelization Strategy

Per-camera timestamp derivation is **embarrassingly parallel**. Future optimization can distribute computation:

```python
from concurrent.futures import ProcessPoolExecutor

with ProcessPoolExecutor(max_workers=5) as executor:
    futures = {
        executor.submit(compute_camera_timestamps, cam_id, ttl_path)
        for cam_id, ttl_path in sync_files.items()
    }
    results = [f.result() for f in futures]
```

### Caching

Optional caching based on hashed sync files + config snapshot:

```python
from w2t_bkin.utils import file_hash

cache_key = file_hash(ttl_path) + file_hash(config_path)
if cache_exists(cache_key):
    return load_cached_timestamps(cache_key)
```

## Implementation Notes

### Monotonic Enforcement

The `domain.TimestampSeries` dataclass enforces strict monotonicity:

```python
@dataclass(frozen=True)
class TimestampSeries:
    frame_index: list[int]
    timestamp_sec: list[float]

    def __post_init__(self) -> None:
        # Validate strictly increasing
        for i in range(1, len(self.timestamp_sec)):
            if self.timestamp_sec[i] <= self.timestamp_sec[i - 1]:
                raise ValueError(f"Non-monotonic at index {i}")
```

This ensures **all timestamp outputs are validated** before being written to CSV.

### Primary Clock Selection

Priority order:

1. Function argument `primary_clock` (highest priority)
2. Config setting `config.sync.primary_clock`
3. Default fallback `"cam0"`

### Absolute Path Resolution

All file paths (manifest, sync files, output directory) are resolved to absolute:

```python
manifest_path = Path(manifest_path).resolve()
output_dir = Path(output_dir).resolve()
```

This ensures reproducibility and eliminates relative path ambiguity (NFR-1).

## See Also

- **Ingest Module** (`src/w2t_bkin/ingest/`) — Upstream stage producing manifest.json
- **NWB Module** (`src/w2t_bkin/nwb/`) — Downstream consumer of timestamps
- **Design Document** (`design.md`) — Architecture and data contracts
- **Requirements** (`requirements.md`) — FR-2, FR-3 specifications
- **API Reference** (`api.md`) — Module interface specification
