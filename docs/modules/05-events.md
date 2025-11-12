# Events Module

**Phase:** 3 (Optional Modalities)  
**Status:** ✅ Complete  
**Requirements:** FR-11, FR-14, NFR-7

## Purpose

Parses Bpod .mat files into TrialData and BehavioralEvents, generates QC summaries. Extracts trial timing, states, and events from Bpod SessionData structure. Infers trial outcomes from visited states (handling NaN for unvisited states).

## Key Functions

### Bpod File Parsing

```python
def parse_bpod_mat(path: Path) -> Dict[str, Any]:
    """Parse Bpod MATLAB .mat file.

    Args:
        path: Path to .mat file

    Returns:
        Dictionary with parsed Bpod data

    Raises:
        EventsError: If file not found
        BpodParseError: If file cannot be parsed

    Note:
        Requires scipy. Uses loadmat with squeeze_me=True, struct_as_record=False

    Example:
        >>> from w2t_bkin.events import parse_bpod_mat
        >>> data = parse_bpod_mat(Path("Bpod_Session_001.mat"))
        >>> print(data.keys())  # ['SessionData', '__header__', ...]
    """

def validate_bpod_structure(data: Dict[str, Any]) -> bool:
    """Validate Bpod data structure.

    Checks for required fields:
    - SessionData.nTrials
    - SessionData.TrialStartTimestamp
    - SessionData.TrialEndTimestamp
    - SessionData.RawEvents.Trial

    Args:
        data: Parsed Bpod data

    Returns:
        True if structure is valid, False otherwise

    Note:
        Handles both dict and scipy mat_struct objects
    """
```

### Trial Extraction

```python
def extract_trials(data: Dict[str, Any]) -> List[TrialData]:
    """Extract trial data from parsed Bpod data.

    Process:
    1. Validate Bpod structure
    2. Extract nTrials count
    3. Extract TrialStartTimestamp and TrialEndTimestamp arrays
    4. Extract RawEvents.Trial data for each trial
    5. Extract States from each trial
    6. Infer outcome from visited states (non-NaN)
    7. Build TrialData objects

    Args:
        data: Parsed Bpod .mat data

    Returns:
        List of TrialData objects (1-indexed trial numbers)

    Raises:
        BpodParseError: If structure invalid or extraction fails

    Example:
        >>> trials = extract_trials(session_data)
        >>> print(f"Found {len(trials)} trials")
        >>> print(f"First trial start: {trials[0].start_time}")
        >>> print(f"First trial outcome: {trials[0].outcome}")
    """

def _is_state_visited(state_times: Any) -> bool:
    """Check if a state was visited (not NaN).

    Args:
        state_times: State timing array (e.g., [start, end])

    Returns:
        True if state was visited (start time is not NaN)
    """

def _infer_outcome(states: Dict[str, Any]) -> str:
    """Infer trial outcome from visited states.

    Checks for outcome states in priority order:
    1. HIT (if visited) → "hit"
    2. Miss (if visited) → "miss"
    3. CorrectReject (if visited) → "correct_rejection"
    4. FalseAlarm (if visited) → "false_alarm"
    5. Otherwise → "unknown"

    Args:
        states: Dictionary of state names to timing arrays

    Returns:
        Outcome string

    Note:
        Only considers states where start time is not NaN
    """
```

### Behavioral Event Extraction

```python
def extract_behavioral_events(data: Dict[str, Any]) -> List[BehavioralEvent]:
    """Extract behavioral events from parsed Bpod data.

    Process:
    1. Validate Bpod structure
    2. For each trial, extract Events dict from RawEvents.Trial
    3. For each event type, extract timestamp(s)
    4. Handle multiple timestamps per event (e.g., BNC1High: [1.5, 8.5])
    5. Filter out NaN timestamps
    6. Create BehavioralEvent for each valid timestamp

    Args:
        data: Parsed Bpod .mat data

    Returns:
        List of BehavioralEvent objects (flattened across all trials)

    Note:
        Returns empty list if structure invalid or no events found

    Example:
        >>> events = extract_behavioral_events(session_data)
        >>> print(f"Found {len(events)} events")
        >>> event_types = {e.event_type for e in events}
        >>> print(f"Event types: {event_types}")
    """
```

