---
post_title: "Module README — pose"
author1: "Project Team"
post_slug: "readme-pose"
microsoft_alias: "na"
featured_image: "/assets/og.png"
categories: ["docs", "pipeline"]
tags: ["pose", "deeplabcut", "sleap", "harmonization"]
ai_note: "Generated as module documentation."
summary: "Documentation for the pose module - import and harmonize pose estimation outputs to canonical schema."
post_date: "2025-11-10"
---

## Overview

The `pose` module provides optional pose estimation integration for the W2T Body Kinematics pipeline. When enabled via configuration, it imports pose tracking results from DeepLabCut (DLC) and/or SLEAP, harmonizes them to a canonical skeleton representation, and aligns them to the session timebase.

## Scope

- Import pose estimation results from DLC (.h5, .csv) and SLEAP (.slp, .h5) formats
- Harmonize heterogeneous keypoint names to a canonical skeleton schema
- Align pose timestamps to the session timebase using sync stage outputs
- Preserve confidence scores for downstream quality assessment
- Generate harmonized pose tables in Parquet format
- Support both precomputed results and inference-ready configurations

## Responsibilities

- Parse manifest to identify pose inputs (files or models)
- Load and validate pose outputs from DLC/SLEAP
- Map keypoint names using configurable skeleton mappings
- Interpolate or align timestamps to session timebase
- Validate confidence score ranges and data integrity
- Generate pose summary with statistics (coverage, confidence distributions)
- Export harmonized pose tables for NWB assembly

## Key Features

### Optional Processing

- Enabled/disabled via `labels.dlc.model` or `labels.sleap.model` configuration
- When disabled, the stage is a no-op with clear logging
- Pipeline operates without pose data if tracking is not required

### Format Support

- **DeepLabCut**: H5 format (primary), CSV fallback
- **SLEAP**: Native .slp files, H5 exports
- Extensible architecture for future pose estimation frameworks

### Skeleton Harmonization

- Configurable keypoint mapping (e.g., "nose" → "snout", "left_ear" → "ear_L")
- Canonical schema with consistent naming across tools
- Metadata preservation (original names, tool versions, model hashes)

### Timebase Alignment

- Uses sync stage timestamp CSVs for frame-to-time mapping
- Handles dropped frames and timing gaps
- Preserves original frame indices for traceability

### Quality Assurance

- Confidence score validation (0.0-1.0 range)
- Missing keypoint detection
- Low-confidence frame flagging
- Coverage statistics per keypoint

## Public API

### Functions

#### `harmonize_pose(input_path, format, output_dir, skeleton_map=None, timestamps_dir=None) -> pose_summary`

**Purpose**: Import and harmonize pose estimation outputs to canonical schema.

**Parameters**:

- `input_path` (Path): Path to pose estimation output file (DLC .h5 or SLEAP .slp)
- `format` (str): Source format ("dlc" or "sleap")
- `output_dir` (Path): Directory for harmonized pose tables
- `skeleton_map` (Optional[dict]): Keypoint name mapping (source → canonical)
- `timestamps_dir` (Optional[Path]): Directory containing timestamp CSVs from sync stage

**Returns**:

- `PoseSummary`: Summary object with statistics and file references

**Dependencies**:

- `w2t_bkin.domain.PoseTable`, `PoseSample`
- `w2t_bkin.utils`

**Raises**:

- `MissingInputError`: Pose file or timestamps not found
- `PoseFormatError`: Invalid or corrupted pose file
- `SkeletonMappingError`: Unmapped keypoints in source data

## Configuration Keys

```toml
[labels.dlc]
model = "models/dlc_model_snapshot-100000"  # Path to DLC model (enables DLC import)
run_inference = false                       # Whether to run inference or import existing

[labels.sleap]
model = "models/sleap_model.zip"            # Path to SLEAP model
run_inference = false                       # Whether to run inference or import existing

[pose]
skeleton_map_path = "config/skeleton_map.json"  # Optional custom mapping
confidence_threshold = 0.1                       # Minimum confidence for QC warnings
```

## Data Flow

```
manifest.json + pose files → harmonize_pose() → data/interim/<session>/pose/
                                                → pose_harmonized.parquet
                                                → pose_summary.json
                                                → pose_metadata.json
```

## Output Structure

### Harmonized Pose Table (Parquet)

- Location: `data/interim/<session>/pose/pose_harmonized.parquet`
- Schema:
  - `time` (float): Session timestamp in seconds
  - `keypoint` (str): Canonical keypoint name
  - `x_px` (float): X coordinate in pixels
  - `y_px` (float): Y coordinate in pixels
  - `confidence` (float): Tracking confidence [0.0, 1.0]
  - `frame_index` (int): Original frame index for traceability
  - `source` (str): Original tool ("dlc" or "sleap")

