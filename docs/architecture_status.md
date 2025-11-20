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

## Known Deviations

- `events.bpod` now exposes a Session-free low-level entrypoint (`parse_bpod(session_dir, pattern, order, continuous_time)`), but some high-level helpers elsewhere in the codebase may still call Bpod logic with `Session` rather than primitives. Those call sites SHOULD be migrated to compute `session_dir`, `pattern`, and `order` from `Session` and then delegate to `parse_bpod`.
- Many models (e.g., trials, pose bundles, facemap bundles, alignment stats) are still defined in a shared `domain` package rather than being owned by their respective tool modules. The target design expects each module to define and expose its own models.
- Some ingest and events helpers expose legacy dict-based shapes rather than the module-local models described in the design. These helpers remain for compatibility but are not part of the target contracts.
- High-level orchestration/CLI is currently expressed primarily through tests and examples rather than a dedicated `pipeline` or `cli` module. The design assumes a dedicated orchestration layer that owns `Session` and wires low- and mid-level tools.

## Migration Notes

- Low-level APIs SHOULD grow raw-file based entry points (e.g., `load_bpod_files(paths: list[str], order: str = "name_asc")`) while legacy `Session`-aware helpers are either removed or relegated to high-level orchestration.
- Integration tests SHOULD gradually move to exercise a high-level pipeline/orchestration API instead of calling low-level tools with `Session`.
