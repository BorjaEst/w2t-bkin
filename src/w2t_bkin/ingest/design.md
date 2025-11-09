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
- Support flexible Settings interface for testing and production use.

## Inputs/Outputs (Contract)

- Inputs: Settings-like object with session_root and file patterns, filesystem paths.
- Outputs: manifest.json with absolute paths and key metadata.

## Settings Interface

The module accepts settings objects with the following attributes (checked in order of precedence):

### Required Attributes (at least one must be present)

- `session_root`: Direct path to session directory (highest priority)
- `paths.raw_root`: Path from nested paths config

### Optional Pattern Attributes

- `video_pattern` or `video.pattern`: Glob pattern for video files (default: "cam\*.mp4")
- `sync_pattern`: Glob pattern for sync files (default: "\*.sync")
- `sync_required`: Boolean flag for sync requirement (default: True)
- `events_pattern`: Glob pattern for event files (default: None)
- `pose_pattern`: Glob pattern for pose files (default: None)
- `facemap_pattern`: Glob pattern for facemap files (default: None)
- `output_dir`: Optional output directory for manifest

### Settings Resolution Strategy

1. Check for direct attributes (e.g., `settings.session_root`, `settings.video_pattern`)
2. Fall back to nested structures (e.g., `settings.paths.raw_root`, `settings.video.pattern`)
3. Use default values where applicable
4. Raise MissingInputError if required values cannot be determined

This design allows:

- Full Settings objects from `config` module in production
- Simplified mock objects (e.g., `SimpleNamespace`) in unit tests
- Flexible test fixtures without requiring full pydantic validation

## Dependencies

- ffprobe/ffmpeg (system), optional OpenCV.

## Public Interfaces (planned)

- `build_manifest(settings) -> Manifest`
  - Accepts any object with settings-like attributes
  - Returns validated Manifest domain object
  - Raises MissingInputError for missing required inputs

## Error Handling

- MissingInputError when required files are absent.
- MissingInputError when session_root cannot be determined from settings.
- ValueError when ffprobe fails or metadata extraction fails.

## Testing

- Unit: metadata extraction on synthetic files with mock settings.
- Integration: end-to-end manifest creation in temp dirs with test fixtures.
- Mock settings objects use `types.SimpleNamespace` or similar for simplified testing.

## Future Notes

- Optional checksums for provenance.
