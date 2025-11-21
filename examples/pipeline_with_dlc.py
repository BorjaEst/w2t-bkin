#!/usr/bin/env python3
"""Example: Pipeline with DLC Inference.

Demonstrates high-level pipeline orchestration with DLC inference enabled.
Shows how Config/Session are owned by orchestration layer, which extracts
primitives and calls low-level DLC API.

Features
--------
- Loads config.toml and session.toml
- Discovers video files via manifest
- Optionally runs DLC batch inference before pose import
- Integrates DLC results into pipeline provenance
- Demonstrates Phase 4.1 execution pattern

Usage
-----
Run pipeline with DLC inference enabled:
    $ python examples/pipeline_with_dlc.py --config config.toml --session Session-000001

Skip DLC inference (use existing H5 files):
    $ python examples/pipeline_with_dlc.py --config config.toml --session Session-000001 --skip-dlc

Configuration
-------------
In config.toml, enable DLC inference:

    [labels.dlc]
    run_inference = true
    model = "BA_W2T_v1"
    gputouse = 0  # GPU index, -1 for CPU, None for auto-detect

Architecture
------------
This example demonstrates the ORCHESTRATION pattern:
1. Load Config and Session (high-level only)
2. Build Manifest (discovers files, counts frames)
3. Extract primitives from Session:
   - Video paths: manifest.cameras[i].video_files
   - Model config: models_root / config.labels.dlc.model / "config.yaml"
   - Output directory: intermediate_root / session_id / "dlc"
   - GPU selection: config.labels.dlc.gputouse
4. Call low-level API: run_dlc_inference_batch(video_paths, model_config, output_dir, options)
5. Update provenance with DLC results

Compare with examples/dlc_inference_batch.py which uses low-level API directly.
"""

import argparse
import json
import logging
from pathlib import Path
import sys
from typing import Optional

from w2t_bkin.config import load_and_validate_config
from w2t_bkin.dlc import DLCInferenceOptions, run_dlc_inference_batch, validate_dlc_model
from w2t_bkin.ingest import build_and_count_manifest

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def run_dlc_phase(
    config,
    session,
    manifest,
    skip_inference: bool = False,
) -> Optional[dict]:
    """Execute DLC inference phase (Phase 4.1).

    Args:
        config: Validated Config object
        session: Validated Session object
        manifest: Session manifest with discovered files
        skip_inference: Skip DLC inference if True

    Returns:
        Dict with DLC results for provenance, or None if skipped

    Architecture:
        This function is HIGH-LEVEL ORCHESTRATION - it owns Config/Session
        and extracts primitives to call the low-level DLC API.
    """
    # Check if DLC inference is enabled
    if not config.labels.dlc.run_inference:
        logger.info("DLC inference disabled in config (labels.dlc.run_inference=false)")
        return None

    if skip_inference:
        logger.info("DLC inference skipped (--skip-dlc specified)")
        return None

    logger.info("=== Phase 4.1: DLC Inference ===")

    # Extract primitives from Config/Session (orchestration pattern)
    session_id = session.session.id
    models_root = Path(config.paths.models_root)
    intermediate_root = Path(config.paths.intermediate_root)
    model_name = config.labels.dlc.model

    if not model_name:
        logger.warning("DLC model not specified (labels.dlc.model is empty)")
        return None

    # Build model config path
    model_config_path = models_root / model_name / "config.yaml"
    if not model_config_path.exists():
        logger.error(f"DLC model config not found: {model_config_path}")
        return None

    # Validate model before inference
    try:
        model_info = validate_dlc_model(model_config_path)
        logger.info(f"DLC model validated: {model_info.task}")
        logger.info(f"  Bodyparts: {', '.join(model_info.bodyparts)}")
    except Exception as e:
        logger.error(f"Invalid DLC model: {e}")
        return None

    # Extract video paths from manifest
    video_paths = []
    for camera in manifest.cameras:
        video_paths.extend(camera.video_files)

    if not video_paths:
        logger.warning("No videos found in manifest for DLC inference")
        return None

    logger.info(f"Processing {len(video_paths)} video(s) with DLC")

    # Create output directory
    output_dir = intermediate_root / session_id / "dlc"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create inference options from config
    options = DLCInferenceOptions(
        gputouse=config.labels.dlc.gputouse,  # From config.toml
        save_as_csv=False,  # H5 only (pose import reads H5)
        allow_growth=True,
        allow_fallback=True,
    )

    logger.info(f"GPU mode: {options.gputouse}")
    logger.info(f"Output directory: {output_dir}")

    # Execute batch inference (low-level API)
    try:
        dlc_results = run_dlc_inference_batch(video_paths, model_config_path, output_dir, options)
    except Exception as e:
        logger.error(f"DLC inference failed: {e}")
        return None

    # Report results
    success_count = sum(r.success for r in dlc_results)
    total_time = sum(r.timing or 0.0 for r in dlc_results)

    logger.info(f"DLC inference complete: {success_count}/{len(dlc_results)} successful")
    logger.info(f"Total time: {total_time:.2f}s")

    # Log failures
    for result in dlc_results:
        if not result.success:
            logger.error(f"✗ {result.video_path.name}: {result.error_message}")

    # Build provenance data
    provenance = {
        "model": model_name,
        "scorer": model_info.scorer,
        "bodyparts": model_info.bodyparts,
        "gpu_mode": options.gputouse,
        "videos_processed": len(dlc_results),
        "videos_successful": success_count,
        "total_time_s": total_time,
        "outputs": [
            {
                "video": str(r.video_path),
                "h5_output": str(r.h5_output_path),
                "success": r.success,
                "timing": r.timing,
            }
            for r in dlc_results
        ],
    }

    return provenance


