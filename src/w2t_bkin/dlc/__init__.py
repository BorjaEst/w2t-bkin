"""DLC (DeepLabCut) inference module.

This module provides low-level primitives for running DeepLabCut model inference
on video files. It follows the 3-tier architecture:

- **Low-level**: Functions accept primitives only (Path, int, bool, List)
- **No Config/Session**: Never imports config, Session, or Manifest
- **Module-local models**: Owns DLCInferenceOptions, DLCInferenceResult, DLCModelInfo

**Key Features**:
- Batch processing: Single DLC call for multiple videos (optimal GPU utilization)
- GPU auto-detection: Automatic GPU selection with manual override support
- Partial failure handling: Gracefully handle individual video failures in batch
- Idempotency: Content-addressed outputs, skip inference if unchanged

**Architecture**:
- ``dlc/core.py``: Low-level inference functions
- ``dlc/models.py``: Module-local data models
- ``dlc/__init__.py``: Public API surface

Requirements:
    - FR-5: Optional pose estimation
    - NFR-1: Determinism (idempotent outputs)
    - NFR-2: Performance (batch processing)

Example:
    >>> from w2t_bkin.dlc import run_dlc_inference_batch, DLCInferenceOptions
    >>> from pathlib import Path
    >>>
    >>> videos = [Path("cam0.mp4"), Path("cam1.mp4")]
    >>> model_config = Path("models/dlc_model/config.yaml")
    >>> output_dir = Path("output/dlc")
    >>>
    >>> options = DLCInferenceOptions(gputouse=0, save_as_csv=False)
    >>> results = run_dlc_inference_batch(videos, model_config, output_dir, options)
    >>>
    >>> for result in results:
    ...     if result.success:
    ...         print(f"Success: {result.h5_output_path}")
    ...     else:
    ...         print(f"Failed: {result.error_message}")
"""

from w2t_bkin.dlc.core import DLCInferenceError, auto_detect_gpu, predict_output_paths, run_dlc_inference_batch, validate_dlc_model
from w2t_bkin.dlc.models import DLCInferenceOptions, DLCInferenceResult, DLCModelInfo

__all__ = [
    # Exception
    "DLCInferenceError",
    # Models
    "DLCInferenceOptions",
    "DLCInferenceResult",
    "DLCModelInfo",
    # Functions
    "run_dlc_inference_batch",
    "validate_dlc_model",
    "predict_output_paths",
    "auto_detect_gpu",
]
