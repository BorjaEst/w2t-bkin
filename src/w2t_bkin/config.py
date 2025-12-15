"""Configuration management for W2T-BKIN pipeline.

This module provides Pydantic models for validating configuration files (config.toml)
and functions for loading, validating, and hashing configurations.

The configuration system enforces strict schema validation to catch errors early,
supports deterministic hashing for reproducibility, and provides clear error messages.

Key Configuration Sections:
    - Project: Project identification and metadata
    - Paths: File system paths for data, models, and outputs
    - Synchronization: Hardware sync strategy and alignment settings
    - Preprocessing: Pose estimation (DLC, SLEAP) and other preprocessing tasks
    - Verification: Runtime checks for frame counts and sync validation
    - Video: Video analysis and transcoding settings
    - Bpod: Behavioral trial synchronization mappings
    - NWB: Neurodata Without Borders export configuration
    - QC: Quality control report generation
    - Logging: Log level and format settings

Model Path Resolution:
    Pose estimation model paths in PreprocessingConfig are resolved relative
    to paths.models_root. Use the resolve_model_path() method on DLCConfig
    or SLEAPConfig to get absolute paths.

Typical usage example:
    >>> from w2t_bkin.config import load_config
    >>>
    >>> config = load_config("config.toml")
    >>> print(config.project.name)
    >>> print(config.synchronization.strategy)
    >>>
    >>> # Resolve DLC model path
    >>> if config.preprocessing.dlc.enabled:
    ...     model_path = config.preprocessing.dlc.resolve_model_path(
    ...         config.paths.models_root
    ...     )
    ...     print(f"DLC model: {model_path}")
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # Python < 3.11 fallback

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from w2t_bkin.utils import compute_hash, read_toml, recursive_dict_update

# =============================================================================
# Constants
# =============================================================================

VALID_SYNC_STRATEGIES = frozenset({"rate_based", "hardware_pulse", "network_stream"})
VALID_ALIGNMENT_METHODS = frozenset({"nearest", "linear"})
VALID_LOGGING_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


# =============================================================================
# Configuration Models - Core
# =============================================================================


class ProjectConfig(BaseModel, extra="forbid"):
    """Project identification.

    Attributes:
        name: Project name identifier.
    """

    name: str = Field(..., description="Project name")


class PathsConfig(BaseModel, extra="forbid"):
    """File system paths configuration.

    Attributes:
        raw_root: Path to raw data directory.
        intermediate_root: Path for intermediate processing outputs.
        output_root: Path for final outputs.
        models_root: Directory containing pose estimation models (default: models).
        root_metadata: Optional path to global metadata file outside raw_root.
                      This metadata is loaded first (base layer) and is overridden
                      by any metadata files within raw_root hierarchy.
    """

    raw_root: Path = Field(..., description="Raw data root directory")
    intermediate_root: Path = Field(..., description="Intermediate processing outputs")
    output_root: Path = Field(..., description="Output data root directory")
    models_root: Path = Field(default="models", description="Pose estimation models directory")
    root_metadata: Optional[Path] = Field(None, description="Optional global metadata file (base layer)")

    @model_validator(mode="after")
    def resolve_paths(self) -> "PathsConfig":
        """Resolve all paths to absolute paths.

        Converts relative paths to absolute paths based on current working directory.
        This ensures consistent path handling regardless of execution context.

        Note: If paths are already absolute (e.g., from deployment config), they are
        kept as-is. This allows deployments to pre-resolve paths at deployment time.
        """
        # Only resolve if path is relative
        if not self.raw_root.is_absolute():
            self.raw_root = self.raw_root.resolve()
        if not self.intermediate_root.is_absolute():
            self.intermediate_root = self.intermediate_root.resolve()
        if not self.output_root.is_absolute():
            self.output_root = self.output_root.resolve()
        if not self.models_root.is_absolute():
            self.models_root = self.models_root.resolve()
        if self.root_metadata and not self.root_metadata.is_absolute():
            self.root_metadata = self.root_metadata.resolve()
        return self


class AlignmentConfig(BaseModel, extra="forbid"):
    """Alignment configuration.

    Attributes:
        method: Alignment strategy ("nearest" or "linear").
        tolerance_s: Maximum acceptable jitter in seconds.
        global_offset_s: Global time offset before mapping (default: 0.0).
    """

    method: Literal["nearest", "linear"] = Field(..., description="Alignment strategy")
    tolerance_s: float = Field(..., ge=0.0, description="Max allowed jitter in seconds")
    global_offset_s: float = Field(default=0.0, description="Global offset before mapping")


class SynchronizationConfig(BaseModel, extra="forbid"):
    """Synchronization configuration.

    Attributes:
        strategy: Synchronization strategy ("rate_based", "hardware_pulse", "network_stream").
        reference_channel: Reference channel ID (required for hardware_pulse/network_stream).
        alignment: Alignment configuration.
    """

    strategy: Literal["rate_based", "hardware_pulse", "network_stream"] = Field(..., description="Synchronization strategy")
    reference_channel: Optional[str] = Field(None, description="Reference channel ID (required for hardware_pulse)")
    alignment: AlignmentConfig


class AcquisitionConfig(BaseModel, extra="forbid"):
    """Data acquisition policies.

    Attributes:
        concat_strategy: Video concatenation method (ffconcat or streamlist).
    """

    concat_strategy: Literal["ffconcat", "streamlist"] = Field(default="ffconcat", description="Video concatenation strategy")


class VerificationConfig(BaseModel, extra="forbid"):
    """Hardware synchronization verification.

    Attributes:
        enabled: Master switch to enable/disable all verification checks.
        check_frame_counts: Count and verify video frame counts (slow for large videos).
        check_sync_mismatch: Verify frame/TTL count synchronization.
        skip_nwb_requirements: Skip NWB-required frame counting for multi-file videos (use estimates).
        mismatch_tolerance_frames: Max allowed frame/TTL count mismatch before abort.
        warn_on_mismatch: If True, warn instead of abort when within tolerance.
    """

    enabled: bool = Field(default=True, description="Master switch for all verification checks")
    check_frame_counts: bool = Field(default=True, description="Count video frames (can be slow)")
    check_sync_mismatch: bool = Field(default=True, description="Verify frame/TTL synchronization")
    skip_nwb_requirements: bool = Field(default=False, description="Skip NWB frame count requirements (use FPS estimates)")
    mismatch_tolerance_frames: int = Field(default=0, ge=0, description="Abort if frame_count - ttl_pulse_count > tolerance")
    warn_on_mismatch: bool = Field(default=False, description="Warn instead of abort if within tolerance")


# =============================================================================
# Configuration Models - Bpod
# =============================================================================


class BpodSyncTrialType(BaseModel, extra="forbid"):
    """Bpod trial type synchronization mapping.

    Maps a Bpod trial type to its synchronization signal and TTL channel,
    enabling conversion from Bpod relative timestamps to absolute time.

    Attributes:
        trial_type: Trial type identifier matching Bpod classification.
        sync_signal: Bpod state/event name for alignment (e.g., 'W2T_Audio').
        sync_ttl: TTL channel whose pulses correspond to sync_signal.
    """

    trial_type: int = Field(..., ge=0, description="Trial type identifier")
    sync_signal: str = Field(..., description="Bpod state/event for alignment")
    sync_ttl: str = Field(..., description="TTL channel for sync pulses")


class BpodSyncConfig(BaseModel, extra="forbid"):
    """Bpod-to-TTL synchronization configuration.

    Attributes:
        trial_types: List of trial type sync configurations.
    """

    trial_types: List[BpodSyncTrialType] = Field(default_factory=list, description="Trial type sync configs")


class BpodConfig(BaseModel, extra="forbid"):
    """Bpod behavioral control system configuration.

    Attributes:
        parse: Whether to parse Bpod .mat files.
        sync: Trial synchronization configuration.
    """

    parse: bool = Field(default=True, description="Parse Bpod .mat files if present")
    sync: BpodSyncConfig = Field(default_factory=BpodSyncConfig, description="Trial sync configuration")


# =============================================================================
# Configuration Models - Video
# =============================================================================


class TranscodeConfig(BaseModel, extra="forbid"):
    """Video transcoding settings.

    Attributes:
        enabled: Enable video transcoding.
        codec: FFmpeg codec (e.g., 'h264', 'libx264').
        crf: Constant rate factor quality (0-51, lower is better).
        preset: FFmpeg encoding preset (e.g., 'fast', 'medium').
        keyint: GOP (group of pictures) length.
    """

    enabled: bool = Field(default=True, description="Enable transcoding")
    codec: str = Field(default="h264", description="FFmpeg codec name")
    crf: int = Field(default=20, ge=0, le=51, description="Quality factor (0-51)")
    preset: str = Field(default="fast", description="FFmpeg preset")
    keyint: int = Field(default=15, ge=1, description="GOP length")


class VideoAnalysisConfig(BaseModel, extra="forbid"):
    """Video analysis configuration.

    Attributes:
        frame_count_timeout: Maximum time in seconds for frame counting operations (default: 30).
                             Increase for very long videos that take longer to analyze.
    """

    frame_count_timeout: int = Field(default=30, ge=1, description="Frame counting timeout in seconds")


class VideoConfig(BaseModel, extra="forbid"):
    """Video processing configuration.

    Attributes:
        analysis: Video analysis settings.
        transcode: Transcoding settings.
    """

    analysis: VideoAnalysisConfig = Field(default_factory=VideoAnalysisConfig, description="Analysis config")
    transcode: TranscodeConfig = Field(default_factory=TranscodeConfig, description="Transcoding config")


# =============================================================================
# Configuration Models - Output & Logging
# =============================================================================


class NWBConfig(BaseModel, extra="forbid"):
    """NWB (Neurodata Without Borders) export settings.

    Attributes:
        link_external_video: Use external links for videos instead of embedding.
        lab: Laboratory name.
        institution: Institution name.
        file_name_template: Template for NWB filename.
        session_description_template: Template for session description.
    """

    link_external_video: bool = Field(default=True, description="Link videos externally")
    lab: str = Field(default="Lab Name", description="Lab name")
    institution: str = Field(default="Institution Name", description="Institution name")
    file_name_template: str = Field(default="{session.id}.nwb", description="NWB filename template")
    session_description_template: str = Field(default="Session {session.id} on {session.date}", description="Session description template")


class QCConfig(BaseModel, extra="forbid"):
    """Quality control report configuration.

    Attributes:
        generate_report: Enable QC report generation.
        out_template: Output path template for reports.
        include_verification: Include frame/TTL verification in reports.
    """

    generate_report: bool = Field(default=True, description="Generate QC report")
    out_template: str = Field(default="qc/{session.id}", description="Output path template")
    include_verification: bool = Field(default=True, description="Include verification in report")


class LoggingConfig(BaseModel, extra="forbid"):
    """Logging configuration.

    Attributes:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        structured: Use structured (JSON) logging format.
    """

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(default="INFO", description="Logging level")
    structured: bool = Field(default=False, description="Use structured logging")


# =============================================================================
# Configuration Models - Pose Estimation (Preprocessing)
# =============================================================================


class DLCConfig(BaseModel, extra="forbid"):
    """DeepLabCut pose estimation configuration.

    Controls DLC pose estimation execution and model configuration.
    Model paths are resolved relative to paths.models_root if relative,
    or used as-is if absolute.

    Attributes:
        enabled: Enable DLC pose estimation (default: False).
        model_path: Path to DLC project config.yaml (relative to models_root or absolute).
        gpu: GPU index to use (None = auto-detect, -1 = CPU).
        save_csv: Generate CSV output in addition to H5 (default: False).
    """

    enabled: bool = Field(default=False, description="Enable DLC pose estimation")
    model_path: Optional[Path] = Field(None, description="Path to DLC config.yaml")
    gpu: Optional[int] = Field(None, description="GPU index (None = auto-detect, -1 = CPU)")
    save_csv: bool = Field(default=False, description="Generate CSV outputs")

    def resolve_model_path(self, models_root: Path) -> Optional[Path]:
        """Resolve model_path relative to models_root.

        Args:
            models_root: Base directory for pose estimation models.

        Returns:
            Absolute path to model file, or None if model_path not set.
        """
        if self.model_path is None:
            return None
        if self.model_path.is_absolute():
            return self.model_path
        return (models_root / self.model_path).resolve()


class SLEAPConfig(BaseModel, extra="forbid"):
    """SLEAP pose estimation configuration.

    Controls SLEAP pose estimation execution and model configuration.
    Model paths are resolved relative to paths.models_root if relative,
    or used as-is if absolute.

    Attributes:
        enabled: Enable SLEAP pose estimation (default: False).
        model_path: Path to SLEAP model file (relative to models_root or absolute).
        gpu: GPU index to use (None = auto-detect, -1 = CPU).
    """

    enabled: bool = Field(default=False, description="Enable SLEAP pose estimation")
    model_path: Optional[Path] = Field(None, description="Path to SLEAP model file")
    gpu: Optional[int] = Field(None, description="GPU index (None = auto-detect, -1 = CPU)")

    def resolve_model_path(self, models_root: Path) -> Optional[Path]:
        """Resolve model_path relative to models_root.

        Args:
            models_root: Base directory for pose estimation models.

        Returns:
            Absolute path to model file, or None if model_path not set.
        """
        if self.model_path is None:
            return None
        if self.model_path.is_absolute():
            return self.model_path
        return (models_root / self.model_path).resolve()


class PreprocessingConfig(BaseModel, extra="forbid"):
    """Preprocessing phase configuration.

    Controls preprocessing tasks that generate intermediate artifacts
    stored in the interim folder. Model paths in DLC and SLEAP configs
    are resolved relative to paths.models_root.

    Attributes:
        force_rerun: Force regeneration of all intermediate files (default: False).
        dlc: DLC pose estimation task configuration.
        sleap: SLEAP pose estimation task configuration.
    """

    force_rerun: bool = Field(default=False, description="Force rerun of all preprocessing tasks")
    dlc: DLCConfig = Field(default_factory=DLCConfig, description="DLC pose estimation config")
    sleap: SLEAPConfig = Field(default_factory=SLEAPConfig, description="SLEAP pose estimation config")


# =============================================================================
# Main Configuration Model
# =============================================================================


class Config(BaseModel, extra="forbid"):
    """Main pipeline configuration.

    Root configuration model loaded from config.toml. Uses strict validation
    with extra="forbid" to prevent typos and configuration errors.

    Attributes:
        project: Project identification.
        paths: File system paths.
        synchronization: Synchronization configuration.
        acquisition: Data acquisition policies.
        verification: Hardware sync verification.
        bpod: Bpod behavioral control settings.
        preprocessing: Preprocessing phase configuration.
        video: Video processing configuration.
        nwb: NWB export settings.
        qc: Quality control configuration.
        logging: Logging configuration.
    """

    project: ProjectConfig
    paths: PathsConfig
    synchronization: SynchronizationConfig
    acquisition: AcquisitionConfig = Field(default_factory=AcquisitionConfig)
    verification: VerificationConfig = Field(default_factory=VerificationConfig)
    bpod: BpodConfig = Field(default_factory=BpodConfig)
    preprocessing: PreprocessingConfig = Field(default_factory=PreprocessingConfig)
    video: VideoConfig = Field(default_factory=VideoConfig)
    nwb: NWBConfig = Field(default_factory=NWBConfig)
    qc: QCConfig = Field(default_factory=QCConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


# =============================================================================
# Public API Functions
# =============================================================================
# Configuration Loading
# =============================================================================


def _load_paths_from_env() -> Dict[str, Any]:
    """Load path configuration from environment variables.

    Environment variables override configuration file settings.
    Supported variables:
    - W2T_RAW_ROOT
    - W2T_INTERMEDIATE_ROOT
    - W2T_OUTPUT_ROOT
    - W2T_MODELS_ROOT
    - W2T_ROOT_METADATA
    """
    paths = {}
    if raw := os.getenv("W2T_RAW_ROOT"):
        paths["raw_root"] = raw
    if interim := os.getenv("W2T_INTERMEDIATE_ROOT"):
        paths["intermediate_root"] = interim
    if output := os.getenv("W2T_OUTPUT_ROOT"):
        paths["output_root"] = output
    if models := os.getenv("W2T_MODELS_ROOT"):
        paths["models_root"] = models
    if metadata := os.getenv("W2T_ROOT_METADATA"):
        paths["root_metadata"] = metadata

    return {"paths": paths} if paths else {}


def load_config(path: Union[str, Path]) -> Config:
    """Load and validate configuration from TOML file.

    Performs comprehensive validation including:
    - Schema validation with extra="forbid" to prevent typos
    - Enum validation for strategy, method, and level fields
    - Numeric constraints (e.g., tolerance_s >= 0)
    - Conditional requirements (e.g., reference_channel when strategy='hardware_pulse')
    - Environment variable overrides for paths

    Args:
        path: Path to config.toml file.

    Returns:
        Validated Config instance with all paths resolved to absolute.

    Raises:
        FileNotFoundError: If config file doesn't exist.
        ValidationError: If config violates Pydantic schema.
        ValueError: If enum or conditional validation fails.

    Example:
        >>> config = load_config("config.toml")
        >>> print(config.project.name)
        >>> print(config.synchronization.strategy)
        >>>
        >>> # Access preprocessing config
        >>> if config.preprocessing.dlc.enabled:
        ...     model_path = config.preprocessing.dlc.resolve_model_path(
        ...         config.paths.models_root
        ...     )
    """
    data = read_toml(path)

    # Override with environment variables
    env_paths = _load_paths_from_env()
    if env_paths:
        recursive_dict_update(data, env_paths)

    # Pre-validate enums for clearer error messages
    _validate_config_enums(data)

    # Pre-validate conditional requirements
    _validate_config_conditionals(data)

    return Config(**data)


def load_config_hierarchy(
    base_config: Optional[Union[str, Path]] = None,
    project_config: Optional[Union[str, Path]] = None,
    runtime_config: Optional[Union[str, Path]] = None,
) -> Config:
    """Load and merge configuration from up to 3 hierarchical layers.

    Implements a Base → Project → Runtime layering pattern where each layer
    can override values from previous layers. This enables:
    - Base: Package-level defaults (e.g., configs/standard.toml)
    - Project: User/experiment-specific settings (e.g., data paths)
    - Runtime: Flow/session-specific overrides (e.g., skip flags)

    Configuration dictionaries are merged using deep merge (recursive_dict_update),
    where nested dictionaries are recursively merged rather than replaced.
    Later layers override earlier layers.

    Args:
        base_config: Base/default configuration path (optional).
        project_config: Project-specific configuration path (optional).
        runtime_config: Runtime/session-specific configuration path (optional).

    Returns:
        Validated Config instance with all paths resolved to absolute.

    Raises:
        ValueError: If no config paths are provided.
        FileNotFoundError: If any specified config file doesn't exist.
        ValidationError: If merged config violates Pydantic schema.

    Example:
        >>> # Use only base config
        >>> config = load_config_hierarchy(base_config="configs/standard.toml")
        >>>
        >>> # Override with project settings
        >>> config = load_config_hierarchy(
        ...     base_config="configs/standard.toml",
        ...     project_config="experiments/exp1/config.toml"
        ... )
        >>>
        >>> # Full hierarchy with runtime overrides
        >>> config = load_config_hierarchy(
        ...     base_config="configs/standard.toml",
        ...     project_config="experiments/exp1/config.toml",
        ...     runtime_config="sessions/session-001/overrides.toml"
        ... )
    """
    from w2t_bkin.utils import recursive_dict_update

    # Validate at least one config is provided
    if not any([base_config, project_config, runtime_config]):
        raise ValueError("At least one config path must be provided")

    # Initialize merged dictionary
    merged_dict: Dict[str, Any] = {}

    # Merge layers in order (first to last, later overrides earlier)
    for layer_name, config_path in [
        ("base", base_config),
        ("project", project_config),
        ("runtime", runtime_config),
    ]:
        if config_path is not None:
            try:
                layer_dict = read_toml(config_path)
                recursive_dict_update(merged_dict, layer_dict)
            except FileNotFoundError as e:
                raise FileNotFoundError(f"Config layer '{layer_name}' not found: {config_path}") from e

    # Override with environment variables
    env_paths = _load_paths_from_env()
    if env_paths:
        recursive_dict_update(merged_dict, env_paths)

    # Pre-validate enums for clearer error messages
    _validate_config_enums(merged_dict)

    # Pre-validate conditional requirements
    _validate_config_conditionals(merged_dict)

    # Validate and create Config instance
    return Config(**merged_dict)


def load_config_from_dict(config_dict: Dict[str, Any]) -> Config:
    """Load configuration from a dictionary.

    Useful when configuration is loaded from a source other than a file
    (e.g., environment variable, database).

    Args:
        config_dict: Dictionary containing configuration data.

    Returns:
        Validated Config instance.
    """
    # Pre-validate enums for clearer error messages
    _validate_config_enums(config_dict)

    # Pre-validate conditional requirements
    _validate_config_conditionals(config_dict)

    return Config(**config_dict)


def compute_config_hash(config: Config) -> str:
    """Compute deterministic SHA256 hash of configuration.

    Converts config to canonical dict representation and computes hash.
    Useful for tracking configuration changes and ensuring reproducibility.

    Args:
        config: Config instance to hash.

    Returns:
        SHA256 hex digest (64 characters).

    Example:
        >>> config = load_config("config.toml")
        >>> hash_value = compute_config_hash(config)
        >>> print(f"Config hash: {hash_value[:16]}...")
    """
    config_dict = config.model_dump()
    return compute_hash(config_dict)


# =============================================================================
# Private Validation Helpers
# =============================================================================


def _validate_config_enums(data: Dict[str, Any]) -> None:
    """Validate enum constraints before Pydantic validation.

    Pre-validates enum fields to provide clearer error messages than
    Pydantic's default validation.

    Args:
        data: Raw configuration dict from TOML.

    Raises:
        ValueError: If any enum value is invalid.
    """
    sync = data.get("synchronization", {})
    alignment = sync.get("alignment", {})

    # Validate synchronization.strategy
    strategy = sync.get("strategy")
    if strategy and strategy not in VALID_SYNC_STRATEGIES:
        raise ValueError(f"Invalid synchronization.strategy: '{strategy}'. " f"Must be one of {sorted(VALID_SYNC_STRATEGIES)}")

    # Validate synchronization.alignment.method
    method = alignment.get("method")
    if method and method not in VALID_ALIGNMENT_METHODS:
        raise ValueError(f"Invalid synchronization.alignment.method: '{method}'. " f"Must be one of {sorted(VALID_ALIGNMENT_METHODS)}")

    # Validate tolerance_s >= 0
    tolerance = alignment.get("tolerance_s")
    if tolerance is not None and tolerance < 0:
        raise ValueError(f"Invalid synchronization.alignment.tolerance_s: {tolerance}. " f"Must be >= 0")

    # Validate logging.level
    logging_config = data.get("logging", {})
    level = logging_config.get("level")
    if level and level not in VALID_LOGGING_LEVELS:
        raise ValueError(f"Invalid logging.level: '{level}'. " f"Must be one of {sorted(VALID_LOGGING_LEVELS)}")


def _validate_config_conditionals(data: Dict[str, Any]) -> None:
    """Validate conditional requirements before Pydantic validation.

    Checks that required fields are present based on other field values.

    Args:
        data: Raw configuration dict from TOML.

    Raises:
        ValueError: If conditional requirements are not met.
    """
    sync = data.get("synchronization", {})
    strategy = sync.get("strategy")

    if strategy == "hardware_pulse" and not sync.get("reference_channel"):
        raise ValueError("synchronization.reference_channel is required when synchronization.strategy='hardware_pulse'")

    if strategy == "network_stream" and not sync.get("reference_channel"):
        raise ValueError("synchronization.reference_channel is required when " "synchronization.strategy='network_stream'")


# =============================================================================
# CLI/Testing Entry Point
# =============================================================================

if __name__ == "__main__":
    """Demonstrate configuration loading and validation."""

    print("=" * 70)
    print("Configuration Loading Examples")
    print("=" * 70)
    print()

    # Example 1: Load valid configuration
    print("Example 1: Load and validate config.toml")
    print("-" * 70)

    try:
        config_path = Path("tests/fixtures/configs/valid_config.toml")
        config = load_config(config_path)

        print(f"✓ Loaded: {config_path}")
        print(f"  Project: {config.project.name}")
        print(f"  Strategy: {config.synchronization.strategy}")
        print(f"  Method: {config.synchronization.alignment.method}")
        print(f"  Tolerance: {config.synchronization.alignment.tolerance_s}s")
        print(f"  Logging: {config.logging.level}")

        config_hash = compute_config_hash(config)
        print(f"  Hash: {config_hash[:16]}...")

    except FileNotFoundError as e:
        print(f"✗ File not found: {e}")
        print("  Hint: Run from project root")
    except ValidationError as e:
        print(f"✗ Validation failed:")
        for error in e.errors():
            print(f"  - {error['loc']}: {error['msg']}")
    except ValueError as e:
        print(f"✗ Configuration error: {e}")

    print()

    # Example 2: Demonstrate validation errors
    print("Example 2: Validation error handling")
    print("-" * 70)

    # Invalid enum
    print("\n2a. Invalid synchronization.strategy:")
    try:
        test_data = {
            "project": {"name": "test"},
            "paths": {
                "raw_root": "data/raw",
                "intermediate_root": "data/interim",
                "output_root": "data/processed",
            },
            "synchronization": {
                "strategy": "invalid",
                "alignment": {
                    "method": "nearest",
                    "tolerance_s": 0.01,
                },
            },
        }
        _validate_config_enums(test_data)
    except ValueError as e:
        print(f"  ✓ Caught: {e}")

    # Missing conditional field
    print("\n2b. Missing conditional field (reference_channel):")
    try:
        test_data = {
            "synchronization": {
                "strategy": "hardware_pulse",
                "alignment": {
                    "method": "nearest",
                    "tolerance_s": 0.01,
                },
            }
        }
        _validate_config_conditionals(test_data)
    except ValueError as e:
        print(f"  ✓ Caught: {e}")

    # Invalid numeric constraint
    print("\n2c. Invalid numeric constraint:")
    try:
        test_data = {
            "synchronization": {
                "strategy": "rate_based",
                "alignment": {
                    "method": "nearest",
                    "tolerance_s": -0.01,
                },
            }
        }
        _validate_config_enums(test_data)
    except ValueError as e:
        print(f"  ✓ Caught: {e}")

    print()
    print("=" * 70)
    print("See module docstring for more information")
    print("=" * 70)
