# Containerization Architecture Design

## Document Information

- **Created**: 2025-12-04
- **Status**: Draft
- **Version**: 1.0
- **Dependencies**: requirements.md

## Executive Summary

This document describes the technical architecture for containerizing the w2t-bkin pipeline using OCI-compliant containers orchestrated by Prefect. The design supports multiple container runtimes (Docker, Podman, Apptainer), enables distributed execution, and maintains compatibility with HPC environments (EBRAINS).

## Architecture Overview

### High-Level Architecture

```mermaid
graph TB
    subgraph "User Machine"
        CLI[CLI Wrapper<br/>w2t-bkin start-*]
        CLI -->|detects| RT{Container<br/>Runtime?}
        RT -->|docker| DOCKER[Docker Engine]
        RT -->|podman| PODMAN[Podman]
        RT -->|apptainer| APPTAINER[Apptainer]
    end

    subgraph "Orchestrator Stack"
        DOCKER & PODMAN & APPTAINER --> SERVER[Prefect Server<br/>:4200]
        SERVER --> POSTGRES[(PostgreSQL<br/>Database)]
        SERVER --> UI[Web UI<br/>Dashboard]
    end

    subgraph "Worker Pool"
        SERVER -->|work queue| W1[Worker 1<br/>Container]
        SERVER -->|work queue| W2[Worker 2<br/>Container]
        SERVER -->|work queue| WN[Worker N<br/>Container]
    end

    subgraph "Storage"
        W1 & W2 & WN -->|mount| DATA[/data/<br/>raw, interim, processed]
        W1 & W2 & WN -->|mount| MODELS[/models/<br/>pose models]
        W1 & W2 & WN -->|mount| CONFIG[/configs/<br/>config.toml]
    end

    USER[Neuroscientist] -->|browser| UI
    USER -->|terminal| CLI

    style SERVER fill:#4A90E2
    style W1 fill:#7ED321
    style W2 fill:#7ED321
    style WN fill:#7ED321
    style POSTGRES fill:#F5A623
```

### Component Architecture

```mermaid
graph LR
    subgraph "Base Image"
        OS[python:3.10-slim]
        OS --> DEPS[System Dependencies<br/>ffmpeg, libgl1]
        DEPS --> PYTHON[Python Environment<br/>w2t-bkin + deps]
    end

    subgraph "Server Image"
        PYTHON --> PREFECT_SERVER[Prefect Server]
        PREFECT_SERVER --> INIT_SERVER[Entrypoint:<br/>start-server.sh]
    end

    subgraph "Worker Image"
        PYTHON --> PREFECT_WORKER[Prefect Worker]
        PREFECT_WORKER --> INIT_WORKER[Entrypoint:<br/>start-worker.sh]
    end

    style PYTHON fill:#4A90E2
    style PREFECT_SERVER fill:#F5A623
    style PREFECT_WORKER fill:#7ED321
```

## Detailed Design

### 1. Container Images

#### 1.1 Base Image Strategy

We will use a **single Dockerfile with multi-stage builds** to create both server and worker images from a common base.

**Base Stage:**

```dockerfile
FROM python:3.10-slim AS base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 -s /bin/bash w2t

# Install Python package
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir -e .
```

**Server Stage:**

```dockerfile
FROM base AS server

# Install Prefect server dependencies
RUN pip install --no-cache-dir prefect[server]>=2.14.0

# Copy server entrypoint
COPY docker/start-server.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/start-server.sh

USER w2t
EXPOSE 4200
ENTRYPOINT ["/usr/local/bin/start-server.sh"]
```

**Worker Stage:**

```dockerfile
FROM base AS worker

# Worker needs CLI access
COPY docker/start-worker.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/start-worker.sh

USER w2t
ENTRYPOINT ["/usr/local/bin/start-worker.sh"]
```

#### 1.2 Image Tagging Strategy

| Tag Pattern      | Description           | Example                                    | Use Case        |
| ---------------- | --------------------- | ------------------------------------------ | --------------- |
| `latest`         | Latest stable release | `ghcr.io/borjaest/w2t-bkin:latest`         | Production      |
| `v{semver}`      | Specific version      | `ghcr.io/borjaest/w2t-bkin:v1.2.3`         | Reproducibility |
| `dev`            | Development branch    | `ghcr.io/borjaest/w2t-bkin:dev`            | Testing         |
| `{branch}-{sha}` | PR/branch builds      | `ghcr.io/borjaest/w2t-bkin:feat-x-a1b2c3d` | CI/CD           |

### 2. Docker Compose Configuration

#### 2.1 Production Stack (docker-compose.yml)