### Event Summary Creation

```python
def create_event_summary(
    session_id: str,
    trials: List[TrialData],
    events: List[BehavioralEvent],
    bpod_files: List[str]
) -> BpodSummary:
    """Create event summary for QC report.

    Args:
        session_id: Session identifier
        trials: List of TrialData objects
        events: List of BehavioralEvent objects
        bpod_files: List of Bpod file paths

    Returns:
        BpodSummary with trial counts, outcome counts, event categories

    Example:
        >>> summary = create_event_summary("Session-001", trials, events, ["/data/bpod.mat"])
        >>> print(f"Total trials: {summary.total_trials}")
        >>> print(f"Outcome counts: {summary.outcome_counts}")
        >>> print(f"Event categories: {summary.event_categories}")
    """

def write_event_summary(summary: BpodSummary, output_path: Path) -> None:
    """Write event summary to JSON file.

    Args:
        summary: BpodSummary instance
        output_path: Output JSON path

    Note:
        Uses utils.write_json() for JSON serialization
    """
```

## Bpod SessionData Structure

### Expected Structure

```python
{
    'SessionData': {
        'nTrials': 3,  # Total trial count
        'TrialStartTimestamp': [0.0, 10.0, 20.0],  # Array or list
        'TrialEndTimestamp': [9.0, 19.0, 29.0],
        'TrialTypes': [1, 2, 1],  # Optional
        'TrialSettings': [...],  # Optional metadata
        'RawEvents': {
            'Trial': [  # Array of trial structs
                {
                    'States': {
                        'ITI': [0.0, 7.0],  # [enter_time, exit_time]
                        'Response_window': [7.0, 8.5],
                        'HIT': [8.5, 8.6],
                        'Miss': [float('nan'), float('nan')],  # Not visited
                        'RightReward': [8.6, 9.0]
                    },
                    'Events': {
                        'Flex1Trig2': [0.0001, 7.1],  # Can have multiple timestamps
                        'BNC1High': [1.5, 8.5],
                        'BNC1Low': [1.6, 8.6],
                        'Tup': [7.0, 8.5, 8.6, 9.0]
                    }
                },
                # ... more trials
            ]
        }
    }
}
```

### Key Fields

- **nTrials:** Total trial count (required)
- **TrialStartTimestamp:** Array of trial start times in Bpod clock (seconds)
- **TrialEndTimestamp:** Array of trial end times
- **RawEvents.Trial:** Array of per-trial data
- **RawEvents.Trial[i].States:** Dict of state names to [enter, exit] times
  - NaN values indicate state was not visited
- **RawEvents.Trial[i].Events:** Dict of event names to timestamp arrays
  - Events can have multiple timestamps per trial

## Domain Models

### TrialData

```python
class TrialData(BaseModel):
    """Trial data extracted from Bpod."""
    model_config = {"frozen": True, "extra": "forbid"}

    trial_number: int  # 1-indexed
    start_time: float
    stop_time: float
    outcome: str  # "hit", "miss", "correct_rejection", "false_alarm", "unknown"
```

### BehavioralEvent

```python
class BehavioralEvent(BaseModel):
    """Behavioral event extracted from Bpod."""
    model_config = {"frozen": True, "extra": "forbid"}

    event_type: str  # e.g., "Flex1Trig2", "BNC1High", "Tup"
    timestamp: float
    trial_number: int  # 1-indexed
```

### BpodSummary

```python
class BpodSummary(BaseModel):
    """Bpod summary for QC report."""
    model_config = {"frozen": True, "extra": "forbid"}

    session_id: str
    total_trials: int
    outcome_counts: dict  # {"hit": 2, "miss": 1, ...}
    event_categories: List[str]  # Unique event types
    bpod_files: List[str]
    generated_at: str  # ISO 8601 timestamp
```

## Error Handling

