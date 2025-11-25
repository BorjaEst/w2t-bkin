# TTL Events Module Implementation Plan (Phase 4.5)

## Status: PLANNED

## Overview

Create a new `events` module to standardize TTL signal integration into NWBFile using ndx-events EventsTable. This module will convert raw TTL pulse timestamps into structured NWB-compatible event tables for hardware synchronization signals.

**Important**: This is a NEW `events` module, distinct from the old deprecated `events` module (renamed to `bpod` in Phase 2). The old module handled Bpod file parsing; this new module handles TTL signal events.

## Background

### Current TTL Handling

TTL signals are currently loaded and used for synchronization but not integrated into NWB files as structured event data:

1. **Loading**: `sync/ttl.py` - `get_ttl_pulses()` loads TTL timestamps from text files
2. **Synchronization**: `sync/behavior.py` - `align_bpod_trials_to_ttl()` uses TTLs for trial alignment
3. **Timebase**: `sync/timebase.py` - `TTLProvider` uses TTL timestamps as reference timebase
4. **Current format**: TTL files contain one timestamp per line (floating-point seconds)

**Problem**: TTL data is used internally but not exported to NWB in a standardized format.

### NDX-Events Extension

The ndx-events extension provides:

- **EventsTable**: Base table for timestamped events (required `timestamp` column)
- **CategoricalVectorData**: Column type for categorical metadata
- **MeaningsTable**: Table for describing categorical values

**Benefits**:

- Standard NWB extension for hardware sync signals
- Queryable event data in NWB files
- Metadata support via custom columns
- Community-standard format for hardware events

## Architecture

### Module Location

```
src/w2t_bkin/events/
├── __init__.py          # Public API exports
├── core.py              # TTL → EventsTable conversion
└── models.py            # Re-export ndx-events types
```

### Layer Classification

**Low-Level Tool**: The events module operates on raw TTL timestamps (primitives) and produces NWB-native EventsTable objects. It follows the established NWB-first pattern.

```
Input:  Dict[str, List[float]]  # TTL pulses (from sync.ttl.get_ttl_pulses)
Output: EventsTable              # ndx-events table (NWB-native)
```

### Dependencies

- **Foundation**: ndx-events (already in pyproject.toml dependencies)
- **Internal**: None (operates on primitives only)
- **Used by**: High-level orchestration (pipeline.py)

## Implementation Tasks

### Task 1: Create Module Structure (15 minutes)

#### 1a. Create `src/w2t_bkin/events/__init__.py`

````python
"""TTL hardware events integration using ndx-events.

This module converts TTL pulse timestamps into NWB-compatible EventsTable
objects using the ndx-events extension.

IMPORTANT: This is a NEW events module (Phase 4.5) for TTL signal integration.
NOT to be confused with the old deprecated events module (renamed to bpod in Phase 2).

Public API:
-----------
from w2t_bkin.events import (
    # ndx-events types (re-exported)
    Events,
    EventsTable,
    TTLs,
    TTLsTable,
    # Core functions
    create_events_table_from_ttls,
    create_ttls_table_from_ttls,
    add_events_to_nwb,
)

Usage Example:
--------------
```python
from w2t_bkin.events import create_ttls_table_from_ttls
from w2t_bkin.sync import get_ttl_pulses

# Load TTL pulses
ttl_patterns = {"ttl_camera": "TTLs/cam*.txt", "ttl_cue": "TTLs/cue*.txt"}
ttl_pulses = get_ttl_pulses(ttl_patterns, session_dir)

# Create TTLsTable
ttls_table = create_ttls_table_from_ttls(
    ttl_pulses,
    descriptions={
        "ttl_camera": "Camera frame sync pulses (30 Hz)",
        "ttl_cue": "Behavioral cue trigger pulses"
    }
)

# Add to NWBFile
nwbfile.add_acquisition(ttls_table)
````

## Requirements:

- FR-17: Hardware sync signal recording
- Phase 4.5: TTL events standardization
  """

from .core import (
EventsError,
add_events_to_nwb,
create_events_table_from_ttls,
create_ttls_table_from_ttls,
)
from .models import Events, EventsTable, TTLs, TTLsTable

