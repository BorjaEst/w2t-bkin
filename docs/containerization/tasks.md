# Containerization Implementation Tasks

## Document Information

- **Created**: 2025-12-04
- **Status**: Active
- **Sprint**: Containerization v1.0
- **Dependencies**: requirements.md, design.md

## Task Breakdown

### Phase 1: Core Infrastructure (Priority: MUST HAVE)

#### TASK-001: Create Base Dockerfile

**Description**: Create multi-stage Dockerfile with base, server, and worker targets.

**Dependencies**: None

**Acceptance Criteria**:

- [ ] Dockerfile builds successfully with `docker build --target base .`
- [ ] Server image builds: `docker build --target server -t w2t-bkin:server .`
- [ ] Worker image builds: `docker build --target worker -t w2t-bkin:worker .`
- [ ] All images run as non-root user (uid 1000)
- [ ] ffmpeg installed and functional: `docker run w2t-bkin:worker ffmpeg -version`
- [ ] Python package installed: `docker run w2t-bkin:worker python -m w2t_bkin.cli --version`
- [ ] Image size < 2GB compressed

**Implementation Details**:

```dockerfile
# Location: Dockerfile (root of repo)

FROM python:3.10-slim AS base
LABEL maintainer="BorjaEst"
LABEL org.opencontainers.image.source="https://github.com/BorjaEst/w2t-bkin"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1-mesa-glx \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 -s /bin/bash w2t

# Install Python package
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
RUN pip install --no-cache-dir -e .

# Switch to non-root user
USER w2t

# Server stage
FROM base AS server
USER root
RUN pip install --no-cache-dir prefect[server]>=2.14.0
USER w2t

COPY --chmod=755 docker/start-server.sh /usr/local/bin/
EXPOSE 4200
ENTRYPOINT ["/usr/local/bin/start-server.sh"]

# Worker stage
FROM base AS worker
COPY --chmod=755 docker/start-worker.sh /usr/local/bin/
ENTRYPOINT ["/usr/local/bin/start-worker.sh"]
```

**Estimated Effort**: 4 hours

**Assignee**: TBD

**Status**: ⬜ NOT STARTED

---

#### TASK-002: Create Entrypoint Scripts

**Description**: Create bash scripts for server and worker initialization.

**Dependencies**: TASK-001

**Acceptance Criteria**:

- [ ] `docker/start-server.sh` starts Prefect server and creates work pool
- [ ] Server waits for PostgreSQL to be ready before starting
- [ ] `docker/start-worker.sh` waits for server health check before connecting
- [ ] Worker logs show successful connection to server
- [ ] Scripts handle SIGTERM gracefully for clean shutdown
- [ ] Scripts are executable (chmod +x)

**Implementation Details**:

```bash
# Location: docker/start-server.sh

#!/bin/bash
set -euo pipefail

echo "🚀 Starting Prefect server..."

# Start server in background
prefect server start \
    --host "${PREFECT_SERVER_API_HOST:-0.0.0.0}" \
    --port "${PREFECT_SERVER_API_PORT:-4200}" &
SERVER_PID=$!

# Wait for server to be ready
echo "⏳ Waiting for server to be ready..."
until curl -sf "http://localhost:${PREFECT_SERVER_API_PORT:-4200}/api/health" > /dev/null 2>&1; do
    sleep 2
done

echo "✅ Server ready at http://localhost:${PREFECT_SERVER_API_PORT:-4200}"

# Create default work pool if not exists
echo "📋 Setting up work pool..."
prefect work-pool create --type process docker-pool 2>/dev/null || echo "Work pool already exists"

# Keep server running and forward signals
trap "kill $SERVER_PID" SIGTERM SIGINT
wait $SERVER_PID
```

```bash
# Location: docker/start-worker.sh

#!/bin/bash
set -euo pipefail

echo "🔧 Starting Prefect worker..."

# Wait for server to be available
PREFECT_API_URL="${PREFECT_API_URL:-http://server:4200/api}"
echo "⏳ Waiting for Prefect server at ${PREFECT_API_URL}..."

MAX_RETRIES=30
RETRY_COUNT=0

until curl -sf "${PREFECT_API_URL}/health" > /dev/null 2>&1; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "❌ Failed to connect to Prefect server after ${MAX_RETRIES} attempts"
        exit 1
    fi
    echo "Retry ${RETRY_COUNT}/${MAX_RETRIES}..."
    sleep 5
done

echo "✅ Connected to Prefect server"

# Start worker
WORKER_NAME="${WORKER_NAME:-worker-$(hostname)}"
WORK_POOL="${WORK_POOL:-docker-pool}"

echo "🏃 Starting worker: ${WORKER_NAME} on pool: ${WORK_POOL}"

exec prefect worker start \
    --pool "${WORK_POOL}" \
    --name "${WORKER_NAME}" \
    --type process
```

