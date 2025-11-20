"""Events domain models (Phase 3).

This module defines Pydantic models for:

- Low-level Bpod MATLAB ``.mat`` file parsing (raw session structures).
- NWB-aligned behavioral trials and events (tool-local trial domain models).

These models are **owned by the events module** and are the canonical
representations for:

- Raw Bpod data used by ``w2t_bkin.events.bpod`` and ``w2t_bkin.events.trials``.
- Trial/event/summary structures used by QC and NWB assembly.

The old ``w2t_bkin.domain.bpod`` and ``w2t_bkin.domain.trials`` modules have
been consolidated here as part of the session-free tools refactor.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Union

import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, ConfigDict, Field, model_validator

# ============================================================================
# Enums and Constants
# ============================================================================


class TrialOutcome(str, Enum):
    """Trial outcome classification for behavioral experiments."""

    HIT = "hit"
    MISS = "miss"
    FALSE_ALARM = "false_alarm"
    CORRECT_REJECTION = "correct_rejection"
    EARLY = "early"
    TIMEOUT = "timeout"


# ============================================================================
# Hardware and Configuration Models
# ============================================================================


class AnalogInfo(BaseModel):
    """Metadata descriptions for analog data fields."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    FileName: str = Field(..., description="Complete path and filename of the binary file")
    nChannels: str = Field(..., description="Number of Flex I/O channels as analog input")
    channelNumbers: str = Field(..., description="Indexes of Flex I/O channels as analog input")
    SamplingRate: str = Field(..., description="Sampling rate of analog data (Hz)")
    nSamples: str = Field(..., description="Total analog samples captured during session")
    Samples: str = Field(..., description="Analog measurements captured (Volts)")
    Timestamps: str = Field(..., description="Time of each sample")
    TrialNumber: str = Field(..., description="Experimental trial for each sample")
    Trial: str = Field(..., description="Cell array of samples per trial")


class AnalogData(BaseModel):
    """Analog data from Flex I/O channels during behavioral session."""

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    info: AnalogInfo
    FileName: str = Field(..., description="Path to binary analog data file")
    nChannels: int = Field(..., description="Number of analog input channels")
    channelNumbers: Union[int, npt.NDArray[np.integer]] = Field(..., description="Channel indexes (int or numpy array)")
    SamplingRate: int = Field(..., description="Sampling rate in Hz")
    nSamples: int = Field(..., description="Total number of samples")


class FirmwareInfo(BaseModel):
    """Firmware version information."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    StateMachine: int = Field(..., description="State machine firmware version")
    StateMachine_Minor: int = Field(..., description="State machine minor version")


class CircuitRevision(BaseModel):
    """Circuit board revision information."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    StateMachine: int = Field(..., description="State machine circuit revision")


class ModulesInfo(BaseModel):
    """Information about connected Bpod modules."""

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    nModules: int = Field(..., description="Number of modules")
    RelayActive: npt.NDArray[np.integer] = Field(..., description="Module relay activation status")
    Connected: npt.NDArray[np.integer] = Field(..., description="Module connection status")
    Name: npt.NDArray[np.object_] = Field(..., description="Module names (e.g., Serial1, Serial2)")
    Module2SM_BaudRate: npt.NDArray[np.integer] = Field(..., description="Module to state machine baud rates")
    FirmwareVersion: npt.NDArray[np.integer] = Field(..., description="Firmware versions")
    nSerialEvents: npt.NDArray[np.integer] = Field(..., description="Number of serial events per module")
    EventNames: npt.NDArray[np.object_] = Field(..., description="Event names per module (nested arrays)")
    USBport: npt.NDArray[np.object_] = Field(..., description="USB port assignments (nested arrays)")
    HWVersion_Major: npt.NDArray[np.floating] = Field(..., description="Hardware major versions (may contain NaN)")
    HWVersion_Minor: npt.NDArray[np.floating] = Field(..., description="Hardware minor versions (may contain NaN)")


class PCSetup(BaseModel):
    """PC setup information."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    OS: Optional[str] = Field(None, description="Operating system")
    MATLABver: str = Field(..., description="MATLAB version")


class SessionInfo(BaseModel):
    """Session metadata and hardware configuration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    BpodSoftwareVersion: str = Field(..., description="Bpod software version")
    StateMachineVersion: str = Field(..., description="State machine model")
    Firmware: FirmwareInfo
    CircuitRevision: CircuitRevision
    Modules: ModulesInfo
    PCsetup: PCSetup
    SessionDate: str = Field(..., description="Session date (DD-Mon-YYYY)")
    SessionStartTime_UTC: str = Field(..., description="Session start time UTC (HH:MM:SS)")
    SessionStartTime_MATLAB: float = Field(..., description="MATLAB serial date number")