**all** = [
# ndx-events types
"Events",
"EventsTable",
"TTLs",
"TTLsTable",
# Core functions
"create_events_table_from_ttls",
"create_ttls_table_from_ttls",
"add_events_to_nwb",
# Exceptions
"EventsError",
]

````

#### 1b. Create `src/w2t_bkin/events/models.py`

```python
"""Re-export ndx-events types for TTL signal integration.

This module provides convenient access to ndx-events types used for
hardware synchronization signal recording.

Types:
------
- Events: Base event recording container
- EventsTable: Table for timestamped events with metadata
- TTLs: Hardware TTL signal container
- TTLsTable: Specialized table for TTL pulse events

Requirements:
-------------
- ndx-events~=0.4.0 (already in dependencies)
"""

from ndx_events import Events, EventsTable, TTLs, TTLsTable

__all__ = [
    "Events",
    "EventsTable",
    "TTLs",
    "TTLsTable",
]
````

### Task 2: Implement Core Functions (2-3 hours)

#### 2a. Create `src/w2t_bkin/events/core.py`

```python
"""Core functions for converting TTL pulses to ndx-events EventsTable objects.

Provides conversion from raw TTL timestamp dictionaries to structured NWB-compatible
event tables using the ndx-events extension.

Functions:
----------
- create_events_table_from_ttls: Generic EventsTable from TTL pulses
- create_ttls_table_from_ttls: Specialized TTLsTable from TTL pulses
- add_events_to_nwb: Helper to add EventsTable to NWBFile

Example:
--------
>>> from w2t_bkin.events import create_ttls_table_from_ttls
>>> from w2t_bkin.sync import get_ttl_pulses
>>>
>>> # Load TTL pulses
>>> ttl_patterns = {"ttl_camera": "TTLs/cam*.txt"}
>>> ttl_pulses = get_ttl_pulses(ttl_patterns, Path("data/session"))
>>>
>>> # Create TTLsTable
>>> ttls_table = create_ttls_table_from_ttls(
...     ttl_pulses,
...     descriptions={"ttl_camera": "Camera frame sync (30 Hz)"}
... )
>>>
>>> # Add to NWBFile
>>> nwbfile.add_acquisition(ttls_table)
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
from ndx_events import Events, EventsTable, TTLs, TTLsTable
from pynwb import NWBFile

logger = logging.getLogger(__name__)


class EventsError(Exception):
    """Exception raised for TTL events processing errors."""

    pass


def create_events_table_from_ttls(
    ttl_pulses: Dict[str, List[float]],
    name: str = "TTLEvents",
    descriptions: Optional[Dict[str, str]] = None,
) -> EventsTable:
    """Create generic EventsTable from TTL pulse timestamps.

    Converts a dictionary of TTL pulse timestamps into an ndx-events EventsTable
    with one row per pulse, labeled by TTL channel ID.

    Args:
        ttl_pulses: Dict mapping TTL ID to list of timestamps (seconds)
        name: Name for the EventsTable container
        descriptions: Optional dict mapping TTL ID to description string

    Returns:
        EventsTable with all TTL pulses as events

    Raises:
        EventsError: If ttl_pulses is empty or invalid

    Example:
        >>> ttl_pulses = {
        ...     "ttl_camera": [0.0, 0.033, 0.066],
        ...     "ttl_cue": [1.0, 3.0, 5.0]
        ... }
        >>> table = create_events_table_from_ttls(
        ...     ttl_pulses,
        ...     descriptions={"ttl_camera": "Camera sync", "ttl_cue": "Cue trigger"}
        ... )
        >>> len(table.timestamp)  # Total pulses across all channels
        6
    """
    if not ttl_pulses:
        raise EventsError("ttl_pulses dictionary is empty")

    descriptions = descriptions or {}

    # Collect all events across channels
    all_timestamps = []
    all_labels = []
    all_descriptions = []

    for ttl_id, timestamps in sorted(ttl_pulses.items()):
        if not timestamps:
            logger.warning(f"TTL channel '{ttl_id}' has no pulses, skipping")
            continue

        description = descriptions.get(ttl_id, f"TTL pulses from {ttl_id}")

        for timestamp in timestamps:
            all_timestamps.append(timestamp)
            all_labels.append(ttl_id)
            all_descriptions.append(description)

    if not all_timestamps:
        raise EventsError("No valid TTL pulses found in any channel")

    # Sort by timestamp
    sorted_indices = np.argsort(all_timestamps)
    sorted_timestamps = np.array(all_timestamps)[sorted_indices]
    sorted_labels = np.array(all_labels)[sorted_indices]
    sorted_descriptions = np.array(all_descriptions)[sorted_indices]

    # Create EventsTable
    events_table = EventsTable(
        name=name,
        description=f"Hardware TTL pulse events from {len(ttl_pulses)} channels",
    )

    # Add data
    for timestamp, label, description in zip(sorted_timestamps, sorted_labels, sorted_descriptions):
        events_table.add_row(
            timestamp=float(timestamp),
            label=str(label),
            description=str(description),
        )

    logger.info(
        f"Created EventsTable '{name}' with {len(all_timestamps)} events "
        f"from {len(ttl_pulses)} TTL channels"
    )

    return events_table


def create_ttls_table_from_ttls(
    ttl_pulses: Dict[str, List[float]],
    name: str = "TTLs",
    descriptions: Optional[Dict[str, str]] = None,
    sources: Optional[Dict[str, str]] = None,
) -> TTLsTable:
    """Create specialized TTLsTable from TTL pulse timestamps.

    Converts TTL pulse timestamps into an ndx-events TTLsTable, which is
    optimized for hardware TTL signals with channel-specific metadata.

    Args:
        ttl_pulses: Dict mapping TTL ID to list of timestamps (seconds)
        name: Name for the TTLsTable container
        descriptions: Optional dict mapping TTL ID to description
        sources: Optional dict mapping TTL ID to source device/system

    Returns:
        TTLsTable with all TTL pulses

    Raises:
        EventsError: If ttl_pulses is empty or invalid

    Example:
        >>> ttl_pulses = {"ttl_camera": [0.0, 0.033, 0.066]}
        >>> table = create_ttls_table_from_ttls(
        ...     ttl_pulses,
        ...     descriptions={"ttl_camera": "Camera frame sync at 30 Hz"},
        ...     sources={"ttl_camera": "FLIR Blackfly S"}
        ... )
    """
    if not ttl_pulses:
        raise EventsError("ttl_pulses dictionary is empty")

    descriptions = descriptions or {}
    sources = sources or {}

    # Collect all TTL events
    all_timestamps = []
    all_channels = []
    all_descriptions = []
    all_sources = []

    total_pulses = 0
    for ttl_id, timestamps in sorted(ttl_pulses.items()):
        if not timestamps:
            logger.warning(f"TTL channel '{ttl_id}' has no pulses, skipping")
            continue

        description = descriptions.get(ttl_id, f"TTL channel {ttl_id}")
        source = sources.get(ttl_id, "unknown")

        for timestamp in timestamps:
            all_timestamps.append(timestamp)
            all_channels.append(ttl_id)
            all_descriptions.append(description)
            all_sources.append(source)

        total_pulses += len(timestamps)
        logger.debug(f"Added {len(timestamps)} pulses from TTL channel '{ttl_id}'")

    if not all_timestamps:
        raise EventsError("No valid TTL pulses found in any channel")

    # Sort by timestamp
    sorted_indices = np.argsort(all_timestamps)
    sorted_timestamps = np.array(all_timestamps)[sorted_indices]
    sorted_channels = np.array(all_channels)[sorted_indices]
    sorted_descriptions = np.array(all_descriptions)[sorted_indices]
    sorted_sources = np.array(all_sources)[sorted_indices]

    # Create TTLsTable
    ttls_table = TTLsTable(
        name=name,
        description=f"Hardware TTL pulse signals from {len(ttl_pulses)} channels, {total_pulses} total pulses",
    )

    # Add data rows
    for timestamp, channel, description, source in zip(
        sorted_timestamps, sorted_channels, sorted_descriptions, sorted_sources
    ):
        ttls_table.add_row(
            timestamp=float(timestamp),
            channel=str(channel),
            description=str(description),
            source=str(source),
        )

    logger.info(
        f"Created TTLsTable '{name}' with {total_pulses} pulses "
        f"from {len(ttl_pulses)} channels"
    )

    return ttls_table


def add_events_to_nwb(
    nwbfile: NWBFile,
    ttl_pulses: Dict[str, List[float]],
    use_ttls_table: bool = True,
    descriptions: Optional[Dict[str, str]] = None,
    sources: Optional[Dict[str, str]] = None,
    container_name: str = "TTLs",
) -> NWBFile:
    """Add TTL events to NWBFile as EventsTable or TTLsTable.

    Convenience function that creates an appropriate events table and adds it
    to the NWBFile acquisition section.

    Args:
        nwbfile: NWBFile to add events to
        ttl_pulses: Dict mapping TTL ID to timestamps
        use_ttls_table: If True, use TTLsTable; else use generic EventsTable
        descriptions: Optional channel descriptions
        sources: Optional source device/system names (TTLsTable only)
        container_name: Name for the events container

    Returns:
        Modified NWBFile with events added

    Example:
        >>> from pynwb import NWBFile
        >>> from w2t_bkin.events import add_events_to_nwb
        >>> from w2t_bkin.sync import get_ttl_pulses
        >>>
        >>> nwbfile = NWBFile(...)
        >>> ttl_pulses = get_ttl_pulses(ttl_patterns, session_dir)
        >>> nwbfile = add_events_to_nwb(nwbfile, ttl_pulses)
    """
    if use_ttls_table:
        events_table = create_ttls_table_from_ttls(
            ttl_pulses,
            name=container_name,
            descriptions=descriptions,
            sources=sources,
        )
    else:
        events_table = create_events_table_from_ttls(
            ttl_pulses,
            name=container_name,
            descriptions=descriptions,
        )

    nwbfile.add_acquisition(events_table)

    logger.info(f"Added {type(events_table).__name__} '{container_name}' to NWBFile acquisition")

    return nwbfile
```

### Task 3: Update Package Exports (5 minutes)

#### Update `src/w2t_bkin/__init__.py`

Add events module to main package exports:

```python
# Add to imports section
from . import events

# Add to __all__
__all__ = [
    # ... existing exports
    "events",
    # ... rest
]
```

### Task 4: Pipeline Integration (30 minutes)

#### Update `src/w2t_bkin/pipeline.py`

Add TTL events integration to pipeline Phase 0 or Phase 1:

```python
# After loading TTL pulses
from w2t_bkin.events import add_events_to_nwb

# Phase 0 or Phase 1: Add TTL events to NWBFile
if ttl_pulses:
    # Get descriptions from config if available
    ttl_descriptions = {}
    ttl_sources = {}

    if hasattr(config, 'ttls') and config.ttls:
        for ttl_config in config.ttls:
            if hasattr(ttl_config, 'description'):
                ttl_descriptions[ttl_config.id] = ttl_config.description
            if hasattr(ttl_config, 'source'):
                ttl_sources[ttl_config.id] = ttl_config.source

    # Add TTL events to NWB
    nwbfile = add_events_to_nwb(
        nwbfile,
        ttl_pulses,
        use_ttls_table=True,
        descriptions=ttl_descriptions,
        sources=ttl_sources,
    )

    logger.info(f"Added TTL events from {len(ttl_pulses)} channels to NWBFile")
```

### Task 5: Write Tests (2-3 hours)

#### Create `tests/unit/test_events.py` (new file, distinct from archived test_events.py)

**IMPORTANT**: The old `test_events.py` was archived in `tests/archived/unit/`. This is a NEW test file.

```python
"""Tests for events module (TTL events integration using ndx-events).

