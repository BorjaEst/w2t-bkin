---
post_title: "Tasks — Neuropixels Ecephys Integration"
author1: "Project Team"
post_slug: "tasks-ecephys"
microsoft_alias: "na"
featured_image: "/assets/og.png"
categories: ["docs", "ecephys", "tasks"]
tags: ["implementation", "neuropixels", "tracking"]
ai_note: "Implementation plan with task tracking."
summary: "Detailed implementation tasks for integrating Neuropixels extracellular electrophysiology data into the w2t-bkin pipeline."
post_date: "2025-12-05"
---

# Tasks — Neuropixels Ecephys Integration

## Overview

This document tracks the implementation of Neuropixels ecephys integration following the phased approach defined in `design.md`. Each phase builds upon the previous, with clear deliverables and acceptance criteria.

## Implementation Phases

### Phase 1: Foundation (Metadata & Electrodes)

**Goal**: Define probes and electrodes in NWB before adding data.

**Priority**: 🔴 High (Required foundation for all subsequent phases)

#### Task 1.1: Configuration Schema

**Status**: ⬜ Not Started

**Description**: Extend configuration templates with ecephys sections.

**Subtasks**:

- [ ] Add `[ecephys]` section to `templates/configuration.toml`
  - `enabled`, `probes`, `storage`, `quality` subsections
  - Documentation comments for each option
- [ ] Add Neuropixels device examples to `templates/full-metadata.toml`
  - Device definitions for imec0, imec1
  - TTL channel mappings for TPrime-corrected signals
- [ ] Update `docs/configuration-parameters.md` with ecephys options
- [ ] Add validation rules to `src/w2t_bkin/config.py` for ecephys config

**Deliverable**: Users can configure ecephys processing via TOML files.

**Acceptance Criteria**:

- [ ] `configuration.toml` validates with ecephys section
- [ ] `metadata.toml` validates with neuropixels devices
- [ ] Config loading succeeds with ecephys enabled/disabled

**Estimated Effort**: Small (2-4 hours)

---

#### Task 1.2: Parser Utilities

**Status**: ⬜ Not Started

**Description**: Implement SpikeGLX .meta file parser.

**Subtasks**:

- [ ] Create `src/w2t_bkin/ingest/ecephys/parsers.py`
- [ ] Implement `parse_spikeglx_meta(meta_path: Path) -> Dict[str, Any]`
  - Extract `imSampRate` (sampling rate)
  - Extract `nSavedChans` (channel count)
  - Extract `imDatPrb_type` (probe type)
  - Parse `~snsGeomMap` for electrode coordinates (optional)
- [ ] Add LRU caching decorator for repeated parsing
- [ ] Write unit tests with fixture `.meta` files
  - Test NP1.0 format
  - Test NP2.0 format
  - Test error handling (missing fields, malformed file)

**Deliverable**: Reliable .meta file parsing with test coverage.

**Acceptance Criteria**:

- [ ] Parser correctly extracts sampling rate, channel count, probe type
- [ ] Parser handles missing optional fields gracefully
- [ ] Unit tests achieve 100% coverage
- [ ] Parser caches results to avoid re-parsing

**Estimated Effort**: Small (3-5 hours)

---

#### Task 1.3: Device Creation Module

**Status**: ⬜ Not Started

**Description**: Implement Device object creation for Neuropixels probes.

**Subtasks**:

- [ ] Create `src/w2t_bkin/ingest/ecephys/__init__.py`
- [ ] Create `src/w2t_bkin/ingest/ecephys/device.py`
- [ ] Implement `create_neuropixels_device()`
  - Accept primitives: `device_name`, `manufacturer`, `model_name`, `description`
  - Create `pynwb.device.Device` object
  - Add to `nwbfile.devices`
  - Handle duplicate device name error
- [ ] Write unit tests
  - Test device creation with valid parameters
  - Test duplicate name error
  - Test device attributes match inputs
- [ ] Export function in `__init__.py`

**Deliverable**: Working device creation function with test coverage.

**Acceptance Criteria**:

- [ ] Function creates Device with correct attributes
- [ ] Device added to NWBFile.devices
- [ ] Duplicate names raise ValueError
- [ ] Unit tests pass

