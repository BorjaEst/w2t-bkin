#!/usr/bin/env python3
"""Example: DLC Batch Inference.

Demonstrates low-level DLC inference API for batch processing multiple
camera videos with GPU optimization.

Key Features
------------
- Validates DLC model before inference
- Predicts output paths following DLC naming convention
- Batch processes all videos in single GPU call (2-3x speedup)
- Handles GPU selection (manual, auto-detect, CPU fallback)
- Graceful error handling for partial failures

Usage
-----
Basic (auto-detect GPU):
    $ python examples/dlc_inference_batch.py

Force CPU mode:
    $ python examples/dlc_inference_batch.py --cpu

Specify GPU:
    $ python examples/dlc_inference_batch.py --gpu 0

Custom model and videos:
    $ python examples/dlc_inference_batch.py \
        --model /path/to/dlc/config.yaml \
        --videos video1.mp4 video2.mp4 video3.mp4

Architecture
------------
This example uses the LOW-LEVEL DLC API which accepts primitives only:
    - Video paths (List[Path])
    - Model config path (Path)
    - Output directory (Path)
    - Inference options (DLCInferenceOptions dataclass)

For PIPELINE integration, see `examples/pipeline_with_dlc.py`.
"""

import argparse
import logging
from pathlib import Path
import sys
from typing import List

from w2t_bkin.dlc import DLCInferenceOptions, predict_output_paths, run_dlc_inference_batch, validate_dlc_model

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """Run DLC batch inference example."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="DeepLabCut batch inference example",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=Path("models/dlc/BA_W2T_v1/config.yaml"),
        help="Path to DLC model config.yaml (default: models/dlc/BA_W2T_v1/config.yaml)",
    )
    parser.add_argument(
        "--videos",
        type=Path,
        nargs="+",
        help="Video files to process (default: auto-discover cam*.mp4)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/interim/dlc"),
        help="Output directory for H5 files (default: data/interim/dlc)",
    )
    parser.add_argument(
        "--gpu",
        type=int,
        help="GPU index (0, 1, ...). Omit for auto-detect.",
    )
    parser.add_argument(
        "--cpu",
        action="store_true",
        help="Force CPU mode (no GPU)",
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        help="Also save CSV outputs (in addition to H5)",
    )

    args = parser.parse_args()

    # Validate model config
    logger.info(f"Validating DLC model: {args.model}")
    try:
        model_info = validate_dlc_model(args.model)
    except Exception as e:
        logger.error(f"Invalid DLC model: {e}")
        return 1

    logger.info(f"Model validated: {model_info.task}")
    logger.info(f"  Scorer: {model_info.scorer}")
    logger.info(f"  Bodyparts: {', '.join(model_info.bodyparts)}")
    logger.info(f"  Num outputs: {model_info.num_outputs}")

    # Discover or use provided videos
    if args.videos:
        video_paths = args.videos
    else:
        # Auto-discover cam*.mp4 in current directory
        video_paths = sorted(Path.cwd().glob("cam*.mp4"))
        if not video_paths:
            logger.error("No videos found. Use --videos to specify files.")
            return 1

    logger.info(f"Found {len(video_paths)} video(s) to process")

    # Predict output paths
    args.output.mkdir(parents=True, exist_ok=True)
    logger.info("Predicted output paths:")
    for video_path in video_paths:
        paths = predict_output_paths(video_path, model_info, args.output, save_csv=args.csv)
        logger.info(f"  {video_path.name} -> {paths['h5'].name}")
        if args.csv:
            logger.info(f"    (CSV: {paths['csv'].name})")

    # Configure GPU selection
    if args.cpu:
        gputouse = -1
        logger.info("Using CPU mode (--cpu specified)")
    elif args.gpu is not None:
        gputouse = args.gpu
        logger.info(f"Using GPU {gputouse} (--gpu specified)")
    else:
        gputouse = None  # Auto-detect
        logger.info("Using auto-detect GPU mode")

    # Create inference options
    options = DLCInferenceOptions(
        gputouse=gputouse,
        save_as_csv=args.csv,
        allow_growth=True,  # Enable GPU memory growth
        allow_fallback=True,  # Fallback to CPU on GPU OOM
        batch_size=None,  # Use DLC default
    )

    # Run batch inference
    logger.info("Starting DLC batch inference...")
    try:
        results = run_dlc_inference_batch(video_paths, args.model, args.output, options)
    except Exception as e:
        logger.error(f"DLC inference failed: {e}")
        return 1

    # Report results
    success_count = sum(r.success for r in results)
    logger.info(f"\nInference complete: {success_count}/{len(results)} successful")

    for result in results:
        if result.success:
            logger.info(f"✓ {result.video_path.name}")
            logger.info(f"    Output: {result.h5_output_path}")
            if result.timing:
                logger.info(f"    Duration: {result.timing:.2f}s")
        else:
            logger.error(f"✗ {result.video_path.name}")
            logger.error(f"    Error: {result.error_message}")

    # Exit with error if any failures
    if success_count < len(results):
        logger.warning(f"{len(results) - success_count} video(s) failed")
        return 1

    logger.info("All videos processed successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
