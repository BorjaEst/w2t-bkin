"""Pydantic models for metadata.toml.

This module defines *schema* for the TOML-driven metadata used by the pipeline.

Two categories of data live in the merged metadata:
1) NWB metadata (fields passed into pynwb.NWBFile creation)
2) Pipeline source definitions (TTLs, cameras, bpod, pose) used for discovery

The templates that drive this schema are:
- templates/metadata.toml (optional NWB metadata + pipeline source definitions)
- templates/session.toml (required NWB session fields)

Note: metadata is hierarchically merged (global -> subject -> session). Some
files will intentionally omit required session fields, so root-level fields are
modeled as optional.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator

SortOrder = Literal["name_asc", "name_desc", "time_asc", "time_desc"]


class DictLikeModel(BaseModel, extra="forbid"):
    """Base model that provides a dict-like `.get()` for legacy call sites."""

    def get(self, key: str, default: Any = None) -> Any:
        """Return an attribute value if present; otherwise return default."""

        return getattr(self, key, default)


class TTLsMeta(DictLikeModel):
    """TTL synchronization source definition (pipeline metadata)."""

    id: str = Field(..., description="TTL channel identifier")
    paths: str = Field(..., description="Glob pattern relative to session dir")
    description: Optional[str] = Field(None, description="Human-readable TTL description")
    order: Optional[SortOrder] = Field(None, description="Optional file sort order override")

    @field_validator("paths", mode="before")
    @classmethod
    def coerce_paths_to_str(cls, v: Any) -> Any:
        """Allow legacy list[str] but normalize to a single glob string."""

        if isinstance(v, list):
            if len(v) == 1 and isinstance(v[0], str):
                return v[0]
            raise ValueError("TTLs.paths must be a single glob string")
        return v


class CameraMeta(DictLikeModel):
    """Camera stream definition for discovery and synchronization."""

    id: str = Field(..., description="Camera identifier")
    paths: str = Field(..., description="Glob pattern relative to session dir")
    fps: Optional[float] = Field(None, gt=0, description="Nominal frames/sec if TTL alignment is unavailable")
    ttl_id: Optional[str] = Field(None, description="TTL channel id used to align camera frames")
    description: Optional[str] = Field(None, description="Optional camera description")

    # Supported by discovery code even if not shown in template.
    order: Optional[SortOrder] = Field(None, description="Optional file sort order override")
    optional: bool = Field(False, description="If true, missing files do not raise")

    @field_validator("paths", mode="before")
    @classmethod
    def coerce_paths_to_str(cls, v: Any) -> Any:
        """Allow legacy list[str] but normalize to a single glob string."""

        if isinstance(v, list):
            if len(v) == 1 and isinstance(v[0], str):
                return v[0]
            raise ValueError("cameras.paths must be a single glob string")
        return v


class BpodSyncTrialTypeMeta(DictLikeModel):
    """Per-trial-type mapping used to align Bpod timestamps to a TTL timebase."""

    trial_type: int = Field(..., ge=0, description="Numeric trial type label produced by Bpod")
    sync_signal: str = Field(..., description="Bpod state/event name whose onset aligns to TTL pulses")
    sync_ttl: str = Field(..., description="TTL channel id containing pulses for sync_signal")


class BpodSyncMeta(DictLikeModel):
    """Bpod-to-TTL synchronization configuration."""

    trial_types: List[BpodSyncTrialTypeMeta] = Field(default_factory=list, description="List of trial-type sync rules")


class BpodMeta(DictLikeModel):
    """Bpod source definition (pipeline metadata)."""

    path: str = Field(..., description="Glob pattern for Bpod MAT files relative to session dir")
    order: SortOrder = Field("name_asc", description="File sort order")
    continuous_time: bool = Field(False, description="If true, timestamps are offset to form a continuous timeline across files")
    sync: Optional[BpodSyncMeta] = Field(None, description="Optional Bpod-to-TTL synchronization rules")


class DeviceMeta(DictLikeModel):
    """NWB device definition (NWB metadata)."""

    name: str = Field(..., description="Device name")
    description: Optional[str] = Field(None, description="Device description")
    manufacturer: Optional[str] = Field(None, description="Device manufacturer")
    model_name: Optional[str] = Field(None, description="Device model name")


class ElectrodeGroupMeta(DictLikeModel):
    """Electrode group definition (NWB metadata)."""

    name: str
    description: Optional[str] = None
    location: Optional[str] = None
    device: Optional[str] = None


class ImagingPlaneMeta(DictLikeModel):
    """Imaging plane definition (NWB metadata)."""

    name: str
    description: Optional[str] = None
    excitation_lambda: Optional[float] = None
    indicator: Optional[str] = None
    location: Optional[str] = None
    device: Optional[str] = None
    imaging_rate: Optional[float] = None


class OgenSiteMeta(DictLikeModel):
    """Optogenetic site definition (NWB metadata)."""

    name: str
    description: Optional[str] = None
    excitation_lambda: Optional[float] = None
    location: Optional[str] = None
    device: Optional[str] = None


class ProcessingModuleMeta(DictLikeModel):
    """Processing module definition (pipeline organization)."""

    name: str
    description: Optional[str] = None


class SubjectMeta(DictLikeModel):
    """NWB subject metadata.

    This typically comes from subject.toml and is included here because the
    pipeline merges metadata hierarchically.
    """

    subject_id: Optional[str] = None
    description: Optional[str] = None
    species: Optional[str] = None
    sex: Optional[str] = None
    age: Optional[str] = None
    age__reference: Optional[str] = Field("birth", description="Reference for age (default: birth)")
    genotype: Optional[str] = None
    strain: Optional[str] = None
    weight: Optional[str] = None
    date_of_birth: Optional[str] = None


class PoseModelMeta(DictLikeModel):
    """Pose estimation model entry under [pose.models.<model_id>]."""

    source: Literal["dlc", "sleap"]
    path: str = Field(..., description="Path to model config (relative to models_root in generate mode)")
    artifacts: Optional[str] = Field(
        None,
        description="Optional default artifact subdirectory for outputs (e.g., dlc-pose). Can be overridden per camera.",
    )


class PoseCameraMeta(DictLikeModel):
    """Per-camera pose configuration under [pose.cameras.<camera_id>]."""

    source: Literal["dlc", "sleap"]
    model_id: Optional[str] = Field(None, description="References pose.models.<model_id>")
    mapping_id: Optional[str] = Field(None, description="References pose.mappings.<mapping_id>")
    skeleton_id: Optional[str] = Field(None, description="References pose.skeletons.<skeleton_id>")
    artifacts: Optional[str] = Field(None, description="Artifact subdirectory (e.g., dlc-pose)")


class PoseSkeletonEdge(DictLikeModel):
    """Optional edge entry for a pose skeleton."""

    source: str
    target: str


class PoseSkeletonMeta(DictLikeModel):
    """Skeleton definition under [pose.skeletons.<skeleton_id>]."""

    name: Optional[str] = None
    nodes: List[str] = Field(default_factory=list)
    edges: Optional[List[PoseSkeletonEdge]] = None


class PoseMeta(DictLikeModel):
    """Complete [pose] section from metadata.toml.

    The TOML uses dict-keyed subtables (e.g., [pose.cameras.camera_0]), so this
    model uses dicts keyed by those ids.
    """

    models: Dict[str, PoseModelMeta] = Field(default_factory=dict)
    cameras: Dict[str, PoseCameraMeta] = Field(default_factory=dict)
    mappings: Dict[str, Dict[str, str]] = Field(default_factory=dict)
    skeletons: Dict[str, PoseSkeletonMeta] = Field(default_factory=dict)


class Metadata(DictLikeModel):
    """Merged metadata model.

    This model is designed to validate the *merged* metadata dict produced by
    hierarchical TOML loading (global -> subject -> session).
    """

    # Required fields for a valid NWBFile, but optional here due to hierarchical merges.
    session_description: Optional[str] = None
    identifier: Optional[str] = None
    session_start_time: Optional[str] = None

    # Optional NWB session metadata (from templates/metadata.toml)
    timestamps_reference_time: Optional[str] = None
    experimenter: Optional[List[str]] = None
    experiment_description: Optional[str] = None
    session_id: Optional[str] = None
    institution: Optional[str] = None
    lab: Optional[str] = None
    keywords: Optional[List[str]] = None
    notes: Optional[str] = None
    protocol: Optional[str] = None
    related_publications: Optional[List[str]] = None
    pharmacology: Optional[str] = None
    slices: Optional[str] = None
    data_collection: Optional[str] = None
    surgery: Optional[str] = None
    virus: Optional[str] = None
    stimulus_notes: Optional[str] = None

    # NWB-ish tables
    subject: Optional[SubjectMeta] = None
    devices: List[DeviceMeta] = Field(default_factory=list)
    electrode_groups: List[ElectrodeGroupMeta] = Field(default_factory=list)
    imaging_planes: List[ImagingPlaneMeta] = Field(default_factory=list)
    ogen_sites: List[OgenSiteMeta] = Field(default_factory=list)
    processing_modules: List[ProcessingModuleMeta] = Field(default_factory=list)

    # Pipeline source definitions
    TTLs: List[TTLsMeta] = Field(default_factory=list, description="TTL source definitions")
    bpod: Optional[BpodMeta] = None
    cameras: List[CameraMeta] = Field(default_factory=list)
    pose: PoseMeta = Field(default_factory=PoseMeta)

    @field_validator("experimenter", mode="before")
    @classmethod
    def coerce_experimenter_to_list(cls, v: Any) -> Any:
        """Allow experimenter as str or list[str], normalize to list[str]."""

        if v is None:
            return None
        if isinstance(v, str):
            return [v]
        if isinstance(v, list) and all(isinstance(item, str) for item in v):
            return v
        raise ValueError("experimenter must be a string or list of strings")
