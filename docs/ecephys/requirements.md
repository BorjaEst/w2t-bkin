---
post_title: "Requirements — Neuropixels Ecephys Integration"
author1: "Project Team"
post_slug: "requirements-ecephys"
microsoft_alias: "na"
featured_image: "/assets/og.png"
categories: ["docs", "ecephys", "requirements"]
tags: ["neuropixels", "spike-sorting", "electrophysiology", "nwb"]
ai_note: "Requirements specified following EARS notation."
summary: "Functional and non-functional requirements for integrating Neuropixels extracellular electrophysiology data into the w2t-bkin NWB pipeline."
post_date: "2025-12-05"
---

# Requirements — Neuropixels Ecephys Integration

## Overview

This document defines requirements for integrating Neuropixels extracellular electrophysiology data into the w2t-bkin pipeline. The integration follows the existing NWB-First architecture and supports SpikeGLX recordings with CatGT preprocessing, TPrime temporal alignment, and Kilosort spike sorting.

## Scope

**In Scope**:

- Ingest preprocessed Neuropixels data (CatGT artifact removal, TPrime drift correction)
- Ingest Kilosort spike sorting results into NWB Units table
- Link external raw AP band data (artifact-blanked) into NWB
- Support multi-probe recordings (imec0, imec1)
- Use Neuropixels NIDQ as master timebase for synchronization
- Quality filtering of sorted units based on curation labels

**Out of Scope (Future Phases)**:

- Automated CatGT execution
- Automated TPrime execution
- Automated Kilosort execution
- LFP computation and storage
- Spike waveform feature extraction
- Real-time processing

## Data Organization

### Current State

Raw SpikeGLX data exists in `data/raw/{subject}/{session}/neural/` with CatGT, TPrime, and Kilosort outputs mixed in the same directory tree.

### Target State

WHEN organizing Neuropixels data, THE SYSTEM SHALL follow this structure:

```
data/raw/{subject}/{session}/neural/
  └── {run_name}_g0/            # Immutable SpikeGLX recordings
      ├── {run_name}_g0_imec0/
      │   ├── *.imec0.ap.bin
      │   └── *.imec0.ap.meta
      └── *.nidq.bin

data/interim/{subject}/{session}/neural/
  ├── catgt/                    # Artifact-blanked, concatenated
  │   └── catgt_{run_name}_g0/
  │       ├── *_tcat.imec0.ap.bin
  │       ├── *_tcat.imec0.ap.meta
  │       └── *.nidq.x[ad]_*.txt  # Extracted TTL edges
  ├── tprime/                   # Drift-corrected timestamps
  │   ├── blanked_*.imec0.ap.bin
  │   ├── corrected_*_TTLs.txt
  │   └── ...
  ├── kilosort/                 # Spike sorting results
  │   ├── imec0/
  │   │   ├── spike_times.npy
  │   │   ├── spike_clusters.npy
  │   │   ├── cluster_info.tsv
  │   │   └── templates.npy
  │   └── imec1/
  │       └── ...
  └── qc/                       # Quality control artifacts
      └── blankshots/

data/processed/{subject}/{session}/
  └── session.nwb              # Final NWB with linked AP data
```

## Functional Requirements

### FR-E1: Device and Probe Metadata

**FR-E1.1**: WHEN loading session metadata, THE SYSTEM SHALL support Neuropixels device definitions with manufacturer, model, and serial number.

**FR-E1.2**: WHEN creating an NWBFile, THE SYSTEM SHALL create Device objects for each configured Neuropixels probe (e.g., "neuropixels_imec0", "neuropixels_imec1").

**FR-E1.3**: WHEN a probe serial number is available in metadata, THE SYSTEM SHALL include it in the Device object.

### FR-E2: Electrodes Table Population

**FR-E2.1**: WHEN processing a Neuropixels probe, THE SYSTEM SHALL parse the SpikeGLX `.meta` file to extract electrode configuration.

