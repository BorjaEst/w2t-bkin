# Troubleshooting Guide

Common issues and solutions for the W2T Body Kinematics Pipeline.

## 📋 Quick Navigation

- [Installation Issues](#installation-issues)
- [Docker & Container Issues](#docker--container-issues)
- [Data Organization Issues](#data-organization-issues)
- [Processing & Pipeline Issues](#processing--pipeline-issues)
- [NWB Output Issues](#nwb-output-issues)
- [Performance Issues](#performance-issues)
- [Configuration Issues](#configuration-issues)
- [Getting Help](#getting-help)

---

## Installation Issues

### ❌ `pip install w2t-bkin` fails with dependency conflicts

**Symptoms:**

```
ERROR: pip's dependency resolver does not currently take into account all the packages that are installed.
ERROR: Could not find a version that satisfies the requirement...
```

**Solutions:**

1. **Use a fresh virtual environment:**

   ```bash
   python -m venv .venv-fresh
   source .venv-fresh/bin/activate  # Linux/Mac
   # or .venv-fresh\Scripts\activate  # Windows
   pip install --upgrade pip
   pip install w2t-bkin[full,prefect]
   ```

2. **Check Python version:**

   ```bash
   python --version  # Must be 3.10 or higher
   ```

3. **Install dependencies separately:**
   ```bash
   pip install pynwb
   pip install prefect
   pip install w2t-bkin
   ```

---

### ❌ `ndx-structured-behavior` installation fails

**Symptoms:**

```
ERROR: Could not find a version that satisfies the requirement ndx-structured-behavior
```

**Solution:**

This extension is not on PyPI yet. Install manually:

```bash
git clone https://github.com/rly/ndx-structured-behavior.git
pip install -U ./ndx-structured-behavior
```

**Verification:**

```python
import ndx_structured_behavior
print("✅ ndx-structured-behavior installed")
```

---

### ❌ Import errors: `ModuleNotFoundError: No module named 'w2t_bkin'`

**Symptoms:**

```
ModuleNotFoundError: No module named 'w2t_bkin'
```

**Solutions:**

1. **Verify installation:**

   ```bash
   pip list | grep w2t-bkin
   ```

2. **Check virtual environment is activated:**

   ```bash
   which python  # Should point to .venv/bin/python
   ```

3. **Reinstall in editable mode (for development):**
   ```bash
   pip install -e .
   ```

---

## Docker & Container Issues

### ❌ Docker container fails to start

**Symptoms:**

```
Error response from daemon: Ports are not available
ERROR: Service 'server' failed to build
```

**Solutions:**

1. **Check Docker is running:**

   ```bash
   docker ps
   # If error, start Docker service/application
   ```

2. **Check port 4200 is available:**

   ```bash
   # Linux/Mac
   lsof -i :4200

   # Windows
   netstat -ano | findstr :4200
   ```

   If port is in use, either:

   - Stop the conflicting service
   - Change the port in `docker-compose.yml`:
     ```yaml
     ports:
       - "8080:4200" # Use port 8080 instead
     ```

3. **Rebuild containers from scratch:**

   ```bash
   docker compose down -v  # Remove volumes
   docker compose build --no-cache
   docker compose up -d
   ```

4. **Check disk space:**
   ```bash
   df -h  # Ensure sufficient space for Docker images
   ```

---

### ❌ Cannot access Prefect UI at http://localhost:4200

**Symptoms:**

- Browser shows "Connection refused" or "Site can't be reached"
- Container is running but UI is inaccessible

**Solutions:**

1. **Check containers are running:**

   ```bash
   docker compose ps
   # Both 'server' and 'worker' should show "Up"
   ```

2. **Check server logs:**

   ```bash
   docker compose logs server
   # Look for "Uvicorn running on http://0.0.0.0:4200"
   ```

3. **Wait for startup (first launch can take 30-60 seconds):**

   ```bash
   docker compose logs -f server  # Watch logs until ready
   ```

4. **Check port binding:**

   ```bash
   docker compose ps server
   # Should show "0.0.0.0:4200->4200/tcp"
   ```

5. **Try accessing from container IP (Docker Desktop/Rancher):**

   - Windows: http://localhost:4200
   - Linux: http://172.17.0.1:4200 (or container IP)

6. **Restart containers:**
   ```bash
   docker compose restart
   ```

---

### ❌ Docker Compose command not found

**Symptoms:**

```
bash: docker-compose: command not found
```

**Solutions:**

1. **Use `docker compose` (v2 syntax):**

   ```bash
   docker compose up -d  # Note: no hyphen
   ```

2. **Install Docker Compose plugin:**

   ```bash
   # Linux
   sudo apt-get update
   sudo apt-get install docker-compose-plugin
   ```

3. **Install standalone Docker Compose (legacy):**
   ```bash
   sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
   sudo chmod +x /usr/local/bin/docker-compose
   ```

---

### ❌ Permission denied errors with Docker

**Symptoms:**

```
Got permission denied while trying to connect to the Docker daemon socket
```

**Solutions:**

1. **Add user to docker group (Linux):**

   ```bash
   sudo usermod -aG docker $USER
   newgrp docker  # Or logout/login
   ```

2. **Use sudo (temporary workaround):**

   ```bash
   sudo docker compose up -d
   ```

3. **Check Docker socket permissions:**
   ```bash
   ls -la /var/run/docker.sock
   sudo chmod 666 /var/run/docker.sock  # Not recommended for production
   ```

---

## Data Organization Issues

### ❌ `FileNotFoundError: No such file or directory`

**Symptoms:**

```
FileNotFoundError: [Errno 2] No such file or directory: 'data/raw/subject-001/session-001/...'
```

**Solutions:**

1. **Verify folder structure:**

   ```bash
   w2t-bkin data validate /path/to/experiment
   # Or manually check:
   ls -R data/raw/
   ```

2. **Check subject and session IDs are correct (case-sensitive):**

   ```bash
   # List available subjects
   ls data/raw/

   # List sessions for a subject
   ls data/raw/subject-001/
   ```

3. **Verify data files exist:**

   ```bash
   ls data/raw/subject-001/session-001/Video/
   ls data/raw/subject-001/session-001/TTLs/
   ls data/raw/subject-001/session-001/Bpod/
   ```

4. **Check file permissions:**
   ```bash
   ls -la data/raw/subject-001/session-001/
   # Ensure read permissions for your user
   ```

---

### ❌ Metadata validation errors

**Symptoms:**

```
ValidationError: 1 validation error for ExperimentConfig
```

**Solutions:**

1. **Validate TOML syntax:**

   ```bash
   # Check for syntax errors
   python -c "import tomli; tomli.load(open('data/raw/metadata.toml', 'rb'))"
   ```

2. **Check required fields are present:**

   ```toml
   # metadata.toml (experiment level)
   experiment_name = "my-experiment"
   lab = "Lab Name"
   institution = "Institution"
   experimenters = ["Alice", "Bob"]

   # subject.toml (subject level)
   subject_id = "subject-001"
   species = "Mus musculus"
   sex = "F"  # or "M", "U"

   # session.toml (session level)
   session_id = "session-001"
   session_start_time = "2024-01-15T10:00:00"
   ```

3. **Check for duplicate keys:**

   ```bash
   grep -n "^experiment_name" data/raw/metadata.toml
   # Should only appear once
   ```

4. **Regenerate metadata files:**

   ```bash
   # Backup existing
   mv data/raw/metadata.toml data/raw/metadata.toml.backup

   # Reinitialize
   w2t-bkin data init /path/to/experiment --lab "Lab" -y
   ```

---

## Processing & Pipeline Issues

### ❌ Processing fails with "No videos found"

**Symptoms:**

```
RuntimeError: No video files found in data/raw/subject-001/session-001/Video/
```

**Solutions:**

1. **Check video files exist and have correct extensions:**

   ```bash
   ls data/raw/subject-001/session-001/Video/
   # Supported: .mp4, .avi, .mov, .mkv
   ```

2. **Check video file permissions:**

   ```bash
   ls -la data/raw/subject-001/session-001/Video/*.mp4
   ```

3. **Verify video file patterns in configuration:**

   ```toml
   [cameras.cam0]
   video_pattern = "cam0_*.mp4"  # Must match actual filenames
   ```

4. **Use symbolic links if videos are elsewhere:**
   ```bash
   ln -s /original/location/videos/*.mp4 data/raw/subject-001/session-001/Video/
   ```

---

### ❌ Pose estimation fails

**Symptoms:**

```
Error: Could not load pose model
KeyError: 'DLC_config'
```

**Solutions:**

1. **Verify model path in configuration:**

   ```toml
   [pose]
   tool = "deeplabcut"  # or "sleap"
   model_path = "models/dlc-model-name"
   ```

2. **Check model directory exists:**

   ```bash
   ls -la models/dlc-model-name/
   # Should contain config.yaml and model files
   ```

3. **Verify model format is correct:**

   - **DeepLabCut**: `config.yaml` present
   - **SLEAP**: `*.slp` project file present

4. **Check model compatibility:**
   - DLC version matches (2.2+)
   - SLEAP version matches (1.3+)

---

### ❌ Synchronization fails: "TTL alignment error"

**Symptoms:**

```
RuntimeError: Could not align TTL pulses with video frames
```

**Solutions:**

1. **Verify TTL files exist:**

   ```bash
   ls data/raw/subject-001/session-001/TTLs/
   ```

2. **Check TTL configuration:**

   ```toml
   [sync]
   ttl_source = "bpod"  # or "camera", "external"
   sampling_rate = 1000.0
   min_pulse_width = 0.001  # 1ms
   ```

3. **Inspect TTL data manually:**

   ```python
   import pandas as pd
   ttls = pd.read_csv('data/raw/.../TTLs/ttls.csv')
   print(ttls.head())
   # Check for reasonable timestamps and pulse counts
   ```

4. **Adjust synchronization tolerance:**
   ```toml
   [sync]
   max_time_diff = 0.1  # Allow 100ms tolerance
   ```

---

### ❌ Bpod data import fails

**Symptoms:**

```
Error loading Bpod .mat file
KeyError: 'SessionData'
```

**Solutions:**

1. **Verify Bpod .mat file format:**

   ```python
   import scipy.io
   data = scipy.io.loadmat('data/raw/.../Bpod/session.mat')
   print(data.keys())  # Should contain 'SessionData'
   ```

2. **Check Bpod protocol in configuration:**

   ```toml
   [behavior]
   bpod_protocol = "standard"  # Must match your protocol
   ```

3. **Verify Bpod file is not corrupted:**

   - Try opening in MATLAB/Octave
   - Check file size is reasonable (not 0 bytes)

4. **Use latest Bpod version** (compatibility issues with old formats)

---

### ❌ Batch processing hangs or stalls

**Symptoms:**

- Some sessions process, others never start
- Worker shows "idle" but tasks remain queued

**Solutions:**

1. **Check worker logs:**

   ```bash
   docker compose logs -f worker
   # Look for errors or exceptions
   ```

2. **Reduce max_workers:**

   ```bash
   python -m w2t_bkin.cli batch config.toml --max-workers 2
   ```

3. **Check system resources:**

   ```bash
   top  # or htop
   # Look for OOM (Out of Memory) killer
   ```

4. **Restart worker:**

   ```bash
   docker compose restart worker
   ```

5. **Process sessions individually to identify problematic ones:**
   ```bash
   python -m w2t_bkin.cli run config.toml subject-001 session-001
   python -m w2t_bkin.cli run config.toml subject-001 session-002
   # Identify which session causes hang
   ```

---

## NWB Output Issues

### ❌ NWB file validation fails

**Symptoms:**

```
ValidationError: NWB file does not conform to schema
```

**Solutions:**

1. **Run NWB validator:**

   ```bash
   python -m pynwb.validate output.nwb
   ```

2. **Check validation report:**

   ```bash
   cat data/processed/subject-001/session-001/validation_report.json
   ```

3. **Verify NWB file integrity:**

   ```python
   from pynwb import NWBHDF5IO

   with NWBHDF5IO('output.nwb', 'r') as io:
       nwbfile = io.read()
       print(nwbfile)  # Should load without errors
   ```

4. **Common issues:**
   - Missing required fields (check `subject_id`, `session_start_time`)
   - Invalid timestamps (check for NaT or negative values)
   - Data shape mismatches (check pose data dimensions)

---

### ❌ Cannot open NWB file: "Unable to open file"

**Symptoms:**

```
OSError: Unable to open file (file signature not found)
```

**Solutions:**

1. **Check file is not corrupted:**

   ```bash
   ls -lh output.nwb  # Should have reasonable size (>1KB)
   file output.nwb    # Should show "Hierarchical Data Format"
   ```

2. **Verify file was written completely:**

   - Check processing logs for errors during write
   - Ensure disk didn't fill during processing

3. **Try opening with h5py:**

   ```python
   import h5py
   with h5py.File('output.nwb', 'r') as f:
       print(list(f.keys()))  # Should show NWB structure
   ```

4. **Re-run processing** if file is corrupted

---

## Performance Issues

### ❌ Processing is very slow

**Symptoms:**

- Single session takes hours to process
- CPU usage is low despite processing

**Solutions:**

1. **Enable parallel processing:**

   ```bash
   python -m w2t_bkin.cli batch config.toml --max-workers 4
   ```

2. **Check disk I/O:**

   ```bash
   iostat -x 1  # Linux
   # Look for high %util or await times
   ```

   - Use SSD instead of HDD if possible
   - Avoid network-mounted storage for interim data

3. **Reduce video resolution** (if acceptable):

   ```toml
   [processing]
   downscale_factor = 0.5  # Process at half resolution
   ```

4. **Profile bottlenecks:**

   ```bash
   python -m cProfile -o profile.stats -m w2t_bkin.cli run config.toml subject-001 session-001
   python -c "import pstats; p = pstats.Stats('profile.stats'); p.sort_stats('cumulative').print_stats(20)"
   ```

5. **Use interim results** (avoid recomputation):
   ```toml
   [processing]
   save_interim_results = true
   load_interim_if_available = true
   ```

---

### ❌ Out of memory errors

**Symptoms:**

```
MemoryError: Unable to allocate array
Killed  # Process terminated by OOM killer
```

**Solutions:**

1. **Reduce parallel workers:**

   ```bash
   python -m w2t_bkin.cli batch config.toml --max-workers 1
   ```

2. **Process in chunks:**

   ```bash
   # Process subjects one at a time
   python -m w2t_bkin.cli batch config.toml --subject-filter "subject-001"
   python -m w2t_bkin.cli batch config.toml --subject-filter "subject-002"
   ```

3. **Increase Docker memory limit:**

   - Docker Desktop: Settings → Resources → Memory (increase to 8GB+)
   - Linux: No limit by default (check system RAM)

4. **Reduce video resolution:**

   ```toml
   [processing]
   downscale_factor = 0.5
   ```

5. **Use streaming processing** (if implemented):
   ```toml
   [processing]
   streaming_mode = true
   chunk_size = 1000  # Process 1000 frames at a time
   ```

---

## Configuration Issues

### ❌ Configuration file not found

**Symptoms:**

```
FileNotFoundError: [Errno 2] No such file or directory: 'config.toml'
```

**Solutions:**

1. **Check configuration file path:**

   ```bash
   ls /path/to/experiment/configs/
   # Should show .toml files
   ```

2. **Use absolute path:**

   ```bash
   python -m w2t_bkin.cli run /absolute/path/to/config.toml subject-001 session-001
   ```

3. **Copy from template:**
   ```bash
   cp templates/configuration.toml /path/to/experiment/configs/standard.toml
   ```

---

### ❌ Invalid configuration: "Validation error"

**Symptoms:**

```
ValidationError: 1 validation error for PipelineConfig
```

**Solutions:**

1. **Check TOML syntax:**

   ```bash
   python -c "import tomli; tomli.load(open('config.toml', 'rb'))"
   ```

2. **Validate against schema:**

   ```python
   from w2t_bkin.config import PipelineConfig
   config = PipelineConfig.from_file('config.toml')
   ```

3. **Check for common issues:**

   - Missing required sections (`[general]`, `[cameras]`, etc.)
   - Invalid data types (string instead of number)
   - Duplicate keys
   - Invalid enum values

4. **Use template as reference:**
   ```bash
   diff templates/configuration.toml configs/standard.toml
   ```

---

## Getting Help

### 🔍 Diagnostic Information to Collect

When asking for help, please provide:

1. **System information:**

   ```bash
   python --version
   pip list | grep w2t-bkin
   docker --version
   ```

2. **Error logs:**

   ```bash
   # Docker
   docker compose logs server > logs.txt
   docker compose logs worker >> logs.txt

   # Local
   cat data/processed/subject-001/session-001/processing_log.txt
   ```

3. **Configuration:**

   ```bash
   cat configs/standard.toml
   ```

4. **Directory structure:**
   ```bash
   tree -L 4 data/raw/  # Or ls -R
   ```

### 📚 Resources

- **Documentation**: [docs/README.md](README.md)
- **FAQ**: [docs/FAQ.md](FAQ.md)
- **GitHub Issues**: [github.com/BorjaEst/w2t-bkin/issues](https://github.com/BorjaEst/w2t-bkin/issues)
- **Examples**: [examples/](../examples/)

### 🐛 Reporting Bugs

When opening a GitHub issue, include:

1. **Clear description** of the problem
2. **Steps to reproduce**
3. **Expected vs. actual behavior**
4. **System information** (Python version, OS, Docker version)
5. **Error logs** (complete, not truncated)
6. **Configuration files** (sanitized if needed)
7. **Data structure** (folder tree, file sizes)

---

## Still Stuck?

If none of these solutions work:

1. **Search existing issues**: [GitHub Issues](https://github.com/BorjaEst/w2t-bkin/issues)
2. **Open a new issue**: Include all diagnostic information above
3. **Check documentation**: You might have missed something in [Getting Started](../README.md#quick-start)

We're here to help! 🚀

---

## 📚 Navigation

- **⬅️ [Documentation Hub](README.md)**
- **📖 [Getting Started](../README.md#quick-start)**
- **❓ [FAQ](FAQ.md)**
- **💻 [CLI Reference](cli/README.md)**
- **📋 [Configuration Reference](reference/configuration-parameters.md)**
- **🐳 [Container Deployment](containerization/README.md)**
