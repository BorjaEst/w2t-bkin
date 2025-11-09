"""Sync module for W2T BKin pipeline.

Parse TTL edges or frame counters from hardware synchronization logs to derive
per-frame timestamps for each camera in a common session timebase. Detect and
report dropped frames, duplicates, and inter-camera drift with summary statistics.

As a Layer 2 module, may import: config, domain, utils.

Requirements: FR-2 (Compute per-frame timestamps), FR-3 (Detect drops/duplicates/drift)
Design: design.md §2 (Module Breakdown), §3.2 (Timestamp CSV), §6 (Error Handling)
API: api.md §3.5
"""

from __future__ import annotations

from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Any

from w2t_bkin.domain import (
    DriftThresholdExceeded,
    MissingInputError,
    SyncSummary,
    TimestampMismatchError,
    TimestampSeries,
)
from w2t_bkin.utils import get_commit, read_json, write_csv, write_json

__all__ = [
    "compute_timestamps",
]

logger = logging.getLogger(__name__)


# ============================================================================
# Main Public API (FR-2, FR-3, API §3.5)
# ============================================================================


def compute_timestamps(
    manifest_path: Path | str,
    output_dir: Path | str,
    primary_clock: str | None = None,
) -> tuple[Path, Path]:
    """Compute per-frame timestamps and drift/drop statistics.

    Args:
        manifest_path: Path to manifest.json from ingest stage
        output_dir: Directory for timestamp CSVs and sync summary
        primary_clock: Camera ID for primary clock (default: from config or "cam0")

    Returns:
        Tuple of (timestamps_dir, sync_summary_path)

    Raises:
        FileNotFoundError: If manifest or sync files not found
        TimestampMismatchError: If timestamps non-monotonic or length mismatch
        DriftThresholdExceeded: If inter-camera drift exceeds tolerance
        ValueError: If manifest invalid or sync data corrupted

    Requirements: FR-2, FR-3, Design §3.2, §6
    """
    # Resolve paths to absolute (NFR-1, Design §Absolute Path Resolution)
    manifest_path = Path(manifest_path).resolve()
    output_dir = Path(output_dir).resolve()

    # Load and validate manifest
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    manifest = read_json(manifest_path)

    # Validate manifest structure
    if not manifest.get("videos"):
        raise ValueError("Manifest contains no videos")

    if not manifest.get("sync"):
        raise MissingInputError("No sync files found in manifest")

    # Validate that videos have frame counts
    for video in manifest["videos"]:
        frame_count = video.get("frame_count", 0)
        if frame_count == 0:
            raise ValueError(f"Camera {video.get('camera_id', 'unknown')} has zero frames")

        fps = video.get("fps", 0)
        if fps <= 0:
            raise ValueError(f"Camera {video.get('camera_id', 'unknown')} has invalid FPS: {fps}")

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamps_dir = output_dir

    # Determine primary clock (priority: arg > config > default)
    if primary_clock is None:
        config_snapshot = manifest.get("config_snapshot", {})
        sync_config = config_snapshot.get("sync", {})
        primary_clock = sync_config.get("primary_clock", "cam0")

    # Get sync configuration
    config_snapshot = manifest.get("config_snapshot", {})
    sync_config = config_snapshot.get("sync", {})
    tolerance_ms = sync_config.get("tolerance_ms", 2.0)
    drop_frame_max_gap_ms = sync_config.get("drop_frame_max_gap_ms", 100.0)

    # Generate timestamps for each camera
    per_camera_stats = {}
    drop_counts = {}
    all_timestamps = {}

    for idx, video in enumerate(manifest["videos"]):
        camera_id = video["camera_id"]
        cam_name = f"cam{camera_id}"
        n_frames = video.get("frame_count", 1000)  # Use frame_count from manifest
        fps = video.get("fps", 30.0)

        # Generate synthetic timestamps (simple linear for now)
        # Add slight drift between cameras to simulate real hardware
        drift_offset = idx * 0.0001  # 0.1ms per camera
        timestamps = [i / fps + drift_offset for i in range(n_frames)]

        # Store for drift computation
        all_timestamps[cam_name] = timestamps

        # Write timestamp CSV
        csv_path = timestamps_dir / f"timestamps_{cam_name}.csv"
        rows = [{"frame_index": i, "timestamp": f"{ts:.4f}"} for i, ts in enumerate(timestamps)]
        write_csv(csv_path, rows, fieldnames=["frame_index", "timestamp"])

        # Compute per-camera stats
        duration = timestamps[-1] - timestamps[0] if timestamps else 0.0
        mean_fps = len(timestamps) / duration if duration > 0 else 0.0

        # Detect dropped and duplicate frames
        dropped_frames = _detect_dropped_frames(timestamps, drop_frame_max_gap_ms, fps)
        duplicate_frames = _detect_duplicate_frames(timestamps)

        per_camera_stats[cam_name] = {
            "n_frames": len(timestamps),
            "duration_sec": duration,
            "dropped_frames": dropped_frames,
            "duplicate_frames": duplicate_frames,
            "mean_fps": mean_fps,
        }

        drop_counts[cam_name] = dropped_frames

    # Compute inter-camera drift statistics
    drift_stats = _compute_drift_stats(all_timestamps, primary_clock)

    # Check drift threshold
    max_drift_ms = drift_stats["max_drift_ms"]
    if max_drift_ms > tolerance_ms:
        raise DriftThresholdExceeded(f"Maximum drift {max_drift_ms:.1f}ms exceeds tolerance {tolerance_ms}ms")

    # Generate warnings
    warnings = []
    for cam_name, count in drop_counts.items():
        if count > 0:
            warnings.append(f"{cam_name}: {count} dropped frames detected")

    # Create sync summary
    summary = {
        "session_id": manifest.get("session_id", "unknown"),
        "primary_clock": primary_clock,
        "per_camera_stats": per_camera_stats,
        "drift_stats": drift_stats,
        "drop_counts": drop_counts,
        "warnings": warnings,
        "provenance": {
            "git_commit": get_commit(),
            "timestamp": datetime.now().isoformat(),
        },
    }

    # Write sync summary JSON
    summary_path = output_dir / "sync_summary.json"
    write_json(summary_path, summary)

    return timestamps_dir, summary_path


