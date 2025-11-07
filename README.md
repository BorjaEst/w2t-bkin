# W2T Body Kinematics — Daily log

This README doubles as a lightweight daily lab notebook for the project. Keep entries short and useful, and link to scripts, notebooks, and data when relevant.

## Base information (editable)

- Objective: design a pipeline to process rodent behavior video data.
- Recording setup:
  - 5 cameras capturing from different angles.
  - Cameras labeled as videos 1–5; video 1 is the top–bottom view.
  - Mouse whiskers are colored to simplify labeling.
  - Trials are separated using a flashlight cue.
  - Only video 1 contains the flashlight signal that separates trials.
- Trial segmentation (current approach):
  - Use DLC-derived features plus image-based k-means clustering on video 1 to auto-detect trial frames.
  - Export a per-frame boolean/int flags array delimiting trial boundaries for the session.
- Tracking strategy (current):
  - Use DeepLabCut (DLC) to track whisker movements from the top–bottom camera (video 1).
  - Use facemap for the other 4 cameras (evaluate SLEAP as an alternative).
- Data standard: NWB for pipeline outputs.

## Current plan (editable)

- [ ] Pre-processing: trim long videos using the same software across all cameras/datasets prior to labeling/training to avoid trimming-induced bias.
- [ ] Standardize output format to NWB for all pipeline files.
- [ ] Trial segmentation automation on video 1 using DLC features + k-means; export trial boundary flags.
- [ ] Tracking: DLC on video 1; facemap on other 4 (evaluate SLEAP alternative).
- [ ] Outline initial contributor docs and project README in `docs/`.

## How to use

- Keep "Base information" and "Current plan" at the top up to date as the project evolves.
- Add one daily note per day under an H2 heading.
- Heading format: `## YYYY-MM-DD – <short title>`.
- Daily notes are concise bullets about what happened; link to assets instead of pasting long outputs (e.g., `notebooks/`, `data/`, `reports/`).

### New entry template

<details>
<summary>Click to copy the template</summary>

```markdown
## YYYY-MM-DD – <short title>

- Note 1 (steps taken, parameters, commands, links)
- Note 2 (observations, metrics, artifacts paths/links)
```

</details>

## Beginner Guide (merged)

You record a mouse with 5 hardware-synchronized cameras. You want: (a) the true time each frame happened, (b) derived signals (pose keypoints, facial metrics), (c) behavioral events/trials, all aligned to one timeline, then stored in a standard neuroscience format (NWB) with a quality report. The pipeline automates that transformation.

## 1. Big Picture

You record a mouse with 5 hardware-synchronized cameras. You want: (a) the true time each frame happened, (b) derived signals (pose keypoints, facial metrics), (c) behavioral events/trials, all aligned to one timeline, then stored in a standard neuroscience format (NWB) with a quality report. The pipeline automates that transformation.

## 2. Core Data Types (What They Are & Why We Need Them)

### 2.1 Camera Videos

Five separate video files (cam0–cam4) capturing different viewpoints (body, face, whiskers, etc.). They provide pixels; they do not inherently guarantee perfect timing.

### 2.2 Sync Logs (TTL / Frame Counters)

Sync logs are text/CSV/TSV files recorded by acquisition hardware. They contain timing signals used to reconstruct exact frame times.

#### TTL (Transistor-Transistor Logic) Pulses

Think of TTL as a sharp square pulse (0 → 1 → 0). Each rising edge marks a precise event (e.g., camera exposure). Listing these edges gives you an absolute list of timestamps. Using them, you map frame indices to real times. This reveals drops (missing pulses), duplicates (extra pulses), and drift (slow divergence among cameras).

#### Frame Counters

Some systems log an incrementing counter per captured frame with a timestamp column. Similar goal: reconstruct a timestamp per frame.

Why not rely on video FPS alone? Nominal FPS assumes perfect regular spacing. Real hardware can jitter or drop frames. Relying only on FPS hides timing errors and shifts alignment with behavioral or neural signals.

### 2.3 NDJSON Behavioral Logs

NDJSON (Newline-Delimited JSON): Each line is a standalone JSON object. Example fields you have: t, phase, trial, valid, marker positions.

You typically have two kinds:

- Per-sample or per-event lines ("training" NDJSON) — fine-grained instantaneous states.
- Trial summary lines ("trial_stats" NDJSON) — metadata per trial (durations, outcomes, counts).

Why needed? They add semantic meaning (context, trial structure) to raw sensor data. They do not replace TTL for synchronization.

### 2.4 Pose Data (DLC / SLEAP)

