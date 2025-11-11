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

- (Directory exists for future video fixtures)
