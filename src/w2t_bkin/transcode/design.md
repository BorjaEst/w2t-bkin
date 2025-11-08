---
post_title: "Module Design — transcode"
author1: "Project Team"
post_slug: "design-transcode"
microsoft_alias: "na"
featured_image: "/assets/og.png"
categories: ["pipeline", "docs"]
tags: ["design", "transcode"]
ai_note: "Generated as a module design stub."
summary: "Design for optional mezzanine video generation for stable seeking."
post_date: "2025-11-08"
---

<!-- markdownlint-disable MD041 -->

## Scope

Optionally transcode videos to a normalized format; timing remains defined by sync outputs.

## Responsibilities

- Build ffmpeg commands per settings.
- Preserve frame counts; do not regenerate timestamps.

## Inputs/Outputs (Contract)

- Inputs: Manifest, raw video paths, settings.
- Outputs: Mezzanine video files and metadata sidecars.

## Dependencies

- ffmpeg/ffprobe, ffmpeg-python (optional).

## Public Interfaces (planned)

- transcode_videos(manifest: Manifest) -> TranscodeReport

## Error Handling

- ExternalToolError with captured stderr on ffmpeg failures.

## Testing

- Integration: small sample videos; verify output params & frame counts.

## Future Notes

- GPU/NVENC presets; configurable keyframe interval.
