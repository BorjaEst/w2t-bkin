# Tasks and Milestones (No Calibration)

Milestone 0 — Project scaffolding

- T0.1 Initialize repo structure: src/ (package code), configs/ (YAML templates), tests/ (pytest), scripts/, docs/ (MkDocs), models/ (pretrained), .github/workflows
- T0.2 Add pyproject with dependencies (pynwb, ndx-pose, nwbinspector, numpy/pandas, typer, ffmpeg-python, opencv)
- T0.3 Implement basic CLI skeleton and logging
- Acceptance: `mmnwb --help` works; CI runs lint/type/tests

Milestone 1 — Ingestion and manifest

- T1.1 Define YAML config template (paths, session, video, sync, labels, facemap, nwb, qc)
- T1.2 Implement ingest command: discover videos (5 cams), sync files, and optional event logs (e.g., `*_training.ndjson`, `*_trial_stats.ndjson`); compute metadata; write manifest.yaml (with absolute paths for all discovered assets)
- T1.3 Add checksums (optional) and basic input validation
- Acceptance: Manifest includes absolute paths and video metadata for a sample session

Milestone 2 — Synchronization

- T2.1 Implement TTL parser and edge detection (polarity, debounce, tolerances)
- T2.2 Map frame indices to timestamps per camera; detect dropped/duplicate frames
- T2.3 Produce timestamps_cam{i}.csv and sync_summary.json (drift stats, counts)
- T2.4 Unit tests for edge cases (missing frames, irregular TTL)
- Acceptance: Reproducible per-frame timestamps and clear summary metrics
- Note: NDJSON event logs are NOT treated as sync inputs; accepted sync inputs are TTL/frame counter logs (CSV/TSV).

Milestone 3 — Optional video transcoding

- T3.1 Implement transcode command (ffmpeg) with config (codec, crf, preset, keyint)
- T3.2 Verify frame-accurate seeking on outputs; preserve or recompute timestamps as needed
- T3.3 Skippable path if disabled
- Acceptance: Transcoded files present when enabled; stage is a no-op when disabled

Milestone 4 — Pose datasets and inference (DLC/SLEAP)

- T4.1 Frame sampling/export for training datasets (optional)
- T4.2 Import precomputed DLC/SLEAP outputs (CSV/H5/SLP); map to canonical skeleton
- T4.3 Optional inference runners (guarded by extras)
- T4.4 Harmonization: timestamps, keypoint order, confidence, smoothing (optional)
- T4.5 Resolve model paths from `paths.models_root` (default: ./models) with support for absolute paths in config
- Acceptance: Harmonized pose parquet/csv with timestamps aligned to sync

Milestone 5 — Facemap features

- T5.1 Run or import Facemap metrics; define minimal set of signals and metadata
- T5.2 Ensure alignment to session timebase; export standardized table
- Acceptance: Facemap timeseries ready for NWB ingestion

Milestone 6 — NWB export

- T6.1 Build NWBFile: subject/session metadata, devices (5 cameras)
- T6.2 Add per-camera ImageSeries with external_file and timestamps
- T6.3 Add sync TimeSeries; embed config/provenance
- T6.4 Add ndx-pose containers for pose runs
- T6.5 Add facemap BehavioralTimeSeries
- T6.6 If present, add Trials table from `*_trial_stats.ndjson` and BehavioralEvents/processing module for per-sample `*_training.ndjson`
- Acceptance: NWB written; opens with pynwb; contains expected modules and links

Milestone 7 — Validation and QC

- T7.1 nwbinspector integration; save JSON report
- T7.2 QC HTML report with sync charts, pose confidence histograms, facemap previews, metadata table
- Acceptance: QC report renders without errors and highlights anomalies

Milestone 8 — Testing and CI

- T8.1 Unit tests for ingestion, sync math, NWB writer (pytest under tests/)
- T8.2 Tiny synthetic integration dataset; run ingest → sync → to-nwb in CI
- T8.3 Code quality: ruff, mypy
- Acceptance: CI green; test coverage on core logic

Milestone 9 — Documentation

- T9.1 User guide: quickstart, config reference, FAQ (including “what is transcoding?”)
- T9.2 Developer guide: module layout, adding new labelers, schema guidelines
- Acceptance: Docs sufficient for onboarding

Milestone 10 — Release hardening

- T10.1 Versioning and CHANGELOG; SemVer
- T10.2 License and contribution guide
- T10.3 Optional: containerization (Docker) and HPC notes
- Acceptance: Tagged 0.1.0, installable via pip with extras

Cross-cutting tasks

- C1 Logging and error messages with actionable context
- C2 Determinism and idempotence (seed control, stable outputs)
- C3 Performance profiling on representative sessions
- C4 Data privacy (subject anonymization policy)
