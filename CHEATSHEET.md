# w2t-bkin Cheat Sheet

Minimal quick reference for running the pipeline.

## Install

Development / local execution:

```bash
pip install -e .[worker]
```

Lightweight orchestration (Docker workers):

```bash
pip install -e .
```

## Create an experiment workspace

```bash
w2t-bkin data init /data/my-experiment -y --lab "Larkum Lab" --institution "HU Berlin" --experimenters "Alice,Bob"
cd /data/my-experiment
```

## Add subject + session skeleton

```bash
w2t-bkin data add-subject /data/my-experiment SNA-000000 --sex F --age P90D -y
w2t-bkin data add-session /data/my-experiment SNA-000000 day1 --description "Baseline" --experimenter Alice -y
```

## Import existing raw data (safe symlinks)

Dry-run preview:

```bash
w2t-bkin data import-raw /path/to/raw -e /data/my-experiment -s SNA-000000 --session day1
```

Execute:

```bash
w2t-bkin data import-raw /path/to/raw -e /data/my-experiment -s SNA-000000 --session day1 --confirm
```

## Validate experiment structure

```bash
w2t-bkin data validate /data/my-experiment
w2t-bkin discover /data/my-experiment --format plain
```

## Start Prefect

Development mode (flows run locally, no workers):

```bash
cd /data/my-experiment
w2t-bkin server start --dev
```

Production mode (Docker workers):

```bash
cd /data/my-experiment
w2t-bkin server start
```

In another terminal:

```bash
cd /data/my-experiment
w2t-bkin worker start --pool docker-pool --type docker --limit 1
```

## Run workflows

Open Prefect UI: http://localhost:4200

- Deployments → `process-session` (single) or `batch-process` (multi)
- Fill parameters (subject/session) and run

## Outputs

By default, outputs land under:

- `data/processed/<subject>/<session>/` (NWB, provenance, pipeline.log)
- `data/interim/<subject>/<session>/` (recomputable artifacts)

## Validate / inspect NWB

```bash
w2t-bkin validate /data/my-experiment/data/processed/SNA-000000/day1/day1.nwb
w2t-bkin inspect /data/my-experiment/data/processed/SNA-000000/day1/day1.nwb
```
