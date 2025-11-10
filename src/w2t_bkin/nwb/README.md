# NWB Module — Neurodata Without Borders Assembly

## Overview

The `nwb` module assembles the final NWB file from all pipeline stages, incorporating video metadata, synchronization data, and optional pose, facemap, and behavioral event data. This is a Layer 2 module that orchestrates the creation of a standards-compliant NWB file with comprehensive provenance tracking.

**Requirements**: FR-7 (Export NWB), FR-9 (Validation), NFR-1 (Reproducibility), NFR-2 (Idempotence), NFR-3 (Observability), NFR-6 (PyNWB compatibility), NFR-11 (Provenance)

**Design**: design.md §2 (Module Breakdown), §3 (Data Contracts), §11 (Provenance)

**API**: api.md §3.10

## Architecture

```
w2t_bkin.nwb/
├── __init__.py          # Main API: assemble_nwb()
└── README.md            # This file
```

### Dependencies

**Layer 2 Module** — May import:
- `w2t_bkin.config` (Settings, load_settings)
- `w2t_bkin.domain` (Manifest, NWBAssemblyOptions, VideoMetadata, TimestampSeries, PoseTable, FacemapMetrics, Trial, Event, MissingInputError)
- `w2t_bkin.utils` (read_json, write_json, file_hash, get_commit)

**Must NOT import**: Other stage modules (sync, pose, facemap, events, etc.)

### External Dependencies
- `pynwb` — NWB file creation and manipulation
- `h5py` — HDF5 file handling
- `hdmf` — Hierarchical Data Modeling Framework
- `ndx-pose` (optional) — NWB extension for pose data
- `pandas` — Data manipulation for tables

## Public API

### Main Function

```python
def assemble_nwb(
    manifest_path: Path,
    timestamps_dir: Path,
    output_dir: Path,
    pose_dir: Path | None = None,
    facemap_dir: Path | None = None,
    events_dir: Path | None = None,
    options: NWBAssemblyOptions | None = None,
) -> Path:
    """Assemble NWB file from pipeline stage outputs.
    
    Args:
        manifest_path: Path to manifest.json from ingest stage
        timestamps_dir: Directory containing per-camera timestamp CSVs
        output_dir: Directory for NWB output
        pose_dir: Optional directory with harmonized pose data
        facemap_dir: Optional directory with facemap metrics
        events_dir: Optional directory with normalized trials/events
        options: Optional NWB assembly options (uses manifest config if None)
    
    Returns:
        Path to created NWB file
    
    Raises:
        MissingInputError: Required inputs not found
        NWBBuildError: NWB construction failed
    """
```

### Data Contracts

**Input**: `NWBSummary` (returned by `assemble_nwb`)

```python
@dataclass(frozen=True)
class NWBSummary:
    """Summary of NWB assembly results.
    
    Requirements: NFR-3 (Observability)
    """
    session_id: str
    nwb_path: str
    file_size_mb: float
    n_devices: int
    n_image_series: int
    n_timestamps: int
    pose_included: bool
    facemap_included: bool
    trials_included: bool
    events_included: bool
    provenance: dict[str, Any]
    warnings: list[str]
    skipped: bool
```

### Custom Exceptions

```python
class NWBBuildError(Exception):
    """Raised when NWB file construction fails."""
    pass
```

## NWB File Structure

The module creates an NWB file with the following structure:

### Required Components (FR-7)

1. **NWBFile Metadata**
   - `session_id`: From manifest
   - `session_description`: From config or options
   - `session_start_time`: Derived from first timestamp
   - `experimenter`: From config
   - `lab`: From config  
   - `institution`: From config
   - `subject`: Subject metadata (id, sex, age, genotype)

2. **Devices** (5 cameras)
   - One `Device` per camera with:
     - `name`: "Camera_{i}"
     - `description`: Video metadata (codec, fps, resolution)
     - `manufacturer`: "Unknown" (not in source data)

3. **ImageSeries** (5 per session)
   - One `ImageSeries` per camera in `acquisition`:
     - `name`: "VideoCamera{i}"
     - `external_file`: Path(s) to video file(s)
     - `timestamps`: Per-frame timestamps from sync stage
     - `dimension`: [height, width]
     - `device`: Link to corresponding Device
     - `format`: "external"
     - `starting_frame`: [0]

4. **Synchronization TimeSeries**
   - One `TimeSeries` in `processing/sync`:
     - `name`: "SyncTimestamps"
     - `description`: "Per-frame timestamps for all cameras"
     - `data`: Flattened array of all timestamps
     - `timestamps`: Camera indices or frame numbers
     - `unit`: "seconds"

### Optional Components

