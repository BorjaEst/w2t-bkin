# Design: Multi-camera Mouse Behavior to NWB Pipeline (No Calibration)

Scope and assumptions

- Five hardware-synchronized cameras (cam0–cam4), no camera calibration required (intrinsic/extrinsic are assumed correct or not needed).
- Hardware synchronization via TTL triggers or frame counters to derive per-frame timestamps.
- Pose estimation labels from DeepLabCut (DLC) and/or SLEAP; facial metrics via Facemap.
- Outputs are packaged into NWB using pynwb and ndx-pose, with external video file references preferred.
- Optional video transcoding for frame-accurate seeking and storage normalization (skip if not needed).

Goals

- Reproducible, configuration-driven pipeline that ingests videos + sync, harmonizes labels, and exports NWB with QC and validation.
- Scales from laptop to HPC; idempotent stages; clear artifacts and logs.
- Minimal assumptions about lab-specific data layout; configurable via TOML using Pydantic models (pydantic-settings for environment overrides).

Inputs

- Raw video files for 5 cameras (ideally constant frame rate, but not required).
- Sync signals: TTL events or per-frame trigger logs.
- Optional session event logs (e.g., NDJSON) that describe trials or behavioral events; these are NOT sync TTL and are used for Trials/BehavioralEvents in NWB, not for deriving video timestamps.
- Optional precomputed pose (DLC/SLEAP) and Facemap outputs, or models to run inference. Pretrained models are stored under the repository `models/` directory by default (configurable), and model paths can be absolute.

Outputs

- NWB file:
  - Devices: 5 Camera devices.
  - Acquisition: per-camera ImageSeries with per-frame timestamps, linking external video files.
  - Sync: TTL TimeSeries and/or event series used to compute timestamps.
  - Pose: ndx-pose PoseEstimation/PoseEstimationSeries per model/run, harmonized to a canonical skeleton.
  - Facial metrics: BehavioralTimeSeries (e.g., motion energy, pupil, whisker).
- QC report (HTML) summarizing sync integrity, frame drops, drift, pose confidence, Facemap trace previews.
- nwbinspector validation report.

Pipeline stages (no calibration)

1. Ingestion and manifest

- Discover session resources (videos, sync files, optional labels).
- Extract video metadata (codec, fps, duration, resolution).
- Build a single manifest.json per session with normalized paths and key metadata (JSON for easy downstream consumption; source config remains TOML).
- Compute checksums for provenance (optional).
- Optionally discover and register event logs (e.g., `*.ndjson`) for trials/behavioral events; record absolute paths in the manifest.

2. Synchronization

- Parse hardware TTL or frame counter logs.
- Map frame indices to a common timebase; detect dropped/duplicate frames; compute drift metrics.
- Emit per-camera timestamp CSVs and a sync_summary.json with diagnostics.
- Note: Session event NDJSON files are not used for synchronization; accepted sync inputs are TTL pulse logs or camera frame counter logs (e.g., CSV/TSV with timestamps/levels).

3. Optional video transcoding

- Re-encode to a mezzanine format that guarantees frame-accurate seeking and uniform keyframe interval.
- Typical choice: MP4 (H.264), constant frame rate or per-frame timestamps retained externally, keyframe every N frames (e.g., 30 or 60).
- Skippable if raw files already work reliably downstream.

4. Pose and facial features

- DLC/SLEAP:
  - Prepare training/inference datasets (frame sampling lists) or import precomputed outputs.
  - Harmonize outputs to a canonical skeleton: consistent keypoint order, units (pixels), and per-frame timestamps aligned to the selected camera/timebase.
  - Manage multi-model, multi-run provenance; store confidence scores; optional smoothing/interpolation.
  - Model discovery: resolve model paths relative to `paths.models_root` (default: project `models/`) or accept absolute paths.
- Facemap:
  - Extract ROI-based facial signals with timestamps aligned to the timebase.
  - Save time series in standardized CSV/Parquet prior to NWB assembly.

5. NWB packaging