Pose estimation predicts 2D coordinates of anatomical keypoints (e.g., nose, tail base, ears) per frame. Tools like DeepLabCut (DLC) or SLEAP produce files with keypoint positions and confidence scores.

Why needed? Converts pixels to structured movement features enabling kinematic analysis, classification, and linking behavior to neural data.

### 2.5 Facemap Signals

Facemap extracts facial metrics such as motion energy, pupil size, whisker pad movement from a face-view video.

Why needed? These continuous signals capture internal states (arousal, attention) and fine motor patterns beyond gross body pose.

### 2.6 NWB File

NWB (Neurodata Without Borders) is a standardized container + schema for neuroscience data. It organizes metadata, time series, imaging, behavioral events, derived features, all with consistent time alignment and provenance.

Why needed? Interoperability, reproducibility, long-term archival, and tool ecosystem support (pynwb, validation, viewers).

### 2.7 QC Report

Quality Control (QC) HTML summarizes data integrity: frame drops, drift curves, pose confidence distributions, examples of facial signals, video metadata anomalies. It gives an immediate health check before deeper science.

### 2.8 Out-of-Scope Elements

- Camera calibration (intrinsic/extrinsic) — not required for per-frame timestamps or 2D keypoints.
- Multi-camera 3D triangulation/fusion — significantly more complexity; pipeline focuses on synchronized 2D.
- Embedding raw video inside NWB — external links reduce file size and improve access speed.

## 3. Data Flow Overview

Text diagram:

```
Raw Videos (cam0..cam4)   ─┐
                  ├─ Ingestion ─► manifest.yaml (absolute paths, metadata)
Sync Logs (TTL / counters) ┘
manifest.yaml + sync logs ─► Synchronization ─► timestamps_cam{i}.csv + sync_summary.json
Videos (+ optional transcode) ─► (optional mezzanine files)
Pose raw (DLC/SLEAP) ─┐
Facemap raw           ├─ Harmonization ─► pose_harmonized.* + facemap_metrics.*
Behavior NDJSON       ┘
All stage outputs ─► NWB packaging ─► session_id.nwb
session_id.nwb ─► Validation (nwbinspector.json)
All diagnostics ─► QC report (index.html)
```

## 4. Synchronization Deep Dive

### 4.1 Goal

Produce a trustworthy timestamp for every frame of each camera expressed in one session timebase (choose a primary clock, typically cam0).

### 4.2 Steps

1. Parse TTL or counter log: extract edge timestamps or frame timestamp rows.
2. Associate each frame index (from video decoding or counter value) with nearest valid pulse.
3. Detect anomalies:

- Dropped frame: expected pulse missing → gap larger than tolerance.
- Duplicate frame: multiple pulses for same frame index or identical timestamps within minimum interval.
- Drift: difference in cumulative time between cameras over session.

4. Emit `timestamps_cam{i}.csv` (one timestamp per frame) and `sync_summary.json` (counts, drift stats).

### 4.3 Timestamps vs Rate

Use explicit per-frame timestamps instead of `starting_time + rate` unless you have proven perfect regularity. This preserves jitter, enables re-validation, and prevents hidden alignment errors.

## 5. Pose Harmonization

### 5.1 Input Variability

Different tools label keypoints differently (names, order, confidence fields, missing data markers).

### 5.2 Harmonization Actions

- Map keypoint order to a canonical skeleton list.
- Standardize columns (x, y, confidence) and units (pixels).
- Align all pose rows to the unified session timebase (using synchronized frame timestamps).
- Preserve missing frames as gaps (do not fabricate). Optional smoothing flagged in metadata.

### 5.3 Interpolation Policy

Do not interpolate during synchronization. Only interpolate later for analysis grids, with:

- Gap-aware methods (limit max gap fill).
- Flags to mark synthetic values.

## 6. Facemap Processing

### 6.1 Extraction

Compute facial ROI metrics frame-by-frame (or block-wise). Each metric becomes a continuous time series.

### 6.2 Alignment

Map each metric sample to the session timebase using the face camera timestamps.

### 6.3 Output

Tabular (CSV/Parquet) with columns: `time`, `metric_name(s)` (+ metadata JSON). Later inserted as BehavioralTimeSeries in NWB.

## 7. Behavioral Events & Trials (NDJSON Mapping)

### 7.1 Event Records

Each line with `t`, `phase`, `trial`, `valid`, etc. → Event TimeSeries (timestamps = `t`, data columns for phase/trial). This keeps fine temporal granularity.

### 7.2 Trials Table (TimeIntervals "trials")

