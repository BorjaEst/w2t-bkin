---
post_title: Configuration Reference
author1: Project Team
post_slug: configuration
microsoft_alias: borja
featured_image: /assets/cover.png
categories: [docs]
tags: [config, yaml]
ai_note: partial
summary: YAML schema, keys, defaults, and examples for all pipeline modules.
post_date: 2025-11-06
---

## Structure

- `project`: name, `n_cameras`, skeleton definition.
- `paths`: `raw_root`, `intermediate_root`, `output_root`, `models_root`.
- `session`: id, subject metadata, date, and description.
- `video`: filename `pattern`, `fps` (nullable), `transcode` { enabled, codec, crf, preset, keyint }.
- `sync`: TTL/frame counter inputs, tolerance, drop detection, `primary_clock`.
- `labels`: DLC/SLEAP model paths and inference toggles.
- `facemap`: run flag and ROI params.
- `nwb`: file name template, `session_description`, `link_external_video`.
- `qc`: report flag and output directory.
- `logging`: level.
- `events`: patterns for NDJSON logs and format.

## Example

```yaml
project:
  name: demo
  n_cameras: 5
paths:
  raw_root: data/raw
  intermediate_root: data/interim
  output_root: data/processed
  models_root: models
session:
  id: S001
  subject_id: mouse1
video:
  pattern: "cam{index}.mp4"
  fps: null
  transcode:
    enabled: false
sync:
  ttl_channels:
    - path: sync_ttl.csv
      name: camera_trig
      polarity: rising
  tolerance_ms: 2.0
  drop_frame_max_gap_ms: 50.0
  primary_clock: cam0
labels:
  dlc:
    model: models/dlc/model.yaml
    run_inference: false
facemap:
  run: false
nwb:
  link_external_video: true
  session_description: Demo session
qc:
  generate_report: true
```

## Notes

- Use absolute paths in the manifest; relative paths are resolved from repo root if needed.
- Event NDJSON files are not used for synchronization; they populate Trials/BehavioralEvents in NWB.
