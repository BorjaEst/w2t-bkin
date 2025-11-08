---
post_title: "Module Design — facemap"
author1: "Project Team"
post_slug: "design-facemap"
microsoft_alias: "na"
featured_image: "/assets/og.png"
categories: ["facemap", "docs", "pipeline"]
tags: ["design", "metrics"]
ai_note: "Generated as a module design stub."
summary: "Design for importing/deriving facial metrics and aligning them to the session timebase."
post_date: "2025-11-08"
---

<!-- markdownlint-disable MD041 -->

## Scope

Ingest or compute facial metrics (e.g., motion energy, pupil area) and align to timestamps.

## Responsibilities

- Read inputs (CSV/NPY/Parquet) or compute metrics.
- Align to timebase using face camera timestamps.
- Emit standardized tables plus metadata.

## Inputs/Outputs (Contract)

- Inputs: Face video metrics or raw face video; timestamps; settings.
- Outputs: Time series table (wide) + metadata.

## Dependencies

- pandas, numpy.

## Public Interfaces (planned)

- harmonize_facemap(inputs: FacemapInputs, timestamps: TimestampSeries) -> MetricsTable

## Error Handling

- DataIntegrityWarning for gaps beyond threshold; record flags.

## Testing

- Unit: alignment; basic metrics validation.
- Integration: sample metrics → aligned table.

## Future Notes

- ROI configuration and calibration as optional metadata only.