**FR-E2.2**: WHEN parsing a `.meta` file, THE SYSTEM SHALL extract for each channel:

- Channel ID
- x, y, z coordinates (if available)
- Brain region location (from metadata or config)
- Impedance (if available)
- Filtering applied (from metadata)
- Reference scheme (from metadata)

**FR-E2.3**: WHEN populating the electrodes table, THE SYSTEM SHALL create an ElectrodeGroup for each probe.

**FR-E2.4**: WHEN multiple probes are configured, THE SYSTEM SHALL maintain unique electrode IDs across all probes.

### FR-E3: Spike Sorting Data Ingestion

**FR-E3.1**: WHEN Kilosort output exists in `interim/neural/kilosort/{probe_id}/`, THE SYSTEM SHALL ingest spike sorting results into the NWB Units table.

**FR-E3.2**: WHEN loading Kilosort data, THE SYSTEM SHALL read:

- `spike_times.npy` — Spike timestamps in samples
- `spike_clusters.npy` — Cluster assignment per spike
- `cluster_info.tsv` or `cluster_KSLabel.tsv` — Unit quality labels

**FR-E3.3**: WHEN a quality filter is configured, THE SYSTEM SHALL include only units matching the filter criteria (e.g., "good", "mua").

**FR-E3.4**: WHEN a minimum spike count threshold is configured, THE SYSTEM SHALL exclude units below the threshold.

**FR-E3.5**: WHEN adding units to the NWB Units table, THE SYSTEM SHALL include:

- spike_times (converted to seconds using sampling rate from `.meta`)
- electrodes (region linking to electrodes table)
- quality label (from cluster_KSLabel.tsv)

**FR-E3.6**: WHEN `templates.npy` exists, THE SYSTEM SHALL optionally include mean waveforms in the Units table.

**FR-E3.7**: WHEN cluster quality metrics exist (ContamPct, Amplitude), THE SYSTEM SHALL optionally add them as custom columns to the Units table.

### FR-E4: Raw Data Storage

**FR-E4.1**: WHEN `storage_strategy = "link"`, THE SYSTEM SHALL create an HDF5 external link to the artifact-blanked AP data file (`interim/neural/tprime/blanked_*.imec0.ap.bin`).

**FR-E4.2**: WHEN `storage_strategy = "copy"`, THE SYSTEM SHALL embed the AP data directly in the NWB file (with warning about file size).

**FR-E4.3**: WHEN `storage_strategy = "skip"`, THE SYSTEM SHALL not include raw AP data in the NWB file.

**FR-E4.4**: WHEN adding raw AP data, THE SYSTEM SHALL create an ElectricalSeries object with:

- Data reference (external link or embedded array)
- Sampling rate (from `.meta` file)
- Electrodes region (all channels for this probe)
- Starting time = 0.0 (Neuropixels is master clock)
- Unit = "microvolts"

**FR-E4.5**: WHEN raw AP data is added, THE SYSTEM SHALL place the ElectricalSeries in `nwbfile.acquisition`.

### FR-E5: Synchronization

**FR-E5.1**: WHEN Neuropixels is configured as master clock, THE SYSTEM SHALL use TPrime-corrected TTL timestamps as reference for aligning other modalities.

**FR-E5.2**: WHEN reading TPrime-corrected TTL files, THE SYSTEM SHALL match filenames to TTL channel IDs defined in `metadata.toml`:

- `corrected_1_response_TTLs.txt` → `ttl_cue`
- `corrected_7_video_TTLs.txt` → `ttl_camera`
- `corrected_3_trials_TTLs.txt` → `ttl_bpod_trials`

**FR-E5.3**: WHEN Neuropixels is master clock, THE SYSTEM SHALL NOT apply timebase transformations to spike times (they are already in reference time).

**FR-E5.4**: WHEN Neuropixels is NOT master clock, THE SYSTEM SHALL apply timebase alignment using TTL sync signals (future: FR for external sync).

