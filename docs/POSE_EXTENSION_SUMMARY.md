# Pose Extension Implementation Summary

## Overview

This document describes the complete implementation of the pose data extension for the w2t-bkin pipeline. The extension enables flexible pose data sourcing through a `mode` field that controls whether pose H5 files are generated via DLC/SLEAP inference or discovered from pre-existing files.

## Schema note (current implementation)

The current pipeline implementation represents pose metadata as dicts keyed by id:

- `pose.cameras.<camera_id>`
- `pose.mappings.<mapping_id>`
- `pose.skeletons.<skeleton_id>`

Some older documentation patterns use `[[pose.cameras]]` list entries. Treat those as legacy; the authoritative schema is defined in `PoseMetadata` in [src/w2t_bkin/models.py](../src/w2t_bkin/models.py).

## Problem Statement

Previously, the pipeline required:

- DLC model path for any DLC processing (couldn't use pre-existing H5 files without model)
- No formal configuration for specifying which H5 file belongs to which camera
- No support for body part name harmonization (canonical mapping)
- No skeleton definition support in metadata

## Solution Architecture

### 1. Mode-Based Sourcing Policy

Added a `mode` field to control pose data sourcing:

- **`off`**: Skip pose processing entirely (enabled=False)
- **`discover`**: Use pre-existing H5 files from `interim/dlc-pose` or `interim/sleap-pose` (requires metadata.pose.cameras)
- **`generate`**: Run DLC/SLEAP inference to create H5 files (requires model_path)
- **`auto`**: Generate if model_path is set, otherwise discover

### 2. Configuration Structure

#### configuration.toml (Runtime Policy)

```toml
[preprocessing]
force_rerun = false  # Applies to 'generate' mode only

[preprocessing.dlc]
enabled = true
mode = "auto"  # off | discover | generate | auto
# model_path = "iteration-1/BA_W2T_cam0.newOct30-trainset95shuffle1/config.yaml"
# gpu = 0
# save_csv = false

[preprocessing.sleap]
enabled = false
mode = "auto"  # off | discover | auto (generate NOT IMPLEMENTED)
# model_path = "sleap_model.h5"
# gpu = 0
```

#### metadata.toml (Data Declarations)

```toml
# Camera-specific pose data sources
[[pose.cameras]]
camera_id = "camera_0"             # Must match [[cameras]].id
source = "dlc"                     # dlc | sleap
h5_path = "dlc-pose/camera_0.h5"  # Relative to intermediate_root/session_id/
mapping_id = "canonical_mouse"     # Optional: reference to [[pose.mappings]]
skeleton_id = "mouse_bodyparts"    # Optional: reference to [[pose.skeletons]]

# Body part name mappings (harmonization)
[[pose.mappings]]
id = "canonical_mouse"
description = "DLC model-specific to canonical mouse bodypart names"

[pose.mappings.map]
nose = "snout"
leftear = "ear_left"
rightear = "ear_right"
bodycentre = "body_center"
tailbase = "tail_base"
tailend = "tail_tip"

# Skeleton definitions (nodes and edges)
[[pose.skeletons]]
id = "mouse_bodyparts"
name = "Mouse Full Body"
description = "Standard mouse skeleton with head, body, and tail"

[[pose.skeletons.nodes]]
name = "snout"

[[pose.skeletons.nodes]]
name = "body_center"

[[pose.skeletons.edges]]
source = "snout"
target = "body_center"
```

### 3. Pydantic Models (Validation)

#### config.py Extensions

**DLCConfig**:

```python
class DLCConfig(BaseModel, extra="forbid"):
    enabled: bool = Field(default=False, ...)
    mode: Literal["off", "discover", "generate", "auto"] = Field(default="auto", ...)
    model_path: Optional[Path] = Field(None, ...)
    gpu: Optional[int] = Field(None, ...)
    save_csv: bool = Field(default=False, ...)

    @model_validator(mode="after")
    def validate_mode_consistency(self) -> "DLCConfig":
        # Auto-correct enabled/mode consistency
        if not self.enabled and self.mode != "off":
            self.mode = "off"
        if self.mode == "off":
            self.enabled = False

        # Validate generate mode requirements
        if self.mode == "generate" and self.model_path is None:
            raise ValueError("DLC mode='generate' requires model_path")

        return self
```

**SLEAPConfig**:

```python
class SLEAPConfig(BaseModel, extra="forbid"):
    enabled: bool = Field(default=False, ...)
    mode: Literal["off", "discover", "generate", "auto"] = Field(default="auto", ...)
    model_path: Optional[Path] = Field(None, ...)
    gpu: Optional[int] = Field(None, ...)

    @model_validator(mode="after")
    def validate_mode_consistency(self) -> "SLEAPConfig":
        # Auto-correct enabled/mode consistency
        if not self.enabled and self.mode != "off":
            self.mode = "off"
        if self.mode == "off":
            self.enabled = False

        # SLEAP generate mode not implemented
        if self.mode == "generate":
            raise ValueError("SLEAP mode='generate' is not yet implemented")

        return self
```

#### models.py Extensions

**Metadata Pose Models**:

```python
class PoseCameraConfig(BaseModel, extra="forbid"):
    """Pose configuration for a specific camera.

    H5 files are discovered by stem-matching video files in:
      interim/{dlc-pose|sleap-pose}/<camera_id>/
    """

    source: Literal["dlc", "sleap"]
    model_id: Optional[str] = None
    mapping_id: Optional[str] = None
    skeleton_id: Optional[str] = None

class SkeletonNode(BaseModel, extra="forbid"):
    """Single node in a pose skeleton."""
    name: str

class SkeletonEdge(BaseModel, extra="forbid"):
    """Edge connecting two nodes."""
    source: str
    target: str

class PoseSkeleton(BaseModel, extra="forbid"):
    """Skeleton definition for pose visualization."""
    id: str
    name: str
    description: Optional[str] = None
    nodes: List[SkeletonNode]
    edges: Optional[List[SkeletonEdge]] = None

class PoseMetadata(BaseModel, extra="forbid"):
    """Complete pose metadata section."""
    models: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    cameras: Dict[str, PoseCameraConfig] = Field(default_factory=dict)
    mappings: Dict[str, Dict[str, str]] = Field(default_factory=dict)
    skeletons: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
```

### 4. Function Mapping

#### Pose Ingestion Functions (src/w2t_bkin/ingest/pose.py)

##### import_dlc_pose(h5_path, mapping=None)

- **Parameters**:
  - `h5_path`: Path to DLC H5 file
  - `mapping`: Optional dict mapping DLC bodypart names → canonical names
- **Returns**: `(frames, metadata)` tuple
- **Used by**: `ingest_dlc_poses()` in src/w2t_bkin/operations/ingestion.py
- **Config source**: H5 path comes from stem-based discovery under `interim/dlc-pose/<camera_id>/`; optional mappings may come from `metadata.pose.mappings.<mapping_id>` (not currently applied in the ingestion operation).

##### import_sleap_pose(h5_path, mapping=None)

- **Parameters**:
  - `h5_path`: Path to SLEAP H5 file
  - `mapping`: Optional dict mapping SLEAP bodypart names → canonical names
- **Returns**: `(frames, metadata)` tuple
- **Used by**: `ingest_sleap_poses()` in src/w2t_bkin/operations/ingestion.py
- **Config source**: H5 path comes from stem-based discovery under `interim/sleap-pose/<camera_id>/`; optional mappings may come from `metadata.pose.mappings.<mapping_id>` (not currently applied in the ingestion operation).

##### harmonize_to_canonical(data, mapping)

- **Parameters**:
  - `data`: Pose data array
  - `mapping`: Dict mapping source names → canonical names
- **Returns**: Harmonized data with canonical names
- **Used by**: `import_dlc_pose()`, `import_sleap_pose()` internally
- **Config source**: `metadata.pose.mappings.<mapping_id>` (when wired up)

##### create_skeleton(name, nodes, edges=None)

- **Parameters**:
  - `name`: Skeleton name
  - `nodes`: List of node names (bodyparts)
  - `edges`: Optional list of (source, target) tuples
- **Returns**: ndx-pose Skeleton object
- **Used by**: `assemble_pose_estimation()` in operations/assembly.py
- **Config source**: `metadata.pose.skeletons.<skeleton_id>`

##### build_pose_estimation(data, reference_times, skeleton, ...)

- **Parameters**:
  - `data`: Pose frames
  - `reference_times`: Aligned timestamps
  - `skeleton`: Skeleton object (from `create_skeleton()`)
  - Other NWB-specific parameters
- **Returns**: ndx-pose PoseEstimation object
- **Used by**: `assemble_pose_estimation()` in operations/assembly.py
- **Config source**: Metadata-driven skeleton if provided, else auto-derived from H5

### 5. Session Flow Integration

#### Phase 2: Artifact Processing (\_process_pose_artifacts)

**Generate Mode**:

```python
if dlc_mode == "generate":
    dlc_artifacts = generate_dlc_session_task(
        session_info=session_info,
        force_rerun=force_rerun,
    )
```

**Discover Mode**:

```python
elif dlc_mode == "discover":
    # No artifact generation; ingestion uses metadata.pose.cameras
    run_logger.info("DLC mode='discover': Will use H5 files from metadata.pose.cameras")
```

#### Phase 3: Ingestion (\_ingest_pose_data)

##### Metadata-Driven Ingestion (Discover Mode)

```python
pose_metadata = session_info.metadata.get("pose", {})
pose_cameras = pose_metadata.get("cameras", {})  # Dict keyed by camera_id

if pose_cameras and (dlc_mode == "discover" or sleap_mode == "discover"):
    for camera_id, camera_config in pose_cameras.items():
        source = camera_config.get("source")
        if source == "dlc":
            camera_dlc_dir = session_info.interim_dir / "dlc-pose" / camera_id
            dlc_poses = ingest_dlc_poses_task(video_paths=video_paths, dlc_dir=camera_dlc_dir, camera_id=camera_id)
        elif source == "sleap":
            camera_sleap_dir = session_info.interim_dir / "sleap-pose" / camera_id
            sleap_poses = ingest_sleap_poses_task(video_paths=video_paths, sleap_dir=camera_sleap_dir, camera_id=camera_id)
```

##### Legacy Artifact-Based Ingestion (Generate Mode)

```python
# Uses existing ingest_dlc_poses_task/ingest_sleap_poses_task
for camera_id, artifacts in dlc_artifacts.items():
    dlc_poses = ingest_dlc_poses_task(
        video_paths=video_paths,
        dlc_dir=camera_dlc_dir,
        camera_id=camera_id,
    )
```

#### Phase 5: Assembly (No Changes)

Assembly already supports metadata-driven skeletons:

```python
# In operations/assembly.py
skeleton_id = camera_config.get("skeleton_id")
if skeleton_id and "skeletons" in metadata:
    skeleton = create_skeleton(...)  # Uses metadata.pose.skeletons
else:
    skeleton = auto_derive_from_h5(...)  # Default behavior
```

## Key Design Decisions

### 1. Separation of Concerns

- **configuration.toml** (SessionFlowConfig): Runtime policy (mode, force_rerun, GPU)
- **metadata.toml** (free-form dict): Data declarations (H5 paths, mappings, skeletons)

### 2. One H5 Per Camera Constraint

- Each camera has exactly one pose source (no merging/ambiguity)
- Specified in `metadata.pose.cameras[]` with `camera_id` mapping to `[[cameras]].id`

### 3. Force Rerun Orthogonality

- `force_rerun` only applies to `mode="generate"` (cache invalidation)
- `mode` controls sourcing policy (generate vs discover)
- No interaction between the two fields

### 4. Auto Mode Resolution

- `mode="auto"` for DLC: Generate if `model_path` set, else discover
- `mode="auto"` for SLEAP: Always discover (generate not implemented)

### 5. Backward Compatibility

- Legacy artifact-based ingestion still works for `mode="generate"`
- If `metadata.pose` is missing, falls back to video-stem matching

## Validation Rules

### Configuration Validation (config.py)

1. If `mode="off"`, set `enabled=False`
2. If `enabled=False`, set `mode="off"`
3. If `mode="generate"` and `model_path is None`, raise error (DLC only)
4. If `mode="generate"` for SLEAP, raise error (not implemented)

### Metadata Validation (models.py)

1. `PoseCamera.camera_id` must exist in `metadata.cameras[]`
2. `PoseCamera.mapping_id` must exist in `metadata.pose.mappings[]` if set
3. `PoseCamera.skeleton_id` must exist in `metadata.pose.skeletons[]` if set
4. `PoseCamera.h5_path` relative to `interim_dir/session_id/`
5. `SkeletonEdge.source` and `target` must exist in parent skeleton's nodes

## Usage Examples

### Example 1: Generate DLC Poses (Default)

**configuration.toml**:

```toml
[preprocessing.dlc]
enabled = true
mode = "generate"  # or "auto" if model_path is set
model_path = "iteration-1/BA_W2T_cam0.newOct30-trainset95shuffle1/config.yaml"
```

**metadata.toml**:

```toml
# No [pose] section needed; generated H5s auto-discovered
```

### Example 2: Discover Pre-Existing DLC H5 Files

**configuration.toml**:

```toml
[preprocessing.dlc]
enabled = true
mode = "discover"  # Explicitly use pre-existing H5s
# model_path not required
```

**metadata.toml**:

```toml
[[pose.cameras]]
camera_id = "camera_0"
source = "dlc"
h5_path = "dlc-pose/camera_0.h5"
```

### Example 3: Discover with Harmonization and Skeleton

**configuration.toml**:

```toml
[preprocessing.dlc]
enabled = true
mode = "discover"
```

**metadata.toml**:

```toml
[[pose.cameras]]
camera_id = "camera_0"
source = "dlc"
h5_path = "dlc-pose/camera_0.h5"
mapping_id = "canonical_mouse"
skeleton_id = "mouse_bodyparts"

[[pose.mappings]]
id = "canonical_mouse"
[pose.mappings.map]
nose = "snout"
bodycentre = "body_center"

[[pose.skeletons]]
id = "mouse_bodyparts"
name = "Mouse Full Body"
[[pose.skeletons.nodes]]
name = "snout"
[[pose.skeletons.nodes]]
name = "body_center"
[[pose.skeletons.edges]]
source = "snout"
target = "body_center"
```

## Implementation Checklist

- [x] Add `mode` field to `DLCConfig` and `SLEAPConfig`
- [x] Add validation for `mode`/`model_path` consistency
- [x] Update `templates/configuration.toml` with mode examples
- [x] Create Pydantic models for `metadata.pose` section
- [x] Update `_process_pose_artifacts()` to handle discover mode
- [x] Update `_ingest_pose_data()` to use metadata-driven ingestion
- [x] Add comprehensive docstrings and comments
- [x] Validate all Python files compile without errors

## Testing Strategy

### Unit Tests

1. Test `DLCConfig` validation (mode/model_path consistency)
2. Test `SLEAPConfig` validation (generate mode rejection)
3. Test `PoseMetadata` schema validation (missing camera_id, invalid references)
4. Test auto mode resolution logic

### Integration Tests

1. Test discover mode with manually placed H5 files
2. Test mapping application (harmonize_to_canonical)
3. Test skeleton creation from metadata
4. Test backward compatibility (no metadata.pose section)
5. Test error handling (missing H5 file, invalid mapping_id)

### End-to-End Tests

1. Full session with `mode="generate"` (existing behavior)
2. Full session with `mode="discover"` and complete metadata.pose
3. Full session with `mode="auto"` (auto-resolve based on model_path)

## Migration Guide

### For Existing Pipelines

- **No changes required**: Default `mode="auto"` maintains current behavior
- If `model_path` is set, continues to generate poses
- If `model_path` is not set, switches to discover mode (requires metadata.pose)

### For New Discover-Only Workflows

1. Place H5 files in `interim/<session_id>/dlc-pose/` or `interim/<session_id>/sleap-pose/`
2. Add `[[pose.cameras]]` section to `metadata.toml`
3. Set `preprocessing.dlc.mode = "discover"` (or omit model_path and use auto)
4. Optionally add `[[pose.mappings]]` and `[[pose.skeletons]]` for harmonization

## Future Enhancements

1. **SLEAP Generate Mode**: Implement `generate_sleap_poses_for_session()`
2. **Validation at Runtime**: Check H5 file existence during flow validation phase
3. **Multi-Source Merging**: Support multiple H5 files per camera (requires merge strategy)
4. **Auto-Mapping Discovery**: Infer mappings from H5 bodypart names
5. **Schema Evolution**: Support versioned metadata schemas with migration tools

## Files Modified

1. [src/w2t_bkin/config.py](../src/w2t_bkin/config.py)

   - Added `mode` field to `DLCConfig` and `SLEAPConfig`
   - Added `validate_mode_consistency()` validators

2. [src/w2t_bkin/models.py](../src/w2t_bkin/models.py)

   - Added `PoseCamera`, `PoseMapping`, `PoseSkeleton`, `SkeletonNode`, `SkeletonEdge`
   - Added `PoseMetadata` container model

3. [src/w2t_bkin/flows/session.py](../src/w2t_bkin/flows/session.py)

   - Updated `_process_pose_artifacts()` to support discover mode
   - Updated `_ingest_pose_data()` with metadata-driven ingestion

4. [templates/configuration.toml](../templates/configuration.toml)

   - Added `mode` field documentation with examples

5. [templates/metadata.toml](../templates/metadata.toml)
   - Added `[pose]` section with complete examples

## References

- **DLC H5 Format**: DeepLabCut stores bodyparts, scorer, coordinates in HDF5
- **SLEAP H5 Format**: SLEAP uses `tracks`, `track_names`, `node_names` structure
- **ndx-pose**: NWB extension for pose estimation data (skeletons, nodes, edges)
- **EARS Notation**: Requirements formatted as "WHEN [condition] THE SYSTEM SHALL [behavior]"
