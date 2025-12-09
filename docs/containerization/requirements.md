# Containerization Requirements

## Document Information

- **Created**: 2025-12-04
- **Status**: Draft
- **Owner**: Development Team
- **Target Audience**: Developers, DevOps, System Administrators

## Executive Summary

This document defines the requirements for containerizing the w2t-bkin pipeline to enable multi-platform deployment, simplified installation, and distributed execution across local workstations, HPC clusters (EBRAINS), and cloud environments.

## Problem Statement

### Current State

- Users must manually install Python environment, system dependencies (ffmpeg), and configure Prefect
- Docker Desktop licensing restrictions prevent use at large institutions
- Neuroscience researchers lack container/orchestration expertise
- No standardized deployment for HPC clusters (EBRAINS/HPC centers)
- Manual setup is error-prone and time-consuming

### Target State

- Single-command setup: `w2t-bkin start-server` (orchestrator) + `w2t-bkin start-worker` (executor)
- Multi-runtime support: Podman, Docker, Apptainer/Singularity
- Web UI access at `http://localhost:4200` for monitoring
- Distributed execution across networks
- EBRAINS/HPC cluster compatible
- Zero-cost licensing for all users

## Stakeholders

| Stakeholder        | Role                    | Primary Concern                        |
| ------------------ | ----------------------- | -------------------------------------- |
| Neuroscientists    | End Users               | Ease of use, zero licensing cost       |
| Lab IT Staff       | Installation Support    | Multi-platform compatibility, security |
| HPC Administrators | Cluster Integration     | Rootless execution, job scheduling     |
| EBRAINS Platform   | Infrastructure Provider | Standards compliance (OCI, Apptainer)  |
| Development Team   | Maintainers             | Maintainability, testing, CI/CD        |

## Requirements (EARS Notation)

### FR-1: Multi-Runtime Container Support

**WHEN a user has Podman, Docker, or Apptainer installed, THE SYSTEM SHALL run the containerized pipeline without modification.**

- **Priority**: MUST HAVE
- **Rationale**: Different environments require different runtimes (Docker Desktop licensing, HPC security)
- **Acceptance Criteria**:
  - Single OCI-compliant Dockerfile builds image for all runtimes
  - docker-compose.yml works with both Docker and Podman
  - Apptainer can pull and run the OCI image from registry
  - Image passes validation tests on all three runtimes

### FR-2: Orchestrator Container (Prefect Server)

**THE SYSTEM SHALL provide a containerized Prefect server with web UI accessible at configurable host:port.**

- **Priority**: MUST HAVE
- **Rationale**: Centralized orchestration, observability, and job scheduling
- **Acceptance Criteria**:
  - Prefect server runs in container with PostgreSQL backend
  - Web UI accessible at http://localhost:4200 by default
  - Persistent storage for flow runs, logs, and database
  - Environment variables configure server settings
  - Starts in <30 seconds on typical hardware

### FR-3: Worker Container (Executor)

**THE SYSTEM SHALL provide a containerized worker that connects to Prefect server and executes pipeline tasks.**

- **Priority**: MUST HAVE
- **Rationale**: Distributed execution across network, resource isolation
- **Acceptance Criteria**:
  - Worker connects to remote Prefect server via PREFECT_API_URL
  - Supports volume mounts for data access (local files)
  - Supports environment variable configuration
  - Multiple workers can run in parallel
  - Worker auto-registers with server work pool

### FR-4: Data Volume Mounting

**WHEN processing local data, THE SYSTEM SHALL mount host directories into containers as volumes.**

- **Priority**: MUST HAVE
- **Rationale**: Data files too large to copy into container, shared storage
- **Acceptance Criteria**:
  - docker-compose.yml defines volume mounts for data/, models/, output/
  - Read-only mounts for raw data (safety)
  - Read-write mounts for interim/ and processed/ directories
  - Preserves file permissions and ownership
  - Works across Windows (WSL2), macOS, Linux

### FR-5: Simplified CLI Wrapper

**THE SYSTEM SHALL provide CLI commands that abstract container runtime complexity.**

