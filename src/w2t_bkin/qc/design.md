---
post_title: "Module Design — qc"
author1: "Project Team"
post_slug: "design-qc"
microsoft_alias: "na"
featured_image: "/assets/og.png"
categories: ["validation", "docs"]
tags: ["design", "qc", "report"]
ai_note: "Generated as a module design stub."
summary: "Design for generating an HTML QC report summarizing sync integrity, pose, and metrics."
post_date: "2025-11-08"
---

<!-- markdownlint-disable MD041 -->

## Scope

Render a compact HTML report from stage summaries and quick plots.

## Responsibilities

- Aggregate summaries (sync, pose, facemap, events).
- Render drift plots, distributions, and version tables.

## Inputs/Outputs (Contract)

- Inputs: Summary JSONs; optional thumbnails/figures.
- Outputs: qc/<session>/index.html and assets.

## Dependencies

- Jinja2, Plotly/Matplotlib (offline).

## Public Interfaces (planned)

- build_qc(manifest: Manifest, summaries: Summaries) -> Path

## Error Handling

- QCBuildError with details on missing inputs.

## Testing

- Unit: template rendering with fake data.
- Integration: end-to-end HTML generation.

## Future Notes

- Add interactive elements when possible offline.