def main():
    """Run pipeline with DLC inference."""
    parser = argparse.ArgumentParser(
        description="Pipeline with DLC inference example",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to config.toml",
    )
    parser.add_argument(
        "--session",
        type=str,
        required=True,
        help="Session ID (e.g., Session-000001)",
    )
    parser.add_argument(
        "--skip-dlc",
        action="store_true",
        help="Skip DLC inference (use existing H5 files)",
    )

    args = parser.parse_args()

    # Load and validate config
    logger.info(f"Loading config: {args.config}")
    try:
        config = load_and_validate_config(args.config)
    except Exception as e:
        logger.error(f"Config validation failed: {e}")
        return 1

    # Build manifest (discovers files, counts frames)
    logger.info(f"Building manifest for session: {args.session}")
    try:
        # Note: In real pipeline, session.toml would be loaded here
        # For this example, we simulate with config only
        manifest = build_and_count_manifest(config, session_id=args.session)
    except Exception as e:
        logger.error(f"Manifest build failed: {e}")
        return 1

    logger.info(f"Manifest: {len(manifest.cameras)} camera(s), " f"{sum(len(c.video_files) for c in manifest.cameras)} video(s)")

    # Run DLC inference phase
    # Note: In real pipeline, Session would be passed here
    dlc_provenance = run_dlc_phase(
        config=config,
        session=None,  # Would be actual Session object
        manifest=manifest,
        skip_inference=args.skip_dlc,
    )

    if dlc_provenance:
        logger.info("\n=== DLC Provenance ===")
        print(json.dumps(dlc_provenance, indent=2))

        # In real pipeline, this would be merged into full provenance
        provenance_path = Path("data/processed") / args.session / "dlc_provenance.json"
        provenance_path.parent.mkdir(parents=True, exist_ok=True)
        with open(provenance_path, "w") as f:
            json.dump(dlc_provenance, f, indent=2)
        logger.info(f"Provenance saved to: {provenance_path}")

    logger.info("\nPipeline complete!")
    logger.info("Next steps:")
    logger.info("  1. Run pose import to load DLC H5 files")
    logger.info("  2. Continue with sync, events, and NWB assembly")

    return 0


if __name__ == "__main__":
    sys.exit(main())
