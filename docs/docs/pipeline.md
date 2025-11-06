---
post_title: Pipeline Stages
author1: Project Team
post_slug: pipeline-stages
microsoft_alias: borja
featured_image: /assets/cover.png
categories: [pipeline]
tags: [pipeline, stages]
ai_note: partial
summary: Stage-by-stage description, inputs, outputs, and idempotence.
post_date: 2025-11-06
---

## Ingestion

- Discover videos, sync files, and optional event logs.
- Extract video metadata and write `manifest.yaml` with absolute paths.

## Synchronization

- Parse TTL or frame counters, handle polarity/debounce/tolerance.
- Map frames to timestamps; detect dropped/duplicate frames and drift.
- Emit `timestamps_cam{i}.csv` and `sync_summary.json`.

## Transcoding (optional)

- Re-encode to a mezzanine format for reliable seeking; skippable when not needed.

## Pose and Facemap

- Import or run DLC/SLEAP and Facemap; harmonize skeleton/timebase.

## NWB packaging

- Create devices, ImageSeries with external files and per-frame timestamps.
- Add sync TimeSeries, ndx-pose containers, and behavioral metrics.
- Optionally add Trials and event series from NDJSON logs.

## Validation and QC

- Run nwbinspector and generate a QC HTML report with key diagnostics.