### FR-E6: Configuration and Metadata

**FR-E6.1**: WHEN `[ecephys].enabled = false` in `configuration.toml`, THE SYSTEM SHALL skip all ecephys processing.

**FR-E6.2**: WHEN `[ecephys].probes` lists probe device names, THE SYSTEM SHALL process only those probes.

**FR-E6.3**: WHEN a configured probe's data is missing from `interim/neural/`, THE SYSTEM SHALL fail with an error message indicating which files are missing.

**FR-E6.4**: WHEN `metadata.toml` defines a device with name matching `[ecephys].probes`, THE SYSTEM SHALL use that device's description and manufacturer in the NWB Device object.

**FR-E6.5**: WHEN `[ecephys.quality].include_labels` is specified, THE SYSTEM SHALL filter units to include only those labels.

**FR-E6.6**: WHEN `[ecephys.quality].min_spike_count` is specified, THE SYSTEM SHALL exclude units below that threshold.

### FR-E7: Verification and Validation

**FR-E7.1**: WHEN discovery phase finds ecephys data, THE SYSTEM SHALL verify:

- Required `.meta` files exist for each probe
- Kilosort output directory exists and contains required `.npy` files
- TPrime-corrected TTL files exist (if sync is enabled)

**FR-E7.2**: WHEN verification fails, THE SYSTEM SHALL log specific missing files and abort before NWB creation.

**FR-E7.3**: WHEN adding units to NWB, THE SYSTEM SHALL verify electrode indices are valid (within electrodes table bounds).

**FR-E7.4**: WHEN linking external AP data, THE SYSTEM SHALL verify the target file exists and is readable.

### FR-E8: Pipeline Integration

**FR-E8.1**: WHEN running the session pipeline, THE SYSTEM SHALL process ecephys data in Phase 2.5 (after Bpod ingestion, before Pose ingestion).

**FR-E8.2**: WHEN ecephys processing succeeds, THE SYSTEM SHALL log summary statistics:

- Number of electrodes added per probe
- Number of units added per probe
- Number of spikes per probe
- Quality label distribution

**FR-E8.3**: WHEN ecephys processing fails, THE SYSTEM SHALL preserve partial NWB file state (devices, electrodes) for debugging.

## Non-Functional Requirements

### NFR-E1: Performance

**NFR-E1.1**: WHEN using external links (`storage_strategy = "link"`), THE SYSTEM SHALL complete NWB file creation in < 10 seconds for typical multi-probe recordings.

**NFR-E1.2**: WHEN loading spike times for 200 units, THE SYSTEM SHALL complete Units table population in < 5 seconds.

**NFR-E1.3**: WHEN reading `.meta` files, THE SYSTEM SHALL cache parsed metadata to avoid re-parsing within the same session.

### NFR-E2: Data Integrity

**NFR-E2.1**: WHEN external links are used, THE SYSTEM SHALL store relative paths (relative to NWB file location) to maintain portability.

**NFR-E2.2**: WHEN spike times are converted to seconds, THE SYSTEM SHALL use double precision (float64) to preserve microsecond timing accuracy.

**NFR-E2.3**: WHEN reading Kilosort cluster IDs, THE SYSTEM SHALL handle non-contiguous cluster numbering (gaps from merged/deleted units).

### NFR-E3: Maintainability

**NFR-E3.1**: THE SYSTEM SHALL implement ecephys ingestion as a low-level module (`ingest.ecephys`) that accepts primitives only (no Config objects).

**NFR-E3.2**: THE SYSTEM SHALL separate parsing logic (`.meta`, `.npy`, `.tsv`) from NWB construction logic.

**NFR-E3.3**: THE SYSTEM SHALL provide standalone functions that can be unit-tested without full pipeline execution.

### NFR-E4: Extensibility

**NFR-E4.1**: THE SYSTEM SHALL support addition of LFP data in future versions without breaking existing spike data workflows.

