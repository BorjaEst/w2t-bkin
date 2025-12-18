# Troubleshooting Guide

## Common Issues and Solutions

### Server and Worker Issues

#### "Port 4200 already in use"

**Problem:** Another Prefect server is running or port is occupied.

**Solution:**

```bash
# Check if Prefect server is running
w2t-bkin server status

# Stop existing server
w2t-bkin server stop

# Or use a different port
w2t-bkin server start --port 5000
```

#### "Worker extras not installed"

**Problem:** Trying to run flows that require DeepLabCut, Facemap, or other heavy processing libraries.

**Symptoms:**

- ImportError for `deeplabcut`, `facemap`, `nwbinspector`
- "No module named 'tensorflow'" errors
- Development mode (`--dev`) fails to start

**Solution:**

```bash
# Install worker extras
pip install w2t-bkin[worker]

# Or in development mode
pip install -e .[worker]
```

**Note:** Worker extras require ~600MB of additional dependencies. For production, install base package on orchestrator and worker extras only on compute nodes.

#### "Docker not running" / "Cannot connect to Docker daemon"

**Problem:** Docker Desktop (Windows/Mac) or Docker Engine (Linux) is not running.

**Solution:**

**Windows/Mac:**

- Start Docker Desktop from Applications
- Wait for Docker icon in system tray to show "running"

**Linux:**

```bash
# Start Docker service
sudo systemctl start docker

# Enable Docker to start on boot
sudo systemctl enable docker

# Check Docker status
sudo systemctl status docker
```

#### "Worker not picking up flows"

**Problem:** Worker is running but flows stay in "Scheduled" state.

**Diagnosis:**

```bash
# Check if worker is connected
# In Prefect UI: Work Pools → docker-pool → Workers tab
# Should show online worker with heartbeat

# Check worker logs
docker logs w2t-worker

# For process workers
# Check terminal where prefect worker start is running
```

**Common causes:**

1. **Wrong PREFECT_API_URL**

   ```bash
   # Linux should use
   PREFECT_API_URL=http://127.0.0.1:4200/api

   # Windows/WSL should use
   PREFECT_API_URL=http://host.docker.internal:4200/api
   ```

2. **Wrong work pool name**

   ```bash
   # Check deployment configuration in Prefect UI
   # Worker pool must match deployment pool
   prefect worker start --pool docker-pool --type docker
   ```

3. **Worker crashed**

   ```bash
   # Restart worker
   docker restart w2t-worker

   # Or for process workers, Ctrl+C and restart
   prefect worker start --pool default-pool --type process
   ```

#### "Prefect server not reachable"

**Problem:** Cannot connect to Prefect server at http://localhost:4200

**Diagnosis:**

```bash
# Check if server is running
w2t-bkin server status

# Check if port is accessible
curl http://localhost:4200/api/health
```

**Solutions:**

1. **Server not started**

   ```bash
   w2t-bkin server start
   ```

2. **Firewall blocking port**

   ```bash
   # Linux - allow port 4200
   sudo ufw allow 4200/tcp
   ```

3. **Server crashed**

   ```bash
   # Check logs
   cat .prefect/server.log

   # Restart server
   w2t-bkin server restart
   ```

### Data and File Issues

#### "Session not found" / "No sessions discovered"

**Problem:** `w2t-bkin discover` returns empty or session not found in UI.

**Diagnosis:**

```bash
# Check directory structure
w2t-bkin data validate /path/to/experiment

# List sessions manually
w2t-bkin discover configs/standard.toml --format plain
```

**Requirements for valid session:**

- Must have `session.toml` OR `metadata.toml` in session directory
- Session directory must be: `raw_root/subject-XXX/session-YYY/`
- Config file must specify correct `raw_root` path

**Solution:**

```bash
# Check config raw_root
grep raw_root configs/standard.toml

# Verify session metadata exists
ls -la data/raw/subject-001/session-001/
# Should contain: session.toml or metadata.toml

# Add missing session
w2t-bkin data add-session /path/to/experiment subject-001 session-001 -y
```

#### "Config file not found"

**Problem:** Pipeline cannot find configuration TOML file.

**Solution:**

```bash
# Use absolute path
w2t-bkin server start --config /full/path/to/config.toml

# Or relative from experiment directory
cd /path/to/experiment
w2t-bkin server start --config configs/standard.toml

# Check if file exists
ls -la configs/standard.toml
```

#### "Frame/TTL mismatch" or "Sync validation failed"

**Problem:** Video frame counts don't match TTL pulse counts.

**Symptoms:**

- `Camera frame count (3120) != TTL count (3150)`
- Sync validation errors in pipeline

**Causes:**

- Dropped video frames during recording
- TTL pulses before/after video recording
- Camera stopped recording early

**Solutions:**

1. **Allow mismatch with tolerance**

   ```toml
   # In session.toml or metadata.toml
   [sync.validation]
   frame_tolerance = 5  # Allow up to 5 frame difference
   ```

2. **Skip sync validation** (not recommended for analysis)

   ```bash
   # In Prefect UI, set skip_ttl=true parameter
   ```

3. **Manual sync recovery**
   ```bash
   # Use sync recovery utilities
   # See examples/sync_recovery_demo.py
   ```

### Processing and Pipeline Issues

#### "GPU not available" / "CUDA errors"

**Problem:** DeepLabCut or other GPU-accelerated tools cannot find GPU.

**Diagnosis:**

```bash
# Check NVIDIA GPU availability
nvidia-smi

# Check CUDA availability in Python
python -c "import tensorflow as tf; print(tf.config.list_physical_devices('GPU'))"
```

**Solutions:**