- **Priority**: MUST HAVE
- **Rationale**: Neuroscientists should not need to learn Docker/Podman syntax
- **Acceptance Criteria**:
  - `w2t-bkin start-server` launches orchestrator
  - `w2t-bkin start-worker` launches executor
  - `w2t-bkin stop` stops all containers
  - CLI auto-detects available runtime (podman > docker > apptainer)
  - CLI provides helpful error messages if no runtime found
  - CLI forwards logs to terminal with `--follow` flag

### FR-6: Container Image Registry

**THE SYSTEM SHALL publish container images to a public OCI-compliant registry.**

- **Priority**: MUST HAVE
- **Rationale**: Users should not need to build images locally, EBRAINS needs public pull
- **Acceptance Criteria**:
  - Images published to GitHub Container Registry (ghcr.io)
  - Semantic versioning tags (e.g., v1.0.0, latest, dev)
  - Multi-architecture support (amd64, arm64 for Mac M1/M2)
  - Image size <2GB compressed
  - Automated builds via GitHub Actions on release

### FR-7: HPC/Apptainer Support

**WHEN running on HPC cluster, THE SYSTEM SHALL execute via Apptainer without root privileges.**

- **Priority**: MUST HAVE
- **Rationale**: HPC centers (EBRAINS) do not allow Docker, require rootless execution
- **Acceptance Criteria**:
  - Apptainer can build .sif from OCI image: `apptainer build w2t_bkin.sif docker://ghcr.io/borjaest/w2t-bkin`
  - .sif runs without root: `apptainer run w2t_bkin.sif`
  - File permissions work with shared HPC storage (--no-home, --bind flags)
  - Integration with Slurm job scheduler documented
  - Prefect can submit jobs to Slurm work pool

### FR-8: Configuration Injection

**THE SYSTEM SHALL allow runtime configuration via environment variables and mounted config files.**

- **Priority**: MUST HAVE
- **Rationale**: Different deployments need different settings without rebuilding image
- **Acceptance Criteria**:
  - PREFECT_API_URL configures worker connection
  - CONFIG_PATH environment variable sets default config.toml
  - Config files mounted via volume: `-v ./configs:/app/configs`
  - Environment variables override config file settings
  - Secrets (API keys) passed via environment, not baked in image

### FR-9: Health Checks

**THE SYSTEM SHALL provide health check endpoints for orchestrator and worker containers.**

- **Priority**: SHOULD HAVE
- **Rationale**: Monitoring, auto-restart policies, Kubernetes readiness probes
- **Acceptance Criteria**:
  - Prefect server health: `curl http://localhost:4200/api/health`
  - Worker health: Prefect heartbeat mechanism
  - docker-compose.yml defines healthcheck for each service
  - Unhealthy containers automatically restart (restart: unless-stopped)

### FR-10: Development Mode

**WHEN developing locally, THE SYSTEM SHALL support hot-reload of code without rebuilding image.**

- **Priority**: SHOULD HAVE
- **Rationale**: Faster iteration during development
- **Acceptance Criteria**:
  - docker-compose.dev.yml mounts `./src` as volume
  - Changes to Python code reflected immediately in container
  - Development image installs code in editable mode: `pip install -e .[full,prefect]`
  - Separate dev vs. prod compose files

### NFR-1: Image Build Performance

**THE SYSTEM SHALL build container images in <5 minutes on typical CI/CD infrastructure.**

- **Priority**: SHOULD HAVE
- **Rationale**: Fast feedback loop for developers
- **Acceptance Criteria**:
  - Multi-stage Dockerfile minimizes layer count
  - Build cache leverages layer caching
  - Base image (python:3.10-slim) pulled from cache
  - Dependencies installed before copying source code

### NFR-2: Image Size

**THE SYSTEM SHALL produce container images <2GB compressed.**

- **Priority**: SHOULD HAVE
- **Rationale**: Faster pulls, lower storage costs, better user experience
- **Acceptance Criteria**:
  - Use slim/alpine base images where possible
  - Multi-stage builds discard build-time dependencies
  - Clean up apt cache, pip cache in same layer
  - Compressed image size verified in CI

### NFR-3: Security

**THE SYSTEM SHALL run containers as non-root user.**

- **Priority**: MUST HAVE
- **Rationale**: Security best practice, required for HPC
- **Acceptance Criteria**:
  - Dockerfile creates non-root user (uid 1000)
  - All processes run as this user (USER directive)
  - No sudo or setuid binaries in image
  - Security scan (Trivy) passes with no HIGH/CRITICAL vulnerabilities

