# NWB-First Migration: Progress Report

## Date: 2024-11-24

## Status: Phase 1 Complete ✅

### What Has Been Implemented

#### 1. Session Models (NWB-Compliant) ✅

**File**: `src/w2t_bkin/domain/session.py`

Added comprehensive NWB-compliant models:

- `NWBRequired`: session_description, identifier, session_start_time
- `NWBMetadata`: experimenter, keywords, experiment_description, institution, lab, etc.
- `NWBSubject`: subject_id, species, sex, age, genotype, strain, weight, date_of_birth
- `NWBDevice`: name, description, manufacturer, model_name
- `NWBProcessingModule`: name, description
- `LabMetadata`: Custom lab fields (room, rig_id, training_stage, etc.)
- `GenerationInfo`: software_packages, creation_notes

Updated `Session` model to support both:

- **New NWB-compliant format**: Uses `required`, `metadata`, `subject`, `devices`, etc.
- **Legacy format**: Maintains backward compatibility with existing `session`, `bpod`, `TTLs`, `cameras`

#### 2. Session Module (NWBFile Creation) ✅

**File**: `src/w2t_bkin/session.py`

Implemented complete session-to-NWB workflow:

- `load_session_metadata()`: Load session.toml files
- `create_nwb_file()`: Convert metadata to pynwb.NWBFile
- `create_subject()`: Build pynwb.file.Subject objects
- `create_devices()`: Build Device objects
- `get_nwb_metadata_summary()`: Extract metadata summary
- `_parse_datetime()`: ISO 8601 datetime parsing

**Features**:

- Supports both dict and file path input
- Handles optional/required fields gracefully
- ISO 8601 datetime parsing
- Device metadata aggregation
- Backward compatible with legacy session format

#### 3. Example Script ✅

**File**: `examples/create_nwb_from_session.py`

Working example that demonstrates:

- Loading session.toml
- Creating NWBFile with full metadata
- Saving to disk
- Reading back for verification

**Verified working** with current `data/raw/Session-000001/session.toml`

#### 4. Session.toml Template ✅

**File**: `data/raw/Session-000001/session.toml`

Comprehensive NWB-compliant template with:

- Required fields (session_description, identifier, session_start_time)
- Optional metadata (experimenter, keywords, institution, etc.)
- Subject information (species, sex, age, genotype, etc.)
- Devices list (bpod, cameras)
- Processing modules (behavior, sync)
- Lab-specific metadata
- Generation info

### Current Architecture

```
session.toml (NWB-compliant)
    ↓
load_session_metadata()
    ↓
create_nwb_file()
    ↓
NWBFile (in memory, with full metadata)
    ↓
[Next: Add acquisition data]
    ↓
[Next: Add processing results]
    ↓
Write to disk
```

### Verification Results

✅ **Models load successfully**

```python
from w2t_bkin.domain import NWBRequired, NWBMetadata, NWBSubject, NWBDevice
# All imports work
```

✅ **NWBFile creation works**

```python
from w2t_bkin.session import create_nwb_file
nwbfile = create_nwb_file("data/raw/Session-000001/session.toml")
# Successfully creates NWBFile with:
# - Identifier: Session-000001
# - Subject: M001
# - Devices: 3 (bpod, camera_0, camera_1)
# - Keywords: ['behavior', 'pose tracking', ...]
```

✅ **Example script runs**

```bash
python examples/create_nwb_from_session.py
# Creates and saves NWB file successfully
```

### Next Steps (In Priority Order)

#### Step 3: Integrate NWBFile into Pipeline

**File**: `src/w2t_bkin/pipeline.py`

Current workflow:

```python
config + session → discover_files() → Manifest
Manifest → populate_counts() → Manifest
Manifest + processing → assemble_nwb() → NWBFile
```

Target workflow:

```python
session → create_nwb_file() → NWBFile (early)
config + session → discover_files() → file_dict
NWBFile + file_dict → add_acquisition() → NWBFile (with cameras)
NWBFile + processing → add_behavior/pose/facemap() → NWBFile (complete)
NWBFile → write_nwb() → disk
```