**Estimated Effort**: Small (2-3 hours)

---

#### Task 1.4: Electrodes Table Population

**Status**: ⬜ Not Started

**Description**: Implement electrodes table population from .meta file.

**Subtasks**:

- [ ] Implement `add_electrodes_from_meta()` in `device.py`
  - Parse .meta file using `parse_spikeglx_meta()`
  - Create ElectrodeGroup for this probe
  - Loop over channels, add to `nwbfile.electrodes`
    - Generate unique IDs (handle multi-probe case)
    - Set location, filtering, impedance, coordinates
- [ ] Handle multi-probe electrode ID uniqueness
  - Use offset based on existing electrode count
- [ ] Write unit tests
  - Test single probe (384 channels)
  - Test multi-probe (electrode ID uniqueness)
  - Test electrode attributes match .meta
  - Test ElectrodeGroup linkage
- [ ] Write integration test with full NWBFile

**Deliverable**: Electrodes table populated from .meta file.

**Acceptance Criteria**:

- [ ] Electrodes table has correct number of rows
- [ ] Electrode IDs are unique across probes
- [ ] ElectrodeGroup correctly references Device
- [ ] Location, filtering, coordinates populated
- [ ] Unit and integration tests pass

**Estimated Effort**: Medium (4-6 hours)

---

#### Task 1.5: Phase 1 Integration Test

**Status**: ⬜ Not Started

**Description**: End-to-end test of device and electrode creation.

**Subtasks**:

- [ ] Create fixture session in `tests/fixtures/ecephys/`
  - Sample `.meta` file (NP2.0, 384 channels)
  - Sample `metadata.toml` with neuropixels devices
  - Sample `configuration.toml` with ecephys enabled
- [ ] Write integration test
  - Load config, create NWBFile
  - Call `create_neuropixels_device()`
  - Call `add_electrodes_from_meta()`
  - Write NWB file, read back
  - Verify devices and electrodes present
- [ ] Test with `nwbinspector` (no critical errors)

**Deliverable**: Verified Phase 1 functionality with fixture data.

**Acceptance Criteria**:

- [ ] Integration test creates valid NWB file
- [ ] NWB contains Device and electrodes
- [ ] `nwbinspector` validates successfully
- [ ] Test runs in CI pipeline

**Estimated Effort**: Medium (3-4 hours)

---

### Phase 2: Spike Data (Units Table)

**Goal**: Ingest Kilosort output into NWB Units table.

**Priority**: 🟡 Medium (Core scientific data)

#### Task 2.1: Kilosort File Loaders

**Status**: ⬜ Not Started

**Description**: Implement utilities to load Kilosort .npy and .tsv files.

**Subtasks**:

- [ ] Add `load_kilosort_data()` to `parsers.py`
  - Load `spike_times.npy`, `spike_clusters.npy`
  - Load `templates.npy` (optional)
  - Return dict with numpy arrays
- [ ] Add `load_cluster_labels()` to `parsers.py`
  - Try `cluster_info.tsv` first (newer Kilosort)
  - Fallback to `cluster_KSLabel.tsv` (older versions)
  - Return pandas DataFrame with `cluster_id`, `KSLabel`
- [ ] Add `load_cluster_metrics()` to `parsers.py`
  - Load `cluster_ContamPct.tsv`, `cluster_Amplitude.tsv`
  - Return pandas DataFrame with metrics
- [ ] Write unit tests with fixture files
  - Test successful loading
  - Test missing file handling
  - Test malformed file handling

**Deliverable**: Reliable Kilosort data loading utilities.

**Acceptance Criteria**:

- [ ] Functions load data correctly
- [ ] Missing optional files handled gracefully
- [ ] Unit tests achieve 100% coverage

**Estimated Effort**: Medium (4-5 hours)

---

#### Task 2.2: Spike Sorting Ingestion Module

**Status**: ⬜ Not Started

**Description**: Implement Units table population from Kilosort output.

**Subtasks**:

