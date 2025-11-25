# NWB-First Migration Implementation Plan

## Goal

Replace Manifest with NWBFile as the primary orchestration artifact after file discovery.

## Architecture Change

### Before (Manifest-centric)

```
Config + Session → discover_files() → Manifest
Manifest → populate_counts() → Manifest
Manifest → verify() → VerificationResult
Manifest + processing → assemble_nwb() → NWBFile → write()
```

### After (NWB-centric)

```
Config + Session → discover_files() → file_dict
file_dict + Session → create_nwbfile() → NWBFile (in memory)
NWBFile → populate_acquisition() → NWBFile (cameras added)
NWBFile → add_processing_module() → NWBFile (behavior/pose added)
NWBFile → validate_and_write() → NWBFile (on disk)
```

## Implementation Steps

### Step 1: Update Session Model for NWB Metadata ✅

**File**: `src/w2t_bkin/domain/session.py`

Add new models to support the rich NWB session.toml structure:

- `NWBRequired`: session_description, identifier, session_start_time
- `NWBMetadata`: experimenter (list), experiment_description, institution, lab, keywords, notes, protocol, etc.
- `NWBSubject`: subject_id, description, species, sex, age, genotype, strain, weight, date_of_birth
- `NWBDevice`: name, description, manufacturer, model_name
- `NWBProcessingModule`: name, description
- `LabMetadata`: Custom lab-specific fields (room, rig_id, training_stage, etc.)
- `GenerationInfo`: software_packages, creation_notes

Update `Session` model to include these new sections while maintaining backward compatibility with existing camera/TTL/bpod sections.

### Step 2: Create Early NWBFile Builder

**File**: `src/w2t_bkin/nwb.py` (refactored)

Create `create_nwbfile_from_session(session: Session) -> NWBFile`:

- Parse session.toml metadata into NWBFile constructor
- Create Subject from session.subject
- Create Devices from session.devices
- Create empty ProcessingModules from session.processing_modules
- Store lab_metadata in NWBFile.lab_meta_data (LabMetaData extension)
- Return in-memory NWBFile ready for population

### Step 3: Add File Discovery Metadata to NWBFile

**File**: `src/w2t_bkin/ingest.py` (refactored)

Change `discover_files()` to return Dict instead of Manifest:

- Return: `{"cameras": [...], "ttls": [...], "bpod": [...]}`
- Each entry contains: `{"id": str, "files": List[Path], "frame_count": Optional[int]}`

Create `add_acquisition_to_nwb(nwbfile: NWBFile, discovered_files: Dict) -> NWBFile`:

- For each camera: create ImageSeries with external_file links
- Store frame_count in nwbfile.scratch["file_discovery"]["cameras"][cam_id]["frame_count"]
- Store TTL info in nwbfile.scratch["file_discovery"]["ttls"]
- Return updated NWBFile

### Step 4: Update Processing Modules

**Files**: `src/w2t_bkin/sync/*.py`, `src/w2t_bkin/behavior/*.py`, `src/w2t_bkin/pose/*.py`

Update each module to accept and modify NWBFile:

- `sync.align_cameras(nwbfile: NWBFile, ...) -> NWBFile`
  - Read camera info from nwbfile.acquisition
  - Write AlignmentStats to nwbfile.processing["sync"]
- `behavior.add_task_recording(nwbfile: NWBFile, bpod_data: Dict) -> NWBFile`
  - Add TaskRecording to nwbfile.processing["behavior"]
- `pose.add_pose_estimation(nwbfile: NWBFile, pose_data: ...) -> NWBFile`
  - Add PoseEstimation to nwbfile.processing["behavior"]

### Step 5: Simplify NWB Write Operation

**File**: `src/w2t_bkin/nwb.py`

Create `write_nwb(nwbfile: NWBFile, output_path: Path, provenance: Dict) -> Path`:

- Add provenance to nwbfile.scratch["provenance"]
- Validate required fields (session_description, identifier, session_start_time)
- Write to HDF5 using NWBHDF5IO
- Return path to written file

### Step 6: Update Pipeline Orchestration

**File**: `src/w2t_bkin/pipeline.py`

Refactor `run_session()` to use NWB-first pattern:

