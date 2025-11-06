---
post_title: Developer Guide
author1: Project Team
post_slug: developer-guide
microsoft_alias: borja
featured_image: /assets/cover.png
categories: [dev]
tags: [dev]
ai_note: partial
summary: Code layout, extending modules, logging, determinism, and references.
post_date: 2025-11-06
---

## Code layout

- `src/w2t_bkin/` for pipeline modules and CLI entry points.
- `tests/` for unit and integration tests.

## Extensibility

- Add new labelers, metrics, or CLI subcommands following existing patterns.
- Keep schemas stable; document changes clearly.

## Logging and determinism

- Structured logs and idempotent stages; prefer deterministic outputs.

## References

- Primary sources: `requirements.md`, `design.md`, and `tasks.md` at repo root.
