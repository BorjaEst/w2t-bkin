# Metadata parameters

Metadata is TOML-driven and hierarchically merged (later overrides earlier):

1. Optional global metadata (from `W2T_ROOT_METADATA`, if set)
2. Experiment-level: `data/raw/metadata.toml`
3. Subject-level: `data/raw/<subject>/subject.toml`
4. Session-level: `data/raw/<subject>/<session>/session.toml`

The merged metadata serves two purposes:

- It provides NWB metadata (passed into `pynwb.NWBFile` creation).
- It provides pipeline source definitions (camera/TTL/Bpod/pose discovery and assembly).

## NWB core fields (commonly used)

The following keys are read when constructing the NWBFile (see `create_nwb_file()` in `src/w2t_bkin/core/session.py`).

Required for a valid session:

- `session_description` (str): free text description
- `identifier` (str): unique identifier for the NWB file

Strongly recommended:

- `session_start_time` (str): ISO-8601 datetime (e.g., `2025-11-20T14:30:00Z`)

Optional (directly mapped into `NWBFile`):

- `timestamps_reference_time` (str): ISO-8601 datetime
- `experimenter` (list[str] or str)
- `experiment_description` (str)
- `session_id` (str)
- `institution` (str)
- `keywords` (list[str])
- `notes` (str)
- `pharmacology` (str)
- `protocol` (str)
- `related_publications` (list[str])
- `slices` (str)
- `data_collection` (str)
- `surgery` (str)
- `virus` (str)
- `stimulus_notes` (str)
- `lab` (str)

## `[subject]`

If present, a `pynwb.file.Subject` is created.

- `subject_id` (str)
- `description` (str)
- `species` (str)
- `sex` (str)
- `age` (str): ISO-8601 duration (e.g., `P84D`)
- `age__reference` (str, default `birth`)
- `genotype` (str)
- `strain` (str)
- `weight` (str)
- `date_of_birth` (str): ISO-8601 datetime

## `[[devices]]`

Optional list of NWB devices.

- `name` (str, required)
- `description` (str, optional)
- `manufacturer` (str, optional)
- `model_name` (str, optional)

Note: cameras listed under `[[cameras]]` are also added as NWB devices if they aren’t already present in `[[devices]]`.

## Pipeline source definitions

These keys control discovery/ingestion/assembly.

### `[[cameras]]`

Declares camera streams for file discovery and pose timestamping.

- `id` (str, required): camera identifier (e.g., `top`, `pupil_left`)
- `paths` (str, required): glob pattern relative to the session directory (e.g., `Video/top/*.avi`)
- `fps` (float, optional): nominal frame rate used when TTL alignment is not available
- `ttl_id` (str, optional): TTL channel id used to align camera frames (must match `[[TTLs]].id`)
- `description` (str, optional): used when auto-creating an NWB device for the camera

### `[[TTLs]]`

Declares TTL sources for synchronization.

- `id` (str, required): TTL identifier referenced by cameras and Bpod sync rules
- `paths` (str, required): glob pattern relative to the session directory (e.g., `TTLs/*_frame.txt`)
- `description` (str, optional)

### `[bpod]`

Declares Bpod files and (optional) Bpod-to-TTL synchronization mappings.

- `path` (str, required): glob pattern for Bpod MAT files (relative to session directory)
- `order` (str, optional, default depends on template): one of `name_asc`, `name_desc`, `time_asc`, `time_desc`
- `continuous_time` (bool, optional, default `false` in template): if true, offsets timestamps to form a continuous timeline across files

#### `[[bpod.sync.trial_types]]`

- `trial_type` (int, required): trial type label from Bpod
- `sync_signal` (str, required): Bpod state/event name whose onset is aligned to TTL pulses
- `sync_ttl` (str, required): TTL id containing the pulses (must match `[[TTLs]].id`)

## Pose metadata

Pose configuration lives under the `[pose]` table.
The current implementation expects dicts keyed by id.

### `[pose.models.<model_id>]` (generate mode)

Defines available pose models.

- `source` (str, required): `dlc` or `sleap`
- `path` (str, required): path to the model config file
  - For DLC, this is typically the `config.yaml` under the DLC project
  - Paths are resolved relative to `W2T_MODELS_ROOT` in generate mode

### `[pose.cameras.<camera_id>]`

Per-camera pose configuration.

- `source` (str, required): `dlc` or `sleap`
- `model_id` (str, optional): references `pose.models.<model_id>` (required for DLC generate mode)
- `mapping_id` (str, optional): references `pose.mappings.<mapping_id>`
- `skeleton_id` (str, optional): references `pose.skeletons.<skeleton_id>`

Pose discovery is stem-based and uses both `metadata` and `configuration.toml`:

- Video files are discovered from `[[cameras]].paths`.
- H5 files are discovered under `data/interim/<subject>/<session>/`:
  - DLC: `interim/dlc-pose/<camera_id>/{video_stem}DLC*.h5`
  - SLEAP: `interim/sleap-pose/<camera_id>/*{video_stem}*.h5`

### `[pose.mappings.<mapping_id>]`

Optional name harmonization mapping from pose-estimator labels to canonical labels.

- Keys/values: `source_name = "canonical_name"`

### `[pose.skeletons.<skeleton_id>]`

Optional skeleton definition used for pose visualization/structuring.

- `name` (str, optional): human-readable name
- `nodes` (list[str], recommended): ordered list of body part names
- `edges` (list[table], optional): list of `{ source = "...", target = "..." }`
