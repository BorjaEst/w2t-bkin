# Frequently Asked Questions (FAQ)

Quick answers to common questions about the W2T Body Kinematics Pipeline.

## 📋 Table of Contents

- [Installation & Setup](#installation--setup)
- [Data Organization](#data-organization)
- [Processing & Workflows](#processing--workflows)
- [Troubleshooting](#troubleshooting)
- [NWB & Output Files](#nwb--output-files)
- [Docker & Containers](#docker--containers)
- [Performance & Optimization](#performance--optimization)

---

## Installation & Setup

### Q: Do I need Docker to use w2t-bkin?

**A:** No, Docker is optional but recommended. You can run the pipeline locally with Python 3.10+, but Docker provides:

- Automatic dependency management
- Web UI for monitoring (Prefect)
- Easier deployment and reproducibility
- Parallel processing orchestration

For quick testing or development, local Python execution works fine.

### Q: Why do I need to manually install `ndx-structured-behavior` and other NWB extensions?

**A:** The NWB extensions (`ndx-structured-behavior`, `ndx-pose`, `ndx-events`) are not yet published on PyPI. We maintain forks as git submodules to ensure compatibility and add custom features.

**For Docker users**: Extensions are pre-installed in the container - no action needed!

**For local development**:

```bash
# Install ndx-structured-behavior from source (required - not on PyPI)
git clone https://github.com/rly/ndx-structured-behavior.git
pip install ./ndx-structured-behavior

# Install w2t-bkin with all dependencies
pip install w2t-bkin[full,prefect]
```

**For contributors modifying w2t-bkin code**:

```bash
# Clone repository with submodules
git clone --recurse-submodules https://github.com/BorjaEst/w2t-bkin.git
cd w2t-bkin

# Install NWB extensions from submodules
pip install ./nwb-extensions/ndx-structured-behavior/
pip install ./nwb-extensions/ndx-pose/
pip install ./nwb-extensions/ndx-events/

# Install pipeline in editable mode for development
pip install -e .[full,prefect,dev]
```

**Why not on PyPI?** The extensions are maintained by third parties and not yet published. We include them as submodules for convenience.

- Contribute improvements back upstream

### Q: Can I use w2t-bkin on Windows?

**A:** Yes! Windows is fully supported:

- Use **Rancher Desktop** for Docker on Windows (easier than Docker Desktop)
- Or run locally with Python (use PowerShell or Git Bash)
- WSL2 (Windows Subsystem for Linux) also works great

### Q: What Python version do I need?

**A:** Python 3.10 or higher. We recommend Python 3.11 for best performance. Python 3.9 and earlier are **not supported** due to type hinting syntax requirements.

---

## Data Organization

### Q: Do I have to use the CLI to create folders?

**A:** No, the CLI is provided for convenience and consistency, but manual folder creation works fine. Just follow the expected structure:

```
experiment/
├── configuration.toml
├── data/
│   ├── raw/
│   │   ├── metadata.toml
│   │   └── {subject-id}/
│   │       ├── subject.toml
│   │       └── {session-id}/
│   │           ├── session.toml
│   │           ├── Video/
│   │           ├── TTLs/
│   │           └── Bpod/
```

The CLI helps prevent mistakes and generates valid `.toml` files automatically.

### Q: Can I organize data differently (e.g., by date instead of subject)?

**A:** The pipeline expects the `subject-id/session-id` hierarchy. However, you can use **symbolic links** to organize your storage however you like:

```bash
# Your actual storage
/storage/by-date/2024-01-15/videos/

# Symlink to expected structure
ln -s /storage/by-date/2024-01-15/videos/ data/raw/mouse-001/session-001/Video
```

**Important:** The CLI command `w2t-bkin data validate` can check for broken symlinks (enabled by default):

```bash
w2t-bkin data validate /path/to/experiment --check-symlinks
```

### Q: Why is the directory structure so strict?

**A:** The pipeline enforces a strict directory layout for several important reasons:

1. **Reliability**: Predictable paths prevent runtime errors and data loss
2. **NWB Compliance**: The structure maps directly to NWB file organization standards
3. **Reproducibility**: Anyone can understand the experiment layout at a glance
4. **Automation**: Tools can discover and process data without configuration
5. **Collaboration**: Teams share a common language for data organization

**The pipeline will fail immediately if**:

- Required directories (`raw/`, `interim/`, `processed/`) don't exist
- Metadata files (`metadata.toml`, `subject.toml`, `session.toml`) are missing
- Session folders lack expected subfolders (`Video/`, `TTLs/`, `Bpod/`)
- Symlinks are broken (if validation is enabled)

**Design Philosophy**: "Fail fast, fail clearly." If something is wrong with the directory structure, you'll know immediately with a clear error message, rather than discovering issues after hours of processing.

**Best Practices**:

- Use `w2t-bkin data init` to create the root structure
- Use `w2t-bkin data add-subject` and `w2t-bkin data add-session` to add entities
- Run `w2t-bkin data validate` before starting processing runs
- Use symlinks for flexible storage organization (but validate them regularly)

**See**: [Data Management CLI Guide](cli/data-management.md) for detailed commands.

### Q: What is "hierarchical metadata"?

**A:** Metadata cascades from experiment → subject → session levels:

- **Experiment level** (`metadata.toml`): Lab-wide defaults (experimenters, institution)
- **Subject level** (`subject.toml`): Subject info (species, sex, age, genotype)
- **Session level** (`session.toml`): Session details (date, description, experimenter)

Each level **extends and overrides** the previous. This reduces repetition.

**Example:**

```toml
# metadata.toml (experiment)
experimenters = ["Alice", "Bob", "Charlie"]

# session.toml (session)
experimenter = ["Alice"]  # Override: only Alice for this session
```

### Q: Can I have multiple experiments in the same directory?

**A:** Each experiment should have its own root directory. However, you can share **models** and **external data** across experiments using symbolic links:

```bash
ln -s /shared/models/dlc-v1 experiment-1/models/dlc-v1
ln -s /shared/models/dlc-v1 experiment-2/models/dlc-v1
```

---

## Processing & Workflows

### Q: How do I process just one session?

**A:** Use the `process-session` deployment (Docker) or CLI:

**Docker (Prefect UI):**

1. Open http://localhost:4200
2. Go to **Deployments** → **process-session**
3. Click **Run** → **Custom**
4. Fill in: config file, subject ID, session ID
5. Click **Run**

**CLI:**

```bash
python -m w2t_bkin.cli run config.toml subject-001 session-001
```

**Python API:**

```python
from w2t_bkin.flows import SessionFlowConfig, process_session_flow

config = SessionFlowConfig(
    config_path="config.toml",
    subject_id="subject-001",
    session_id="session-001"
)
result = process_session_flow(config)
```

### Q: How do I batch process multiple sessions in parallel?

**A:** Use the `batch-processing` deployment or CLI with `--max-workers`:

**Docker (Prefect UI):**

1. Go to **Deployments** → **batch-processing**
2. Click **Run** → **Custom**
3. Set `max_workers` (e.g., 4)
4. Optionally set filters (regex patterns for subjects/sessions)
5. Click **Run**

**CLI:**

```bash
python -m w2t_bkin.cli batch config.toml --max-workers 4
```

### Q: Can I reprocess a session that already has output?

**A:** Yes, the pipeline will **overwrite** existing NWB files. However, intermediate files (pose estimates) are **cached by default**.

- **NWB files**: Always regenerated
- **Pose estimates**: Reused from cache unless `force_rerun = true`

If you want to preserve old outputs:

```bash
mv data/processed/subject-001/session-001 data/processed/subject-001/session-001.backup
```

**See**: [Caching and Reprocessing Guide](user-guide/caching-and-reprocessing.md) for complete details.

### Q: How do I skip certain processing steps?

**A:** Edit the `configuration.toml` file and set steps to `false`:

```toml
[processing]
run_pose_estimation = false    # Skip pose estimation
run_bpod_ingestion = true      # Keep Bpod processing
run_sync = true                # Keep synchronization
```

---

## Troubleshooting

### Q: Processing fails with "FileNotFoundError: No such file or directory"

**A:** Check:

1. Are your raw data files in the correct folders?
   ```bash
   ls data/raw/subject-001/session-001/Video/
   ls data/raw/subject-001/session-001/TTLs/
   ls data/raw/subject-001/session-001/Bpod/
   ```
2. Is the `configuration.toml` path correct?
3. Are subject/session IDs spelled correctly (case-sensitive)?

Use `w2t-bkin data validate /path/to/experiment` to check structure.

### Q: Docker container fails to start

**A:** Common fixes:

1. **Check Docker is running:**
   ```bash
   docker ps
   ```
2. **Check port 4200 is available:**
   ```bash
   lsof -i :4200  # Linux/Mac
   netstat -ano | findstr :4200  # Windows
   ```
3. **Rebuild containers:**
   ```bash
   docker compose down
   docker compose build --no-cache
   docker compose up -d
   ```
4. **Check logs:**
   ```bash
   docker compose logs server
   docker compose logs worker
   ```

### Q: Processing is very slow

**A:** Optimization tips:

1. **Increase workers for batch processing:**
   ```bash
   python -m w2t_bkin.cli batch config.toml --max-workers 8
   ```
2. **Use Docker with parallel processing** (Prefect orchestration)
3. **Check disk I/O** (slow drives can bottleneck video processing)
4. **Reduce video resolution** in configuration if possible
5. **Use interim data** (processed pose/sync) to avoid recomputation

### Q: How do I view detailed error logs?

**A:** Logs are in multiple places:

**Docker deployment:**

```bash
docker compose logs -f server   # Prefect server logs
docker compose logs -f worker   # Worker logs
```

**Local processing:**

- Console output (real-time)
- `data/processed/{subject-id}/{session-id}/processing_log.txt`

**Prefect UI:**

- Navigate to **Flow Runs** → Click failed run → View **Logs** tab

---

## NWB & Output Files

### Q: What is an NWB file?

**A:** **Neurodata Without Borders (NWB)** is a standardized format for neuroscience data. It stores:

- Subject metadata (species, age, sex)
- Session information (timestamps, experimenters)
- Behavioral data (trials, events, pose tracking)
- Electrophysiology (optional)
- Videos and other raw data (references or embedded)

Benefits: Interoperable, self-documenting, FAIR principles, supported by major analysis tools.

### Q: How do I open and read NWB files?

**A:** Use the `pynwb` library:

```python
from pynwb import NWBHDF5IO

with NWBHDF5IO('output.nwb', 'r') as io:
    nwbfile = io.read()
    print(nwbfile)  # Inspect structure

    # Access data
    pose_data = nwbfile.processing['behavior']['pose']
    trials = nwbfile.trials[:]
```

Or use GUI tools:

- **NWB Explorer** (web-based viewer)
- **neurosift** (visualization)
- **DANDI** (data archive and viewer)

### Q: Can I export data to other formats (CSV, MAT, etc.)?

**A:** Yes, you can extract data from NWB files:

```python
import pandas as pd
from pynwb import NWBHDF5IO

with NWBHDF5IO('output.nwb', 'r') as io:
    nwbfile = io.read()

    # Export trials to CSV
    trials_df = nwbfile.trials.to_dataframe()
    trials_df.to_csv('trials.csv')

    # Export pose data
    pose = nwbfile.processing['behavior']['pose']
    # ... extract and export
```

### Q: Where are the output files?

**A:** Output files are organized by subject and session:

```
data/processed/
└── {subject-id}/
    └── {session-id}/
        ├── {subject-id}_{session-id}.nwb     # Main NWB file
        ├── processing_log.txt                 # Detailed logs
        └── validation_report.json             # NWB validation results
```

---

## Docker & Containers

### Q: How do I access the Prefect UI?

**A:** After starting containers with `docker compose up -d`, open your browser to:

**http://localhost:4200**

### Q: Can I change the Prefect UI port?

**A:** Yes, edit `docker-compose.yml`:

```yaml
services:
  server:
    ports:
      - "8080:4200" # Change 8080 to your preferred port
```

Then restart: `docker compose restart server`

### Q: How do I update to the latest version?

**A:** Pull the latest image and restart:

```bash
docker compose down
docker compose pull
docker compose up -d
```

For local installations:

```bash
pip install --upgrade w2t-bkin
```

### Q: Can I run containers on a remote server?

**A:** Yes! Options:

1. **SSH tunnel** to access Prefect UI:

   ```bash
   ssh -L 4200:localhost:4200 user@remote-server
   ```

   Then open http://localhost:4200 on your local machine

2. **Configure remote server** to bind to public IP (less secure):
   Edit `docker-compose.yml` to change `127.0.0.1:4200` to `0.0.0.0:4200`

3. **Use reverse proxy** (nginx, Traefik) for production deployments

---

## Performance & Optimization

### Q: How many sessions can I process in parallel?

**A:** It depends on your hardware:

- **CPU**: Generally `max_workers = number of CPU cores - 1`
- **RAM**: Each session needs ~2-4GB RAM (varies with video size)
- **Disk I/O**: Fast SSD recommended for 4+ parallel sessions

**Example:**

- 8-core CPU, 32GB RAM → `max_workers=6` is safe
- 4-core CPU, 16GB RAM → `max_workers=2-3`

### Q: Can I resume interrupted processing?

**A:** Currently, the pipeline does **not** support mid-session resume. If processing fails:

1. Check logs for the error
2. Fix the issue (missing files, configuration errors)
3. Restart the session processing

**Workaround**: Enable interim data saving in `configuration.toml`:

```toml
[processing]
save_interim_results = true
```

Then manually skip completed steps on retry.

### Q: How much disk space do I need?

**A:** Rough estimates per session:

- **Raw data**: 10-50GB (videos, pose data, Bpod files)
- **Interim files**: 5-20GB (temporary processing artifacts)
- **NWB output**: 1-10GB (compressed, efficient storage)

**Total**: ~20-80GB per session. Multiply by number of sessions.

**Tip**: Use `--symlink` with `w2t-bkin data import-raw` to avoid duplicating raw data.

---

## Still Have Questions?

- **Check the full documentation**: [docs/README.md](README.md)
- **Search existing issues**: [GitHub Issues](https://github.com/BorjaEst/w2t-bkin/issues)
- **Open a new issue**: Provide logs, configuration, and error messages
- **See troubleshooting guide**: [docs/TROUBLESHOOTING.md](TROUBLESHOOTING.md)

---

## 📚 Navigation

- **⬅️ [Documentation Hub](README.md)**
- **📖 [Getting Started](../README.md#quick-start)**
- **🔧 [Troubleshooting](TROUBLESHOOTING.md)**
- **💻 [CLI Reference](cli/README.md)**
- **📋 [Configuration Reference](reference/configuration-parameters.md)**
