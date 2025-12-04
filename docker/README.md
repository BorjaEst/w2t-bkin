# Container Deployment

This directory contains the containerization setup for w2t-bkin.

## Quick Start

### 1. Install Container Runtime

**Recommended: Podman Desktop** (free, open-source)

- Download from: https://podman-desktop.io/downloads

**Alternative: Docker**

- Download from: https://docs.docker.com/get-docker/
- ⚠️ Note: Docker Desktop requires paid license for organizations >250 employees

### 2. Start Server

```bash
# Install w2t-bkin if not already installed
pip install w2t-bkin

# Start Prefect server and database
w2t-bkin container start-server

# Access web UI at http://localhost:4200
```

### 3. Start Workers

```bash
# Start 4 worker containers
w2t-bkin container start-worker --workers 4
```

### 4. Run Pipeline

```bash
# Process all sessions
w2t-bkin batch config.toml --max-workers 4

# Or process specific subject
w2t-bkin batch config.toml --subject subject-001 --max-workers 2
```

### 5. Stop Containers

```bash
w2t-bkin container stop
```

## Commands

### Server Management

```bash
# Start server (default port 4200)
w2t-bkin container start-server

# Start on different port
w2t-bkin container start-server --port 4201

# Watch logs in foreground
w2t-bkin container start-server --follow
```

### Worker Management

```bash
# Start workers
w2t-bkin container start-worker --workers 4

# With custom config
w2t-bkin container start-worker --workers 2 --config ./configs/custom.toml
```

### Monitoring

```bash
# Show status of all containers
w2t-bkin container status

# View server logs
w2t-bkin container logs server

# Follow worker logs
w2t-bkin container logs worker --follow

# View last 100 lines
w2t-bkin container logs server --tail 100
```

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and customize:

```bash
cp .env.example .env
```

Key variables:

- `DATA_ROOT`: Path to raw data directory
- `MODELS_ROOT`: Path to pose estimation models
- `OUTPUT_ROOT`: Path for processed outputs
- `WORKER_REPLICAS`: Number of workers to start
- `PREFECT_UI_PORT`: Port for web UI (default: 4200)

### Volume Mounts

Data is mounted into containers (not copied):

- `/data` - Raw data (read-only)
- `/models` - Pose models (read-only)
- `/configs` - Configuration files (read-only)
- `/data/interim` - Intermediate outputs (read-write)
- `/data/processed` - Final outputs (read-write)

## Development

### Local Development with Hot-Reload

```bash
# Start with development compose file
podman compose -f docker-compose.yml -f docker-compose.dev.yml up

# Changes to src/ automatically reflected in containers
```

### Build Images Locally

```bash
# Build server image
podman build --target server -t w2t-bkin:server .

# Build worker image
podman build --target worker -t w2t-bkin:worker .

# Or use compose
podman compose build
```

## Troubleshooting

### "No container runtime detected"

- Install Podman Desktop or Docker
- Restart terminal after installation
- Verify: `podman --version` or `docker --version`

### "Connection refused on port 4200"

- Check if server is running: `podman ps | grep server`
- View logs: `w2t-bkin container logs server`
- Try different port: `w2t-bkin container start-server --port 4201`

### "Permission denied" errors

- Use Podman (better permission handling than Docker)
- Check file ownership: `ls -l /your/data/path`
- Ensure container user (uid 1000) can access files

### Workers not appearing in UI

- Wait 30 seconds (registration takes time)
- Check logs: `w2t-bkin container logs worker`
- Verify server is running: `w2t-bkin container status`

## Architecture

```
┌─────────────────┐
│   User Machine  │
│                 │
│  CLI Wrapper    │
└────────┬────────┘
         │
         ▼
┌────────────────────────────┐
│  Container Runtime         │
│  (Podman/Docker/Apptainer) │
└──────┬─────────────────────┘
       │
       ├──► PostgreSQL (database)
       │
       ├──► Prefect Server (orchestrator)
       │    └─► Web UI :4200
       │
       └──► Workers (executors)
            ├─► Worker 1
            ├─► Worker 2
            └─► Worker N
```

## Documentation

- **Full Guide**: [docs/containerization/deployment-guide.md](docs/containerization/deployment-guide.md)
- **HPC Deployment**: [docs/containerization/hpc-guide.md](docs/containerization/hpc-guide.md)
- **Requirements**: [docs/containerization/requirements.md](docs/containerization/requirements.md)
- **Architecture**: [docs/containerization/design.md](docs/containerization/design.md)
- **Tasks**: [docs/containerization/tasks.md](docs/containerization/tasks.md)

## Files

| File                     | Purpose                                  |
| ------------------------ | ---------------------------------------- |
| `Dockerfile`             | Multi-stage build (base, server, worker) |
| `docker-compose.yml`     | Production deployment                    |
| `docker-compose.dev.yml` | Development overrides                    |
| `docker/start-server.sh` | Server entrypoint script                 |
| `docker/start-worker.sh` | Worker entrypoint script                 |
| `.env.example`           | Environment variable template            |
| `.dockerignore`          | Build optimization                       |

## Support

- **Issues**: https://github.com/BorjaEst/w2t-bkin/issues
- **Discussions**: https://github.com/BorjaEst/w2t-bkin/discussions
- **Documentation**: https://github.com/BorjaEst/w2t-bkin/tree/main/docs
