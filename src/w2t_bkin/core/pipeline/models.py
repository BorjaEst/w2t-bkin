"""Data models for pipeline execution context and results."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from pynwb import NWBFile

from ... import config as config_pkg

if TYPE_CHECKING:
    from ...figures.profiling import PipelineProfile


@dataclass
class RunOptions:
    """Options for pipeline execution.

    Attributes:
        skip_bpod: Skip Bpod processing (default: False)
        skip_pose: Skip pose processing (default: False)
        skip_ttl: Skip TTL processing (default: False)
        skip_verification: Skip file verification (default: False)
        skip_nwb_validation: Skip NWB validation with nwbinspector (default: False)
        force_overwrite: Overwrite existing output files (default: False)
        verification_tolerance: Optional tolerance for frame/pulse mismatch
        warn_on_mismatch: Warn instead of fail on mismatch
    """

    skip_bpod: bool = False
    skip_pose: bool = False
    skip_ttl: bool = False
    skip_verification: bool = False
    skip_nwb_validation: bool = False
    force_overwrite: bool = False
    verification_tolerance: Optional[int] = None
    warn_on_mismatch: Optional[bool] = None


@dataclass
class RunResult:
    """Result of pipeline execution.

    Attributes:
        nwb_path: Path to written NWB file
        nwbfile: In-memory NWBFile object
        alignment_stats: Synchronization alignment statistics
        validation_results: NWB validation results from nwbinspector
        profile: Pipeline profiling data (timing and phase statistics)
        success: Whether pipeline completed successfully
        error: Error message if failed
    """

    nwb_path: Path
    nwbfile: Optional[NWBFile] = None
    alignment_stats: Optional[Dict[str, Any]] = None
    validation_results: Optional[List[Dict[str, Any]]] = None
    profile: Optional["PipelineProfile"] = None
    success: bool = True
    error: Optional[str] = None


@dataclass
class PipelineContext:
    """Context holding the state of a pipeline execution.

    This object is passed between pipeline phases and accumulates state.
    It is designed to be serializable for distributed execution.
    """

    # Inputs
    config_path: Path
    subject_id: str
    session_id: str
    options: RunOptions

    # State variables (populated during phases)
    config: Optional[config_pkg.Config] = None
    metadata: Optional[Dict[str, Any]] = None
    nwbfile: Optional[NWBFile] = None
    session_dir: Optional[Path] = None

    # Intermediate results
    camera_files: Dict[str, List[Path]] = field(default_factory=dict)
    bpod_files: Dict[str, List[Path]] = field(default_factory=dict)
    ttl_files: Dict[str, List[Path]] = field(default_factory=dict)
    pose_data: Dict[str, Any] = field(default_factory=dict)
    bpod_data: Optional[Dict[str, Any]] = None
    trial_offsets: Optional[Dict[int, float]] = None
    ttl_pulses: Dict[str, List[float]] = field(default_factory=dict)
    alignment_stats: Dict[str, Any] = field(default_factory=dict)
    nwb_path: Optional[Path] = None
    validation_results: Optional[List[Dict[str, Any]]] = None