```yaml
version: "3.8"

services:
  postgres:
    image: postgres:14-alpine
    environment:
      POSTGRES_USER: prefect
      POSTGRES_PASSWORD: prefect
      POSTGRES_DB: prefect
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U prefect"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  server:
    image: ghcr.io/borjaest/w2t-bkin:latest
    target: server
    ports:
      - "4200:4200"
    environment:
      PREFECT_API_DATABASE_CONNECTION_URL: postgresql+asyncpg://prefect:prefect@postgres:5432/prefect
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
    restart: unless-stopped

  worker:
    image: ghcr.io/borjaest/w2t-bkin:latest
    target: worker
    environment:
      PREFECT_API_URL: http://server:4200/api
    volumes:
      - ${DATA_ROOT:-./data}:/data:ro
      - ${INTERIM_ROOT:-./data/interim}:/data/interim:rw
      - ${OUTPUT_ROOT:-./data/processed}:/data/processed:rw
      - ${MODELS_ROOT:-./models}:/models:ro
      - ${CONFIG_ROOT:-./configs}:/configs:ro
    depends_on:
      server:
        condition: service_healthy
    deploy:
      replicas: 2
    restart: unless-stopped

volumes:
  postgres_data:
```

#### 2.2 Development Stack (docker-compose.dev.yml)

```yaml
version: "3.8"

services:
  server:
    build:
      context: .
      dockerfile: Dockerfile
      target: server
    volumes:
      - ./src:/app/src:ro # Hot-reload source code
    environment:
      PREFECT_LOGGING_LEVEL: DEBUG

  worker:
    build:
      context: .
      dockerfile: Dockerfile
      target: worker
    volumes:
      - ./src:/app/src:ro # Hot-reload source code
      - ./data:/data
      - ./models:/models
      - ./configs:/configs
    environment:
      PREFECT_LOGGING_LEVEL: DEBUG
```

### 3. CLI Wrapper Design

#### 3.1 Runtime Detection Logic

```python
# src/w2t_bkin/container/runtime.py

from enum import Enum
from typing import Optional
import shutil
import subprocess

class ContainerRuntime(Enum):
    PODMAN = "podman"
    DOCKER = "docker"
    APPTAINER = "apptainer"
    NONE = None

def detect_runtime() -> ContainerRuntime:
    """Detect available container runtime (priority: podman > docker > apptainer)."""
    if shutil.which("podman"):
        return ContainerRuntime.PODMAN
    elif shutil.which("docker"):
        # Check if Docker daemon is running
        try:
            subprocess.run(
                ["docker", "info"],
                check=True,
                capture_output=True,
                timeout=5
            )
            return ContainerRuntime.DOCKER
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass

    if shutil.which("apptainer") or shutil.which("singularity"):
        return ContainerRuntime.APPTAINER

    return ContainerRuntime.NONE
```

#### 3.2 CLI Commands

```python
# src/w2t_bkin/cli.py (additions)

import click
from w2t_bkin.container import runtime, orchestrator

@cli.group()
def container():
    """Container orchestration commands."""
    pass

@container.command()
@click.option("--port", default=4200, help="Prefect UI port")
@click.option("--detach", "-d", is_flag=True, help="Run in background")
def start_server(port: int, detach: bool):
    """Start Prefect server and database."""
    rt = runtime.detect_runtime()
    if rt == runtime.ContainerRuntime.NONE:
        click.echo("❌ No container runtime detected.", err=True)
        click.echo("Please install: Podman Desktop, Docker, or Apptainer", err=True)
        raise click.Abort()

    orchestrator.start_server(rt, port=port, detach=detach)

@container.command()
@click.option("--workers", default=1, help="Number of worker instances")
@click.option("--config", default="./configs/config.toml", help="Config file path")
def start_worker(workers: int, config: str):
    """Start worker container(s)."""
    rt = runtime.detect_runtime()
    if rt == runtime.ContainerRuntime.NONE:
        click.echo("❌ No container runtime detected.", err=True)
        raise click.Abort()

    orchestrator.start_workers(rt, count=workers, config_path=config)

@container.command()
def stop():
    """Stop all containers."""
    rt = runtime.detect_runtime()
    orchestrator.stop_all(rt)

@container.command()
def status():
    """Show container status."""
    rt = runtime.detect_runtime()
    orchestrator.show_status(rt)
```

### 4. Prefect Configuration

#### 4.1 Work Pool Setup

The server will auto-create a work pool on first start:

