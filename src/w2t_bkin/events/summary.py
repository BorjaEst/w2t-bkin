"""QC summary creation and persistence.

Generates TrialSummary objects for quality control reporting, including
trial counts, outcome distributions, event categories, and alignment statistics.
"""

from datetime import datetime
import logging
from pathlib import Path
from typing import List, Optional

from ..events.models import Trial, TrialEvent, TrialSummary
from ..utils import write_json

logger = logging.getLogger(__name__)


# =============================================================================
# Event Summary Creation
# =============================================================================


def create_event_summary(
    session_id: str,
    trials: List[Trial],
    events: List[TrialEvent],
    bpod_files: Optional[List[str]] = None,
    n_total_trials: Optional[int] = None,
    alignment_warnings: Optional[List[str]] = None,
) -> TrialSummary:
    """Create event summary for QC report from extracted data.

    This low-level API is Session-free. Callers must pass the resolved
    ``session_id`` and list of Bpod file paths explicitly. High-level code
    (e.g. ingest/orchestration) is responsible for deriving these values
    from `config.toml` / `session.toml`.

    Args:
        session_id: Identifier for the session (e.g. "Session-000001")
        trials: List of extracted trials
        events: List of extracted behavioral events
        bpod_files: List of Bpod file paths associated with the session
        n_total_trials: Total trials before alignment (for computing n_dropped)
        alignment_warnings: List of alignment warnings (if alignment was performed)

    Returns:
        TrialSummary object for QC reporting
    """
    if bpod_files is None:
        bpod_files = []

    # Count outcomes
    outcome_counts = {}
    for trial in trials:
        outcome_str = trial.outcome.value  # Get string value from enum
        outcome_counts[outcome_str] = outcome_counts.get(outcome_str, 0) + 1

    # Count trial types
    trial_type_counts = {}
    for trial in trials:
        trial_type_counts[trial.trial_type] = trial_type_counts.get(trial.trial_type, 0) + 1

    # Calculate mean trial duration from start_time/stop_time
    durations = [trial.stop_time - trial.start_time for trial in trials]
    mean_trial_duration = sum(durations) / len(durations) if durations else 0.0

    # Calculate mean response latency (only for trials with response_time field)
    latencies = []
    for trial in trials:
        # Check if trial has response_time field (protocol-specific)
        trial_dict = trial.model_dump()
        if "response_time" in trial_dict and trial_dict["response_time"] is not None:
            latency = trial_dict["response_time"] - trial.start_time
            latencies.append(latency)

    mean_response_latency = sum(latencies) / len(latencies) if latencies else None

    # Extract unique event categories
    event_categories = sorted(set(e.event_type for e in events))

    # Compute alignment stats if applicable
    n_aligned = None
    n_dropped = None
    if n_total_trials is not None:
        n_aligned = len(trials)
        n_dropped = n_total_trials - n_aligned

    summary = TrialSummary(
        session_id=session_id,
        total_trials=n_total_trials if n_total_trials is not None else len(trials),
        n_aligned=n_aligned,
        n_dropped=n_dropped,
        outcome_counts=outcome_counts,
        trial_type_counts=trial_type_counts,
        mean_trial_duration=mean_trial_duration,
        mean_response_latency=mean_response_latency,
        event_categories=event_categories,
        bpod_files=bpod_files,
        alignment_warnings=alignment_warnings if alignment_warnings is not None else [],
        generated_at=datetime.utcnow().isoformat(),
    )

    logger.info(f"Created event summary: {len(trials)} trials, {len(events)} events")
    return summary


def write_event_summary(summary: TrialSummary, output_path: Path) -> None:
    """Write event summary to JSON file.

    Args:
        summary: TrialSummary object to write
        output_path: Destination path for JSON file
    """
    data = summary.model_dump()
    write_json(data, output_path)
    logger.info(f"Wrote event summary to {output_path.name}")
