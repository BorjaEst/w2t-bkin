# Metadata Parameters

Metadata is TOML-driven and split into:

- Experiment-level: `data/raw/metadata.toml`
- Subject-level: `data/raw/<subject>/subject.toml`
- Session-level: `data/raw/<subject>/<session>/session.toml`

The session file also declares where raw data lives for that session.

## `[[cameras]]`

Declares camera streams.

Common fields:

- `id`: camera identifier (e.g., `top`, `pupil_left`)
- `paths`: glob pattern relative to the session directory (e.g., `video/top/cam*.avi`)
- `fps`: nominal frame rate
- `ttl_id`: which TTL channel syncs this camera

## `[[TTLs]]`

Declares TTL sources for synchronization.

- `id`: TTL identifier used by cameras and Bpod sync mappings
- `paths`: glob pattern relative to the session directory

## `[bpod]`

Declares Bpod files and (optional) synchronization mappings.

- `path`: glob pattern for Bpod MAT files (relative to session directory)

## `[pose.cameras.<camera_id>]`

Declares pose source per camera.

- `source`: `dlc` or `sleap`

Pose H5 discovery is driven by `configuration.toml` and the `data/interim/<subject>/<session>/` folder structure.
