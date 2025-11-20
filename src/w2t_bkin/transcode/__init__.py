"""Video transcoding module with idempotence and content addressing (Phase 3 - Optional).

Transcodes raw video recordings to a mezzanine format using FFmpeg with content-based
output paths for idempotent processing.

Public API:
-----------
All public functions and models are re-exported at the package level:

    from w2t_bkin.transcode import (
        TranscodeOptions,
        TranscodedVideo,
        create_transcode_options,
        transcode_video,
        is_already_transcoded,
    )

See core and models modules for detailed documentation.
"""

# Re-export core functions
from .core import TranscodeError, create_transcode_options, is_already_transcoded, transcode_video, update_manifest_with_transcode

# Re-export models
from .models import TranscodedVideo, TranscodeOptions

__all__ = [
    # Models
    "TranscodeOptions",
    "TranscodedVideo",
    # Exceptions
    "TranscodeError",
    # Core functions
    "create_transcode_options",
    "is_already_transcoded",
    "transcode_video",
    "update_manifest_with_transcode",
]
