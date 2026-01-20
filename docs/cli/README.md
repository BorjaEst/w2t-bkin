# CLI Reference

The `w2t-bkin` command is a thin UI over Prefect flows and data-management helpers.

## Data management

### Initialize experiment workspace

```bash
w2t-bkin data init /data/my-experiment -y --lab "Larkum Lab" --institution "HU Berlin" --experimenters "Alice,Bob"
```

Creates:

- `data/raw/`, `data/interim/`, `data/processed/`, `data/external/`
- `models/`
- `configuration.toml`
- `.workers/.env` and `.workers/.env.dev` (unless `--skip-docker-env`)

### Add a subject

```bash
w2t-bkin data add-subject /data/my-experiment SNA-000000 --sex F --age P90D -y
```

### Add a session

```bash
w2t-bkin data add-session /data/my-experiment SNA-000000 day1 --description "Baseline" --experimenter Alice -y
```

### Import existing raw data (symlinks)

Dry-run:

```bash
w2t-bkin data import-raw /path/to/raw -e /data/my-experiment -s SNA-000000 --session day1
```

Execute:

```bash
w2t-bkin data import-raw /path/to/raw -e /data/my-experiment -s SNA-000000 --session day1 --confirm
```

### Validate structure

```bash
w2t-bkin data validate /data/my-experiment
```

## Orchestration (Prefect)

### Start server

From the experiment root:

```bash
w2t-bkin server start
```

Development mode (runs flows locally, no worker required):

```bash
w2t-bkin server start --dev
```

Useful commands:

- `w2t-bkin server status`
- `w2t-bkin server stop`
- `w2t-bkin server restart`
- `w2t-bkin server reset -y`

### Start worker

Production Docker worker:

```bash
w2t-bkin worker start --pool docker-pool --type docker --limit 1
```

Local process worker (requires worker extras):

```bash
w2t-bkin worker start --pool default-pool --type process --limit 1
```

## Discovery

```bash
w2t-bkin discover /data/my-experiment --format plain
w2t-bkin discover /data/my-experiment --subject SNA-000000
```

## NWB utilities

```bash
w2t-bkin validate data/processed/SNA-000000/day1/day1.nwb
w2t-bkin inspect data/processed/SNA-000000/day1/day1.nwb
```
