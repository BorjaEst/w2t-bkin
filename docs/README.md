# W2T-BKIN Documentation

This directory contains comprehensive documentation for the W2T Body Kinematics Pipeline.

## 📚 Documentation Structure

### Core Documentation

- **[design.md](design.md)** - Technical architecture, domain model, and implementation details
- **[architecture_diagram.mmd](architecture_diagram.mmd)** - Visual representation of the system architecture
- **[configuration-parameters.md](configuration-parameters.md)** - Configuration file format and parameters
- **[batch-processing.md](batch-processing.md)** - Guide for parallel batch processing
- **[data-management-cli.md](data-management-cli.md)** - Data management CLI commands reference

### Specialized Topics

#### Containerization (`containerization/`)

Docker and Prefect deployment documentation:

- **[README.md](containerization/README.md)** - Quick start and container deployment guide
- **[deployment-guide.md](containerization/deployment-guide.md)** - Detailed deployment instructions
- **[design.md](containerization/design.md)** - Container architecture and design decisions
- **[requirements.md](containerization/requirements.md)** - Container requirements and specifications
- **[tasks.md](containerization/tasks.md)** - Implementation tasks and progress

## 🏗️ Architecture Overview

The W2T-BKIN pipeline uses a layered Prefect-native architecture (v0.0.10):

### 1. User Interfaces

- **CLI** - Command-line interface for local execution
- **Prefect UI** - Web dashboard for monitoring and deployment
- **Docker Compose** - Multi-container orchestration

### 2. Orchestration Layer (Prefect)

- **Flows** - High-level workflows (`process_session_flow`, `batch_process_flow`)
- **Tasks** - Atomic operations with retry logic and error handling

### 3. Operations Layer (Pure Python)

Pure Python functions with no Prefect dependencies:

- Discovery - Session and file discovery
- Ingestion - Bpod, pose, TTL data loading
- Artifact Generation - DeepLabCut/SLEAP pose estimation
- Assembly - Trial alignment and behavior tables
- Finalization - NWB writing and validation

### 4. Foundation Layer (NWB-First)

- `pynwb` - Core NWB data structures
- `ndx-pose` - Pose estimation extension
- `ndx-events` - TTL/hardware events
- `ndx-structured-behavior` - Trial structure and behavioral events

## 🚀 Quick Start

### Local Execution

```bash
# Process a single session
python -m w2t_bkin.cli run config.toml subject-001 session-001

# Batch process multiple sessions
python -m w2t_bkin.cli batch config.toml --max-workers 4

# Validate NWB output
python -m w2t_bkin.cli validate output/session-001.nwb
```

### Docker Deployment

```bash
# Initialize experiment (creates docker/.env automatically)
w2t-bkin data init /data/my-experiment --lab "Lab" -y

# Start services
cd /data/my-experiment
docker compose up -d

# Access Prefect UI
open http://localhost:4200
```

## 📖 Key Concepts

### NWB-First Design

The pipeline treats NWB as a foundational data layer, not just an export format:

- All processing outputs are NWB-native data structures
- Eliminates intermediate models and conversion layers
- Maximizes interoperability with neuroscience research tools
- Simplifies architecture and reduces testing burden

### Prefect-Native Orchestration

Pure Prefect flows and tasks provide:

- Automatic retry logic with exponential backoff
- Parallel execution with configurable concurrency
- Real-time monitoring via Prefect UI
- Comprehensive error handling and logging
- Production-ready deployment with Docker

### Layered Architecture

Clear separation of concerns:

- **Operations** - Pure Python, no framework dependencies
- **Tasks** - Prefect wrappers for retry/error handling
- **Flows** - High-level orchestration and composition
- **CLI/UI** - User-facing interfaces

## 📝 Recent Changes (v0.0.10)

- ✅ Completed Prefect-native refactoring
- ✅ Removed ~3,700 lines of deprecated code (58% reduction)
- ✅ Updated all deployment scripts for new flow architecture
- ✅ Added `.env` generation command for Docker deployment
- ✅ Comprehensive documentation cleanup and updates
- ✅ All integration tests passing

## 🔗 Additional Resources

- [Main README](../README.md) - Project overview and installation
- [Examples](../examples/) - Sample scripts and notebooks
- [Tests](../tests/) - Integration and unit tests
- [Docker Files](../docker/) - Container configuration and scripts

## 💡 Getting Help

- Check the relevant documentation file for your topic
- Review examples in the `examples/` directory
- Examine tests in the `tests/` directory for usage patterns
- Open an issue on GitHub for bugs or feature requests

## 📅 Version

Current documentation version: **v0.0.10** (December 2025)

Architecture status: **Production Ready** ✅
