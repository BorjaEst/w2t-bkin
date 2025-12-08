---
post_title: "Design — Neuropixels Ecephys Integration"
author1: "Project Team"
post_slug: "design-ecephys"
microsoft_alias: "na"
featured_image: "/assets/og.png"
categories: ["docs", "ecephys", "design"]
tags: ["neuropixels", "spike-sorting", "architecture", "nwb"]
ai_note: "Technical design for ecephys integration."
summary: "Technical architecture, module responsibilities, data flows, and API contracts for integrating Neuropixels extracellular electrophysiology data into the NWB pipeline."
post_date: "2025-12-05"
---

# Design — Neuropixels Ecephys Integration

## Overview

This document describes the technical design for integrating Neuropixels extracellular electrophysiology (ecephys) data into the w2t-bkin pipeline. The design follows the existing **NWB-First** architecture where all processing modules produce NWB-native data structures directly.

**Implementation Strategy**: Phase 1 focuses on ingesting preprocessed data (CatGT, TPrime, Kilosort outputs). Future phases will add automated preprocessing pipelines.

## Architecture Integration

### Layer Assignment

Following the existing three-layer architecture:

```
Foundation Layer (Available to all)
  └─ pynwb, hdmf, ndx-* extensions

Low-Level Tools (Primitives only)
  └─ ingest.ecephys           [NEW MODULE]

Mid-Level Tools (Composition)
  └─ sync                      [EXTENDED: neuropixels timebase provider]

High-Level Orchestration (Session-aware)
  ├─ config                    [EXTENDED: [ecephys] section]
  ├─ core.session              [EXTENDED: add_ecephys_data()]
  └─ core.pipeline             [EXTENDED: Phase 2.5 - Ecephys Ingestion]
```

### Module Responsibilities

| Module                     | Layer      | Input                        | Output                                        | Dependencies           |
| -------------------------- | ---------- | ---------------------------- | --------------------------------------------- | ---------------------- |
| `ingest.ecephys`           | Low-level  | File paths, primitives       | NWB objects (Device, ElectricalSeries, Units) | pynwb, numpy, utils    |
| `sync` (extended)          | Mid-level  | TTL timestamps, probe config | Alignment indices                             | ingest.ecephys         |
| `core.session` (extended)  | High-level | Config, NWBFile, probe data  | Populated NWBFile                             | ingest.ecephys, config |
| `core.pipeline` (extended) | High-level | Config, session path         | Complete session                              | core.session           |

## Data Flow

### Phase 1: Discovery and Verification

**High-level orchestration** (`pipeline.py`) discovers ecephys data:

```python
# Inline in pipeline.run_session()
if config.ecephys.enabled:
    for probe_id in config.ecephys.probes:
        # Discover preprocessed data
        meta_files = discover_files(session_path / "interim/neural/catgt", f"*{probe_id}.ap.meta")
        sorting_dir = session_path / "interim/neural/kilosort" / probe_id

        # Verify required files exist
        verify_ecephys_files(meta_files, sorting_dir, probe_id)

        # Store for Phase 2.5
        discovered_probes[probe_id] = {
            "meta_path": meta_files[0],
            "sorting_dir": sorting_dir,
            "ap_bin_path": find_ap_bin(meta_files[0]),
        }
```

### Phase 2.5: Ecephys Ingestion

**High-level orchestration** calls low-level tools with primitives:

```python
# pipeline.py - Phase 2.5
for probe_id, probe_data in discovered_probes.items():
    # Get device metadata from metadata.toml
    device_name = f"neuropixels_{probe_id}"
    device_meta = session.devices[device_name]

    # Call low-level tools with primitives only
    device = ecephys.create_neuropixels_device(
        nwbfile=nwbfile,
        device_name=device_name,
        manufacturer=device_meta["manufacturer"],
        model_name=device_meta["model_name"],
        description=device_meta["description"],
    )

    ecephys.add_electrodes_from_meta(
        nwbfile=nwbfile,
        meta_path=probe_data["meta_path"],
        device=device,
        probe_id=probe_id,
        location=config.ecephys.get(f"location_{probe_id}", "unknown"),
    )

    ecephys.add_spike_sorting(
        nwbfile=nwbfile,
        sorting_dir=probe_data["sorting_dir"],
        probe_id=probe_id,
        include_labels=config.ecephys.quality.include_labels,
        min_spike_count=config.ecephys.quality.min_spike_count,
    )

    if config.ecephys.storage.raw_data_strategy != "skip":
        ecephys.add_raw_data(
            nwbfile=nwbfile,
            ap_bin_path=probe_data["ap_bin_path"],
            probe_id=probe_id,
            storage_strategy=config.ecephys.storage.raw_data_strategy,
        )
```