```python
# docker/start-server.sh (bash script)

#!/bin/bash
set -e

echo "🚀 Starting Prefect server..."

# Start server in background
prefect server start --host 0.0.0.0 --port 4200 &
SERVER_PID=$!

# Wait for server to be ready
echo "⏳ Waiting for server to be ready..."
until curl -sf http://localhost:4200/api/health > /dev/null 2>&1; do
    sleep 2
done

echo "✅ Server ready!"

# Create default work pool if not exists
echo "📋 Setting up work pool..."
prefect work-pool create --type process docker-pool 2>/dev/null || true

# Wait for server process
wait $SERVER_PID
```

#### 4.2 Worker Configuration

```python
# docker/start-worker.sh (bash script)

#!/bin/bash
set -e

echo "🔧 Starting Prefect worker..."

# Wait for server to be available
until curl -sf "${PREFECT_API_URL}/health" > /dev/null 2>&1; do
    echo "⏳ Waiting for Prefect server at ${PREFECT_API_URL}..."
    sleep 5
done

echo "✅ Connected to Prefect server"

# Start worker
exec prefect worker start \
    --pool docker-pool \
    --name "worker-$(hostname)" \
    --type process
```

### 5. Data Access Patterns

#### 5.1 Volume Mount Strategy

| Data Type      | Mount Path        | Access     | Rationale                       |
| -------------- | ----------------- | ---------- | ------------------------------- |
| Raw data       | `/data/raw`       | Read-only  | Prevent accidental modification |
| Interim data   | `/data/interim`   | Read-write | Pipeline intermediate outputs   |
| Processed data | `/data/processed` | Read-write | Final NWB files                 |
| Models         | `/models`         | Read-only  | Pose estimation models          |
| Configs        | `/configs`        | Read-only  | TOML configuration files        |

#### 5.2 Configuration File Resolution

Workers will look for configuration in this order:

1. Environment variable: `CONFIG_PATH=/configs/custom.toml`
2. Mounted config: `/configs/config.toml`
3. Fallback: Generate minimal config with prompts

### 6. HPC/Apptainer Integration

#### 6.1 Image Conversion

```bash
# Pull OCI image and convert to SIF
apptainer build w2t_bkin.sif docker://ghcr.io/borjaest/w2t-bkin:latest

# Verify
apptainer inspect w2t_bkin.sif
```

#### 6.2 Execution on HPC

```bash
# Run pipeline on HPC node
apptainer exec \
    --bind /scratch/user/data:/data \
    --bind /scratch/user/models:/models \
    --env PREFECT_API_URL=http://head-node:4200/api \
    w2t_bkin.sif \
    python -m w2t_bkin.cli run /data/config.toml subject-001 session-001
```

#### 6.3 Slurm Integration

```bash
# Prefect can submit Slurm jobs that run Apptainer
# Example Slurm job script generated by Prefect

#!/bin/bash
#SBATCH --job-name=w2t-bkin-{subject}-{session}
#SBATCH --time=02:00:00
#SBATCH --mem=8GB
#SBATCH --cpus-per-task=4

module load apptainer

apptainer exec \
    --bind ${DATA_ROOT}:/data \
    --bind ${MODELS_ROOT}:/models \
    --env PREFECT_API_URL=${PREFECT_API_URL} \
    ${SIF_PATH} \
    python -m w2t_bkin.cli run /data/config.toml ${SUBJECT_ID} ${SESSION_ID}
```

### 7. Security Considerations

#### 7.1 Non-Root Execution

- All processes run as uid 1000 (user `w2t`)
- No sudo or privileged operations required
- File permissions preserved via user namespace mapping

#### 7.2 Network Security

- Prefect server only binds to localhost by default
- Use reverse proxy (nginx) for external access
- Environment variables for secrets (not hardcoded)

#### 7.3 Image Scanning

- GitHub Actions runs Trivy scan on every build
- Block merge if HIGH/CRITICAL vulnerabilities detected
- Automated dependency updates via Dependabot

### 8. Monitoring & Observability

#### 8.1 Logging Strategy

| Component      | Log Destination | Format          | Retention    |
| -------------- | --------------- | --------------- | ------------ |
| Prefect Server | PostgreSQL      | Structured JSON | 30 days      |
| Worker stdout  | Docker logs     | Plain text      | 7 days       |
| Pipeline logs  | Mounted volume  | Plain text      | User-defined |

#### 8.2 Metrics

Exposed via Prefect UI:

- Task success/failure rate
- Task duration (p50, p95, p99)
- Queue depth
- Worker utilization
- Memory/CPU usage (via Docker stats)

### 9. CI/CD Pipeline

#### 9.1 Build Pipeline

