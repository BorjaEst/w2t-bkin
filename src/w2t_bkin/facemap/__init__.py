"""Facemap motion energy computation and alignment module (Phase 3 - Optional).

Provides Facemap ROI handling, signal import/compute, and alignment to reference timebase
for facial motion analysis.

Public API:
-----------
All public functions and models are re-exported at the package level:

    from w2t_bkin.facemap import (
        FacemapBundle,
        FacemapROI,
        FacemapSignal,
        define_rois,
        import_facemap_output,
        compute_facemap_signals,
        align_facemap_to_timebase,
    )

See core and models modules for detailed documentation.
"""

# Re-export core functions
from .core import FacemapError, align_facemap_to_timebase, compute_facemap_signals, define_rois, import_facemap_output, validate_facemap_sampling_rate

# Re-export models
from .models import FacemapBundle, FacemapROI, FacemapSignal

__all__ = [
    # Models
    "FacemapBundle",
    "FacemapROI",
    "FacemapSignal",
    # Exceptions
    "FacemapError",
    # Core functions
    "define_rois",
    "import_facemap_output",
    "compute_facemap_signals",
    "align_facemap_to_timebase",
    "validate_facemap_sampling_rate",
]
