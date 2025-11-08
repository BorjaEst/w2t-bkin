---
post_title: "Module Design — pose"
author1: "Project Team"
post_slug: "design-pose"
microsoft_alias: "na"
featured_image: "/assets/og.png"
categories: ["pose", "docs", "pipeline"]
tags: ["design", "harmonization"]
ai_note: "Generated as a module design stub."
summary: "Design for importing and harmonizing DLC/SLEAP pose outputs to a canonical skeleton/timebase."
post_date: "2025-11-08"
---

<!-- markdownlint-disable MD041 -->

## Scope

Import pose results, standardize schema, align to session timebase, preserve confidence scores.

## Responsibilities

- Map heterogeneous schemas to canonical skeleton and fields.
- Align timestamps to primary timebase via camera timestamps.
- Emit harmonized tables (prefer Parquet) and metadata.

## Inputs/Outputs (Contract)

- Inputs: Pose files or inference outputs; camera timestamps; settings.
- Outputs: Harmonized pose table + metadata JSON.

## Dependencies

- pandas, numpy; ndx-pose at NWB stage.

## Public Interfaces (planned)

- harmonize_pose(inputs: PoseInputs, timestamps: TimestampSeries) -> PoseTable

## Error Handling

- DataIntegrityWarning when confidence/out-of-range values found.

## Testing

- Unit: column mapping; confidence handling; timestamp alignment.
- Integration: sample DLC/SLEAP files → harmonized output.

## Future Notes

- Optional smoothing with metadata flagging.