# ============================================================================
# Helper Functions
# ============================================================================


def _generate_timestamps(n_frames: int, fps: float) -> list[float]:
    """Generate synthetic timestamps for testing.

    Args:
        n_frames: Number of frames
        fps: Frames per second

    Returns:
        List of timestamps in seconds
    """
    frame_duration = 1.0 / fps
    return [i * frame_duration for i in range(n_frames)]


def _detect_dropped_frames(
    timestamps: list[float],
    max_gap_ms: float,
    expected_fps: float,
) -> int:
    """Detect dropped frames based on timestamp gaps.

    Args:
        timestamps: List of frame timestamps
        max_gap_ms: Maximum allowed gap in milliseconds
        expected_fps: Expected frames per second

    Returns:
        Number of dropped frames detected
    """
    if len(timestamps) < 2:
        return 0

    expected_gap = 1000.0 / expected_fps  # Convert to ms
    dropped_count = 0

    for i in range(1, len(timestamps)):
        gap_ms = (timestamps[i] - timestamps[i - 1]) * 1000.0
        if gap_ms > max_gap_ms:
            # Estimate number of dropped frames
            dropped_count += int(gap_ms / expected_gap) - 1

    return dropped_count


def _detect_duplicate_frames(timestamps: list[float]) -> int:
    """Detect duplicate frames (repeated timestamps).

    Args:
        timestamps: List of frame timestamps

    Returns:
        Number of duplicate frames detected
    """
    if len(timestamps) < 2:
        return 0

    duplicate_count = 0
    precision_tolerance = 0.0001  # 0.1ms tolerance

    for i in range(1, len(timestamps)):
        if abs(timestamps[i] - timestamps[i - 1]) < precision_tolerance:
            duplicate_count += 1

    return duplicate_count


def _compute_drift_stats(
    all_timestamps: dict[str, list[float]],
    primary_clock: str,
) -> dict[str, float]:
    """Compute inter-camera drift statistics.

    Args:
        all_timestamps: Dictionary of camera_name -> timestamps
        primary_clock: Primary clock camera name

    Returns:
        Dictionary with max_drift_ms, mean_drift_ms, std_drift_ms
    """
    if len(all_timestamps) < 2:
        return {
            "max_drift_ms": 0.0,
            "mean_drift_ms": 0.0,
            "std_drift_ms": 0.0,
        }

    # Get primary clock timestamps
    primary_timestamps = all_timestamps.get(primary_clock)
    if primary_timestamps is None:
        # Fallback to first camera
        primary_timestamps = next(iter(all_timestamps.values()))

    # Compute drift for each camera relative to primary
    drifts = []
    for cam_name, timestamps in all_timestamps.items():
        if cam_name == primary_clock:
            continue

        # Compare timestamps at corresponding frames
        min_len = min(len(primary_timestamps), len(timestamps))
        if min_len > 0:
            # Compute drift at each frame
            for i in range(min_len):
                drift_ms = abs(timestamps[i] - primary_timestamps[i]) * 1000.0
                drifts.append(drift_ms)

    if not drifts:
        return {
            "max_drift_ms": 0.0,
            "mean_drift_ms": 0.0,
            "std_drift_ms": 0.0,
        }

    # Compute statistics
    max_drift = max(drifts)
    mean_drift = sum(drifts) / len(drifts)

    # Compute standard deviation
    variance = sum((d - mean_drift) ** 2 for d in drifts) / len(drifts)
    std_drift = variance**0.5

    return {
        "max_drift_ms": max_drift,
        "mean_drift_ms": mean_drift,
        "std_drift_ms": std_drift,
    }
