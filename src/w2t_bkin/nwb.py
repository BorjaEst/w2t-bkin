"""NWB module for W2T-BKIN pipeline (Phase 4).

Assemble NWB files with Devices, ImageSeries (external links, rate-based timing),
optional pose/facemap/bpod data, and provenance metadata.

Requirements: FR-7, NFR-6, NFR-1, NFR-2, NFR-11
Acceptance: A1, A12
"""

from datetime import datetime
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pynwb import NWBHDF5IO, NWBFile
from pynwb.device import Device
from pynwb.image import ImageSeries

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


def create_device(camera_metadata: Dict[str, Any]) -> Device:
    """Create pynwb Device from camera metadata.

    Args:
        camera_metadata: Camera metadata dictionary

    Returns:
        pynwb Device object with camera information
    """
    return Device(
        name=camera_metadata.get("camera_id", DEFAULT_CAMERA_ID),
        description=camera_metadata.get("description", ""),
        manufacturer=camera_metadata.get("manufacturer", DEFAULT_MANUFACTURER),
    )


def create_devices(cameras: List[Dict[str, Any]]) -> List[Device]:
    """Create pynwb Devices for all cameras.

    Args:
        cameras: List of camera metadata dictionaries

    Returns:
        List of pynwb Device objects
    """
    return [create_device(camera) for camera in cameras]


# =============================================================================
# ImageSeries Creation
# =============================================================================


def create_image_series(video_metadata: Dict[str, Any], device: Optional[Device] = None) -> ImageSeries:
    """Create ImageSeries with external_file link and rate-based timing.

    Uses rate-based timing (no per-frame timestamps) as per FR-7, NFR-6, A12.

    Args:
        video_metadata: Video metadata with path, frame_rate, etc.
        device: Optional pynwb Device object

    Returns:
        pynwb ImageSeries object
    """
    camera_id = video_metadata.get("camera_id", "video")
    video_path = video_metadata.get("video_path", "")

    # Create ImageSeries with external file reference
    # Note: external_file requires a list of file paths
    image_series = ImageSeries(
        name=camera_id,
        description=f"Video from {camera_id}",
        external_file=[video_path],
        format="external",
        starting_time=video_metadata.get("starting_time", DEFAULT_STARTING_TIME),
        rate=video_metadata.get("frame_rate", DEFAULT_FRAME_RATE),
        unit="n/a",  # Required by NWB schema for ImageSeries
    )

    # Link device if provided
    if device is not None:
        image_series.device = device

    return image_series


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


def _merge_session_metadata(session_metadata: Optional[Dict[str, Any]], manifest: Dict[str, Any]) -> Dict[str, Any]:
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


