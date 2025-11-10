---
post_title: "Module README — transcode"
author1: "Project Team"
post_slug: "readme-transcode"
microsoft_alias: "na"
featured_image: "/assets/og.png"
categories: ["docs", "pipeline"]
tags: ["transcode", "video", "mezzanine"]
ai_note: "Generated as module documentation."
summary: "Documentation for the transcode module - optional video transcoding to mezzanine format."
post_date: "2025-11-10"
---

## Overview

The `transcode` module provides optional video transcoding to a mezzanine format for the W2T Body Kinematics pipeline. When enabled via configuration, it produces normalized video files optimized for seeking and downstream processing.

## Scope

- Transcode raw camera videos to a mezzanine format (typically H.264/H.265)
- Preserve or normalize frame rates and resolution
- Generate metadata for transcoded files
- Support configuration-driven codec selection

## Responsibilities

- Parse manifest to identify videos requiring transcoding
- Execute FFmpeg-based transcoding with configured parameters
- Validate transcoded output (frame count, duration, codec)
- Update manifest with transcoded video references
- Generate transcode summary with statistics

## Key Features

### Optional Processing
- Enabled/disabled via `video.transcode.enabled` configuration
- When disabled, the stage is a no-op with clear logging
- Pipeline operates directly on raw videos if transcoding is skipped

### Configuration-Driven
- Codec selection: H.264, H.265, VP9, etc.
- CRF (Constant Rate Factor) for quality control
- Preset for encoding speed/efficiency trade-off
- Keyframe interval configuration

### Quality Assurance
- Frame count verification
- Duration validation
- Codec verification
- Hash/checksum recording for provenance

## Public API

### Functions

#### `transcode_videos(manifest_path, output_dir, codec=None) -> transcode_summary`

**Purpose**: Produce mezzanine videos from raw inputs and update metadata.

**Parameters**:
- `manifest_path` (Path): Path to manifest.json from ingest stage
- `output_dir` (Path): Directory for transcoded videos
- `codec` (Optional[str]): Override codec from config (e.g., 'libx264', 'libx265')

**Returns**: 
- `TranscodeSummary`: Summary object with per-video statistics and validation results

**Dependencies**: 
- `w2t_bkin.domain.VideoMetadata`
- `w2t_bkin.utils`

**Raises**:
- `TranscodeError`: FFmpeg execution failed or validation errors
- `MissingInputError`: Video files not found
- `ConfigValidationError`: Invalid codec or parameters

## Configuration Keys

```toml
[video.transcode]
enabled = true              # Enable/disable transcoding
codec = "libx264"          # FFmpeg codec name
crf = 23                   # Constant Rate Factor (0-51, lower = better quality)
preset = "medium"          # FFmpeg preset (ultrafast, fast, medium, slow, veryslow)
keyint = 30                # Keyframe interval (frames)
```

## Data Flow

```
manifest.json → transcode_videos() → data/interim/<session>/video/
                                   → transcode_summary.json
                                   → updated manifest (optional)
```

## Output Structure

### Transcoded Videos
- Location: `data/interim/<session>/video/`
- Naming: `<camera_id>_transcoded.<ext>` (e.g., `cam0_transcoded.mp4`)
- Format: Configured codec in MP4/MKV container

### Transcode Summary JSON
```json
{
  "session_id": "session_001",
  "timestamp": "2025-11-10T12:00:00Z",
  "codec": "libx264",
  "crf": 23,
  "preset": "medium",
  "videos": [
    {
      "camera_id": "cam0",
      "input_path": "/data/raw/session_001/cam0.avi",
      "output_path": "/data/interim/session_001/video/cam0_transcoded.mp4",
      "input_frames": 18000,
      "output_frames": 18000,
      "input_duration_sec": 600.0,
      "output_duration_sec": 600.0,
      "frame_count_match": true,
      "duration_delta_sec": 0.0,
      "transcoding_time_sec": 45.2,
      "compression_ratio": 2.3,
      "validation_passed": true
    }
  ],
  "total_transcoding_time_sec": 225.8,
  "warnings": [],
  "errors": []
}
```

## Error Handling

| Error Type | Cause | Response |
|------------|-------|----------|
| `MissingInputError` | Input video not found | Fail fast with path details |
| `TranscodeError` | FFmpeg execution failure | Log stderr, suggest codec/parameter check |
| `ValidationError` | Frame/duration mismatch | Warn or fail based on tolerance threshold |
| `ConfigValidationError` | Invalid codec/preset | Abort with supported options list |

## Testing Strategy

### Unit Tests
- Manifest parsing and video discovery
- FFmpeg command generation
- Frame count validation logic
- Codec parameter validation
- No-op behavior when disabled

### Integration Tests
- End-to-end transcoding with small test video
- Validation of output metadata
- Error handling with corrupted inputs

## Dependencies

**Internal**:
- `w2t_bkin.config` - Settings and configuration
- `w2t_bkin.domain` - VideoMetadata, TranscodeSummary contracts
- `w2t_bkin.utils` - JSON I/O, hashing, timing

**External**:
- `ffmpeg-python` - FFmpeg wrapper
- `pymediainfo` - Media file inspection (optional)

## Performance Considerations

- **Parallelization**: Transcode multiple cameras concurrently
- **Disk I/O**: Use temporary directory on fast storage
- **Memory**: Streaming mode to avoid loading entire video
- **Benchmarking**: Log transcoding time per video for analysis

## Idempotence

- Check for existing transcoded files before processing
- Compare input hash to detect changes
- Skip transcoding if output exists and is valid (unless forced)

## Provenance

- Record input file hashes
- Store FFmpeg version and exact command used
- Log codec parameters and encoding time
- Include in overall pipeline provenance metadata

## Notes

- Transcoding is **optional** and can be completely bypassed
- Raw video links are preferred for NWB export (external references)
- Mezzanine files are intermediate artifacts for processing stages
- Not intended for archival storage (raw videos remain canonical)

## Future Enhancements

- Hardware acceleration (NVENC, QSV, VideoToolbox)
- Adaptive quality based on input characteristics
- Audio track preservation (if present)
- Multi-pass encoding for better quality
- Progress reporting and cancellation support
