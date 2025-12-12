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

### Server Management Commands

- **`server start`** - Start Prefect server and create deployments
- **`server stop`** - Stop the running Prefect server
- **`server status`** - Check if Prefect server is running
- **`server restart`** - Restart Prefect server

## Starting the Prefect Server

The server command starts a local Prefect server and automatically creates workflow deployments:

```bash
# Start server (opens browser at http://localhost:4200)
w2t-bkin server start

# Start with custom config
w2t-bkin server start --config configs/custom.toml

# Start with custom port
w2t-bkin server start --port 5000

# Configure workers (Docker recommended, local alternative)
w2t-bkin server start --pool docker-pool --pool-type docker  # Recommended
w2t-bkin server start --pool local-pool --pool-type process  # Requires [worker] extras

# Check server status
w2t-bkin server status

# Stop server
w2t-bkin server stop
```

After starting the server, use the Prefect UI at http://localhost:4200 to trigger workflows.

## CLI vs Prefect UI vs Python API

Choose the right interface for your workflow:

| Interface            | Best For                                                                    | Advantages                                                                                | Limitations                                                               |
| -------------------- | --------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| **CLI (`w2t-bkin`)** | • Project setup<br>• Quick tests<br>• Single sessions<br>• Debugging        | • Fast to use<br>• No browser needed<br>• Scriptable<br>• Immediate feedback              | • Limited parallelism<br>• No visual monitoring<br>• Manual batch control |
| **Prefect UI**       | • Production runs<br>• Batch processing<br>• Team workflows<br>• Monitoring | • Visual progress<br>• Real-time logs<br>• Retry management<br>• True parallelism         | • Requires server start<br>• Browser-based                                |
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

# Import raw data files
w2t-bkin data import-raw /data/experiment-2024 mouse-001 session-001 /source/videos

# Start Prefect server and use UI to trigger workflows
cd /data/experiment-2024
w2t-bkin server start
# Opens browser at http://localhost:4200
```

#### Workflow 2: Production Batch Processing (Prefect UI)

```bash
# Start server
cd /data/experiment-2024
w2t-bkin server start

# Server automatically:
# - Creates deployments (process-session, batch-process)
# - Opens browser at http://localhost:4200

# In Prefect UI:
# Navigate to Deployments → batch-process
# Set parameters via UI (config path, filters, max_parallel)
# Click Run
# Monitor progress in Flow Runs tab
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

Start with CLI for setup, use Prefect UI for production:

1. **Initial Setup**: Use CLI to create experiment structure

   ```bash
   w2t-bkin data init /data/experiment
   w2t-bkin data add-subject ...
   w2t-bkin data add-session ...
   ```

2. **Test Pipeline**: Run single session via CLI

   ```bash
   w2t-bkin run config.toml subject-001 session-001
   ```

3. **Production Processing**: Start server and use Prefect UI
   ```bash
   w2t-bkin server start
   # Opens browser at http://localhost:4200
   # Use UI to run batch-process deployment
   ```

## Design Philosophy

The CLI follows these principles:

1. **Thin Layer**: CLI is purely presentational - all logic in flows/operations
2. **Prefect-First**: Commands invoke Prefect flows for consistency
3. **User-Friendly**: Rich output, clear error messages, helpful hints
4. **Safe Defaults**: Dry-run modes, confirmations for destructive operations

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
