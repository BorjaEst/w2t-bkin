"""Video transcoding domain models (Phase 3 - Optional).

This module defines models for video transcoding metadata. Transcode
operations produce mezzanine format videos with content-addressed
checksums for idempotent operations.

Model Hierarchy:
---------------
- TranscodeOptions: Transcoding configuration
- TranscodedVideo: Metadata for transcoded output

Key Features:
-------------
- **Immutable**: frozen=True prevents accidental modification
- **Strict Schema**: extra="forbid" rejects unknown fields
- **Type Safe**: Full annotations with runtime validation
- **Content-Addressed**: Checksum-based deduplication

Requirements:
-------------
- FR-4: Optional transcoding to mezzanine format
- NFR-2: Idempotent operations

Acceptance Criteria:
-------------------
- Idempotent transcoding via content-addressed paths

Usage:
------
>>> from pathlib import Path
>>> from w2t_bkin.domain.transcode import TranscodeOptions, TranscodedVideo
>>>
>>> options = TranscodeOptions(
...     codec="libx264",
...     crf=23,
...     preset="medium",
...     keyint=30
... )
>>>
>>> video = TranscodedVideo(
...     camera_id="cam0",
...     original_path=Path("raw/video.avi"),
...     output_path=Path("intermediate/video_abc123.mp4"),
...     codec="libx264",
...     checksum="abc123...",
...     frame_count=8580
... )

See Also:
---------
- w2t_bkin.transcode: Transcoding implementation
- design.md: Transcode configuration
"""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class TranscodeOptions(BaseModel):
    """Transcoding configuration options.

    Defines ffmpeg parameters for video transcoding to mezzanine format.

    Attributes:
        codec: ffmpeg video codec (e.g., "libx264", "libx265")
        crf: Constant Rate Factor for quality (0-51, lower=better)
        preset: ffmpeg preset (e.g., "ultrafast", "medium", "veryslow")
        keyint: Keyframe interval in frames

    Requirements:
        - FR-4: Configurable transcoding

    Example:
        >>> options = TranscodeOptions(
        ...     codec="libx264",
        ...     crf=23,
        ...     preset="medium",
        ...     keyint=30
        ... )
    """

    model_config = {"frozen": True, "extra": "forbid"}

    codec: Literal["libx264", "libx265", "libvpx-vp9", "libaom-av1"] = Field(..., description="ffmpeg video codec: 'libx264' | 'libx265' | 'libvpx-vp9' | 'libaom-av1'")
    crf: int = Field(..., description="Constant Rate Factor (0-51, lower=better quality)", ge=0, le=51)
    preset: Literal["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"] = Field(
        ..., description="ffmpeg encoding preset (speed vs. compression trade-off)"
    )
    keyint: int = Field(..., description="Keyframe interval in frames", gt=0)


class TranscodedVideo(BaseModel):
    """Metadata for a transcoded video file.

    Tracks transcoding operation results with content-addressed
    checksums for idempotent operations.

    Attributes:
        camera_id: Camera identifier
        original_path: Path to original raw video
        output_path: Path to transcoded mezzanine video
        codec: Video codec used for transcoding
        checksum: Content-addressed hash (e.g., SHA256)
        frame_count: Total frame count (for verification)

    Requirements:
        - FR-4: Transcode to mezzanine format
        - NFR-2: Idempotent operations via checksums

    Design Notes:
        - output_path should be content-addressed using checksum
        - Re-running transcoding with same inputs produces same checksum
        - Allows skipping transcoding if output exists with matching checksum

    Example:
        >>> from pathlib import Path
        >>> video = TranscodedVideo(
        ...     camera_id="cam0",
        ...     original_path=Path("raw/session_cam0.avi"),
        ...     output_path=Path("intermediate/session_cam0_abc123.mp4"),
        ...     codec="libx264",
        ...     checksum="abc123def456...",
        ...     frame_count=8580
        ... )
    """

    model_config = {"frozen": True, "extra": "forbid"}

    camera_id: str = Field(..., description="Camera identifier")
    original_path: Path = Field(..., description="Path to original raw video file")
    output_path: Path = Field(..., description="Path to transcoded mezzanine video (content-addressed)")
    codec: Literal["libx264", "libx265", "libvpx-vp9", "libaom-av1"] = Field(..., description="Video codec used for transcoding")
    checksum: str = Field(..., description="Content-addressed hash (e.g., SHA256) for idempotent operations")
    frame_count: int = Field(..., description="Total frame count for verification", ge=0)