# ============================================================================
# Trial-Level Models (Raw Bpod Data)
# ============================================================================


class StateTimings(BaseModel):
    """State entry and exit times for a trial.

    Protocol-specific states allowed via extra='allow'.
    """

    model_config = ConfigDict(frozen=True, extra="allow", arbitrary_types_allowed=True)  # Allow protocol-specific states

    # Common states across trials (numpy arrays of [start, end] times, may contain NaN)
    ITI: Optional[npt.NDArray[np.floating]] = Field(None, description="Inter-trial interval [start, end]")
    W2T_Audio: Optional[npt.NDArray[np.floating]] = Field(None, description="Whisker-to-tone audio [start, end]")
    A2L_Audio: Optional[npt.NDArray[np.floating]] = Field(None, description="Audio-to-lick audio [start, end]")
    Airpuff: Optional[npt.NDArray[np.floating]] = Field(None, description="Airpuff stimulus [start, end]")
    Sensorcalm: Optional[npt.NDArray[np.floating]] = Field(None, description="Sensor calm period [start, end]")
    Response_window: Optional[npt.NDArray[np.floating]] = Field(None, description="Response window [start, end]")
    Miss: Optional[npt.NDArray[np.floating]] = Field(None, description="Miss trial state [start, end]")
    HIT: Optional[npt.NDArray[np.floating]] = Field(None, description="Hit trial state [start, end]")
    Licking_delay: Optional[npt.NDArray[np.floating]] = Field(None, description="Licking delay [start, end]")
    LeftReward: Optional[npt.NDArray[np.floating]] = Field(None, description="Left reward delivery [start, end]")
    RightReward: Optional[npt.NDArray[np.floating]] = Field(None, description="Right reward delivery [start, end]")
    reward_window: Optional[npt.NDArray[np.floating]] = Field(None, description="Reward window [start, end]")
    Microstim: Optional[npt.NDArray[np.floating]] = Field(None, description="Microstimulation [start, end]")


class TrialEvents(BaseModel):
    """Events that occurred during a trial.

    Protocol-specific events allowed via extra='allow'.
    """

    model_config = ConfigDict(frozen=True, extra="allow", arbitrary_types_allowed=True)  # Allow protocol-specific events

    # Common events (numpy arrays of timestamps, scalars, or None, may contain NaN)
    Flex1Trig1: Optional[Union[npt.NDArray[np.floating], np.number]] = Field(None, description="Flex channel 1 trigger 1 times")
    Flex1Trig2: Optional[Union[npt.NDArray[np.floating], np.number]] = Field(None, description="Flex channel 1 trigger 2 times")
    Tup: Optional[Union[npt.NDArray[np.floating], np.number]] = Field(None, description="Timer up events")
    Port1In: Optional[Union[npt.NDArray[np.floating], np.number]] = Field(None, description="Port 1 entry times")
    Port1Out: Optional[Union[npt.NDArray[np.floating], np.number]] = Field(None, description="Port 1 exit times")
    Port2In: Optional[Union[npt.NDArray[np.floating], np.number]] = Field(None, description="Port 2 entry times")
    Port2Out: Optional[Union[npt.NDArray[np.floating], np.number]] = Field(None, description="Port 2 exit times")
    Port3In: Optional[Union[npt.NDArray[np.floating], np.number]] = Field(None, description="Port 3 entry times")
    Port3Out: Optional[Union[npt.NDArray[np.floating], np.number]] = Field(None, description="Port 3 exit times")


class RawTrial(BaseModel):
    """Raw events and states for a single trial."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    States: StateTimings
    Events: TrialEvents


class RawEvents(BaseModel):
    """Collection of all trial events."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    Trial: List[RawTrial] = Field(..., description="Raw data for each trial")


class RawData(BaseModel):
    """Raw state machine data."""

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    OriginalStateNamesByNumber: npt.NDArray[np.object_] = Field(..., description="State names indexed by number for each trial (nested object array)")


# ============================================================================
# Session-Level Models
# ============================================================================


class SessionData(BaseModel):
    """Complete Bpod session data structure loaded from Bpod MATLAB .mat files."""

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    Analog: AnalogData
    Info: SessionInfo
    SettingsFile: Dict[str, Any]
    nTrials: int = Field(..., ge=0)
    RawEvents: RawEvents
    RawData: RawData
    TrialStartTimestamp: npt.NDArray[np.floating] = Field(..., description="Trial start timestamps")
    TrialEndTimestamp: npt.NDArray[np.floating] = Field(..., description="Trial end timestamps")
    TrialSettings: List[Dict[str, Any]]
    TrialTypes: npt.NDArray[np.integer] = Field(..., description="Trial type codes (uint8 array)")