## Module Design: `ingest.ecephys`

### File Structure

```
src/w2t_bkin/ingest/ecephys/
├── __init__.py              # Public API exports
├── device.py                # Device and electrode creation
├── sorting.py               # Kilosort output ingestion
├── raw_data.py              # Raw AP band data (external links)
└── parsers.py               # .meta, .npy, .tsv file parsers
```

### API Contract

#### 1. Device Creation

```python
def create_neuropixels_device(
    nwbfile: NWBFile,
    device_name: str,
    manufacturer: str = "IMEC",
    model_name: str = "Neuropixels 2.0",
    description: str = "",
) -> Device:
    """
    Create a Device object for a Neuropixels probe.

    Args:
        nwbfile: NWBFile to add device to
        device_name: Unique device identifier (e.g., "neuropixels_imec0")
        manufacturer: Device manufacturer
        model_name: Probe model (e.g., "Neuropixels 1.0", "Neuropixels 2.0")
        description: Human-readable description

    Returns:
        Device object added to nwbfile

    Raises:
        ValueError: If device_name already exists in nwbfile
    """
```

#### 2. Electrodes Table Population

```python
def add_electrodes_from_meta(
    nwbfile: NWBFile,
    meta_path: Path,
    device: Device,
    probe_id: str,
    location: str = "unknown",
    group_name: Optional[str] = None,
) -> int:
    """
    Parse SpikeGLX .meta file and populate electrodes table.

    Args:
        nwbfile: NWBFile to add electrodes to
        meta_path: Path to .meta file (e.g., *_tcat.imec0.ap.meta)
        device: Device object created by create_neuropixels_device()
        probe_id: Probe identifier (e.g., "imec0")
        location: Brain region (e.g., "Motor Cortex, M1")
        group_name: ElectrodeGroup name (defaults to f"probe_{probe_id}")

    Returns:
        Number of electrodes added

    Raises:
        FileNotFoundError: If meta_path does not exist
        ValueError: If .meta file is malformed
    """
```

**Implementation Notes**:

- Parse `imDatPrb_type` to determine probe generation (1.0, 2.0, etc.)
- Extract channel count from `nSavedChans`
- Extract sampling rate from `imSampRate`
- If available, parse `~snsGeomMap` for x/y coordinates
- Create single ElectrodeGroup for all channels on this probe
- Add electrodes to table with:
  - `id`: Auto-incremented (ensure uniqueness across probes)
  - `group`: ElectrodeGroup reference
  - `location`: Brain region string
  - `x`, `y`, `z`: Coordinates (if available)
  - `filtering`: "High-pass filtered at 300 Hz" (from CatGT settings)
  - `imp`: Impedance (if available in metadata)

#### 3. Spike Sorting Ingestion

```python
def add_spike_sorting(
    nwbfile: NWBFile,
    sorting_dir: Path,
    probe_id: str,
    include_labels: Optional[List[str]] = None,
    min_spike_count: int = 0,
    add_waveforms: bool = False,
    add_quality_metrics: bool = False,
) -> Dict[str, int]:
    """
    Load Kilosort output and populate NWB Units table.

    Args:
        nwbfile: NWBFile to add units to
        sorting_dir: Path to Kilosort output (e.g., interim/neural/kilosort/imec0/)
        probe_id: Probe identifier for electrode lookup
        include_labels: Quality labels to include (e.g., ["good", "mua"]). None = all.
        min_spike_count: Minimum spike count threshold (0 = no threshold)
        add_waveforms: Include mean waveforms from templates.npy
        add_quality_metrics: Include ContamPct, Amplitude as custom columns

    Returns:
        Summary statistics: {"units_added": N, "spikes_added": M, "units_filtered": K}

    Raises:
        FileNotFoundError: If required .npy files missing
        ValueError: If electrode indices out of bounds
    """
```

