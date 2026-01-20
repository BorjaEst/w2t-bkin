# Pose Extension Quick Reference

## Important note (current schema)

The current pipeline implementation expects pose metadata as **dicts keyed by id**, e.g. `pose.cameras.<camera_id>`.

Some older docs/examples use `[[pose.cameras]]` list entries; treat those as legacy.

## Configuration Options

### configuration.toml

```toml
[preprocessing.dlc]
enabled = true
mode = "auto"  # off | discover | generate | auto
gpu = 0        # Optional: GPU index
save_csv = false  # Optional: export CSV

[preprocessing.sleap]
enabled = false
mode = "auto"  # off | discover | auto (generate NOT IMPLEMENTED)
```

### metadata.toml

```toml
# Per-camera pose configuration (dict keyed by camera_id)
[pose.cameras.top]
source = "dlc"          # dlc | sleap
mapping_id = "canonical" # Optional
skeleton_id = "mouse"    # Optional

# Optional: body part name mappings (dict keyed by mapping_id)
[pose.mappings.canonical]
nose = "snout"
leftear = "ear_left"

# Optional: skeletons (dict keyed by skeleton_id)
[pose.skeletons.mouse]
name = "Mouse Full Body"
nodes = ["snout", "body_center"]
edges = [{ source = "snout", target = "body_center" }]
```

## Mode Behavior

- `off`: Skip processing (no metadata required)
- `discover`: Use pre-existing H5 via stem-based discovery (requires `metadata.pose.cameras`)
- `generate`: Run DLC inference (requires `metadata.pose.cameras` + `metadata.pose.models`; SLEAP generate not implemented)
- `auto`: Generate if `metadata.pose.models` exists, otherwise discover (metadata optional)

## Function Signatures

### Ingestion Functions

```python
# Import DLC pose with optional mapping
import_dlc_pose(h5_path: Path, mapping: Optional[Dict[str, str]] = None)
    -> Tuple[np.ndarray, Dict[str, Any]]

# Import SLEAP pose with optional mapping
import_sleap_pose(h5_path: Path, mapping: Optional[Dict[str, str]] = None)
    -> Tuple[np.ndarray, Dict[str, Any]]

# Harmonize bodypart names to canonical format
harmonize_to_canonical(data: np.ndarray, mapping: Dict[str, str])
    -> np.ndarray

# Create skeleton object
create_skeleton(name: str, nodes: List[str], edges: Optional[List[Tuple[str, str]]] = None)
    -> Skeleton

# Build pose estimation NWB object
build_pose_estimation(data: np.ndarray, reference_times: np.ndarray,
                     skeleton: Skeleton, ...)
    -> PoseEstimation
```

## Validation Rules

### Configuration (config.py)

- DLC `mode="generate"` requires `metadata.pose.cameras` + `metadata.pose.models` at runtime
- `mode="generate"` raises error for SLEAP (not implemented)
- `mode="off"` sets `enabled=False`
- `enabled=False` sets `mode="off"`
- DLC `mode="auto"` generates if `metadata.pose.models` exists, otherwise discovers

### Metadata (models.py)

- `pose.cameras.<camera_id>` keys should match `metadata.cameras[].id` to be ingested
- `pose.cameras.<camera_id>.mapping_id` must exist in `pose.mappings.<mapping_id>` if set
- `pose.cameras.<camera_id>.skeleton_id` must exist in `pose.skeletons.<skeleton_id>` if set
- `pose.skeletons.<skeleton_id>.edges` references must exist in `nodes`

## Common Use Cases

### 1. Generate DLC Poses

```toml
# configuration.toml
[preprocessing.dlc]
enabled = true
mode = "generate"

# metadata.toml
[pose.models.dlc_top]
source = "dlc"
path = "dlc/top/config.yaml"

[pose.cameras.top]
source = "dlc"
model_id = "dlc_top"
```

### 2. Use Pre-Existing H5 Files

```toml
# configuration.toml
[preprocessing.dlc]
enabled = true
mode = "discover"

# metadata.toml
[pose.cameras.top]
source = "dlc"

# Place H5 outputs in:
# interim/<session_id>/dlc-pose/top/{video_stem}DLC*.h5
```

### 3. Use Pre-Existing H5 with Mapping

```toml
# configuration.toml
[preprocessing.dlc]
enabled = true
mode = "discover"

# metadata.toml
[pose.cameras.top]
source = "dlc"
mapping_id = "canonical"

[pose.mappings.canonical]
nose = "snout"
bodycentre = "body_center"

# Place H5 outputs in:
# interim/<session_id>/dlc-pose/top/{video_stem}DLC*.h5
```

### 4. Use Pre-Existing H5 with Full Skeleton

```toml
# configuration.toml
[preprocessing.dlc]
enabled = true
mode = "discover"

# metadata.toml
[pose.cameras.top]
source = "dlc"
skeleton_id = "mouse"

[pose.skeletons.mouse]
name = "Mouse Full Body"
nodes = ["snout", "body_center"]
edges = [{ source = "snout", target = "body_center" }]

# Place H5 outputs in:
# interim/<session_id>/dlc-pose/top/{video_stem}DLC*.h5
```

## File Locations

### Interim Directory Structure

```text
interim/
  <session_id>/
    dlc-pose/
      <camera_id>/
        {video_stem}DLC*.h5
    sleap-pose/
      <camera_id>/
        *{video_stem}*.h5
```

### Template Files

- `templates/configuration.toml` - Runtime configuration template
- `templates/metadata.toml` - Session metadata template with pose section

### Source Files

- `src/w2t_bkin/config.py` - DLCConfig, SLEAPConfig models
- `src/w2t_bkin/models.py` - PoseMetadata, PoseCameraConfig models
- `src/w2t_bkin/flows/session.py` - \_process_pose_artifacts, \_ingest_pose_data
- `src/w2t_bkin/ingest/pose.py` - import_dlc_pose, import_sleap_pose, create_skeleton

## Troubleshooting

### Error: "DLC mode='generate' requires model_path"

- **Cause**: Legacy error text; current implementation validates DLC generate-mode via `metadata.pose.cameras` and `metadata.pose.models`
- **Fix**: Define `pose.models.<model_id>` and reference it from `pose.cameras.<camera_id>.model_id`, or switch to `mode="discover"`

### Error: "SLEAP mode='generate' is not yet implemented"

- **Cause**: `mode="generate"` for SLEAP
- **Fix**: Use `mode="discover"` for SLEAP

### Error: "Invalid pose metadata"

- **Cause**: Missing required fields or invalid references in metadata.pose
- **Fix**: Validate metadata.toml against PoseMetadata schema

### Warning: "No pose.cameras found in metadata"

- **Cause**: `mode="discover"` but no `[[pose.cameras]]` in metadata.toml
- **Fix**: Add pose.cameras section or switch to `mode="generate"`

### Error: "H5 file not found"

- **Cause**: `h5_path` in metadata.pose.cameras doesn't exist
- **Fix**: Verify H5 file exists at `interim/<session_id>/<h5_path>`
