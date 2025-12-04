# Quick Start: Batch Processing

This guide gets you started with batch processing in under 5 minutes.

## Prerequisites

```bash
# Install GNU Parallel (if not already installed)
sudo apt-get install parallel  # Ubuntu/Debian
brew install parallel           # macOS
```

## Step 1: Verify Your Data Structure

Your raw data should be organized as:

```
data/raw/
├── subject-001/
│   ├── subject.toml           # Optional: subject metadata
│   ├── session_20251120/
│   │   ├── session.toml       # Required: session metadata
│   │   ├── Video/
│   │   ├── TTLs/
│   │   └── Bpod/
│   └── session_20251121/
│       └── ...
└── subject-002/
    └── ...
```

## Step 2: Discover Available Sessions

```bash
# See what sessions are available
python -m w2t_bkin.cli discover config.toml --format plain
```

Expected output:

```
Found 4 session(s):

  subject-001          / session_20251120               (session.toml)
  subject-001          / session_20251121               (session.toml)
  subject-002          / session_20251120               (session.toml)
  subject-002          / session_20251121               (session.toml)
```

## Step 3: Test on One Session

Before batch processing, verify the pipeline works on one session:

```bash
python -m w2t_bkin.cli run config.toml subject-001 session_20251120
```

## Step 4: Batch Process All Sessions

### Option A: Serial Processing (Safest)

Process one session at a time:

```bash
python -m w2t_bkin.cli discover config.toml --format tsv | \
    parallel -j1 --col-sep '\t' \
        python -m w2t_bkin.cli run config.toml {1} {2}
```

### Option B: Parallel Processing (Faster)

Process multiple sessions simultaneously (adjust `-j4` based on CPU cores):

```bash
python -m w2t_bkin.cli discover config.toml --format tsv | \
    parallel -j4 --bar --col-sep '\t' \
        python -m w2t_bkin.cli run config.toml {1} {2}
```

### Option C: With Logging

Save logs for debugging:

```bash
mkdir -p logs

python -m w2t_bkin.cli discover config.toml --format tsv | \
    parallel -j4 --bar --joblog logs/parallel.log --col-sep '\t' \
        'python -m w2t_bkin.cli run config.toml {1} {2} > logs/{1}_{2}.log 2>&1'
```

## Step 5: Check Results

View processing status:

```bash
# Check parallel job log
cat logs/parallel.log

# View individual session logs
ls logs/*.log

# Check failed jobs (exit code != 0)
awk '$7 != "0" {print "Failed:", $8, $9}' logs/parallel.log
```

## Common Filters

```bash
# Process only one subject
python -m w2t_bkin.cli discover config.toml --subject subject-001 --format tsv | \
    parallel -j2 --bar --col-sep '\t' \
        python -m w2t_bkin.cli run config.toml {1} {2}

# Process only specific session date
python -m w2t_bkin.cli discover config.toml --session session_20251120 --format tsv | \
    parallel -j2 --bar --col-sep '\t' \
        python -m w2t_bkin.cli run config.toml {1} {2}
```

## Performance Tips

### Skip Slow Verification Steps

If you're confident about data quality, skip time-consuming checks:

```bash
python -m w2t_bkin.cli discover config.toml --format tsv | \
    parallel -j4 --bar --col-sep '\t' \
        python -m w2t_bkin.cli run config.toml {1} {2} --no-frame-count
```

Available flags:

- `--no-verification`: Skip all verification
- `--no-frame-count`: Skip video frame counting (saves ~2 minutes per video)
- `--no-sync-check`: Skip sync mismatch detection

### Monitor Resource Usage

```bash
# In another terminal, monitor CPU/memory
htop

# Or use top
top
```

## Troubleshooting

### All Jobs Failing

```bash
# Test one session manually
python -m w2t_bkin.cli run config.toml subject-001 session_20251120

# Check discovery finds sessions
python -m w2t_bkin.cli discover config.toml --format plain
```

### Out of Memory

Reduce parallelism:

```bash
# Use only 2 parallel jobs instead of 4
parallel -j2 ...
```

### Some Jobs Failing

Re-run only failed jobs:

```bash
# Retry failed jobs from log
parallel --retry-failed --joblog logs/parallel.log
```

## Next Steps

- Read [docs/batch-processing.md](batch-processing.md) for advanced techniques
- Explore Python programmatic APIs for custom workflows
- Plan for Prefect/Kubernetes integration for production

## Cheat Sheet

| Command                                | Purpose                          |
| -------------------------------------- | -------------------------------- |
| `discover config.toml --format plain`  | List sessions (human-readable)   |
| `discover config.toml --format tsv`    | List sessions (pipe to parallel) |
| `discover config.toml --subject X`     | Filter by subject                |
| `parallel -j1 ...`                     | Serial processing                |
| `parallel -j4 --bar ...`               | Parallel with progress bar       |
| `parallel --joblog log ...`            | Save job status                  |
| `parallel --retry-failed --joblog log` | Retry failed                     |
| `run ... --no-frame-count`             | Skip slow video checks           |

---

**Time Savings Example**:

- Manual: 10 minutes/session × 50 sessions = 8.3 hours
- Parallel (8 cores): 10 minutes/session ÷ 8 = 1.25 hours
- **Savings: 7 hours** ⚡