**Implementation Notes**:

- **Required files**: `spike_times.npy`, `spike_clusters.npy`
- **Optional files**: `cluster_info.tsv`, `cluster_KSLabel.tsv`, `templates.npy`, `cluster_ContamPct.tsv`, `cluster_Amplitude.tsv`
- **Sampling rate**: Load from `.meta` file (parse from `meta_path` determined during discovery)
- **Unit filtering**:
  1. Load cluster labels from `cluster_KSLabel.tsv` (columns: `cluster_id`, `KSLabel`)
  2. If `include_labels` specified, filter to matching labels
  3. Count spikes per cluster from `spike_clusters.npy`
  4. If `min_spike_count` specified, exclude below threshold
- **Spike time conversion**: Convert samples → seconds: `spike_times_sec = spike_times_samples / sampling_rate`
- **Electrode assignment**: Map cluster → electrode using `cluster_info.tsv` → `ch` column
- **Waveforms** (if `add_waveforms=True`):
  - Load `templates.npy` (shape: `[n_templates, n_samples, n_channels]`)
  - Map cluster → template using `spike_templates.npy` (take modal template per cluster)
  - Add to Units table as `waveform_mean` column
- **Quality metrics** (if `add_quality_metrics=True`):
  - Add custom columns: `contamination_pct`, `amplitude`
  - Load from respective `.tsv` files

#### 4. Raw Data Linking

```python
def add_raw_data(
    nwbfile: NWBFile,
    ap_bin_path: Path,
    probe_id: str,
    storage_strategy: Literal["link", "copy", "skip"] = "link",
    series_name: Optional[str] = None,
) -> Optional[ElectricalSeries]:
    """
    Add artifact-blanked AP band data to NWB.

    Args:
        nwbfile: NWBFile to add data to
        ap_bin_path: Path to .bin file (e.g., interim/neural/tprime/blanked_*.imec0.ap.bin)
        probe_id: Probe identifier for electrode lookup
        storage_strategy: "link" (HDF5 external link), "copy" (embed), "skip" (none)
        series_name: ElectricalSeries name (defaults to f"ElectricalSeries_{probe_id}")

    Returns:
        ElectricalSeries object if added, None if skipped

    Raises:
        FileNotFoundError: If ap_bin_path does not exist
        ValueError: If .meta file not found or sampling rate unavailable
    """
```

**Implementation Notes**:

- **Meta file lookup**: Infer `.meta` path from `.bin` path (same name, `.meta` extension)
- **Sampling rate**: Parse from `.meta` file (`imSampRate`)
- **Channel count**: Parse from `.meta` file (`nSavedChans`)
- **Data shape**: `[n_samples, n_channels]` (samples = filesize / (n_channels \* 2 bytes))
- **Storage strategy**:
  - `"link"`: Create `h5py.ExternalLink` to `.bin` file (relative path from NWB file)
  - `"copy"`: Memory-map `.bin` → copy to NWB dataset (warn about file size)
  - `"skip"`: Return `None`, log message
- **Electrode region**: Create `DynamicTableRegion` referencing all electrodes for this probe
- **ElectricalSeries construction**:
  ```python
  ElectricalSeries(
      name=series_name,
      description=f"Artifact-blanked AP band data from {probe_id}",
      data=data_link,  # H5DataIO with external link or direct array
      electrodes=electrode_region,
      starting_time=0.0,  # Neuropixels is master clock
      rate=sampling_rate,
      conversion=1e-6,  # Convert to volts (SpikeGLX uses microvolts)
      unit="volts",
  )
  ```
- **Add to acquisition**: `nwbfile.add_acquisition(electrical_series)`

### Parsing Utilities (`parsers.py`)

#### SpikeGLX .meta Parser