### NFR-4: Documentation

**THE SYSTEM SHALL provide comprehensive documentation for all deployment scenarios.**

- **Priority**: MUST HAVE
- **Rationale**: Users need guidance for different platforms and use cases
- **Acceptance Criteria**:
  - Quick-start guide (<5 commands to running pipeline)
  - Platform-specific guides (Windows/WSL, macOS, Linux, HPC)
  - Troubleshooting section for common issues
  - Architecture diagrams (Mermaid) showing container interactions
  - Example configuration files for common scenarios

### NFR-5: Backward Compatibility

**THE SYSTEM SHALL maintain support for non-containerized execution.**

- **Priority**: MUST HAVE
- **Rationale**: Users with existing Python environments should not be forced to containers
- **Acceptance Criteria**:
  - CLI commands work with and without containers
  - `python -m w2t_bkin.cli run` continues to work
  - Documentation clearly separates container vs. native execution
  - Tests validate both execution modes

## Out of Scope (Future Iterations)

### FUT-1: Kubernetes Helm Charts

- **Rationale**: Adds complexity, defer until user demand proven
- **Timeline**: Version 2.0

### FUT-2: GUI Installer (Electron/Tauri)

- **Rationale**: Nice-to-have for non-technical users, significant development effort
- **Timeline**: Version 2.0

### FUT-3: Cloud-Native Storage (S3/MinIO)

- **Rationale**: Current users have local data, cloud storage adds cost/complexity
- **Timeline**: Version 1.5 (optional feature)

### FUT-4: GPU Support

- **Rationale**: Pose estimation models can leverage GPU, but not critical path
- **Timeline**: Version 1.5 (NVIDIA Container Toolkit)

## Constraints

1. **Licensing**: All container runtime options must be free and open-source
2. **Platform**: Must support Linux, macOS, Windows (via WSL2)
3. **Dependencies**: Python 3.9+, ffmpeg, PostgreSQL (for Prefect)
4. **Registry**: GitHub Container Registry (free for public repos)
5. **Standards**: OCI-compliant images (Docker, Podman, Apptainer compatible)

## Assumptions

1. Users have sufficient disk space (5GB for images + data)
2. Users have internet access to pull images from registry
3. HPC administrators allow Apptainer/Singularity usage
4. Network allows HTTP traffic on port 4200 (Prefect UI)

## Dependencies

| Dependency              | Type    | Status        | Notes                     |
| ----------------------- | ------- | ------------- | ------------------------- |
| Prefect >=2.0           | Runtime | Installed     | Already in pyproject.toml |
| PostgreSQL 14+          | Runtime | To Install    | Container-only, not host  |
| ffmpeg                  | System  | To Install    | Via apt in Dockerfile     |
| Docker/Podman/Apptainer | Runtime | User-provided | Detection logic needed    |

## Risks & Mitigations

| Risk                                   | Impact | Probability | Mitigation                              |
| -------------------------------------- | ------ | ----------- | --------------------------------------- |
| Users unfamiliar with containers       | High   | High        | Simplified CLI wrapper, excellent docs  |
| Docker Desktop licensing confusion     | Medium | Medium      | Clear guidance to use Podman Desktop    |
| HPC storage permissions issues         | High   | Medium      | Document --bind and --no-home flags     |
| Image pull failures (network/firewall) | High   | Low         | Provide offline .sif build instructions |
| Version mismatch (image vs. code)      | Medium | Medium      | Automated tagging in CI, version checks |

## Success Metrics

1. **Adoption**: >50% of new users choose container deployment within 3 months
2. **Installation Time**: <10 minutes from zero to running pipeline
3. **Support Tickets**: <10% related to container issues
4. **Build Time**: <5 minutes per image in CI
5. **Image Size**: <2GB compressed

## Approval

| Role              | Name      | Date | Signature |
| ----------------- | --------- | ---- | --------- |
| Product Owner     | [Pending] |      |           |
| Technical Lead    | [Pending] |      |           |
| Security Reviewer | [Pending] |      |           |

---

**Next Steps:**

1. Review and approve requirements
2. Create detailed technical design (design.md)
3. Break down into implementation tasks (tasks.md)
4. Develop Dockerfile and docker-compose.yml
5. Test on multiple platforms
6. Write user documentation