**Estimated Effort**: 3 hours

**Assignee**: TBD

**Status**: ⬜ NOT STARTED

---

#### TASK-003: Create Docker Compose Configuration

**Description**: Create docker-compose.yml for production deployment.

**Dependencies**: TASK-001, TASK-002

**Acceptance Criteria**:

- [ ] `docker compose up` starts all services (postgres, server, worker)
- [ ] Prefect UI accessible at http://localhost:4200
- [ ] Worker successfully connects to server
- [ ] PostgreSQL data persists across restarts (named volume)
- [ ] Environment variables can override defaults
- [ ] Health checks work for all services
- [ ] Graceful shutdown with `docker compose down`

**Implementation Details**:

```yaml
# Location: docker-compose.yml

version: "3.8"

services:
  postgres:
    image: postgres:14-alpine
    container_name: w2t-bkin-postgres
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-prefect}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-prefect}
      POSTGRES_DB: ${POSTGRES_DB:-prefect}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-prefect}"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    networks:
      - w2t-network

  server:
    build:
      context: .
      dockerfile: Dockerfile
      target: server
    container_name: w2t-bkin-server
    ports:
      - "${PREFECT_UI_PORT:-4200}:4200"
    environment:
      PREFECT_API_DATABASE_CONNECTION_URL: postgresql+asyncpg://${POSTGRES_USER:-prefect}:${POSTGRES_PASSWORD:-prefect}@postgres:5432/${POSTGRES_DB:-prefect}
      PREFECT_SERVER_API_HOST: 0.0.0.0
      PREFECT_SERVER_API_PORT: 4200
    depends_on:
      postgres:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:4200/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    restart: unless-stopped
    networks:
      - w2t-network

  worker:
    build:
      context: .
      dockerfile: Dockerfile
      target: worker
    environment:
      PREFECT_API_URL: http://server:4200/api
      WORK_POOL: ${WORK_POOL:-docker-pool}
    volumes:
      - ${DATA_ROOT:-./data}:/data
      - ${MODELS_ROOT:-./models}:/models:ro
      - ${CONFIG_ROOT:-./configs}:/configs:ro
    depends_on:
      server:
        condition: service_healthy
    deploy:
      replicas: ${WORKER_REPLICAS:-1}
    restart: unless-stopped
    networks:
      - w2t-network

volumes:
  postgres_data:
    driver: local

networks:
  w2t-network:
    driver: bridge
```

**Estimated Effort**: 3 hours

**Assignee**: TBD

**Status**: ⬜ NOT STARTED

---

#### TASK-004: Create Development Compose Override

**Description**: Create docker-compose.dev.yml for local development with hot-reload.

**Dependencies**: TASK-003

**Acceptance Criteria**:

- [ ] `docker compose -f docker-compose.yml -f docker-compose.dev.yml up` works
- [ ] Source code mounted as volume for hot-reload
- [ ] Debug logging enabled (PREFECT_LOGGING_LEVEL=DEBUG)
- [ ] Local data directories auto-mounted
- [ ] Can rebuild with `--build` flag

**Implementation Details**:

```yaml
# Location: docker-compose.dev.yml

version: "3.8"

services:
  server:
    build:
      context: .
      dockerfile: Dockerfile
      target: server
    volumes:
      - ./src:/app/src:ro
    environment:
      PREFECT_LOGGING_LEVEL: DEBUG
      PREFECT_LOGGING_TO_API_ENABLED: "true"

  worker:
    build:
      context: .
      dockerfile: Dockerfile
      target: worker
    volumes:
      - ./src:/app/src:ro
      - ./data:/data
      - ./models:/models
      - ./configs:/configs
      - ./temp:/temp
    environment:
      PREFECT_LOGGING_LEVEL: DEBUG
```

**Estimated Effort**: 1 hour

**Assignee**: TBD

**Status**: ⬜ NOT STARTED

---

### Phase 2: CLI Wrapper (Priority: MUST HAVE)

#### TASK-005: Implement Container Runtime Detection

**Description**: Create Python module to detect available container runtime.

**Dependencies**: None

**Acceptance Criteria**:

- [ ] Detects Podman (priority 1)
- [ ] Detects Docker (priority 2)
- [ ] Detects Apptainer/Singularity (priority 3)
- [ ] Returns enum ContainerRuntime.NONE if nothing found
- [ ] Verifies Docker daemon is running (not just binary present)
- [ ] Unit tests for all detection paths

**Implementation Details**:

```python
# Location: src/w2t_bkin/container/runtime.py

from enum import Enum
from typing import Optional
import shutil
import subprocess
from pathlib import Path

class ContainerRuntime(Enum):
    """Available container runtimes in priority order."""
    PODMAN = "podman"
    DOCKER = "docker"
    APPTAINER = "apptainer"
    SINGULARITY = "singularity"
    NONE = None

def detect_runtime() -> ContainerRuntime:
    """
    Detect available container runtime.

    Priority: podman > docker > apptainer > singularity

    Returns:
        ContainerRuntime enum indicating detected runtime.
    """
    # Check Podman
    if shutil.which("podman"):
        return ContainerRuntime.PODMAN

    # Check Docker (verify daemon is running)
    if shutil.which("docker"):
        try:
            result = subprocess.run(
                ["docker", "info"],
                check=True,
                capture_output=True,
                timeout=5,
                text=True
            )
            if result.returncode == 0:
                return ContainerRuntime.DOCKER
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass

    # Check Apptainer
    if shutil.which("apptainer"):
        return ContainerRuntime.APPTAINER

    # Check Singularity (older name)
    if shutil.which("singularity"):
        return ContainerRuntime.SINGULARITY

    return ContainerRuntime.NONE

def get_runtime_version(runtime: ContainerRuntime) -> Optional[str]:
    """Get version string for a runtime."""
    if runtime == ContainerRuntime.NONE:
        return None

    try:
        result = subprocess.run(
            [runtime.value, "--version"],
            capture_output=True,
            timeout=5,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
```

**Estimated Effort**: 2 hours

**Assignee**: TBD

**Status**: ⬜ NOT STARTED

---

#### TASK-006: Implement Container Orchestrator

**Description**: Create Python module to start/stop containers via detected runtime.

**Dependencies**: TASK-005

**Acceptance Criteria**:

- [ ] `start_server()` launches server stack (postgres + server)
- [ ] `start_workers()` launches N worker containers
- [ ] `stop_all()` gracefully shuts down all containers
- [ ] `show_status()` displays running containers and health
- [ ] Works with both Docker and Podman
- [ ] Handles errors gracefully with helpful messages

**Implementation Details**:

```python
# Location: src/w2t_bkin/container/orchestrator.py

import subprocess
import sys
from pathlib import Path
from typing import Optional
import click
from .runtime import ContainerRuntime, detect_runtime

def start_server(
    runtime: ContainerRuntime,
    port: int = 4200,
    detach: bool = True,
    compose_file: Optional[Path] = None
) -> None:
    """
    Start Prefect server stack.

    Args:
        runtime: Container runtime to use
        port: Port for Prefect UI (default: 4200)
        detach: Run in background (default: True)
        compose_file: Path to docker-compose.yml (auto-detected if None)
    """
    if runtime not in [ContainerRuntime.DOCKER, ContainerRuntime.PODMAN]:
        click.echo(f"❌ {runtime.value} not supported for compose", err=True)
        sys.exit(1)

    if compose_file is None:
        compose_file = Path(__file__).parent.parent.parent.parent / "docker-compose.yml"

    cmd = [
        runtime.value, "compose",
        "-f", str(compose_file),
        "-p", "w2t-bkin",
        "up"
    ]

    if detach:
        cmd.append("-d")

    cmd.extend(["postgres", "server"])

    click.echo(f"🚀 Starting Prefect server with {runtime.value}...")

    try:
        subprocess.run(cmd, check=True)
        if detach:
            click.echo(f"✅ Server started at http://localhost:{port}")
            click.echo("📊 View dashboard: open http://localhost:4200")
    except subprocess.CalledProcessError as e:
        click.echo(f"❌ Failed to start server: {e}", err=True)
        sys.exit(1)

def start_workers(
    runtime: ContainerRuntime,
    count: int = 1,
    config_path: Optional[str] = None
) -> None:
    """Start worker container(s)."""
    # Implementation similar to start_server
    pass

def stop_all(runtime: ContainerRuntime) -> None:
    """Stop all w2t-bkin containers."""
    if runtime not in [ContainerRuntime.DOCKER, ContainerRuntime.PODMAN]:
        click.echo(f"❌ {runtime.value} not supported", err=True)
        sys.exit(1)

    cmd = [
        runtime.value, "compose",
        "-p", "w2t-bkin",
        "down"
    ]

    click.echo(f"🛑 Stopping all containers...")
    subprocess.run(cmd, check=True)
    click.echo("✅ All containers stopped")

def show_status(runtime: ContainerRuntime) -> None:
    """Show status of all containers."""
    # Implementation
    pass
```

