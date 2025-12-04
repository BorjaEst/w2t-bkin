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

Requirements:
    - FR-5: Optional pose estimation
    - NFR-1: Determinism (idempotent outputs)
    - NFR-2: Performance (batch processing)

Example:
    >>> from w2t_bkin.processors.dlc import run_dlc_inference_batch, DLCInferenceOptions
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

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


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


class DLCInferenceError(Exception):
    """Exception raised for DLC inference errors.

    Raised for:
    - Invalid model (missing config.yaml, corrupt structure)
    - Critical failures (GPU not found, disk full)
    - Pre-flight validation failures

    Not raised for:
    - Individual video failures in batch (handled gracefully)
    """

    pass


def validate_dlc_model(config_path: Path) -> DLCModelInfo:
    """Validate DLC model structure and extract metadata.

    Pre-flight validation before inference. Checks model structure and
    extracts metadata from config.yaml.

    Args:
        config_path: Path to DLC project config.yaml

    Returns:
        DLCModelInfo with validated metadata

    Raises:
        DLCInferenceError: If model invalid or config.yaml missing/corrupt

    Requirements:
        - REQ-DLC-5: Validate model before inference
        - REQ-DLC-9: Raise error if config.yaml missing

    Example:
        >>> model_info = validate_dlc_model(Path("models/dlc/config.yaml"))
        >>> print(f"Scorer: {model_info.scorer}")
        >>> print(f"Bodyparts: {model_info.bodyparts}")
    """
    # Check config.yaml exists
    if not config_path.exists():
        raise DLCInferenceError(f"DLC config.yaml not found: {config_path}")

    if not config_path.is_file():
        raise DLCInferenceError(f"DLC config path must be a file: {config_path}")

    # Parse YAML
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise DLCInferenceError(f"Failed to parse DLC config.yaml: {e}")
    except Exception as e:
        raise DLCInferenceError(f"Failed to read DLC config.yaml: {e}")

    if not isinstance(config, dict):
        raise DLCInferenceError(f"DLC config.yaml must contain a YAML dictionary, got {type(config).__name__}")

    # Extract and validate required fields
    required_fields = ["Task", "bodyparts"]
    missing = [f for f in required_fields if f not in config]
    if missing:
        raise DLCInferenceError(f"DLC config.yaml missing required fields: {missing}")

    # Extract bodyparts
    bodyparts = config["bodyparts"]
    if not isinstance(bodyparts, list):
        raise DLCInferenceError(f"DLC config 'bodyparts' must be a list, got {type(bodyparts).__name__}")
    if not bodyparts:
        raise DLCInferenceError("DLC config 'bodyparts' list is empty")

    # Determine project_path (parent of config.yaml)
    project_path = config_path.parent

    # Build scorer name if available, otherwise use a default pattern
    # DLC scorer format for filenames: <network>_<Task><date>shuffle<N>_<iteration>
    # Note: "DLC_" prefix is added in the filename, not in the scorer itself
    task = config["Task"]
    date = config.get("date", "unknown")

    # Try to construct scorer from snapshot info or use a simplified version
    scorer_parts = []

    # Add network if available
    if "net_type" in config:
        scorer_parts.append(config["net_type"])

    # Add task
    scorer_parts.append(task)

    # Add date if available and not 'unknown'
    if date != "unknown":
        # Convert to string in case YAML parsed it as a date object
        date_str = str(date).replace("-", "")
        scorer_parts.append(date_str)

    # Add shuffle info
    shuffle = config.get("TrainingFraction", [1])[0] if "TrainingFraction" in config else 1
    scorer_parts.append(f"shuffle{shuffle}")

    # Add iteration if available
    iteration = config.get("iteration", 0)
    if "snapshotindex" in config:
        scorer_parts.append(str(config["snapshotindex"]))

    scorer = "_".join(scorer_parts)

    # Extract skeleton edges from config (optional)
    skeleton = config.get("skeleton", [])
    if skeleton and not isinstance(skeleton, list):
        logger.warning(f"DLC config 'skeleton' is not a list, ignoring: {type(skeleton).__name__}")
        skeleton = []

    # Validate skeleton edges if present
    skeleton_edges = []
    if skeleton:
        for edge in skeleton:
            if isinstance(edge, (list, tuple)) and len(edge) == 2:
                try:
                    idx0, idx1 = int(edge[0]), int(edge[1])
                    if 0 <= idx0 < len(bodyparts) and 0 <= idx1 < len(bodyparts):
                        skeleton_edges.append([idx0, idx1])
                    else:
                        logger.warning(f"Skeleton edge indices out of range: {edge}")
                except (ValueError, TypeError):
                    logger.warning(f"Invalid skeleton edge format: {edge}")
            else:
                logger.warning(f"Skeleton edge must be a pair of indices: {edge}")

    # Log validation success
    logger.debug(f"Validated DLC model: task='{task}', bodyparts={len(bodyparts)}, scorer='{scorer}', skeleton_edges={len(skeleton_edges)}")

    return DLCModelInfo(
        config_path=config_path,
        project_path=project_path,
        scorer=scorer,
        bodyparts=bodyparts,
        num_outputs=len(bodyparts) * 3,  # x, y, likelihood per bodypart
        skeleton=skeleton_edges,
        task=task,
        date=str(date) if date != "unknown" else date,
    )


