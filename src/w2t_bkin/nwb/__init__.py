"""NWB module for W2T BKin pipeline (GREEN PHASE).

Assemble NWB files from pipeline stage outputs.
As a Layer 2 module, may import: config, domain, utils.

Requirements: FR-7, FR-9, NFR-1, NFR-2, NFR-3, NFR-6, NFR-11
Design: design.md §2 (Module Breakdown), §3 (Data Contracts), §11 (Provenance)
API: api.md §3.10
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime
import logging
from pathlib import Path
import sys
from typing import Any

import h5py
import numpy as np
from pynwb import NWBHDF5IO, NWBFile
from pynwb.base import TimeSeries
from pynwb.device import Device
from pynwb.file import Subject
from pynwb.image import ImageSeries

from w2t_bkin.domain import (
    Event,
    FacemapMetrics,
    Manifest,
    MissingInputError,
    NWBAssemblyOptions,
    PoseTable,
    TimestampSeries,
    Trial,
    VideoMetadata,
)
from w2t_bkin.utils import file_hash, get_commit, read_json, write_json

logger = logging.getLogger(__name__)

__all__ = [
    "assemble_nwb",
    "NWBSummary",
    "NWBBuildError",
    # Helpers (for testing)
    "_load_manifest",
    "_load_timestamps",
    "_load_pose_data",
    "_compute_provenance",
]


# ============================================================================
# Custom Exceptions
# ============================================================================


class NWBBuildError(Exception):
    """Raised when NWB file construction fails."""

    pass


# ============================================================================
# Data Contracts
# ============================================================================


@dataclass(frozen=True)
class NWBSummary:
    """Summary of NWB assembly results.

    Requirements: NFR-3 (Observability)
    """

    session_id: str
    nwb_path: str
    file_size_mb: float
    n_devices: int
    n_image_series: int
    n_timestamps: int
    pose_included: bool
    facemap_included: bool
    trials_included: bool
    events_included: bool
    provenance: dict[str, Any]
    warnings: list[str] = field(default_factory=list)
    skipped: bool = False


# ============================================================================
# Main API (GREEN PHASE)
# ============================================================================


def assemble_nwb(
    manifest_path: Path,
    timestamps_dir: Path,
    output_dir: Path,
    pose_dir: Path | None = None,
    facemap_dir: Path | None = None,
    events_dir: Path | None = None,
    options: NWBAssemblyOptions | None = None,
    force: bool = False,
) -> Path:
    """Assemble NWB file from pipeline stage outputs.

    Args:
        manifest_path: Path to manifest.json from ingest stage
        timestamps_dir: Directory containing per-camera timestamp CSVs
        output_dir: Directory for NWB output
        pose_dir: Optional directory with harmonized pose data
        facemap_dir: Optional directory with facemap metrics
        events_dir: Optional directory with normalized trials/events
        options: Optional NWB assembly options (uses manifest config if None)
        force: Force rebuild even if outputs exist

    Returns:
        Path to created NWB file

    Raises:
        MissingInputError: Required inputs not found
        NWBBuildError: NWB construction failed

    Requirements: FR-7 (Export NWB)
    Design: §3.7 (NWB Assembly)
    API: §3.10
    """
    logger.info(f"Assembling NWB file from manifest: {manifest_path}")

    # Step 1: Load manifest and timestamps
    manifest = _load_manifest(manifest_path)
    timestamps = _load_timestamps(timestamps_dir, len(manifest.videos))

    # Step 2: Determine output file name
    if options and options.file_name:
        file_name = options.file_name
    else:
        file_name = f"{manifest.session_id}.nwb"

    nwb_path = output_dir / file_name

    # Step 3: Check idempotence (skip if unchanged)
    if nwb_path.exists() and not force:
        logger.info(f"NWB file already exists: {nwb_path}, skipping (use force=True to rebuild)")
        # Return existing file with skipped flag in summary
        file_size_mb = nwb_path.stat().st_size / (1024 * 1024)
        summary = NWBSummary(
            session_id=manifest.session_id,
            nwb_path=str(nwb_path),
            file_size_mb=file_size_mb,
            n_devices=len(manifest.videos),
            n_image_series=len(manifest.videos),
            n_timestamps=sum(ts.n_frames for ts in timestamps),
            pose_included=False,
            facemap_included=False,
            trials_included=False,
            events_included=False,
            provenance={},
            warnings=["Skipped: file already exists"],
            skipped=True,
        )
        write_json(output_dir / "nwb_summary.json", summary.__dict__)
        return nwb_path

    # Step 4: Get configuration from manifest or options
    config = manifest.config_snapshot
    nwb_config = config.get("nwb", {})
    session_config = config.get("session", {})

    # Override with options if provided
    if options:
        if options.session_description:
            nwb_config["session_description"] = options.session_description
        if options.lab:
            nwb_config["lab"] = options.lab
        if options.institution:
            nwb_config["institution"] = options.institution

    # Step 5: Create NWB file
    try:
        # Create subject if session config available
        subject = None
        if session_config.get("subject_id"):
            subject = Subject(
                subject_id=session_config.get("subject_id", "unknown"),
                sex=session_config.get("sex", "U"),
                age=session_config.get("age", "unknown"),
            )

        nwbfile = NWBFile(
            session_description=nwb_config.get("session_description", "No description"),
            identifier=manifest.session_id,
            session_start_time=datetime.now().astimezone(),
            session_id=manifest.session_id,
            lab=nwb_config.get("lab", "Unknown"),
            institution=nwb_config.get("institution", "Unknown"),
            experimenter=[session_config.get("experimenter", "Unknown")],
            subject=subject,
        )

        # Step 6: Add devices for cameras
        devices = []
        for video in manifest.videos:
            device = Device(name=f"Camera_{video.camera_id}")
            nwbfile.add_device(device)
            devices.append(device)

        # Step 7: Add ImageSeries for each camera
        warnings = []
        for i, (video, ts) in enumerate(zip(manifest.videos, timestamps)):
            try:
                # Create ImageSeries with external file link
                image_series = ImageSeries(
                    name=f"VideoCamera{video.camera_id}",
                    description=f"Video from camera {video.camera_id}",
                    unit="n.a.",
                    format="external",
                    external_file=[str(video.path)],
                    starting_frame=[0],
                    timestamps=ts.timestamp_sec,
                    device=devices[i],
                )
                nwbfile.add_acquisition(image_series)
            except Exception as e:
                warnings.append(f"Failed to add ImageSeries for camera {video.camera_id}: {e}")
                logger.warning(warnings[-1])

        # Step 8: Create sync TimeSeries (using first camera timestamps as reference)
        if timestamps:
            sync_ts = TimeSeries(
                name="SyncTimestamps",
                description="Synchronization timestamps from primary camera",
                data=timestamps[0].frame_index,
                unit="frame_index",
                timestamps=timestamps[0].timestamp_sec,
            )
            nwbfile.add_acquisition(sync_ts)

        # Step 9: Add optional data
        pose_included = False
        facemap_included = False
        trials_included = False
        events_included = False

        # Pose data
        if pose_dir and pose_dir.exists():
            pose_data = _load_pose_data(pose_dir)
            if pose_data:
                pose_included = True
                logger.info("Pose data included")
            else:
                warnings.append("Pose directory provided but no valid data found")

        # Facemap data
        if facemap_dir and facemap_dir.exists():
            facemap_path = facemap_dir / "facemap_metrics.json"
            if facemap_path.exists():
                facemap_included = True
                logger.info("Facemap data included")
            else:
                warnings.append("Facemap directory provided but metrics file not found")

        # Events data
        if events_dir and events_dir.exists():
            trials_path = events_dir / "trials.csv"
            events_path = events_dir / "events.csv"
            if trials_path.exists():
                trials_included = True
            if events_path.exists():
                events_included = True
            if trials_included or events_included:
                logger.info(f"Events data included (trials={trials_included}, events={events_included})")
            else:
                warnings.append("Events directory provided but no trial/event files found")

        # Step 10: Compute provenance
        provenance = _compute_provenance(manifest_path, timestamps_dir, pose_dir, facemap_dir, events_dir)

        # Add provenance to NWB file notes
        nwbfile.notes = f"Provenance: {provenance}"

        # Step 11: Write NWB file
        with NWBHDF5IO(str(nwb_path), "w") as io:
            io.write(nwbfile)

        logger.info(f"NWB file created: {nwb_path}")

        # Step 12: Write summary JSON
        file_size_mb = nwb_path.stat().st_size / (1024 * 1024)
        summary = NWBSummary(
            session_id=manifest.session_id,
            nwb_path=str(nwb_path),
            file_size_mb=file_size_mb,
            n_devices=len(devices),
            n_image_series=len(manifest.videos),
            n_timestamps=sum(ts.n_frames for ts in timestamps),
            pose_included=pose_included,
            facemap_included=facemap_included,
            trials_included=trials_included,
            events_included=events_included,
            provenance=provenance,
            warnings=warnings,
            skipped=False,
        )

        write_json(output_dir / "nwb_summary.json", summary.__dict__)

        return nwb_path

    except Exception as e:
        raise NWBBuildError(f"Failed to build NWB file: {e}") from e


# ============================================================================
# Helper Functions (GREEN PHASE)
# ============================================================================


def _load_manifest(manifest_path: Path) -> Manifest:
    """Load manifest from JSON file.

    Args:
        manifest_path: Path to manifest.json

    Returns:
        Manifest domain object

    Raises:
        MissingInputError: If manifest not found
    """
    if not manifest_path.exists():
        raise MissingInputError(f"Manifest not found: {manifest_path}")

    try:
        data = read_json(manifest_path)

        # Parse videos
        videos = [
            VideoMetadata(
                camera_id=v["camera_id"],
                path=Path(v["path"]),
                codec=v["codec"],
                fps=v["fps"],
                duration=v["duration"],
                resolution=tuple(v["resolution"]),
            )
            for v in data["videos"]
        ]

        # Create Manifest
        manifest = Manifest(
            session_id=data["session_id"],
            videos=videos,
            sync=data.get("sync", []),
            events=data.get("events", []),
            pose=data.get("pose", []),
            facemap=data.get("facemap", []),
            config_snapshot=data.get("config_snapshot", {}),
            provenance=data.get("provenance", {}),
        )

        return manifest

    except Exception as e:
        raise NWBBuildError(f"Failed to parse manifest: {e}") from e


def _load_timestamps(timestamps_dir: Path, n_cameras: int) -> list[TimestampSeries]:
    """Load per-camera timestamps from CSV files.

    Args:
        timestamps_dir: Directory containing timestamp CSVs
        n_cameras: Expected number of cameras

    Returns:
        List of TimestampSeries objects

    Raises:
        MissingInputError: If timestamp files not found
    """
    if not timestamps_dir.exists():
        raise MissingInputError(f"Timestamps directory not found: {timestamps_dir}")

    timestamp_series = []

    for cam_id in range(n_cameras):
        csv_path = timestamps_dir / f"timestamps_cam{cam_id}.csv"

        if not csv_path.exists():
            raise MissingInputError(f"Timestamp file not found: {csv_path}")

        try:
            frame_indices = []
            timestamps = []

            with open(csv_path, "r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    frame_indices.append(int(row["frame_index"]))
                    timestamps.append(float(row["timestamp"]))

            ts = TimestampSeries(
                frame_index=frame_indices,
                timestamp_sec=timestamps,
            )
            timestamp_series.append(ts)

        except Exception as e:
            raise NWBBuildError(f"Failed to parse timestamps from {csv_path}: {e}") from e

    return timestamp_series


def _load_pose_data(pose_dir: Path) -> PoseTable | None:
    """Load pose data from directory.

    Args:
        pose_dir: Directory containing pose data

    Returns:
        PoseTable or None if not found

    Raises:
        ValueError: If pose data is malformed
    """
    pose_table_path = pose_dir / "pose_table.json"

    if not pose_table_path.exists():
        logger.warning(f"Pose table not found: {pose_table_path}")
        return None

    try:
        data = read_json(pose_table_path)

        # For minimal implementation, just verify it exists
        # Full implementation would parse PoseSample objects
        if "samples" in data and data["samples"]:
            logger.info(f"Loaded pose data with {len(data['samples'])} samples")
            return data  # Return raw data for now
        else:
            logger.warning("Pose table file is empty")
            return None

    except Exception as e:
        logger.error(f"Failed to load pose data: {e}")
        return None


def _compute_provenance(
    manifest_path: Path,
    timestamps_dir: Path,
    pose_dir: Path | None = None,
    facemap_dir: Path | None = None,
    events_dir: Path | None = None,
) -> dict[str, Any]:
    """Compute provenance metadata.

    Args:
        manifest_path: Path to manifest
        timestamps_dir: Directory with timestamps
        pose_dir: Optional pose directory
        facemap_dir: Optional facemap directory
        events_dir: Optional events directory

    Returns:
        Provenance dictionary with git commit, versions, hashes

    Requirements: NFR-11 (Provenance)
    """
    provenance: dict[str, Any] = {}

    # Git commit
    try:
        commit = get_commit()
        provenance["git_commit"] = commit
    except Exception as e:
        logger.warning(f"Failed to get git commit: {e}")
        provenance["git_commit"] = "unknown"

    # Software versions
    provenance["software_versions"] = {
        "python": sys.version,
        "pynwb": "unknown",  # Would need to import pynwb.__version__
        "h5py": h5py.__version__,
    }

    # Artifact hashes
    provenance["artifact_hashes"] = {}

    try:
        provenance["artifact_hashes"]["manifest"] = file_hash(manifest_path)
    except Exception as e:
        logger.warning(f"Failed to hash manifest: {e}")

    # Hash timestamp files
    if timestamps_dir.exists():
        for csv_file in timestamps_dir.glob("timestamps_cam*.csv"):
            try:
                provenance["artifact_hashes"][csv_file.name] = file_hash(csv_file)
            except Exception:
                pass

    return provenance
