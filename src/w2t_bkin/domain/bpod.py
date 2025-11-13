"""Bpod file parsing domain models (Phase 3).

This module defines low-level Pydantic models for parsing Bpod MATLAB .mat files.
These models map directly to the MATLAB structure returned by the Bpod system,
handling numpy array conversions and optional fields.

Model Hierarchy:
---------------
**File Structure**:
- BpodMatFile: Root MATLAB file structure
  - SessionData: Complete session data
    - Info: Session metadata and hardware configuration
    - Analog: Analog data from Flex I/O channels
    - RawEvents: Trial-by-trial events and states
    - RawData: State machine configuration

**Hardware/Config**:
- SessionInfo: Bpod version, hardware, date/time
- FirmwareInfo, CircuitRevision, ModulesInfo, PCSetup
- AnalogData, AnalogInfo

**Trial-Level**:
- RawTrial: Raw events and states for a single trial
- StateTimings: State entry/exit times (ITI, Response_window, etc.)
- TrialEvents: Event timestamps (Port1In, Flex1Trig1, etc.)

Key Features:
-------------
- **MATLAB Compatibility**: Direct mapping from scipy.io.loadmat structures
- **Numpy Conversion**: Automatic conversion of numpy arrays to Python types
- **Flexible Schema**: ConfigDict(extra="allow") for protocol-specific states/events
- **Type Safe**: Full annotations with runtime validation via field_validators
- **Optional Fields**: Handles missing/NaN values from MATLAB
- **Immutable**: frozen=True prevents accidental modification (where appropriate)

Requirements:
-------------
- FR-11: Parse Bpod .mat files
- FR-14: Include trial/event summaries in QC

Acceptance Criteria:
-------------------
- A4: Bpod data in QC report

Usage:
------
>>> from pathlib import Path
>>> from scipy.io import loadmat
>>> from w2t_bkin.domain.bpod import BpodMatFile
>>>
>>> # Load and convert MATLAB .mat file
>>> raw_data = loadmat("session.mat", struct_as_record=False, squeeze_me=True)
>>> # ... convert MATLAB structs to dicts ...
>>> bpod_file = BpodMatFile(**data)
>>>
>>> # Access session info
>>> print(bpod_file.SessionData.Info.BpodSoftwareVersion)
>>> print(bpod_file.SessionData.nTrials)
>>>
>>> # Access trial data
>>> trial_0 = bpod_file.SessionData.RawEvents.Trial[0]
>>> print(trial_0.States.ITI)  # [start_time, end_time]
>>> print(trial_0.Events.Port1In)  # [timestamp1, timestamp2, ...]

See Also:
---------
- w2t_bkin.domain.trials: High-level trial domain models
- w2t_bkin.events: Bpod parsing implementation
- design.md: Bpod summary schema
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator

# ============================================================================
# Hardware and Configuration Models
# ============================================================================


class AnalogInfo(BaseModel):
    """Metadata descriptions for analog data fields."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    FileName: str = Field(description="Complete path and filename of the binary file")
    nChannels: str = Field(description="Number of Flex I/O channels as analog input")
    channelNumbers: str = Field(description="Indexes of Flex I/O channels as analog input")
    SamplingRate: str = Field(description="Sampling rate of analog data (Hz)")
    nSamples: str = Field(description="Total analog samples captured during session")
    Samples: str = Field(description="Analog measurements captured (Volts)")
    Timestamps: str = Field(description="Time of each sample")
    TrialNumber: str = Field(description="Experimental trial for each sample")
    Trial: str = Field(description="Cell array of samples per trial")


class AnalogData(BaseModel):
    """Analog data from Flex I/O channels during behavioral session."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    info: AnalogInfo
    FileName: str = Field(description="Path to binary analog data file")
    nChannels: int = Field(description="Number of analog input channels")
    channelNumbers: Union[int, List[int]] = Field(description="Channel indexes")
    SamplingRate: int = Field(description="Sampling rate in Hz")
    nSamples: int = Field(description="Total number of samples")

    @field_validator("channelNumbers", mode="before")
    @classmethod
    def convert_channel_numbers(cls, v: Any) -> Union[int, List[int]]:
        """Convert numpy array or int to appropriate type."""
        if isinstance(v, np.ndarray):
            return v.tolist() if v.size > 1 else int(v.item())
        return v


class FirmwareInfo(BaseModel):
    """Firmware version information."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    StateMachine: int = Field(description="State machine firmware version")
    StateMachine_Minor: int = Field(description="State machine minor version")