Represents segments of purposeful behavioral structure.

#### 7.2.1 Challenge

No explicit start/end markers; trial_stats may only have duration. Need a derivation algorithm.

#### 7.2.2 Hybrid Derivation (Option H)

For each trial ID k:

1. Collect all events where `trial == k`. If none: mark missing, skip or create flagged minimal row.
2. `event_start_k = min(t)`; `event_end_k = max(t)`.
3. Estimate median inter-event delta `Δt_med_k` (fallback to global median).
4. `observational_stop_k = event_end_k + Δt_med_k / 2` (avoid zero-width).
5. If trial_stats provides duration_k:

- `stats_stop_k = event_start_k + duration_k`.
- If |stats_stop_k − observational_stop_k| ≤ tolerance (e.g., max(1 frame period, 2\*Δt_med_k)): use `stats_stop_k`.
- Else keep `observational_stop_k` and flag mismatch.

6. Enforce non-overlap with previous trial; adjust start/flag if needed.
7. Record QC columns: `observed_span`, `declared_duration`, `duration_delta`, `qc_flags`.

#### 7.2.3 Tolerance Choice

Default tolerance = max( one frame period, 2 \* median Δt ). This prevents tiny timing noise from triggering false mismatches.

### 7.3 Why Keep Both Events & Trials

- Trials: coarse segmentation for summary stats.
- Events: precise moment-by-moment state changes used for alignment with pose/facial signals.

## 8. NWB Structure (What Goes Where)

| Component         | NWB Entity                                             | Contents                                                 |
| ----------------- | ------------------------------------------------------ | -------------------------------------------------------- |
| Cameras           | `Device` objects                                       | Metadata (name, description)                             |
| Video streams     | `ImageSeries` (external_file)                          | Per-frame timestamps + file reference                    |
| Sync pulses       | `TimeSeries` (e.g., camera_triggers)                   | TTL edge timestamps + signal values                      |
| Pose              | `PoseEstimation` + `PoseEstimationSeries` (ndx-pose)   | Keypoints, confidence, skeleton definition, timestamps   |
| Facemap metrics   | `ProcessingModule` (behavior) + `BehavioralTimeSeries` | Continuous facial signals                                |
| Behavioral events | `TimeSeries` or `BehavioralEvents` container           | Event timestamps + labels                                |
| Trials            | `TimeIntervals` named "trials"                         | start_time, stop_time, columns (phase, flags, durations) |
| Provenance        | NWBFile fields / notes / processing module             | Config snapshot, software versions, git commit           |
| QC outputs        | Stored outside NWB (HTML + JSON)                       | Cross-stage integrity summary                            |

## 9. Quality Control (QC)

### 9.1 Goals

Rapidly detect mis-synchronization, data loss, misalignment, model failures.

### 9.2 Typical Panels

- Drift plot (time difference between cameras vs session time).
- Frame drop histogram and duplicate count.
- Pose confidence distribution + missing keypoint rate.
- Facemap metric previews (pupil, motion energy).
- Trial duration mismatch summary (observed vs declared).
- Version/provenance table.

### 9.3 Interpretation

Green panels = high integrity. Mismatch flags require inspection before downstream analysis.

## 10. Transcoding (Optional)

### 10.1 Purpose

Normalize video for predictable seeking (constant keyframe interval, stable container), reduce size, avoid decoder edge cases.

### 10.2 When to Skip

Raw files already seek reliably and analysis tools handle them without sync anomalies.

### 10.3 Effects on Timestamps

Transcoding should not regenerate timing; keep original synchronized timestamps. Validate that frame count matches expectation.

## 11. Timestamp Integrity & Analysis

### 11.1 Original vs Resampled

Store original empirical timestamps (truth). Any later regular grid (resampled) should carry metadata referencing the original source and method.

### 11.2 Analytical Risks of Assuming Fixed Rate

- Silent drift → misaligned pose vs events.
- Hidden drops → false movement pauses or artifacts.
- Incorrect derivatives (velocity/acceleration) due to wrong Δt.

## 12. Common Pitfalls & Mitigations

| Pitfall                               | Consequence                  | Mitigation                                              |
| ------------------------------------- | ---------------------------- | ------------------------------------------------------- |
| Using nominal FPS only                | Misaligned multimodal data   | Use TTL/frame counters + explicit timestamps            |
| Interpolating missing frames early    | Artificial motion continuity | Defer interpolation, keep gaps flagged                  |
| Assuming trial_stats duration blindly | Trial window distortion      | Hybrid interval derivation + QC flags                   |
| Mixing timebases (NDJSON vs video)    | Event-frame misalignment     | Normalize NDJSON times to primary clock (offset/scale)  |
| Dropping confidence scores            | Loss of uncertainty info     | Preserve confidence; mark smoothed/interpolated samples |
| Embedding huge videos in NWB          | Oversized NWB, slow IO       | Use external_file references                            |