```python
def run_session(config_path, session_id, options):
    # Load config
    config = load_config(config_path)
    session = load_session(session_path)

    # Create NWBFile early (with all metadata from session.toml)
    nwbfile = create_nwbfile_from_session(session)

    # Discover files
    discovered_files = discover_files(config, session)
    nwbfile = add_acquisition_to_nwb(nwbfile, discovered_files)

    # Optional: Verify frame/TTL counts
    verify_nwbfile(nwbfile, tolerance=config.verification.mismatch_tolerance)

    # Process behavioral data (if present)
    if bpod_files:
        bpod_data = parse_bpod(bpod_files)
        nwbfile = add_task_recording(nwbfile, bpod_data)

    # Process pose data (if present)
    if pose_files:
        pose_data = import_dlc_pose(pose_files)
        nwbfile = add_pose_estimation(nwbfile, pose_data)

    # Synchronization
    nwbfile = align_cameras(nwbfile, timebase_config)

    # Write NWB file
    provenance = build_provenance(config, session)
    nwb_path = write_nwb(nwbfile, output_dir, provenance)

    # Validate
    if not options.get("skip_validation"):
        validation_result = validate_nwb(nwb_path)

    return {"nwb_path": nwb_path, "validation": validation_result}
```

### Step 7: Remove Manifest Model

**Files to modify**:

- `src/w2t_bkin/domain/manifest.py` - DELETE
- `src/w2t_bkin/domain/__init__.py` - Remove Manifest imports
- `tests/**/test_*manifest*.py` - DELETE or UPDATE

**Files to update**:

- All imports of `Manifest`, `ManifestCamera`, `ManifestTTL` → replace with NWBFile operations
- All `verify_manifest()` calls → replace with `verify_nwbfile()`

### Step 8: Create NWB-Based Validation

**File**: `src/w2t_bkin/validate.py` (new)

```python
def verify_nwbfile(nwbfile: NWBFile, tolerance: int) -> VerificationResult:
    """Verify frame/TTL alignment using data stored in NWBFile."""
    file_discovery = nwbfile.scratch["file_discovery"]

    errors = []
    for cam_id, cam_info in file_discovery["cameras"].items():
        frame_count = cam_info["frame_count"]
        ttl_id = cam_info["ttl_id"]
        ttl_count = file_discovery["ttls"][ttl_id]["pulse_count"]

        if abs(frame_count - ttl_count) > tolerance:
            errors.append(f"{cam_id}: {frame_count} frames vs {ttl_count} TTL pulses")

    return VerificationResult(
        status="pass" if not errors else "fail",
        errors=errors
    )

def validate_nwb(nwb_path: Path) -> ValidationReport:
    """Validate NWB file using nwbinspector."""
    from nwbinspector import inspect_nwbfile

    results = list(inspect_nwbfile(nwb_path=nwb_path))
    return ValidationReport(
        path=nwb_path,
        issues=results,
        status="pass" if all(r.severity != "ERROR" for r in results) else "fail"
    )
```

## Migration Strategy

### Phase 1: Add NWB Metadata Support (Non-Breaking)

1. Add new Session models for NWB metadata
2. Update config parser to handle new structure
3. Keep Manifest model (deprecated but functional)
4. Add `create_nwbfile_from_session()` function

### Phase 2: Dual Mode (Transition)

1. Update `assemble_nwb()` to accept either Manifest or NWBFile
2. Add deprecation warnings for Manifest usage
3. Update examples to use NWBFile pattern

### Phase 3: NWB-Only (Breaking Change)

1. Remove Manifest model completely
2. Remove `verify_manifest()` function
3. All validation operates on NWBFile
4. Update all tests

## Benefits

1. **Standards Compliance**: NWB-first from discovery onwards
2. **Code Simplification**: Single validation path (no Manifest + NWB)
3. **Better UX**: Users work with standard NWB objects throughout
4. **Reduced Duplication**: One metadata source (session.toml → NWBFile)
5. **Improved Validation**: nwbinspector integration from the start

## Risks

1. **Breaking Changes**: Existing code using Manifest will break
2. **Memory Usage**: Keeping NWBFile in memory vs incremental Manifest
3. **Learning Curve**: Users must understand NWB structure

## Mitigation

1. **Deprecation Period**: Support both Manifest and NWBFile for 1 release
2. **Memory Management**: Provide streaming write option if needed
3. **Documentation**: Comprehensive migration guide with examples