class BpodMatFile(BaseModel):
    """Root structure for Bpod MATLAB file.

    Uses field aliases to map MATLAB's double-underscore naming convention.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True, populate_by_name=True)

    header: bytes = Field(..., alias="__header__", description="MATLAB file header")
    version: str = Field(..., alias="__version__", description="MAT file version")
    globals_: List[Any] = Field(..., alias="__globals__", description="Global variables")
    SessionData: SessionData


# Rebuild models to resolve forward references
SessionData.model_rebuild()
BpodMatFile.model_rebuild()


# ============================================================================
# NWB-aligned behavioral trial domain models (tool-local)
# ============================================================================


class TrialEvent(BaseModel):
    """Single behavioral event extracted from Bpod.

    Timestamps are in Bpod's internal timebase and must be converted to
    absolute session time for NWB storage.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_type: str = Field(..., description="Event type identifier (e.g., 'Port1In', 'BNC1High')")
    timestamp: float = Field(..., description="Event timestamp (relative or absolute seconds)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Optional metadata dict")


class BehavioralEvents(BaseModel):
    """Behavioral events as NWB-compatible TimeSeries.

    Groups all occurrences of a single event type across multiple trials.
    Timestamps must be in absolute seconds relative to session_start_time.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(..., description="Event type identifier (e.g., 'Port1In', 'LeftReward')")
    description: str = Field(..., description="Human-readable description of event type")
    timestamps: List[float] = Field(..., description="Event timestamps in absolute seconds (session_start_time)")
    trial_ids: Optional[List[int]] = Field(None, description="Trial numbers (1-indexed) corresponding to each event")
    data: Optional[List[float]] = Field(None, description="Optional event data values")
    unit: Optional[str] = Field(None, description="Optional unit for data values (e.g., 'volts', 'degrees')")


class Trial(BaseModel):
    """Single trial row for NWB trials table (NWB-aligned).

    All temporal fields in absolute seconds relative to session_start_time.
    Protocol-specific extra fields allowed with automatic NWB validation.
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    trial_number: int = Field(..., description="Sequential trial identifier (1-indexed, maps to NWB trials.id)", ge=1)
    trial_type: int = Field(..., description="Protocol-specific trial type classification", ge=0)
    start_time: float = Field(..., description="Trial start in absolute seconds (session_start_time reference)", ge=0)
    stop_time: float = Field(..., description="Trial end in absolute seconds (session_start_time reference)", ge=0)
    outcome: TrialOutcome = Field(..., description="Trial outcome classification")

    @model_validator(mode="after")
    def validate_nwb_compatibility(self) -> "Trial":
        """Validate that extra fields are NWB-compatible types.

        NWB DynamicTable columns must be numeric, string, or boolean types.

        Raises:
            ValueError: If extra field has incompatible type for NWB.
        """
        defined_fields = {"trial_number", "trial_type", "start_time", "stop_time", "outcome"}
        extra_fields = set(self.model_dump().keys()) - defined_fields

        for field_name in extra_fields:
            value = getattr(self, field_name)
            if value is None:
                continue

            if not isinstance(value, (int, float, str, bool)):
                raise ValueError(
                    f"Extra field '{field_name}' has type {type(value).__name__}, "
                    f"which is not NWB-compatible. NWB trials table columns must be "
                    f"numeric (int, float), string (str), or boolean (bool) types."
                )

        return self


class TrialSummary(BaseModel):
    """Aggregated trial statistics for QC reporting and NWB ProcessingModule.

    Store in NWB processing["behavior"]["summary"] or lab_meta_data.
    Do NOT embed in the NWB trials table.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    session_id: str = Field(..., description="Session identifier")
    total_trials: int = Field(..., description="Total number of trials in session", ge=0)
    n_aligned: Optional[int] = Field(None, description="Number of trials successfully aligned to TTL (None if no alignment)", ge=0)
    n_dropped: Optional[int] = Field(None, description="Number of trials dropped during alignment (None if no alignment)", ge=0)
    outcome_counts: Dict[str, int] = Field(..., description="Dictionary of outcome counts (e.g., {'hit': 45, 'miss': 5})")
    trial_type_counts: Dict[int, int] = Field(..., description="Dictionary of trial type counts (e.g., {1: 30, 2: 20})")
    mean_trial_duration: float = Field(..., description="Mean trial duration in seconds", ge=0)
    mean_response_latency: Optional[float] = Field(None, description="Mean response latency in seconds (for trials with responses)", ge=0)
    event_categories: List[str] = Field(..., description="List of unique event types observed in session")
    bpod_files: List[str] = Field(..., description="List of Bpod .mat file paths processed")
    alignment_warnings: List[str] = Field(default_factory=list, description="List of alignment warnings (empty if no alignment)")
    generated_at: str = Field(..., description="ISO 8601 timestamp of summary generation")
