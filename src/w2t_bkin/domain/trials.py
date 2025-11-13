"""NWB-aligned behavioral trial domain models.

This module provides Pydantic models for representing behavioral trials and events
in a format compatible with NWB (Neurodata Without Borders) TimeIntervals and
BehavioralEvents structures.

Classes:
    Trial: Single trial row for NWB trials table with flexible protocol-specific columns
    TrialEvent: Single behavioral event occurrence (e.g., port entry, TTL pulse)
    BehavioralEvents: Event TimeSeries collection (e.g., all "Port1In" events)
    TrialOutcome: Enumeration of trial outcome classifications
    TrialSummary: Aggregated trial statistics for QC reporting

NWB Compatibility:
    - Trial maps to nwbfile.trials (TimeIntervals/DynamicTable)
    - BehavioralEvents map to processing["behavior"]["BehavioralEvents"]
    - TrialSummary belongs in ProcessingModule, not trials table
    - All times in absolute seconds from session_start_time
    - Extra fields validated for NWB compatibility (numeric, string, or bool only)

Example:
    >>> trial = Trial(
    ...     trial_number=1, trial_type=1, start_time=10.0, stop_time=15.5,
    ...     outcome=TrialOutcome.HIT, stimulus_id=5, correct=True
    ... )
    >>> event = TrialEvent(
    ...     event_type="Port1In", timestamp=12.3, metadata={"trial_number": 1}
    ... )
    >>> events = BehavioralEvents(
    ...     name="Port1In", description="Center port entries",
    ...     timestamps=[12.3, 25.1], trial_ids=[1, 2]
    ... )

See Also:
    - w2t_bkin.domain.bpod: Low-level Bpod parsing models
    - w2t_bkin.nwb: NWB file assembly
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class TrialOutcome(str, Enum):
    """Trial outcome classification for behavioral experiments."""

    HIT = "hit"
    MISS = "miss"
    FALSE_ALARM = "false_alarm"
    CORRECT_REJECTION = "correct_rejection"
    EARLY = "early"
    TIMEOUT = "timeout"


class TrialEvent(BaseModel):
    """Single behavioral event extracted from Bpod.

    Represents a single event occurrence (e.g., port entry, TTL pulse, reward delivery)
    within a trial. Events have relative timestamps (Bpod timebase) that must be
    converted to absolute time for NWB storage.

    Attributes:
        event_type: Event type identifier (e.g., "Port1In", "BNC1High", "Flex1Trig2")
        timestamp: Event timestamp (relative to trial start or absolute after alignment)
        metadata: Optional metadata dict for additional event information

    Requirements:
        - FR-11: Parse event data from Bpod
        - FR-14: Include in QC report

    Example:
        >>> event = TrialEvent(
        ...     event_type="Port1In",
        ...     timestamp=12.3,
        ...     metadata={"trial_number": 1.0}
        ... )
    """

    model_config = {"frozen": True, "extra": "forbid"}

    event_type: str = Field(..., description="Event type identifier (e.g., 'Port1In', 'BNC1High')")
    timestamp: float = Field(..., description="Event timestamp (relative or absolute seconds)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Optional metadata dict")


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
    All temporal fields are in absolute seconds relative to session_start_time.

    Accepts protocol-specific extra fields which are automatically validated
    to ensure NWB compatibility (must be numeric, string, or bool types).

    Attributes:
        trial_number: Sequential trial identifier (1-indexed, maps to NWB trials.id)
        trial_type: Protocol-specific trial type classification
        start_time: Trial start in absolute seconds (session_start_time reference)
        stop_time: Trial end in absolute seconds (session_start_time reference)
        outcome: Trial outcome (HIT, MISS, FALSE_ALARM, etc.)

    Note:
        Bpod timestamps must be converted to absolute seconds during parsing:
        absolute_time = session_start_time + bpod_time_offset + bpod_timestamp

    Example:
        >>> trial = Trial(
        ...     trial_number=1,
        ...     trial_type=1,
        ...     start_time=10.0,
        ...     stop_time=15.5,
        ...     outcome=TrialOutcome.HIT,
        ...     cue_time=11.0,
        ...     response_time=12.3,
        ...     stimulus_id=5,
        ...     correct=True
        ... )
    """

    model_config = {"frozen": True, "extra": "allow"}

    trial_number: int = Field(..., description="Sequential trial identifier (1-indexed, maps to NWB trials.id)", ge=1)
    trial_type: int = Field(..., description="Protocol-specific trial type classification", ge=0)
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

    In NWB, this belongs in processing["behavior"]["summary"] or lab_meta_data,
    NOT embedded in the trials table.

    Attributes:
        session_id: Session identifier
        total_trials: Total number of trials
        n_aligned: Number of trials successfully aligned to TTL (None if no alignment)
        n_dropped: Number of trials dropped during alignment (None if no alignment)
        outcome_counts: Dictionary of outcome counts (e.g., {"hit": 45, "miss": 5})
        trial_type_counts: Dictionary of trial type counts
        mean_trial_duration: Mean trial duration in seconds
        mean_response_latency: Mean response latency in seconds (for trials with responses)
        event_categories: List of unique event types observed
        bpod_files: List of Bpod .mat file paths processed
        alignment_warnings: List of alignment warnings (empty if no alignment)
        generated_at: ISO 8601 timestamp

    Example:
        >>> summary = TrialSummary(
        ...     session_id="Session-001",
        ...     total_trials=50,
        ...     n_aligned=48,
        ...     n_dropped=2,
        ...     outcome_counts={"hit": 45, "miss": 5},
        ...     trial_type_counts={1: 30, 2: 20},
        ...     mean_trial_duration=5.2,
        ...     mean_response_latency=1.3,
        ...     event_categories=["Port1In", "Port1Out", "LeftReward"],
        ...     bpod_files=["Bpod/session.mat"],
        ...     alignment_warnings=["Trial 3: missing sync_signal"],
        ...     generated_at="2025-11-13T10:30:00Z"
        ... )
    """

    model_config = {"frozen": True, "extra": "forbid"}

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
