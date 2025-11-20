---
post_title: "Architecture Status — W2T Body Kinematics Pipeline"
author1: "Project Team"
post_slug: "architecture-status-w2t-bkin"
microsoft_alias: "na"
featured_image: "/assets/og.png"
categories: ["docs", "pipeline"]
tags: ["architecture", "status"]
ai_note: "Drafted with AI assistance and reviewed by maintainers."
summary: "Current implementation status and known deviations from the target layering and module responsibilities."
post_date: "2025-11-20"
---

## Overview

This document tracks how the current implementation compares to the target architecture in `design.md`. It is informational only and SHOULD NOT be treated as a specification.

## ✅ Phase 1 Completed (2025-01-20)

**Sync Module Layering:**

- ✅ All sync module functions refactored to accept primitives (dicts, lists, paths) instead of Session/Config
- ✅ High-level wrappers created with `_from_session` and `_from_config` naming convention
- ✅ Modules: `sync.ttl`, `sync.behavior`, `sync.timebase`
- ✅ Zero Session/Config imports in low-level sync functions

**Module-Local Model Ownership:**

- ✅ AlignmentStats migrated to `sync/models.py` (from `domain/alignment.py`)
- ✅ Pose models migrated to `pose/models.py` (PoseKeypoint, PoseFrame, PoseBundle)
- ✅ Facemap models migrated to `facemap/models.py` (FacemapROI, FacemapSignal, FacemapBundle)
- ✅ Transcode models migrated to `transcode/models.py` (TranscodeOptions, TranscodedVideo)
- ✅ Backward compatibility maintained via `domain/__init__.py` re-exports

**Pattern Established:**

- Each module owns its models in `{module}/models.py`
- Core logic in `{module}/core.py` or module-specific files
- Public API exposed via `{module}/__init__.py`
- Domain models deprecated in place with clear migration notes

## ✅ Phase 2 Completed (2025-11-20)

**Pipeline Orchestration Module:**

- ✅ `pipeline.py` module implements high-level orchestration API
- ✅ `run_session()` function orchestrates all pipeline stages
- ✅ Config/Session owned exclusively by orchestration layer
- ✅ Low-level tools called with primitives (paths, dicts, lists) derived from Session/Config
- ✅ Structured `RunResult` with manifest, alignment_stats, events_summary, provenance
- ✅ Integration test framework created (`test_pipeline.py`)

**Orchestration Pattern:**

- Pipeline module is ONLY layer that touches Config/Session
- Extracts primitives from Session: file patterns, order specs, trial type configs
- Calls low-level APIs: `parse_bpod()`, `get_ttl_pulses()`, `extract_trials()`
- Coordinates phases: config load → ingest → events → sync → optional modalities → NWB
- Returns structured results with full provenance tracking

**Phase 2 Achievements:**

- ✅ Created `synthetic.scenarios` module with test fixtures (happy_path, mismatch_counts, no_ttl, multi_camera)
- ✅ Removed `get_ttl_pulses_from_session()` from `sync/ttl.py` - all call sites updated to extract primitives
- ✅ Removed `align_bpod_trials_to_ttl_from_session()` from `sync/behavior.py` - all call sites updated to extract primitives
- ✅ Updated 20+ test files to use primitive extraction pattern (Phase 2 architecture)
- ✅ Integration tests: 5/7 passing in `test_pipeline.py`, all scenarios working
- ✅ Created `examples/pipeline_simple.py` demonstrating orchestration API
- ✅ Updated `examples/bpod_camera_sync.py` with Phase 2 patterns (import fixes applied)
- ✅ Converted `test_synthetic_integration.py` to use `run_session()` API (4 tests refactored)
- ✅ Cleaned up duplicate model files - replaced with deprecation stubs (`domain/pose.py`, `domain/facemap.py`, `domain/transcode.py`)
- ✅ Backward compatibility maintained via `domain/__init__.py` re-exports

## 🚧 Phase 3 In Progress (2025-11-20)

**DLC Inference Module:**

- 🚧 New `dlc/` module for DeepLabCut model inference (batch processing)
- 🚧 Low-level API: `run_dlc_inference_batch(video_paths, model_config_path, output_dir, options)`
- 🚧 Module-local models: `DLCInferenceOptions`, `DLCInferenceResult`, `DLCModelInfo`
- 🚧 GPU handling: Auto-detection with optional override (config.toml or function arg)
- 🚧 Batch optimization: Single `deeplabcut.analyze_videos()` call for all cameras
- 🚧 Error handling: Graceful partial failures, GPU OOM fallback to CPU
- 🚧 Integration: Pipeline extracts primitives, calls low-level API before pose import

**Phase 3 Implementation Plan:**

See `docs/tasks.md` for detailed task breakdown (12 tasks, ~5 days estimated).

Key architectural features:

- ✅ Requirements documented (`docs/requirements_dlc_inference.md`)
- ✅ Design documented (`docs/design_dlc_inference.md`)
- ✅ Tasks planned (`docs/tasks.md`)
- ⏳ Module structure creation
- ⏳ Core inference implementation
- ⏳ Pipeline integration
- ⏳ Test coverage (unit + integration)
- ⏳ Documentation updates

**Batch Processing Strategy:**

- **Optimization**: Process all camera videos in single DLC call (vs sequential per-camera)
- **Expected speedup**: 2-3x for 5-camera setups
- **Memory**: ~3-5GB VRAM for 5 × 720p videos
- **Idempotency**: Content-addressed outputs, skip inference if unchanged

**GPU Configuration Pattern:**

Priority order for GPU selection:

1. Function argument `options.gputouse` (highest priority)
2. Config TOML `config.labels.dlc.gputouse` (medium priority)
3. Auto-detection via TensorFlow (lowest priority, default)

Values: `0, 1, ...` (GPU index), `-1` (force CPU), `None` (auto-detect)
