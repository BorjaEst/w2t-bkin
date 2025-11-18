"""Synthetic configuration generator for W2T-BKIN.

This module builds valid `config.toml` files using the project's
Pydantic domain models. It is intended for tests, demos, and local
experimentation where a minimal-yet-valid configuration is needed.

Key capabilities:
- Construct a `Config` model with sensible defaults.
- Customize key knobs (project name, paths, timebase source, logging).
- Render the model deterministically to TOML without extra dependencies.
- Save the TOML to disk.

Notes:
- We avoid third-party TOML writers to keep dependencies minimal.
- The writer here only covers the fields used by the `Config` schema.

Example:
        from pathlib import Path
        from synthetic.config_synth import build_config, write_config_toml

        cfg = build_config(project_name="demo-project")
        write_config_toml(Path("output/synthetic-config.toml"), cfg)
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Literal, Optional, Union

from pydantic import BaseModel, Field

from w2t_bkin.domain.config import (
    DLCConfig,
    FacemapConfig,
    LabelsConfig,
    LoggingConfig,
    NWBConfig,
    PathsConfig,
    ProjectConfig,
    QCConfig,
    SLEAPConfig,
    TimebaseConfig,
    TranscodeConfig,
    VerificationConfig,
    VideoConfig,
)
from w2t_bkin.domain.config import AcquisitionConfig, BpodConfig
from w2t_bkin.domain.config import Config as ConfigModel


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
    metadata_file: str = Field(default="session.toml")
    models_root: str = Field(default="models")

    # Timebase
    timebase_source: Literal["nominal_rate", "ttl", "neuropixels"] = Field(default="nominal_rate")
    timebase_mapping: Literal["nearest", "linear"] = Field(default="nearest")
    jitter_budget_s: float = Field(default=0.01, gt=0)
    offset_s: float = Field(default=0.0)
    timebase_ttl_id: Optional[str] = Field(default=None)
    neuropixels_stream: Optional[str] = Field(default=None)

    # Logging
    logging_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(default="INFO")
    logging_structured: bool = Field(default=False)

    # Acquisition/verification
    concat_strategy: str = Field(default="by_camera_then_time")
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

    # Labels/Facemap
    dlc_run_inference: bool = Field(default=False)
    dlc_model: str = Field(default="models/dlc/model.yaml")
    sleap_run_inference: bool = Field(default=False)
    sleap_model: str = Field(default="models/sleap/model.slp")
    facemap_run_inference: bool = Field(default=False)
    facemap_rois: list[str] = Field(default_factory=lambda: ["whisker", "snout"])


def build_config(*, options: Optional[SynthConfigOptions] = None, **overrides) -> ConfigModel:
    """Create a valid `Config` model from `SynthConfigOptions`.

    Usage patterns:
    - Preferred: `build_config(options=SynthConfigOptions(...))`
    - Convenience: pass any field as a keyword override, e.g.
      `build_config(project_name="demo", timebase_source="ttl", timebase_ttl_id="cam0")`
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
        metadata_file=base.metadata_file,
        models_root=base.models_root,
    )

    timebase = TimebaseConfig(
        source=base.timebase_source,
        mapping=base.timebase_mapping,
        jitter_budget_s=base.jitter_budget_s,
        offset_s=base.offset_s,
        ttl_id=base.timebase_ttl_id,
        neuropixels_stream=base.neuropixels_stream,
    )

    acquisition = AcquisitionConfig(concat_strategy=base.concat_strategy)

    verification = VerificationConfig(
        mismatch_tolerance_frames=base.mismatch_tolerance_frames,
        warn_on_mismatch=base.warn_on_mismatch,
    )

    bpod = BpodConfig(parse=False)

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

    logging = LoggingConfig(level=base.logging_level, structured=base.logging_structured)

    labels = LabelsConfig(
        dlc=DLCConfig(run_inference=base.dlc_run_inference, model=base.dlc_model),
        sleap=SLEAPConfig(run_inference=base.sleap_run_inference, model=base.sleap_model),
    )

    facemap = FacemapConfig(
        run_inference=base.facemap_run_inference,
        ROIs=list(base.facemap_rois),
    )

    return ConfigModel(
        project=project,
        paths=paths,
        timebase=timebase,
        acquisition=acquisition,
        verification=verification,
        bpod=bpod,
        video=video,
        nwb=nwb,
        qc=qc,
        logging=logging,
        labels=labels,
        facemap=facemap,
    )


