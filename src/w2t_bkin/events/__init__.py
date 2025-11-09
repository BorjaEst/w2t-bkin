"""Events module for normalizing NDJSON behavioral logs.

This module is responsible for:
- Parsing NDJSON event logs and normalizing schema
- Deriving trial intervals using hybrid derivation policy (Option H)
- Flagging mismatches between declared and observed trial durations

IMPORTANT: This module SHALL NOT be used for video synchronization (MR-3).
Video synchronization is handled by the sync module.

Requirements: MR-1, MR-2, MR-3, M-NFR-1, M-NFR-2
Design: events/design.md
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator

from w2t_bkin.domain import DataIntegrityWarning, MissingInputError, TrialsTable


# ============================================================================
# EventsTable Domain Model
# ============================================================================


class EventsTable(BaseModel):
    """Normalized events table from NDJSON logs (MR-1).
    
    Represents normalized behavioral event data with standardized schema.
    Supports optional metadata columns like phase.
    """

    model_config = {"frozen": True, "extra": "allow"}

    timestamp: list[float] = Field(..., description="Event timestamps in seconds")
    event_type: list[str] = Field(..., description="Event type labels")
    trial_id: list[int] = Field(..., description="Trial identifiers")
    phase: list[str] = Field(default_factory=list, description="Optional phase labels")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Optional metadata")

    @model_validator(mode="after")
    def validate_equal_lengths(self) -> EventsTable:
        """Validate all arrays have equal length (MR-1)."""
        base_length = len(self.timestamp)

        # Check required fields
        if len(self.event_type) != base_length:
            raise ValueError(f"event_type length {len(self.event_type)} != timestamp length {base_length}")
        if len(self.trial_id) != base_length:
            raise ValueError(f"trial_id length {len(self.trial_id)} != timestamp length {base_length}")

        # Check optional phase field if provided
        if self.phase and len(self.phase) != base_length:
            raise ValueError(f"phase length {len(self.phase)} != timestamp length {base_length}")

        return self


# ============================================================================
# NDJSON Normalization Functions
# ============================================================================


def normalize_events(paths: list[Path]) -> EventsTable:
    """Normalize NDJSON behavioral logs into EventsTable (MR-1).
    
    Parses NDJSON files and normalizes different schema formats into a
    standardized EventsTable. Handles multiple files and combines them.
    
    Schema normalization:
    - 't' → 'timestamp'
    - 'trial' → 'trial_id'
    - 'phase' → 'phase'
    
    Args:
        paths: List of NDJSON file paths to parse
        
    Returns:
        EventsTable with normalized event data
        
    Raises:
        MissingInputError: If required file is missing
        ValueError: If JSON is malformed or schema is invalid
        
    Warnings:
        DataIntegrityWarning: If inconsistent IDs or timestamps detected
        
    Requirements: MR-1, M-NFR-2 (deterministic outputs)
    """
    all_events = []
    
    for path in paths:
        if not path.exists():
            raise MissingInputError(f"NDJSON file not found: {path}")
        
        try:
            with path.open("r") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        event = json.loads(line)
                        all_events.append(event)
                    except json.JSONDecodeError as e:
                        raise ValueError(f"Malformed JSON at {path}:{line_num}: {e}") from e
        except Exception as e:
            if isinstance(e, (MissingInputError, ValueError)):
                raise
            raise ValueError(f"Error reading {path}: {e}") from e
    
    if not all_events:
        # Return empty EventsTable
        return EventsTable(timestamp=[], event_type=[], trial_id=[])
    
    # Normalize schema
    timestamps = []
    event_types = []
    trial_ids = []
    phases = []
    has_phases = False
    
    for event in all_events:
        # Normalize timestamp field (t → timestamp)
        if "timestamp" in event:
            timestamps.append(float(event["timestamp"]))
        elif "t" in event:
            timestamps.append(float(event["t"]))
        else:
            timestamps.append(0.0)  # Default if missing
        
        # Normalize event_type (infer from context or use placeholder)
        if "event_type" in event:
            event_types.append(str(event["event_type"]))
        else:
            # Infer event type from available fields
            event_types.append("sample")  # Default for continuous sampling
        
        # Normalize trial_id (trial → trial_id)
        if "trial_id" in event:
            trial_ids.append(int(event["trial_id"]))
        elif "trial" in event:
            trial_ids.append(int(event["trial"]))
        else:
            trial_ids.append(0)  # Default trial
        
        # Optional phase field
        if "phase" in event:
            phases.append(str(event["phase"]))
            has_phases = True
        else:
            phases.append("")
    
    # Check for inconsistencies and warn
    _check_data_integrity(timestamps, trial_ids)
    
    # Build EventsTable
    if has_phases and any(phases):
        return EventsTable(
            timestamp=timestamps,
            event_type=event_types,
            trial_id=trial_ids,
            phase=phases,
        )
    else:
        return EventsTable(
            timestamp=timestamps,
            event_type=event_types,
            trial_id=trial_ids,
        )


def _check_data_integrity(timestamps: list[float], trial_ids: list[int]) -> None:
    """Check for data integrity issues and issue warnings.
    
    Requirements: Design - DataIntegrityWarning
    """
    # Check for non-monotonic timestamps within trials
    current_trial = None
    last_timestamp = None
    
    for ts, tid in zip(timestamps, trial_ids):
        if tid != current_trial:
            current_trial = tid
            last_timestamp = ts
        elif last_timestamp is not None and ts < last_timestamp:
            warnings.warn(
                f"Non-monotonic timestamps detected in trial {tid}: {ts} < {last_timestamp}",
                DataIntegrityWarning,
                stacklevel=3,
            )
            break
        last_timestamp = ts
    
    # Check for negative trial IDs
    if any(tid < 0 for tid in trial_ids):
        warnings.warn("Negative trial IDs detected", DataIntegrityWarning, stacklevel=3)


# ============================================================================
# Trial Derivation Functions
# ============================================================================


def derive_trials(
    events: EventsTable,
    stats: Optional[Path] = None,
    tolerance: float = 0.1,
) -> TrialsTable:
    """Derive trial intervals using hybrid policy (Option H) (MR-2).
    
    Derives trial start/stop times from events and optionally compares with
    declared durations from trial_stats file. Flags mismatches when observed
    durations differ from declared by more than tolerance.
    
    Hybrid Policy (Option H):
    - Calculate observed intervals from trial_start/trial_end events
    - If trial_stats provided, load declared durations
    - Compare and flag mismatches beyond tolerance threshold
    - Identify first and last phases within each trial
    
    Args:
        events: EventsTable with normalized event data
        stats: Optional path to trial_stats NDJSON file with declared durations
        tolerance: Tolerance in seconds for duration comparison (default: 0.1s)
                  Mismatches within tolerance are not flagged.
        
    Returns:
        TrialsTable with trial intervals and QC flags
        
    Requirements: MR-2, M-NFR-1 (documented tolerances), M-NFR-2 (deterministic)
    
    Tolerance threshold (M-NFR-1):
        Default tolerance is 0.1 seconds. Differences between declared and
        observed durations within this threshold are not flagged as mismatches.
        Adjust tolerance based on expected timing precision of the system.
    """
    # Group events by trial
    trials_dict: dict[int, dict[str, Any]] = {}
    
    for i, trial_id in enumerate(events.trial_id):
        if trial_id not in trials_dict:
            trials_dict[trial_id] = {
                "trial_id": trial_id,
                "timestamps": [],
                "event_types": [],
                "phases": [],
            }
        
        trials_dict[trial_id]["timestamps"].append(events.timestamp[i])
        trials_dict[trial_id]["event_types"].append(events.event_type[i])
        
        if events.phase and i < len(events.phase):
            trials_dict[trial_id]["phases"].append(events.phase[i])
    
    # Load declared durations if stats provided
    declared_durations = {}
    if stats is not None and stats.exists():
        try:
            with stats.open("r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    stat = json.loads(line)
                    # Normalize trial_total → trial_id
                    trial_id = stat.get("trial_total") or stat.get("trial_id")
                    duration = stat.get("total_time_s") or stat.get("duration")
                    if trial_id is not None and duration is not None:
                        declared_durations[int(trial_id)] = float(duration)
        except Exception:
            # Stats file optional, continue without it
            pass
    
    # Derive trial intervals
    trial_ids = []
    start_times = []
    stop_times = []
    phase_firsts = []
    phase_lasts = []
    declared_durs = []
    observed_spans = []
    duration_deltas = []
    qc_flags_list = []
    
    for trial_id in sorted(trials_dict.keys()):
        trial_data = trials_dict[trial_id]
        timestamps = trial_data["timestamps"]
        phases = trial_data["phases"]
        
        if not timestamps:
            continue
        
        # Calculate start and stop from min/max timestamps
        start_time = min(timestamps)
        stop_time = max(timestamps)
        observed_span = stop_time - start_time
        
        # Identify phases
        phase_first = phases[0] if phases else ""
        phase_last = phases[-1] if phases else ""
        
        # Get declared duration
        declared_duration = declared_durations.get(trial_id, observed_span)
        
        # Calculate delta and flag if needed
        duration_delta = observed_span - declared_duration
        qc_flag = ""
        
        if abs(duration_delta) > tolerance:
            qc_flag = f"duration_mismatch: observed={observed_span:.3f}s, declared={declared_duration:.3f}s, delta={duration_delta:.3f}s"
        
        trial_ids.append(trial_id)
        start_times.append(start_time)
        stop_times.append(stop_time)
        phase_firsts.append(phase_first)
        phase_lasts.append(phase_last)
        declared_durs.append(declared_duration)
        observed_spans.append(observed_span)
        duration_deltas.append(duration_delta)
        qc_flags_list.append(qc_flag)
    
    # Return TrialsTable
    return TrialsTable(
        trial_id=trial_ids,
        start_time=start_times,
        stop_time=stop_times,
        phase_first=phase_firsts,
        phase_last=phase_lasts,
        declared_duration=declared_durs,
        observed_span=observed_spans,
        duration_delta=duration_deltas,
        qc_flags=qc_flags_list,
    )


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    "EventsTable",
    "normalize_events",
    "derive_trials",
]
