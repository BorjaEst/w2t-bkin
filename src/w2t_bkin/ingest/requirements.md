---
post_title: "Module Requirements — ingest"
author1: "Project Team"
post_slug: "requirements-ingest"
microsoft_alias: "na"
featured_image: "/assets/og.png"
categories: ["pipeline", "docs", "testing"]
tags: ["requirements", "EARS", "module"]
ai_note: "Generated as a module requirements stub."
summary: "EARS requirements for the ingestion subsystem."
post_date: "2025-11-08"
---

## Functional requirements (EARS)

- MR-1 — Ubiquitous: THE MODULE SHALL discover five camera videos and associated sync files.
- MR-2 — Ubiquitous: THE MODULE SHALL extract per-video metadata and write a manifest.json.
- MR-3 — Event-driven: WHEN required inputs are missing, THE MODULE SHALL fail with MissingInputError.
- MR-4 — Optional: WHERE event/pose/facemap files are present, THE MODULE SHALL record their paths in the manifest.

## Non-functional requirements

- M-NFR-1: Avoid loading entire videos; rely on probe tools.
- M-NFR-2: Deterministic manifest ordering and stable keys.
