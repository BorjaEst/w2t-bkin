# W2T-BKIN Container Deployment

Complete guide to deploying W2T-BKIN using containers (Docker/Podman/Apptainer).

## 🚀 Quick Start - Get Running in 5 Minutes

```bash
# 1. Install CLI
pip install w2t-bkin

# 2. Initialize experiment (creates docker/.env automatically)
w2t-bkin data init /data/my-experiment \
  --lab "Your Lab" \
  --institution "Your Institution" \
  --experimenters "Alice,Bob" \
  -y

# 3. Navigate to experiment and start containers
cd /data/my-experiment
docker compose up -d

# 4. Wait for initialization (60 seconds)
sleep 60

# 5. Verify deployment
docker exec w2t-bkin-server prefect deployment ls
# Should show:
#   - process-session-flow/process-session
#   - batch-process-flow/batch-processing

# 6. Open Prefect UI
# Browser: http://localhost:4200
```

## Prerequisites

- Docker or Podman installed
- Your data in `./data/raw/` structure
- DeepLabCut models in `./models/` (if using pose estimation)

## Directory Structure

```text
w2t-bkin/
├── .env                    # Configuration (edit to customize)
├── docker-compose.yml      # Container orchestration
├── configs/
│   ├── container.toml      # ✅ For Prefect (absolute paths)
│   └── standard.toml       # For local CLI (relative paths)
├── data/
│   ├── raw/               # Your raw data (read-only in container)
│   ├── interim/           # Processing intermediates (read-write)
│   └── processed/         # Final outputs (read-write)
└── models/                # DeepLabCut models (read-only in container)
```

## Configuration (.env)

The `.env` file controls all container settings. Generate it with:

```bash
# Generate with defaults
python -m w2t_bkin.cli data generate-env

# Initialize experiment (automatically creates docker/.env)
w2t-bkin data init /data/my-experiment \
  --lab "Lab Name" \
  --institution "Institution" \
  --experimenters "Alice,Bob" \
  -y

# Or manually copy template and edit (for developers)
cp .env.template docker/.env
```

Key settings:

```bash
# Data paths (host paths, mounted into containers)
DATA_ROOT=./data
CONFIG_ROOT=./configs
MODELS_ROOT=./models

# Deployment defaults
DEFAULT_CONFIG_FILE=container.toml  # Uses absolute paths
DEFAULT_MAX_WORKERS=4               # Concurrent sessions

# Prefect settings
PREFECT_UI_PORT=4200
WORK_POOL=docker-pool
WORKER_REPLICAS=2
```

## Running Pipelines

### Via Prefect UI (Recommended)

1. Open <http://localhost:4200>
2. Go to "Deployments"
3. Choose a deployment:
   - **process-session-flow/process-session**: Process a single session
   - **batch-process-flow/batch-processing**: Process multiple sessions in parallel
4. Click "Run"
5. Set parameters:

   **For single session (process-session)**:

   - `config_path`: Path to config (default: `/configs/container.toml`)
   - `subject_id`: Subject identifier (e.g., `subject-001`)
   - `session_id`: Session identifier (e.g., `session-001`)
   - `skip_bpod`: Skip Bpod processing (default: `false`)
   - `skip_pose`: Skip pose processing (default: `false`)
   - `skip_ecephys`: Skip electrophysiology processing (default: `false`)
   - `skip_camera_sync`: Skip camera verification (default: `false`)
   - `skip_nwb_validation`: Skip NWB validation (default: `false`)

   **For batch processing (batch-processing)**:

   - `config_path`: Path to config (default: `/configs/container.toml`)
   - `subject_filter`: Process only this subject (optional)
   - `session_filter`: Process only this session (optional)
   - `max_parallel`: Concurrent sessions (default: 4)
   - `skip_bpod`: Skip Bpod processing (default: `false`)
   - `skip_pose`: Skip pose processing (default: `false`)
   - `skip_ecephys`: Skip electrophysiology processing (default: `false`)
   - `skip_camera_sync`: Skip camera verification (default: `false`)
   - `skip_nwb_validation`: Skip NWB validation (default: `false`)

6. Click "Run" to start
7. Monitor in "Flow Runs" tab

### Via Prefect CLI

