# Facemap Module — Facial Metrics Import & Computation

## Layer 2 Processing Stage

Import or compute facial motion metrics (pupil area, motion energy, etc.) from Facemap outputs or raw face videos and align to the session timebase.

## Overview

The `facemap` module is responsible for:

1. **Metrics Import** — Load pre-computed Facemap outputs (.npy format)
2. **Optional Computation** — Compute metrics from face video if configured
3. **Timebase Alignment** — Align facial metrics to session timestamps
4. **Quality Validation** — Detect missing samples, validate metric ranges
5. **Output Generation** — Emit Parquet table with time-aligned metrics and summary JSON

This module is optional (NFR-7) and pluggable — it can import precomputed results or run inference when enabled.

## Requirements

- **FR-6**: Import or compute facial metrics aligned to session timebase
- **Design §3.4**: Wide table format with `time` + metric columns
- **Design §6**: Handle missing samples as NaN, validate metric ranges
- **NFR-2**: Idempotent re-runs (skip if output exists)
- **NFR-3**: Emit facemap_summary.json with statistics
- **NFR-7**: Pluggable optional stage
- **NFR-11**: Capture provenance (model hash, Facemap version)

## Scope

### In Scope

- Import Facemap .npy outputs (motion SVD, pupil tracking)
- Optional: Invoke Facemap for computation from face video
- Align metrics to per-camera timestamps from sync stage
- Detect and report missing/invalid samples
- Generate wide-format Parquet table (time, pupil_area, motion_energy, ...)
- Preserve NaN for missing values
- Record model hash and Facemap version for provenance

### Out of Scope

- Custom ROI definition (uses configuration)
- Multi-animal face tracking
- Real-time streaming metrics

## Responsibilities

1. **Validate Inputs** — Check for Facemap file existence or face video availability
2. **Import Metrics** — Parse Facemap .npy arrays
3. **Optional Computation** — Run Facemap inference if configured
4. **Timebase Alignment** — Match frame indices to session timestamps
5. **Quality Checks** — Flag excessive missing data or out-of-range values
6. **Output Writing** — Write Parquet table and JSON summary

## Public API

### `compute_facemap`

```python
def compute_facemap(
    face_video: Path | str,
    output_dir: Path | str,
    model_path: Path | str | None = None,
    timestamps_dir: Path | str | None = None,
    roi: dict[str, Any] | None = None,
    force: bool = False,
) -> FacemapSummary:
    """Import or compute facial metrics aligned to session timebase.
    
    Args:
        face_video: Path to face camera video or Facemap .npy output
        output_dir: Directory for metrics table and summary
        model_path: Optional path to Facemap model weights
        timestamps_dir: Optional directory with timestamp CSVs for alignment
        roi: Optional region of interest specification
        force: Force recomputation even if output exists
        
    Returns:
        FacemapSummary with statistics and metadata
        
    Raises:
        MissingInputError: When face video not found
        FacemapFormatError: When Facemap output format invalid
        TimestampAlignmentError: When timestamp alignment fails
        MetricsRangeError: When metrics outside expected ranges
    """
```

### `import_facemap_metrics`

```python
def import_facemap_metrics(
    facemap_file: Path | str,
    output_dir: Path | str,
    timestamps_dir: Path | str | None = None,
    force: bool = False,
) -> FacemapSummary:
    """Import pre-computed Facemap metrics.
    
    Args:
        facemap_file: Path to Facemap .npy output
        output_dir: Directory for harmonized metrics table
        timestamps_dir: Optional directory with timestamp CSVs
        force: Force re-import even if output exists
        
    Returns:
        FacemapSummary with statistics and metadata
        
    Raises:
        MissingInputError: When facemap file not found
        FacemapFormatError: When .npy format invalid
        TimestampAlignmentError: When alignment fails
    """
```

## Configuration Keys

From `requirements.md` and `design.md`:

```toml
[facemap]
run = false  # Whether to compute or just import
roi = { x = 100, y = 100, width = 400, height = 300 }
model = "models/facemap_model.pt"  # Optional model path
```

## Data Flow

```text
Input (Facemap .npy OR face video)
    ↓
Parse/Compute Metrics (motion SVD, pupil tracking)
    ↓
Align to Session Timebase (via timestamps from sync)
    ↓
Validate Metrics (range checks, missing data)
    ↓
Write Parquet Table (time, pupil_area, motion_energy, ...)
    ↓
Generate Summary JSON (coverage, statistics, provenance)
```

## Output Structure

### Facemap Metrics Table (Parquet)

Columns:
- `time` (float): Session timebase timestamp in seconds
- `pupil_area` (float): Pupil area in pixels (NaN if missing)
- `motion_energy` (float): Motion energy metric (NaN if missing)
- `blink` (int): Blink detection flag (0/1)
- Additional metrics depending on Facemap configuration

### Facemap Summary JSON

