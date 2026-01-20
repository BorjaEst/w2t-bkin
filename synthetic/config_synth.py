"""Synthetic configuration generator for W2T-BKIN.

This module builds valid `config.toml` files using the project's
Pydantic domain models. It is intended for tests, demos, and local
experimentation where a minimal-yet-valid configuration is needed.

Key capabilities:
- Construct a `Config` model with sensible defaults.
- Customize key knobs (project name, paths, synchronization strategy, logging).
- Configure preprocessing tasks (DLC/SLEAP pose estimation).
- Render the model deterministically to TOML without extra dependencies.
- Save the TOML to disk.

Configuration Structure:
- Uses PreprocessingConfig for pose estimation (DLC/SLEAP)
- Model paths are relative to paths.models_root
- Supports hardware_pulse, rate_based, and network_stream synchronization

Notes:
- We avoid third-party TOML writers to keep dependencies minimal.
- The writer here only covers the fields used by the `Config` schema.
- Legacy labels/facemap configs have been removed in favor of preprocessing.

Example:
        from pathlib import Path
        from synthetic.config_synth import build_config, write_config_toml

        cfg = build_config(
            project_name="demo-project",
            sync_strategy="hardware_pulse",
            preprocessing_dlc_enabled=True
        )
        write_config_toml(Path("output/synthetic-config.toml"), cfg)
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Literal, Optional, Union

from pydantic import BaseModel, Field

from w2t_bkin.config import (
    DLCConfig,
    LoggingConfig,
    NWBConfig,
    PathsConfig,
    PreprocessingConfig,
    ProjectConfig,
    QCConfig,
    SLEAPConfig,
    SynchronizationConfig,
    TranscodeConfig,
    VerificationConfig,
    VideoConfig,
)
from w2t_bkin.config import AcquisitionConfig, AlignmentConfig, BpodConfig, BpodSyncConfig, BpodSyncTrialType
from w2t_bkin.config import Config as ConfigModel


class SynthConfigOptions(BaseModel):
    """Options for synthesizing a minimal, valid pipeline `Config`.

    This model groups the many optional knobs into a coherent object,
    improving discoverability and IDE autocompletion. Values mirror the
    prior `build_config` parameters.
    """

    # Project and paths
    project_name: str = Field(default="synthetic-project")
    raw_root: str = Field(default="data/raw")
    intermediate_root: str = Field(default="data/interim")
    output_root: str = Field(default="data/processed")
    models_root: str = Field(default="models")

    # Synchronization
    sync_strategy: Literal["rate_based", "hardware_pulse", "network_stream"] = Field(default="rate_based")
    alignment_method: Literal["nearest", "linear"] = Field(default="nearest")
    alignment_tolerance_s: float = Field(default=0.01, ge=0)
    alignment_global_offset_s: float = Field(default=0.0)
    reference_channel: Optional[str] = Field(default=None)

    # Logging
    logging_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(default="INFO")
    logging_structured: bool = Field(default=False)

    # Acquisition/verification
    concat_strategy: str = Field(default="ffconcat")
    mismatch_tolerance_frames: int = Field(default=0, ge=0)
    warn_on_mismatch: bool = Field(default=True)

    # Video/transcode
    transcode_enabled: bool = Field(default=False)
    transcode_codec: str = Field(default="libx264")
    transcode_crf: int = Field(default=23, ge=0, le=51)
    transcode_preset: str = Field(default="medium")
    transcode_keyint: int = Field(default=60, gt=0)

    # NWB
    nwb_link_external_video: bool = Field(default=True)
    nwb_lab: str = Field(default="Synthetic Lab")
    nwb_institution: str = Field(default="Synthetic Institute")
    nwb_file_name_template: str = Field(default="{session_id}.nwb")
    nwb_session_description_template: str = Field(default="Synthetic session {session_id}")

    # QC
    qc_generate_report: bool = Field(default=False)
    qc_out_template: str = Field(default="{session_id}_qc.html")
    qc_include_verification: bool = Field(default=True)

    # Preprocessing
    preprocessing_dlc_enabled: bool = Field(default=False)
    preprocessing_force_rerun: bool = Field(default=False)


def build_config(*, options: Optional[SynthConfigOptions] = None, **overrides) -> ConfigModel:
    """Create a valid `Config` model from `SynthConfigOptions`.

    Builds a complete Config instance suitable for testing or demonstration.
    Uses PreprocessingConfig for pose estimation (DLC/SLEAP) with model paths
    relative to paths.models_root.

    Args:
        options: SynthConfigOptions instance with configuration values.
        **overrides: Keyword arguments to override specific option fields.

    Returns:
        ConfigModel: Fully validated Config instance.

    Usage patterns:
        - Preferred: `build_config(options=SynthConfigOptions(...))`
        - Convenience: pass any field as a keyword override, e.g.
          `build_config(project_name="demo", sync_strategy="hardware_pulse",
                       reference_channel="cam0", preprocessing_dlc_enabled=True)`
    """

    # Merge defaults with overrides (and explicit options if provided)
    base = options or SynthConfigOptions()
    if overrides:
        base = base.model_copy(update=overrides)

    project = ProjectConfig(name=base.project_name)

    paths = PathsConfig(
        raw_root=base.raw_root,
        intermediate_root=base.intermediate_root,
        output_root=base.output_root,
        models_root=base.models_root,
    )

    alignment = AlignmentConfig(
        method=base.alignment_method,
        tolerance_s=base.alignment_tolerance_s,
        global_offset_s=base.alignment_global_offset_s,
    )

    synchronization = SynchronizationConfig(
        strategy=base.sync_strategy,
        reference_channel=base.reference_channel,
        alignment=alignment,
    )

    acquisition = AcquisitionConfig(concat_strategy=base.concat_strategy)

    verification = VerificationConfig(
        mismatch_tolerance_frames=base.mismatch_tolerance_frames,
        warn_on_mismatch=base.warn_on_mismatch,
    )

    # Build Bpod sync configuration with trial types
    sync_trial_types = [
        BpodSyncTrialType(
            trial_type=1,
            sync_signal="W2T_Audio",
            sync_ttl="ttl_cue",
        ),
        BpodSyncTrialType(
            trial_type=2,
            sync_signal="A2L_Audio",
            sync_ttl="ttl_cue",
        ),
        BpodSyncTrialType(
            trial_type=3,
            sync_signal="Microstim",
            sync_ttl="ttl_cue",
        ),
    ]
    sync_config = BpodSyncConfig(trial_types=sync_trial_types)
    bpod = BpodConfig(parse=False, sync=sync_config)

    transcode = TranscodeConfig(
        enabled=base.transcode_enabled,
        codec=base.transcode_codec,
        crf=base.transcode_crf,
        preset=base.transcode_preset,
        keyint=base.transcode_keyint,
    )

    video = VideoConfig(transcode=transcode)

    nwb = NWBConfig(
        link_external_video=base.nwb_link_external_video,
        lab=base.nwb_lab,
        institution=base.nwb_institution,
        file_name_template=base.nwb_file_name_template,
        session_description_template=base.nwb_session_description_template,
    )

    qc = QCConfig(
        generate_report=base.qc_generate_report,
        out_template=base.qc_out_template,
        include_verification=base.qc_include_verification,
    )

    preprocessing = PreprocessingConfig(
        force_rerun=base.preprocessing_force_rerun,
        dlc=DLCConfig(enabled=base.preprocessing_dlc_enabled),
    )

    logging = LoggingConfig(level=base.logging_level, structured=base.logging_structured)

    # Only pass fields that are active in Config model
    # (other fields are commented out in config.py)
    return ConfigModel(
        project=project,
        paths=paths,
        synchronization=synchronization,
        bpod=bpod,
        preprocessing=preprocessing,
        logging=logging,
    )


def _toml_kv(key: str, value: Union[str, int, float, bool, Path]) -> str:
    """Render a single TOML key-value line.

    Strings and Paths are quoted; booleans/ints/floats are written as-is.
    """

    if isinstance(value, (str, Path)):
        # Always quote strings and paths
        return f'{key} = "{value}"\n'
    if isinstance(value, bool):
        return f"{key} = {'true' if value else 'false'}\n"
    return f"{key} = {value}\n"


def config_to_toml(config: ConfigModel) -> str:
    """Convert Config model to TOML string.

    This writer is schema-aware and intentionally minimal.
    It preserves a logical section order and outputs all active fields.

    Sections written:
        - project: Project identification
        - paths: File system paths
        - synchronization: Sync strategy and alignment
        - bpod: Behavioral trial synchronization (if configured)
        - preprocessing: Pose estimation tasks (DLC, SLEAP)
        - logging: Log level and format

    Note:
        Does not write deprecated sections (labels, facemap).
        Model paths in preprocessing are relative to paths.models_root.
    """

    lines: list[str] = []

    # [project]
    lines.append("[project]\n")
    lines.append(_toml_kv("name", config.project.name))
    lines.append("\n")

    # [paths]
    lines.append("[paths]\n")
    lines.append(_toml_kv("raw_root", config.paths.raw_root))
    lines.append(_toml_kv("intermediate_root", config.paths.intermediate_root))
    lines.append(_toml_kv("output_root", config.paths.output_root))
    lines.append(_toml_kv("models_root", config.paths.models_root))
    lines.append("\n")

    # [synchronization]
    lines.append("[synchronization]\n")
    lines.append(_toml_kv("strategy", config.synchronization.strategy))
    if config.synchronization.reference_channel:
        lines.append(_toml_kv("reference_channel", config.synchronization.reference_channel))
    lines.append("\n")

    # [synchronization.alignment]
    lines.append("[synchronization.alignment]\n")
    lines.append(_toml_kv("method", config.synchronization.alignment.method))
    lines.append(_toml_kv("tolerance_s", config.synchronization.alignment.tolerance_s))
    lines.append(_toml_kv("global_offset_s", config.synchronization.alignment.global_offset_s))
    lines.append("\n")

    # [bpod] - only active section
    lines.append("[bpod]\n")
    lines.append(_toml_kv("parse", config.bpod.parse))
    # Optional ingestion controls
    if hasattr(config.bpod, "pattern"):
        lines.append(_toml_kv("pattern", getattr(config.bpod, "pattern")))
    if hasattr(config.bpod, "order"):
        lines.append(_toml_kv("order", getattr(config.bpod, "order")))
    if hasattr(config.bpod, "continuous_time"):
        lines.append(_toml_kv("continuous_time", getattr(config.bpod, "continuous_time")))
    lines.append("\n")

    # [[bpod.sync.trial_types]]
    for tt in config.bpod.sync.trial_types:
        lines.append("[[bpod.sync.trial_types]]\n")
        lines.append(_toml_kv("trial_type", tt.trial_type))
        lines.append(_toml_kv("sync_signal", tt.sync_signal))
        lines.append(_toml_kv("sync_ttl", tt.sync_ttl))
        lines.append("\n")

    # [preprocessing]
    lines.append("[preprocessing]\n")
    lines.append(_toml_kv("force_rerun", config.preprocessing.force_rerun))
    lines.append("\n")

    # [preprocessing.dlc]
    lines.append("[preprocessing.dlc]\n")
    lines.append(_toml_kv("enabled", config.preprocessing.dlc.enabled))
    lines.append("\n")

    # [logging]
    lines.append("[logging]\n")
    lines.append(_toml_kv("level", config.logging.level))
    lines.append(_toml_kv("structured", config.logging.structured))
    lines.append("\n")

    return "".join(lines)


def write_config_toml(path: Union[str, Path], config: ConfigModel) -> Path:
    """Write the provided `Config` model to a TOML file.

    Serializes the configuration to TOML format with proper section ordering
    and formatting. Creates parent directories if they don't exist.

    Args:
        path: Output path for the TOML file.
        config: Validated configuration model to serialize.

    Returns:
        Path: The resolved output path where the file was written.

    Example:
        >>> from synthetic.config_synth import build_config, write_config_toml
        >>> cfg = build_config(project_name="test", preprocessing_dlc_enabled=True)
        >>> write_config_toml("output/test-config.toml", cfg)
    """

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    toml_text = config_to_toml(config)
    path.write_text(toml_text, encoding="utf-8")
    return path.resolve()


def generate_and_save(path: Union[str, Path], **kwargs) -> Path:
    """Convenience: build a config with overrides and save it to `path`.

    Any keyword arguments are forwarded to `build_config`.
    """

    cfg = build_config(**kwargs)
    return write_config_toml(path, cfg)


if __name__ == "__main__":
    # Minimal CLI-like behavior: generate a default config and save it.
    default_out = Path("output/synthetic-config.toml")
    out_path = write_config_toml(default_out, build_config())
    print(f"Wrote synthetic config to: {out_path}")