```python
from w2t_bkin.events import EventsError, BpodParseError

# File not found
try:
    data = parse_bpod_mat(Path("missing.mat"))
except EventsError as e:
    print(f"Event error: {e}")

# Parse error
try:
    data = parse_bpod_mat(bpod_path)
    trials = extract_trials(data)
except BpodParseError as e:
    print(f"Parse error: {e}")
```

### Exception Types

**EventsError:**

- Base exception for events module
- Raised when file not found

**BpodParseError (extends EventsError):**

- Raised when scipy not installed
- Raised when .mat file cannot be parsed
- Raised when Bpod structure is invalid
- Raised when trial extraction fails

## Testing

**Test file:** `tests/unit/test_events.py`

**Coverage:**

- ✅ parse_bpod_mat() with valid .mat files
- ✅ parse_bpod_mat() with missing files
- ✅ validate_bpod_structure() with valid/invalid structures
- ✅ extract_trials() with outcome inference
- ✅ \_is_state_visited() NaN checking
- ✅ \_infer_outcome() priority logic
- ✅ extract_behavioral_events() with multiple timestamps
- ✅ extract_behavioral_events() NaN filtering
- ✅ create_event_summary() QC summary generation
- ✅ write_event_summary() JSON output

**Run tests:**

```bash
pytest tests/unit/test_events.py -v
```

## Usage Examples

### Complete workflow

```python
from w2t_bkin.events import (
    parse_bpod_mat,
    extract_trials,
    extract_behavioral_events,
    create_event_summary,
    write_event_summary
)
from pathlib import Path

# 1. Parse Bpod .mat file
bpod_path = Path("data/raw/session_001/Bpod_Session_001.mat")
session_data = parse_bpod_mat(bpod_path)

# 2. Extract trials with outcome inference
trials = extract_trials(session_data)

print(f"Found {len(trials)} trials")
for trial in trials[:3]:
    print(f"Trial {trial.trial_number}: {trial.outcome} "
          f"({trial.start_time:.2f}s - {trial.stop_time:.2f}s)")

# 3. Extract behavioral events
events = extract_behavioral_events(session_data)

print(f"Found {len(events)} behavioral events")
for event in events[:5]:
    print(f"{event.event_type} at {event.timestamp:.3f}s (trial {event.trial_number})")

# 4. Create QC summary
summary = create_event_summary(
    trials=trials,
    events=events,
    session_id="session_001",
    bpod_files=[str(bpod_path)]
)

print(f"Outcome counts: {summary.outcome_counts}")
print(f"Event categories: {summary.event_categories}")

# 5. Write summary to JSON
output_path = Path("data/interim/session_001_bpod_summary.json")
write_event_summary(summary, output_path)
```

### Handling NaN and missing states

```python
from w2t_bkin.events import parse_bpod_mat, _is_state_visited
import math

session_data = parse_bpod_mat(bpod_path)

# Check if state was visited (not NaN)
trial = session_data.RawEvents.Trial[0]
if _is_state_visited(trial.States.Hit):
    print("Hit state visited")
else:
    print("Hit state not visited (NaN)")

# Iterate through trials and check outcomes
from w2t_bkin.events import _infer_outcome

for i, trial in enumerate(session_data.RawEvents.Trial):
    outcome = _infer_outcome(trial.States)
    print(f"Trial {i+1}: {outcome}")
```

## Performance Notes

- **scipy.io.loadmat:** ~50-200ms per .mat file depending on size
- **NaN checking:** Adds ~5-10% overhead per trial (math.isnan calls)
- **Trial extraction:** ~1-10ms for 100 trials (dictionary operations)
- **Event extraction:** ~10-50ms for 100 trials with 10-20 events/trial
- **Summary generation:** <1ms (outcome counting + event categorization)

**Optimization tips:**

- scipy parsing with `squeeze_me=True` reduces memory overhead
- NaN checks are vectorizable but kept simple for clarity
- Event flattening is O(n\*m) where n=trials, m=avg events/trial

## Design Decisions

### Why scipy.io.loadmat?

- Standard library for MATLAB .mat file parsing in Python
- Handles complex nested structures from Bpod
- squeeze_me=True simplifies array handling
- struct_as_record=False enables attribute access (e.g., SessionData.nTrials)

