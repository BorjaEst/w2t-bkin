"""Behavioral events (Bpod) domain models (Phase 3).

This module defines models for Bpod behavioral data including trials,
events, and summary statistics. These are optional models used when
Bpod .mat files are present.

Model Hierarchy:
---------------
- TrialData: Single trial information
- BehavioralEvent: Single behavioral event
- BpodSummary: Summary for QC reporting

Key Features:
-------------
- **Immutable**: frozen=True prevents accidental modification
- **Strict Schema**: extra="forbid" rejects unknown fields
- **Type Safe**: Full annotations with runtime validation
- **Optional**: Only used when bpod.parse=true

Requirements:
-------------
- FR-11: Parse Bpod .mat files
- FR-14: Include trial/event summaries in QC

Acceptance Criteria:
-------------------
- A4: Bpod data in QC report

Usage:
------
>>> from w2t_bkin.domain.bpod import TrialData, BehavioralEvent
>>> trial = TrialData(
...     trial_number=1,
...     start_time=0.0,
...     stop_time=5.5,
...     outcome="correct"
... )
>>>
>>> event = BehavioralEvent(
...     event_type="nose_poke",
...     timestamp=2.3,
...     trial_number=1
... )

See Also:
---------
- w2t_bkin.events: Bpod parsing implementation
- design.md: Bpod summary schema
"""

from typing import List

from pydantic import BaseModel


class TrialData(BaseModel):
    """Trial data extracted from Bpod.

    Represents a single behavioral trial with temporal boundaries
    and outcome classification.

    Attributes:
        trial_number: Sequential trial identifier (1-indexed)
        start_time: Trial start time (seconds, Bpod timebase)
        stop_time: Trial stop time (seconds, Bpod timebase)
        outcome: Trial outcome classification (e.g., "correct", "incorrect", "miss")

    Requirements:
        - FR-11: Parse trial data from Bpod
        - FR-14: Include in QC report

    Note:
        Trial times are in Bpod's internal timebase and are NOT aligned
        to the video reference timebase (FR-11 explicitly states Bpod is
        not used for video timing).
    """

    model_config = {"frozen": True, "extra": "forbid"}

    trial_number: int
    start_time: float
    stop_time: float
    outcome: str


class BehavioralEvent(BaseModel):
    """Behavioral event extracted from Bpod.

    Represents a discrete behavioral event (e.g., nose poke, reward delivery)
    within a trial.

    Attributes:
        event_type: Event classification (e.g., "nose_poke", "reward", "tone")
        timestamp: Event timestamp (seconds, Bpod timebase)
        trial_number: Associated trial number (1-indexed)

    Requirements:
        - FR-11: Parse event data from Bpod
        - FR-14: Include in QC report

    Note:
        Event times are in Bpod's internal timebase and are NOT aligned
        to the video reference timebase.
    """

    model_config = {"frozen": True, "extra": "forbid"}

    event_type: str
    timestamp: float
    trial_number: int


class BpodSummary(BaseModel):
    """Bpod summary for QC report.

    Aggregates trial and event statistics for quality control reporting.
    Persisted as bpod_summary.json sidecar.

    Attributes:
        session_id: Session identifier
        total_trials: Total number of trials
        outcome_counts: Dictionary of outcome counts (e.g., {"correct": 45, "incorrect": 5})
        event_categories: List of unique event types observed
        bpod_files: List of Bpod .mat file paths processed
        generated_at: ISO 8601 timestamp

    Requirements:
        - FR-11: Parse Bpod data
        - FR-14: Include trial/event summaries in QC report

    Example:
        >>> summary = BpodSummary(
        ...     session_id="Session-001",
        ...     total_trials=50,
        ...     outcome_counts={"correct": 45, "incorrect": 5},
        ...     event_categories=["nose_poke", "reward", "tone"],
        ...     bpod_files=["Bpod/session.mat"],
        ...     generated_at="2025-11-13T10:30:00Z"
        ... )
    """

    model_config = {"frozen": True, "extra": "forbid"}

    session_id: str
    total_trials: int
    outcome_counts: dict
    event_categories: List[str]
    bpod_files: List[str]
    generated_at: str
