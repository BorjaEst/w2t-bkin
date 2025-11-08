---
post_title: "Module Design — cli"
author1: "Project Team"
post_slug: "design-cli"
microsoft_alias: "na"
featured_image: "/assets/og.png"
categories: ["dev", "docs"]
tags: ["design", "cli", "typer"]
ai_note: "Generated as a module design stub."
summary: "Design for a Typer-based CLI orchestrating pipeline stages."
post_date: "2025-11-08"
---

<!-- markdownlint-disable MD041 -->

## Scope

Expose subcommands: ingest, sync, transcode, pose, infer, facemap, to-nwb, validate, report.

## Responsibilities

- Parse arguments; load settings; call module entry points.
- Consistent logging and exit codes.

## Inputs/Outputs (Contract)

- Inputs: CLI args; environment; settings path.
- Outputs: Stage artifacts on disk; logs to console/file.

## Dependencies

- Typer, rich/logging.

## Public Interfaces (planned)

- app = Typer(); subcommands registered under cli/app.py.

## Error Handling

- Map known exceptions to user-friendly messages and non-zero exit codes.

## Testing

- CLI smoke tests: --help; dry-run flags.

## Future Notes

- Add global --config and --force; --jobs for parallel stages.
