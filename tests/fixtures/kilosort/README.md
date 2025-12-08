# Kilosort Fixtures

This directory contains Kilosort spike sorting output fixtures for testing units ingestion.

## Files

### Core Spike Data

- **`spike_times.npy`** (100,928 bytes): Spike times in samples (12,600 spikes)
- **`spike_clusters.npy`** (50,528 bytes): Cluster assignments for each spike (12,600 values)
- **`templates.npy`** (210,048 bytes): Mean waveforms (20 units × 82 samples × 32 channels)

### Quality Labels

- **`cluster_info.tsv`**: Primary quality metadata (Kilosort 4 format)

  - `cluster_id`: Unit identifier
  - `KSLabel`: Quality label (good, mua, noise)
  - `ch`: Peak electrode channel
  - `ContamPct`: Contamination percentage
  - `Amplitude`: Spike amplitude (μV)

- **`cluster_KSLabel.tsv`**: Fallback quality labels (older Kilosort versions)
  - Minimal format with just `cluster_id` and `KSLabel`

### Additional Files

- **`cluster_KSLabel.npy`** (legacy): Binary format of quality labels
- **`cluster_ContamPct.tsv`**: Standalone contamination metrics

## Data Characteristics

**Recording Parameters**:

- Duration: 60 seconds
- Sampling rate: 30,000 Hz
- Total samples: 1,800,000

**Spike Sorting Results**:

- Total units: 20
  - Good units: 12
  - Multi-unit activity (MUA): 5
  - Noise: 3
- Total spikes: 12,600
- Firing rates: 1-20 Hz (linear increase by unit ID)

**Waveform Templates**:

- Samples per waveform: 82 (~2.7 ms at 30 kHz)
- Channels per template: 32 (subset for compact fixtures)
- Data type: float32

## Usage

```python
from pathlib import Path
from w2t_bkin.ingest.kilosort import (
    load_kilosort_data,
    load_cluster_labels,
    add_units_from_kilosort
)

# In test fixtures
@pytest.fixture
def kilosort_dir(self):
    return Path(__file__).parent.parent / "fixtures/kilosort"

# Load data
data = load_kilosort_data(kilosort_dir)
print(data["spike_times"].shape)     # (12600,)
print(data["spike_clusters"].shape)  # (12600,)
print(data["templates"].shape)       # (20, 82, 32)

# Load quality labels
labels = load_cluster_labels(kilosort_dir)
good_units = labels[labels["KSLabel"] == "good"]
print(len(good_units))  # 12

# Add to NWB
stats = add_units_from_kilosort(
    nwbfile=nwbfile,
    sorting_dir=kilosort_dir,
    probe_id="imec0",
    sampling_rate=30000.0,
    include_labels=["good", "mua"],
    min_spike_count=100,
)
print(stats["n_units_added"])  # 17 (12 good + 5 mua)
```

## Used By

- `tests/unit/test_kilosort.py` - Data loading and units ingestion tests
- `tests/integration/test_ecephys_phase1.py` - Phase 2 integration tests (spike sorting)

## Notes

- Spike times are in **samples**, not seconds (conversion happens during ingestion)
- Cluster IDs are contiguous (0-19), but real data may have gaps from manual curation
- Templates use only 32 channels for compact fixture size (real templates typically have 384 channels)
- Firing rates follow Poisson distribution for realistic spike train statistics
