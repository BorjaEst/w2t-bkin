# Events Module

## Overview

The `events` module normalizes behavioral event logs in NDJSON format to structured Trials and Events tables aligned to the session timebase. This is an **optional** Layer 2 processing stage that imports precomputed behavioral data without performing inference.

## Requirements

- **FR-11**: WHERE event NDJSON logs are present, THE SYSTEM SHALL import them as a Trials TimeIntervals table and BehavioralEvents without using them for video synchronization
- **NFR-7**: Optional stages SHALL be pluggable and import precomputed results
- **NFR-1**: Reproducibility - identical inputs produce identical outputs
- **NFR-2**: Idempotence - re-running without changes is a no-op
- **NFR-3**: Observability - emit structured logs and JSON summaries

## Design

See `design.md` §3.5 (Trials Table) and §2 (Module Breakdown - events).

## Architecture

- **Layer**: 2 (Processing Stage)
- **Dependencies**: `domain` (Event, Trial), `utils` (I/O, hashing), `config` (Settings)
- **Outputs**: `trials.csv`, `events.csv`, `events_summary.json`

## API

### Primary Function

```python
normalize_events(
    input_paths: list[Path],
    output_dir: Path,
    schema: str = "trials_events",
    force: bool = False
) -> EventsSummary
```

Normalizes NDJSON behavioral logs to Trials/Events tables.

**Arguments:**
- `input_paths`: List of paths to NDJSON event files
- `output_dir`: Directory for output tables and summary
- `schema`: Normalization schema (default: "trials_events")
- `force`: Force reprocessing even if outputs exist

**Returns:**
- `EventsSummary` dataclass with statistics and provenance

**Raises:**
- `MissingInputError`: Required input file not found
- `EventsFormatError`: Invalid NDJSON structure
- `EventsValidationError`: Data fails validation rules

## Data Contracts

### Input Format: NDJSON

Two types of event logs are supported:

#### 1. Training Events (`*_training.ndjson`)

Each line is a JSON object representing a behavioral event with timestamp:

```json
{"t": 0.0019, "phase": "OUT_OF_LANE", "trial": 0, "valid": true, "x_center": 1003.59, "angle": 94.13, "used_preproc": false, "marker_ids": [4,1,3], "marker_centers": [[826.75,710.75],[856.5,299],[1188.75,363]]}
```

**Required fields:**
- `t`: Timestamp in seconds (float)
- `phase`: Event phase/type (string)
- `trial`: Trial index (int)

**Optional fields:**
- All other fields preserved as metadata

#### 2. Trial Stats (`*_trial_stats.ndjson`)

Each line is a JSON object representing a trial summary:

```json
{"trial_total": 1, "solved": true, "total_time_s": 4.426, "turn_direction": "RIGHT", "target_lane_deg": 0, "entered_lane_deg": 0}
```

**Required fields:**
- `trial_total`: Trial ID (int, 1-indexed)
- `total_time_s`: Trial duration (float)

**Optional fields:**
- `solved`: Success boolean
- `turn_direction`: Direction string
- `target_lane_deg`, `entered_lane_deg`: Lane angles
- All other fields preserved as metadata

### Output Format: CSV + Parquet

#### Trials Table (`trials.csv`)

Columns matching `domain.Trial` contract:
- `trial_id`: Trial identifier (int, 0-indexed)
- `start_time`: Trial start in session timebase (float, seconds)
- `stop_time`: Trial stop in session timebase (float, seconds)
- `phase_first`: First phase observed (string)
- `phase_last`: Last phase observed (string)
- `declared_duration`: Duration from trial_stats (float, seconds)
- `observed_span`: Computed duration from events (float, seconds)
- `duration_delta`: Difference between declared and observed (float, seconds)
- `qc_flags`: Comma-separated QC warnings (string)

#### Events Table (`events.csv`)

Columns matching `domain.Event` contract:
- `time`: Event timestamp in session timebase (float, seconds)
- `kind`: Event type/phase (string)
- `payload`: JSON-encoded metadata (string)

### Summary Output (`events_summary.json`)

Structure:
```json
{
  "session_id": "session_t02",
  "n_trials": 10,
  "n_events": 1234,
  "trial_statistics": {
    "mean_duration_s": 15.3,
    "median_duration_s": 12.1,
    "solved_ratio": 0.8
  },
  "qc_flags": ["duration_mismatch_trial_3"],
  "skipped": false,
  "output_paths": {
    "trials": "data/interim/session_t02/events/trials.csv",
    "events": "data/interim/session_t02/events/events.csv"
  },
  "provenance": {
    "input_files": ["..."],
    "input_hashes": {"...": "..."},
    "timestamp": "2025-11-10T12:00:00Z",
    "schema": "trials_events"
  }
}
```