```python
def parse_spikeglx_meta(meta_path: Path) -> Dict[str, Any]:
    """
    Parse SpikeGLX .meta file into structured dictionary.

    Returns:
        {
            "sampling_rate": float,  # imSampRate
            "n_channels": int,       # nSavedChans
            "probe_type": str,       # imDatPrb_type (0=NP1.0, 21=NP2.0 single-shank, etc.)
            "geometry": List[Tuple[float, float]],  # [(x, y), ...] from ~snsGeomMap
            "filtering": str,        # Inferred from CatGT settings
        }
    """
```

**Implementation**:

- .meta files are simple key-value text files (`key=value\n`)
- Use regex or `configparser` to parse
- Cache parsed results in memory (decorator: `@functools.lru_cache`)

#### Kilosort File Loaders

```python
def load_kilosort_data(sorting_dir: Path) -> Dict[str, np.ndarray]:
    """Load core Kilosort files into memory."""
    return {
        "spike_times": np.load(sorting_dir / "spike_times.npy"),
        "spike_clusters": np.load(sorting_dir / "spike_clusters.npy"),
        "templates": np.load(sorting_dir / "templates.npy") if exists else None,
    }

def load_cluster_labels(sorting_dir: Path) -> pd.DataFrame:
    """Load cluster quality labels (KSLabel, group)."""
    # Try cluster_info.tsv first (newer Kilosort), fallback to cluster_KSLabel.tsv
    ...

def load_cluster_metrics(sorting_dir: Path) -> pd.DataFrame:
    """Load quality metrics (ContamPct, Amplitude, etc.)."""
    ...
```

## Configuration Extension

### `configuration.toml`

```toml
[ecephys]
enabled = false  # Master switch (default off to not break existing pipelines)

# List of probe device names (must match [[devices]] in metadata.toml)
probes = ["neuropixels_imec0", "neuropixels_imec1"]

[ecephys.storage]
# How to handle raw AP band data
raw_data_strategy = "link"  # Options: "link" | "copy" | "skip"

# Whether to compute LFP (future: pipeline can generate from AP)
compute_lfp = false

[ecephys.quality]
# Filter units by cluster quality labels
include_labels = ["good", "mua"]  # Options: "good", "mua", "noise" (from cluster_KSLabel.tsv)

# Minimum spike count per unit
min_spike_count = 100

# Whether to include additional data in Units table
add_waveforms = false         # Include mean waveforms (increases file size)
add_quality_metrics = false   # Include ContamPct, Amplitude, etc.

# Brain region per probe (optional, can override metadata.toml)
# location_imec0 = "Motor Cortex, M1"
# location_imec1 = "Sensory Cortex, S1"
```

### `metadata.toml`

```toml
# Add to [[devices]] section
[[devices]]
name = "neuropixels_imec0"
description = "Neuropixels 2.0 probe - Motor Cortex"
manufacturer = "IMEC"
model_name = "Neuropixels 2.0"

[[devices]]
name = "neuropixels_imec1"
description = "Neuropixels 2.0 probe - Sensory Cortex"
manufacturer = "IMEC"
model_name = "Neuropixels 2.0"

# TTL channels recorded by Neuropixels NIDQ
[[TTLs]]
id = "ttl_camera"
paths = "neural/TPrime_output/corrected_7_video_TTLs.txt"
description = "Camera frame triggers recorded by Neuropixels NIDQ XA_7_0"

[[TTLs]]
id = "ttl_cue"
paths = "neural/TPrime_output/corrected_1_response_TTLs.txt"
description = "Behavioral cue onsets recorded by Neuropixels NIDQ XA_1_0"

[[TTLs]]
id = "ttl_bpod_trials"
paths = "neural/TPrime_output/corrected_3_trials_TTLs.txt"
description = "Bpod trial start markers recorded by Neuropixels NIDQ XD_3_0"
```

## Synchronization Integration

### Neuropixels as Master Clock

When `synchronization.reference_channel = "neuropixels"` (future config option):

1. **Spike times**: Already in reference time (no transformation needed)
2. **Camera frames**: Align using `ttl_camera` (TPrime-corrected timestamps)
3. **Bpod trials**: Align using `ttl_bpod_trials` (TPrime-corrected timestamps)
4. **Pose data**: Inherits camera timestamp alignment

