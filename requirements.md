# Fundamental Requirements (Editable)

Functional requirements (FR)

- FR-1: The pipeline shall ingest 5 camera video files for a session and discover associated sync files.
- FR-2: The pipeline shall compute per-frame timestamps for each camera using hardware sync signals (TTL/frame counters).
- FR-3: The pipeline shall detect and report dropped or duplicate frames and any inter-camera drift.
- FR-4: The pipeline shall optionally transcode videos to a mezzanine format; when disabled, the pipeline shall operate directly on raw videos.
- FR-5: The pipeline shall import pose estimation results from DeepLabCut and/or SLEAP and harmonize them to a canonical skeleton and timebase.
- FR-6: The pipeline shall import or compute Facemap-derived facial metrics and align them to the session timebase.
- FR-7: The pipeline shall export a single NWB file per session including:
  - Devices for 5 cameras
  - Per-camera ImageSeries linking external video files and per-frame timestamps
  - Sync TimeSeries (e.g., TTL edges)
  - ndx-pose containers for each model/run of pose data
  - BehavioralTimeSeries for Facemap signals
- FR-8: The pipeline shall generate a QC HTML report summarizing sync integrity, pose confidence, and Facemap metrics.
- FR-9: The pipeline shall validate the NWB with nwbinspector and save the report.
- FR-10: The pipeline shall be driven by a YAML configuration and a CLI with subcommands (ingest, sync, transcode, label-extract, infer, facemap, to-nwb, validate, report).

Optional functional requirements (OFR)

- OFR-1: The pipeline may import session event logs (e.g., NDJSON files describing trials or per-sample events) into the NWB file as a Trials table and/or BehavioralEvents. These files are not used for video synchronization.

Explicit non-requirements / out of scope

- OOS-1: Camera calibration (intrinsic/extrinsic) shall not be performed by the pipeline.
- OOS-2: Optical tracking fusion or triangulation across cameras is not included.
- OOS-3: Embedding raw videos inside the NWB (default is external linking).

Non-functional requirements (NFR)

- NFR-1: Reproducibility: Given the same inputs and config, outputs shall be bitwise-identical where feasible (excluding timestamps and file paths embedded by external tools).
- NFR-2: Idempotence: Re-running a stage without input changes shall not alter artifacts (unless forced).
- NFR-3: Observability: The pipeline shall produce structured logs and summary JSON for each stage (e.g., sync_summary.json).
- NFR-4: Performance: The pipeline shall process a typical 1-hour session of 5x 1080p videos within practical lab time budgets; heavy steps (transcode, inference) shall support parallelization.
- NFR-5: Portability: The pipeline shall run on Linux and macOS; Windows support is best-effort.
- NFR-6: Compatibility: Outputs shall be readable by pynwb and pass nwbinspector with no critical errors.
- NFR-7: Modularity: Pose/Facemap stages shall be optional; the pipeline shall import precomputed results without requiring inference.
- NFR-8: Data integrity: The pipeline shall verify input file existence and optionally record checksums.
- NFR-9: Privacy: The pipeline shall avoid storing PII and support anonymized subject IDs.
- NFR-10: Configurability: All file patterns, paths, and toggles (e.g., transcode enabled) shall be configurable via YAML.
- NFR-11: Provenance: The pipeline shall embed configuration and software versions into the NWB or sidecar metadata.
- NFR-12: Testability and CI: The repository shall organize tests under `tests/` using pytest, include a minimal synthetic dataset for fast runs, and support CI jobs that run linting, type checks, and tests.
  Repository conventions
- Code lives under `src/` (importable package `w2t_bkin`), tests under `tests/` (pytest), documentation under `docs/` (MkDocs).
- Pretrained models are kept under `models/` by default and can be overridden via `paths.models_root`.

Configuration keys (reference skeleton)

- project: { name, n_cameras }
- paths: { raw_root, intermediate_root, output_root, models_root }
- session: { id, subject_id, date, experimenter, description, sex, age, genotype }
- video: { pattern, fps, transcode: { enabled, codec, crf, preset, keyint } }
- sync: { ttl_channels: [ { path, name, polarity } ], tolerance_ms, drop_frame_max_gap_ms, primary_clock }
- labels: { dlc: { model, run_inference }, sleap: { model, run_inference } }
- facemap: { run, roi }
- nwb: { link_external_video, file_name, session_description, lab, institution }
- qc: { generate_report, out }
- logging: { level }
- events: { patterns: ["**/*_training.ndjson", "**/*_trial_stats.ndjson"], format: "ndjson" }

CLI commands (contract)

- ingest: Build session manifest from config; fail if expected files are missing.
- sync: Produce per-camera timestamps and summary stats; non-zero exit on severe mismatches.
- transcode: If enabled, transcode videos; otherwise no-op with clear log.
- label-extract / infer: Prepare datasets or run inference; or import existing results.
- facemap: Run or import facial metrics.
- to-nwb: Assemble NWB with all available data; warn if optional data missing.
- validate: Run nwbinspector and save report.
- report: Generate QC HTML summary.
- Note: If events are configured, `ingest` should discover them and include absolute paths in the manifest; `to-nwb` should add Trials/BehavioralEvents from these logs.

Acceptance criteria (summary)

- A1: For a sample session, running ingest → sync → to-nwb → validate → report completes without errors, producing an NWB with external video links, valid timestamps, pose (if provided), and Facemap (if provided).
- A2: nwbinspector report contains no critical issues.
- A3: QC report includes sync drift plot and pose confidence histogram when pose is present.

Notes for adaptation

- If only a subset of cameras is present, allow n_cameras override per session.
- If no TTL is available, allow fallback to container timestamps (with clear warnings).
- If pose is multi-animal, extend skeleton and container mapping accordingly.
- If event NDJSON files are present, treat them as behavioral metadata only; do not use them as sync inputs.
- By default, models are stored under the repository `models/` directory; set `paths.models_root` to override or use absolute model paths in `labels.*.model`.
