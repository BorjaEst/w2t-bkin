---
post_title: Overview
author1: Project Team
post_slug: overview
microsoft_alias: borja
featured_image: /assets/cover.png
categories: [docs]
tags: [nwb, behavior, pipeline]
ai_note: partial
summary: Overview of the multi-camera behavior-to-NWB pipeline, scope, goals, and outputs.
post_date: 2025-11-06
---

## Scope and assumptions

- Five hardware-synchronized cameras (cam0–cam4); no camera calibration.
- Sync via TTL or frame counters to derive per-frame timestamps.
- Pose via DLC/SLEAP; facial metrics via Facemap.
- Outputs packaged into NWB with external video links; QC and validation included.

## Goals

- Config-driven, reproducible pipeline with clear artifacts and logs.
- Idempotent stages; scales from laptop to HPC.
- Minimal assumptions about lab-specific layout; configurable via YAML.

## Inputs and outputs

- Inputs: 5 videos, sync TTL/frame counters, optional pose/facemap, optional event logs (NDJSON).
- Outputs: NWB, QC HTML, nwbinspector report, and intermediate artifacts (timestamps, summaries).

## What is out of scope

- Camera calibration and multi-view fusion/triangulation are not performed.
- Raw videos are not embedded inside NWB by default (external linking is preferred).

## Source of truth

- See `requirements.md`, `design.md`, and `tasks.md` in the repo root for the canonical specification.
