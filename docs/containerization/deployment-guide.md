# Container Deployment Guide

## Document Information

- **Audience**: End Users (Neuroscientists, Lab Technicians)
- **Prerequisites**: Basic command-line knowledge
- **Time to Complete**: 15-30 minutes

## Overview

This guide walks you through deploying w2t-bkin using containers. Containers provide a consistent, portable environment that works across Windows, macOS, Linux, and HPC clusters without manual dependency installation.

### Why Use Containers?

✅ **No Manual Setup**: ffmpeg, Python dependencies automatically included  
✅ **Multi-Platform**: Same commands work on Windows, macOS, Linux  
✅ **Reproducible**: Same environment every time  
✅ **Distributed**: Scale to multiple machines  
✅ **Free**: All recommended tools are open-source

### What You'll Get

- **Prefect Server**: Web dashboard at http://localhost:4200 to monitor pipelines
- **Workers**: Background processes that execute your pipeline tasks
- **Persistence**: Database keeps history of all runs

### ⚠️ Important: Container Configuration

Containers require **absolute paths** in config files. A pre-configured `configs/container.toml` is provided:

```toml
[paths]
raw_root = "/data/raw"              # ✅ Absolute container path
intermediate_root = "/data/interim"  # ✅ Absolute container path
output_root = "/data/processed"      # ✅ Absolute container path
models_root = "/models"              # ✅ Absolute container path
```

**Why absolute paths?** Prefect workers copy code to temporary directories. Relative paths (like `data/raw`) would resolve incorrectly. The default deployment uses `container.toml` which is already configured with correct paths.

## Choosing a Container Runtime

You need ONE of these tools installed:

