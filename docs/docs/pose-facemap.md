---
post_title: Pose and Facemap
author1: Project Team
post_slug: pose-facemap
microsoft_alias: borja
featured_image: /assets/cover.png
categories: [pose, facemap]
tags: [pose, facemap]
ai_note: partial
summary: DLC/SLEAP import and harmonization, Facemap extraction, and alignment to timebase.
post_date: 2025-11-06
---

## Pose (DLC/SLEAP)

- Import outputs; harmonize to canonical skeleton and keypoint order.
- Preserve confidence scores; optional smoothing or interpolation.
- Align timestamps to the session timebase selected during sync.

## Facemap

- Extract ROI-based metrics; standardize columns and metadata.
- Align to the timebase; export as CSV/Parquet prior to NWB.