### Pose Summary JSON

```json
{
  "session_id": "session_001",
  "timestamp": "2025-11-10T12:00:00Z",
  "source_format": "dlc",
  "source_file": "/data/raw/session_001/pose_dlc.h5",
  "model_hash": "abc123def456",
  "skeleton": {
    "canonical_keypoints": [
      "snout",
      "ear_L",
      "ear_R",
      "spine1",
      "spine2",
      "tail_base"
    ],
    "mapping_applied": true,
    "unmapped_keypoints": []
  },
  "statistics": {
    "total_frames": 18000,
    "keypoints_per_frame": 6,
    "mean_confidence": 0.87,
    "median_confidence": 0.92,
    "low_confidence_frames": 234,
    "missing_keypoints": 12,
    "coverage_by_keypoint": {
      "snout": 0.99,
      "ear_L": 0.98,
      "ear_R": 0.97
    }
  },
  "timebase_alignment": {
    "sync_applied": true,
    "timestamp_source": "data/interim/session_001/sync/timestamps_cam0.csv",
    "dropped_frames_handled": 3
  },
  "warnings": [],
  "errors": []
}
```

### Pose Metadata JSON

```json
{
  "skeleton": {
    "canonical_keypoints": [
      "snout",
      "ear_L",
      "ear_R",
      "spine1",
      "spine2",
      "tail_base"
    ],
    "edges": [
      ["snout", "spine1"],
      ["spine1", "spine2"],
      ["spine2", "tail_base"]
    ],
    "symmetry_pairs": [["ear_L", "ear_R"]]
  },
  "source_tool": "deeplabcut",
  "source_version": "2.3.5",
  "model_path": "models/dlc_model_snapshot-100000",
  "model_hash": "abc123def456",
  "training_iterations": 100000,
  "original_keypoint_names": ["bodypart1", "bodypart2", "bodypart3"]
}
```

## Error Handling

| Error Type                | Cause                           | Response                                   |
| ------------------------- | ------------------------------- | ------------------------------------------ |
| `MissingInputError`       | Pose file not found             | Fail fast with path details                |
| `PoseFormatError`         | Corrupted or unsupported format | Log format details, suggest tool version   |
| `SkeletonMappingError`    | Unmapped keypoints              | List unmapped names, suggest config update |
| `TimestampAlignmentError` | Frame count mismatch with sync  | Warn or fail based on severity             |
| `ConfidenceRangeError`    | Confidence outside [0,1]        | Normalize or fail based on config          |

## Testing Strategy

### Unit Tests

- DLC H5 file parsing and validation
- SLEAP file parsing and validation
- Skeleton mapping logic (canonical name resolution)
- Confidence score validation and filtering
- Timestamp alignment with dropped frames
- Summary statistics computation

### Integration Tests

- End-to-end harmonization with real DLC/SLEAP files
- Timebase alignment with sync outputs
- Error handling with malformed inputs

## Dependencies

**Internal**:

- `w2t_bkin.config` - Settings and configuration
- `w2t_bkin.domain` - PoseTable, PoseSample contracts
- `w2t_bkin.utils` - JSON I/O, hashing, timing

**External**:

- `pandas` - DataFrame operations for pose data
- `pyarrow` / `fastparquet` - Parquet I/O
- `h5py` - HDF5 file reading (DLC format)
- `sleap-io` (optional) - SLEAP file parsing

## Performance Considerations

- **Lazy loading**: Read pose data in chunks for large files
- **Vectorized operations**: Use pandas/numpy for coordinate transforms
- **Memory efficiency**: Stream to Parquet without full in-memory table
- **Caching**: Store harmonization metadata to skip re-mapping

## Idempotence

- Check for existing harmonized outputs before processing
- Compare input file hash and skeleton map hash
- Skip harmonization if output exists and is valid (unless forced)

## Provenance

- Record source tool version and model hash
- Store original keypoint names and mapping applied
- Log harmonization timestamp and configuration
- Include in overall pipeline provenance metadata

## Notes

- Pose estimation is **optional** and can be completely bypassed
- Pre-computed pose outputs are preferred over re-running inference
- Canonical skeleton should be documented and version-controlled
- Confidence thresholds are configurable per use case

## Future Enhancements

- Support for additional pose estimation tools (OpenPose, MMPose)
- 3D pose reconstruction from multi-view (out of current scope)
- Temporal smoothing and interpolation options
- Automated skeleton inference from keypoint covariance
- Real-time pose visualization in QC reports