5. **Pose Data** (FR-5, if `pose_dir` provided)
   - Uses `ndx-pose` extension:
     - `PoseEstimation` container in `processing/behavior`
     - `PoseEstimationSeries` for each keypoint
     - Skeleton definition in metadata
     - Confidence scores preserved

6. **Facemap Metrics** (FR-6, if `facemap_dir` provided)
   - `BehavioralTimeSeries` in `processing/behavior`:
     - One timeseries per metric (pupil_area, motion_energy, etc.)
     - Aligned to session timebase
     - NaN values preserved for missing samples

7. **Trials & Events** (FR-11, if `events_dir` provided)
   - **Trials**: `TimeIntervals` table in `intervals`:
     - Columns: trial_id, start_time, stop_time, phase_first, phase_last, qc_flags
     - Trial duration statistics in metadata
   - **Events**: `Events` table in `processing/behavior`:
     - Columns: time, kind, payload (JSON string)
     - Event count in metadata

### Provenance Metadata (NFR-11)

Embedded in NWB `notes` field or `/processing/provenance`:

```json
{
  "pipeline": "w2t-bkin",
  "git_commit": "abc1234",
  "config_snapshot": { ... },
  "software_versions": {
    "pynwb": "2.x.x",
    "hdmf": "3.x.x",
    "python": "3.10.x"
  },
  "stage_artifacts": {
    "manifest_hash": "sha256:...",
    "sync_summary_hash": "sha256:...",
    "pose_hash": "sha256:...",
    "facemap_hash": "sha256:...",
    "events_hash": "sha256:..."
  },
  "timestamp": "2025-11-10T12:34:56Z"
}
```

## Processing Logic

### 1. Input Validation

- Verify `manifest.json` exists and is valid
- Verify `timestamps_dir` exists with expected CSV files
- Check optional directories (pose, facemap, events) if provided
- Log warnings for missing optional data

### 2. Load Artifacts

- Parse `manifest.json` → `Manifest` domain object
- Load per-camera timestamp CSVs → list of `TimestampSeries`
- Load pose data (if present) → `PoseTable` or skip
- Load facemap metrics (if present) → `FacemapMetrics` or skip
- Load trials/events (if present) → lists of `Trial`/`Event` or skip

### 3. Create NWB File

**Session Metadata**:
- Use manifest `session_id`
- Use config for experimenter, lab, institution
- Derive `session_start_time` from first timestamp

**Devices & ImageSeries**:
- Create one `Device` per camera from manifest videos
- Create one `ImageSeries` per camera:
  - Use `external_file` links (not embedded) per FR-7
  - Attach per-camera timestamps
  - Link to corresponding device

**Sync Data**:
- Create processing module: `/processing/sync`
- Add `TimeSeries` with combined timestamp data
- Include drift statistics from sync_summary.json

**Optional Data**:
- If `pose_dir`: Import pose with ndx-pose extension
- If `facemap_dir`: Create BehavioralTimeSeries
- If `events_dir`: Create TimeIntervals for trials, Events table

**Provenance**:
- Embed config snapshot in notes or processing module
- Record git commit, software versions, artifact hashes

### 4. Write & Validate

- Write NWB file to `output_dir/{session_id}.nwb`
- Compute file size
- Create `nwb_summary.json` with metadata
- Return NWB file path

### 5. Idempotence (NFR-2)

- Check if NWB file already exists with matching provenance
- Compare artifact hashes (manifest, timestamps, optional data)
- Skip if unchanged unless `force=True`
- Log idempotence decision

## Error Handling

| Error Type | Cause | Response |
|------------|-------|----------|
| `MissingInputError` | Required manifest or timestamps missing | Fail fast with clear path message |
| `NWBBuildError` | PyNWB/HDMF error during construction | Fail with diagnostic context |
| `FileNotFoundError` | External video file referenced but not found | Warn, continue (external link can be broken) |
| `ValueError` | Invalid timestamp data (non-monotonic, length mismatch) | Fail with validation error |
| `ImportError` | `ndx-pose` missing but pose data provided | Warn, skip pose data |

## Validation Strategy (FR-9)

The NWB module creates files that should pass `nwbinspector` without critical issues:

1. **Required Metadata**: All required NWB fields populated
2. **Valid References**: Device/ImageSeries links valid
3. **Timestamp Monotonicity**: All timestamps monotonically increasing
4. **Schema Compliance**: Follows NWB 2.x schema
5. **Extension Validity**: If using ndx-pose, validates against extension schema

**Note**: Validation itself is handled by a separate CLI command (`validate`), not this module.

## Configuration

NWB assembly is controlled by config section `[nwb]`:

```toml
[nwb]
link_external_video = true          # Use external_file (not embedded)
file_name = ""                       # Auto-generated if empty: {session_id}.nwb
session_description = "Behavioral recording session"
lab = "Neuroscience Lab"
institution = "University"
```

Can be overridden via `NWBAssemblyOptions` argument.

## Observability (NFR-3)

### Structured Logging

```python
logger.info("Assembling NWB for session: {session_id}")
logger.info("Loaded {n} cameras from manifest")
logger.info("Loaded timestamps: {n} frames per camera")
logger.warning("Pose data not found, skipping")
logger.info("NWB file created: {nwb_path} ({size_mb} MB)")
```

### Summary JSON

`nwb_summary.json` written alongside NWB file:

```json
{
  "session_id": "session_001",
  "nwb_path": "/path/to/session_001.nwb",
  "file_size_mb": 12.34,
  "n_devices": 5,
  "n_image_series": 5,
  "n_timestamps": 54000,
  "pose_included": true,
  "facemap_included": false,
  "trials_included": true,
  "events_included": true,
  "provenance": { ... },
  "warnings": [
    "Facemap data not found"
  ],
  "skipped": false
}
```

## Testing Strategy

### Unit Tests

- **NWB Creation**: Verify file structure with minimal inputs
- **Devices & ImageSeries**: Validate per-camera devices and series
- **Timestamps**: Ensure correct timestamp embedding
- **Optional Data**: Test pose, facemap, events integration individually
- **Provenance**: Verify config snapshot and git commit embedded
- **Idempotence**: Verify skip behavior when inputs unchanged
- **Error Handling**: Test missing inputs, malformed data
- **Warnings**: Verify warnings for missing optional data

### Integration Tests

- **Full Pipeline**: ingest → sync → nwb (with and without optional stages)
- **PyNWB Compatibility**: Verify file is readable by pynwb.NWBHDF5IO
- **nwbinspector**: Run inspector and verify no critical issues (in validation tests)

## Usage Examples

### Minimal (Core Only)

```python
from w2t_bkin.nwb import assemble_nwb

nwb_path = assemble_nwb(
    manifest_path=Path("data/interim/manifest.json"),
    timestamps_dir=Path("data/interim/sync"),
    output_dir=Path("data/processed"),
)
# Creates: data/processed/session_001.nwb
```

### With Optional Data

```python
from w2t_bkin.domain import NWBAssemblyOptions

nwb_path = assemble_nwb(
    manifest_path=Path("data/interim/manifest.json"),
    timestamps_dir=Path("data/interim/sync"),
    output_dir=Path("data/processed"),
    pose_dir=Path("data/interim/pose"),
    facemap_dir=Path("data/interim/facemap"),
    events_dir=Path("data/interim/events"),
    options=NWBAssemblyOptions(
        link_external_video=True,
        session_description="Custom description",
        lab="My Lab",
        institution="My University",
    ),
)
```

### Idempotent Re-run

```python
# First run: creates NWB
nwb_path = assemble_nwb(manifest_path, timestamps_dir, output_dir)

# Second run: skips if inputs unchanged
nwb_path = assemble_nwb(manifest_path, timestamps_dir, output_dir)
# Logs: "NWB file up-to-date, skipping (use force=True to rebuild)"

# Force rebuild
nwb_path = assemble_nwb(manifest_path, timestamps_dir, output_dir, force=True)
```

## Implementation Notes

### External Video Links

Per FR-7 and OOS-3, videos are linked externally (not embedded):

```python
image_series = ImageSeries(
    name=f"VideoCamera{camera_id}",
    external_file=[str(video_path)],  # Relative or absolute
    format="external",
    timestamps=timestamps,
    device=device,
)
```

### Timestamp Alignment

All timestamps must be in the same session timebase (handled by sync stage). NWB module verifies:
- All cameras have same number of timestamps (or documents differences)
- Timestamps are monotonically increasing
- Start times are aligned (or offset recorded)

### Pose Extension

If pose data is present, requires `ndx-pose`:

```bash
pip install ndx-pose
```

If not installed, pose data is skipped with a warning.

### Memory Efficiency

For large sessions:
- Timestamps loaded incrementally per camera
- External video links avoid loading video data
- Pose/facemap data streamed if possible

## Future Enhancements

- Streaming NWB writing for very large sessions (Design §14)
- Incremental updates (append trials without rebuilding)
- Compression options for embedded data
- Custom NWB extensions for lab-specific metadata

## References

- **NWB Specification**: https://nwb-schema.readthedocs.io/
- **PyNWB Documentation**: https://pynwb.readthedocs.io/
- **ndx-pose Extension**: https://github.com/rly/ndx-pose
- **nwbinspector**: https://nwbinspector.readthedocs.io/
