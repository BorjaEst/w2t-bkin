# W2T-BKIN Documentation Hub

Welcome to the W2T Body Kinematics Pipeline documentation! This is your central hub for all documentation resources.

## 🎯 Start Here

### New Users

- **📖 [Getting Started Guide](../README.md#quick-start)** - Complete setup from zero to first processing
- **❓ [FAQ](FAQ.md)** - Common questions and quick answers
- **🔧 [Troubleshooting](TROUBLESHOOTING.md)** - Solutions to common issues

### Existing Users

- **💻 [CLI Reference](cli/README.md)** - Command-line interface documentation
- **📋 [Configuration Reference](reference/configuration-parameters.md)** - Complete parameter guide
- **🐳 [Container Deployment](containerization/README.md)** - Docker and Prefect setup

---

## 📚 Documentation by Category

### User Guides

Core guides for using the pipeline:

- **[Getting Started](../README.md#quick-start)** - First-time setup and workflow
- **[Caching and Reprocessing](user-guide/caching-and-reprocessing.md)** - Understanding cache behavior and force regeneration
- **[FAQ](FAQ.md)** - Frequently asked questions
- **[Troubleshooting](TROUBLESHOOTING.md)** - Common issues and solutions

### CLI Tools

Command-line interface documentation:

- **[CLI Overview](cli/README.md)** - Complete CLI reference
- **[Data Management](cli/data-management.md)** - Experiment setup and organization
- **[Pipeline Commands](cli/pipeline-commands.md)** - Running processing workflows
- **[Validation](cli/validation.md)** - NWB file validation

### Reference Documentation

Technical references and API documentation:

- **[Configuration Parameters](reference/configuration-parameters.md)** - Complete configuration reference
- **[Architecture Diagram](reference/architecture_diagram.mmd)** - System architecture visualization
- **[Data Manager Utilities](reference/data-manager-utilities.md)** - File and metadata utilities
- **[Prefect UI Configuration](reference/prefect-ui-configuration.md)** - Prefect orchestration setup
- **[Pydantic Config Implementation](reference/pydantic-config-implementation.md)** - Configuration system internals

### Container Deployment

Docker and orchestration:

- **[Container Quick Start](containerization/README.md)** - Get started with containers
- **[Deployment Guide](containerization/deployment-guide.md)** - Detailed deployment instructions
- **[Container Design](containerization/design.md)** - Architecture and design decisions
- **[Requirements](containerization/requirements.md)** - System requirements and specifications
- **[Tasks & Progress](containerization/tasks.md)** - Implementation status

### Developer Documentation

For contributors and developers:

- **[Technical Design](development/design.md)** - System architecture and domain model
- **[Requirements](development/requirements.md)** - Project requirements and specifications
- **[Tasks](development/tasks.md)** - Development tasks and roadmap
- **[Internal Docs](development/internal/)** - Implementation notes and reviews

## 🏗️ Architecture Overview

The W2T-BKIN pipeline uses a layered Prefect-native architecture (v0.0.10):

### 1. User Interfaces

- **CLI** - Command-line interface for local execution
- **Prefect UI** - Web dashboard with auto-generated configuration forms
- **Python API** - Direct flow invocation with Pydantic models
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

---

## 🔍 Search & Navigation

### By Task

Looking for something specific?

- **Setup a new experiment** → [Getting Started](../README.md#quick-start) → [CLI Data Management](cli/data-management.md)
- **Configure the pipeline** → [Configuration Reference](reference/configuration-parameters.md)
- **Run processing** → [Getting Started](../README.md#quick-start) or [CLI Pipeline Commands](cli/pipeline-commands.md)
- **Deploy with Docker** → [Container Quick Start](containerization/README.md)
- **Fix an error** → [Troubleshooting](TROUBLESHOOTING.md) or [FAQ](FAQ.md)
- **Validate NWB files** → [CLI Validation](cli/validation.md)
- **Understand the architecture** → [Technical Design](development/design.md) or [Architecture Diagram](reference/architecture_diagram.mmd)

### By User Type

- **🆕 First-time users** → Start with [Getting Started](../README.md#quick-start), then read [FAQ](FAQ.md)
- **👨‍🔬 Researchers running experiments** → [CLI Data Management](cli/data-management.md) + [Pipeline Commands](cli/pipeline-commands.md)
- **🔧 DevOps / System administrators** → [Container Deployment](containerization/README.md) + [Deployment Guide](containerization/deployment-guide.md)
- **👩‍💻 Developers & Contributors** → [Technical Design](development/design.md) + [Development Tasks](development/tasks.md)
- **📊 Data analysts** → [Configuration Reference](reference/configuration-parameters.md) + [CLI Validation](cli/validation.md)

---

## 🚀 Quick Start Examples

### Example 1: Complete Workflow (First Time)

```bash
# 1. Install CLI tools
pip install w2t-bkin

# 2. Install manual dependencies
git clone https://github.com/rly/ndx-structured-behavior.git
pip install -U ./ndx-structured-behavior

# 3. Create experiment
w2t-bkin data init /data/my-exp --lab "Lab" -y
w2t-bkin data add-subject /data/my-exp mouse-001 --species "Mus musculus" -y
w2t-bkin data add-session /data/my-exp mouse-001 session-001 -y

# 4. Copy data to session folders
cp /source/videos/*.mp4 /data/my-exp/data/raw/mouse-001/session-001/Video/
cp /source/bpod/*.mat /data/my-exp/data/raw/mouse-001/session-001/Bpod/

# 5. Start Docker processing
cd /data/my-exp
docker compose up -d

# 6. Access Prefect UI at http://localhost:4200
# → Click "Deployments" → "process-session" → "Run"
```

### Example 2: Local Python Processing

```python
from w2t_bkin.flows import SessionFlowConfig, process_session_flow

# Process a single session
config = SessionFlowConfig(
    config_path="/data/my-exp/configs/standard.toml",
    subject_id="mouse-001",
    session_id="session-001"
)
result = process_session_flow(config)
print(f"Success: {result}")
```

### Example 3: Batch Processing via CLI

```bash
# Process all sessions in parallel
cd /data/my-exp
python -m w2t_bkin.cli batch configs/standard.toml --max-workers 4

# Or with filters
python -m w2t_bkin.cli batch configs/standard.toml \
  --subject-filter "mouse-00[1-3]" \
  --session-filter "session-.*" \
  --max-workers 2

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
- **Pydantic-based configuration** with auto-generated UI forms
- Type-safe validation and IDE autocompletion
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