**NFR-E4.2**: THE SYSTEM SHALL support addition of automated CatGT/TPrime/Kilosort execution in future versions via optional preprocessing stages.

**NFR-E4.3**: THE SYSTEM SHALL support alternative spike sorting tools (e.g., MountainSort, SpyKING CIRCUS) by providing a common Units table interface.

### NFR-E5: Usability

**NFR-E5.1**: WHEN ecephys data is missing, THE SYSTEM SHALL provide actionable error messages indicating:

- Expected file paths (with glob pattern)
- Discovered files (if partial data exists)
- Migration instructions (if data is in `raw/` instead of `interim/`)

**NFR-E5.2**: THE SYSTEM SHALL provide example `metadata.toml` and `configuration.toml` snippets in documentation.

**NFR-E5.3**: THE SYSTEM SHALL log a migration guide when detecting ecephys data in `raw/neural/` that should be in `interim/neural/`.

## Acceptance Criteria

### AC-E1: Metadata and Electrodes

- [ ] NWB file contains Device objects for each configured probe
- [ ] Electrodes table populated with correct channel count per probe
- [ ] Electrode coordinates match `.meta` file specifications
- [ ] ElectrodeGroup correctly links to Device

### AC-E2: Spike Sorting

- [ ] Units table contains spike times for all "good" units (default filter)
- [ ] Spike times converted correctly to seconds using sampling rate
- [ ] Quality labels preserved in Units table
- [ ] Mean waveforms included when templates.npy exists

### AC-E3: Raw Data

- [ ] External link created when `storage_strategy = "link"`
- [ ] Link points to correct artifact-blanked AP file
- [ ] ElectricalSeries has correct sampling rate and units
- [ ] Data accessible via `nwbfile.acquisition["ElectricalSeries_imec0"].data[:]`

### AC-E4: Configuration

- [ ] Pipeline skips ecephys when `enabled = false`
- [ ] Only configured probes are processed
- [ ] Quality filters correctly exclude noise/bad units
- [ ] Minimum spike count threshold enforced

### AC-E5: Integration

- [ ] Pipeline completes successfully with ecephys + behavior + pose
- [ ] All modalities synchronized to Neuropixels master clock
- [ ] NWB file validates with `nwbinspector` (no critical errors)
- [ ] Session summary includes ecephys statistics

## Dependencies

### External Libraries

- `pynwb ~= 3.1.0` — NWB file creation
- `hdmf ~= 4.1.0` — HDF5 external links
- `numpy` — Loading `.npy` files
- `pandas` (optional) — Reading `.tsv` files

### Pipeline Modules

- `config` — Load configuration and metadata
- `utils` — File discovery, path validation, logging
- `sync` — Timebase alignment (when Neuropixels is slave)
- `core.session` — NWBFile assembly

### External Tools (User-Run, Not Pipeline)

- **CatGT** — Artifact removal, TTL extraction
- **TPrime** — Temporal alignment across streams
- **Kilosort 4** — Spike sorting
- **Phy** — Manual curation (optional)

## Risk Assessment

| Risk                                       | Impact | Mitigation                                    |
| ------------------------------------------ | ------ | --------------------------------------------- |
| Large AP files cause NWB bloat             | High   | Default to external links, warn if copying    |
| Electrode coordinates missing from `.meta` | Medium | Allow manual override in metadata.toml        |
| Kilosort version incompatibility           | Medium | Document supported versions, provide adapters |
| TPrime output format changes               | Low    | Version-check corrected TTL files             |
| Multi-probe electrode ID collisions        | High   | Implement strict unique ID generation         |

## Notes

- This integration assumes **Phase 1** implementation: ingest preprocessed data only (no automated CatGT/TPrime/Kilosort).
- Future phases will add automated preprocessing pipelines with GPU task scheduling.
- Neuropixels as master clock is the primary use case; slave mode sync is future work.
