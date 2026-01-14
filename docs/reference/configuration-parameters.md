# Configuration Parameters

The pipeline runtime policy lives in `<experiment_root>/configuration.toml`.

This file controls how the pipeline synchronizes streams, verifies integrity, and discovers/produces intermediate artifacts.

## Key sections

## `synchronization`

- `strategy`: `rate_based` | `hardware_pulse` | `network_stream`
- `reference_channel`: TTL channel id used as timebase for `hardware_pulse`
- `alignment.method`: `nearest` or `linear`
- `alignment.tolerance_s`: allowed time error for QC/validation

## `verification`

- `enabled`: master switch
- `check_frame_counts`: count frames via ffprobe (can be slow)
- `check_sync_mismatch`: validate TTL pulse count vs frame count
- `mismatch_tolerance_frames`: allowed mismatch before failing

## `preprocessing.dlc` / `preprocessing.sleap`

This project currently focuses on discovery of existing pose H5 files for assembly into NWB.

- `enabled`: enable/disable pose ingestion
- `mode`: `off` | `discover` | `generate` | `auto`

Discovery contracts are documented as comments in the default `configuration.toml`.

## `logging`

- `level`: `DEBUG` | `INFO` | `WARNING` | `ERROR` | `CRITICAL`
- `structured`: if true, prefer structured logging
