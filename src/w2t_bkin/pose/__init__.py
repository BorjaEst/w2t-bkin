"""Pose estimation import, harmonization, and alignment module (Phase 3 - Optional).

Ingests pose tracking data from DeepLabCut (DLC) or SLEAP, harmonizes diverse
skeleton definitions to a canonical W2T model, and aligns pose frames to the
reference timebase for integration into NWB files.

Public API:
-----------
All public functions and models are re-exported at the package level:

    from w2t_bkin.pose import (
        PoseBundle,
        PoseFrame,
        PoseKeypoint,
        import_dlc_pose,
        import_sleap_pose,
        harmonize_dlc_to_canonical,
        align_pose_to_timebase,
    )

See core and models modules for detailed documentation.
"""

# Re-export core functions
from .core import (
    KeypointsDict,
    PoseError,
    align_pose_to_timebase,
    harmonize_dlc_to_canonical,
    harmonize_sleap_to_canonical,
    import_dlc_pose,
    import_sleap_pose,
    validate_pose_confidence,
)

# Re-export models
from .models import PoseBundle, PoseFrame, PoseKeypoint

__all__ = [
    # Models
    "PoseBundle",
    "PoseFrame",
    "PoseKeypoint",
    # Exceptions
    "PoseError",
    # Core functions
    "KeypointsDict",
    "import_dlc_pose",
    "import_sleap_pose",
    "harmonize_dlc_to_canonical",
    "harmonize_sleap_to_canonical",
    "align_pose_to_timebase",
    "validate_pose_confidence",
]
