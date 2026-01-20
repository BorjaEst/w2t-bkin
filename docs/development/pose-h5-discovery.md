# Pose H5 discovery contract (developer notes)

This project currently focuses on _discovering existing_ pose H5 outputs and assembling them into NWB.

Primary implementation:

- Discovery: [src/w2t_bkin/operations/dlc_generator.py](../../src/w2t_bkin/operations/dlc_generator.py), [src/w2t_bkin/operations/sleap_generator.py](../../src/w2t_bkin/operations/sleap_generator.py)
- Ingestion: [src/w2t_bkin/operations/ingestion.py](../../src/w2t_bkin/operations/ingestion.py)
- Orchestration: [src/w2t_bkin/flows/session.py](../../src/w2t_bkin/flows/session.py)
- User-facing summary: [docs/POSE_EXTENSION_SUMMARY.md](../POSE_EXTENSION_SUMMARY.md)

## Folder contract

For a given session:

```text
data/interim/<subject_id>/<session_id>/
  dlc-pose/<camera_id>/
  sleap-pose/<camera_id>/
```

`<camera_id>` must match the camera IDs used in session metadata (`session.toml`) and discovery results.

## Stem matching

Pose H5 files are matched to videos by filename stem.

Let the video be:

```text
<video_dir>/<video_stem>.avi
```

### DLC discovery (artifact discovery)

`discover_dlc_poses()` looks for:

```text
<dlc_dir>/{video_stem}DLC*.h5
```

### DLC ingestion (actual load)

`ingest_dlc_poses()` loads:

```text
<dlc_dir>/{video_stem}DLC_*.h5
```

Note the underscore after `DLC_` for ingestion.

Practical implication: if a file matches `DLC*.h5` but not `DLC_*.h5`, it may show up in “discovered artifacts” but fail ingestion.

### SLEAP discovery vs ingestion

Discovery is permissive:

```text
<sleap_dir>/*{video_stem}*.h5
```

Ingestion is strict:

```text
<sleap_dir>/{video_stem}.sleap.h5
```

## Metadata-driven routing

In `flows/session.py`, discover-mode ingestion is driven by `metadata.pose.cameras` (a dict keyed by camera_id):

```toml
[pose.cameras.top]
source = "dlc"
```

At runtime, the flow:

1. Discovers videos from `[[cameras]]` patterns in `session.toml`
2. For each configured `pose.cameras.<camera_id>`, ingests H5 outputs from `interim/{dlc|sleap}-pose/<camera_id>/` using the stem contract

## Worked example (from project-1-jelte)

Given a session raw video:

```text
data/raw/SNA-144233/day1/video/top/cam0_2025-08-16-17-46-54.avi
```

The video stem is:

```text
cam0_2025-08-16-17-46-54
```

The DLC H5 must be placed under:

```text
data/interim/SNA-144233/day1/dlc-pose/top/
```

And must match:

```text
cam0_2025-08-16-17-46-54DLC_*.h5
```

The `tree.txt` snapshot shows H5 filenames in this format, e.g.:

```text
.../dlc-pose/top/cam0_2025-08-16-17-46-54DLC_manual.h5
.../dlc-pose/top/cam0_2025-08-16-18-04-52DLC_manual.h5
```

These match the ingestion contract (`DLC_*.h5`) and will be picked up as long as the corresponding video stems exist in the discovered camera videos.

## Practical dev checklist

- Ensure `session.toml` camera IDs match the `dlc-pose/<camera_id>/` folders.
- Ensure H5 naming matches stems produced by the actual video filenames.
- When debugging missing poses, check both discovery and ingestion patterns (DLC: `DLC*.h5` vs `DLC_*.h5`).
