# Migration Guide

This project is transitioning toward a single canonical “experiment workspace” layout and Prefect-first execution.

## From ad-hoc scripts to the experiment workspace

Recommended structure:

- `data/raw/<subject>/<session>/` contains `subject.toml` and `session.toml`
- `data/interim/<subject>/<session>/` contains recomputable artifacts (e.g., pose H5)
- `data/processed/<subject>/<session>/` contains outputs (NWB, logs, provenance)

Create this layout via:

```bash
w2t-bkin data init /path/to/experiment -y --lab "..." --institution "..." --experimenters "..."
```

## From direct scripts to Prefect runs

Instead of calling processing functions directly:

- Start Prefect: `w2t-bkin server start` (or `--dev`)
- Run deployments in the UI at http://127.0.0.1:4200
