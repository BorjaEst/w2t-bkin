"""Synthetic session configuration generator for W2T-BKIN.

Generates valid `metadata.toml` and `metadata.toml` files for the pipeline.
Intended for tests, demos, and quick experimentation.

Features:
- Structured `SessionSynthOptions` Pydantic model to configure generation.
- Deterministic building of session and metadata dictionaries.
- TOML rendering without external dependencies (arrays-of-tables syntax).
- NWB-compliant metadata generation with subject, devices, and processing modules.

Example:
    from synthetic.session_synth import build_session, write_session_toml
    from synthetic.session_synth import build_metadata, write_metadata_toml

    # Generate metadata.toml (cameras, TTLs, bpod)
    session = build_session()  # uses defaults (two cameras, one TTL)
    write_session_toml('output/Session-SYNTH-0001/metadata.toml', session)

    # Generate metadata.toml (NWB-compliant metadata)
    metadata = build_metadata()  # uses same defaults
    write_metadata_toml('output/Session-SYNTH-0001/metadata.toml', metadata)

Advanced overrides:
    from synthetic.session_synth import SessionSynthOptions, build_session
    opts = SessionSynthOptions(
        camera_ids=['camA','camB','camTop'],
        ttl_ids=['ttl_sync'],
        institution='My Lab',
        species='Rattus norvegicus'
    )
    session = build_session(options=opts)
    metadata = build_metadata(options=opts)
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Literal, Optional, Union

from pydantic import BaseModel, Field


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

    # NWB metadata fields (for metadata.toml)
    session_start_time: Optional[str] = Field(default=None, description="ISO 8601 datetime, defaults to date + 14:30:00")
    session_description: str = Field(default="Synthetic behavioral session with camera tracking")
    experiment_description: str = Field(default="Synthetic test session for pipeline validation")
    institution: str = Field(default="Synthetic Institute")
    lab: str = Field(default="Synthetic Lab")
    keywords: List[str] = Field(default_factory=lambda: ["behavior", "pose tracking", "synchronization"])
    notes: str = Field(default="Synthetic session generated for testing")
    protocol: str = Field(default="TEST-SYNTH-001")
    pharmacology: str = Field(default="None")
    surgery: str = Field(default="No surgery")
    virus: str = Field(default="None")
    stimulus_notes: str = Field(default="Synthetic stimulus")
    data_collection: str = Field(default="Synthetic data generated programmatically")
    species: str = Field(default="Mus musculus")
    strain: str = Field(default="C57BL/6J")
    weight: str = Field(default="0.025 kg")
    date_of_birth: Optional[str] = Field(default=None, description="ISO 8601 date, auto-calculated from age if not provided")

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


def build_metadata(*, options: Optional[SessionSynthOptions] = None, **overrides) -> dict:
    """Create a synthetic NWB-compliant metadata dictionary.

    Returns a dictionary that can be written to metadata.toml.
    This generates all required NWB fields plus subject, devices, and processing modules.

    Preferred usage: `build_metadata(options=SessionSynthOptions(...))`.
    Convenience: pass overrides as kwargs.
    """
    base = options or SessionSynthOptions()
    if overrides:
        base = base.model_copy(update=overrides)

    # Build session_start_time from date if not provided
    session_start_time = base.session_start_time
    if session_start_time is None:
        session_start_time = f"{base.date}T14:30:00"

    # Build date_of_birth from age if not provided (simple heuristic)
    date_of_birth = base.date_of_birth
    if date_of_birth is None:
        # Extract days from age string like "P60D" or "P84D"
        import re

        match = re.match(r"P(\d+)D", base.age)
        if match:
            days_old = int(match.group(1))
            from datetime import datetime, timedelta

            session_date = datetime.fromisoformat(base.date)
            birth_date = session_date - timedelta(days=days_old)
            date_of_birth = birth_date.strftime("%Y-%m-%dT00:00:00")
        else:
            date_of_birth = "2024-01-01T00:00:00Z"  # Fallback

    # Build experimenter list (convert string to list if needed)
    experimenter_list = [base.experimenter] if isinstance(base.experimenter, str) else base.experimenter

    # Build metadata dictionary matching metadata.toml structure
    metadata = {
        # Required NWB fields
        "session_description": base.session_description,
        "identifier": base.session_id,
        "session_start_time": session_start_time,
        # Optional session metadata
        "session_id": base.session_id,
        "experimenter": experimenter_list,
        "experiment_description": base.experiment_description,
        "institution": base.institution,
        "lab": base.lab,
        "keywords": base.keywords,
        "notes": base.notes,
        "protocol": base.protocol,
        "related_publications": [],
        "pharmacology": base.pharmacology,
        "slices": "N/A - in vivo experiment",
        "data_collection": base.data_collection,
        "surgery": base.surgery,
        "virus": base.virus,
        "stimulus_notes": base.stimulus_notes,
        # Subject information
        "subject": {
            "subject_id": base.subject_id,
            "description": f"Synthetic subject {base.subject_id}",
            "species": base.species,
            "sex": base.sex,
            "age": base.age,
            "age__reference": "birth",
            "genotype": base.genotype,
            "strain": base.strain,
            "weight": base.weight,
            "date_of_birth": date_of_birth,
        },
        # Devices (Bpod + cameras from camera_ids)
        "devices": [
            {
                "name": "bpod",
                "description": "Bpod State Machine for behavioral control",
                "manufacturer": "Sanworks",
            }
        ],
        # Processing modules
        "processing_modules": [
            {
                "name": "behavior",
                "description": "Processed behavioral data including pose estimates and synchronized events",
            },
            {
                "name": "sync",
                "description": "Synchronization data between Bpod and cameras",
            },
        ],
    }

    # Add camera devices
    for i, cam_id in enumerate(base.camera_ids):
        metadata["devices"].append(
            {
                "name": cam_id,
                "description": f"Camera {i} for pose tracking - {cam_id} view",
                "manufacturer": "Synthetic Camera Co.",
            }
        )

    return metadata


def build_session(*, options: Optional[SessionSynthOptions] = None, **overrides) -> dict:
    """Create a synthetic session configuration dictionary.

    Returns a dictionary that can be written to metadata.toml.

    Preferred usage: `build_session(options=SessionSynthOptions(...))`.
    Convenience: pass overrides as kwargs.
    """
    base = options or SessionSynthOptions()
    if overrides:
        base = base.model_copy(update=overrides)

    # Build session dictionary matching metadata.toml structure
    session_dict = {
        "session": {
            "id": base.session_id,
            "subject_id": base.subject_id,
            "date": base.date,
            "experimenter": base.experimenter,
            "description": base.description,
            "sex": base.sex,
            "age": base.age,
            "genotype": base.genotype,
        },
        "bpod": {
            "path": base.bpod_path,
            "order": base.bpod_order,
            "continuous_time": base.bpod_continuous_time,
        },
        "TTLs": [],
        "cameras": [],
    }

    # Add TTLs
    for tid in base.ttl_ids:
        session_dict["TTLs"].append(
            {
                "id": tid,
                "description": base.ttl_description_template.format(ttl_id=tid),
                "paths": base.ttl_paths_template.format(ttl_id=tid),
            }
        )

    # Add cameras
    camera_ttl = base.trial_type_sync_ttl or (base.ttl_ids[0] if base.ttl_ids else "ttl_sync")
    for cid in base.camera_ids:
        session_dict["cameras"].append(
            {
                "id": cid,
                "description": base.camera_description_template.format(camera_id=cid),
                "paths": base.camera_paths_template.format(camera_id=cid),
                "order": base.camera_order,
                "ttl_id": camera_ttl,
            }
        )

    return session_dict


def _kv_line(key: str, value: Union[str, int, float, bool]) -> str:
    if isinstance(value, str):
        return f'{key} = "{value}"\n'
    if isinstance(value, bool):
        return f"{key} = {'true' if value else 'false'}\n"
    return f"{key} = {value}\n"


def metadata_to_toml(metadata: dict) -> str:
    """Render a metadata dictionary to TOML text matching NWB metadata.toml format."""
    lines: list[str] = []

    # Helper for multiline strings
    def _multiline(value: str) -> str:
        # Use triple-quoted strings for multiline content
        if "\n" in value or len(value) > 80:
            return f'"""\n{value}\n"""'
        return f'"{value}"'

    # Helper for arrays
    def _array(values: list) -> str:
        if not values:
            return "[]"
        if isinstance(values[0], str):
            items = ", ".join(f'"{v}"' for v in values)
            return f"[\n    {items},\n]"
        return str(values)

    # Required NWB fields
    lines.append("# NWB Session Configuration File\n")
    lines.append("# Auto-generated by synthetic session builder\n\n")
    lines.append("# Required fields\n")
    lines.append(_kv_line("session_description", metadata["session_description"]))
    lines.append(_kv_line("identifier", metadata["identifier"]))
    lines.append(_kv_line("session_start_time", metadata["session_start_time"]))
    lines.append("\n")

    # Optional session metadata
    lines.append("# Optional metadata\n")
    lines.append(_kv_line("session_id", metadata["session_id"]))
    lines.append(f'experimenter = {_array(metadata["experimenter"])}\n')
    lines.append(f'experiment_description = {_multiline(metadata["experiment_description"])}\n')
    lines.append(_kv_line("institution", metadata["institution"]))
    lines.append(_kv_line("lab", metadata["lab"]))
    lines.append(f'keywords = {_array(metadata["keywords"])}\n')
    lines.append(f'notes = {_multiline(metadata["notes"])}\n')
    lines.append(_kv_line("protocol", metadata["protocol"]))
    lines.append(f'related_publications = {_array(metadata["related_publications"])}\n')
    lines.append(_kv_line("pharmacology", metadata["pharmacology"]))
    lines.append(_kv_line("slices", metadata["slices"]))
    lines.append(f'data_collection = {_multiline(metadata["data_collection"])}\n')
    lines.append(f'surgery = {_multiline(metadata["surgery"])}\n')
    lines.append(_kv_line("virus", metadata["virus"]))
    lines.append(_kv_line("stimulus_notes", metadata["stimulus_notes"]))
    lines.append("\n")

    # Subject information
    lines.append("[subject]\n")
    for key, value in metadata["subject"].items():
        lines.append(_kv_line(key, value))
    lines.append("\n")

    # Devices
    for device in metadata["devices"]:
        lines.append("[[devices]]\n")
        for key, value in device.items():
            lines.append(_kv_line(key, value))
        lines.append("\n")

    # Processing modules
    for module in metadata["processing_modules"]:
        lines.append("[[processing_modules]]\n")
        for key, value in module.items():
            lines.append(_kv_line(key, value))
        lines.append("\n")

    return "".join(lines)


def session_to_toml(session: dict) -> str:
    """Render a session dictionary to TOML text with arrays-of-tables."""
    lines: list[str] = []

    # [session]
    lines.append("[session]\n")
    for key, value in session["session"].items():
        lines.append(_kv_line(key, value))
    lines.append("\n")

    # [bpod]
    lines.append("[bpod]\n")
    for key, value in session["bpod"].items():
        lines.append(_kv_line(key, value))
    lines.append("\n")

    # NOTE: trial_types moved to config.bpod.sync.trial_types

    # [[TTLs]]
    for ttl in session["TTLs"]:
        lines.append("[[TTLs]]\n")
        for key, value in ttl.items():
            lines.append(_kv_line(key, value))
        lines.append("\n")

    # [[cameras]]
    for cam in session["cameras"]:
        lines.append("[[cameras]]\n")
        for key, value in cam.items():
            lines.append(_kv_line(key, value))
        lines.append("\n")

    return "".join(lines)


def write_session_toml(path: Union[str, Path], session: dict) -> Path:
    """Write session dictionary to TOML file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = session_to_toml(session)
    path.write_text(text, encoding="utf-8")
    return path.resolve()


def write_metadata_toml(path: Union[str, Path], metadata: dict) -> Path:
    """Write metadata dictionary to TOML file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = metadata_to_toml(metadata)
    path.write_text(text, encoding="utf-8")
    return path.resolve()


def generate_and_save_session(path: Union[str, Path], **kwargs) -> Path:
    session = build_session(**kwargs)
    return write_session_toml(path, session)


if __name__ == "__main__":
    # Generate and write a synthetic session.
    out = Path("output/Session-SYNTH-0001/metadata.toml")
    session = build_session()
    p = write_session_toml(out, session)
    print(f"Wrote synthetic session to: {p}")
