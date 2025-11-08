---
post_title: "Module Requirements — nwb"
author1: "Project Team"
post_slug: "requirements-nwb"
microsoft_alias: "na"
featured_image: "/assets/og.png"
categories: ["nwb", "validation", "testing"]
tags: ["requirements", "EARS", "nwb"]
ai_note: "Generated as a module requirements stub."
summary: "EARS requirements for the NWB packaging subsystem."
post_date: "2025-11-08"
---

## Functional requirements (EARS)

- MR-1 — Ubiquitous: THE MODULE SHALL create an NWB file linking external videos with per-frame timestamps.
- MR-2 — Optional: WHERE pose/facemap/events are provided, THE MODULE SHALL add them to the NWB.
- MR-3 — Ubiquitous: THE MODULE SHALL store provenance and configuration snapshot.

## Non-functional requirements

- M-NFR-1: Outputs pass nwbinspector without critical issues.
- M-NFR-2: Large binaries remain external; NWB remains portable.
