"""Synthetic session configuration generator for W2T-BKIN.

Generates valid `session.toml` files using the project's domain session
models. Intended for tests, demos, and quick experimentation.

Features:
- Structured `SessionSynthOptions` Pydantic model to configure generation.
- Deterministic building of `Session` model instances.
- TOML rendering without external dependencies (arrays-of-tables syntax).
- Convenience helpers to write and load synthetic sessions.

Example:
    from synthetic.session_synth import build_session, write_session_toml
    session = build_session()  # uses defaults (two cameras, one TTL)
    write_session_toml('output/Session-SYNTH-0001/session.toml', session)

Advanced overrides:
    from synthetic.session_synth import SessionSynthOptions, build_session
    opts = SessionSynthOptions(camera_ids=['camA','camB','camTop'], ttl_ids=['ttl_sync'])
    session = build_session(options=opts, number_of_trial_types=2)
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Literal, Optional, Union

from pydantic import BaseModel, Field

from w2t_bkin.domain.session import Session as SessionModel
from w2t_bkin.domain.session import SessionMetadata
from w2t_bkin.domain.session import TTL, BpodSession, BpodTrialType, Camera


class SessionSynthOptions(BaseModel):
    """Options for synthesizing a minimal session.

    Designed to keep defaults sensible while allowing targeted overrides.
    All fields may be overridden via `build_session(..., field=value)`.
    """

    # Session metadata
    session_id: str = Field(default="Session-SYNTH-0001")
    subject_id: str = Field(default="Subject-XYZ")
    date: str = Field(default="2025-01-01")
    experimenter: str = Field(default="synthetic")
    description: str = Field(default="Synthetic test session")
    sex: Literal["M", "F", "U"] = Field(default="U")
    age: str = Field(default="P60")
    genotype: str = Field(default="WT")

    # Cameras
    camera_ids: List[str] = Field(default_factory=lambda: ["cam0", "cam1"])
    camera_paths_template: str = Field(default="Video/{camera_id}_*.avi")
    camera_description_template: str = Field(default="Camera {camera_id} view")
    camera_order: Literal["name_asc", "name_desc", "time_asc", "time_desc"] = Field(default="name_asc")

    # TTLs
    ttl_ids: List[str] = Field(default_factory=lambda: ["ttl_sync"])
    ttl_description_template: str = Field(default="Sync TTL channel {ttl_id}")
    ttl_paths_template: str = Field(default="TTLs/{ttl_id}_*.txt")

    # Bpod
    bpod_enabled: bool = Field(default=True)
    bpod_path: str = Field(default="Bpod/*.mat")
    bpod_order: Literal["name_asc", "name_desc", "time_asc", "time_desc"] = Field(default="name_asc")
    bpod_continuous_time: bool = Field(default=True)
    number_of_trial_types: int = Field(default=1, ge=0)
    trial_type_description_template: str = Field(default="Trial type {trial_type}")
    trial_type_sync_signal_template: str = Field(default="SyncSignal{trial_type}")
    trial_type_sync_ttl: Optional[str] = Field(default=None, description="TTL id to associate with trial types; defaults to first ttl id")


def build_session(*, options: Optional[SessionSynthOptions] = None, **overrides) -> SessionModel:
    """Create a synthetic `Session` model.

    Preferred usage: `build_session(options=SessionSynthOptions(...))`.
    Convenience: pass overrides as kwargs.
    """
    base = options or SessionSynthOptions()
    if overrides:
        base = base.model_copy(update=overrides)

    # Metadata
    metadata = SessionMetadata(
        id=base.session_id,
        subject_id=base.subject_id,
        date=base.date,
        experimenter=base.experimenter,
        description=base.description,
        sex=base.sex,
        age=base.age,
        genotype=base.genotype,
    )

    # TTLs
    ttl_models: List[TTL] = []
    for tid in base.ttl_ids:
        ttl_models.append(
            TTL(
                id=tid,
                description=base.ttl_description_template.format(ttl_id=tid),
                paths=base.ttl_paths_template.format(ttl_id=tid),
            )
        )

    # Cameras referencing first TTL (or specified mapping)
    camera_models: List[Camera] = []
    camera_ttl = base.trial_type_sync_ttl or (base.ttl_ids[0] if base.ttl_ids else "ttl_sync")
    for cid in base.camera_ids:
        camera_models.append(
            Camera(
                id=cid,
                description=base.camera_description_template.format(camera_id=cid),
                paths=base.camera_paths_template.format(camera_id=cid),
                order=base.camera_order,
                ttl_id=camera_ttl,
            )
        )

    # Bpod / trial types
    trial_types: List[BpodTrialType] = []
    if base.bpod_enabled and base.number_of_trial_types > 0:
        # Smart TTL selection: if trial_type_sync_ttl is explicitly set, use it
        # Otherwise, if we have >1 TTL, assume second one is for Bpod sync
        # Otherwise fall back to the camera TTL
        if base.trial_type_sync_ttl:
            sync_ttl = base.trial_type_sync_ttl
        elif len(base.ttl_ids) > 1:
            sync_ttl = base.ttl_ids[1]  # Second TTL for Bpod
        else:
            sync_ttl = camera_ttl
        for i in range(1, base.number_of_trial_types + 1):
            trial_types.append(
                BpodTrialType(
                    trial_type=i,
                    description=base.trial_type_description_template.format(trial_type=i),
                    sync_signal=base.trial_type_sync_signal_template.format(trial_type=i),
                    sync_ttl=sync_ttl,
                )
            )

    bpod = BpodSession(
        path=base.bpod_path,
        order=base.bpod_order,
        continuous_time=base.bpod_continuous_time,
        trial_types=trial_types,
    )

    return SessionModel(
        session=metadata,
        bpod=bpod,
        TTLs=ttl_models,
        cameras=camera_models,
        session_dir=".",  # load_session will override
    )


def _kv_line(key: str, value: Union[str, int, float, bool]) -> str:
    if isinstance(value, str):
        return f'{key} = "{value}"\n'
    if isinstance(value, bool):
        return f"{key} = {'true' if value else 'false'}\n"
    return f"{key} = {value}\n"


def session_to_toml(session: SessionModel) -> str:
    """Render a `Session` model to TOML text with arrays-of-tables."""
    lines: list[str] = []

    # [session]
    lines.append("[session]\n")
    lines.append(_kv_line("id", session.session.id))
    lines.append(_kv_line("subject_id", session.session.subject_id))
    lines.append(_kv_line("date", session.session.date))
    lines.append(_kv_line("experimenter", session.session.experimenter))
    lines.append(_kv_line("description", session.session.description))
    lines.append(_kv_line("sex", session.session.sex))
    lines.append(_kv_line("age", session.session.age))
    lines.append(_kv_line("genotype", session.session.genotype))
    lines.append("\n")

    # [bpod]
    lines.append("[bpod]\n")
    lines.append(_kv_line("path", session.bpod.path))
    lines.append(_kv_line("order", session.bpod.order))
    lines.append(_kv_line("continuous_time", session.bpod.continuous_time))
    lines.append("\n")

    # [[bpod.trial_types]]
    for tt in session.bpod.trial_types:
        lines.append("[[bpod.trial_types]]\n")
        lines.append(_kv_line("trial_type", tt.trial_type))
        lines.append(_kv_line("description", tt.description))
        lines.append(_kv_line("sync_signal", tt.sync_signal))
        lines.append(_kv_line("sync_ttl", tt.sync_ttl))
        lines.append("\n")

    # [[TTLs]]
    for ttl in session.TTLs:
        lines.append("[[TTLs]]\n")
        lines.append(_kv_line("id", ttl.id))
        lines.append(_kv_line("description", ttl.description))
        lines.append(_kv_line("paths", ttl.paths))
        lines.append("\n")

    # [[cameras]]
    for cam in session.cameras:
        lines.append("[[cameras]]\n")
        lines.append(_kv_line("id", cam.id))
        lines.append(_kv_line("description", cam.description))
        lines.append(_kv_line("paths", cam.paths))
        lines.append(_kv_line("order", cam.order))
        lines.append(_kv_line("ttl_id", cam.ttl_id))
        lines.append("\n")

    return "".join(lines)


def write_session_toml(path: Union[str, Path], session: SessionModel) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = session_to_toml(session)
    path.write_text(text, encoding="utf-8")
    return path.resolve()


def generate_and_save_session(path: Union[str, Path], **kwargs) -> Path:
    session = build_session(**kwargs)
    return write_session_toml(path, session)


if __name__ == "__main__":
    # Generate and write a synthetic session.
    out = Path("output/Session-SYNTH-0001/session.toml")
    session = build_session()
    p = write_session_toml(out, session)
    print(f"Wrote synthetic session to: {p}")
