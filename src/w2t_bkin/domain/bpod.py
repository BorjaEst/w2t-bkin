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
- **Numpy Native**: Uses numpy arrays directly without conversion for efficiency
- **Flexible Schema**: ConfigDict(extra="allow") for protocol-specific states/events
- **Type Safe**: Full annotations with numpy type hints
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
import numpy.typing as npt
from pydantic import BaseModel, ConfigDict, Field

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

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    info: AnalogInfo
    FileName: str = Field(description="Path to binary analog data file")
    nChannels: int = Field(description="Number of analog input channels")
    channelNumbers: Union[int, npt.NDArray[np.integer]] = Field(description="Channel indexes (int or numpy array)")
    SamplingRate: int = Field(description="Sampling rate in Hz")
    nSamples: int = Field(description="Total number of samples")


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

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    nModules: int = Field(description="Number of modules")
    RelayActive: npt.NDArray[np.integer] = Field(description="Module relay activation status")
    Connected: npt.NDArray[np.integer] = Field(description="Module connection status")
    Name: npt.NDArray[np.object_] = Field(description="Module names (e.g., Serial1, Serial2)")
    Module2SM_BaudRate: npt.NDArray[np.integer] = Field(description="Module to state machine baud rates")
    FirmwareVersion: npt.NDArray[np.integer] = Field(description="Firmware versions")
    nSerialEvents: npt.NDArray[np.integer] = Field(description="Number of serial events per module")
    EventNames: npt.NDArray[np.object_] = Field(description="Event names per module (nested arrays)")
    USBport: npt.NDArray[np.object_] = Field(description="USB port assignments (nested arrays)")
    HWVersion_Major: npt.NDArray[np.floating] = Field(description="Hardware major versions (may contain NaN)")
    HWVersion_Minor: npt.NDArray[np.floating] = Field(description="Hardware minor versions (may contain NaN)")


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
    """Events that occurred during a trial."""

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

    Trial: List[RawTrial] = Field(description="Raw data for each trial")


class RawData(BaseModel):
    """Raw state machine data."""

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    OriginalStateNamesByNumber: npt.NDArray[np.object_] = Field(description="State names indexed by number for each trial (nested object array)")


# ============================================================================
# Session-Level Models
# ============================================================================


class SessionData(BaseModel):
    """Complete Bpod session data structure."""

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    Analog: AnalogData
    Info: SessionInfo
    SettingsFile: Dict[str, Any]
    nTrials: int
    RawEvents: RawEvents
    RawData: RawData
    TrialStartTimestamp: npt.NDArray[np.floating] = Field(description="Trial start timestamps")
    TrialEndTimestamp: npt.NDArray[np.floating] = Field(description="Trial end timestamps")
    TrialSettings: List[Dict[str, Any]]
    TrialTypes: npt.NDArray[np.integer] = Field(description="Trial type codes (uint8 array)")


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