### Why check for NaN instead of missing keys?

Bpod stores unvisited states as [NaN, NaN] rather than omitting them. This preserves the structure consistency across trials but requires explicit NaN checking with `math.isnan()`.

### Why prioritize outcomes (Hit > Miss > ...)?

Trials can visit multiple terminal states due to Bpod state machine complexity. Priority order reflects typical behavior task semantics where Hit indicates successful completion, Miss indicates attempt failure, etc. "unknown" is fallback.

### Why flatten events into single list?

NWB format expects behavioral events as a flat timeseries, not nested by trial. Flattening during extraction simplifies downstream NWB assembly. Trial association is preserved via trial_number field.

### Why separate summary creation from extraction?

Summary generation is QC-specific and shouldn't be coupled to core extraction logic. Separating allows for flexible summary formats and optional summary generation.

## Integration with Pipeline

### Phase 1 (Ingest)

```python
# events module is Phase 3 (optional), not called during ingest
# Bpod files are discovered and listed in manifest but not parsed
```

### Phase 3 (Events)

```python
# Parse Bpod files and extract behavioral data
from w2t_bkin.events import (
    parse_bpod_mat,
    extract_trials,
    extract_behavioral_events,
    create_event_summary,
    write_event_summary
)

for bpod_path in session.bpod_files:
    # Parse and extract
    session_data = parse_bpod_mat(bpod_path)
    trials = extract_trials(session_data)
    events = extract_behavioral_events(session_data)

    # Generate QC summary
    summary = create_event_summary(
        trials=trials,
        events=events,
        session_id=session.session_id,
        bpod_files=[str(bpod_path)]
    )
    write_event_summary(summary, output_path)
```

### Phase 4 (NWB)

```python
# nwb module reads trial/event data and writes to NWB
# Events data stored in NWB TimeIntervals (trials) and TimeSeries (events)
from w2t_bkin.nwb import write_trials_to_nwb, write_events_to_nwb

write_trials_to_nwb(nwbfile, trials)
write_events_to_nwb(nwbfile, events)
```

**Note:** Timebase synchronization (Phase 2) is not yet implemented. Current implementation extracts Bpod-relative timestamps. Future sync module will provide offset for alignment to video/TTL timebase.

## Bpod Protocol Compatibility

**Tested protocols:**

- ✅ Classical conditioning (Pavlovian)
- ✅ Operant conditioning (lever press, nose poke)
- ✅ Go/NoGo tasks
- ✅ Two-alternative forced choice (2AFC)

**Requirements for compatibility:**

- SessionData.nTrials must be present
- SessionData.TrialStartTimestamp must be present
- SessionData.RawEvents.Trial must be list with nTrials elements
- States should include at least one terminal state (Hit, Miss, CorrectReject, FalseAlarm)

**State naming conventions:**

Events module recognizes common Bpod state names for outcome inference:

- "Hit" → "hit"
- "Miss" → "miss"
- "CorrectReject" (or "CorrectReject") → "correct_rejection"
- "FalseAlarm" (or "FA") → "false_alarm"
- Other/none → "unknown"

## Related Modules

- **ingest:** Discovers Bpod .mat files and includes them in manifest
- **domain:** Defines TrialData, BehavioralEvent, BpodSummary models
- **nwb:** Writes trials and events to NWB file format
- **utils:** Provides write_json() for summary output

## Further Reading

- [Requirements: FR-11](../../requirements.md#functional-requirements) - Behavioral data extraction
- [Requirements: FR-14](../../requirements.md#functional-requirements) - Event categorization
- [Requirements: NFR-7](../../requirements.md#non-functional-requirements) - QC summary generation (A4)
- [Bpod Documentation](https://sanworks.io/shop/viewproduct?productID=1011) - Bpod hardware/software
- [scipy.io.loadmat](https://docs.scipy.org/doc/scipy/reference/generated/scipy.io.loadmat.html) - MATLAB file I/O
- [Pydantic v2 Models](https://docs.pydantic.dev/latest/) - Domain model validation