**Estimated Effort**: 6 hours

**Assignee**: TBD

**Status**: ⬜ NOT STARTED

---

#### TASK-007: Add CLI Container Commands

**Description**: Extend CLI with container subcommands.

**Dependencies**: TASK-006

**Acceptance Criteria**:

- [ ] `w2t-bkin container start-server` works
- [ ] `w2t-bkin container start-worker` works
- [ ] `w2t-bkin container stop` works
- [ ] `w2t-bkin container status` works
- [ ] Helpful error messages when no runtime detected
- [ ] `--help` text clear and comprehensive

**Implementation Details**:

```python
# Location: src/w2t_bkin/cli.py (additions)

@cli.group()
def container():
    """Container orchestration commands."""
    pass

@container.command()
@click.option("--port", default=4200, help="Prefect UI port")
@click.option("--detach/--follow", "-d", default=True, help="Run in background")
def start_server(port: int, detach: bool):
    """Start Prefect server and database."""
    from w2t_bkin.container import runtime, orchestrator

    rt = runtime.detect_runtime()
    if rt == runtime.ContainerRuntime.NONE:
        click.echo("❌ No container runtime detected.", err=True)
        click.echo("\nPlease install one of the following:", err=True)
        click.echo("  • Podman Desktop (recommended): https://podman-desktop.io/", err=True)
        click.echo("  • Docker: https://docs.docker.com/get-docker/", err=True)
        click.echo("  • Apptainer: https://apptainer.org/", err=True)
        raise click.Abort()

    version = runtime.get_runtime_version(rt)
    click.echo(f"🔧 Using {rt.value} ({version})")

    orchestrator.start_server(rt, port=port, detach=detach)

# Similar for other commands...
```

**Estimated Effort**: 4 hours

**Assignee**: TBD

**Status**: ⬜ NOT STARTED

---

### Phase 3: CI/CD & Registry (Priority: MUST HAVE)

#### TASK-008: Create GitHub Actions Workflow

**Description**: Automate container image builds and push to GHCR.

**Dependencies**: TASK-001, TASK-002

**Acceptance Criteria**:

- [ ] Workflow triggers on push to main/dev and tags
- [ ] Builds multi-platform images (amd64, arm64)
- [ ] Pushes to ghcr.io/borjaest/w2t-bkin
- [ ] Tags images correctly (latest, v\*, branch names)
- [ ] Build completes in < 10 minutes
- [ ] Uses layer caching for faster builds

**Implementation Details**:

```yaml
# Location: .github/workflows/build-images.yml

name: Build Container Images

on:
  push:
    branches: [main, dev]
    tags: ["v*"]
  pull_request:
    branches: [main]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to Container Registry
        if: github.event_name != 'pull_request'
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=ref,event=branch
            type=ref,event=pr
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=raw,value=latest,enable={{is_default_branch}}

      - name: Build and push Server image
        uses: docker/build-push-action@v5
        with:
          context: .
          target: server
          push: ${{ github.event_name != 'pull_request' }}
          tags: ${{ steps.meta.outputs.tags }}-server
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
          platforms: linux/amd64,linux/arm64

      - name: Build and push Worker image
        uses: docker/build-push-action@v5
        with:
          context: .
          target: worker
          push: ${{ github.event_name != 'pull_request' }}
          tags: ${{ steps.meta.outputs.tags }}-worker
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
          platforms: linux/amd64,linux/arm64
```

**Estimated Effort**: 4 hours

**Assignee**: TBD

**Status**: ⬜ NOT STARTED

---

#### TASK-009: Add Security Scanning

**Description**: Integrate Trivy to scan images for vulnerabilities.

**Dependencies**: TASK-008

**Acceptance Criteria**:

- [ ] Trivy scans run on every image build
- [ ] Fails build if HIGH or CRITICAL vulnerabilities found
- [ ] Scan results uploaded to GitHub Security tab
- [ ] Scheduled daily scans on latest image

**Implementation Details**:

```yaml
# Add to .github/workflows/build-images.yml

- name: Run Trivy vulnerability scanner
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ steps.meta.outputs.version }}-worker
    format: "sarif"
    output: "trivy-results.sarif"
    severity: "HIGH,CRITICAL"
    exit-code: "1"

- name: Upload Trivy results to GitHub Security
  if: always()
  uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: "trivy-results.sarif"
```

