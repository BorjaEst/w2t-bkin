---
post_title: "Tasks — W2T Body Kinematics Pipeline"
author1: "Project Team"
post_slug: "tasks-w2t-bkin"
microsoft_alias: "na"
featured_image: "/assets/og.png"
categories: ["docs", "pipeline"]
tags: ["tasks", "refactor"]
ai_note: "Drafted with AI assistance and reviewed by maintainers."
summary: "Implementation tasks for refactoring toward session-free tools and a layered architecture."
post_date: "2025-11-20"
---

### Refactor: Session-Free Tools and Layered Architecture

### Phase 1 – Unit-Level Refactor (tools APIs)

1. Events/Bpod low-level APIs

   - Introduce functions in `events.bpod` that accept raw Bpod `.mat` file paths and primitive options instead of `Session` or `Manifest`, for example:
     - `load_bpod_files(paths: list[str], order: str = "name_asc")`
     - `parse_bpod_trials(raw_bpod, trial_type_specs)`
   - Ensure these functions operate purely on file paths, parsed MATLAB structures, and simple arguments such as `order`, `continuous_time`, and trial-type mappings.
   - Mark any `Session`-accepting helpers as internal or scheduled for removal once integration tests are updated.
   - Update `tests/unit/test_events.py` to construct inputs from fixture file paths and explicit arguments, not from `Session`.

2. Pose/facemap/transcode APIs

   - Confirm that `pose`, `facemap`, and `transcode` public APIs only accept file paths, ROI specs, and primitive options.
   - Where necessary, add arguments that correspond to fields currently read from `Session` (e.g., file ordering) so high-level orchestration can pass them explicitly.
   - Update unit tests (`tests/unit/test_pose.py`, `tests/unit/test_facemap.py`, `tests/unit/test_transcode.py`) to use these explicit arguments.

3. Sync/NWB contracts
   - Verify that `sync` and `nwb` do not accept `Session` or TOML structures.
   - Ensure that alignment stats and other mid-level models are owned by `sync` and `nwb` modules rather than a shared `domain` package.
   - Where `Manifest` is currently required, consider offering overloads that take primitive metadata or modality-specific module-local models directly, keeping `Manifest` as an orchestration convenience only.

### Phase 2 – Integration-Level Refactor (orchestration)

1. High-level pipeline/orchestration module

   - Introduce a `pipeline` or `cli` module responsible for end-to-end orchestration:
     - Load `Config` and `Session` via `config`.
     - Use `Session` to derive file paths, glob patterns, and options per modality.
     - Call low-level tools (events, pose, facemap, transcode) with raw file paths and primitive arguments.
     - Call `sync` to create a timebase and align modalities.
     - Call `nwb` to assemble the NWB file, then `validate` and `qc`.

2. Update integration tests

   - Adapt tests under `tests/integration/` to use the orchestration layer instead of calling low-level tools with `Session`:
     - `test_phase_0_foundation.py` remains focused on config/session loading.
     - `test_phase_1_ingest.py` and `test_phase_2_sync.py` should go through the new pipeline/orchestration APIs.
     - `test_phase_3_optionals.py` should exercise events/pose/facemap via orchestration, not by constructing `Session` for low-level calls.
     - `test_phase_4_nwb.py` and `test_synthetic_integration.py` should validate the full pipeline via high-level entry points.

3. Decommission legacy Session-coupled helpers
   - Once integration tests are using the new orchestration APIs, remove or internalize any remaining helpers in low-level modules that accept `Session` or `Manifest` directly.
