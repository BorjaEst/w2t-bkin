# Configuration parameters

The runtime policy is controlled by `<experiment_root>/configuration.toml`.

At server startup (dev and prod), the effective configuration is built by merging:

1. Base defaults from `configs/standard.toml`
2. Project overrides from `<experiment_root>/configuration.toml`

Only the non-path sections are passed into Prefect as the `SessionFlowConfig` parameter.
Filesystem roots are provided via environment variables at runtime.

## Runtime filesystem roots (environment variables)

These variables are required by session runs (see `build_session_info()` in `src/w2t_bkin/operations/session_info.py`).

- `W2T_RAW_ROOT` (required): root containing `data/raw/<subject>/<session>/...`
- `W2T_INTERMEDIATE_ROOT` (required): root for intermediate artifacts, e.g. `data/interim/<subject>/<session>/...`
- `W2T_OUTPUT_ROOT` (required): root for final outputs, e.g. `data/processed/<subject>/<session>/...`
- `W2T_MODELS_ROOT` (optional, default `models`): root for pose models
- `W2T_ROOT_METADATA` (optional): absolute path to a global metadata TOML applied as the lowest-precedence metadata layer

Note: `configuration.toml` may contain a `[paths]` section for deployment-time convenience, but session execution reads roots from the environment.

## `[paths]` (deployment-time helpers)

These values are used by `w2t-bkin server start` when creating deployments.

- `raw_root` (Path, required if present): host path that will be exported as `W2T_RAW_ROOT`
- `intermediate_root` (Path, required if present): host path that will be exported as `W2T_INTERMEDIATE_ROOT`
- `output_root` (Path, required if present): host path that will be exported as `W2T_OUTPUT_ROOT`
- `models_root` (Path, default `models`): host path exported as `W2T_MODELS_ROOT`
- `root_metadata` (Path, optional): host path exported as `W2T_ROOT_METADATA`

## `[synchronization]`

Controls how timestamps are aligned across modalities.

- `strategy` (required):
  - `rate_based`: no TTLs required; uses sampling rates
  - `hardware_pulse`: aligns via TTL pulses
  - `network_stream`: aligns via a streamed reference channel
- `reference_channel` (optional/required): TTL/channel id used as the timebase
  - Required when `strategy` is `hardware_pulse` or `network_stream`

### `[synchronization.alignment]`

- `method` (required):
  - `nearest`: snap each sample to nearest reference
  - `linear`: linear interpolation between reference samples
- `tolerance_s` (required, float >= 0): maximum allowed absolute alignment error (used for verification/QC)
- `global_offset_s` (optional, default `0.0`): constant offset in seconds applied before alignment

## `[acquisition]`

Policies for multi-file acquisitions (e.g., split/rolled videos).

- `concat_strategy` (optional, default `ffconcat`):
  - `ffconcat`: FFmpeg concat demuxer
  - `streamlist`: list-based concatenation

## `[verification]`

Runtime checks for sync and integrity.

- `enabled` (optional, default `true`): master switch
- `check_frame_counts` (optional, default `true`): count frames (accurate but may be slow)
- `check_sync_mismatch` (optional, default `true`): compare frame counts against TTL pulse counts
- `mismatch_tolerance_frames` (optional, default `0`, int >= 0): allowed absolute mismatch (frames)
- `warn_on_mismatch` (optional, default `false`): warn instead of failing when within tolerance

## `[bpod]`

Controls Bpod parsing and (optional) Bpod-to-TTL alignment rules.

- `parse` (optional, default `true`): parse Bpod MAT files if present
- `pattern` (optional, default `Bpod/*.mat`): glob pattern for Bpod MAT files (relative to the session directory)
- `order` (optional, default `time_asc`): sort order for multiple Bpod files: `name_asc` | `name_desc` | `time_asc` | `time_desc`
- `continuous_time` (optional, default `true`): if true, offsets timestamps to form a continuous timeline across files

Note: if the session metadata includes a `[bpod]` section (in `metadata.toml`/`session.toml`), those values take precedence for that session.

### `[[bpod.sync.trial_types]]`

Defines how to align specific Bpod trial types to TTL channels.

- `trial_type` (required, int >= 0): Bpod trial type label
- `sync_signal` (required, str): Bpod state/event name whose onset is used for synchronization
- `sync_ttl` (required, str): TTL id (must match `[[TTLs]].id` in metadata)

## `[preprocessing]`

Optional preprocessing that creates intermediate artifacts.

- `force_rerun` (optional, default `false`): recompute intermediates even if cached

### `[preprocessing.dlc]`

- `enabled` (optional, default `false`): enable DLC handling
- `mode` (optional, default `auto`): `off` | `discover` | `generate` | `auto`
  - `discover`: ingest pre-existing DLC H5 files (stem-based discovery)
  - `generate`: run DLC inference (requires `metadata.pose.cameras` + `metadata.pose.models`)
  - `auto`: `generate` if `metadata.pose.models` exists, otherwise `discover`
- `gpu` (optional, int): GPU index (`None` = auto, `-1` = force CPU)
- `save_csv` (optional, default `false`): also export CSV alongside H5

### `[preprocessing.sleap]`

- `enabled` (optional, default `false`): enable SLEAP handling
- `mode` (optional, default `auto`): `off` | `discover` | `generate` | `auto`
  - `generate` is not implemented and will raise an error
- `gpu` (optional, int): GPU index (`None` = auto, `-1` = force CPU)

## `[video]`

Controls video probing and derived/transcoded outputs.

### `[video.analysis]`

- `frame_count_timeout` (optional, default `30`): timeout in seconds for frame counting/probing per file

### `[video.transcode]`

- `enabled` (optional, default `true`): enable transcoding to standardize codec/format
- `codec` (optional, default `h264`): FFmpeg codec name (commonly `libx264`)
- `crf` (optional, default `20`, 0–51): quality value (lower = higher quality)
- `preset` (optional, default `fast`): encoder preset
- `keyint` (optional, default `15`, int >= 1): keyframe interval (GOP size) in frames

## `[nwb]`

Controls NWB export behavior.

- `link_external_video` (optional, default `true`): store videos as external file references in NWB
- `lab` (optional, default `Lab Name`): lab name written into NWB
- `institution` (optional, default `Institution Name`): institution written into NWB
- `file_name_template` (optional, default `{session.id}.nwb`): NWB output filename template
- `session_description_template` (optional, default `Session {session.id} on {session.date}`): session description template

## `[qc]`

Controls QC outputs.

- `generate_report` (optional, default `true`): generate QC plots/metrics
- `out_template` (optional, default `qc/{session.id}`): QC output path under `output_root`
- `include_verification` (optional, default `true`): include verification results in QC

## `[logging]`

- `level` (optional, default `INFO`): `DEBUG` | `INFO` | `WARNING` | `ERROR` | `CRITICAL`
- `structured` (optional, default `false`): emit JSON logs