- [ ] Create `src/w2t_bkin/ingest/ecephys/sorting.py`
- [ ] Implement `add_spike_sorting()`
  - Load spike data using `load_kilosort_data()`
  - Load cluster labels using `load_cluster_labels()`
  - Filter by `include_labels` (e.g., ["good", "mua"])
  - Count spikes per cluster, filter by `min_spike_count`
  - Convert spike times: samples → seconds (using sampling rate)
  - Map cluster → electrode (from `cluster_info.tsv` → `ch` column)
  - Add units to `nwbfile.units` with spike times
  - Optionally add waveforms from `templates.npy`
  - Optionally add quality metrics as custom columns
  - Return summary statistics dict
- [ ] Handle edge cases
  - Non-contiguous cluster IDs (gaps from curation)
  - Missing electrode mapping (warn, use probe-wide region)
  - Empty spike trains after filtering (warn, skip unit)
- [ ] Write unit tests
  - Test quality filtering
  - Test spike count filtering
  - Test time conversion accuracy
  - Test waveform inclusion
  - Test quality metrics inclusion
- [ ] Export function in `__init__.py`

**Deliverable**: Working spike sorting ingestion with filtering and metrics.

**Acceptance Criteria**:

- [ ] Units table populated with correct spike times
- [ ] Quality filtering works as expected
- [ ] Spike times in seconds (not samples)
- [ ] Summary statistics accurate
- [ ] Unit tests pass

**Estimated Effort**: Large (6-8 hours)

---

#### Task 2.3: Phase 2 Integration Test

**Status**: ⬜ Not Started

**Description**: End-to-end test of spike sorting ingestion.

**Subtasks**:

- [ ] Extend fixture session with Kilosort output
  - `spike_times.npy`, `spike_clusters.npy` (100 units, 10k spikes)
  - `cluster_info.tsv`, `cluster_KSLabel.tsv` (quality labels)
  - `templates.npy` (mean waveforms)
- [ ] Write integration test
  - Build on Phase 1 test (devices + electrodes)
  - Call `add_spike_sorting()` with various filter options
  - Verify Units table contents
  - Test quality label filtering
  - Test spike count filtering
  - Test waveform inclusion
- [ ] Test with `nwbinspector` (no critical errors)

**Deliverable**: Verified Phase 2 functionality with fixture data.

**Acceptance Criteria**:

- [ ] Integration test creates valid NWB with Units
- [ ] Filtering works correctly
- [ ] Spike times accurate
- [ ] `nwbinspector` validates successfully

**Estimated Effort**: Medium (3-4 hours)

---

### Phase 3: Raw Data (External Links)

**Goal**: Link artifact-blanked AP data into NWB.

**Priority**: 🟢 Low (Nice-to-have for reproducibility)

#### Task 3.1: Raw Data Linking Module

**Status**: ⬜ Not Started

**Description**: Implement external link creation for AP band data.

**Subtasks**:

- [ ] Create `src/w2t_bkin/ingest/ecephys/raw_data.py`
- [ ] Implement `add_raw_data()`
  - Infer `.meta` path from `.bin` path
  - Parse sampling rate and channel count from `.meta`
  - Calculate data shape: `[n_samples, n_channels]`
  - Create electrode region (all electrodes for this probe)
  - Implement storage strategies:
    - `"link"`: Create `H5DataIO` with `h5py.ExternalLink` (relative path)
    - `"copy"`: Memory-map `.bin`, copy to NWB (warn about size)
    - `"skip"`: Return None, log message
  - Create `ElectricalSeries` with correct metadata
  - Add to `nwbfile.acquisition`
  - Return ElectricalSeries or None
- [ ] Write unit tests
  - Test external link creation (requires writing NWB to verify)
  - Test copy strategy (small fixture file)
  - Test skip strategy
  - Test relative path calculation
- [ ] Export function in `__init__.py`

**Deliverable**: Raw data linking with configurable strategies.

**Acceptance Criteria**:

- [ ] External link points to correct file
- [ ] Relative path used (portability)
- [ ] ElectricalSeries has correct sampling rate, units
- [ ] Data accessible after writing/reading NWB
- [ ] Unit tests pass

**Estimated Effort**: Medium (5-6 hours)

---

#### Task 3.2: Phase 3 Integration Test

**Status**: ⬜ Not Started

**Description**: End-to-end test of raw data linking.

**Subtasks**:

- [ ] Extend fixture session with AP bin file
  - Small synthetic `.bin` file (1 second, 384 channels)
  - Corresponding `.meta` file
