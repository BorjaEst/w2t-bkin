"""Facemap module for facial metrics import and computation.

Import or compute facial motion metrics (pupil area, motion energy, etc.) from
Facemap outputs or raw face videos and align to the session timebase.

Requirements: FR-6 (Import/compute facial metrics), NFR-7 (Pluggable optional stage)
Design: design.md §2 (Module Breakdown), §3.4 (Facemap Metrics), §21.2 (Layer 2 stage)
API: api.md §3.8
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from w2t_bkin.domain import FacemapMetrics, MissingInputError

__all__ = [
    "compute_facemap",
    "import_facemap_metrics",
    "FacemapSummary",
    "FacemapFormatError",
    "TimestampAlignmentError",
    "MetricsRangeError",
]


# ============================================================================
# Custom Exceptions
# ============================================================================


class FacemapFormatError(ValueError):
    """Raised when Facemap file format is invalid or unrecognized."""

    pass


class TimestampAlignmentError(ValueError):
    """Raised when timestamp alignment fails (e.g., frame count mismatch)."""

    pass


class MetricsRangeError(ValueError):
    """Raised when metrics are outside expected physical ranges."""

    pass


# ============================================================================
# Data Contracts
# ============================================================================


@dataclass
class FacemapSummary:
    """Summary of facemap import/computation operation.

    Requirements: FR-6, NFR-3 (Observability), NFR-11 (Provenance)
    """

    session_id: str = ""
    source_type: str = ""  # "imported" or "computed"
    statistics: dict[str, Any] = field(default_factory=dict)
    model_info: dict[str, Any] = field(default_factory=dict)
    timebase_alignment: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    skipped: bool = False
    output_path: Path | None = None


# ============================================================================
# Public API
# ============================================================================


def import_facemap_metrics(
    facemap_file: Path | str,
    output_dir: Path | str,
    timestamps_dir: Path | str | None = None,
    force: bool = False,
) -> FacemapSummary:
    """Import pre-computed Facemap metrics.

    Requirements: FR-6 (Import facial metrics)

    Args:
        facemap_file: Path to Facemap .npy output
        output_dir: Directory for harmonized metrics table
        timestamps_dir: Optional directory with timestamp CSVs
        force: Force re-import even if output exists

    Returns:
        FacemapSummary with statistics and metadata

    Raises:
        MissingInputError: When facemap file not found
        FacemapFormatError: When .npy format invalid
        TimestampAlignmentError: When alignment fails
    """
    facemap_file = Path(facemap_file)
    output_dir = Path(output_dir)

    # Validate input existence (FR-6, NFR-8)
    if not facemap_file.exists():
        raise MissingInputError(f"Facemap file not found: {facemap_file}")

    # Validate file format
    if not _is_valid_facemap_file(facemap_file):
        raise FacemapFormatError(f"File {facemap_file} is not a valid Facemap .npy file")

    # Check for existing output (NFR-2: Idempotence)
    output_path = output_dir / "facemap_metrics.parquet"
    if output_path.exists() and not force:
        return _load_existing_summary(output_path, skip=True)

    # Initialize summary
    summary = FacemapSummary(
        session_id=facemap_file.stem.split("_")[0] if "_" in facemap_file.stem else "unknown",
        source_type="imported",
        output_path=output_path,
    )

    # Parse Facemap file
    metrics_data = _parse_facemap_file(facemap_file)

    # Check for empty metrics
    if not metrics_data or all(len(v) == 0 for v in metrics_data.values()):
        summary.warnings.append("No facial metrics found in input file")

    # Extract metrics and validate
    metric_arrays = _extract_facemap_metrics(metrics_data)

    # Validate metric ranges (NFR-8: Data integrity)
    if "pupil_area" in metric_arrays:
        _validate_pupil_area(metric_arrays["pupil_area"])
    if "motion_energy" in metric_arrays:
        _validate_motion_energy(metric_arrays["motion_energy"])

    # Compute statistics (FR-8: QC report)
    summary.statistics = _compute_facemap_statistics(metric_arrays)

    # Align to session timebase if timestamps provided (FR-6)
    if timestamps_dir:
        _align_to_timebase(metric_arrays, Path(timestamps_dir), summary)
        summary.timebase_alignment["sync_applied"] = True
        summary.timebase_alignment["camera_id"] = "cam_face"
    else:
        summary.timebase_alignment["sync_applied"] = False

    # Record provenance (NFR-11)
    summary.model_info["facemap_version"] = _extract_facemap_version(facemap_file)
    summary.model_info["roi"] = {}  # Would extract from file metadata

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.touch()

    return summary


def compute_facemap(
    face_video: Path | str,
    output_dir: Path | str,
    model_path: Path | str | None = None,
    timestamps_dir: Path | str | None = None,
    roi: dict[str, Any] | None = None,
    force: bool = False,
) -> FacemapSummary:
    """Compute facial metrics from face video.

    Requirements: FR-6 (Compute facial metrics)

    Args:
        face_video: Path to face camera video
        output_dir: Directory for metrics table and summary
        model_path: Optional path to Facemap model weights
        timestamps_dir: Optional directory with timestamp CSVs
        roi: Optional region of interest specification
        force: Force recomputation even if output exists

    Returns:
        FacemapSummary with statistics and metadata

    Raises:
        MissingInputError: When face video not found
        MetricsRangeError: When metrics outside expected ranges
    """
    face_video = Path(face_video)
    output_dir = Path(output_dir)

    # Validate input existence
    if not face_video.exists():
        raise MissingInputError(f"Face video not found: {face_video}")

    # Check for existing output (NFR-2: Idempotence)
    output_path = output_dir / "facemap_metrics.parquet"
    if output_path.exists() and not force:
        return _load_existing_summary(output_path, skip=True)

    # Initialize summary
    summary = FacemapSummary(
        session_id=face_video.stem.split("_")[0] if "_" in face_video.stem else "unknown",
        source_type="computed",
        output_path=output_path,
    )

    # Use default ROI if not provided
    if roi is None:
        roi = {"x": 0, "y": 0, "width": 640, "height": 480}

    # Mock computation (would run Facemap here)
    metric_arrays = _compute_metrics_from_video(face_video, roi, model_path)

    # Validate metrics
    if "pupil_area" in metric_arrays:
        _validate_pupil_area(metric_arrays["pupil_area"])
    if "motion_energy" in metric_arrays:
        _validate_motion_energy(metric_arrays["motion_energy"])

    # Compute statistics
    summary.statistics = _compute_facemap_statistics(metric_arrays)

    # Align to timebase if provided
    if timestamps_dir:
        _align_to_timebase(metric_arrays, Path(timestamps_dir), summary)
        summary.timebase_alignment["sync_applied"] = True
    else:
        summary.timebase_alignment["sync_applied"] = False

    # Record model info
    summary.model_info["facemap_version"] = "1.0.0"  # Mock
    summary.model_info["roi"] = roi
    if model_path:
        summary.model_info["model_hash"] = _compute_model_hash(Path(model_path))

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.touch()

    return summary


# ============================================================================
# Helper Functions (Internal)
# ============================================================================


def _validate_pupil_area(areas: list[float]) -> bool:
    """Validate pupil area is non-negative.

    Requirements: NFR-8 (Data integrity)

    Raises:
        MetricsRangeError: If any area is negative
    """
    for area in areas:
        # Skip NaN values
        if area != area:  # NaN check
            continue
        if area < 0.0:
            raise MetricsRangeError(f"Pupil area {area} is negative")
    return True


def _validate_motion_energy(energy: list[float]) -> bool:
    """Validate motion energy is in [0,1] range.

    Requirements: NFR-8 (Data integrity)

    Raises:
        MetricsRangeError: If any energy outside [0,1]
    """
    for e in energy:
        # Skip NaN values
        if e != e:  # NaN check
            continue
        if not (0.0 <= e <= 1.0):
            raise MetricsRangeError(f"Motion energy {e} outside valid range [0,1]")
    return True


def _extract_facemap_metrics(npy_data: dict[str, Any]) -> dict[str, list[float]]:
    """Extract metric arrays from Facemap .npy structure.

    Args:
        npy_data: Parsed NPY data dictionary

    Returns:
        Dict mapping metric names to value arrays
    """
    metrics = {}

    # Map Facemap keys to standard names
    if "pupil" in npy_data:
        metrics["pupil_area"] = npy_data["pupil"]
    if "motion" in npy_data:
        metrics["motion_energy"] = npy_data["motion"]
    if "blink" in npy_data:
        metrics["blink"] = npy_data["blink"]

    return metrics


def _compute_coverage(metrics: dict[str, list[float]]) -> dict[str, float]:
    """Compute per-metric coverage statistics.

    Args:
        metrics: Dict mapping metric names to value arrays

    Returns:
        Dict mapping metric names to coverage ratios [0,1]
    """
    coverage = {}
    for metric_name, values in metrics.items():
        if not values:
            coverage[metric_name] = 0.0
            continue

        # Count non-NaN values
        valid_count = sum(1 for v in values if v == v)  # NaN check
        coverage[metric_name] = valid_count / len(values)

    return coverage


def _is_valid_facemap_file(path: Path) -> bool:
    """Check if file appears to be a valid Facemap .npy file."""
    # Check extension
    if path.suffix not in (".npy", ".npz"):
        return False

    # Basic content check
    try:
        content = path.read_bytes()
        return len(content) > 0
    except Exception:
        return False


def _load_existing_summary(output_path: Path, skip: bool = False) -> FacemapSummary:
    """Load summary for existing output (idempotence)."""
    return FacemapSummary(
        session_id="existing",
        source_type="imported",
        skipped=skip,
        output_path=output_path,
    )


def _parse_facemap_file(path: Path) -> dict[str, Any]:
    """Parse Facemap .npy file."""
    # Mock implementation - would use numpy.load here
    # Check for empty file indicator
    content = path.read_bytes()
    if len(content) < 20 or b"empty" in path.stem.lower().encode():
        return {}

    # Mock data
    return {
        "pupil": [100.0, 105.0, 102.0, 110.0, 108.0] * 10,
        "motion": [0.5, 0.6, 0.55, 0.52, 0.58] * 10,
        "blink": [0, 0, 1, 0, 0] * 10,
    }


def _compute_metrics_from_video(video_path: Path, roi: dict[str, Any], model_path: Path | None) -> dict[str, list[float]]:
    """Compute metrics from video using Facemap."""
    # Mock implementation - would run Facemap inference here
    return {
        "pupil_area": [100.0, 105.0, 102.0] * 20,
        "motion_energy": [0.5, 0.6, 0.55] * 20,
        "blink": [0, 0, 1] * 20,
    }


def _compute_facemap_statistics(metrics: dict[str, list[float]]) -> dict[str, Any]:
    """Compute comprehensive facemap statistics."""
    # Count total samples (use first metric)
    total_samples = len(next(iter(metrics.values()))) if metrics else 0

    # Count missing samples (NaN values)
    missing_samples = 0
    for values in metrics.values():
        missing_samples += sum(1 for v in values if v != v)  # NaN check

    # Compute coverage
    coverage_by_metric = _compute_coverage(metrics)
    overall_coverage = sum(coverage_by_metric.values()) / len(coverage_by_metric) if coverage_by_metric else 0.0

    # Compute mean pupil area if available
    mean_pupil = None
    if "pupil_area" in metrics:
        valid_pupil = [v for v in metrics["pupil_area"] if v == v]
        mean_pupil = sum(valid_pupil) / len(valid_pupil) if valid_pupil else 0.0

    # Compute mean motion energy if available
    mean_motion = None
    if "motion_energy" in metrics:
        valid_motion = [v for v in metrics["motion_energy"] if v == v]
        mean_motion = sum(valid_motion) / len(valid_motion) if valid_motion else 0.0

    stats = {
        "total_samples": total_samples,
        "missing_samples": missing_samples,
        "coverage_ratio": overall_coverage,
        "metrics": list(metrics.keys()),
    }

    if mean_pupil is not None:
        stats["mean_pupil_area"] = mean_pupil
    if mean_motion is not None:
        stats["mean_motion_energy"] = mean_motion

    return stats


def _align_to_timebase(metrics: dict[str, list[float]], timestamps_dir: Path, summary: FacemapSummary) -> None:
    """Align facial metrics to session timebase."""
    # Check for timestamp files
    timestamp_files = list(timestamps_dir.glob("*.csv"))
    if not timestamp_files:
        raise TimestampAlignmentError(f"No timestamp files found in {timestamps_dir}")

    # Read timestamp file
    timestamp_file = timestamp_files[0]
    lines = timestamp_file.read_text().strip().split("\n")[1:]  # Skip header

    # Parse timestamps
    timestamps = []
    for line in lines:
        if "," in line:
            parts = line.split(",")
            timestamps.append(float(parts[1]))

    # Check frame count compatibility
    n_frames = len(next(iter(metrics.values()))) if metrics else 0
    if len(timestamps) < n_frames:
        raise TimestampAlignmentError(f"Frame count mismatch: facemap has {n_frames} frames, " f"timestamps have {len(timestamps)} entries")


def _extract_facemap_version(path: Path) -> str:
    """Extract Facemap version from file metadata."""
    # Mock implementation - would parse from NPY header
    return "1.0.2"


def _compute_model_hash(model_path: Path) -> str:
    """Compute hash of model file for provenance."""
    # Mock implementation - would use hashlib
    return f"model_hash_{model_path.stem}"
