# Project Templates

This directory contains standardized templates for organizing data and configurations within the `w2t-bkin` project. These templates ensure consistency across experiments and facilitate the automated ingestion pipeline.

## Session Template

The `session/` directory provides the required structure for a new experimental session. It includes the necessary folder hierarchy for raw data and a configuration file for session metadata.

### Directory Structure

```text
session/
├── metadata.toml   # NWB session configuration and metadata
├── Bpod/           # Place raw Bpod .mat files here
├── TTLs/           # Place raw TTL pulse files here
└── Video/          # Place raw video files (.avi, .mp4) here
```

### Usage

To start a new session, copy the `session` template to your raw data directory and rename it with your session identifier (e.g., `Session-000001`).

```bash
# Example: Creating a new session directory
cp -r templates/session data/raw/Session-000001
```

After copying:

1. **Populate Data**: Move your raw data files into the respective subdirectories (`Bpod/`, `TTLs/`, `Video/`).
2. **Configure Metadata**: Edit `metadata.toml` in the new session folder.

### Metadata Configuration (`metadata.toml`)

The `metadata.toml` file is crucial for generating valid NWB files. It maps your experimental metadata to the NWB standard.

**Key Fields to Update:**

- **`identifier`**: A unique ID for the session (must match your folder name if using the pipeline defaults).
- **`session_start_time`**: The exact start time of the recording (ISO 8601 format).
- **`subject`**: Details about the animal (ID, age, sex, genotype).
- **`devices`**: Configuration for cameras and behavioral hardware.

Refer to the comments within `metadata.toml` for detailed instructions on each field.
