# Troubleshooting

## `w2t-bkin server start` exits immediately

Common causes:

- Port already in use (default `4200`)
  - Fix: `w2t-bkin server start --port 4201`
- Broken Prefect state in the experiment’s `.prefect/`
  - Fix: from the experiment root, run `w2t-bkin server reset -y`

## Prefect UI opens but deployments don’t run

Production mode requires a worker.

From the experiment root:

```bash
w2t-bkin worker start --pool docker-pool --type docker
```

If you want to run locally without Docker, use dev mode:

```bash
w2t-bkin server start --dev
```

## Worker can’t connect to the server

Make sure the worker is pointing at the same Prefect API URL and port.

- Server default: `http://127.0.0.1:4200/api`
- If server uses `--port 4201`, also pass `--port 4201` to `w2t-bkin worker start`.

## Session not discovered by `w2t-bkin discover`

The discover command scans `data/raw/<subject>/<session>/` and expects at least a `session.toml`.

- Fix: ensure `data/raw/<subject>/<session>/session.toml` exists.
- Fix: run `w2t-bkin data validate <experiment_root>` to see what is missing.

## Pose H5 files are not picked up

If you are using DLC discover mode, ensure:

- H5 location: `data/interim/<subject>/<session>/dlc-pose/<camera_id>/`
- H5 naming: `{video_stem}DLC*.h5` where `video_stem` matches the corresponding video filename stem.

## NWB validation fails

Use:

```bash
w2t-bkin validate path/to/file.nwb --output validation.json
```

Then attach `validation.json` plus `data/processed/<subject>/<session>/pipeline.log` when reporting the issue.
