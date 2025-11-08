---
post_title: "Module Design — nwb"
author1: "Project Team"
post_slug: "design-nwb"
microsoft_alias: "na"
featured_image: "/assets/og.png"
categories: ["nwb", "docs", "pipeline"]
tags: ["design", "nwb"]
ai_note: "Generated as a module design stub."
summary: "Design for assembling the NWB file with devices, ImageSeries, pose, facemap, events, and sync."
post_date: "2025-11-08"
---

<!-- markdownlint-disable MD041 -->

## Scope

Package all available artifacts into a single NWB file using pynwb and ndx-pose with external video links.

## Responsibilities

- Create Devices (cameras), ImageSeries per camera with external_file and timestamps.
- Insert pose (ndx-pose), facemap, events, trials, and sync.
- Store provenance (config snapshot, software versions).

## Inputs/Outputs (Contract)

- Inputs: Manifest; timestamps; harmonized pose; facemap; events/trials; settings.
- Outputs: session_id.nwb.

## Dependencies

- pynwb, ndx-pose.

## Public Interfaces (planned)

- build_nwb(inputs: NwbInputs) -> Path

## Error Handling

- NwbBuildError with context for missing or malformed inputs.

## Testing

- Integration: miniature session produces valid NWB.
- Validation: nwbinspector with no critical issues.

## Future Notes

- Consider relative external_file paths for portability.