def _toml_kv(key: str, value: Union[str, int, float, bool]) -> str:
    """Render a single TOML key-value line.

    Strings are quoted; booleans/ints/floats are written as-is.
    """

    if isinstance(value, str):
        return f'{key} = "{value}"\n'
    if isinstance(value, bool):
        return f"{key} = {'true' if value else 'false'}\n"
    return f"{key} = {value}\n"


def config_to_toml(config: ConfigModel) -> str:
    """Render a `Config` model to TOML text.

    This writer is schema-aware and intentionally minimal.
    It preserves a logical section order and omits no required fields.
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
    lines.append(_toml_kv("metadata_file", config.paths.metadata_file))
    lines.append(_toml_kv("models_root", config.paths.models_root))
    lines.append("\n")

    # [timebase]
    lines.append("[timebase]\n")
    lines.append(_toml_kv("source", config.timebase.source))
    lines.append(_toml_kv("mapping", config.timebase.mapping))
    lines.append(_toml_kv("jitter_budget_s", config.timebase.jitter_budget_s))
    lines.append(_toml_kv("offset_s", config.timebase.offset_s))
    if config.timebase.ttl_id is not None:
        lines.append(_toml_kv("ttl_id", config.timebase.ttl_id))
    if config.timebase.neuropixels_stream is not None:
        lines.append(_toml_kv("neuropixels_stream", config.timebase.neuropixels_stream))
    lines.append("\n")

    # [acquisition]
    lines.append("[acquisition]\n")
    lines.append(_toml_kv("concat_strategy", config.acquisition.concat_strategy))
    lines.append("\n")

    # [verification]
    lines.append("[verification]\n")
    lines.append(_toml_kv("mismatch_tolerance_frames", config.verification.mismatch_tolerance_frames))
    lines.append(_toml_kv("warn_on_mismatch", config.verification.warn_on_mismatch))
    lines.append("\n")

    # [bpod]
    lines.append("[bpod]\n")
    lines.append(_toml_kv("parse", config.bpod.parse))
    lines.append("\n")

    # [video.transcode]
    lines.append("[video.transcode]\n")
    lines.append(_toml_kv("enabled", config.video.transcode.enabled))
    lines.append(_toml_kv("codec", config.video.transcode.codec))
    lines.append(_toml_kv("crf", config.video.transcode.crf))
    lines.append(_toml_kv("preset", config.video.transcode.preset))
    lines.append(_toml_kv("keyint", config.video.transcode.keyint))
    lines.append("\n")

    # [nwb]
    lines.append("[nwb]\n")
    lines.append(_toml_kv("link_external_video", config.nwb.link_external_video))
    lines.append(_toml_kv("lab", config.nwb.lab))
    lines.append(_toml_kv("institution", config.nwb.institution))
    lines.append(_toml_kv("file_name_template", config.nwb.file_name_template))
    lines.append(_toml_kv("session_description_template", config.nwb.session_description_template))
    lines.append("\n")

    # [qc]
    lines.append("[qc]\n")
    lines.append(_toml_kv("generate_report", config.qc.generate_report))
    lines.append(_toml_kv("out_template", config.qc.out_template))
    lines.append(_toml_kv("include_verification", config.qc.include_verification))
    lines.append("\n")

    # [logging]
    lines.append("[logging]\n")
    lines.append(_toml_kv("level", config.logging.level))
    lines.append(_toml_kv("structured", config.logging.structured))
    lines.append("\n")

    # [labels.dlc]
    lines.append("[labels.dlc]\n")
    lines.append(_toml_kv("run_inference", config.labels.dlc.run_inference))
    lines.append(_toml_kv("model", config.labels.dlc.model))
    lines.append("\n")

    # [labels.sleap]
    lines.append("[labels.sleap]\n")
    lines.append(_toml_kv("run_inference", config.labels.sleap.run_inference))
    lines.append(_toml_kv("model", config.labels.sleap.model))
    lines.append("\n")

    # [facemap]
    lines.append("[facemap]\n")
    lines.append(_toml_kv("run_inference", config.facemap.run_inference))
    # ROIs as a TOML array of strings
    rois = ", ".join(f'"{roi}"' for roi in config.facemap.ROIs)
    lines.append(f"ROIs = [{rois}]\n")

    return "".join(lines)


def write_config_toml(path: Union[str, Path], config: ConfigModel) -> Path:
    """Write the provided `Config` model to a TOML file.

    Parameters
    ----------
    path: Output path for the TOML file.
    config: Validated configuration model to serialize.

    Returns
    -------
    Path
            The resolved output path.
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
