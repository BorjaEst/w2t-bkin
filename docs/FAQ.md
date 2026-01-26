# FAQ

## What is w2t-bkin?

w2t-bkin is a Prefect-orchestrated pipeline that assembles multi-camera behavior, synchronization signals (TTLs), and behavioral events (Bpod), with optional pose artifacts, into NWB files.

## What’s the “supported” way to run it?

- Development: `w2t-bkin server start --dev` (flows run locally via Prefect Runner)
- Production: `w2t-bkin server start` + `w2t-bkin worker start --type docker` (flows run in Docker containers)

## Where are outputs written?

In a standard experiment workspace created by `w2t-bkin data init`:

- `data/interim/<subject>/<session>/` for intermediate artifacts
- `data/processed/<subject>/<session>/` for outputs like `*.nwb`, `pipeline.log`, `provenance.json`, and QC figures

## Do I need a specific raw folder layout?

No. The pipeline uses the glob patterns in each session’s `session.toml` to locate files. Your session can use lowercase folders like `video/` and `bpod/`, or uppercase like `Video/` and `Bpod/`, as long as `session.toml` matches.

## Do I need DeepLabCut to run pose?

Not for the current primary workflow.

The project currently focuses on discovering existing `*.h5` pose outputs under `data/interim/<subject>/<session>/dlc-pose/<camera_id>/` and assembling them into NWB.

## How does DLC pose discovery work?

The discovery contract is stem-based (see the comments in `configuration.toml`):

- Place DLC H5 files under `data/interim/<subject>/<session>/dlc-pose/<camera_id>/`
- Filenames must match video stems: `{video_stem}DLC*.h5`

## What is “Prefect UI” used for?

The UI is where you create and run flow runs.

- Start it via `w2t-bkin server start` (or `--dev`)
- Open http://127.0.0.1:4200
- Run deployments like `process-session` or `batch-process`
