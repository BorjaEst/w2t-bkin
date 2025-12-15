"""Validation module for W2T Body Kinematics.

This module implements domain-specific validation logic for the pipeline,
including NWB file inspection and synchronization verification.

It separates validation logic from the main pipeline orchestration,
allowing for better testing and reuse.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List

from w2t_bkin.exceptions import MismatchExceedsToleranceError

logger = logging.getLogger(__name__)


def validate_nwb_file(nwb_path: Path) -> List[Dict[str, Any]]:
    """Validate NWB file using nwbinspector.

    Args:
        nwb_path: Path to NWB file

    Returns:
        List of validation results (serializable dictionaries)
    """
    try:
        from nwbinspector import inspect_nwbfile

        # Run inspection
        results = list(inspect_nwbfile(nwbfile_path=str(nwb_path)))

        # Convert to serializable format
        validation_results = []
        for result in results:
            validation_results.append(
                {
                    "severity": result.severity.name,
                    "check_name": result.check_function_name,
                    "message": result.message,
                    "object_type": result.object_type,
                    "object_name": result.object_name,
                    "location": result.location,
                }
            )

        return validation_results

    except ImportError:
        logger.warning("nwbinspector not available, skipping validation")
        return []
    except Exception as e:
        logger.error(f"NWB validation failed: {e}")
        return []


def verify_sync_counts(
    camera_id: str,
    ttl_id: str,
    frame_count: int,
    pulse_count: int,
    tolerance: int = 0,
) -> None:
    """Verify frame and pulse counts match within tolerance (primitive check).

    Args:
        camera_id: Identifier of the camera
        ttl_id: Identifier of the TTL signal
        frame_count: Number of video frames
        pulse_count: Number of TTL pulses
        tolerance: Allowed difference between counts (default: 0)

    Raises:
        MismatchExceedsToleranceError: If mismatch exceeds tolerance
    """
    mismatch = abs(frame_count - pulse_count)

    if mismatch > tolerance:
        raise MismatchExceedsToleranceError(
            camera_id=camera_id,
            frame_count=frame_count,
            ttl_count=pulse_count,
            mismatch=mismatch,
            tolerance=tolerance,
        )

    logger.info(f"  Verification: '{camera_id}' ↔ '{ttl_id}' matched ({frame_count} frames)")
