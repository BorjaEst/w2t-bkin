---
post_title: NWB Mapping
author1: Project Team
post_slug: nwb-mapping
microsoft_alias: borja
featured_image: /assets/cover.png
categories: [nwb]
tags: [nwb]
ai_note: partial
summary: How cameras, sync, pose, and facial metrics are represented in NWB.
post_date: 2025-11-06
---

## Devices and videos

- Five Camera devices; one ImageSeries per camera with `external_file` and per-frame timestamps.

## Sync

- TimeSeries for raw TTL or triggers used to derive timestamps.

## Pose (ndx-pose)

- PoseEstimation container with software version, model hash, and skeleton.
- PoseEstimationSeries per camera or fused view with timestamps and confidence.

## Facemap

- ProcessingModule "facemap" with BehavioralTimeSeries for each metric.

## Provenance

- Embed config snapshot and software versions into the NWB file.
