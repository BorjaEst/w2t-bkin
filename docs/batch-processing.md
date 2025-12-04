# Batch Processing Guide

This guide explains how to process multiple subjects and sessions in parallel using the W2T Body Kinematics pipeline.

## Overview

The pipeline processes one subject/session at a time. For batch processing across multiple subjects/sessions, we provide two approaches:

- **Prefect Orchestration** (Recommended): Built-in batch command with automatic retries, observability dashboard, and intelligent resource management
- **Shell-based Parallelism**: GNU Parallel or xargs for power users who prefer shell scripting
- **Future**: HPC cluster integration (Dask/Slurm) and Kubernetes deployments

## Batch Processing with Prefect (Recommended)

The `batch` command provides Prefect-based orchestration with automatic retries, real-time observability, and graceful error handling.

### Quick Start

```bash
# Process all sessions with 4 parallel workers
python -m w2t_bkin.cli batch config.toml --max-workers 4

# Process specific subject
python -m w2t_bkin.cli batch config.toml --subject subject-001 --max-workers 2

# Process specific session across all subjects
python -m w2t_bkin.cli batch config.toml --session session_20251120
```

### With Prefect UI (Highly Recommended)

For real-time monitoring and observability:

```bash
# Terminal 1: Start Prefect server
prefect server start

# Terminal 2: Run batch processing
python -m w2t_bkin.cli batch config.toml --max-workers 4

# Open browser to http://localhost:4200
# You'll see:
# - Real-time task status and progress
# - Execution timeline and duration
# - Detailed logs for each session
# - Retry attempts and failures
# - Resource usage statistics
```

### Features

- ✅ **Automatic Retries**: 2 retry attempts with 60-second delays
- ✅ **Observability**: Real-time dashboard with task status and logs
- ✅ **Error Handling**: Continues processing even if some sessions fail
- ✅ **Resource Management**: Intelligent concurrency control via max_workers
- ✅ **Structured Logging**: Searchable logs in Prefect UI
- ✅ **Distributed Ready**: Can scale to HPC clusters and Kubernetes

### Programmatic Usage

```python
from w2t_bkin.orchestration import batch_process_sessions

# Process all sessions
result = batch_process_sessions("config.toml", max_workers=4)
print(f"Completed {result['successful']}/{result['total']} sessions")

# With filters
result = batch_process_sessions(
    "config.toml",
    subject_filter="subject-001",
    max_workers=2,
)

# Check for failures
if result['failed'] > 0:
    for r in result['results']:
        if not r['success']:
            print(f"Failed: {r['subject_id']}/{r['session_id']}")
            print(f"Error: {r['error']}")
```

## Session Discovery

The `discover` command scans your raw data directory and lists all valid subject/session combinations.

### Basic Usage

```bash
# List all sessions (JSON format, default)
python -m w2t_bkin.cli discover config.toml

# Human-readable format
python -m w2t_bkin.cli discover config.toml --format plain

# Tab-separated format (for piping to parallel tools)
python -m w2t_bkin.cli discover config.toml --format tsv
```

### Filtering

```bash
# Filter by specific subject
python -m w2t_bkin.cli discover config.toml --subject subject-001

# Filter by specific session
python -m w2t_bkin.cli discover config.toml --session session_20251120

# Combine filters
python -m w2t_bkin.cli discover config.toml --subject subject-001 --session session_20251120
```

### Output Formats

#### JSON (Default)

Detailed output with metadata information, suitable for programmatic use:

```json
[
  {
    "subject": "subject-001",
    "session": "session_20251120",
    "has_subject_metadata": true,
    "metadata_file": "session.toml"
  }
]
```

#### TSV

Tab-separated values, ideal for piping to GNU Parallel:

```
subject-001     session_20251120
subject-002     session_20251121
```

#### Plain

Human-readable table format:

```
Found 4 session(s):

  subject-001          / session_20251120               (session.toml)
  subject-002          / session_20251121               (session.toml)
```

## Parallel Processing with GNU Parallel

### Installation

```bash
# Ubuntu/Debian
sudo apt-get install parallel

# macOS
brew install parallel

# Or via conda
conda install -c conda-forge parallel
```

### Basic Parallel Execution

Process all sessions in parallel (respects CPU cores):

```bash
python -m w2t_bkin.cli discover config.toml --format tsv | \
    parallel --col-sep '\t' python -m w2t_bkin.cli run config.toml {1} {2}
```

### Control Parallelism

```bash
# Limit to 4 parallel jobs
python -m w2t_bkin.cli discover config.toml --format tsv | \
    parallel -j4 --col-sep '\t' python -m w2t_bkin.cli run config.toml {1} {2}

# Serial execution (one at a time)
python -m w2t_bkin.cli discover config.toml --format tsv | \
    parallel -j1 --col-sep '\t' python -m w2t_bkin.cli run config.toml {1} {2}
```