| Runtime               | Best For                | Cost                                   | Installation                                                      |
| --------------------- | ----------------------- | -------------------------------------- | ----------------------------------------------------------------- |
| **Podman Desktop** ⭐ | Everyone (recommended)  | Free                                   | [podman-desktop.io](https://podman-desktop.io)                    |
| Docker                | If already using Docker | Free (personal), Paid (>250 employees) | [docs.docker.com/get-docker](https://docs.docker.com/get-docker/) |
| Apptainer             | HPC clusters only       | Free                                   | Usually pre-installed on HPC                                      |

**Recommendation**: Install **Podman Desktop** - it's free for everyone, open-source, and has a nice GUI.

## Installation

### Step 1: Install Container Runtime

#### Option A: Podman Desktop (Recommended)

**Windows:**

1. Download installer from https://podman-desktop.io/downloads
2. Run `podman-desktop-setup.exe`
3. Launch "Podman Desktop" from Start Menu
4. Click "Initialize" button to set up Podman machine
5. Wait for "Running" status (green checkmark)

**macOS:**

```bash
# Option 1: Download from website
# Visit https://podman-desktop.io/downloads and get .dmg

# Option 2: Homebrew
brew install podman podman-desktop
```

After install:

1. Open "Podman Desktop" app
2. Click "Initialize Podman machine"
3. Wait for "Running" status

**Linux:**

```bash
# Debian/Ubuntu
sudo apt-get update
sudo apt-get install podman

# Fedora/RHEL
sudo dnf install podman

# Arch
sudo pacman -S podman
```

**Verify Installation:**

```bash
podman --version
# Should output: podman version 4.8.0 (or higher)

podman ps
# Should output: Empty table (no containers running yet)
```

#### Option B: Docker

See official guide: https://docs.docker.com/get-docker/

⚠️ **Note**: Docker Desktop requires a paid subscription for organizations with >250 employees or >$10M revenue.

**Verify Installation:**

```bash
docker --version
docker ps
```

### Step 2: Install w2t-bkin CLI

Choose installation method based on your needs:

**Option A: Minimal CLI Only** (Quick, ~30 seconds)

```bash
# Create virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install CLI only (minimal dependencies)
pip install w2t-bkin

# Verify
w2t-bkin --version
```

**Option B: Full Pipeline with All Processing Libraries** (~15 minutes)

```bash
# Create virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install with all heavy dependencies
pip install w2t-bkin[full]

# Verify
w2t-bkin --version
```

**Note**: For container-based processing, only Option A is needed on the host machine. The containers include all processing libraries. Use Option B only if you need to run pipelines locally without containers.

### Step 3: Pull Container Images

```bash
# Pull latest stable images
podman pull ghcr.io/borjaest/w2t-bkin:latest-server
podman pull ghcr.io/borjaest/w2t-bkin:latest-worker

# This may take 5-10 minutes depending on internet speed
# Images are ~1.5GB each
```

If using Docker, replace `podman` with `docker` in all commands.

## Basic Usage

### Start the Server

```bash
# Start Prefect server and database
w2t-bkin container start-server

# Output:
# 🔧 Using podman (version 4.8.0)
# 🚀 Starting Prefect server with podman...
# ⏳ Starting database...
# ⏳ Starting server...
# ✅ Server started at http://localhost:4200
# 📊 View dashboard: open http://localhost:4200
```

**Open your browser** to http://localhost:4200 - you should see the Prefect dashboard.

![Prefect Dashboard](../images/prefect-dashboard.png)

### Start Workers

Workers execute your pipeline tasks. Start as many as you have CPU cores:

```bash
# Start 4 workers (adjust based on your CPU)
w2t-bkin container start-worker --workers 4

# Output:
# 🔧 Using podman (version 4.8.0)
# 🚀 Starting 4 worker(s)...
# ✅ Worker 1 started (container: w2t-bkin-worker-1)
# ✅ Worker 2 started (container: w2t-bkin-worker-2)
# ✅ Worker 3 started (container: w2t-bkin-worker-3)
# ✅ Worker 4 started (container: w2t-bkin-worker-4)
```

Check the Prefect dashboard - you should see 4 workers registered under "Work Pools".

### Run Your Pipeline

Now you can run batch processing with the container workers:

```bash
# Process all sessions
w2t-bkin batch config.toml --max-workers 4

# Or process specific subject
w2t-bkin batch config.toml --subject subject-001 --max-workers 2
```

Monitor progress in real-time at http://localhost:4200

### Stop Containers

When you're done:

```bash
# Stop all containers
w2t-bkin container stop

# Output:
# 🛑 Stopping all containers...
# ✅ All containers stopped
```

## Advanced Configuration

### Custom Ports

If port 4200 is already in use:

```bash
w2t-bkin container start-server --port 4201
```

Update workers to use new port:

```bash
export PREFECT_API_URL=http://localhost:4201/api
w2t-bkin container start-worker
```

### Custom Data Locations

By default, containers look for data in `./data`. To use different locations, edit the `.env` file:

```bash
# Edit .env file in project root
nano .env

# Update these paths:
DATA_ROOT=./data              # Change to your data location
CONFIG_ROOT=./configs         # Config files location
MODELS_ROOT=./models          # Model files location

# Deployment defaults (optional)
DEFAULT_CONFIG_FILE=container.toml  # Which config to use
DEFAULT_MAX_WORKERS=4               # Concurrent sessions
```

After editing `.env`, restart containers:

```bash
docker compose down
docker compose up -d
```

**Note**: Paths in `.env` are **host paths** (relative to docker-compose.yml). They are mounted into containers at fixed locations (`/data`, `/models`, `/configs`).

### View Logs

```bash
# Server logs
podman logs w2t-bkin-server

# Worker logs
podman logs w2t-bkin-worker-1

# Follow logs in real-time
podman logs -f w2t-bkin-worker-1
```

### Restart Containers

```bash
# Restart server
podman restart w2t-bkin-server

# Restart all workers
podman restart w2t-bkin-worker-1 w2t-bkin-worker-2
```

## Platform-Specific Notes

### Windows (WSL2)

If using Docker Desktop on Windows, ensure WSL2 integration is enabled:

1. Open Docker Desktop
2. Settings → Resources → WSL Integration
3. Enable integration with your WSL2 distro

**Data Access**: Use WSL paths, not Windows paths:

```bash
# Good
export DATA_ROOT=/mnt/c/Users/YourName/Data

# Bad (won't work)
export DATA_ROOT=C:\Users\YourName\Data
```

### macOS

**M1/M2 Macs**: Images are built for ARM64, will work natively.

**Intel Macs**: Images will work via Rosetta emulation (slightly slower).

**File Permissions**: macOS handles permissions differently. If you get "permission denied":

```bash
# Grant container access to directories
podman machine ssh
sudo chmod -R 755 /Users/YourName/Data
exit
```

### Linux

**Rootless Podman** (default): Runs without sudo. File permissions match your user.

**Rootful Docker**: May need to adjust file ownership:

```bash
# If output files owned by root, run worker as your user
docker run --user $(id -u):$(id -g) ...
```

Or use `podman` which handles this automatically.

## HPC Deployment

For HPC clusters (Slurm, PBS), see [HPC Guide](./hpc-guide.md).

Quick overview:

1. Build Apptainer image:

   ```bash
   apptainer build w2t_bkin.sif docker://ghcr.io/borjaest/w2t-bkin:latest-worker
   ```

2. Submit Slurm job array:

   ```bash
   sbatch run_pipeline.sh
   ```

3. Monitor from local Prefect server or Prefect Cloud.

## Troubleshooting

### "No container runtime detected"

**Problem**: CLI can't find podman/docker/apptainer.

**Solutions**:

- Verify installation: `podman --version` or `docker --version`
- Restart terminal after installing
- Check PATH: `which podman`
- On Windows, ensure WSL integration enabled

### "Connection refused" on port 4200

**Problem**: Server didn't start or is on different port.

**Solutions**:

- Check server status: `podman ps | grep server`
- View server logs: `podman logs w2t-bkin-server`
- Try different port: `w2t-bkin container start-server --port 4201`
- Check firewall: Allow port 4200

### "Permission denied" accessing files

**Problem**: Container can't read/write your data directories.

**Solutions**:

- Check file permissions: `ls -l /your/data/path`
- Use podman (better permission handling than Docker)
- Set ownership: `chown -R $USER:$USER /your/data`
- On Windows: Use WSL paths (`/mnt/c/...`) not Windows paths

### "Cannot connect to Prefect API"

**Problem**: Workers can't reach server.

**Solutions**:

- Verify server running: `podman ps | grep server`
- Check network: `curl http://localhost:4200/api/health`
- Update PREFECT_API_URL:
  ```bash
  export PREFECT_API_URL=http://localhost:4200/api
  ```
- On macOS, try `host.docker.internal` instead of `localhost`

### "Out of memory" errors

**Problem**: Not enough RAM for workers.

**Solutions**:

- Reduce worker count: Start with 1-2 workers
- Increase Docker/Podman memory limit:
  - Docker Desktop: Settings → Resources → Memory
  - Podman: `podman machine set --memory 8192`
- Close other applications
- Process fewer sessions at once: `--max-workers 1`

### Workers not showing in Prefect UI

**Problem**: Workers started but not registered.

**Solutions**:

- Wait 30 seconds (registration takes time)
- Check worker logs: `podman logs w2t-bkin-worker-1`
- Verify PREFECT_API_URL matches server
- Restart workers: `podman restart w2t-bkin-worker-1`

### Image pull fails

**Problem**: Can't download images from registry.

**Solutions**:

- Check internet connection
- Try different registry mirror (if in China, use mirror)
- Use VPN if behind firewall
- Download manually:
  ```bash
  podman pull ghcr.io/borjaest/w2t-bkin:latest-server
  ```
- Build locally:
  ```bash
  git clone https://github.com/BorjaEst/w2t-bkin
  cd w2t-bkin
  podman build -t w2t-bkin:latest-server --target server .
  ```

### "Database locked" errors

**Problem**: Multiple processes accessing same SQLite database.

**Solutions**:

- Use PostgreSQL backend (production setup in docker-compose.yml)
- Don't run multiple servers
- Check for zombie processes: `podman ps -a`

## Performance Tips

### Optimize Worker Count

**Rule of thumb**: Number of workers = Number of CPU cores - 1

Check your CPU count:

```bash
# Linux/macOS
nproc  # or: sysctl -n hw.ncpu

# Windows (PowerShell)
(Get-WmiObject -Class Win32_ComputerSystem).NumberOfLogicalProcessors
```

Start with fewer workers, monitor CPU usage with `htop` or Task Manager, then increase.

### Use SSD Storage

Store data and output on SSD (not HDD) for 5-10x faster I/O.

### Persistent Database

By default, PostgreSQL data persists in Docker volume. To back up:

```bash
# Backup database
podman exec w2t-bkin-postgres pg_dump -U prefect prefect > backup.sql

# Restore
podman exec -i w2t-bkin-postgres psql -U prefect prefect < backup.sql
```

### Monitor Resources

```bash
# Real-time container stats
podman stats

# Output:
# CONTAINER       CPU %   MEM USAGE / LIMIT   NET I/O       BLOCK I/O
# w2t-bkin-worker-1  45.2%   1.5GB / 4GB        10MB / 5MB    500MB / 200MB
```

## Migration Guide

### From Native Python to Containers

Already running w2t-bkin directly with Python? Here's how to migrate:

1. **Keep existing data**: No need to move files
2. **Stop native Prefect server** (if running):
   ```bash
   # Find and kill process
   ps aux | grep "prefect server"
   kill <pid>
   ```
3. **Start container server**: `w2t-bkin container start-server`
4. **Start container workers**: `w2t-bkin container start-worker --workers 4`
5. **Run pipelines** as before: `w2t-bkin batch config.toml`

Your existing config files, data, and models work as-is.

### From Docker Compose to CLI Wrapper

Previously using `docker-compose up` manually? The CLI wrapper is easier:

**Old way**:

```bash
cd /path/to/w2t-bkin
docker compose up -d
docker compose logs -f worker
```

**New way**:

```bash
w2t-bkin container start-server
w2t-bkin container start-worker --workers 4
```

Same result, simpler commands.

## Next Steps

- **Learn Prefect UI**: Explore flow runs, logs, and metrics at http://localhost:4200
- **Batch Processing**: See [Batch Processing Guide](../batch-processing.md)
- **HPC Deployment**: Deploy on your institution's cluster with [HPC Guide](./hpc-guide.md)
- **Custom Workflows**: Create Prefect flows for custom processing pipelines
- **Monitoring**: Set up alerts for failed runs in Prefect UI

## Getting Help

- **Documentation**: https://github.com/BorjaEst/w2t-bkin/tree/main/docs
- **Issues**: https://github.com/BorjaEst/w2t-bkin/issues
- **Discussions**: https://github.com/BorjaEst/w2t-bkin/discussions
- **Prefect Docs**: https://docs.prefect.io

## Troubleshooting

### "raw_root does not exist" Error

**Cause**: Config file uses relative paths or data directory not mounted.

**Fix**:

1. Verify you're using `container.toml` (check deployment logs)
2. Ensure `container.toml` has absolute paths: `/data/raw`, `/models`, etc.
3. Check data exists: `ls -la data/raw/`
4. Verify volume mounts in `.env`

### "TOMLDecodeError: Invalid value"

**Cause**: Config file has invalid TOML syntax or fields not in schema.

**Fix**:

1. TOML doesn't support `null` - omit optional fields instead
2. Check schema in `src/w2t_bkin/config.py` for valid fields
3. Test config: `docker exec w2t-bkin-worker-1 python -c "from w2t_bkin.config import load_config; load_config('/configs/container.toml')"`

### "Extra inputs are not permitted" ValidationError

**Cause**: Config has fields that don't exist in Pydantic schema.

**Fix**: Remove invalid fields. Common issues:

- `video.enabled` → Remove (not in schema)
- `qc.enabled` → Use `qc.generate_report` instead
- `preprocessing.facemap` → Not supported, remove section

See `docs/containerization/TOML-CONFIG-FIX.md` for full details.

### Workers Not Picking Up Jobs

**Cause**: Workers not connected to correct work pool.

**Fix**:

1. Check work pool: `docker exec w2t-bkin-server prefect work-pool ls`
2. Check worker logs: `docker logs w2t-bkin-worker-1`
3. Verify `PREFECT_API_URL` matches server

### Permission Denied Errors

**Cause**: Container can't access host directories.

**Fix**:

- Linux: `chmod -R 755 data/ models/ configs/`
- macOS: Grant Docker access in System Preferences → Privacy
- Windows WSL: Use WSL paths (`/mnt/c/...`), not Windows paths

### Deployment Not Found

**Cause**: Server initialization didn't complete or deployment failed.

**Fix**:

1. Check server logs: `docker logs w2t-bkin-server | grep -i deploy`
2. Should see: "✅ Deployed: batch-processing"
3. If missing, restart server: `docker compose restart server`
4. Wait 60s for initialization, then check: `docker exec w2t-bkin-server prefect deployment ls`

## FAQ

**Q: Do I need to keep the terminal open?**

A: No. The `start-server` and `start-worker` commands run containers in detached mode (background). You can close the terminal.

**Q: How do I update to latest version?**

A:

```bash
# Pull new images
podman pull ghcr.io/borjaest/w2t-bkin:latest-server
podman pull ghcr.io/borjaest/w2t-bkin:latest-worker

# Restart containers
w2t-bkin container stop
w2t-bkin container start-server
w2t-bkin container start-worker --workers 4
```

**Q: Can I run server on one machine, workers on another?**

A: Yes! This is the distributed execution model:

Machine 1 (server):

```bash
w2t-bkin container start-server
```

Machine 2 (worker):

```bash
export PREFECT_API_URL=http://machine1-ip:4200/api
w2t-bkin container start-worker --workers 4
```

**Q: How much disk space do I need?**

A:

- Container images: ~3GB (server + worker)
- PostgreSQL database: ~100MB (for 1000s of runs)
- Your data: varies (not counted here)

**Q: Is my data copied into containers?**

A: No. Data is mounted as volumes, so containers access your files directly. No duplication.

**Q: Can I use this on shared compute cluster?**

A: Yes, but use Apptainer instead of Docker/Podman. See [HPC Guide](./hpc-guide.md).

**Q: What happens if worker crashes mid-pipeline?**

A: Prefect automatically retries (2 attempts by default, 60s delay). You'll see retry attempts in the UI.

**Q: Can I run multiple pipelines simultaneously?**

A: Yes. Prefect queues tasks and workers pick them up. Start more workers to increase parallelism.

**Q: What's the difference between container.toml and standard.toml?**

A:

- `standard.toml`: Uses relative paths (`data/raw`), works for local CLI execution
- `container.toml`: Uses absolute paths (`/data/raw`), required for containerized Prefect workers

When running via Prefect in containers, always use `container.toml` (default). When running CLI locally, use `standard.toml`.

**Q: How do I customize the config for containers?**

A:

1. Copy `configs/container.toml` to `configs/my-config.toml`
2. Modify settings (keep absolute paths in `[paths]` section!)
3. Update `.env`: `DEFAULT_CONFIG_FILE=my-config.toml`
4. Restart: `docker compose down && docker compose up -d`

**Q: Can I test config before deploying?**

A: Yes:

```bash
# Test config loads without errors
docker exec w2t-bkin-worker-1 python -c "from w2t_bkin.config import load_config; load_config('/configs/container.toml'); print('✅ Valid')"

# Test session discovery
docker exec w2t-bkin-worker-1 python -c "from w2t_bkin.utils import discover_sessions; print(f'{len(discover_sessions(\"/configs/container.toml\"))} sessions found')"
```
