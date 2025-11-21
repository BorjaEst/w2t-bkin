"""DLC inference data models.

Module-local models for DLC inference operations. These models are owned by
the dlc module and follow the established pattern:

- Frozen dataclasses (immutable)
- Type-annotated fields
- Comprehensive docstrings
- No external dependencies (except stdlib + pathlib)

Requirements:
    - Architecture: Module-local model ownership pattern
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass(frozen=True)
class DLCInferenceOptions:
    """Configuration options for DLC inference (immutable).

    Attributes:
        gputouse: GPU index to use (0, 1, ...), -1 for CPU, None for auto-detect
        save_as_csv: Also generate CSV output in addition to H5
        allow_growth: Enable TensorFlow GPU memory growth (prevents OOM)
        allow_fallback: Fallback to CPU if GPU fails with OOM
        batch_size: TensorFlow batch size for inference

    Example:
        >>> options = DLCInferenceOptions(gputouse=0, save_as_csv=False)
        >>> options.gputouse
        0
    """

    gputouse: Optional[int] = None
    save_as_csv: bool = False
    allow_growth: bool = True
    allow_fallback: bool = True
    batch_size: int = 1


@dataclass(frozen=True)
class DLCInferenceResult:
    """Result of DLC inference on a single video (immutable).

    Attributes:
        video_path: Input video file path
        h5_output_path: Generated H5 file path (None if failed)
        csv_output_path: Generated CSV file path (None if not requested or failed)
        model_config_path: DLC model config.yaml path used
        frame_count: Number of frames processed
        inference_time_s: Time taken for inference in seconds
        gpu_used: GPU index used (None if CPU)
        success: Whether inference succeeded
        error_message: Error description if failed (None if success)

    Example:
        >>> result = DLCInferenceResult(
        ...     video_path=Path("video.mp4"),
        ...     h5_output_path=Path("videoDLC_scorer.h5"),
        ...     csv_output_path=None,
        ...     model_config_path=Path("model/config.yaml"),
        ...     frame_count=1000,
        ...     inference_time_s=45.2,
        ...     gpu_used=0,
        ...     success=True,
        ...     error_message=None,
        ... )
        >>> result.success
        True
    """

    video_path: Path
    h5_output_path: Optional[Path]
    csv_output_path: Optional[Path]
    model_config_path: Path
    frame_count: int
    inference_time_s: float
    gpu_used: Optional[int]
    success: bool
    error_message: Optional[str] = None


@dataclass(frozen=True)
class DLCModelInfo:
    """Validated DLC model metadata (immutable).

    Extracted from DLC project config.yaml.

    Attributes:
        config_path: Path to config.yaml
        project_path: Parent directory of config.yaml (project root)
        scorer: DLC scorer name from config
        bodyparts: List of bodypart names from config
        num_outputs: Number of output values (len(bodyparts) * 3 for x, y, likelihood)
        skeleton: Skeleton edge pairs from config (list of [node_idx, node_idx] pairs)
        task: DLC task name from config
        date: DLC project date from config

    Example:
        >>> model_info = DLCModelInfo(
        ...     config_path=Path("model/config.yaml"),
        ...     project_path=Path("model"),
        ...     scorer="DLC_resnet50_BA_W2T_cam0shuffle1_150000",
        ...     bodyparts=["nose", "left_ear", "right_ear"],
        ...     num_outputs=9,
        ...     skeleton=[[0, 1], [1, 2]],
        ...     task="BA_W2T_cam0",
        ...     date="2024-01-01",
        ... )
        >>> model_info.num_outputs
        9
    """

    config_path: Path
    project_path: Path
    scorer: str
    bodyparts: List[str]
    num_outputs: int
    skeleton: List[List[int]]
    task: str
    date: str
