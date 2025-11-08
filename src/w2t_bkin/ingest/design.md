---
post_title: "Module Design — ingest"
author1: "Project Team"
post_slug: "design-ingest"
microsoft_alias: "na"
featured_image: "/assets/og.png"
categories: ["pipeline", "docs", "data"]
tags: ["design", "module", "ingest"]
ai_note: "Generated as a module design stub."
summary: "Design for discovering session resources and building a manifest."
post_date: "2025-11-08"
---

<!-- markdownlint-disable MD041 -->

## Scope

Discover videos, sync logs, and optional artifacts; extract video metadata; write manifest.json.

## Responsibilities

- Resolve file patterns and absolute paths.
- Probe video metadata (codec, fps, duration, resolution).
- Verify required inputs exist; record optional inputs when present.

## Inputs/Outputs (Contract)

- Inputs: Settings, filesystem paths.
- Outputs: manifest.json with absolute paths and key metadata.

## Dependencies

- ffprobe/ffmpeg (system), optional OpenCV.

## Public Interfaces (planned)

- build_manifest(settings: Settings) -> Manifest

## Error Handling

- MissingInputError when required files are absent.

## Testing

- Unit: metadata extraction on synthetic files.
- Integration: end-to-end manifest creation in temp dirs.

## Future Notes

- Optional checksums for provenance.