### Timebase Provider Extension

```python
# sync/timebase.py (extended)

class NeuropixelsTimebaseProvider(TimebaseProvider):
    """Use Neuropixels sampling clock as reference."""

    def __init__(self, meta_path: Path):
        self.meta = parse_spikeglx_meta(meta_path)
        self.sampling_rate = self.meta["sampling_rate"]

    def get_reference_timestamps(self) -> np.ndarray:
        """Return spike times as-is (already in reference time)."""
        # No transformation needed - Neuropixels IS the reference
        return np.array([])  # Placeholder, not used

    def align_to_reference(self, timestamps: np.ndarray, source: str) -> np.ndarray:
        """Map external timestamps to Neuropixels time."""
        # Use TPrime-corrected TTL files for alignment
        ttl_times = load_tprime_corrected_ttl(source)
        return align_nearest(timestamps, ttl_times)
```

## Error Handling

### Discovery Phase Errors

| Condition               | Error Type          | Message                                           | Recovery                     |
| ----------------------- | ------------------- | ------------------------------------------------- | ---------------------------- |
| No `.meta` file found   | `FileNotFoundError` | "Neuropixels .meta file not found for {probe_id}" | Abort, show expected path    |
| Multiple `.meta` files  | `ValueError`        | "Multiple .meta files found, expected 1"          | Abort, show discovered files |
| Kilosort dir missing    | `FileNotFoundError` | "Kilosort output not found: {sorting_dir}"        | Abort, show expected path    |
| Required `.npy` missing | `FileNotFoundError` | "Required Kilosort file missing: spike_times.npy" | Abort, list missing files    |

### Ingestion Phase Errors

| Condition                    | Error Type          | Message                                         | Recovery                      |
| ---------------------------- | ------------------- | ----------------------------------------------- | ----------------------------- |
| Invalid electrode index      | `ValueError`        | "Spike cluster references invalid electrode ID" | Abort, show out-of-bounds IDs |
| Malformed `.meta` file       | `ValueError`        | "Failed to parse sampling rate from .meta"      | Abort, show parsing error     |
| Empty spike times            | `Warning`           | "No spikes found after quality filtering"       | Continue, log warning         |
| External link target missing | `FileNotFoundError` | "AP bin file not found: {ap_bin_path}"          | Abort, show expected path     |

## Testing Strategy

### Unit Tests

```python
# tests/unit/ingest/test_ecephys.py

def test_parse_spikeglx_meta_np20():
    """Parse NP2.0 .meta file correctly."""
    meta = parse_spikeglx_meta(Path("fixtures/imec0.ap.meta"))
    assert meta["sampling_rate"] == 30000.0
    assert meta["n_channels"] == 384

def test_create_device():
    """Create Device with correct attributes."""
    nwbfile = NWBFile(...)
    device = create_neuropixels_device(nwbfile, "test_probe")
    assert device.name == "test_probe"
    assert device.manufacturer == "IMEC"

def test_add_electrodes_from_meta():
    """Populate electrodes table from .meta file."""
    nwbfile = NWBFile(...)
    device = create_neuropixels_device(nwbfile, "imec0")
    n_added = add_electrodes_from_meta(nwbfile, meta_path, device, "imec0")
    assert n_added == 384
    assert len(nwbfile.electrodes) == 384

def test_add_spike_sorting_quality_filter():
    """Filter units by quality label."""
    nwbfile = NWBFile(...)
    # ... add electrodes ...
    stats = add_spike_sorting(
        nwbfile, sorting_dir, "imec0",
        include_labels=["good"], min_spike_count=100
    )
    assert stats["units_added"] < stats["units_filtered"]  # Some filtered out

def test_external_link_creation():
    """Create HDF5 external link to AP bin."""
    nwbfile = NWBFile(...)
    # ... add electrodes ...
    series = add_raw_data(nwbfile, ap_bin_path, "imec0", storage_strategy="link")
    assert series is not None
    # Verify link points to correct file (requires writing NWB to test)
```

### Integration Tests

