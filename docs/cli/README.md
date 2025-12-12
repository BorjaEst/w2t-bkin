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

## CLI vs Prefect UI vs Python API

Choose the right interface for your workflow:

| Interface            | Best For                                                                    | Advantages                                                                                | Limitations                                                               |
| -------------------- | --------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| **CLI (`w2t-bkin`)** | • Project setup<br>• Quick tests<br>• Single sessions<br>• Debugging        | • Fast to use<br>• No browser needed<br>• Scriptable<br>• Immediate feedback              | • Limited parallelism<br>• No visual monitoring<br>• Manual batch control |
| **Prefect UI**       | • Production runs<br>• Batch processing<br>• Team workflows<br>• Monitoring | • Visual progress<br>• Real-time logs<br>• Retry management<br>• True parallelism         | • Requires Docker setup<br>• Browser-based<br>• Slightly more complex     |
| **Python API**       | • Custom workflows<br>• Jupyter notebooks<br>• Integration<br>• Automation  | • Full flexibility<br>• Programmatic control<br>• Custom parameters<br>• Embedded in code | • Requires Python knowledge<br>• No built-in UI<br>• Manual orchestration |

### Decision Guide

**Use CLI when**:

- ✅ Setting up a new experiment (`w2t-bkin data init`)
- ✅ Adding subjects/sessions (`w2t-bkin data add-subject`)
- ✅ Testing a single session (`w2t-bkin run`)
- ✅ Quick validation (`w2t-bkin validate`)
- ✅ Inspecting NWB files (`w2t-bkin inspect`)
- ✅ Debugging pipeline issues

**Use Prefect UI when**:

- ✅ Processing 10+ sessions in parallel
- ✅ Monitoring long-running jobs
- ✅ Team needs to see pipeline status
- ✅ Want automatic retries on failures
- ✅ Need execution history and logs
- ✅ Production deployments

**Use Python API when**:

- ✅ Building custom analysis pipelines
- ✅ Integrating w2t-bkin into larger workflows
- ✅ Working in Jupyter notebooks
- ✅ Need programmatic parameter control
- ✅ Automating complex batch logic

### Example Workflows

#### Workflow 1: New Experiment Setup (CLI)

```bash
# Initialize experiment structure
w2t-bkin data init /data/experiment-2024 \
  --lab "Neuroscience Lab" \
  --institution "University" \
  -y

# Add subjects
w2t-bkin data add-subject /data/experiment-2024 mouse-001 --species "Mus musculus" -y
w2t-bkin data add-subject /data/experiment-2024 mouse-002 --species "Mus musculus" -y

# Add sessions
w2t-bkin data add-session /data/experiment-2024 mouse-001 session-001 -y
w2t-bkin data add-session /data/experiment-2024 mouse-001 session-002 -y

# Copy data files...
# Edit configs...

# Test single session
w2t-bkin run config.toml mouse-001 session-001
```

#### Workflow 2: Production Batch Processing (Prefect UI)

```bash
# Start server once
docker compose up -d

# Open browser to http://localhost:4200
# Navigate to Deployments → batch-processing
# Set parameters:
#   - config_path: /configs/container.toml
#   - max_parallel: 8
# Click Run
# Monitor in Flow Runs tab
```

#### Workflow 3: Custom Analysis Pipeline (Python API)

```python
from w2t_bkin.flows import process_session_flow, SessionFlowConfig
from w2t_bkin.utils import discover_sessions

# Discover sessions
sessions = discover_sessions("config.toml", subject_filter="mouse-00[1-3]")

# Custom processing logic
results = []
for session in sessions:
    config = SessionFlowConfig(
        config_path="config.toml",
        subject_id=session["subject"],
        session_id=session["session"],
        skip_pose=True,  # Already have poses
        skip_nwb_validation=True  # Speed up for testing
    )

    result = process_session_flow(config)
    results.append(result)

# Custom analysis on results
successful = [r for r in results if r.success]
print(f"Processed {len(successful)}/{len(results)} sessions")
```

### Migration Path

Start with CLI for setup, migrate to Prefect UI for production:

1. **Week 1**: Use CLI to set up experiment and test pipeline

   ```bash
   w2t-bkin data init ...
   w2t-bkin run config.toml subject-001 session-001
   ```

2. **Week 2**: Validate results, then set up Docker

   ```bash
   cd /data/experiment
   docker compose up -d
   ```

3. **Week 3+**: Use Prefect UI for all batch processing
   - Browser → http://localhost:4200
   - Deployments → batch-processing → Run
   - Monitor progress, check logs, review results

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