## 13. Minimal Provenance Checklist

- Config YAML snapshot.
- Software/package versions (pip freeze subset).
- Git commit hash.
- Sync summary stats (drift, drops, duplicates).
- Skeleton definition & model hashes (pose).
- QC version and generation timestamp.

## 14. Glossary (Quick Reference)

| Term                   | Meaning                                                      |
| ---------------------- | ------------------------------------------------------------ |
| TTL                    | Hardware pulse marking precise event times.                  |
| Drift                  | Gradual divergence in timing between sources.                |
| NDJSON                 | Text file: one JSON object per line.                         |
| Pose                   | 2D keypoint positions (body landmarks) per frame.            |
| Facemap                | Facial signal extraction (pupil, motion energy).             |
| ImageSeries            | NWB object referencing video frames (can use external_file). |
| TimeIntervals / trials | Table of start/stop times + metadata for trials.             |
| BehavioralEvents       | Time-stamped behavioral event series in NWB.                 |
| QC                     | Quality Control summary of data integrity.                   |
| Harmonization          | Standardizing pose outputs to a canonical skeleton/timebase. |

## 15. Decision Rationale (Why These Design Choices)

- External video linking: Keeps NWB lean; large binary video storage belongs outside for performance.
- Explicit timestamps: Preserve empirical truth; enables verification and re-synchronization checks.
- Hybrid trial interval derivation: Balances observed data and declared durations, surfaces mismatches instead of masking them.
- Separate events vs trials: Supports both fine-grained behavior reconstruction and coarse segmentation.
- Optional transcoding: Avoid unnecessary processing; only apply for seeking stability or size constraints.
- Idempotent stages: Re-runs are predictable; aids reproducibility and debugging.

## 16. Quick Mental Model Recap

1. Find all inputs (videos, sync, optional pose/facemap/events) → manifest.
2. Convert hardware signals to per-frame timestamps (truth timeline).
3. (Optional) Transcode videos for convenience (timing untouched).
4. Harmonize pose + facial signals to session timebase.
5. Build NWB with structured devices, series, intervals, events, provenance.
6. Validate (nwbinspector) and summarize integrity (QC HTML).
7. Use flags and mismatch metrics to guide downstream trust decisions.

## 17. Next Steps for a New User

1. Inspect a sync log (TTL CSV) and identify a pulse pattern.
2. Visualize timestamps_cam0.csv spacing (should be near frame period with small jitter).
3. Load a pose file and map columns to canonical skeleton names.
4. Derive a trials table using Hybrid Option H and count mismatch flags.
5. Open NWB (pynwb) and list acquisition keys to confirm ImageSeries.
6. Review QC report before any analysis.

## 18. Validation Checklist Before Trusting Data

- Drift < predefined threshold (e.g., < 5 ms over session).
- Drop/duplicate counts acceptable (document thresholds).
- Pose confidence median within expected range per keypoint.
- Trial duration mismatches minimal (flag summary small).
- nwbinspector reports no critical issues.

If any fail → revisit synchronization or source logs before analysis.

## 19. Summary Sentence

This pipeline turns raw multi-view behavioral recordings plus timing and event logs into a fully synchronized, provenance-rich NWB dataset with explicit timestamps, standardized behavioral segmentation, and transparent quality diagnostics—while deliberately avoiding higher-complexity 3D reconstruction or calibration tasks.

---

## 2025-11-04 – Rotation kickoff

- Documented base recording setup and initial segmentation/tracking approach (see top sections).
- Confirmed cameras monitor pupils, whiskers, and face of the mouse.

## 2025-11-06 – Defining the project skeleton

- Repository scaffolded based on Cookiecutter Data Science (with changes). GitHub project: `w2t-bkin`.
- Licensing initialized for open science reuse: added `LICENSE` (Apache-2.0).

## 2025-11-07 – Project ideation

- Created first draft for documentation.
- training.ndjson: contains session information at each timepoint (t, phase, trial, valid, marker positions). (Missing start/end times for each trial.)
- trial_stats.ndjson: contains summary statistics for each trial (duration, outcome, counts).
- We need TTL or frame counters for synchronization (because relying on nominal FPS is risky).