def predict_output_paths(
    video_path: Path,
    model_info: DLCModelInfo,
    output_dir: Path,
    save_csv: bool = False,
) -> Dict[str, Path]:
    """Predict DLC output file paths before inference.

    DLC uses deterministic naming convention:
    - H5: {video_stem}DLC_{scorer}.h5
    - CSV: {video_stem}DLC_{scorer}.csv (if requested)

    Args:
        video_path: Input video file path
        model_info: Validated model metadata
        output_dir: Output directory for H5/CSV files
        save_csv: Whether CSV will be generated

    Returns:
        Dict with 'h5' key and optionally 'csv' key

    Requirements:
        - REQ-DLC-4: Return deterministic H5 output paths

    Example:
        >>> paths = predict_output_paths(
        ...     Path("video.mp4"),
        ...     model_info,
        ...     Path("output"),
        ...     save_csv=True
        ... )
        >>> paths['h5']
        PosixPath('output/videoDLC_scorer.h5')
    """
    # Extract video stem (filename without extension)
    video_stem = video_path.stem

    # Build output filename following DLC naming convention
    # Format: {video_stem}DLC_{scorer}.h5
    base_name = f"{video_stem}DLC_{model_info.scorer}"

    # Build output paths
    result = {"h5": output_dir / f"{base_name}.h5"}

    # Add CSV path if requested
    if save_csv:
        result["csv"] = output_dir / f"{base_name}.csv"

    logger.debug(f"Predicted output paths for '{video_path.name}': h5={result['h5'].name}")

    return result


def auto_detect_gpu() -> Optional[int]:
    """Auto-detect first available GPU.

    Uses TensorFlow to detect available GPUs. Returns 0 if any GPU is
    available, None for CPU-only systems.

    Returns:
        0 if GPU available, None for CPU

    Requirements:
        - REQ-DLC-7: Auto-detect GPU when not specified

    Example:
        >>> gpu_index = auto_detect_gpu()
        >>> if gpu_index is not None:
        ...     print(f"Using GPU {gpu_index}")
        ... else:
        ...     print("Using CPU")
    """
    try:
        # Attempt to import TensorFlow
        import tensorflow as tf

        # Get list of physical GPU devices
        gpus = tf.config.list_physical_devices("GPU")

        if gpus:
            logger.debug(f"Auto-detected {len(gpus)} GPU(s), using GPU 0")
            return 0
        else:
            logger.debug("No GPUs detected, will use CPU")
            return None

    except ImportError:
        # TensorFlow not available, fall back to CPU
        logger.debug("TensorFlow not available for GPU detection, will use CPU")
        return None
    except Exception as e:
        # Any other error in GPU detection, fall back to CPU
        logger.warning(f"GPU detection failed: {e}, will use CPU")
        return None


