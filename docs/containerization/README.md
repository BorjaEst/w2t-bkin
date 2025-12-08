# Container Deployment Documentation

Complete guide to deploying W2T-BKIN using containers (Docker/Podman/Apptainer).

## 📚 Documentation Index

### Getting Started

1. **[QUICK-START.md](QUICK-START.md)** ⚡

   - Get running in 5 minutes
   - Essential commands
   - Quick troubleshooting
   - **Start here if you want to run now!**

2. **[deployment-guide.md](deployment-guide.md)** 📖
   - Complete installation guide
   - Platform-specific instructions (Windows/macOS/Linux)
   - Container runtime selection (Podman vs Docker)
   - Step-by-step setup
   - Advanced configuration

### Configuration

3. **[CONFIGURATION.md](CONFIGURATION.md)** ⚙️

   - Environment variables (.env file)
   - Volume mounting
   - Deployment parameters
   - Customization options
   - Parameter reference

4. **[PATH-RESOLUTION-FIX.md](PATH-RESOLUTION-FIX.md)** 🔧

   - Why absolute paths are required in containers
   - container.toml vs standard.toml
   - Volume mapping explained
   - Path resolution technical details

5. **[TOML-CONFIG-FIX.md](TOML-CONFIG-FIX.md)** 🐛
   - Common config errors
   - Schema validation issues
   - TOML syntax requirements
   - Troubleshooting guide

### Architecture & Design

6. **[design.md](design.md)** 🏗️

   - System architecture
   - Container orchestration
   - Multi-stage builds
   - Technical decisions
   - Build optimization (26x speedup)

7. **[requirements.md](requirements.md)** 📋
   - Functional requirements
   - Non-functional requirements
   - User stories
   - Success criteria

### Project Management

8. **[tasks.md](tasks.md)** ✅

   - Implementation checklist
   - Completed features
   - Testing status
   - Validation results

9. **[PROGRESS.md](PROGRESS.md)** 📊
   - Development timeline
   - Milestone tracking
   - Known issues
   - Future enhancements

## 🚀 Quick Decision Tree

**"I just want to run the pipeline"**
→ Go to [QUICK-START.md](QUICK-START.md)

**"I need detailed installation instructions"**
→ Go to [deployment-guide.md](deployment-guide.md)

**"I'm getting config errors"**
→ Go to [TOML-CONFIG-FIX.md](TOML-CONFIG-FIX.md)

**"I want to customize paths/settings"**
→ Go to [CONFIGURATION.md](CONFIGURATION.md)

**"I'm getting path-related errors"**
→ Go to [PATH-RESOLUTION-FIX.md](PATH-RESOLUTION-FIX.md)

**"I want to understand the architecture"**
→ Go to [design.md](design.md)

**"I'm deploying on HPC cluster"**
→ Go to [hpc-guide.md](hpc-guide.md) (if exists) or see Apptainer section in deployment-guide.md

## 🎯 Key Concepts

### Container vs Local Execution

| Aspect              | Container              | Local CLI             |
| ------------------- | ---------------------- | --------------------- |
| **Config file**     | `container.toml`       | `standard.toml`       |
| **Paths**           | Absolute (`/data/raw`) | Relative (`data/raw`) |
| **Execution**       | Prefect workers        | Direct Python         |
| **Orchestration**   | Web UI + workers       | Command line          |
| **Parallelization** | Multiple workers       | Single process        |

### Path Resolution

```
Host Path              Container Path         Config Value
./data/raw       →     /data/raw         →    raw_root = "/data/raw"
./models         →     /models           →    models_root = "/models"
./configs        →     /configs          →    (config location)
```

### Environment Variables (.env)

```bash
DATA_ROOT=./data              # Host path (what to mount)
DEFAULT_CONFIG_FILE=container.toml  # Which config to use
DEFAULT_MAX_WORKERS=4         # Concurrent sessions
WORKER_REPLICAS=2             # Number of worker containers
```

## 🆘 Common Issues & Solutions

| Symptom                      | Likely Cause               | Fix                         |
| ---------------------------- | -------------------------- | --------------------------- |
| `raw_root does not exist`    | Config uses relative paths | Use `container.toml`        |
| `TOMLDecodeError`            | Invalid TOML syntax        | See TOML-CONFIG-FIX.md      |
| `Extra inputs not permitted` | Invalid config fields      | Remove fields not in schema |
| Deployment not found         | Server init incomplete     | Wait 60s, check logs        |
| Workers not running          | Volume mount issues        | Check .env paths exist      |

## 📖 Reading Order

For first-time users:

1. QUICK-START.md - Get it running
2. deployment-guide.md - Understand what you're running
3. CONFIGURATION.md - Customize for your needs

For troubleshooting:

1. TOML-CONFIG-FIX.md - Config syntax errors
2. PATH-RESOLUTION-FIX.md - Path-related errors
3. deployment-guide.md - General troubleshooting section

For advanced users:

1. design.md - Architecture overview
2. requirements.md - System requirements
3. CONFIGURATION.md - Advanced customization

## 🔗 External Resources

- **Prefect Documentation**: <https://docs.prefect.io>
- **Docker Documentation**: <https://docs.docker.com>
- **Podman Documentation**: <https://podman.io/docs>
- **Apptainer Documentation**: <https://apptainer.org/docs>

## 📝 Contributing

Found an issue or want to improve the docs?

- Open an issue: <https://github.com/BorjaEst/w2t-bkin/issues>
- Submit a PR: <https://github.com/BorjaEst/w2t-bkin/pulls>

## 📄 License

See [../../LICENSE](../../LICENSE) for project license information.
