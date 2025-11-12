# W2T-BKIN Module Documentation

## Overview

The W2T Body Kinematics Pipeline is organized into 12 modular Python packages, each with well-defined responsibilities and minimal coupling. This documentation provides detailed information about each module's purpose, interfaces, and usage.

## Module Architecture

```
Foundation (Phase 0)
├── utils       - Shared utilities (hashing, paths, subprocess, logging)
├── domain      - Pydantic models (immutable data contracts)
└── config      - Configuration loading and validation

Ingestion (Phase 1)
└── ingest      - File discovery and manifest building

Synchronization (Phase 2)
└── sync        - Timebase providers and alignment

Optional Modalities (Phase 3)
├── events      - Bpod .mat file parsing and behavioral data extraction
├── transcode   - Video transcoding to mezzanine format
├── pose        - DLC/SLEAP pose import and harmonization
└── facemap     - Facial metrics computation and alignment

Output (Phase 4-5)
├── nwb         - NWB file assembly
├── validate    - nwbinspector validation (not yet implemented)
└── qc          - QC HTML report generation (not yet implemented)

Orchestration
└── cli         - Command-line interface
```

## Design Principles

1. **No cross-imports** between sibling service packages
2. **Composition through files** + domain models only
3. **Fail fast** before heavy processing
4. **Sidecars for observability** (verification, alignment, provenance, validation)
5. **Deterministic outputs** when inputs unchanged

## Module Dependencies

- **Foundation modules** (utils, domain, config) have no dependencies on other pipeline modules
- **Ingest** depends on: utils, domain, config
- **Sync** depends on: utils, domain, config
- **Events** depends on: utils, domain (Phase 3, optional)
- **Optional modalities** (transcode, pose, facemap) depend on: utils, domain
- **NWB** depends on: utils, domain, and optional modality outputs
- **QC/Validate** (not yet implemented) will depend on: utils, domain, nwb
- **CLI** (not yet implemented) will orchestrate all modules

## Documentation Contents

- [01-utils](./01-utils.md) - Shared utilities ✅
- [02-domain](./02-domain.md) - Domain models ✅
- [03-config](./03-config.md) - Configuration management ✅
- [04-ingest](./04-ingest.md) - File ingestion ✅
- [05-events](./05-events.md) - Bpod event parsing ✅
- [06-sync](./06-sync.md) - Timebase synchronization ✅
- [07-transcode](./07-transcode.md) - Video transcoding (to be documented)
- [08-pose](./08-pose.md) - Pose estimation (to be documented)
- [09-facemap](./09-facemap.md) - Facial metrics (to be documented)
- [10-nwb](./10-nwb.md) - NWB assembly (to be documented)
- [11-validate](./11-validate.md) - NWB validation (not yet implemented)
- [12-qc](./12-qc.md) - QC reporting (not yet implemented)
- [13-cli](./13-cli.md) - Command-line interface (not yet implemented)

## Quick Reference

| Module    | Phase | Status             | Key Functions                                                  | Requirements      |
| --------- | ----- | ------------------ | -------------------------------------------------------------- | ----------------- |
| utils     | 0     | ✅ Complete        | compute_hash, sanitize_path, run_ffprobe                       | NFR-1/2/3         |
| domain    | 0     | ✅ Complete        | All Pydantic models                                            | FR-12, NFR-7      |
| config    | 0     | ✅ Complete        | load_config, load_session                                      | FR-10, NFR-10/11  |
| ingest    | 1     | ✅ Complete        | build_manifest, verify_manifest                                | FR-1/2/3/13/15/16 |
| sync      | 2     | ✅ Complete        | create_timebase_provider, align_samples                        | FR-TB-1..6, FR-17 |
| events    | 3     | ✅ Complete        | parse_bpod_mat, extract_trials, extract_behavioral_events      | FR-11/14, NFR-7   |
| transcode | 3     | ✅ Complete        | transcode_video, compute_video_checksum                        | FR-4, NFR-2       |
| pose      | 3     | ✅ Complete        | import_dlc_pose, import_sleap_pose, harmonize_dlc_to_canonical | FR-5              |
| facemap   | 3     | ✅ Complete        | define_rois, compute_facemap_signals                           | FR-6              |
| nwb       | 4     | � Stub only        | assemble_nwb (planned)                                         | FR-7, NFR-6       |
| validate  | 5     | ❌ Not implemented | run_nwbinspector (planned)                                     | FR-9              |
| qc        | 5     | ❌ Not implemented | render_qc_report (planned)                                     | FR-8/14, NFR-3    |
| cli       | -     | ❌ Not implemented | Typer commands (planned)                                       | User interaction  |