**Estimated Effort**: 2 hours

**Assignee**: TBD

**Status**: ⬜ NOT STARTED

---

### Phase 4: Testing (Priority: SHOULD HAVE)

#### TASK-010: Write Container Integration Tests

**Description**: Test containers start, communicate, and execute pipelines.

**Dependencies**: TASK-003, TASK-006

**Acceptance Criteria**:

- [ ] Test server starts and responds to health check
- [ ] Test worker connects to server
- [ ] Test pipeline execution via container
- [ ] Test volume mounts work correctly
- [ ] Tests run in CI on every PR
- [ ] Tests clean up containers after execution

**Implementation Details**:

```python
# Location: tests/integration/test_containers.py

import pytest
import subprocess
import time
import requests
from pathlib import Path

@pytest.fixture(scope="module")
def docker_compose():
    """Start docker compose stack for testing."""
    # Start services
    subprocess.run(
        ["docker", "compose", "-f", "docker-compose.yml", "-p", "w2t-test", "up", "-d"],
        check=True
    )

    # Wait for health
    time.sleep(30)

    yield

    # Cleanup
    subprocess.run(
        ["docker", "compose", "-p", "w2t-test", "down", "-v"],
        check=True
    )

def test_server_health(docker_compose):
    """Test Prefect server is healthy."""
    response = requests.get("http://localhost:4200/api/health", timeout=10)
    assert response.status_code == 200

def test_worker_registration(docker_compose):
    """Test worker registers with server."""
    # Query Prefect API for workers
    response = requests.get("http://localhost:4200/api/work_pools/docker-pool/workers", timeout=10)
    assert response.status_code == 200
    workers = response.json()
    assert len(workers) > 0

def test_pipeline_execution(docker_compose, tmp_path):
    """Test pipeline runs via container."""
    # Create minimal config
    config = tmp_path / "config.toml"
    config.write_text("""
[paths]
raw_root = "/data/raw"
intermediate_root = "/data/interim"
output_root = "/data/processed"
    """)

    # Run pipeline
    result = subprocess.run(
        [
            "docker", "exec", "w2t-test-worker-1",
            "python", "-m", "w2t_bkin.cli", "run",
            str(config), "subject-001", "session-001"
        ],
        capture_output=True,
        text=True
    )

    # Should fail gracefully (no data), but CLI should work
    assert "subject-001" in result.stdout or "subject-001" in result.stderr
```

**Estimated Effort**: 6 hours

**Assignee**: TBD

**Status**: ⬜ NOT STARTED

---

### Phase 5: Documentation (Priority: MUST HAVE)

#### TASK-011: Write Quick Start Guide

**Description**: User documentation for getting started with containers.

**Dependencies**: TASK-007

**Acceptance Criteria**:

- [ ] Step-by-step instructions from zero to running pipeline
- [ ] Covers Windows (WSL2), macOS, Linux
- [ ] Explains runtime installation (Podman Desktop recommended)
- [ ] Shows how to access Prefect UI
- [ ] Includes troubleshooting section
- [ ] Screenshots/GIFs of key steps

**Implementation Details**:

````markdown
# Location: docs/containerization/quick-start.md

# Quick Start: Containerized Deployment

## Prerequisites

- **Container Runtime**: Podman Desktop (recommended), Docker, or Apptainer
- **Disk Space**: 5GB free
- **Memory**: 4GB RAM minimum

## Step 1: Install Runtime

### Option A: Podman Desktop (Recommended - Free & Open Source)

**Windows/macOS**:

1. Download from https://podman-desktop.io/downloads
2. Run installer
3. Open Podman Desktop
4. Click "Initialize" to set up Podman machine

**Linux**:

```bash
sudo apt-get install podman podman-compose  # Debian/Ubuntu
# or
sudo dnf install podman podman-compose      # Fedora/RHEL
```
````

### Option B: Docker

See: https://docs.docker.com/get-docker/

⚠️ **Note**: Docker Desktop requires paid license for organizations >250 employees.

## Step 2: Pull Container Images

```bash
# Pull latest images
podman pull ghcr.io/borjaest/w2t-bkin:latest-server
podman pull ghcr.io/borjaest/w2t-bkin:latest-worker
```

## Step 3: Start Server