- [ ] Write integration test
  - Build on Phase 2 test (devices + electrodes + units)
  - Call `add_raw_data()` with `storage_strategy="link"`
  - Write NWB file
  - Read back NWB file
  - Verify external link exists
  - Access data (first 100 samples) to verify readability
- [ ] Test with `nwbinspector` (no critical errors)

**Deliverable**: Verified Phase 3 functionality with external links.

**Acceptance Criteria**:

- [ ] Integration test creates valid NWB with external link
- [ ] Link readable after NWB file relocation (relative path)
- [ ] Data accessible via NWB API
- [ ] `nwbinspector` validates successfully

**Estimated Effort**: Medium (3-4 hours)

---

### Phase 4: High-Level Orchestration

**Goal**: Wire ecephys into the session pipeline.

**Priority**: 🟣 Critical (Integration with existing pipeline)

#### Task 4.1: Session Module Extension

**Status**: ⬜ Not Started

**Description**: Add ecephys orchestration to `core.session`.

**Subtasks**:

- [ ] Add `add_ecephys_data()` method to `src/w2t_bkin/core/session.py`
  - Accept NWBFile, config, discovered probe data
  - For each probe:
    - Get device metadata from session metadata
    - Call `create_neuropixels_device()`
    - Call `add_electrodes_from_meta()`
    - Call `add_spike_sorting()`
    - Call `add_raw_data()` (if enabled)
  - Log summary statistics
  - Handle errors gracefully (partial state recovery)
- [ ] Add discovery helpers (or inline in pipeline)
  - `discover_ecephys_data(session_path, config) -> Dict[str, ProbeData]`
  - Find `.meta` files in `interim/neural/catgt/`
  - Find Kilosort dirs in `interim/neural/kilosort/{probe_id}/`
  - Find AP bin files in `interim/neural/tprime/`
  - Verify required files exist
- [ ] Update docstrings and type hints

**Deliverable**: Session module can orchestrate ecephys ingestion.

**Acceptance Criteria**:

- [ ] `add_ecephys_data()` successfully adds all ecephys data
- [ ] Discovery finds correct files
- [ ] Verification catches missing files
- [ ] Errors logged with actionable messages

**Estimated Effort**: Medium (4-5 hours)

---

#### Task 4.2: Pipeline Integration

**Status**: ⬜ Not Started

**Description**: Add Phase 2.5 (Ecephys Ingestion) to pipeline.

**Subtasks**:

- [ ] Update `src/w2t_bkin/core/pipeline.py`
  - Add Phase 2.5 after Bpod ingestion (Phase 2)
  - Check if `config.ecephys.enabled`
  - Call discovery helpers
  - Call `session.add_ecephys_data()`
  - Log phase summary
- [ ] Add ecephys statistics to session summary
  - Number of probes processed
  - Electrodes per probe
  - Units per probe
  - Total spikes per probe
- [ ] Update phase numbering in logs (existing phases shift)
- [ ] Handle optional ecephys (skip if disabled or missing)

**Deliverable**: Pipeline executes ecephys ingestion in correct order.

**Acceptance Criteria**:

- [ ] Pipeline runs successfully with ecephys enabled
- [ ] Pipeline skips ecephys when disabled
- [ ] Phase logging clear and informative
- [ ] Session summary includes ecephys stats

**Estimated Effort**: Small (2-3 hours)

---

#### Task 4.3: End-to-End Pipeline Test

**Status**: ⬜ Not Started

**Description**: Full pipeline test with ecephys + behavior + pose.

**Subtasks**:

- [ ] Create complete fixture session in `tests/fixtures/ecephys_session/`
  - Bpod `.mat` files
  - Camera videos + TTL files
  - Pose H5 files
  - Neuropixels data (interim structure)
  - `metadata.toml`, `configuration.toml`
- [ ] Write integration test `test_ecephys_full_pipeline()`
  - Run `pipeline.run_session()`
  - Verify NWB contains:
    - Bpod trials
    - Camera acquisition
    - Pose data
    - Neuropixels devices, electrodes, units
  - Verify all modalities present
  - Verify synchronization (if Neuropixels as master)