class CircuitRevision(BaseModel):
    """Circuit board revision information."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    StateMachine: int = Field(description="State machine circuit revision")


class ModulesInfo(BaseModel):
    """Information about connected Bpod modules."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    nModules: int = Field(description="Number of modules")
    RelayActive: List[int] = Field(description="Module relay activation status")
    Connected: List[int] = Field(description="Module connection status")
    Name: List[str] = Field(description="Module names (e.g., Serial1, Serial2)")
    Module2SM_BaudRate: List[int] = Field(description="Module to state machine baud rates")
    FirmwareVersion: List[int] = Field(description="Firmware versions")
    nSerialEvents: List[int] = Field(description="Number of serial events per module")
    EventNames: List[List[Any]] = Field(description="Event names per module")
    USBport: List[List[Any]] = Field(description="USB port assignments")
    HWVersion_Major: List[Optional[float]] = Field(description="Hardware major versions")
    HWVersion_Minor: List[Optional[float]] = Field(description="Hardware minor versions")

    @field_validator("RelayActive", "Connected", "FirmwareVersion", "nSerialEvents", mode="before")
    @classmethod
    def convert_numpy_array(cls, v: Any) -> List[int]:
        """Convert numpy arrays to Python lists."""
        if isinstance(v, np.ndarray):
            return v.tolist()
        return v

    @field_validator("Name", mode="before")
    @classmethod
    def convert_name_array(cls, v: Any) -> List[str]:
        """Convert numpy object array to string list."""
        if isinstance(v, np.ndarray):
            return [str(item) for item in v]
        return v

    @field_validator("Module2SM_BaudRate", mode="before")
    @classmethod
    def convert_baudrate_array(cls, v: Any) -> List[int]:
        """Convert numpy int32 array to Python int list."""
        if isinstance(v, np.ndarray):
            return v.tolist()
        return v

    @field_validator("EventNames", "USBport", mode="before")
    @classmethod
    def convert_nested_arrays(cls, v: Any) -> List[List[Any]]:
        """Convert nested numpy arrays to nested lists."""
        if isinstance(v, np.ndarray):
            return [arr.tolist() if isinstance(arr, np.ndarray) else [] for arr in v]
        return v

    @field_validator("HWVersion_Major", "HWVersion_Minor", mode="before")
    @classmethod
    def convert_version_array(cls, v: Any) -> List[Optional[float]]:
        """Convert numpy array with NaN to list with None."""
        if isinstance(v, np.ndarray):
            return [None if np.isnan(x) else float(x) for x in v]
        return v


class PCSetup(BaseModel):
    """PC setup information."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    OS: Optional[str] = Field(None, description="Operating system")
    MATLABver: str = Field(description="MATLAB version")


class SessionInfo(BaseModel):
    """Session metadata and hardware configuration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    BpodSoftwareVersion: str = Field(description="Bpod software version")
    StateMachineVersion: str = Field(description="State machine model")
    Firmware: FirmwareInfo
    CircuitRevision: CircuitRevision
    Modules: ModulesInfo
    PCsetup: PCSetup
    SessionDate: str = Field(description="Session date (DD-Mon-YYYY)")
    SessionStartTime_UTC: str = Field(description="Session start time UTC (HH:MM:SS)")
    SessionStartTime_MATLAB: float = Field(description="MATLAB serial date number")


# ============================================================================
# Trial-Level Models (Raw Bpod Data)
# ============================================================================


class StateTimings(BaseModel):
    """State entry and exit times for a trial."""

    model_config = ConfigDict(frozen=True, extra="allow")  # Allow protocol-specific states

    # Common states across trials
    ITI: Optional[List[float]] = Field(None, description="Inter-trial interval [start, end]")
    W2T_Audio: Optional[List[float]] = Field(None, description="Whisker-to-tone audio [start, end]")
    A2L_Audio: Optional[List[float]] = Field(None, description="Audio-to-lick audio [start, end]")
    Airpuff: Optional[List[float]] = Field(None, description="Airpuff stimulus [start, end]")
    Sensorcalm: Optional[List[float]] = Field(None, description="Sensor calm period [start, end]")
    Response_window: Optional[List[float]] = Field(None, description="Response window [start, end]")
    Miss: Optional[List[float]] = Field(None, description="Miss trial state [start, end]")
    HIT: Optional[List[float]] = Field(None, description="Hit trial state [start, end]")
    Licking_delay: Optional[List[float]] = Field(None, description="Licking delay [start, end]")
    LeftReward: Optional[List[float]] = Field(None, description="Left reward delivery [start, end]")
    RightReward: Optional[List[float]] = Field(None, description="Right reward delivery [start, end]")
    reward_window: Optional[List[float]] = Field(None, description="Reward window [start, end]")
    Microstim: Optional[List[float]] = Field(None, description="Microstimulation [start, end]")

    model_config = ConfigDict(frozen=True, extra="allow")  # Allow additional states not defined above

    @field_validator("*", mode="before")
    @classmethod
    def convert_state_times(cls, v: Any) -> Optional[List[float]]:
        """Convert numpy arrays to lists, handle NaN as None."""
        if v is None:
            return None
        if isinstance(v, np.ndarray):
            # Check if array contains NaN values
            if np.any(np.isnan(v)):
                return None
            return v.tolist()
        return v


