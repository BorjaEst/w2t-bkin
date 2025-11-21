"""Pose estimation import, harmonization, and alignment module (Phase 3 - Optional).

Ingests pose tracking data from DeepLabCut (DLC) or SLEAP H5 files, harmonizes
diverse skeleton definitions to a canonical W2T model, and aligns pose frames to
the reference timebase for integration into NWB files.

Supported Formats:
------------------
- DeepLabCut: H5 files (pandas DataFrame with MultiIndex)
- SLEAP: H5 files (HDF5 with 4D numpy arrays)

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
        harmonize_sleap_to_canonical,
        align_pose_to_timebase,
        validate_pose_confidence,
        # TTL mock generation
        TTLMockOptions,
        generate_ttl_from_dlc_likelihood,
        generate_and_write_ttl_from_pose,
    )

See core, models, and ttl_mock modules for detailed documentation.
"""

# Re-export core functions
from .core import (
    KeypointsDict,
    PoseError,
    align_pose_to_timebase,
    build_pose_estimation,
    harmonize_dlc_to_canonical,
    harmonize_sleap_to_canonical,
    import_dlc_pose,
    import_sleap_pose,
    validate_pose_confidence,
)

# Re-export models
from .models import PoseBundle, PoseFrame, PoseKeypoint

# Re-export TTL mock utilities
from .ttl_mock import (
    TTLMockOptions,
    generate_and_write_ttl_from_pose,
    generate_ttl_from_custom_predicate,
    generate_ttl_from_dlc_likelihood,
    load_dlc_likelihood_series,
    write_ttl_timestamps,
)

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
    "build_pose_estimation",
    "validate_pose_confidence",
    # TTL mock generation
    "TTLMockOptions",
    "generate_ttl_from_dlc_likelihood",
    "generate_ttl_from_custom_predicate",
    "generate_and_write_ttl_from_pose",
    "load_dlc_likelihood_series",
    "write_ttl_timestamps",
]
