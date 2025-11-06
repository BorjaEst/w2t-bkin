---
post_title: Quickstart
author1: Project Team
post_slug: quickstart
microsoft_alias: borja
featured_image: /assets/cover.png
categories: [docs]
tags: [quickstart, setup]
ai_note: partial
summary: Minimal steps to install, configure, and run the core pipeline stages.
post_date: 2025-11-06
---

## Prerequisites

- Python 3.10+
- FFmpeg installed and available on PATH

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Minimal run

1. Create a config under `configs/session.yaml`.
2. Run ingest → sync → to-nwb → validate → report.

```bash
mmnwb ingest --config configs/session.yaml
mmnwb sync --config configs/session.yaml
mmnwb to-nwb --config configs/session.yaml
mmnwb validate --config configs/session.yaml
mmnwb report --config configs/session.yaml
```

## Expected artifacts

- Intermediate: `timestamps_cam{i}.csv`, `sync_summary.json`, harmonized pose/facemap (if present).
- Output: `output/<session_id>/<session_id>.nwb`, QC HTML, and nwbinspector JSON.
