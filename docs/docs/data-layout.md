---
post_title: Data Layout
author1: Project Team
post_slug: data-layout
microsoft_alias: borja
featured_image: /assets/cover.png
categories: [data]
tags: [data]
ai_note: partial
summary: Recommended directory structure for raw data, intermediates, outputs, and models.
post_date: 2025-11-06
---

## Structure

- `raw/<session_id>/cam{i}.mp4` and `sync_ttl.csv` (or lab-specific names via pattern).
- `raw/<session_id>/*_training.ndjson` and `*_trial_stats.ndjson` (optional).
- `intermediate/<session_id>/{sync,video,labels,facemap,events}/`.
- `output/<session_id>/<session_id>.nwb` and `qc/<session_id>/index.html`.
- `models/{dlc|sleap}/...` for pretrained models.
