---
post_title: "Module Requirements — events"
author1: "Project Team"
post_slug: "requirements-events"
microsoft_alias: "na"
featured_image: "/assets/og.png"
categories: ["testing", "docs"]
tags: ["requirements", "EARS", "events"]
ai_note: "Generated as a module requirements stub."
summary: "EARS requirements for the events subsystem."
post_date: "2025-11-08"
---

## Functional requirements (EARS)

- MR-1 — Optional: WHERE NDJSON logs are present, THE MODULE SHALL normalize them into Events.
- MR-2 — Optional: WHERE trial_stats exist, THE MODULE SHALL derive Trials using a hybrid policy and flag mismatches.
- MR-3 — Ubiquitous: THE MODULE SHALL not be used for video synchronization.

## Non-functional requirements

- M-NFR-1: Document tolerances for trial derivation.
- M-NFR-2: Deterministic outputs from same inputs.