## Getting Started

For a typical pipeline execution:

```python
from w2t_bkin import config, ingest, sync, events, nwb

# 1. Load configuration
cfg = config.load_config("tests/fixtures/configs/valid_config.toml")
session = config.load_session("tests/fixtures/data/raw/Session-000001/session.toml")

# 2. Ingest and verify
manifest = ingest.build_manifest(cfg, session)
verification = ingest.verify_manifest(manifest, tolerance=5, warn_on_mismatch=True)

# 3. Create timebase and align (Phase 2)
from w2t_bkin.sync import create_timebase_provider, align_samples
provider = create_timebase_provider(cfg, manifest)
# reference_times = provider.get_timestamps(n_samples=1000)
# alignment = align_samples(sample_times, reference_times, cfg.timebase)

# 4. Optional: Parse Bpod behavioral data (Phase 3)
if session.bpod:
    from w2t_bkin.events import parse_bpod_mat, extract_trials, extract_behavioral_events
    bpod_data = parse_bpod_mat(session.bpod.files[0])
    trials = extract_trials(bpod_data)
    events_list = extract_behavioral_events(bpod_data)

# 5. Optional: Import pose/facemap (Phase 3)
# from w2t_bkin.pose import import_dlc_pose, harmonize_dlc_to_canonical
# from w2t_bkin.facemap import define_rois, compute_facemap_signals
# pose_data = import_dlc_pose(pose_csv_path)
# harmonized = harmonize_dlc_to_canonical(pose_data, mapping)
# facemap_signals = compute_facemap_signals(video_path, rois)

# 6. Assemble NWB (Phase 4 - not yet implemented)
# nwb_path = nwb.assemble_nwb(manifest, cfg, bundles=[...])

# 7. Validate and QC (Phase 5 - not yet implemented)
# validate.run_nwbinspector(nwb_path)
# qc.render_qc_report(nwb_path, verification, ...)
```

## Testing

Each module has comprehensive test coverage:

- **Unit tests**: `tests/unit/test_<module>.py`
- **Integration tests**: `tests/integration/test_phase_<N>_<name>.py`
- **Property tests**: `tests/property/test_invariants.py`

**Implemented test files:**

- ✅ `test_utils.py` - Utility functions
- ✅ `test_domain.py` - Pydantic models
- ✅ `test_config.py` - Configuration loading
- ✅ `test_ingest.py` - File discovery and verification
- ✅ `test_sync.py` - Timebase providers and alignment
- ✅ `test_events.py` - Bpod parsing and event extraction
- ✅ `test_transcode.py` - Video transcoding
- ✅ `test_pose.py` - Pose import and harmonization
- ✅ `test_facemap.py` - ROI and motion energy computation

Run tests with:

```bash
pytest tests/unit/test_config.py -v
pytest tests/integration/ -v
pytest -m integration  # Run all integration tests
```

## Error Handling

All modules use structured errors with clear inheritance:

```python
from w2t_bkin.utils import VideoAnalysisError
from w2t_bkin.config import ValidationError  # from Pydantic
from w2t_bkin.ingest import IngestError
from w2t_bkin.sync import SyncError, JitterBudgetExceeded
from w2t_bkin.events import EventsError, BpodParseError
from w2t_bkin.transcode import TranscodeError
from w2t_bkin.pose import PoseError
from w2t_bkin.facemap import FacemapError

try:
    manifest = ingest.build_manifest(cfg, session)
except IngestError as e:
    print(f"Ingest failed: {e}")

try:
    trials = events.extract_trials(bpod_data)
except BpodParseError as e:
    print(f"Bpod parsing failed: {e}")
```

**Standard exceptions used:**

- `ValueError` - Invalid input parameters
- `FileNotFoundError` - Missing required files
- `ValidationError` (Pydantic) - Schema validation failures

## Contributing

When adding new functionality:

1. **Define domain models** in `domain.py`
2. **Implement module logic** following existing patterns
3. **Write tests first** (TDD approach)
4. **Update documentation** in this directory
5. **Follow naming conventions**: `test_Should_X_When_Y`

## Further Reading

- [Design Document](../../design.md) - Architecture and principles
- [Requirements](../../requirements.md) - Functional and non-functional requirements
- [Tasks](../../tasks.md) - Implementation roadmap