IMPORTANT: This tests the NEW events module (Phase 4.5) for TTL signal integration.
The old test_events.py (archived) tested the deprecated events module (now bpod).
"""

import pytest
import numpy as np
from pynwb import NWBFile
from datetime import datetime

from w2t_bkin.events import (
    EventsError,
    create_events_table_from_ttls,
    create_ttls_table_from_ttls,
    add_events_to_nwb,
    EventsTable,
    TTLsTable,
)


class TestCreateEventsTableFromTTLs:
    """Test generic EventsTable creation from TTL pulses."""

    def test_creates_events_table_with_single_channel(self):
        """Should create EventsTable from single TTL channel."""
        ttl_pulses = {"ttl_camera": [0.0, 0.033, 0.066, 0.099]}

        table = create_events_table_from_ttls(ttl_pulses)

        assert isinstance(table, EventsTable)
        assert len(table.timestamp) == 4
        assert np.allclose(table.timestamp[:], [0.0, 0.033, 0.066, 0.099])
        assert all(label == "ttl_camera" for label in table.label[:])

    def test_creates_events_table_with_multiple_channels(self):
        """Should merge and sort events from multiple channels."""
        ttl_pulses = {
            "ttl_camera": [0.0, 0.033, 0.066],
            "ttl_cue": [0.050, 0.100]
        }

        table = create_events_table_from_ttls(ttl_pulses)

        assert len(table.timestamp) == 5
        # Should be sorted by timestamp
        assert np.allclose(table.timestamp[:], [0.0, 0.033, 0.050, 0.066, 0.100])

        # Labels should match timestamps
        expected_labels = ["ttl_camera", "ttl_camera", "ttl_cue", "ttl_camera", "ttl_cue"]
        assert list(table.label[:]) == expected_labels

    def test_uses_custom_descriptions(self):
        """Should use provided descriptions for each channel."""
        ttl_pulses = {"ttl_camera": [0.0, 0.033]}
        descriptions = {"ttl_camera": "Camera frame sync at 30 Hz"}

        table = create_events_table_from_ttls(ttl_pulses, descriptions=descriptions)

        assert all(desc == "Camera frame sync at 30 Hz" for desc in table.description[:])

    def test_raises_on_empty_ttl_pulses(self):
        """Should raise EventsError when ttl_pulses is empty."""
        with pytest.raises(EventsError, match="empty"):
            create_events_table_from_ttls({})

    def test_raises_on_all_channels_empty(self):
        """Should raise EventsError when all channels have no pulses."""
        ttl_pulses = {"ttl_camera": [], "ttl_cue": []}

        with pytest.raises(EventsError, match="No valid TTL pulses"):
            create_events_table_from_ttls(ttl_pulses)

    def test_skips_empty_channels(self):
        """Should skip channels with no pulses and log warning."""
        ttl_pulses = {
            "ttl_camera": [0.0, 0.033],
            "ttl_empty": []
        }

        table = create_events_table_from_ttls(ttl_pulses)

        # Should only have events from ttl_camera
        assert len(table.timestamp) == 2
        assert all(label == "ttl_camera" for label in table.label[:])


class TestCreateTTLsTableFromTTLs:
    """Test specialized TTLsTable creation from TTL pulses."""

    def test_creates_ttls_table_with_metadata(self):
        """Should create TTLsTable with channel, description, and source."""
        ttl_pulses = {"ttl_camera": [0.0, 0.033]}
        descriptions = {"ttl_camera": "Camera sync"}
        sources = {"ttl_camera": "FLIR Blackfly S"}

        table = create_ttls_table_from_ttls(
            ttl_pulses,
            descriptions=descriptions,
            sources=sources
        )

        assert isinstance(table, TTLsTable)
        assert len(table.timestamp) == 2
        assert all(ch == "ttl_camera" for ch in table.channel[:])
        assert all(desc == "Camera sync" for desc in table.description[:])
        assert all(src == "FLIR Blackfly S" for src in table.source[:])

    def test_sorts_by_timestamp_across_channels(self):
        """Should sort all pulses by timestamp regardless of channel."""
        ttl_pulses = {
            "ttl_b": [0.100, 0.300],
            "ttl_a": [0.050, 0.200]
        }

        table = create_ttls_table_from_ttls(ttl_pulses)

        # Should be sorted: 0.050, 0.100, 0.200, 0.300
        assert np.allclose(table.timestamp[:], [0.050, 0.100, 0.200, 0.300])
        expected_channels = ["ttl_a", "ttl_b", "ttl_a", "ttl_b"]
        assert list(table.channel[:]) == expected_channels

    def test_uses_default_source_when_not_provided(self):
        """Should use 'unknown' as default source."""
        ttl_pulses = {"ttl_camera": [0.0]}

        table = create_ttls_table_from_ttls(ttl_pulses)

        assert table.source[0] == "unknown"


class TestAddEventsToNWB:
    """Test adding TTL events to NWBFile."""

    @pytest.fixture
    def minimal_nwbfile(self):
        """Create minimal NWBFile for testing."""
        return NWBFile(
            session_description="Test session",
            identifier="test-001",
            session_start_time=datetime.now(),
        )

    def test_adds_ttls_table_to_nwbfile(self, minimal_nwbfile):
        """Should add TTLsTable to NWBFile acquisition."""
        ttl_pulses = {"ttl_camera": [0.0, 0.033, 0.066]}

        nwbfile = add_events_to_nwb(minimal_nwbfile, ttl_pulses, use_ttls_table=True)

        assert "TTLs" in nwbfile.acquisition
        assert isinstance(nwbfile.acquisition["TTLs"], TTLsTable)
        assert len(nwbfile.acquisition["TTLs"].timestamp) == 3

    def test_adds_events_table_to_nwbfile(self, minimal_nwbfile):
        """Should add generic EventsTable when requested."""
        ttl_pulses = {"ttl_camera": [0.0, 0.033]}

        nwbfile = add_events_to_nwb(minimal_nwbfile, ttl_pulses, use_ttls_table=False)

        assert "TTLs" in nwbfile.acquisition
        assert isinstance(nwbfile.acquisition["TTLs"], EventsTable)

    def test_uses_custom_container_name(self, minimal_nwbfile):
        """Should use provided container name."""
        ttl_pulses = {"ttl_camera": [0.0]}

        nwbfile = add_events_to_nwb(
            minimal_nwbfile,
            ttl_pulses,
            container_name="HardwareEvents"
        )

        assert "HardwareEvents" in nwbfile.acquisition

    def test_passes_descriptions_and_sources(self, minimal_nwbfile):
        """Should pass through descriptions and sources to TTLsTable."""
        ttl_pulses = {"ttl_camera": [0.0]}
        descriptions = {"ttl_camera": "Test camera"}
        sources = {"ttl_camera": "Test source"}

        nwbfile = add_events_to_nwb(
            minimal_nwbfile,
            ttl_pulses,
            descriptions=descriptions,
            sources=sources,
        )

        table = nwbfile.acquisition["TTLs"]
        assert table.description[0] == "Test camera"
        assert table.source[0] == "Test source"


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_handles_large_number_of_pulses(self):
        """Should handle large pulse counts efficiently."""
        # Generate 10k pulses at 1kHz
        ttl_pulses = {"ttl_high_freq": list(np.arange(0, 10, 0.001))}

        table = create_ttls_table_from_ttls(ttl_pulses)

        assert len(table.timestamp) == 10000

    def test_handles_float_precision(self):
        """Should preserve timestamp precision."""
        ttl_pulses = {"ttl_test": [0.123456789, 1.987654321]}

        table = create_ttls_table_from_ttls(ttl_pulses)

        assert table.timestamp[0] == pytest.approx(0.123456789)
        assert table.timestamp[1] == pytest.approx(1.987654321)
```

### Task 6: Documentation Updates (1 hour)

#### 6a. Update `docs/architecture_status.md`

Add Phase 4.5 section:

```markdown
### Phase 4.5: TTL Events Module ✅ (COMPLETE)

**Target**: Create events module for TTL signal integration using ndx-events

**Status**: ✅ COMPLETE - TTL pulses now exported to NWB as structured events

**Tasks**:

- [x] Create events module structure (\_\_init\_\_.py, models.py, core.py)
- [x] Implement create_events_table_from_ttls() function
- [x] Implement create_ttls_table_from_ttls() function
- [x] Implement add_events_to_nwb() helper function
- [x] Update pipeline.py to add TTL events to NWBFile
- [x] Write comprehensive test suite (15 tests)
- [x] Update documentation

**Implementation**:

- **Module**: `src/w2t_bkin/events/` (NEW - distinct from old deprecated events)
- **Functions**: 3 core functions for TTL → EventsTable conversion
- **Integration**: ndx-events extension (TTLsTable, EventsTable)
- **Tests**: 15 tests covering creation, sorting, metadata, edge cases

**Benefits**:

- Standardized TTL signal storage in NWB files
- Queryable event data with timestamps
- Channel-specific metadata (description, source)
- Community-standard format (ndx-events extension)

**Completed**: 2025-11-25  
**Time Spent**: ~4 hours  
**Status**: Production-ready

**Next Phase**: Phase 5 (Testing & Documentation)
```

#### 6b. Update `docs/MIGRATION.md`

Add Phase 4.5 section:

````markdown
### Phase 4.5: TTL Events Module (NEW) ✅ (Completed 2025-11-25)

**IMPORTANT**: This is a NEW `events` module for TTL signal integration.
NOT the old deprecated `events` module (renamed to `bpod` in Phase 2).

**Added module:**

- `w2t_bkin.events` - TTL signal → ndx-events EventsTable conversion

**New functionality:**

```python
from w2t_bkin.events import add_events_to_nwb
from w2t_bkin.sync import get_ttl_pulses

# Load TTL pulses
ttl_pulses = get_ttl_pulses(ttl_patterns, session_dir)

# Add to NWBFile as structured events
nwbfile = add_events_to_nwb(nwbfile, ttl_pulses)

# TTL events now queryable in NWB file
ttls_table = nwbfile.acquisition["TTLs"]
print(f"Total TTL pulses: {len(ttls_table.timestamp)}")
```
````

**Benefits:**

- TTL signals now stored in standard NWB format
- Queryable event data with metadata
- Compatible with ndx-events extension

````

#### 6c. Update `docs/design.md`

Add events module to low-level tools table:

```markdown
| Module          | Key Input                                                 | Output / Contract                                       | FR/NFR Coverage        |
| --------------- | --------------------------------------------------------- | ------------------------------------------------------- | ---------------------- |
| events          | TTL pulse timestamps (Dict[str, List[float]])            | EventsTable, TTLsTable (ndx-events)                     | FR-17                  |
````

#### 6d. Update `README.md`

Add to package modules table:

```markdown
| events | TTL → ndx-events EventsTable | ✅ Complete |
```

### Task 7: Architecture Diagram Update (10 minutes)

Update `docs/architecture_diagram.mmd` to include events module in low-level layer:

```mermaid
events["events<br/>━━━━━<br/>TTL pulses → EventsTable<br/>(ndx-events integration)"]
```

Add data flow arrow:

```mermaid
events -->|"EventsTable,<br/>TTLsTable"| session_mod
```

## Breaking Changes

**None** - This is a new module with no breaking changes.

## Migration Path

**No migration required** - New functionality.

Users can optionally add TTL events to existing pipelines:

```python
# Optional: Add TTL events to NWBFile
from w2t_bkin.events import add_events_to_nwb

if ttl_pulses:
    nwbfile = add_events_to_nwb(nwbfile, ttl_pulses)
```

## Benefits

1. **Standardization**: TTL signals stored in community-standard format (ndx-events)
2. **Queryability**: Event data easily accessible in NWB files
3. **Metadata**: Rich metadata support (descriptions, sources, channels)
4. **Interoperability**: Compatible with NWB ecosystem tools
5. **Consistency**: Follows established NWB-first pattern

## Success Criteria

- ✅ Events module structure created
- ✅ Core conversion functions implemented
- ✅ Tests cover all functionality (15+ tests)
- ✅ Pipeline integration complete
- ✅ Documentation updated
- ✅ No breaking changes to existing code

## Estimated Effort

- **Total Time**: 6-8 hours
- **Lines Added**: ~400 (core: 200, tests: 200)
- **Tests**: 15 tests
- **Dependencies**: ndx-events (already in pyproject.toml)

## References

- ndx-events documentation: https://github.com/rly/ndx-events
- NWB best practices: https://www.nwb.org/
- Phase 1 (Pose) and Phase 2 (Behavior) patterns: Established NWB-first workflows