1. **Install NVIDIA drivers** (if no GPU detected)

   ```bash
   # Ubuntu/Debian
   sudo ubuntu-drivers autoinstall
   sudo reboot
   ```

2. **Use CPU instead**

   ```toml
   # In config.toml
   [preprocessing]
   gpu_index = -1  # Force CPU
   ```

3. **Docker GPU access** (for Docker workers)
   ```bash
   # Install nvidia-container-toolkit
   # Add --gpus all to docker run command
   docker run --gpus all ...
   ```

#### "NWB validation failed"

**Problem:** Generated NWB file fails validation.

**Diagnosis:**

```bash
# Validate NWB file manually
w2t-bkin validate path/to/file.nwb

# Inspect NWB contents
w2t-bkin inspect path/to/file.nwb
```

**Common validation errors:**

1. **Missing required metadata**

   - Check `session.toml` has all required fields
   - Verify experimenter, lab, institution are specified

2. **Invalid timestamps**

   - Check camera FPS in metadata
   - Verify TTL timing file exists and is readable

3. **Schema violations**
   - Check NWB extensions are installed: `ndx-pose`, `ndx-events`, `ndx-structured-behavior`
   - Reinstall if needed: `pip install -e nwb-extensions/ndx-pose/`

#### "DeepLabCut model not found"

**Problem:** Cannot find pose estimation model.

**Solution:**

```bash
# Check model path in config
grep model_path configs/standard.toml

# Verify model exists
ls -la models/iteration-1/BA_W2T_cam0.newOct30-trainset95shuffle1/

# Update config if model moved
# Edit configs/standard.toml
[preprocessing.pose.dlc]
model_path = "/full/path/to/model"
```

#### "Permission denied" errors

**Problem:** Cannot write to output directories.

**Solution:**

```bash
# Check directory permissions
ls -la data/interim/
ls -la data/processed/

# Fix permissions (Linux)
sudo chown -R $USER:$USER data/
chmod -R u+w data/

# For Docker workers, ensure volume mounts have correct permissions
```

### Development Mode Issues

#### "Development mode requires worker extras"

**Problem:** Using `w2t-bkin server start --dev` without worker dependencies.

**Solution:**

```bash
# Install worker extras
pip install w2t-bkin[worker]

# Or use production mode (no worker extras needed for server)
w2t-bkin server start  # Without --dev
# Then start workers separately
```

#### "Config not found in development mode"

**Problem:** Dev mode cannot inject runtime config.

**Diagnosis:**

```bash
# Check if config path is absolute
w2t-bkin server start --dev --config /full/path/to/config.toml

# Check environment variable
echo $W2T_RUNTIME_CONFIG_JSON
```

**Solution:**

```bash
# Use absolute path for config
cd /path/to/experiment
w2t-bkin server start --dev --config $(pwd)/configs/standard.toml
```

### Network and Connectivity Issues

#### "host.docker.internal not found" (Windows/WSL)

**Problem:** Docker container cannot reach host Prefect server.

**Solution:**

```bash
# For WSL2, use WSL IP instead
ip addr show eth0 | grep inet

# Use that IP in PREFECT_API_URL
docker run -e PREFECT_API_URL=http://172.XX.XX.XX:4200/api ...
```

#### "Cannot pull Docker image"

**Problem:** `docker pull ghcr.io/borjaest/w2t-bkin:latest` fails.

**Solutions:**

1. **Not logged in to GitHub Container Registry**

   ```bash
   # Login with GitHub Personal Access Token
   echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin
   ```

2. **Network issues**

   ```bash
   # Check Docker Hub connectivity
   docker pull hello-world

   # Try with different DNS
   # Edit /etc/docker/daemon.json
   {
     "dns": ["8.8.8.8", "8.8.4.4"]
   }
   sudo systemctl restart docker
   ```

## Getting Additional Help

### Enable Debug Logging

```bash
# Set log level to DEBUG
w2t-bkin server start --log-level DEBUG

# In Python API
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Check Logs

**Server logs:**

```bash
cat .prefect/server.log
```

**Worker logs (Docker):**

```bash
docker logs w2t-worker
docker logs -f w2t-worker  # Follow logs
```

**Worker logs (Process):**

- Check terminal where `prefect worker start` is running

**Flow run logs:**

- Prefect UI → Flow Runs → Select run → Logs tab

### Debugging Workflow

1. **Start with simple test**

   ```bash
   # Test single session in dev mode
   w2t-bkin server start --dev --log-level DEBUG
   ```

2. **Check each component**

   - Server status: `w2t-bkin server status`
   - Session discovery: `w2t-bkin discover config.toml`
   - Data validation: `w2t-bkin data validate /path/to/experiment`

3. **Isolate the issue**

   - Try with `--skip-pose`, `--skip-bpod`, `--skip-ttl` flags in UI
   - Process single modality at a time

4. **Review logs systematically**
   - Server logs for startup issues
   - Worker logs for execution issues
   - Flow run logs for pipeline issues

### Report Issues

When reporting bugs, include:

1. **Environment info**

   ```bash
   w2t-bkin version
   python --version
   docker --version
   pip list | grep -E "(w2t-bkin|prefect|pynwb|deeplabcut)"
   ```

2. **Configuration**

   - Anonymized config file (remove sensitive paths)
   - Installation method (pip, pip -e, Docker)
   - OS and platform (Linux, Windows, WSL, Mac)

3. **Reproduction steps**

   - Exact commands run
   - Expected vs. actual behavior
   - Error messages and logs

4. **Submit to GitHub Issues**
   - https://github.com/BorjaEst/w2t-bkin/issues
