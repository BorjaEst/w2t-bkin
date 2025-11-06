---
post_title: Testing and CI
author1: Project Team
post_slug: testing-ci
microsoft_alias: borja
featured_image: /assets/cover.png
categories: [testing]
tags: [testing, ci]
ai_note: partial
summary: Pytest strategy, synthetic fixtures, and CI coverage for core logic.
post_date: 2025-11-06
---

## Tests

- Unit tests for ingestion, sync math, NWB writer mapping, and optional stages.
- Tiny synthetic fixtures under `data/raw/testing` for speed and determinism.

## CI

- Lint (ruff), type-check (mypy), run tests, and build docs.
- Minimal integration path: ingest → sync → to-nwb on fixtures.
