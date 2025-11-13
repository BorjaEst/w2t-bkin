"""Behavioral trial domain models (Phase 3).

This module defines high-level domain models for behavioral trials,
providing a clean abstraction over raw Bpod data. These models represent
the semantic concept of a behavioral trial with structured information about
cues, responses, outcomes, and events.

Model Hierarchy:
---------------
- Trial: Complete behavioral trial with all information
- TrialEvent: Single behavioral event within a trial
- TrialOutcome: Trial outcome classification
- TrialSummary: Aggregated statistics for QC reporting

Key Features:
-------------
- **Immutable**: frozen=True prevents accidental modification
- **Strict Schema**: extra="forbid" rejects unknown fields
- **Type Safe**: Full annotations with runtime validation
- **Protocol-Agnostic**: Can represent different experimental protocols

Requirements:
-------------
- FR-11: Parse Bpod .mat files
- FR-14: Include trial/event summaries in QC

Acceptance Criteria:
-------------------
- A4: Bpod data in QC report

Usage:
------
>>> from w2t_bkin.domain.trials import Trial, TrialEvent, TrialOutcome
>>>
>>> # Create a trial
>>> trial = Trial(
...     trial_number=1,
...     trial_type=1,
...     start_time=0.0,
...     end_time=5.5,
...     outcome=TrialOutcome.HIT,
...     cue_time=1.0,
...     response_window_start=1.5,
...     response_window_end=3.5,
...     response_time=2.3,
...     events=[
...         TrialEvent(event_type="Port1In", timestamp=2.3),
...         TrialEvent(event_type="LeftReward", timestamp=2.5)
...     ]
... )
>>>
>>> # Access trial information
>>> print(f"Trial {trial.trial_number}: {trial.outcome.value}")
>>> print(f"Duration: {trial.duration:.2f}s")
>>> print(f"Response latency: {trial.response_latency:.2f}s")

See Also:
---------
- w2t_bkin.domain.bpod: Low-level Bpod file parsing models
- w2t_bkin.events: Bpod parsing implementation
- design.md: Trial structure and semantics
"""

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, computed_field


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


class TrialEvent(BaseModel):
    """Single behavioral event within a trial.

    Represents a discrete behavioral event (e.g., nose poke, lick, reward delivery)
    with its timestamp and optional metadata.

    Attributes:
        event_type: Event classification (e.g., "Port1In", "LeftReward", "Airpuff")
        timestamp: Event timestamp in seconds (Bpod timebase)
        metadata: Optional additional event information

    Requirements:
        - FR-11: Parse event data from Bpod
        - FR-14: Include in QC report

    Note:
        Event times are in Bpod's internal timebase and are NOT aligned
        to the video reference timebase.
    """

    model_config = {"frozen": True, "extra": "forbid"}

    event_type: str = Field(..., description="Event classification (e.g., 'Port1In', 'LeftReward', 'Airpuff')")
    timestamp: float = Field(..., description="Event timestamp in seconds (Bpod timebase)", ge=0)
    metadata: Optional[Dict[str, float]] = Field(None, description="Optional additional event information (e.g., {'value': 1.5})")


class Trial(BaseModel):
    """Complete behavioral trial with structured information.

    High-level representation of a single behavioral trial, containing
    temporal boundaries, task structure (cues, response windows), behavioral
    events, and outcome classification.

    Attributes:
        trial_number: Sequential trial identifier (1-indexed)
        trial_type: Protocol-specific trial type classification
        start_time: Trial start time in seconds (Bpod timebase)
        end_time: Trial end time in seconds (Bpod timebase)
        outcome: Trial outcome (HIT, MISS, FALSE_ALARM, etc.)
        cue_time: Time of cue presentation (optional)
        response_window_start: Start of response window (optional)
        response_window_end: End of response window (optional)
        response_time: Time of first response (optional)
        reward_time: Time of reward delivery (optional)
        events: List of behavioral events during trial
        settings: Protocol-specific trial settings

    Requirements:
        - FR-11: Parse trial data from Bpod
        - FR-14: Include in QC report

    Note:
        All times are in Bpod's internal timebase and are NOT aligned
        to the video reference timebase (FR-11 explicitly states Bpod is
        not used for video timing).

    Example:
        >>> trial = Trial(
        ...     trial_number=1,
        ...     trial_type=1,
        ...     start_time=0.0,
        ...     end_time=5.5,
        ...     outcome=TrialOutcome.HIT,
        ...     cue_time=1.0,
        ...     response_window_start=1.5,
        ...     response_window_end=3.5,
        ...     response_time=2.3,
        ...     events=[]
        ... )
        >>> print(f"Duration: {trial.duration:.2f}s")
        >>> print(f"Response latency: {trial.response_latency:.2f}s")
    """

    model_config = {"frozen": True, "extra": "forbid"}

    trial_number: int = Field(..., description="Sequential trial identifier (1-indexed)", ge=1)
    trial_type: int = Field(..., description="Protocol-specific trial type classification", ge=1)
    start_time: float = Field(..., description="Trial start time in seconds (Bpod timebase)", ge=0)
    end_time: float = Field(..., description="Trial end time in seconds (Bpod timebase)", ge=0)
    outcome: TrialOutcome = Field(..., description="Trial outcome classification")

    # Task structure (protocol-dependent)
    cue_time: Optional[float] = Field(None, description="Time of cue presentation (seconds, Bpod timebase)", ge=0)
    response_window_start: Optional[float] = Field(None, description="Start of response window (seconds, Bpod timebase)", ge=0)
    response_window_end: Optional[float] = Field(None, description="End of response window (seconds, Bpod timebase)", ge=0)
    response_time: Optional[float] = Field(None, description="Time of first response (seconds, Bpod timebase)", ge=0)
    reward_time: Optional[float] = Field(None, description="Time of reward delivery (seconds, Bpod timebase)", ge=0)

    # Events and settings
    events: List[TrialEvent] = Field(default_factory=list, description="List of behavioral events during trial")
    settings: Dict[str, float] = Field(default_factory=dict, description="Protocol-specific trial settings (e.g., {'stimulus_duration': 0.5})")

    @computed_field
    @property
    def duration(self) -> float:
        """Trial duration in seconds."""
        return self.end_time - self.start_time

    @computed_field
    @property
    def response_latency(self) -> Optional[float]:
        """Response latency from cue in seconds (None if no cue or no response)."""
        if self.cue_time is not None and self.response_time is not None:
            return self.response_time - self.cue_time
        return None

    @computed_field
    @property
    def reward_latency(self) -> Optional[float]:
        """Reward latency from response in seconds (None if no response or no reward)."""
        if self.response_time is not None and self.reward_time is not None:
            return self.reward_time - self.response_time
        return None


class TrialSummary(BaseModel):
    """Trial summary for QC report.

    Aggregates trial and event statistics for quality control reporting.
    Persisted as trial_summary.json sidecar.

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
