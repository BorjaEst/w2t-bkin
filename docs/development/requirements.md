# Testing Requirements

## Overview

This document defines the requirements for the `w2t-bkin` test suite. The goal is to ensure a robust, reliable, and maintainable test suite that accurately reflects the current system architecture and data schemas.

## Implementation Status

**Last Updated**: December 11, 2025

### Unit Tests ✅
- **259/268 passing** (96.6% pass rate)
- 1 expected failure (Prefect API connection)
- 8 expected skips (missing fixtures)

### Integration Tests 🔄
- **20/45 passing** (44.4% pass rate)
- Focus areas: Sync tests, pipeline tests, CLI tests
- Fixed: Ecephys Phase 1 API compatibility

## Functional Requirements

### Configuration Testing

- **REQ-TEST-001**: The system shall validate that valid TOML configurations are loaded correctly.
- **REQ-TEST-002**: The system shall reject invalid TOML configurations with descriptive error messages.
- **REQ-TEST-003**: The system shall verify that all required configuration keys are present.

### Synthetic Data Generation

- **REQ-TEST-010**: The synthetic data generator shall produce directory structures that match the production pipeline's expectation.
- **REQ-TEST-011**: The synthetic data generator shall create valid `metadata.toml` files conforming to the current schema.
- **REQ-TEST-012**: The synthetic data generator shall create valid dummy data files (e.g., `.h5` for pose, `.mat` for Bpod) that can be parsed by the pipeline.

### Unit Testing

- **REQ-TEST-020**: Each core module (`config`, `utils`, `session`, `pose`, `ecephys`) shall have corresponding unit tests.
- **REQ-TEST-021**: Unit tests shall mock external dependencies (filesystem, heavy computation) where appropriate.

### Integration Testing

- **REQ-TEST-030**: The integration pipeline test shall run the full `process_session_flow` from start to finish using synthetic data.
- **REQ-TEST-031**: The integration test shall verify the existence and basic validity of the output NWB file.
- **REQ-TEST-032**: The integration test shall verify that the output NWB file contains the expected modules (Pose, Behavior, etc.).

## Non-Functional Requirements

- **REQ-TEST-100**: The full test suite shall run in under 5 minutes on a standard developer machine.
- **REQ-TEST-101**: Tests shall be deterministic (no flaky tests).
- **REQ-TEST-102**: Test failures shall provide clear diagnostics (diffs, logs).