```yaml
# .github/workflows/build-images.yml

name: Build Container Images

on:
  push:
    branches: [main, dev]
    tags: ["v*"]
  pull_request:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ghcr.io/borjaest/w2t-bkin
          tags: |
            type=ref,event=branch
            type=ref,event=pr
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=raw,value=latest,enable={{is_default_branch}}

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: ${{ github.event_name != 'pull_request' }}
          tags: ${{ steps.meta.outputs.tags }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
          platforms: linux/amd64,linux/arm64

      - name: Run Trivy security scan
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: ghcr.io/borjaest/w2t-bkin:${{ steps.meta.outputs.version }}
          severity: HIGH,CRITICAL
          exit-code: 1
```

### 10. Testing Strategy

#### 10.1 Container Tests

```python
# tests/integration/test_containers.py

import pytest
import docker
import subprocess

def test_server_starts():
    """Test Prefect server container starts and is healthy."""
    client = docker.from_env()
    container = client.containers.run(
        "ghcr.io/borjaest/w2t-bkin:latest",
        target="server",
        detach=True,
        ports={"4200/tcp": 4200},
    )

    # Wait for health check
    container.reload()
    assert container.status == "running"

    # Cleanup
    container.stop()
    container.remove()

def test_worker_connects():
    """Test worker container connects to server."""
    # Start server first
    # Start worker
    # Verify worker registers in work pool
    pass

@pytest.mark.hpc
def test_apptainer_execution():
    """Test pipeline runs via Apptainer."""
    result = subprocess.run(
        [
            "apptainer", "exec",
            "w2t_bkin.sif",
            "python", "-m", "w2t_bkin.cli", "run",
            "test_config.toml", "subject-001", "session-001"
        ],
        capture_output=True,
        check=True
    )
    assert result.returncode == 0
```

## Implementation Phases

### Phase 1: Core Infrastructure (Week 1-2)

- Dockerfile (base, server, worker stages)
- docker-compose.yml (production)
- Entrypoint scripts (start-server.sh, start-worker.sh)
- GitHub Actions for image builds

### Phase 2: CLI Wrapper (Week 2-3)

- Runtime detection
- start-server, start-worker, stop, status commands
- Environment variable handling
- Basic error messages and user guidance

### Phase 3: Testing & Documentation (Week 3-4)

- Integration tests for all runtimes
- User documentation (quick start, platform guides)
- Architecture diagrams
- Troubleshooting guide

### Phase 4: HPC Integration (Week 4-5)

- Apptainer/Singularity validation
- Slurm job templates
- EBRAINS-specific documentation
- Performance benchmarking

### Phase 5: Polish & Release (Week 5-6)

- Security scan fixes
- Image size optimization
- Beta testing with real users
- Release v1.0.0

## Open Questions

1. **PostgreSQL Persistence**: Should we use named volumes or bind mounts for database?

   - **Recommendation**: Named volumes (more portable across platforms)

2. **Worker Auto-scaling**: Should we support dynamic worker scaling based on queue depth?

   - **Recommendation**: Defer to v1.1, start with fixed replicas

3. **Image Registry**: GitHub Container Registry (free) vs Docker Hub (rate limits)?

   - **Recommendation**: GHCR (better CI/CD integration, no rate limits)

4. **Multi-architecture**: Support ARM64 for Mac M1/M2?
   - **Recommendation**: Yes, use buildx multi-platform builds

## Decision Log

### Decision 2025-12-04: Single Dockerfile with Multi-Stage Builds

**Context**: Need separate server and worker images, but they share 90% of dependencies.

**Options**:

1. Separate Dockerfiles (more duplication)
2. Single Dockerfile with multi-stage builds (shared base layer)

**Decision**: Single Dockerfile with multi-stage builds

**Rationale**: Reduces maintenance burden, ensures consistency, better layer caching

**Impact**: Slightly more complex Dockerfile, but simpler CI/CD and updates

---

### Decision 2025-12-04: Prioritize Podman over Docker in Detection

**Context**: Need to choose default when both Docker and Podman are installed.

**Options**:

1. Docker first (most common)
2. Podman first (open-source, rootless)

**Decision**: Podman first

**Rationale**: Aligns with "license-free" goal, encourages better security practices

**Impact**: Users with both installed will use Podman unless they explicitly set CONTAINER_RUNTIME=docker

---

## References

- [Prefect Documentation](https://docs.prefect.io/)
- [OCI Image Spec](https://github.com/opencontainers/image-spec)
- [Apptainer User Guide](https://apptainer.org/docs/user/latest/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [EBRAINS Infrastructure](https://ebrains.eu/)