```python
# tests/integration/test_ecephys_pipeline.py

def test_ecephys_session_end_to_end(tmp_path):
    """Run full pipeline with ecephys data."""
    # Setup fixture session with:
    #   - interim/neural/catgt/*_tcat.imec0.ap.{bin,meta}
    #   - interim/neural/kilosort/imec0/*.npy
    #   - metadata.toml with neuropixels devices
    #   - configuration.toml with [ecephys] enabled

    result = pipeline.run_session(config_path, session_id)

    # Verify NWB contents
    with NWBHDF5IO(result.nwb_path, "r") as io:
        nwb = io.read()
        assert "neuropixels_imec0" in nwb.devices
        assert len(nwb.electrodes) == 384
        assert len(nwb.units) > 0
        assert "ElectricalSeries_imec0" in nwb.acquisition
```

## Performance Considerations

### Memory Management

**Spike sorting data loading**:

- Lazy load `.npy` files only when needed
- Process units in batches if memory-constrained (unlikely for typical datasets)
- Use memory-mapped arrays for large `templates.npy` files

**External links**:

- Significantly reduces NWB file size (GB → MB)
- No memory overhead (data not loaded until accessed)
- Trade-off: NWB portability requires moving `.bin` files alongside

### File I/O Optimization

**Electrode table population**:

- Parse `.meta` file once, cache results
- Batch insert electrodes (PyNWB handles efficiently)

**Units table population**:

- Pre-allocate arrays for spike times
- Use `add_unit()` in a loop (PyNWB optimizes internally)

## Migration Guide

For existing datasets with data in `raw/neural/`:

1. **Create interim structure**:

   ```bash
   mkdir -p data/interim/{subject}/{session}/neural/{catgt,tprime,kilosort}
   ```

2. **Move CatGT output**:

   ```bash
   mv data/raw/{subject}/{session}/neural/catgt_output/* \
      data/interim/{subject}/{session}/neural/catgt/
   ```

3. **Move TPrime output**:

   ```bash
   mv data/raw/{subject}/{session}/neural/TPrime_output/* \
      data/interim/{subject}/{session}/neural/tprime/
   ```

4. **Move Kilosort output** (per probe):

   ```bash
   mv data/raw/{subject}/{session}/neural/index_run \
      data/interim/{subject}/{session}/neural/kilosort/imec0/
   ```

5. **Optional: Move QC artifacts**:

   ```bash
   mkdir -p data/interim/{subject}/{session}/neural/qc
   mv data/raw/{subject}/{session}/neural/blankshots_* \
      data/interim/{subject}/{session}/neural/qc/
   ```

6. **Keep raw data immutable**:
   ```bash
   # Leave in raw/:
   #   - Original SpikeGLX folders (*_g0/)
   #   - *.ap.bin, *.ap.meta, *.nidq.bin
   ```

## Future Enhancements

### Phase 2: Automated Preprocessing

- Add `processors.catgt` module to run CatGT from raw SpikeGLX
- Add `processors.tprime` module to run TPrime alignment
- Add GPU task scheduling for heavy preprocessing

### Phase 3: Automated Spike Sorting

- Add `processors.kilosort` module with GPU batch execution
- Support alternative sorters (MountainSort, SpyKING CIRCUS)
- Automated quality metrics computation

### Phase 4: LFP Computation

- Downsample AP band (30 kHz → 2.5 kHz)
- Apply low-pass filter (< 300 Hz)
- Store as separate `ElectricalSeries` in `processing/ecephys/LFP`

### Phase 5: Advanced Features

- Spike waveform feature extraction (PCA, spike width)
- Cross-correlation analysis
- Cluster quality metrics visualization in QC reports
- Support for other probe types (Neuropixels Ultra, Utah arrays)

## References

- **SpikeGLX**: https://billkarsh.github.io/SpikeGLX/
- **CatGT**: https://billkarsh.github.io/SpikeGLX/help/catgt/catgt/
- **TPrime**: https://billkarsh.github.io/SpikeGLX/help/tprime/TPrime/
- **Kilosort 4**: https://github.com/MouseLand/Kilosort
- **PyNWB Ecephys Tutorial**: https://pynwb.readthedocs.io/en/stable/tutorials/domain/ecephys.html
