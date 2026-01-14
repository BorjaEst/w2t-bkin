# Docker + Prefect deployments (developer notes)

This document explains how production mode is wired up:

- `w2t-bkin server start` creates/updates a Prefect Docker work pool (`docker-pool`) and deploys flows.
- `w2t-bkin worker start --type docker` starts a Prefect worker that polls `docker-pool` and creates a fresh container per run.

Primary implementation: [src/w2t_bkin/cli/server.py](../../src/w2t_bkin/cli/server.py)

## Production-mode control flow

`w2t-bkin server start` (without `--dev`) does:

1. Starts Prefect server
2. Calls `_create_work_pool(project_root)`
3. Calls `_deploy_flows(config_path, project_root)`

### Project isolation

Both server and worker set `PREFECT_HOME` to `<experiment_root>/.prefect`.

This means each experiment directory has its own Prefect state (deployments, run history).

## Work pool volumes (where the container sees your data)

When the pool is created/updated, the code injects volumes into the pool base job template.

The intent is:

- host `<experiment_root>/data` is mounted at `/data` (read/write)
- host `<experiment_root>/models` is mounted at `/models` (read-only)
- host `<experiment_root>/configuration.toml` is mounted at `/configs/configuration.toml` (read-only)

This is implemented by `_create_work_pool()` using:

- `prefect work-pool get-default-base-job-template --type docker`
- patch `job_configuration.volumes`
- `prefect work-pool set-base-job-template docker-pool --base-job-template <temp.json>`

## Container-native config (W2T_RUNTIME_CONFIG_JSON)

Deployments are created with a JSON config blob in `job_variables.env.W2T_RUNTIME_CONFIG_JSON`.

This JSON is derived from:

- `configs/standard.toml` (base config)
- optionally a project config passed via `--config`

Then `_load_and_normalize_config(..., for_container=True)` rewrites paths to container-native fixed mountpoints:

```text
raw_root          -> /data/raw
intermediate_root -> /data/interim
output_root       -> /data/processed
models_root       -> /models
root_metadata     -> /configs/metadata.toml (if configured)
```

Deployments also set path env vars explicitly:

```text
W2T_RAW_ROOT=/data/raw
W2T_INTERMEDIATE_ROOT=/data/interim
W2T_OUTPUT_ROOT=/data/processed
W2T_MODELS_ROOT=/models
```

## Which Docker image runs the flow?

The deployment image is resolved in `_get_docker_image(project_root)`:

1. `W2T_DOCKER_IMAGE` environment variable
2. `<experiment_root>/.workers/.env` line `W2T_DOCKER_IMAGE=...`
3. default: `ghcr.io/borjaest/w2t-bkin:latest`

Important: `W2T_DOCKER_IMAGE` must be the **runner image** (the one that contains the pipeline and dependencies).

## Debugging production runs

Useful checkpoints:

- Work pool exists: `prefect work-pool inspect docker-pool`
- Base template contains volumes: `prefect work-pool inspect docker-pool | grep -n volumes`
- Deployment has correct `job_variables.env`: check in Prefect UI → Deployment → Edit

## Dev mode differences

In `--dev` mode, flows are served via Prefect Runner inside the server process.

Instead of `W2T_RUNTIME_CONFIG_JSON`, dev mode primarily relies on host-absolute path env vars set by `server.py`:

```text
W2T_RAW_ROOT=<experiment_root>/data/raw
W2T_INTERMEDIATE_ROOT=<experiment_root>/data/interim
W2T_OUTPUT_ROOT=<experiment_root>/data/processed
W2T_MODELS_ROOT=<experiment_root>/models
```

Dev mode still uses merged config defaults for flow parameters, but it does not require Docker.