class TrialEvents(BaseModel):
    """Events that occurred during a trial."""

    model_config = ConfigDict(frozen=True, extra="allow")  # Allow protocol-specific events

    Flex1Trig1: Optional[List[float]] = Field(None, description="Flex channel 1 trigger 1 times")
    Flex1Trig2: Optional[List[float]] = Field(None, description="Flex channel 1 trigger 2 times")
    Tup: Optional[List[float]] = Field(None, description="Timer up events")
    Port1In: Optional[List[float]] = Field(None, description="Port 1 entry times")
    Port1Out: Optional[List[float]] = Field(None, description="Port 1 exit times")
    Port2In: Optional[List[float]] = Field(None, description="Port 2 entry times")
    Port2Out: Optional[List[float]] = Field(None, description="Port 2 exit times")
    Port3In: Optional[List[float]] = Field(None, description="Port 3 entry times")
    Port3Out: Optional[List[float]] = Field(None, description="Port 3 exit times")

    model_config = ConfigDict(frozen=True, extra="allow")  # Allow additional events not defined above

    @field_validator("*", mode="before")
    @classmethod
    def convert_event_times(cls, v: Any) -> Optional[List[float]]:
        """Convert numpy arrays to lists, handle scalars as single-item lists."""
        if v is None:
            return None
        if isinstance(v, np.ndarray):
            if v.size == 0 or np.all(np.isnan(v)):
                return None
            # Filter out NaN values
            return [float(x) for x in v.ravel() if not np.isnan(x)]
        # Handle scalar values (convert to single-element list)
        if isinstance(v, (int, float, np.number)) and not np.isnan(v):
            return [float(v)]
        return v


class RawTrial(BaseModel):
    """Raw events and states for a single trial."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    States: StateTimings
    Events: TrialEvents


class RawEvents(BaseModel):
    """Collection of all trial events."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    Trial: List[RawTrial] = Field(description="Raw data for each trial")


class RawData(BaseModel):
    """Raw state machine data."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    OriginalStateNamesByNumber: List[List[str]] = Field(description="State names indexed by number for each trial")

    @field_validator("OriginalStateNamesByNumber", mode="before")
    @classmethod
    def convert_state_names(cls, v: Any) -> List[List[str]]:
        """Convert nested numpy object arrays to list of string lists."""
        if isinstance(v, np.ndarray):
            result = []
            for trial_states in v:
                if isinstance(trial_states, np.ndarray):
                    result.append([str(state) for state in trial_states])
                else:
                    result.append([])
            return result
        return v


# ============================================================================
# Session-Level Models
# ============================================================================


class SessionData(BaseModel):
    """Complete Bpod session data structure."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    Analog: AnalogData
    Info: SessionInfo
    SettingsFile: Dict[str, Any]
    nTrials: int
    RawEvents: RawEvents
    RawData: RawData
    TrialStartTimestamp: List[float]
    TrialEndTimestamp: List[float]
    TrialSettings: List[Dict[str, Any]]
    TrialTypes: List[int]

    @field_validator("TrialStartTimestamp", "TrialEndTimestamp", mode="before")
    @classmethod
    def convert_timestamps(cls, v: Any) -> List[float]:
        """Convert numpy arrays to Python lists."""
        if isinstance(v, np.ndarray):
            return v.tolist()
        return v

    @field_validator("TrialTypes", mode="before")
    @classmethod
    def convert_trial_types(cls, v: Any) -> List[int]:
        """Convert numpy uint8 array to Python int list."""
        if isinstance(v, np.ndarray):
            return v.tolist()
        return v


class BpodMatFile(BaseModel):
    """Root structure for Bpod MATLAB file."""

    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True, frozen=True, extra="forbid")

    header: bytes = Field(alias="__header__", description="MATLAB file header")
    version: str = Field(alias="__version__", description="MAT file version")
    globals_: List[Any] = Field(alias="__globals__", description="Global variables")
    SessionData: SessionData


# Rebuild models to resolve forward references
SessionData.model_rebuild()
BpodMatFile.model_rebuild()
