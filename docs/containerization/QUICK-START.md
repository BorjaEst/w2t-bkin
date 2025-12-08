# W2T-BKIN Container Quick Start

## TL;DR - Get Running in 5 Minutes

```bash
# 1. Clone repository
git clone https://github.com/BorjaEst/w2t-bkin.git
cd w2t-bkin

# 2. Start containers
docker compose up -d

# 3. Wait for initialization (60 seconds)
sleep 60

# 4. Verify deployment
docker exec w2t-bkin-server prefect deployment ls
# Should show: batch-process-sessions-prefect/batch-processing

# 5. Open Prefect UI
# Browser: http://localhost:4200
```

## Prerequisites

- Docker or Podman installed
- Your data in `./data/raw/` structure
- DeepLabCut models in `./models/` (if using pose estimation)

## Directory Structure

```
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

## Default Configuration (.env)

The `.env` file controls all container settings:

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
3. Click "batch-process-sessions-prefect/batch-processing"
4. Click "Run"
5. Optionally override parameters:
   - `config_path`: Path to config (default: `/configs/container.toml`)
   - `subject_filter`: Process only this subject (optional)
   - `session_filter`: Process only this session (optional)
   - `max_workers`: Concurrent sessions (default: 4)
6. Click "Run" to start
7. Monitor in "Flow Runs" tab

### Via Prefect CLI

```bash
# Run with defaults
docker exec w2t-bkin-server prefect deployment run \
  batch-process-sessions-prefect/batch-processing

# Run with custom parameters
docker exec w2t-bkin-server prefect deployment run \
  batch-process-sessions-prefect/batch-processing \
  --param subject_filter=subject-001 \
  --param session_filter=session_20251201
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

## What's Next?

- **Full Guide**: See `deployment-guide.md` for detailed instructions
- **Configuration**: See `CONFIGURATION.md` for config options
- **Path Resolution**: See `PATH-RESOLUTION-FIX.md` for technical details
- **TOML Syntax**: See `TOML-CONFIG-FIX.md` for config troubleshooting

## Architecture

```
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

## Support

- GitHub Issues: <https://github.com/BorjaEst/w2t-bkin/issues>
- Documentation: `docs/containerization/`
- Prefect Docs: <https://docs.prefect.io>