```bash
# Install w2t-bkin CLI (if not already installed)
pip install w2t-bkin

# Start server stack
w2t-bkin container start-server

# Output:
# 🔧 Using podman (version 4.8.0)
# 🚀 Starting Prefect server with podman...
# ✅ Server started at http://localhost:4200
# 📊 View dashboard: open http://localhost:4200
```

## Step 4: Access Web UI

Open browser to http://localhost:4200

You should see the Prefect dashboard.

## Step 5: Start Workers

```bash
# Start 2 worker containers
w2t-bkin container start-worker --workers 2

# Output:
# 🔧 Using podman (version 4.8.0)
# 🚀 Starting 2 worker(s)...
# ✅ Workers started
```

## Step 6: Run Pipeline

```bash
# Run batch processing
w2t-bkin batch config.toml --max-workers 4
```

Monitor progress in the Prefect UI at http://localhost:4200

## Troubleshooting

### "No container runtime detected"

**Solution**: Install Podman Desktop or Docker, then restart terminal.

### "Connection refused on port 4200"

**Solution**:

- Check if server is running: `podman ps`
- Check logs: `podman logs w2t-bkin-server`
- Try different port: `w2t-bkin container start-server --port 4201`

### "Permission denied" errors

**Solution**: Check volume mount paths in `docker-compose.yml` match your data locations.

## Next Steps

- [Platform-Specific Guides](./platform-guides.md)
- [HPC/Apptainer Deployment](./hpc-guide.md)
- [Kubernetes Deployment](./kubernetes-guide.md)

````

**Estimated Effort**: 6 hours

**Assignee**: TBD

**Status**: ⬜ NOT STARTED

---

#### TASK-012: Write HPC/Apptainer Guide

**Description**: Documentation for deploying on HPC clusters with Apptainer.

**Dependencies**: TASK-001

**Acceptance Criteria**:
- [ ] Instructions for building .sif from OCI image
- [ ] Example Slurm job scripts
- [ ] Bind mount examples for HPC storage
- [ ] Prefect server deployment options (local vs. head node)
- [ ] Troubleshooting HPC-specific issues

**Implementation Details**:

```markdown
# Location: docs/containerization/hpc-guide.md

# HPC Deployment with Apptainer

## Overview

This guide covers deploying w2t-bkin on HPC clusters using Apptainer (formerly Singularity).

## Why Apptainer?

- **Rootless**: No sudo required (HPC security requirement)
- **OCI Compatible**: Works with Docker images
- **HPC Optimized**: Better file I/O, MPI support
- **EBRAINS Standard**: Used across European neuroscience infrastructure

## Step 1: Build Apptainer Image

On HPC login node:

```bash
# Load Apptainer module (cluster-specific)
module load apptainer

# Build .sif from GHCR
apptainer build w2t_bkin.sif docker://ghcr.io/borjaest/w2t-bkin:latest-worker

# Verify
apptainer inspect w2t_bkin.sif
````

## Step 2: Test Locally

```bash
# Run CLI help
apptainer exec w2t_bkin.sif python -m w2t_bkin.cli --help

# Test with data
apptainer exec \
    --bind /scratch/$USER/data:/data \
    --bind /scratch/$USER/models:/models \
    w2t_bkin.sif \
    python -m w2t_bkin.cli discover /data/config.toml
```

## Step 3: Create Slurm Job Script

```bash
#!/bin/bash
#SBATCH --job-name=w2t-bkin
#SBATCH --time=02:00:00
#SBATCH --mem=8GB
#SBATCH --cpus-per-task=4
#SBATCH --output=logs/w2t_%A_%a.out
#SBATCH --error=logs/w2t_%A_%a.err
#SBATCH --array=1-10  # Process 10 sessions in parallel

module load apptainer

# Get session from array
SUBJECT_ID=$(sed -n "${SLURM_ARRAY_TASK_ID}p" sessions.txt | cut -f1)
SESSION_ID=$(sed -n "${SLURM_ARRAY_TASK_ID}p" sessions.txt | cut -f2)

echo "Processing ${SUBJECT_ID} / ${SESSION_ID}"

apptainer exec \
    --bind /scratch/$USER/data:/data \
    --bind /scratch/$USER/models:/models \
    --bind /scratch/$USER/output:/output \
    w2t_bkin.sif \
    python -m w2t_bkin.cli run \
        /data/config.toml \
        ${SUBJECT_ID} \
        ${SESSION_ID}

echo "Completed ${SUBJECT_ID} / ${SESSION_ID}"
```

## Step 4: Submit Job Array

```bash
# Create session list
w2t-bkin discover config.toml --format tsv > sessions.txt

# Submit array job
sbatch run_pipeline.sh

# Monitor
squeue -u $USER
```

