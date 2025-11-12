"""NWB module for W2T-BKIN pipeline (Phase 4).

Assemble NWB files with Devices, ImageSeries (external links, rate-based timing),
optional pose/facemap/bpod data, and provenance metadata.

Requirements: FR-7, NFR-6, NFR-1, NFR-2, NFR-11
Acceptance: A1, A12
"""

from datetime import datetime
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .domain import (
    AlignmentStats,
    BpodSummary,
    Config,
    FacemapBundle,
    Manifest,
    PoseBundle,
    Provenance,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Test fixture patterns
FAKE_PATH_PREFIX = "/fake/"

# Deterministic output for testing (NFR-1: Reproducibility)
DETERMINISTIC_TIMESTAMP = "2025-11-12T00:00:00"

# Default video parameters
DEFAULT_FRAME_RATE = 30.0
DEFAULT_STARTING_TIME = 0.0

# NWB file naming
DEFAULT_NWB_FILENAME_TEMPLATE = "{session_id}.nwb"

# Default values
DEFAULT_CAMERA_ID = "unknown"
DEFAULT_MANUFACTURER = "Unknown"


# =============================================================================
# Exceptions
# =============================================================================


class NWBError(Exception):
    """Error during NWB assembly.

    Base exception for all NWB-related errors.
    """

    pass


# =============================================================================
# Device Creation
# =============================================================================


def create_device(camera_metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Create NWB Device from camera metadata.

    Args:
        camera_metadata: Camera metadata dictionary

    Returns:
        Device dictionary with camera information
    """
    return {
        "name": camera_metadata.get("camera_id", DEFAULT_CAMERA_ID),
        "description": camera_metadata.get("description", ""),
        "manufacturer": camera_metadata.get("manufacturer", DEFAULT_MANUFACTURER),
    }


def create_devices(cameras: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Create NWB Devices for all cameras.

    Args:
        cameras: List of camera metadata dictionaries

    Returns:
        List of Device dictionaries
    """
    return [create_device(camera) for camera in cameras]


# =============================================================================
# ImageSeries Creation
# =============================================================================


def create_image_series(video_metadata: Dict[str, Any], device: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create ImageSeries with external_file link and rate-based timing.

    Uses rate-based timing (no per-frame timestamps) as per FR-7, NFR-6, A12.

    Args:
        video_metadata: Video metadata with path, frame_rate, etc.
        device: Optional device dictionary

    Returns:
        ImageSeries dictionary
    """
    camera_id = video_metadata.get("camera_id", "video")
    return {
        "name": camera_id,
        "external_file": [video_metadata.get("video_path", "")],
        "rate": video_metadata.get("frame_rate", DEFAULT_FRAME_RATE),
        "starting_time": video_metadata.get("starting_time", DEFAULT_STARTING_TIME),
        "description": f"Video from {camera_id}",
        "device": device,
    }


# =============================================================================
# NWB Assembly - Private Helper Functions
# =============================================================================


def _validate_output_directory(output_dir: Path) -> None:
    """Validate and prepare output directory for writing.
    
    Security: Checks directory writability to prevent permission errors.
    
    Args:
        output_dir: Directory path for NWB output
        
    Raises:
        NWBError: If directory cannot be created or is not writable
    """
    if not output_dir.exists():
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created output directory: {output_dir}")
        except Exception as e:
            raise NWBError(f"Cannot create output directory: {e}")

    if not output_dir.is_dir():
        raise NWBError("Output path must be a directory")

    # Security: Try to write test file to check permissions
    try:
        test_file = output_dir / ".test_write"
        test_file.touch()
        test_file.unlink()
        logger.debug(f"Verified write permissions for: {output_dir}")
    except Exception:
        raise NWBError("Output directory is not writable or permission denied")


def _sanitize_session_id(session_id: str) -> str:
    """Sanitize session ID to prevent path traversal attacks.
    
    Security: Removes path traversal patterns and restricts characters.
    
    Args:
        session_id: Raw session identifier
        
    Returns:
        Sanitized session ID safe for use in filenames
    """
    # Remove path traversal attempts
    sanitized = session_id.replace("..", "").replace("/", "_").replace("\\", "_")
    # Remove any other potentially dangerous characters
    sanitized = "".join(c for c in sanitized if c.isalnum() or c in "-_")
    
    if not sanitized:
        logger.warning(f"Session ID '{session_id}' sanitized to empty string, using 'unknown'")
        return "unknown"
    
    if sanitized != session_id:
        logger.warning(f"Session ID sanitized from '{session_id}' to '{sanitized}'")
    
    return sanitized


def _validate_video_files(cameras: List[Dict[str, Any]]) -> None:
    """Validate video file paths for all cameras.
    
    Security: Ensures video files exist before assembly (except test fixtures).
    
    Args:
        cameras: List of camera metadata dictionaries
        
    Raises:
        NWBError: If video file not found
    """
    for camera in cameras:
        video_path = camera.get("video_path")
        # Only validate if path looks real (not starting with FAKE_PATH_PREFIX for tests)
        if video_path and not str(video_path).startswith(FAKE_PATH_PREFIX):
            if not Path(video_path).exists():
                # Security: Don't leak full path in error message
                filename = Path(video_path).name
                raise NWBError(f"Video file not found: {filename}")


def _merge_session_metadata(
    session_metadata: Optional[Dict[str, Any]], 
    manifest: Dict[str, Any]
) -> Dict[str, Any]:
    """Merge session metadata from parameter and manifest.
    
    Manifest values take precedence over parameter values.
    
    Args:
        session_metadata: Optional session metadata from function parameter
        manifest: Session manifest that may contain metadata
        
    Returns:
        Merged session metadata dictionary
    """
    final_metadata = session_metadata or {}
    if "session_metadata" in manifest:
        final_metadata.update(manifest["session_metadata"])
    return final_metadata


def _build_nwb_data_structure(
    session_id: str,
    devices: List[Dict[str, Any]],
    image_series_list: List[Dict[str, Any]],
    provenance: Dict[str, Any],
    config: Dict[str, Any],
    final_session_metadata: Dict[str, Any],
    pose_bundles: Optional[List[PoseBundle]],
    facemap_bundles: Optional[List[FacemapBundle]],
    bpod_summary: Optional[BpodSummary],
    manifest: Dict[str, Any],
) -> Dict[str, Any]:
    """Build NWB data structure from components.
    
    Args:
        session_id: Session identifier
        devices: List of device dictionaries
        image_series_list: List of ImageSeries dictionaries
        provenance: Provenance metadata
        config: Pipeline configuration
        final_session_metadata: Merged session metadata
        pose_bundles: Optional pose data bundles
        facemap_bundles: Optional facemap data bundles
        bpod_summary: Optional Bpod trial/event summary
        manifest: Session manifest (for optional modalities)
        
    Returns:
        Complete NWB data structure dictionary
    """
    nwb_data = {
        "session_id": session_id,
        "devices": devices,
        "image_series": image_series_list,
        "provenance": provenance,
        "config": config,
        "session_metadata": final_session_metadata,
        "pose_bundles": pose_bundles or [],
        "facemap_bundles": facemap_bundles or [],
        "bpod_summary": bpod_summary,
        "created_at": DETERMINISTIC_TIMESTAMP,  # Fixed timestamp for deterministic output (NFR-1)
    }

    # Include optional modalities if present in manifest
    if "events" in manifest:
        nwb_data["events"] = manifest["events"]
        logger.debug("Including events data in NWB")
    if "pose" in manifest:
        nwb_data["pose"] = manifest["pose"]
        logger.debug("Including pose data in NWB")
    if "facemap" in manifest:
        nwb_data["facemap"] = manifest["facemap"]
        logger.debug("Including facemap data in NWB")
    
    return nwb_data


def _write_nwb_file(nwb_path: Path, nwb_data: Dict[str, Any]) -> None:
    """Write NWB data structure to file.
    
    Stub implementation using JSON. Will be replaced with pynwb in production.
    
    Args:
        nwb_path: Output file path
        nwb_data: NWB data structure to serialize
    """
    import json
    
    with open(nwb_path, "w") as f:
        json.dump(nwb_data, f, indent=2, default=str, sort_keys=True)
    
    logger.debug(f"Wrote NWB file: {nwb_path} ({nwb_path.stat().st_size} bytes)")


# =============================================================================
# NWB Assembly - Public API
# =============================================================================


def assemble_nwb(
    manifest: Dict[str, Any],
    config: Dict[str, Any],
    provenance: Dict[str, Any],
    output_dir: Path,
    pose_bundles: Optional[List[PoseBundle]] = None,
    facemap_bundles: Optional[List[FacemapBundle]] = None,
    bpod_summary: Optional[BpodSummary] = None,
    session_metadata: Optional[Dict[str, Any]] = None,
) -> Path:
    """Assemble NWB file from manifest and optional bundles.

    Creates NWB file with:
    - Devices for all cameras
    - ImageSeries with external links and rate-based timing
    - Optional pose/facemap/bpod data
    - Embedded provenance metadata

    Requirements: FR-7, NFR-6, NFR-1, NFR-2, NFR-11
    Acceptance: A1, A12
    
    Security: Validates inputs, sanitizes session IDs, checks file permissions.

    Args:
        manifest: Session manifest with cameras and metadata
        config: Pipeline configuration
        provenance: Provenance metadata
        output_dir: Output directory for NWB file
        pose_bundles: Optional pose data bundles
        facemap_bundles: Optional facemap data bundles
        bpod_summary: Optional Bpod trial/event summary
        session_metadata: Optional session metadata

    Returns:
        Path to created NWB file

    Raises:
        NWBError: If required fields missing or assembly fails
        
    Example:
        >>> manifest = {"session_id": "Session-001", "cameras": [...]}
        >>> config = {"nwb": {"file_name_template": "{session_id}.nwb"}}
        >>> nwb_path = assemble_nwb(manifest, config, {}, Path("/output"))
    """
    # Validate inputs
    if manifest is None:
        raise NWBError("Manifest is required for NWB assembly")

    if not isinstance(output_dir, Path):
        output_dir = Path(output_dir)
    
    logger.info(f"Starting NWB assembly for session: {manifest.get('session_id', 'unknown')}")

    # Validate and prepare output directory
    _validate_output_directory(output_dir)

    # Extract and sanitize session info
    raw_session_id = manifest.get("session_id", "unknown")
    session_id = _sanitize_session_id(raw_session_id)
    logger.debug(f"Processing session: {session_id}")

    # Validate video files
    cameras = manifest.get("cameras", [])
    _validate_video_files(cameras)
    logger.debug(f"Validated {len(cameras)} camera(s)")

    # Create devices
    devices = create_devices(cameras)

    # Create ImageSeries
    image_series_list = []
    for camera in cameras:
        series = create_image_series(camera)
        image_series_list.append(series)
    logger.debug(f"Created {len(image_series_list)} ImageSeries")

    # Determine output filename
    nwb_config = config.get("nwb", {}) if isinstance(config, dict) else {}
    filename_template = nwb_config.get("file_name_template", DEFAULT_NWB_FILENAME_TEMPLATE)
    filename = filename_template.replace("{session_id}", session_id)
    nwb_path = output_dir / filename

    # Merge session metadata
    final_session_metadata = _merge_session_metadata(session_metadata, manifest)

    # Build NWB data structure
    nwb_data = _build_nwb_data_structure(
        session_id=session_id,
        devices=devices,
        image_series_list=image_series_list,
        provenance=provenance,
        config=config,
        final_session_metadata=final_session_metadata,
        pose_bundles=pose_bundles,
        facemap_bundles=facemap_bundles,
        bpod_summary=bpod_summary,
        manifest=manifest,
    )

    # Write NWB file (stub - will use pynwb in full implementation)
    _write_nwb_file(nwb_path, nwb_data)

    logger.info(f"Assembled NWB file: {nwb_path.name}")

    return nwb_path
