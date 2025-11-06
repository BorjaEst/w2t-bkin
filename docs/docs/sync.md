---
post_title: Synchronization
author1: Project Team
post_slug: synchronization
microsoft_alias: borja
featured_image: /assets/cover.png
categories: [sync]
tags: [sync, ttl]
ai_note: partial
summary: TTL parsing, timestamp derivation, drift/drop detection, and diagnostics.
post_date: 2025-11-06
---

## Inputs

- TTL edges or frame counter logs (CSV/TSV) with timestamps/levels.

## Processing

- Edge detection with polarity and debounce; tolerance windows for matching.
- Frame-to-time mapping per camera; choose `primary_clock` for session timebase.
- Drift estimation across cameras; dropped/duplicate frame detection.

## Outputs

- Per-camera timestamps CSV files and a `sync_summary.json` with counts and drift metrics.

## Error handling

- Non-zero exit for severe mismatches; logs include actionable hints.