### Progress Monitoring

```bash
# Show progress bar
python -m w2t_bkin.cli discover config.toml --format tsv | \
    parallel --bar --col-sep '\t' python -m w2t_bkin.cli run config.toml {1} {2}

# Show ETA and statistics
python -m w2t_bkin.cli discover config.toml --format tsv | \
    parallel --eta --col-sep '\t' python -m w2t_bkin.cli run config.toml {1} {2}
```

### Error Handling

```bash
# Keep going if one job fails
python -m w2t_bkin.cli discover config.toml --format tsv | \
    parallel --keep-order --col-sep '\t' python -m w2t_bkin.cli run config.toml {1} {2}

# Log failed jobs to file
python -m w2t_bkin.cli discover config.toml --format tsv | \
    parallel --joblog parallel.log --col-sep '\t' \
        python -m w2t_bkin.cli run config.toml {1} {2}

# Retry failed jobs (from log)
parallel --retry-failed --joblog parallel.log
```

### Resource Management

```bash
# Limit memory per job (e.g., 4GB)
python -m w2t_bkin.cli discover config.toml --format tsv | \
    parallel --memfree 4G --col-sep '\t' python -m w2t_bkin.cli run config.toml {1} {2}

# Delay between job starts (e.g., 2 seconds)
python -m w2t_bkin.cli discover config.toml --format tsv | \
    parallel --delay 2 --col-sep '\t' python -m w2t_bkin.cli run config.toml {1} {2}
```

## Programmatic Batch Processing (Python)

### Basic Loop

```python
from w2t_bkin.utils import discover_sessions
from w2t_bkin.core.pipeline import run_pipeline

# Discover all sessions
sessions = discover_sessions("config.toml")

# Process each session
for session_info in sessions:
    subject_id = session_info["subject"]
    session_id = session_info["session"]

    print(f"Processing {subject_id}/{session_id}...")

    try:
        run_pipeline(
            config_path="config.toml",
            subject_id=subject_id,
            session_id=session_id,
        )
        print(f"✓ Completed {subject_id}/{session_id}")
    except Exception as e:
        print(f"✗ Failed {subject_id}/{session_id}: {e}")
```

### Parallel Processing with multiprocessing

```python
from multiprocessing import Pool
from functools import partial
from w2t_bkin.utils import discover_sessions
from w2t_bkin.core.pipeline import run_pipeline

def process_session(session_info, config_path):
    """Process a single session."""
    subject_id = session_info["subject"]
    session_id = session_info["session"]

    try:
        run_pipeline(
            config_path=config_path,
            subject_id=subject_id,
            session_id=session_id,
        )
        return (subject_id, session_id, "success", None)
    except Exception as e:
        return (subject_id, session_id, "failed", str(e))

# Discover sessions
config_path = "config.toml"
sessions = discover_sessions(config_path)

# Process in parallel (4 workers)
with Pool(processes=4) as pool:
    process_fn = partial(process_session, config_path=config_path)
    results = pool.map(process_fn, sessions)

# Report results
for subject_id, session_id, status, error in results:
    if status == "success":
        print(f"✓ {subject_id}/{session_id}")
    else:
        print(f"✗ {subject_id}/{session_id}: {error}")
```

### Filter Before Processing

```python
from w2t_bkin.utils import discover_sessions

# Discover with filters
sessions = discover_sessions(
    config_path="config.toml",
    subject_filter="subject-001",  # Optional
    session_filter=None,           # Optional
)

print(f"Found {len(sessions)} sessions to process")

# Process filtered sessions...
```

## Shell Scripts

### Simple Sequential Script

```bash
#!/bin/bash
# process_all.sh

CONFIG="config.toml"
SESSIONS=$(python -m w2t_bkin.cli discover "$CONFIG" --format tsv)

while IFS=$'\t' read -r SUBJECT SESSION; do
    echo "Processing $SUBJECT / $SESSION ..."
    python -m w2t_bkin.cli run "$CONFIG" "$SUBJECT" "$SESSION"

    if [ $? -eq 0 ]; then
        echo "✓ Completed $SUBJECT / $SESSION"
    else
        echo "✗ Failed $SUBJECT / $SESSION"
    fi
done <<< "$SESSIONS"
```

### Parallel Script with Error Handling

