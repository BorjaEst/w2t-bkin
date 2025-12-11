# CLI Reference

## W2T-BKIN Command Line Interface

The w2t-bkin CLI provides a user-friendly interface to the Prefect-based data processing pipeline. All commands are thin wrappers around Prefect flows, ensuring consistency between CLI and programmatic usage.

## Command Structure

```bash
w2t-bkin [COMMAND] [ARGS] [OPTIONS]
```

### Main Commands

- **`run`** - Process single session
- **`batch`** - Process multiple sessions in parallel
- **`discover`** - List available sessions
- **`validate`** - Validate NWB file
- **`inspect`** - Inspect NWB file contents
- **`version`** - Show version information

### Data Management Commands

- **`data init`** - Initialize experiment structure
- **`data add-subject`** - Add subject to experiment
- **`data add-session`** - Add session for subject
- **`data import-raw`** - Import existing raw data (safe symlinks)
- **`data validate`** - Validate experiment folder structure

## Quick Start

### Process a Single Session

```bash
w2t-bkin run config.toml subject-001 session-001
```

### Process Multiple Sessions

```bash
# Process all sessions with 4 parallel workers
w2t-bkin batch config.toml --max-workers 4

# Process specific subject
w2t-bkin batch config.toml --subject subject-001 --max-workers 2
```

### Initialize New Experiment

```bash
w2t-bkin data init /data/my-experiment \
  --lab "Larkum Lab" \
  --institution "HU Berlin" \
  --experimenters "Alice,Bob"
```

### Discover Available Sessions

```bash
# List all sessions (JSON format)
w2t-bkin discover config.toml

# Human-readable table
w2t-bkin discover config.toml --format plain

# Tab-separated for piping to tools
w2t-bkin discover config.toml --format tsv
```

## Documentation Structure

- **[Pipeline Commands](pipeline-commands.md)** - run, batch, discover, version
- **[Validation Commands](validation.md)** - validate, inspect
- **[Data Management](data-management.md)** - init, add-subject, add-session, import-raw, validate

## Getting Help

```bash
# Show all commands
w2t-bkin --help

# Show command-specific help
w2t-bkin run --help
w2t-bkin data --help
w2t-bkin data init --help
```

## Container Deployment

For containerized deployment, use standard Docker Compose commands:

```bash
# Start Prefect server
docker compose up -d server

# Start worker(s)
docker compose up -d worker

# Scale workers
docker compose up -d --scale worker=4

# View status
docker compose ps

# View logs
docker compose logs -f server
docker compose logs -f worker

# Stop all services
docker compose down
```

The `.env` file for Docker is automatically generated during `data init`.

## Design Philosophy

The CLI follows these principles:

1. **Thin Layer**: CLI is purely presentational - all logic in flows/operations
2. **Prefect-First**: Commands invoke Prefect flows for consistency
3. **User-Friendly**: Rich output, clear error messages, helpful hints
4. **Safe Defaults**: Dry-run modes, confirmations for destructive operations
5. **Standard Tools**: Use docker-compose directly, not custom wrappers

## Architecture

```text
┌─────────────────────────────────────────┐
│           CLI Layer (Typer)             │
│  • Argument parsing                     │
│  • User interaction (Rich)              │
│  • Output formatting                    │
└──────────────┬──────────────────────────┘
               │ invokes
┌──────────────▼──────────────────────────┐
│       Flows Layer (Prefect)             │
│  • process_session_flow()               │
│  • batch_process_flow()                 │
│  • Orchestration & retries              │
└──────────────┬──────────────────────────┘
               │ calls
┌──────────────▼──────────────────────────┐
│    Operations Layer (Pure Functions)    │
│  • Business logic                       │
│  • Data transformations                 │
│  • NWB construction                     │
└─────────────────────────────────────────┘
```

## Next Steps

- Review [Pipeline Commands](pipeline-commands.md) for session processing
- Review [Data Management](data-management.md) for experiment setup
- Review [Validation Commands](validation.md) for NWB validation