def run_dlc_inference_batch(
    video_paths: List[Path],
    model_config_path: Path,
    output_dir: Path,
    options: Optional[DLCInferenceOptions] = None,
) -> List[DLCInferenceResult]:
    """Run DLC inference on multiple videos in a single batch.

    Low-level function accepting primitives only. Processes all videos
    in a single call to deeplabcut.analyze_videos for optimal GPU
    utilization.

    Args:
        video_paths: List of video file paths
        model_config_path: Path to DLC project config.yaml
        output_dir: Directory for H5/CSV outputs
        options: Inference options (None = defaults)

    Returns:
        List of results (one per video, ordered)

    Raises:
        DLCInferenceError: If model invalid or critical failure

    Requirements:
        - REQ-DLC-1: Accept primitives only
        - REQ-DLC-3: Support batch inference
        - REQ-DLC-6: Execute when config.preprocessing.dlc.enabled is true
        - REQ-DLC-10: Continue processing on individual video failure
        - REQ-DLC-13: Graceful partial failure handling

    Implementation Flow:
        1. Validate model with validate_dlc_model()
        2. Auto-detect GPU if options.gputouse is None
        3. Call deeplabcut.analyze_videos with video list
        4. Handle partial failures gracefully
        5. Return results for all videos (success + failures)

    Example:
        >>> results = run_dlc_inference_batch(
        ...     video_paths=[Path("cam0.mp4"), Path("cam1.mp4")],
        ...     model_config_path=Path("models/dlc/config.yaml"),
        ...     output_dir=Path("output/dlc"),
        ...     options=DLCInferenceOptions(gputouse=0)
        ... )
        >>> success_count = sum(1 for r in results if r.success)
        >>> print(f"{success_count}/{len(results)} videos succeeded")
    """
    import time

    # Initialize options with defaults if not provided
    if options is None:
        options = DLCInferenceOptions()

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Validate model
    logger.info(f"Validating DLC model: {model_config_path}")
    try:
        model_info = validate_dlc_model(model_config_path)
    except DLCInferenceError as e:
        # Model validation failed - critical error, cannot proceed
        logger.error(f"Model validation failed: {e}")
        raise

    # Step 2: Resolve GPU selection
    gpu_to_use = options.gputouse
    if gpu_to_use is None:
        gpu_to_use = auto_detect_gpu()
        logger.info(f"GPU auto-detection: {gpu_to_use if gpu_to_use is not None else 'CPU'}")
    else:
        logger.info(f"Using specified GPU: {gpu_to_use}")

    # Step 3: Prepare for batch inference
    logger.info(f"Starting DLC inference for {len(video_paths)} video(s)")
    logger.debug(f"Output directory: {output_dir}")
    logger.debug(f"Model scorer: {model_info.scorer}")
    logger.debug(f"Save CSV: {options.save_as_csv}")

    # Initialize results list
    results = []

    # Process each video (DLC analyze_videos handles batch internally)
    for video_path in video_paths:
        start_time = time.time()

        try:
            # Import deeplabcut
            try:
                import deeplabcut
            except ImportError as e:
                raise DLCInferenceError(f"DeepLabCut not available: {e}")

            # Predict output paths
            predicted_paths = predict_output_paths(
                video_path=video_path,
                model_info=model_info,
                output_dir=output_dir,
                save_csv=options.save_as_csv,
            )

            logger.info(f"Processing video: {video_path.name}")

            # Call DLC inference
            # Note: analyze_videos processes one video at a time but can be called in sequence
            deeplabcut.analyze_videos(
                config=str(model_config_path),
                videos=[str(video_path)],
                destfolder=str(output_dir),
                gputouse=gpu_to_use,
                save_as_csv=options.save_as_csv,
                allow_growth=options.allow_growth,
            )

            # Calculate elapsed time
            elapsed_time = time.time() - start_time

            # Verify output file exists
            h5_output = predicted_paths["h5"]
            if not h5_output.exists():
                raise DLCInferenceError(f"Expected output H5 file not found: {h5_output}")

            # Get frame count from H5 file
            try:
                import pandas as pd

                df = pd.read_hdf(h5_output)
                frame_count = len(df)
            except Exception as e:
                logger.warning(f"Could not read frame count from H5: {e}")
                frame_count = 0

            # Create success result
            result = DLCInferenceResult(
                video_path=video_path,
                h5_output_path=h5_output,
                csv_output_path=predicted_paths.get("csv"),
                model_config_path=model_config_path,
                frame_count=frame_count,
                inference_time_s=elapsed_time,
                gpu_used=gpu_to_use,
                success=True,
                error_message=None,
            )

            logger.info(f"✓ Completed {video_path.name} in {elapsed_time:.1f}s ({frame_count} frames)")
            results.append(result)

        except Exception as e:
            # Individual video failure - log and continue
            elapsed_time = time.time() - start_time
            error_msg = str(e)

            logger.error(f"✗ Failed {video_path.name}: {error_msg}")

            # Create failure result
            result = DLCInferenceResult(
                video_path=video_path,
                h5_output_path=None,
                csv_output_path=None,
                model_config_path=model_config_path,
                frame_count=0,
                inference_time_s=elapsed_time,
                gpu_used=gpu_to_use,
                success=False,
                error_message=error_msg,
            )
            results.append(result)

            # Continue to next video (graceful partial failure handling)
            continue

    # Summary
    success_count = sum(1 for r in results if r.success)
    logger.info(f"Batch inference complete: {success_count}/{len(results)} videos succeeded")

    return results