## Processing Flow

1. **Input Discovery**: Find NDJSON files matching configured patterns
2. **Format Detection**: Classify as training events or trial stats
3. **Parse & Validate**: Load NDJSON, validate required fields
4. **Align Timestamps**: Convert to session timebase (if needed)
5. **Construct Trials**: Build Trial objects from trial_stats + events
6. **Validate Consistency**: Check duration mismatches, overlaps, gaps
7. **Export Tables**: Write CSV/Parquet with domain contracts
8. **Generate Summary**: Compute statistics and provenance

## Configuration

From `config.EventsConfig`:

```toml
[events]
patterns = [
    "**/*_training.ndjson",
    "**/*_trial_stats.ndjson"
]
format = "ndjson"
```

## Quality Checks

### Data Validation

- **Required fields present**: All mandatory fields exist
- **Timestamp monotonicity**: Events within trial are chronologically ordered
- **Trial continuity**: No gaps or overlaps between trials
- **Duration consistency**: `declared_duration` matches `observed_span` within tolerance
- **Phase transitions**: Valid phase sequence (configurable)

### QC Flags

- `missing_trial_stats`: Events exist but no corresponding trial_stats entry
- `duration_mismatch_trial_N`: Declared vs observed duration exceeds threshold
- `overlapping_trials`: Trial N+1 starts before trial N ends
- `invalid_phase_transition`: Unexpected phase sequence
- `negative_duration`: stop_time < start_time

## Error Handling

| Exception | Cause | Response |
|-----------|-------|----------|
| `MissingInputError` | No NDJSON files found | Fail fast with path suggestion |
| `EventsFormatError` | Invalid JSON or missing required fields | Abort with line number |
| `EventsValidationError` | Data fails validation rules | Warn and flag in QC |
| `TimestampAlignmentError` | Cannot align to session timebase | Abort with diagnostic |

## Idempotence

- **Check existing outputs**: If `trials.csv` and `events.csv` exist with matching input hashes, skip processing
- **Force flag**: Override idempotence check
- **Provenance tracking**: Record input file hashes in summary

## Testing Strategy

### Unit Tests

- **Parse training events**: Valid NDJSON → Event objects
- **Parse trial stats**: Valid NDJSON → Trial metadata
- **Construct trials**: Merge events and stats into Trial objects
- **Timestamp alignment**: Convert event times to session timebase
- **Validation**: Duration mismatches, overlaps, invalid phases
- **QC flag generation**: Proper warning generation
- **Idempotence**: Skip when outputs exist
- **Error cases**: Missing files, invalid JSON, validation failures

### Integration Tests

- Full pipeline with sample NDJSON files
- Verify CSV output matches domain contracts
- Validate summary statistics

## Dependencies

### Internal (Layer 0-1)
- `w2t_bkin.domain`: Event, Trial, MissingInputError
- `w2t_bkin.utils`: read_json, write_json, write_csv, file_hash
- `w2t_bkin.config`: EventsConfig

### External
- `pathlib`: Path handling
- `json`: NDJSON parsing
- `dataclasses`: Data structures
- Standard library only (no heavy ML/CV deps)

## Usage Example

```python
from pathlib import Path
from w2t_bkin.events import normalize_events

# Discover NDJSON files
input_paths = [
    Path("data/raw/session_t02/2025-11-06_training.ndjson"),
    Path("data/raw/session_t02/2025-11-06_trial_stats.ndjson")
]

# Normalize to tables
summary = normalize_events(
    input_paths=input_paths,
    output_dir=Path("data/interim/session_t02/events"),
    schema="trials_events",
    force=False
)

# Check results
print(f"Processed {summary.n_trials} trials, {summary.n_events} events")
print(f"QC flags: {summary.qc_flags}")
```

## Output Structure

```
data/interim/<session_id>/events/
├── trials.csv          # Trial intervals with QC metadata
├── events.csv          # Behavioral events timestamped
└── events_summary.json # Processing statistics and provenance
```

## Future Enhancements

- Support for additional event schemas (custom formats)
- Real-time event stream processing
- Advanced phase transition validation with state machines
- Integration with external behavior classification models

## References

- **Requirements**: `requirements.md` FR-11, NFR-7
- **Design**: `design.md` §3.5, §2
- **API**: `api.md` §3.9
- **Domain**: `src/w2t_bkin/domain/__init__.py` (Event, Trial)
