"""Behavioral trial domain models (Phase 3) - NWB-aligned.

This module defines high-level domain models for behavioral trials that align
with NWB (Neurodata Without Borders) standards. Models represent behavioral
trials in a columnar format compatible with NWB's TimeIntervals/DynamicTable
structure, with behavioral events as separate TimeSeries.

Model Hierarchy:
---------------
- Trial: Single trial row for NWB trials table (columnar format)
- BehavioralEvents: Behavioral events as TimeSeries (NWB BehavioralEvents)
- TrialOutcome: Trial outcome classification (enum for NWB column)
- TrialSummary: Aggregated statistics for NWB ProcessingModule

NWB Alignment:
--------------
**Trial Model**:
- Maps to one row in nwbfile.trials (TimeIntervals/DynamicTable)
- Required: start_time, stop_time (absolute seconds from session_start_time)
- User-defined columns: trial_type, outcome, cue_time, response times, etc.
- Accepts extra fields (extra="allow") for protocol-specific columns
- Extra fields validated to be NWB-compatible (numeric, string, or bool types)

**BehavioralEvents Model**:
- Represents BehavioralEvents TimeSeries in NWB
- Events stored separately from trials table
- Links to trials via TimeSeriesReferenceVectorData or time-based queries

**TrialSummary Model**:
- Belongs in NWB ProcessingModule (e.g., "behavior/summary")
- NOT embedded in trials table

**Timebase Requirements**:
- All times MUST be in absolute seconds relative to session_start_time
- Conversion from Bpod timebase to NWB timebase happens during parsing
- See FR-11: Bpod data parsed and aligned to session reference

Key Features:
-------------
- **NWB-Compatible**: Columnar format matching NWB TimeIntervals
- **Immutable**: frozen=True prevents accidental modification
- **Flexible Schema**: extra="allow" accepts protocol-specific columns
- **Type Safe**: Full annotations with runtime validation
- **Protocol-Agnostic**: Can represent different experimental protocols

Requirements:
-------------
- FR-11: Parse Bpod .mat files
- FR-14: Include trial/event summaries in QC
- FR-7: NWB file assembly

Acceptance Criteria:
-------------------
- A4: Bpod data in QC report
- A1: Create NWB files from manifest

Usage:
------
>>> from w2t_bkin.domain.trials import Trial, BehavioralEvents, TrialOutcome
>>>
>>> # Create a trial (NWB-compatible columnar format)
>>> trial = Trial(
...     trial_number=1,
...     trial_type=1,
...     start_time=10.0,  # Absolute time from session_start_time
...     stop_time=15.5,   # Absolute time from session_start_time
...     outcome=TrialOutcome.HIT,
...     cue_time=11.0,
...     response_window_start=11.5,
...     response_window_end=13.5,
...     response_time=12.3,
...     # Protocol-specific columns (automatically validated for NWB compatibility)
...     stimulus_id=5,
...     reward_volume=0.01,
...     correct=True
... )
>>>
>>> # Create behavioral events (separate from trials)
>>> events = BehavioralEvents(
...     name="Port1In",
...     description="Center port entries",
...     timestamps=[12.3, 25.1, 38.7],  # Absolute times
...     trial_ids=[1, 2, 3]  # Links to trial_number
... )
>>>
>>> # Access trial information
>>> print(f"Trial {trial.trial_number}: {trial.outcome.value}")

See Also:
---------
- w2t_bkin.domain.bpod: Low-level Bpod file parsing models
- w2t_bkin.events: Bpod parsing implementation
- w2t_bkin.nwb: NWB file assembly
- design.md: Trial structure and semantics
- NWB 2.x TimeIntervals: https://pynwb.readthedocs.io/en/stable/tutorials/general/plot_timeintervals.html
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class TrialOutcome(str, Enum):
    """Trial outcome classification.

    Common outcomes for behavioral experiments:
    - HIT: Correct response within response window
    - MISS: No response or response outside window
    - FALSE_ALARM: Incorrect response
    - CORRECT_REJECTION: Correct withholding of response
    - EARLY: Response before response window
    - TIMEOUT: No response within timeout period
    """

    HIT = "hit"
    MISS = "miss"
    FALSE_ALARM = "false_alarm"
    CORRECT_REJECTION = "correct_rejection"
    EARLY = "early"
    TIMEOUT = "timeout"


class BehavioralEvents(BaseModel):
    """Behavioral events as NWB-compatible TimeSeries.

    Represents a collection of behavioral events of the same type (e.g., all
    "Port1In" events) across multiple trials. Maps to NWB BehavioralEvents
    TimeSeries structure.

    In NWB, behavioral events are stored separately from the trials table:
    - Each event type gets its own TimeSeries (e.g., "Port1In", "LeftReward")
    - Events are linked to trials via trial_ids or by time-based queries
    - Stored in nwbfile.processing["behavior"].data_interfaces["BehavioralEvents"]

    Attributes:
        name: Event type identifier (e.g., "Port1In", "LeftReward", "Airpuff")
        description: Human-readable description of event type
        timestamps: Event timestamps in absolute seconds (session_start_time)
        trial_ids: Optional trial numbers corresponding to each event
        data: Optional event data values (for continuous events)
        unit: Optional unit for data values (e.g., "volts", "degrees")

    Requirements:
        - FR-11: Parse event data from Bpod
        - FR-14: Include in QC report
        - FR-7: NWB file assembly

    Note:
        All timestamps MUST be in absolute seconds relative to session_start_time,
        NOT in Bpod's internal timebase. Conversion happens during parsing.

    Example:
        >>> events = BehavioralEvents(
        ...     name="Port1In",
        ...     description="Center port entry events",
        ...     timestamps=[12.3, 25.1, 38.7],
        ...     trial_ids=[1, 2, 3]
        ... )
        >>> print(f"{events.name}: {len(events.timestamps)} events")
    """

    model_config = {"frozen": True, "extra": "forbid"}

    name: str = Field(..., description="Event type identifier (e.g., 'Port1In', 'LeftReward')")
    description: str = Field(..., description="Human-readable description of event type")
    timestamps: List[float] = Field(..., description="Event timestamps in absolute seconds (session_start_time)")
    trial_ids: Optional[List[int]] = Field(None, description="Trial numbers (1-indexed) corresponding to each event")
    data: Optional[List[float]] = Field(None, description="Optional event data values")
    unit: Optional[str] = Field(None, description="Optional unit for data values (e.g., 'volts', 'degrees')")


class Trial(BaseModel):
    """Single trial row for NWB trials table (NWB-aligned).

    Represents one row in the NWB trials table (TimeIntervals/DynamicTable).
    All temporal fields are in absolute seconds relative to session_start_time,
    following NWB's unified timebase requirement.

    Accepts protocol-specific extra fields which are automatically validated
    to ensure NWB compatibility (must be numeric, string, or bool types).

    Attributes:
        trial_number: Sequential trial identifier (1-indexed, maps to NWB trials.id)
        trial_type: Protocol-specific trial type classification
        start_time: Trial start in absolute seconds (session_start_time reference)
        stop_time: Trial end in absolute seconds (session_start_time reference)
        outcome: Trial outcome (HIT, MISS, FALSE_ALARM, etc.)
        **extra: Protocol-specific columns (validated for NWB compatibility)

    Requirements:
        - FR-11: Parse trial data from Bpod
        - FR-14: Include in QC report
        - FR-7: NWB file assembly

    Timebase Conversion:
        Bpod timestamps must be converted to absolute seconds during parsing:
        - absolute_time = session_start_time + bpod_time_offset + bpod_timestamp
        - See FR-11: Bpod data parsed and aligned to session reference

    NWB Writing Strategy:
        When writing to NWB:
        1. Create trials table: nwbfile.add_trial_column() for custom columns
        2. Add each trial: nwbfile.add_trial(start_time, stop_time, **columns)
        3. Store events separately: BehavioralEvents TimeSeries in processing module
        4. Link events to trials via trial_ids or time-based queries

    Example:
        >>> trial = Trial(
        ...     trial_number=1,
        ...     trial_type=1,
        ...     start_time=10.0,  # Absolute seconds from session_start_time
        ...     stop_time=15.5,   # Absolute seconds from session_start_time
        ...     outcome=TrialOutcome.HIT,
        ...     cue_time=11.0,
        ...     response_time=12.3,
        ...     reward_time=12.5,
        ...     stimulus_id=5,
        ...     correct=True
        ... )
        >>> print(f"Trial {trial.trial_number}: {trial.outcome.value}")
    """

    model_config = {"frozen": True, "extra": "allow"}

    trial_number: int = Field(..., description="Sequential trial identifier (1-indexed, maps to NWB trials.id)", ge=1)
    trial_type: int = Field(..., description="Protocol-specific trial type classification", ge=1)
    start_time: float = Field(..., description="Trial start in absolute seconds (session_start_time reference)", ge=0)
    stop_time: float = Field(..., description="Trial end in absolute seconds (session_start_time reference)", ge=0)
    outcome: TrialOutcome = Field(..., description="Trial outcome classification")

    @model_validator(mode="after")
    def validate_nwb_compatibility(self) -> "Trial":
        """Validate that extra fields are NWB-compatible types.

        NWB TimeIntervals/DynamicTable columns must be:
        - Numeric types: int, float
        - String types: str
        - Boolean types: bool
        - Optional (None) versions of the above

        Raises:
            ValueError: If extra field has incompatible type for NWB
        """
        # Get all fields that were passed as extras
        defined_fields = {"trial_number", "trial_type", "start_time", "stop_time", "outcome"}
        extra_fields = set(self.model_dump().keys()) - defined_fields

        for field_name in extra_fields:
            value = getattr(self, field_name)
            if value is None:
                continue  # None is acceptable for optional columns

            # Check if value is NWB-compatible
            if not isinstance(value, (int, float, str, bool)):
                raise ValueError(
                    f"Extra field '{field_name}' has type {type(value).__name__}, "
                    f"which is not NWB-compatible. NWB trials table columns must be "
                    f"numeric (int, float), string (str), or boolean (bool) types."
                )

        return self


class TrialSummary(BaseModel):
    """Trial summary for QC report and NWB ProcessingModule.

    Aggregates trial and event statistics for quality control reporting.
    In NWB, this belongs in a ProcessingModule (e.g., "behavior/summary")
    rather than embedded in the trials table.

    Persisted as trial_summary.json sidecar and can be added to NWB as:
    - A DynamicTable in processing["behavior"]["summary"]
    - Or as lab_meta_data for session-level statistics

    Attributes:
        session_id: Session identifier
        total_trials: Total number of trials
        outcome_counts: Dictionary of outcome counts (e.g., {"hit": 45, "miss": 5})
        trial_type_counts: Dictionary of trial type counts
        mean_trial_duration: Mean trial duration in seconds
        mean_response_latency: Mean response latency in seconds (for trials with responses)
        event_categories: List of unique event types observed
        bpod_files: List of Bpod .mat file paths processed
        generated_at: ISO 8601 timestamp

    Requirements:
        - FR-11: Parse Bpod data
        - FR-14: Include trial/event summaries in QC report
        - FR-7: NWB file assembly (as ProcessingModule)

    NWB Storage:
        Store in nwbfile.processing["behavior"].add_container() or as
        lab_meta_data for session-wide behavioral statistics.

    Example:
        >>> summary = TrialSummary(
        ...     session_id="Session-001",
        ...     total_trials=50,
        ...     outcome_counts={"hit": 45, "miss": 5},
        ...     trial_type_counts={1: 30, 2: 20},
        ...     mean_trial_duration=5.2,
        ...     mean_response_latency=1.3,
        ...     event_categories=["Port1In", "Port1Out", "LeftReward"],
        ...     bpod_files=["Bpod/session.mat"],
        ...     generated_at="2025-11-13T10:30:00Z"
        ... )
    """

    model_config = {"frozen": True, "extra": "forbid"}

    session_id: str = Field(..., description="Session identifier")
    total_trials: int = Field(..., description="Total number of trials in session", ge=0)
    outcome_counts: Dict[str, int] = Field(..., description="Dictionary of outcome counts (e.g., {'hit': 45, 'miss': 5})")
    trial_type_counts: Dict[int, int] = Field(..., description="Dictionary of trial type counts (e.g., {1: 30, 2: 20})")
    mean_trial_duration: float = Field(..., description="Mean trial duration in seconds", ge=0)
    mean_response_latency: Optional[float] = Field(None, description="Mean response latency in seconds (for trials with responses)", ge=0)
    event_categories: List[str] = Field(..., description="List of unique event types observed in session")
    bpod_files: List[str] = Field(..., description="List of Bpod .mat file paths processed")
    generated_at: str = Field(..., description="ISO 8601 timestamp of summary generation")