```bash
# Process single session
docker exec w2t-bkin-server prefect deployment run \
  process-session-flow/process-session \
  --param subject_id=subject-001 \
  --param session_id=session-001

# Batch process with defaults
docker exec w2t-bkin-server prefect deployment run \
  batch-process-flow/batch-processing

# Batch process with custom parameters
docker exec w2t-bkin-server prefect deployment run \
  batch-process-flow/batch-processing \
  --param subject_filter=subject-001 \
  --param session_filter=session_20251201 \
  --param max_parallel=2
```

## Common Commands

```bash
# Check status
docker compose ps

# View logs
docker logs w2t-bkin-server        # Server logs
docker logs w2t-bkin-worker-1      # Worker logs
docker logs -f w2t-bkin-worker-1   # Follow logs

# Restart everything
docker compose down
docker compose up -d

# Stop everything
docker compose down

# Update to latest images
docker compose pull
docker compose up -d
```

## Customization

### Change Data Location

Edit `.env`:

```bash
DATA_ROOT=/mnt/external/raw_data
```

Then restart:

```bash
docker compose down && docker compose up -d
```

### Use Custom Config

1. Copy `configs/container.toml` to `configs/my-config.toml`
2. Modify settings (keep absolute paths!)
3. Edit `.env`: `DEFAULT_CONFIG_FILE=my-config.toml`
4. Restart: `docker compose down && docker compose up -d`

### Add More Workers

Edit `.env`:

```bash
WORKER_REPLICAS=4  # Increase from 2 to 4
```

Restart:

```bash
docker compose down && docker compose up -d
```

## Troubleshooting

### Check Deployment Status

```bash
# Server should show deployment creation
docker logs w2t-bkin-server | grep -i deploy

# Should see:
# ✅ Deployed: batch-processing
# Default config: /configs/container.toml
```

### Verify Config Loads

```bash
docker exec w2t-bkin-worker-1 python -c "
from w2t_bkin.config import load_config
config = load_config('/configs/container.toml')
print('✅ Config valid')
print(f'Raw root: {config.paths.raw_root}')
"
```

### Test Session Discovery

```bash
docker exec w2t-bkin-worker-1 python -c "
from w2t_bkin.utils import discover_sessions
sessions = discover_sessions('/configs/container.toml')
print(f'✅ Found {len(sessions)} sessions')
"
```

### Common Issues

| Error                        | Cause                            | Fix                                            |
| ---------------------------- | -------------------------------- | ---------------------------------------------- |
| `raw_root does not exist`    | Config uses relative paths       | Use `container.toml` with absolute paths       |
| `TOMLDecodeError`            | Invalid TOML syntax              | Check for `null` values, remove invalid fields |
| `Extra inputs not permitted` | Config has fields not in schema  | Remove `video.enabled`, `qc.enabled`, etc.     |
| Workers not running          | Container startup failed         | Check logs: `docker logs w2t-bkin-worker-1`    |
| Deployment not found         | Server initialization incomplete | Wait 60s, check: `docker logs w2t-bkin-server` |

## Architecture

```text
┌─────────────────────────────────────────────────────┐
│ Host Machine                                        │
│                                                     │
│  ┌─────────────┐      ┌──────────────────────┐    │
│  │  Browser    │─────▶│  Prefect Server      │    │
│  │ :4200       │      │  (w2t-bkin-server)   │    │
│  └─────────────┘      └──────────────────────┘    │
│                              │                      │
│                              │ Work Pool            │
│                              ▼                      │
│       ┌──────────────────────────────────┐         │
│       │  Workers (w2t-bkin-worker-1/2)   │         │
│       │  Execute pipeline tasks          │         │
│       └──────────────────────────────────┘         │
│                     │                               │
│                     ▼                               │
│       ┌──────────────────────────────────┐         │
│       │  Mounted Volumes                 │         │
│       │  /data, /models, /configs        │         │
│       └──────────────────────────────────┘         │
└─────────────────────────────────────────────────────┘
```

## Additional Documentation

For more detailed information, see:

- **[deployment-guide.md](deployment-guide.md)**: Complete installation guide with platform-specific instructions
- **[design.md](design.md)**: System architecture, technical decisions, and build optimization
- **[requirements.md](requirements.md)**: Functional and non-functional requirements
- **[tasks.md](tasks.md)**: Implementation checklist and feature status

## Support

Need help? Check these resources:

- **Prefect Documentation**: <https://docs.prefect.io>
- **Docker Documentation**: <https://docs.docker.com>
- **Podman Documentation**: <https://podman.io/docs>
- **Project Issues**: <https://github.com/BorjaEst/w2t-bkin/issues>

## License

See [../../LICENSE](../../LICENSE) for project license information.
