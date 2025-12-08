# SpikeGLX Fixtures

This directory contains SpikeGLX hardware metadata fixtures for testing ecephys ingestion.

## Files

### `sample_np20.imec0.ap.meta`

**Description**: Neuropixels 2.0 metadata file from SpikeGLX recording system.

**Contents**:

- Sampling rate: 30,000 Hz
- Number of channels: 384
- Probe type: Neuropixels 2.0 (NP2000)
- Electrode geometry: Checkerboard pattern

**Used by**:

- `tests/unit/test_spikeglx.py` - Device and electrode creation tests
- `tests/unit/test_ecephys_parsers.py` - Metadata parsing tests
- `tests/integration/test_ecephys_phase1.py` - Phase 1 & 2 integration tests

## Usage

```python
from pathlib import Path

# In test fixtures
@pytest.fixture
def sample_meta_path(self):
    return Path(__file__).parent.parent / "fixtures/spikeglx/sample_np20.imec0.ap.meta"

# Usage
from w2t_bkin.ingest.spikeglx import parse_spikeglx_meta

meta = parse_spikeglx_meta(sample_meta_path)
print(meta["sampling_rate"])  # 30000.0
print(meta["n_channels"])     # 384
```

## Notes

- This is a minimal .meta file with essential fields for testing
- Real .meta files contain additional fields (e.g., gain settings, filter parameters)
- Geometry information is optional and may not be present in all files
