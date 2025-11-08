---
post_title: "Module Design — sync"
author1: "Project Team"
post_slug: "design-sync"
microsoft_alias: "na"
featured_image: "/assets/og.png"
categories: ["sync", "pipeline", "docs"]
tags: ["design", "timestamps", "drift"]
ai_note: "Generated as a module design stub."
summary: "Design for deriving per-frame timestamps from TTL or frame counters and computing drift/drop stats."
post_date: "2025-11-08"
---

<!-- markdownlint-disable MD041 -->

## Scope

Parse sync logs to produce per-frame timestamps for each camera in a common timebase.

## Responsibilities

- Parse TTL edges or frame counter logs.
- Map frames to timestamps; detect drops/duplicates and drift.
- Emit timestamps_cam{i}.csv and sync_summary.json.

## Inputs/Outputs (Contract)

- Inputs: Manifest, sync logs, primary clock.
- Outputs: Per-camera timestamps CSVs; summary JSON with counts and drift metrics.

## Dependencies

- numpy, pandas.

## Public Interfaces (planned)

- compute_timestamps(manifest: Manifest, primary: str) -> list[TimestampSeries], SyncSummary

## Error Handling

- TimestampMismatchError for non-monotonic/length mismatches.
- DriftThresholdExceeded based on configured tolerance.

## Testing

- Unit: edge detection, gap/duplicate detection.
- Integration: synthetic session with known drops/drift.

## Future Notes

- Support multiple sync input formats via adapters.