- Create NWBFile with subject/session metadata.
- Devices: five Cameras.
- Acquisition: ImageSeries per camera:
  - Use external_file references to original or mezzanine videos.
  - Provide per-frame timestamps derived from sync outputs.
- Sync TimeSeries: write TTL events or derived triggers.
- Pose (ndx-pose):
  - One PoseEstimation container per tool/model/run; PoseEstimationSeries per camera view if needed.
  - Store skeleton definition and provenance (config hash, model version).
- Facemap: BehavioralTimeSeries for each derived facial metric.
- Trials/behavioral events: If event logs are present (e.g., `*_trial_stats.ndjson` and per-sample `*_training.ndjson`), populate:
  - A TimeIntervals table ("trials") with trial-level fields from the stats NDJSON, and
  - BehavioralEvents or a ProcessingModule with event TimeSeries for per-sample entries from the training NDJSON.
- Save to output/session_id/session_id.nwb.

6. Validation and QC

- Run nwbinspector, save JSON report next to the NWB.
- Generate HTML QC report:
  - Sync integrity (drops, drift over time).
  - Pose keypoint confidence distributions and missing data.
  - Facemap traces preview and summary stats.
  - Per-camera video metadata and any anomalies.

Configuration model (TOML + Pydantic; strongly typed, modifiable)

- project: name, n_cameras=5, skeleton definition.
- paths: raw_root, intermediate_root, output_root, models_root (default: ./models).
- session: id, subject_id, date, experimenter, description, optional demographics.
- video: filename pattern; fps=null to infer; transcode block (enabled, codec, crf, preset, keyint).
- sync: TTL files, channel names/polarity, tolerances; primary_clock.
- labels: dlc/sleap (model paths, whether to run inference or import).
- facemap: run flag, ROI parameters (if any).
- nwb: session_description, link_external_video (true), file_name template.
- qc: report flag and output directory.
- logging: level.
- events: pattern(s) and format for event logs (e.g., `**/*_training.ndjson`, `**/*_trial_stats.ndjson`).

Orchestration

- CLI-first orchestration (e.g., Typer/Click) with subcommands:
  - ingest, sync, transcode, label-extract, infer, facemap, to-nwb, validate, report
- Each stage reads the session manifest and writes stage artifacts to intermediate/session_id/<stage>/.
- Idempotent design: re-running a stage overwrites or caches deterministically; supports --force to rebuild.

Repository layout and testing

- src/w2t_bkin: Source code for pipeline modules and the CLI entry points.
- tests/: Pytest-based unit and integration tests for pipeline components.
  - Include small synthetic fixtures under data/raw/testing to keep tests fast and deterministic.
- docs/: Project documentation (MkDocs), with site config `docs/mkdocs.yml` and content under `docs/docs/`.
- models/: Pretrained models and related metadata (default models_root).
- configs/: Example TOML configuration templates and Pydantic model references.
- scripts/: Utility scripts for maintenance and developer workflows.
- .github/workflows/: CI pipelines (lint, type-check, tests, docs build).

Testing strategy

- Use pytest with test files under tests/ named `test_*.py`.
- Cover core logic: ingestion discovery, sync math (TTL parsing, drift, drop detection), NWB writer mapping, and optional stages (pose/facemap).
- Prefer fast, deterministic tests using tiny synthetic datasets stored in repo under data/raw/testing.
- Validate CLI subcommands minimally (e.g., `--help` and dry-run paths) to ensure wiring remains intact.

Data layout (recommended)

- raw/<session_id>/cam{i}.mp4 (or lab-specific names via pattern)
- raw/<session_id>/sync_ttl.csv (or equivalent)
- raw/<session_id>/\*\_training.ndjson (per-sample behavioral events)
- raw/<session_id>/\*\_trial_stats.ndjson (trial-level summaries)
- models/{dlc|sleap}/... (pretrained model files, config, and metadata)
- intermediate/<session_id>/sync/ timestamps_cam{i}.csv, sync_summary.json
- intermediate/<session_id>/video/ transcoded files (if enabled)
- intermediate/<session_id>/labels/{dlc|sleap}/ harmonized outputs
- intermediate/<session_id>/facemap/ signals.csv or parquet + metadata.json
- intermediate/<session_id>/events/ normalized event tables and metadata.json (if applicable)
- output/<session_id>/<session_id>.nwb
- qc/<session_id>/index.html