- [ ] Test with `nwbinspector` (no critical errors)
- [ ] Performance benchmark (should complete in < 5 minutes)

**Deliverable**: Verified end-to-end pipeline with all modalities.

**Acceptance Criteria**:

- [ ] Pipeline creates valid multi-modality NWB file
- [ ] All modalities present and correct
- [ ] `nwbinspector` validates successfully
- [ ] Performance acceptable

**Estimated Effort**: Large (6-8 hours)

---

### Phase 5: Synchronization Integration

**Goal**: Use Neuropixels NIDQ as master timebase.

**Priority**: 🔵 Future (Depends on sync module design)

#### Task 5.1: Neuropixels Timebase Provider

**Status**: ⬜ Not Started (Blocked: awaiting sync module refactor)

**Description**: Implement Neuropixels timebase provider in `sync` module.

**Subtasks**:

- [ ] Add `NeuropixelsTimebaseProvider` to `src/w2t_bkin/sync/timebase.py`
  - Accept `.meta` path, extract sampling rate
  - Implement `get_reference_timestamps()` (no-op, Neuropixels IS reference)
  - Implement `align_to_reference()` using TPrime-corrected TTLs
- [ ] Update `sync` module to support `"neuropixels"` strategy
- [ ] Load TPrime-corrected TTL files
  - Map TTL file names to channel IDs (from config)
  - Parse timestamp files (text format: one timestamp per line)
- [ ] Write unit tests for timebase provider
- [ ] Write integration test for alignment

**Deliverable**: Sync module supports Neuropixels as master clock.

**Acceptance Criteria**:

- [ ] Timebase provider correctly loads TPrime timestamps
- [ ] Alignment maps camera/Bpod times to Neuropixels time
- [ ] Unit and integration tests pass

**Estimated Effort**: Large (8-10 hours)

---

#### Task 5.2: Configuration Extension for Sync

**Status**: ⬜ Not Started

**Description**: Add Neuropixels sync options to configuration.

**Subtasks**:

- [ ] Update `templates/configuration.toml`
  - Add `synchronization.reference_channel = "neuropixels"` option
  - Add TTL channel mapping (NIDQ channels → TTL IDs)
- [ ] Update `src/w2t_bkin/config.py` validation
- [ ] Document in `docs/configuration-parameters.md`

**Deliverable**: Users can configure Neuropixels as master clock.

**Acceptance Criteria**:

- [ ] Config validates with Neuropixels sync
- [ ] Documentation clear and complete

**Estimated Effort**: Small (2-3 hours)

---

#### Task 5.3: Pipeline Sync Integration Test

**Status**: ⬜ Not Started

**Description**: Test full pipeline with Neuropixels as master clock.

**Subtasks**:

- [ ] Extend fixture session with TPrime-corrected TTL files
- [ ] Write integration test
  - Enable Neuropixels sync in config
  - Run pipeline
  - Verify camera timestamps aligned to Neuropixels
  - Verify Bpod trial times aligned to Neuropixels
  - Check alignment statistics (jitter, drift)
- [ ] Test with `nwbinspector`

**Deliverable**: Verified synchronization with Neuropixels as master.

**Acceptance Criteria**:

- [ ] All modalities synchronized correctly
- [ ] Alignment statistics within tolerances
- [ ] `nwbinspector` validates successfully

**Estimated Effort**: Medium (4-5 hours)

---

### Phase 6: Documentation & Polish

**Goal**: Complete documentation and user-facing materials.

**Priority**: 🟢 Low (After core functionality complete)

#### Task 6.1: User Documentation

**Status**: ⬜ Not Started

**Description**: Write user-facing documentation for ecephys integration.

**Subtasks**:

- [ ] Create `docs/ecephys/user-guide.md`
  - Overview of ecephys integration
  - Prerequisites (CatGT, TPrime, Kilosort)
  - Data organization (interim structure)
  - Configuration options explained
  - Common troubleshooting
- [ ] Update `README.md` with ecephys support
- [ ] Add example session in `examples/ecephys_session/`
- [ ] Add tutorial notebook `notebooks/ecephys_tutorial.ipynb`

**Deliverable**: Complete user documentation.

**Acceptance Criteria**:

- [ ] Documentation covers all user-facing features
- [ ] Examples work out-of-the-box
- [ ] Tutorial notebook runs successfully

**Estimated Effort**: Medium (5-6 hours)

---

#### Task 6.2: Migration Guide

**Status**: ⬜ Not Started

**Description**: Document migration from `raw/` to `interim/` structure.

**Subtasks**:

- [ ] Write `docs/ecephys/migration-guide.md`
  - Detect data in `raw/neural/` (old structure)
  - Provide move commands for each subfolder
  - Explain what to keep in `raw/` vs move to `interim/`
- [ ] Add migration script `scripts/migrate_ecephys_data.py`
  - Automate folder moves
  - Verify data integrity after move
  - Dry-run mode for safety

**Deliverable**: Easy migration path for existing datasets.

**Acceptance Criteria**:

- [ ] Migration guide clear and tested
- [ ] Migration script works correctly
- [ ] Users can migrate existing data safely

**Estimated Effort**: Small (3-4 hours)

---

#### Task 6.3: Architecture Documentation Update

**Status**: ⬜ Not Started

**Description**: Update architecture diagrams and design docs.

**Subtasks**:

- [ ] Update `docs/architecture_diagram.mmd`
  - Add `ingest.ecephys` to Low-Level layer
  - Show dependencies and data flows
- [ ] Update `docs/design.md`
  - Add ecephys to module responsibilities table
  - Document low-level API contracts
  - Add to build order
- [ ] Update CHANGELOG with ecephys feature

**Deliverable**: Architecture documentation reflects ecephys integration.

**Acceptance Criteria**:

- [ ] Mermaid diagram renders correctly
- [ ] Design doc accurate
- [ ] CHANGELOG updated

**Estimated Effort**: Small (2-3 hours)

---

## Summary & Estimates

### Total Effort Breakdown

| Phase                     | Tasks        | Estimated Hours | Priority    |
| ------------------------- | ------------ | --------------- | ----------- |
| Phase 1: Foundation       | 5            | 14-22 hours     | 🔴 High     |
| Phase 2: Spike Data       | 3            | 13-17 hours     | 🟡 Medium   |
| Phase 3: Raw Data         | 2            | 8-10 hours      | 🟢 Low      |
| Phase 4: Orchestration    | 3            | 12-16 hours     | 🟣 Critical |
| Phase 5: Sync Integration | 3            | 14-18 hours     | 🔵 Future   |
| Phase 6: Documentation    | 3            | 10-13 hours     | 🟢 Low      |
| **Total**                 | **19 tasks** | **71-96 hours** |             |

### Critical Path

1. **Phase 1** (Foundation) — Must complete first
2. **Phase 4** (Orchestration) — Depends on Phase 1-3
3. **Phase 2** (Spike Data) — Core scientific value
4. **Phase 3** (Raw Data) — Optional but recommended
5. **Phase 5** (Sync) — Future enhancement
6. **Phase 6** (Docs) — Final polish

### Recommended Order

For a single developer:

1. **Week 1**: Phase 1 (Foundation) — Get devices and electrodes working
2. **Week 2**: Phase 2 (Spike Data) — Core spike sorting ingestion
3. **Week 3**: Phase 4 (Orchestration) — Integrate into pipeline
4. **Week 4**: Phase 3 (Raw Data) + Phase 6 (Docs) — Polish and documentation
5. **Future**: Phase 5 (Sync) — When ready for master clock integration

## Risk Mitigation

| Risk                                 | Impact | Mitigation Strategy                            |
| ------------------------------------ | ------ | ---------------------------------------------- |
| .meta file format changes            | High   | Version-check probe type, add format adapters  |
| Kilosort output incompatibility      | Medium | Support multiple versions (KS3, KS4), document |
| Large AP files cause issues          | Medium | Default to external links, warn on copy        |
| Integration breaks existing pipeline | High   | Comprehensive integration tests, feature flag  |
| Multi-probe electrode ID collision   | High   | Strict unique ID generation with offset        |

## Notes

- All tasks assume familiarity with existing pipeline architecture
- Unit test coverage target: 90%+
- Integration test coverage: All critical paths
- Performance benchmarks required for Phases 2-4
- User documentation should match code completion (not ahead)