```json
{
  "session_id": "mouse1_d2",
  "source_type": "imported",
  "statistics": {
    "total_samples": 1800,
    "missing_samples": 12,
    "coverage_ratio": 0.993,
    "mean_pupil_area": 105.3,
    "mean_motion_energy": 0.42,
    "metrics": ["pupil_area", "motion_energy", "blink"]
  },
  "timebase_alignment": {
    "sync_applied": true,
    "camera_id": "cam_face"
  },
  "model_info": {
    "facemap_version": "1.0.2",
    "model_hash": "abc123...",
    "roi": {"x": 100, "y": 100, "width": 400, "height": 300}
  },
  "warnings": [],
  "skipped": false,
  "output_path": "data/interim/session/facemap/facemap_metrics.parquet"
}
```

## Error Handling

| Exception | Cause | Response |
|-----------|-------|----------|
| `MissingInputError` | Facemap file or face video not found | Fail fast with clear path message |
| `FacemapFormatError` | Invalid .npy structure or corrupt file | Abort with format diagnostics |
| `TimestampAlignmentError` | Frame count mismatch with sync data | Abort with frame count details |
| `MetricsRangeError` | Metrics outside physically plausible ranges | Warn or abort based on severity |
| `ComputationError` | Facemap inference fails | Abort with traceback |

All exceptions include file paths and diagnostic context for debugging.

## Testing Strategy

### Unit Tests

- Parse Facemap .npy arrays correctly
- Validate metric column lengths
- Detect missing samples (NaN values)
- Validate metric ranges (pupil area > 0, motion energy [0,1])
- Align metrics to session timestamps
- Handle frame count mismatches
- Generate correct summary statistics
- Idempotent re-runs (skip existing outputs)
- Force flag overrides skip logic

### Integration Tests

- Import real Facemap output sample
- Compute metrics from short face video
- Align to sync module timestamps
- Validate Parquet output schema
- NWB assembly includes facemap metrics

### Property Tests

- Coverage ratio in [0,1]
- Pupil area non-negative
- Motion energy in [0,1]
- Time series monotonic increasing

## Dependencies

### Config Module

- `Settings`: Pipeline configuration
- `FacemapConfig`: Facemap-specific settings (run, roi, model)

### Domain Module

- `FacemapMetrics`: Wide table with time + metric columns
- `MissingInputError`: File not found exception

### Utils Module

- `read_json()`: Load metadata
- `write_json()`: Write summary
- `file_hash()`: Model provenance
- `get_commit()`: Git commit hash

## Performance Considerations

- **Memory**: Stream large .npy arrays instead of loading entirely
- **Computation**: Facemap inference parallelizable per ROI
- **I/O**: Write Parquet in chunks for large sessions

## Idempotence (NFR-2)

- Check if `facemap_metrics.parquet` exists in output_dir
- Compare input file hash with metadata
- Skip computation if output fresh and input unchanged
- Override with `force=True` flag

## Provenance (NFR-11)

Captured in summary JSON:
- Facemap version (from package metadata or .npy header)
- Model hash (if model file used)
- ROI configuration
- Input file hash
- Processing timestamp
- Git commit hash

## Example Usage

### Import Pre-computed Metrics

```python
from w2t_bkin.facemap import import_facemap_metrics
from pathlib import Path

summary = import_facemap_metrics(
    facemap_file=Path("data/raw/session/facemap_output.npy"),
    output_dir=Path("data/interim/session/facemap"),
    timestamps_dir=Path("data/interim/session/sync"),
)

print(f"Imported {summary.statistics['total_samples']} samples")
print(f"Coverage: {summary.statistics['coverage_ratio']:.1%}")
```

### Compute from Face Video

```python
from w2t_bkin.facemap import compute_facemap

summary = compute_facemap(
    face_video=Path("data/raw/session/cam_face.mp4"),
    output_dir=Path("data/interim/session/facemap"),
    model_path=Path("models/facemap_model.pt"),
    timestamps_dir=Path("data/interim/session/sync"),
    roi={"x": 100, "y": 100, "width": 400, "height": 300},
)
```

## CLI Integration

```bash
# Import pre-computed metrics
w2t-bkin facemap import data/raw/session/facemap_output.npy \
    --output data/interim/session/facemap \
    --timestamps data/interim/session/sync

# Compute from video
w2t-bkin facemap compute data/raw/session/cam_face.mp4 \
    --output data/interim/session/facemap \
    --model models/facemap_model.pt \
    --roi-x 100 --roi-y 100 --roi-width 400 --roi-height 300
```

## Architecture Notes

- **Layer 2 Module**: May only import from `config`, `domain`, `utils`
- **No Cross-Stage Imports**: Cannot import from `pose`, `sync`, `events`, etc.
- **File-Based Contracts**: Consumes timestamps via CSV files, not module imports
- **Pluggable**: Entire module optional based on configuration

## Future Enhancements

- Multi-region tracking (multiple ROIs per face)
- Blink detection refinement
- Whisker tracking metrics
- Real-time streaming mode
- GPU acceleration for computation