NWB mapping details

- Devices: 5x Camera devices named camera_0..camera_4.
- Acquisition: ImageSeries camera_i_video with:
  - format: "external", external_file: [absolute or relative video path]
  - timestamps: per-frame array from sync stage
- Sync:
  - TimeSeries "camera_triggers" (for the raw TTL) with timestamps of edges used.
- Pose (ndx-pose):
  - PoseEstimation with attributes: software version, model hash, skeleton.
  - PoseEstimationSeries per camera or fused, with timestamps and confidence.
- Facemap:
  - ProcessingModule "facemap" with BehavioralTimeSeries for metrics (e.g., motion energy, pupil area).
- Provenance:
  - Store pipeline config snapshot and git commit in NWB file notes or a processing module.

Quality principles and best practices

- Deterministic processing; record configuration and versions.
- Prefer external video linking to avoid ballooning NWB size.
- Validate inputs early; emit actionable errors (missing camera file, TTL mismatch).
- Keep sync inputs and behavioral event logs clearly separated in the manifest; do not infer timestamps from event NDJSON.
- Harmonize skeletons and keep a registry with stable names/indices.
- Treat inference as optional; import existing outputs without forcing retraining.
- Keep rich logs and minimal plots for QC; avoid heavy inline images unless requested.

Security/ethics

- No PII; anonymize subject IDs as needed.
- Do not embed sensitive raw video into the NWB unless policy allows.

Glossary

- Transcoding: Re-encoding video to another codec/container or parameters (e.g., constant frame rate, keyframe interval) for reliable seeking, size reduction, or compatibility. Optional when source videos already behave well across tools.

Out of scope (per request)

- Camera calibration (intrinsic/extrinsic) is not performed.

Software stack and tools

- Core language/runtime
  - Python (3.10+): primary implementation language for all pipeline stages.
- Scientific/data processing
  - numpy: fast numeric operations for sync math and arrays.
  - pandas: tabular I/O (CSV/Parquet/NDJSON) and data wrangling for manifests, timestamps, pose/facemap tables.
- NWB ecosystem
  - pynwb: write the NWB file and containers (Devices, ImageSeries, TimeSeries).
  - ndx-pose: store pose estimation results with skeletons and confidence.
  - nwbinspector: validate NWB output for compliance; produce a JSON report.
- Video I/O and metadata
  - FFmpeg/ffprobe (system binaries): probe codecs/metadata; optional transcoding for reliable seeking.
  - ffmpeg-python: Pythonic wrapper to construct FFmpeg transcode/probe commands.
  - OpenCV (cv2): optional lightweight frame access/verification during QC or sampling.
- Configuration and validation
  - pydantic + pydantic-settings: typed config classes with validation, defaults, env var overrides.
  - tomllib (Python 3.11+) / tomli (Python 3.10): parse TOML config files for loading typed configuration.
- CLI, logging, orchestration
  - Typer: ergonomic CLI with subcommands (ingest, sync, transcode, to-nwb, etc.).
  - logging + rich: structured logs with readable console formatting.
- QC report generation
  - Jinja2: HTML templating for the QC report shell.
  - Plotly (offline) or Matplotlib/Seaborn: generate interactive or static charts (drift, confidence histograms, previews).
- Testing and code quality
  - pytest: unit/integration tests over synthetic datasets.
  - ruff: fast linting (style + simple correctness rules).
  - mypy: static type checks to harden interfaces and data contracts.
  - pre-commit: run ruff/mypy/formatting hooks locally and in CI.
- Documentation and CI
  - MkDocs (+ mkdocs-material): user/developer docs site.
  - GitHub Actions: CI for lint, type, tests, docs build, and nwbinspector checks.

Notes

- FFmpeg/ffprobe must be available on the system PATH for metadata probing and transcoding.
- Extras groups (e.g., pose, facemap, docs, dev) will be defined in pyproject to keep optional dependencies separate.