## Prefect Server Options

### Option A: Local Prefect Server (Simplest)

Run Prefect server on your local machine, workers on HPC connect back:

```bash
# Local machine: Start server
w2t-bkin container start-server

# HPC: Connect workers
export PREFECT_API_URL="http://your-machine.edu:4200/api"
apptainer exec w2t_bkin.sif prefect worker start --pool hpc-pool
```

### Option B: Prefect Cloud (Recommended for Production)

Use Prefect Cloud (free tier available):

```bash
# HPC: Authenticate
export PREFECT_API_KEY="your-api-key"
export PREFECT_API_URL="https://api.prefect.cloud/..."

# Start workers
apptainer exec w2t_bkin.sif prefect worker start --pool hpc-pool
```

### Option C: Server on Head Node

Deploy Prefect server on HPC head node (if allowed):

```bash
# Head node: Start server (non-container)
module load python/3.10
pip install --user prefect
prefect server start --host 0.0.0.0 --port 4200
```

## Troubleshooting

### "Permission denied" on /home

Apptainer mounts /home by default. Disable with `--no-home`:

```bash
apptainer exec --no-home --bind /scratch/$USER:/data ...
```

### "Database locked" errors

Use local /tmp for SQLite:

```bash
export APPTAINER_TMPDIR=/scratch/$USER/tmp
```

### Slow I/O

Use `--bind` for data directories, avoid image overlays:

```bash
# Good
--bind /scratch/$USER/data:/data

# Bad (slow)
--overlay /scratch/$USER/data
```

## Performance Tips

1. **Pre-stage data**: Copy to local node `/tmp` before processing
2. **Use SSD scratch**: If available, use SSD-backed scratch space
3. **Parallel I/O**: Ensure ffmpeg can read from parallel filesystem
4. **Resource requests**: Request adequate memory (8GB+ per worker)

## EBRAINS Integration

For EBRAINS infrastructure, follow their guidelines:

- https://ebrains.eu/service/high-performance-computing
- Contact support@ebrains.eu for deployment assistance

````

**Estimated Effort**: 8 hours

**Assignee**: TBD

**Status**: ⬜ NOT STARTED

---

#### TASK-013: Update Main README

**Description**: Add containerization section to main README.

**Dependencies**: TASK-011

**Acceptance Criteria**:
- [ ] New "Container Deployment" section added
- [ ] Links to detailed guides
- [ ] Quick example showing simplicity
- [ ] Badge showing image size and pulls

**Implementation Details**:

Add to `README.md`:

```markdown
## 🐳 Container Deployment (Recommended)

The easiest way to run w2t-bkin is using containers:

```bash
# Install CLI
pip install w2t-bkin

# Start server (one-time setup)
w2t-bkin container start-server

# Start workers
w2t-bkin container start-worker --workers 4

# Run pipeline
w2t-bkin batch config.toml --max-workers 4
````

✅ **Benefits**:

- No manual dependency installation (ffmpeg, etc.)
- Multi-platform: Windows, macOS, Linux, HPC
- Free & open-source runtimes (Podman)
- Distributed execution across network

📚 **Guides**:

- [Quick Start](docs/containerization/quick-start.md)
- [HPC/Apptainer](docs/containerization/hpc-guide.md)
- [Platform-Specific](docs/containerization/platform-guides.md)

**Supported Runtimes**: Podman (recommended), Docker, Apptainer/Singularity

````

**Estimated Effort**: 2 hours

**Assignee**: TBD

**Status**: ⬜ NOT STARTED

---

### Phase 6: HPC Validation (Priority: SHOULD HAVE)

#### TASK-014: Test on EBRAINS Infrastructure

**Description**: Validate deployment on actual EBRAINS HPC cluster.

**Dependencies**: TASK-012

**Acceptance Criteria**:
- [ ] Successfully build .sif on EBRAINS login node
- [ ] Submit test Slurm job and verify execution
- [ ] Validate file permissions and I/O performance
- [ ] Document any EBRAINS-specific quirks
- [ ] Get approval from EBRAINS support team

**Implementation Details**:

1. Request EBRAINS access: support@ebrains.eu
2. Follow deployment guide
3. Run benchmark on test dataset
4. Document results

**Estimated Effort**: 12 hours (includes coordination)

**Assignee**: TBD

**Status**: ⬜ NOT STARTED

---

### Phase 7: Polish & Release (Priority: SHOULD HAVE)

#### TASK-015: Optimize Image Size

**Description**: Reduce container image size to <2GB.