```bash
#!/bin/bash
# parallel_process.sh

CONFIG="config.toml"
LOGDIR="logs"
JOBLOG="$LOGDIR/parallel.log"
NJOBS=4

mkdir -p "$LOGDIR"

python -m w2t_bkin.cli discover "$CONFIG" --format tsv | \
    parallel -j"$NJOBS" --joblog "$JOBLOG" --bar --col-sep '\t' \
        'python -m w2t_bkin.cli run '"$CONFIG"' {1} {2} > '"$LOGDIR"'/{1}_{2}.log 2>&1'

echo "Processing complete. Check $LOGDIR for individual logs."
echo "Failed jobs (if any):"
awk '$7 != "0" {print $8, $9}' "$JOBLOG"
```

## Future: Prefect Integration

The pipeline architecture is designed for future Prefect integration:

```python
# Example future Prefect flow (conceptual)
from prefect import flow, task
from w2t_bkin.utils import discover_sessions
from w2t_bkin.core.pipeline import run_pipeline

@task(retries=2, retry_delay_seconds=60)
def process_session_task(config_path, subject_id, session_id):
    """Prefect task for processing one session."""
    return run_pipeline(config_path, subject_id, session_id)

@flow
def batch_processing_flow(config_path: str):
    """Prefect flow for batch processing."""
    sessions = discover_sessions(config_path)

    # Submit all sessions as parallel tasks
    futures = [
        process_session_task.submit(
            config_path,
            session["subject"],
            session["session"]
        )
        for session in sessions
    ]

    # Wait for all to complete
    results = [f.result() for f in futures]
    return results

# Run flow
if __name__ == "__main__":
    batch_processing_flow("config.toml")
```

## Future: Kubernetes Integration

For large-scale processing, each session can become a Kubernetes job:

```yaml
# Example k8s job (conceptual)
apiVersion: batch/v1
kind: Job
metadata:
  name: w2t-bkin-subject001-session001
spec:
  template:
    spec:
      containers:
        - name: w2t-bkin
          image: w2t-bkin:latest
          command: ["python", "-m", "w2t_bkin.cli", "run"]
          args: ["config.toml", "subject-001", "session-001"]
          resources:
            requests:
              memory: "4Gi"
              cpu: "2"
            limits:
              memory: "8Gi"
              cpu: "4"
      restartPolicy: Never
```

## Best Practices

### 1. Start Small

Test on a single session before batch processing:

```bash
python -m w2t_bkin.cli run config.toml subject-001 session-001
```

### 2. Check Discovery First

Verify which sessions will be processed:

```bash
python -m w2t_bkin.cli discover config.toml --format plain
```

### 3. Use Verification Flags

Skip slow operations during initial testing:

```bash
python -m w2t_bkin.cli run config.toml subject-001 session-001 \
    --no-frame-count --no-sync-check
```

### 4. Monitor Resources

Use `htop` or similar to monitor CPU/memory usage during parallel processing.

### 5. Log Everything

Save logs for debugging:

```bash
parallel --joblog parallel.log --bar --col-sep '\t' \
    'python -m w2t_bkin.cli run config.toml {1} {2} > logs/{1}_{2}.log 2>&1' \
    < <(python -m w2t_bkin.cli discover config.toml --format tsv)
```

### 6. Handle Failures Gracefully

Use `--keep-order` with parallel to continue on errors.

## Troubleshooting

### All Jobs Failing

- Check one session manually first
- Verify config file paths are correct
- Check raw_root directory permissions

### Out of Memory

- Reduce parallel job count (`-j2` instead of `-j4`)
- Use `--memfree` with GNU Parallel
- Add `--no-frame-count` to skip video frame counting

### Slow Discovery

- Discovery is fast (just scans directories)
- If slow, check network storage latency

### Mixed Results

- Check `parallel.log` for failed jobs
- Re-run failed jobs only: `parallel --retry-failed --joblog parallel.log`

## Summary

| Approach                    | Best For                     | Complexity | Scalability | Setup Time |
| --------------------------- | ---------------------------- | ---------- | ----------- | ---------- |
| **Prefect (batch command)** | Most users, production       | Low        | High        | 5 min      |
| GNU Parallel                | Power users, shell scripting | Medium     | Medium      | 5 min      |
| Python multiprocessing      | Custom logic needed          | Medium     | Medium      | 30 min     |
| Prefect + Dask              | HPC clusters                 | High       | Very High   | 2 hours    |
| Kubernetes                  | Cloud-native, large-scale    | Very High  | Very High   | 1 day      |

**Recommendation**:

- **Start here**: Use `python -m w2t_bkin.cli batch config.toml` for immediate batch processing with built-in retries and observability
- **Power users**: Use `discover | parallel` for shell-based workflows
- **Production**: Add Prefect UI (`prefect server start`) for monitoring and debugging
- **Scale up**: Migrate to Dask/Kubernetes when processing 100+ sessions regularly