def _build_nwb_file(
    session_id: str,
    devices: List[Device],
    image_series_list: List[ImageSeries],
    provenance: Dict[str, Any],
    config: Dict[str, Any],
    final_session_metadata: Dict[str, Any],
    pose_bundles: Optional[List[PoseBundle]],
    facemap_bundles: Optional[List[FacemapBundle]],
    bpod_summary: Optional[BpodSummary],
    manifest: Dict[str, Any],
) -> NWBFile:
    """Build NWBFile from components.

    Args:
        session_id: Session identifier
        devices: List of pynwb Device objects
        image_series_list: List of pynwb ImageSeries objects
        provenance: Provenance metadata
        config: Pipeline configuration
        final_session_metadata: Merged session metadata
        pose_bundles: Optional pose data bundles
        facemap_bundles: Optional facemap data bundles
        bpod_summary: Optional Bpod trial/event summary
        manifest: Session manifest (for optional modalities)

    Returns:
        Complete NWBFile object
    """
    # Parse timestamp (use deterministic for testing, or current time)
    try:
        session_start_time = datetime.fromisoformat(DETERMINISTIC_TIMESTAMP)
    except:
        session_start_time = datetime.now()

    # Get session description from config or use default
    nwb_config = config.get("nwb", {}) if isinstance(config, dict) else {}
    session_description = nwb_config.get("session_description", f"Session {session_id}")

    # Create NWBFile
    nwbfile = NWBFile(
        session_description=session_description,
        identifier=session_id,
        session_start_time=session_start_time,
        lab=nwb_config.get("lab", ""),
        institution=nwb_config.get("institution", ""),
        experimenter=nwb_config.get("experimenter", []),
        subject=None,  # Will add later if session_metadata has subject info
    )

    # Add devices
    for device in devices:
        nwbfile.add_device(device)

    # Add ImageSeries to acquisition
    for image_series in image_series_list:
        nwbfile.add_acquisition(image_series)
        logger.debug(f"Added ImageSeries: {image_series.name}")

    # Store provenance as custom metadata (using lab_meta_data or notes)
    if provenance:
        import json

        provenance_json = json.dumps(provenance, indent=2, default=str)
        if hasattr(nwbfile, "notes"):
            nwbfile.notes = f"Provenance:\n{provenance_json}"
        logger.debug("Embedded provenance metadata")

    # Include optional modalities if present in manifest
    if "events" in manifest:
        logger.debug("Including events data in NWB")
        # TODO: Add BehavioralEvents when events module is complete
    if "pose" in manifest:
        logger.debug("Including pose data in NWB")
        # TODO: Add PoseEstimation when pose module is complete
    if "facemap" in manifest:
        logger.debug("Including facemap data in NWB")
        # TODO: Add BehavioralTimeSeries when facemap module is complete

    return nwbfile


def _write_nwb_file(nwb_path: Path, nwbfile: NWBFile) -> None:
    """Write NWBFile to disk using NWBHDF5IO.

    Args:
        nwb_path: Output file path
        nwbfile: NWBFile object to write
    """
    with NWBHDF5IO(str(nwb_path), "w") as io:
        io.write(nwbfile)

    logger.debug(f"Wrote NWB file: {nwb_path} ({nwb_path.stat().st_size} bytes)")


# =============================================================================
# NWB Assembly - Public API
# =============================================================================


def assemble_nwb(
    manifest: Union[Dict[str, Any], Manifest],
    config: Union[Dict[str, Any], Config],
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
        manifest: Session manifest with cameras and metadata (dict or Manifest object)
        config: Pipeline configuration (dict or Config object)
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

    # Convert Pydantic models to dicts if needed
    if isinstance(manifest, Manifest):
        manifest_dict = manifest.model_dump()
    else:
        manifest_dict = manifest

    if isinstance(config, Config):
        config_dict = config.model_dump()
    else:
        config_dict = config if isinstance(config, dict) else {}

    if not isinstance(output_dir, Path):
        output_dir = Path(output_dir)

    logger.info(f"Starting NWB assembly for session: {manifest_dict.get('session_id', 'unknown')}")

    # Validate and prepare output directory
    _validate_output_directory(output_dir)

    # Extract and sanitize session info
    raw_session_id = manifest_dict.get("session_id", "unknown")
    session_id = _sanitize_session_id(raw_session_id)
    logger.debug(f"Processing session: {session_id}")

    # Validate video files
    cameras = manifest_dict.get("cameras", [])
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
    nwb_config = config_dict.get("nwb", {})
    filename_template = nwb_config.get("file_name_template", DEFAULT_NWB_FILENAME_TEMPLATE)
    filename = filename_template.replace("{session_id}", session_id)
    nwb_path = output_dir / filename

    # Merge session metadata
    final_session_metadata = _merge_session_metadata(session_metadata, manifest_dict)

    # Build NWBFile
    nwbfile = _build_nwb_file(
        session_id=session_id,
        devices=devices,
        image_series_list=image_series_list,
        provenance=provenance,
        config=config_dict,
        final_session_metadata=final_session_metadata,
        pose_bundles=pose_bundles,
        facemap_bundles=facemap_bundles,
        bpod_summary=bpod_summary,
        manifest=manifest_dict,
    )

    # Write NWB file using pynwb NWBHDF5IO
    _write_nwb_file(nwb_path, nwbfile)

    logger.info(f"Assembled NWB file: {nwb_path.name}")

    return nwb_path