**Dependencies**: TASK-001

**Acceptance Criteria**:
- [ ] Compressed worker image <2GB
- [ ] Use alpine base where possible
- [ ] Multi-stage build eliminates build dependencies
- [ ] No unnecessary files (cache, docs) in final image

**Implementation Details**:

Optimizations:
- Use `python:3.10-slim` instead of full image
- Clean apt cache in same layer: `rm -rf /var/lib/apt/lists/*`
- Use `--no-cache-dir` for pip installs
- Consider alpine base (may require more testing)

**Estimated Effort**: 4 hours

**Assignee**: TBD

**Status**: ⬜ NOT STARTED

---

#### TASK-016: Create Architecture Diagrams

**Description**: Visual diagrams for documentation.

**Dependencies**: None

**Acceptance Criteria**:
- [ ] Container architecture diagram (Mermaid)
- [ ] Data flow diagram
- [ ] Deployment topology options (local, HPC, K8s)
- [ ] Diagrams embedded in documentation

**Implementation Details**:

Already included in design.md. Update as needed.

**Estimated Effort**: 3 hours

**Assignee**: TBD

**Status**: ⬜ NOT STARTED

---

#### TASK-017: Beta Testing

**Description**: Real-world testing with neuroscience users.

**Dependencies**: All previous tasks

**Acceptance Criteria**:
- [ ] 3-5 beta testers recruited (different institutions)
- [ ] Test on Windows, macOS, Linux
- [ ] Collect feedback survey
- [ ] Fix critical bugs discovered
- [ ] Document common issues

**Implementation Details**:

1. Recruit from lab collaborators
2. Provide quick start guide
3. Schedule 1-hour onboarding call
4. Monitor for 1 week
5. Collect feedback
6. Iterate

**Estimated Effort**: 20 hours (spread over 2 weeks)

**Assignee**: TBD

**Status**: ⬜ NOT STARTED

---

#### TASK-018: Release v1.0.0

**Description**: Official release of containerization feature.

**Dependencies**: All previous tasks

**Acceptance Criteria**:
- [ ] All tests passing in CI
- [ ] Documentation complete
- [ ] Images pushed to GHCR with v1.0.0 tag
- [ ] Changelog updated
- [ ] GitHub release created
- [ ] PyPI release (if applicable)
- [ ] Announcement on website/blog

**Implementation Details**:

```bash
# Tag release
git tag v1.0.0
git push origin v1.0.0

# Create GitHub release with notes
# CI will automatically build and push images
````

**Estimated Effort**: 4 hours

**Assignee**: TBD

**Status**: ⬜ NOT STARTED

---

## Summary

| Phase                  | Tasks                | Est. Effort               | Priority    |
| ---------------------- | -------------------- | ------------------------- | ----------- |
| 1. Core Infrastructure | TASK-001 to TASK-004 | 11h                       | MUST HAVE   |
| 2. CLI Wrapper         | TASK-005 to TASK-007 | 12h                       | MUST HAVE   |
| 3. CI/CD               | TASK-008 to TASK-009 | 6h                        | MUST HAVE   |
| 4. Testing             | TASK-010             | 6h                        | SHOULD HAVE |
| 5. Documentation       | TASK-011 to TASK-013 | 16h                       | MUST HAVE   |
| 6. HPC Validation      | TASK-014             | 12h                       | SHOULD HAVE |
| 7. Polish & Release    | TASK-015 to TASK-018 | 31h                       | SHOULD HAVE |
| **TOTAL**              | **18 Tasks**         | **94 hours** (~2.5 weeks) |             |

## Risk Register

| Risk                                     | Impact | Probability | Mitigation                            |
| ---------------------------------------- | ------ | ----------- | ------------------------------------- |
| Apptainer version incompatibility on HPC | High   | Medium      | Test on multiple HPC centers early    |
| Image size exceeds 2GB                   | Medium | Low         | Monitor size in CI, optimize layers   |
| Podman bugs on Windows                   | Medium | Medium      | Provide Docker fallback instructions  |
| Beta testers unavailable                 | Low    | Low         | Recruit more testers, extend timeline |
| Security vulnerabilities in base image   | High   | Low         | Automated Trivy scans, rapid patching |

## Next Steps

1. **Assign Tasks**: Distribute tasks to team members
2. **Set Deadlines**: Agree on sprint schedule
3. **Create GitHub Project**: Track progress in GitHub Projects
4. **Daily Standups**: 15-min sync on blockers
5. **Weekly Demo**: Show progress to stakeholders
