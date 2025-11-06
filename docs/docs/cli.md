---
post_title: CLI Reference
author1: Project Team
post_slug: cli
microsoft_alias: borja
featured_image: /assets/cover.png
categories: [docs]
tags: [cli]
ai_note: partial
summary: Commands, options, and examples for the CLI.
post_date: 2025-11-06
---

## Commands

- `ingest`: Build session manifest; validate resources.
- `sync`: Produce per-camera timestamps and summary stats.
- `transcode`: Optional video re-encode.
- `label-extract` / `infer`: Prepare datasets or run inference.
- `facemap`: Run or import facial metrics.
- `to-nwb`: Assemble NWB with all available data.
- `validate`: Run nwbinspector and save report.
- `report`: Generate QC HTML summary.

## Examples

```bash
mmnwb ingest --config configs/session.yaml --force
mmnwb sync --config configs/session.yaml --log-level INFO
mmnwb to-nwb --config configs/session.yaml --dry-run
```
