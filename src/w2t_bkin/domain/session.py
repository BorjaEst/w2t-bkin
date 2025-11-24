"""Session domain models for W2T-BKIN pipeline (Phase 0).

This module defines Pydantic models for session metadata and specifications
loaded from session.toml files. Session models describe the experimental
session, subject information, and file patterns for discovery.

Model Hierarchy:
---------------
- Session (top-level)
  ├── NWBRequired (NWB-compliant metadata)
  ├── NWBMetadata (optional NWB fields)
  ├── NWBSubject (subject information)
  ├── NWBDevice (list of devices)
  ├── NWBProcessingModule (list of processing modules)
  ├── LabMetadata (lab-specific custom fields)
  ├── GenerationInfo (file generation metadata)
  ├── SessionMetadata (legacy - for backward compatibility)
  ├── BpodSession
  ├── TTL (list)
  └── Camera (list)

Key Features:
-------------
- **Immutable**: frozen=True prevents accidental modification
- **Strict Schema**: extra="forbid" rejects unknown fields (relaxed for lab_metadata)
- **Type Safe**: Full annotations with runtime validation
- **Hashable**: Supports deterministic provenance tracking
- **NWB-Compliant**: Follows pynwb.file.NWBFile specification

Requirements:
-------------
- FR-1: Ingest camera videos, TTLs, and Bpod files
- FR-7: NWB file assembly with comprehensive metadata
- FR-15: Validate camera-TTL references
- NFR-6: Standards compliance (NWB best practices)
- NFR-10: Type safety via Pydantic

Acceptance Criteria:
-------------------
- A18: Supports deterministic hashing
- A19: NWB metadata from session.toml

Usage:
------
>>> from w2t_bkin.config import load_session
>>> session = load_session("session.toml")
>>> print(session.required.identifier)
>>> print(session.subject.subject_id)
>>> for device in session.devices:
...     print(f"{device.name}: {device.manufacturer}")

See Also:
---------
- w2t_bkin.config: Loading and validation logic
- pynwb.file.NWBFile: NWB file specification
- https://pynwb.readthedocs.io/en/stable/tutorials/general/plot_file.html
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

# =============================================================================
# NWB-Compliant Session Models
# =============================================================================


class NWBRequired(BaseModel):
    """Required NWB file metadata fields.

    Based on pynwb.file.NWBFile required parameters.
    See: https://pynwb.readthedocs.io/en/stable/pynwb.file.html#pynwb.file.NWBFile

    Attributes:
        session_description: Description of the session where data was generated
        identifier: Unique text identifier for the file (e.g., UUID, session ID)
        session_start_time: Start date and time of recording session (ISO 8601)
    """

    model_config = {"frozen": True, "extra": "forbid"}

    session_description: str = Field(..., description="Description of the session where this data was generated")
    identifier: str = Field(..., description="Unique text identifier for the file (UUID or lab-specific ID)")
    session_start_time: str = Field(..., description="Start date/time of recording (ISO 8601: YYYY-MM-DDTHH:MM:SS)")


class NWBMetadata(BaseModel):
    """Optional NWB file metadata fields.

    Based on pynwb.file.NWBFile optional parameters.
    All fields are optional following NWB best practices.

    Attributes:
        session_id: Lab-specific session identifier
        experimenter: List of people who performed the experiment
        experiment_description: General description of the experiment
        institution: Institution(s) where experiment was performed
        lab: Lab where experiment was performed
        keywords: Terms to search over
        notes: Notes about the experiment
        protocol: Experimental protocol reference (e.g., IACUC number)
        related_publications: Publication information (PMID, DOI, URL)
        pharmacology: Description of drugs used
        slices: Description of slices (for in vitro experiments)
        data_collection: Notes about data collection and analysis
        surgery: Narrative about surgery/surgeries
        virus: Information about virus(es) used
        stimulus_notes: Notes about stimuli presentation
        source_script: Script file used to create NWB file
        source_script_file_name: Name of the source_script file
        timestamps_reference_time: Time zero reference (defaults to session_start_time)
    """

    model_config = {"frozen": True, "extra": "forbid"}

    session_id: Optional[str] = Field(None, description="Lab-specific session identifier")
    experimenter: Optional[List[str]] = Field(None, description="Names of experimenter(s)")
    experiment_description: Optional[str] = Field(None, description="General description of the experiment")
    institution: Optional[str] = Field(None, description="Institution(s) where experiment was performed")
    lab: Optional[str] = Field(None, description="Lab where experiment was performed")
    keywords: Optional[List[str]] = Field(None, description="Terms to search over")
    notes: Optional[str] = Field(None, description="Notes about the experiment")
    protocol: Optional[str] = Field(None, description="Experimental protocol reference (e.g., IACUC protocol number)")
    related_publications: Optional[List[str]] = Field(None, description="Publication information (PMID, DOI, URL)")
    pharmacology: Optional[str] = Field(None, description="Description of drugs used, including administration")
    slices: Optional[str] = Field(None, description="Description of slices (for in vitro experiments)")
    data_collection: Optional[str] = Field(None, description="Notes about data collection and analysis")
    surgery: Optional[str] = Field(None, description="Narrative description about surgery/surgeries")
    virus: Optional[str] = Field(None, description="Information about virus(es) used")
    stimulus_notes: Optional[str] = Field(None, description="Notes about stimuli presentation")
    source_script: Optional[str] = Field(None, description="Script file used to create this NWB file")
    source_script_file_name: Optional[str] = Field(None, description="Name of the source_script file")
    timestamps_reference_time: Optional[str] = Field(None, description="Date and time for time zero of all timestamps")


class NWBSubject(BaseModel):
    """Subject information for NWB file.

    Based on pynwb.file.Subject specification.
    See: https://pynwb.readthedocs.io/en/stable/pynwb.file.html#pynwb.file.Subject

    Attributes:
        subject_id: Subject identifier
        description: Description of the subject
        species: Species (formal Latin binomial name recommended, e.g., "Mus musculus")
        sex: Sex - "F" (female), "M" (male), "U" (unknown), "O" (other)
        age: Age (ISO 8601 Duration format recommended, e.g., "P90D" for 90 days)
        age__reference: Age reference point - "birth" or "gestational"
        genotype: Genotype
        strain: Strain
        weight: Weight (include units, e.g., "0.025 kg")
        date_of_birth: Date of birth (ISO 8601 format)
    """

    model_config = {"frozen": True, "extra": "forbid"}

    subject_id: str = Field(..., description="Subject identifier")
    description: Optional[str] = Field(None, description="Description of the subject")
    species: Optional[str] = Field("Mus musculus", description="Species (Latin binomial, e.g., 'Mus musculus')")
    sex: Optional[Literal["F", "M", "U", "O"]] = Field(None, description="Sex: 'F' (female), 'M' (male), 'U' (unknown), 'O' (other)")
    age: Optional[str] = Field(None, description="Age (ISO 8601 Duration, e.g., 'P90D' for 90 days)")
    age__reference: Optional[Literal["birth", "gestational"]] = Field("birth", description="Age reference: 'birth' or 'gestational'")
    genotype: Optional[str] = Field(None, description="Genotype")
    strain: Optional[str] = Field(None, description="Strain")
    weight: Optional[str] = Field(None, description="Weight (include units, e.g., '0.025 kg')")
    date_of_birth: Optional[str] = Field(None, description="Date of birth (ISO 8601 format)")


class NWBDevice(BaseModel):
    """Device used in experiment.

    Based on pynwb.device.Device specification.

    Attributes:
        name: Device name (must be unique)
        description: Description of the device
        manufacturer: Manufacturer name
        model_name: Model name/number
    """

    model_config = {"frozen": True, "extra": "forbid"}

    name: str = Field(..., description="Device name (must be unique)")
    description: Optional[str] = Field(None, description="Description of the device")
    manufacturer: Optional[str] = Field(None, description="Manufacturer name")
    model_name: Optional[str] = Field(None, description="Model name/number")


class NWBProcessingModule(BaseModel):
    """Processing module for organizing processed data.

    Based on pynwb.base.ProcessingModule specification.

    Attributes:
        name: Module name (must be unique)
        description: Description of the processing module
    """

    model_config = {"frozen": True, "extra": "forbid"}

    name: str = Field(..., description="Processing module name (must be unique)")
    description: str = Field(..., description="Description of the processing module")


class LabMetadata(BaseModel):
    """Lab-specific custom metadata.

    Flexible container for lab-specific fields that don't fit
    standard NWB schema. Will be stored in NWBFile.lab_meta_data.

    Note: Uses extra="allow" to permit arbitrary fields.
    """

    model_config = {"frozen": True, "extra": "allow"}  # Allow custom fields

    # Common fields (optional)
    room: Optional[str] = Field(None, description="Room where experiment was conducted")
    rig_id: Optional[str] = Field(None, description="Rig/setup identifier")
    training_stage: Optional[str] = Field(None, description="Training stage/protocol")
    water_restriction_start: Optional[str] = Field(None, description="Water restriction start date")
    target_weight: Optional[str] = Field(None, description="Target weight (with units)")


class GenerationInfo(BaseModel):
    """NWB file generation information.

    Metadata about the software and process used to generate
    the NWB file. Stored in NWBFile.scratch or provenance.

    Attributes:
        software_packages: List of software packages with versions
        creation_notes: Notes about file creation process
    """

    model_config = {"frozen": True, "extra": "forbid"}

    software_packages: Optional[List[str]] = Field(None, description="Software packages with versions (e.g., 'pynwb==2.8.0')")
    creation_notes: Optional[str] = Field(None, description="Notes about file creation process")


# =============================================================================
# Legacy Session Models (Backward Compatibility)
# =============================================================================


class SessionMetadata(BaseModel):
    """Session metadata and subject information.

    Attributes:
        id: Unique session identifier
        subject_id: Subject/animal identifier
        date: Session date (ISO 8601 format recommended)
        experimenter: Name of experimenter
        description: Session description
        sex: Subject sex (M/F/U)
        age: Subject age (e.g., "P60", "3mo")
        genotype: Subject genotype (e.g., "WT", "Cre+")

    Requirements:
        - FR-1: Session metadata for NWB
        - NFR-9: Support anonymized subject IDs
    """

    model_config = {"frozen": True, "extra": "forbid"}

    id: str = Field(..., description="Unique session identifier")
    subject_id: str = Field(..., description="Subject/animal identifier (supports anonymization)")
    date: str = Field(..., description="Session date (ISO 8601 format recommended)")
    experimenter: str = Field(..., description="Name or ID of experimenter")
    description: str = Field(..., description="Human-readable session description")
    sex: Literal["M", "F", "U"] = Field(..., description="Subject sex: 'M' (male), 'F' (female), or 'U' (unknown)")
    age: str = Field(..., description="Subject age (e.g., 'P60', '3mo', '2y')")
    genotype: str = Field(..., description="Subject genotype (e.g., 'WT', 'Cre+', 'KO')")


class BpodTrialType(BaseModel):
    """Bpod trial type synchronization configuration.

    Maps a trial type to its synchronization signal and TTL channel for
    absolute time alignment. Used to convert Bpod relative timestamps to
    absolute timestamps using external TTL recordings.

    Attributes:
        trial_type: Trial type identifier (matches Bpod trial classification)
        description: Human-readable description of trial type
        sync_signal: Bpod state/event name used for alignment (e.g., "W2L_Audio", "A2L_Audio")
        sync_ttl: TTL channel ID whose pulses correspond to sync_signal (references TTL.id)

    Requirements:
        - FR-11: Parse Bpod trials/events with absolute timestamps
        - FR-6: TTL-based temporal alignment

    Example:
        >>> trial_type = BpodTrialType(
        ...     trial_type=1,
        ...     description="Active whisker touch trials",
        ...     sync_signal="W2L_Audio",
        ...     sync_ttl="ttl_cue"
        ... )
    """

    model_config = {"frozen": True, "extra": "forbid"}

    trial_type: int = Field(..., description="Trial type identifier (matches Bpod trial classification)", ge=0)
    description: str = Field(..., description="Human-readable description of trial type")
    sync_signal: str = Field(..., description="Bpod state/event name used for alignment (e.g., 'W2L_Audio', 'A2L_Audio')")
    sync_ttl: str = Field(..., description="TTL channel ID whose pulses correspond to sync_signal (references TTL.id)")


class BpodSession(BaseModel):
    """Bpod file configuration for session.

    Attributes:
        path: Glob pattern for Bpod .mat files
        order: File ordering strategy (e.g., "name_asc", "time_asc")
        continuous_time: Whether to merge files with continuous timeline (default True)
        trial_type: List of trial type synchronization configurations

    Requirements:
        - FR-1: Discover Bpod files via patterns
        - FR-11: Parse Bpod trials/events with absolute time alignment
    """

    model_config = {"frozen": True, "extra": "forbid"}

    path: str = Field(..., description="Glob pattern for Bpod .mat files (e.g., 'Bpod/*.mat')")
    order: Literal["name_asc", "name_desc", "time_asc", "time_desc"] = Field(..., description="File ordering strategy: 'name_asc', 'name_desc', 'time_asc', 'time_desc'")
    continuous_time: bool = Field(True, description="Whether to merge files with continuous timeline (offset timestamps). If False, timestamps are preserved as-is.")
    trial_types: List[BpodTrialType] = Field(default_factory=list, description="List of trial type synchronization configurations")


class TTL(BaseModel):
    """TTL channel configuration.

    Defines a TTL channel that provides synchronization pulses.
    Cameras reference TTL channels via ttl_id for verification.

    Attributes:
        id: Unique TTL channel identifier
        description: Human-readable description
        paths: Glob pattern for TTL files

    Requirements:
        - FR-1: Discover TTL files via patterns
        - FR-2: Verify frame/TTL counts
        - FR-15: Validate camera-TTL references
    """

    model_config = {"frozen": True, "extra": "forbid"}

    id: str = Field(..., description="Unique TTL channel identifier (referenced by cameras)")
    description: str = Field(..., description="Human-readable description of TTL channel")
    paths: str = Field(..., description="Glob pattern for TTL pulse files (e.g., 'TTLs/cam_sync*.txt')")


class Camera(BaseModel):
    """Camera configuration.

    Defines a camera source with file patterns and TTL reference.

    Attributes:
        id: Unique camera identifier
        description: Human-readable description
        paths: Glob pattern for video files
        order: File ordering strategy (e.g., "name_asc", "time_asc")
        ttl_id: Reference to TTL channel for verification

    Requirements:
        - FR-1: Discover video files via patterns
        - FR-2: Verify frame counts against TTL
        - FR-15: Validate TTL reference exists
    """

    model_config = {"frozen": True, "extra": "forbid"}

    id: str = Field(..., description="Unique camera identifier")
    description: str = Field(..., description="Human-readable description of camera view")
    paths: str = Field(..., description="Glob pattern for video files (e.g., 'Video/cam0_*.avi')")
    order: Literal["name_asc", "name_desc", "time_asc", "time_desc"] = Field(..., description="File ordering strategy: 'name_asc', 'name_desc', 'time_asc', 'time_desc'")
    ttl_id: str = Field(..., description="Reference to TTL channel ID for frame/pulse verification")


class Session(BaseModel):
    """Session configuration model with NWB-compliant metadata.

    Top-level model loaded from session.toml containing comprehensive NWB
    metadata, file patterns, and relationships. Supports both new NWB-compliant
    format and legacy format for backward compatibility.

    NWB-Compliant Attributes:
        required: Required NWB fields (session_description, identifier, session_start_time)
        metadata: Optional NWB metadata (experimenter, keywords, experiment_description, etc.)
        subject: Subject information (species, sex, age, genotype, etc.)
        devices: List of devices used in the experiment
        processing_modules: List of processing modules for data organization
        lab_metadata: Lab-specific custom fields
        generation: File generation information

    Legacy Attributes (backward compatibility):
        session: Session metadata (deprecated - use required/metadata/subject instead)
        bpod: Bpod file configuration
        TTLs: List of TTL channel configurations
        cameras: List of camera configurations
        session_dir: Directory containing session.toml (populated by load_session)

    Requirements:
        - FR-1: Session-driven discovery
        - FR-7: NWB file assembly with comprehensive metadata
        - FR-15: Camera-TTL validation
        - NFR-6: Standards compliance (NWB best practices)
        - NFR-10: Type safety

    Example (NWB-compliant):
        >>> from w2t_bkin.config import load_session
        >>> session = load_session("data/raw/Session-001/session.toml")
        >>> session.required.identifier
        'Session-000001'
        >>> session.subject.subject_id
        'M001'
        >>> session.metadata.experimenter
        ['John Doe', 'Jane Smith']
        >>> [device.name for device in session.devices]
        ['bpod', 'camera_0', 'camera_1']

    Example (Legacy):
        >>> session.session.subject_id  # Still works for backward compatibility
        'Mouse-123'
    """

    model_config = {"frozen": True, "extra": "forbid"}

    # NWB-compliant fields (new)
    required: Optional[NWBRequired] = Field(None, description="Required NWB file metadata")
    metadata: Optional[NWBMetadata] = Field(None, description="Optional NWB metadata fields")
    subject: Optional[NWBSubject] = Field(None, description="Subject information")
    devices: List[NWBDevice] = Field(default_factory=list, description="List of devices used in experiment")
    processing_modules: List[NWBProcessingModule] = Field(default_factory=list, description="List of processing modules")
    lab_metadata: Optional[LabMetadata] = Field(None, description="Lab-specific custom metadata")
    generation: Optional[GenerationInfo] = Field(None, description="File generation information")

    # Legacy fields (backward compatibility)
    session: Optional[SessionMetadata] = Field(None, description="Legacy session metadata (deprecated - use required/metadata/subject)")
    bpod: Optional[BpodSession] = Field(None, description="Bpod file configuration")
    TTLs: List[TTL] = Field(default_factory=list, description="List of TTL channel configurations")
    cameras: List[Camera] = Field(default_factory=list, description="List of camera configurations")
    session_dir: str = Field(default=".", description="Directory containing session.toml (populated by load_session)")
