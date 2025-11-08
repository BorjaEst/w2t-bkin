---
post_title: "Module Design — events"
author1: "Project Team"
post_slug: "design-events"
microsoft_alias: "na"
featured_image: "/assets/og.png"
categories: ["docs", "pipeline"]
tags: ["design", "events", "trials"]
ai_note: "Generated as a module design stub."
summary: "Design for normalizing NDJSON behavioral logs into Events and Trials tables."
post_date: "2025-11-08"
---

<!-- markdownlint-disable MD041 -->

## Scope

Normalize per-sample NDJSON logs to Events; derive Trials TimeIntervals using hybrid derivation.

## Responsibilities

- Parse NDJSON lines; normalize schema.
- Derive trial intervals using Option H with QC flags.

## Inputs/Outputs (Contract)

- Inputs: NDJSON paths; settings; session timebase reference.
- Outputs: Events table; Trials table with QC columns.

## Dependencies

- pandas, json.

## Public Interfaces (planned)

- normalize_events(paths: list[Path]) -> EventsTable
- derive_trials(events: EventsTable, stats: Optional[Path]) -> TrialsTable

## Error Handling

- DataIntegrityWarning on inconsistent IDs/timestamps; record flags.

## Testing

- Unit: NDJSON parsing; trial derivation tolerance.
- Integration: sample logs → Events + Trials.

## Future Notes

- Pluggable derivation policies.
