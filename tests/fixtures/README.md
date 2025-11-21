---
post_title: "Test Fixtures"
author1: "Project Team"
post_slug: "fixtures-readme"
microsoft_alias: "na"
featured_image: "/assets/og.png"
categories: ["testing", "docs"]
tags: ["fixtures", "testing"]
ai_note: "Generated as placeholder for test fixtures directory."
summary: "Directory for small synthetic data used in unit/integration tests."
post_date: "2025-11-08"
---

<!-- markdownlint-disable MD041 -->

## Guidelines

- Keep data tiny and synthetic; avoid real recordings.
- Prefer programmatically generated content in tests; store only when necessary.
- Use subfolders per module if helpful (e.g., sync/, pose/).

## Available Fixtures

### Configs (`configs/`)

- `valid_config.toml` - Complete valid config for positive tests
- `missing_paths.toml` - Config missing required paths section (A13)
- `config_with_extra_key.toml` - Config with forbidden extra key (A13)
- `config_ttl_missing_ttl_id.toml` - TTL source without required ttl_id (A9)

### Sessions (`sessions/`)

- `valid_session.toml` - Complete valid session for positive tests
- `missing_files.toml` - Session with references to non-existent files
- `session_missing_required.toml` - Session missing required 'session' section (A14)

### TTLs (`ttls/`)

- `test_ttl.txt` - Sample TTL pulse data
- `empty_ttl.txt` - Empty TTL file for edge case testing

### Videos (`videos/`)

- `test_video.avi` - Generic test video (111KB)
- `empty_video.avi` - Empty video file for edge case testing
- `dlc_test_cam1.mp4` - Synthetic DLC test video 1 (320x240, 15 frames, ~15KB)
- `dlc_test_cam2.mp4` - Synthetic DLC test video 2 (320x240, 15 frames, ~15KB)
- `dlc_test_cam3.mp4` - Synthetic DLC test video 3 (320x240, 15 frames, ~15KB)

### Models (`models/`)

#### DLC (`models/dlc/`)

- `valid_config.yaml` - Complete valid DLC model config with 5 bodyparts
- `empty_bodyparts.yaml` - DLC config with empty bodyparts list
- `missing_bodyparts.yaml` - DLC config missing bodyparts field
- `missing_task.yaml` - DLC config missing Task field
- `invalid_empty.yaml` - Empty YAML file
- `invalid_not_dict.yaml` - YAML that is not a dictionary