**Tasks**:

1. Modify `run_session()` to create NWBFile early
2. Store file discovery results in NWBFile.scratch["file_discovery"]
3. Pass NWBFile through processing pipeline
4. Write final NWBFile to disk

#### Step 4: Add File Discovery to NWBFile

**File**: `src/w2t_bkin/ingest.py`

**Tasks**:

1. Create `add_acquisition_to_nwb(nwbfile, discovered_files)` function
2. For each camera: create ImageSeries with external_file links
3. Store frame/TTL counts in nwbfile.scratch["file_discovery"]
4. Store verification results in scratch

**Data structure**:

```python
nwbfile.scratch["file_discovery"] = {
    "cameras": {
        "cam0": {
            "files": ["/path/to/video1.avi", ...],
            "frame_count": 10000,
            "ttl_id": "ttl0",
            "order": "name_asc"
        }
    },
    "ttls": {
        "ttl0": {
            "files": ["/path/to/ttl.txt"],
            "pulse_count": 10002
        }
    },
    "bpod": {
        "files": ["/path/to/bpod.mat"],
        "order": "name_asc"
    }
}
```

#### Step 5: Update Processing Modules

**Files**: Various processing modules

Update each module to accept/modify NWBFile:

- `sync/*`: Read from acquisition, write alignment stats to processing["sync"]
- `behavior/*`: Add TaskRecording to processing["behavior"]
- `pose/*`: Add PoseEstimation to processing["behavior"]
- `facemap/*`: Add TimeSeries to processing["behavior"]

**Pattern**:

```python
def add_task_recording(nwbfile: NWBFile, bpod_data: Dict) -> NWBFile:
    """Add TaskRecording to NWBFile processing module."""
    # Create behavior processing module if not exists
    if "behavior" not in nwbfile.processing:
        nwbfile.create_processing_module("behavior", "Behavioral data")

    # Build TaskRecording
    task_recording = build_task_recording(bpod_data)

    # Add to processing module
    nwbfile.processing["behavior"].add(task_recording)

    return nwbfile
```

#### Step 6: Remove Manifest Model

**Files**: Multiple

**Tasks**:

1. Delete `src/w2t_bkin/domain/manifest.py`
2. Remove Manifest imports from `domain/__init__.py`
3. Delete `verify_manifest()` from `ingest.py`
4. Create `verify_nwbfile()` as replacement
5. Update all tests to use NWBFile pattern
6. Update documentation

### Benefits Achieved So Far

1. ✅ **NWB-First from Start**: Session metadata → NWBFile directly
2. ✅ **Standards Compliance**: Using pynwb.file.NWBFile specification
3. ✅ **Comprehensive Metadata**: All NWB recommended fields supported
4. ✅ **Backward Compatible**: Legacy session format still works
5. ✅ **Working Example**: Verified end-to-end workflow

### Remaining Work

- **Pipeline Integration**: Wire NWBFile through pipeline stages
- **Acquisition Data**: Add ImageSeries for cameras
- **Processing Data**: Update modules to add to NWBFile
- **Validation**: Create NWB-based verification
- **Cleanup**: Remove Manifest model and old code
- **Testing**: Update test suite for NWB-first pattern

### Timeline Estimate

- Step 3 (Pipeline Integration): ~2-3 hours
- Step 4 (File Discovery): ~2 hours
- Step 5 (Processing Modules): ~4-6 hours
- Step 6 (Cleanup & Tests): ~3-4 hours

**Total remaining**: ~11-15 hours of development work

### Migration Strategy

Using **phased approach** for safety:

1. **Phase 1** (COMPLETE): Add NWB models and session module
2. **Phase 2** (NEXT): Dual mode - support both Manifest and NWBFile
3. **Phase 3**: NWB-only - remove Manifest completely

This allows gradual migration with validation at each step.
