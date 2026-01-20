# Prefect UI Guide

## Start Prefect

From the experiment root:

```bash
w2t-bkin server start
```

Open http://localhost:4200

## Run a session

1. Go to Deployments
2. Select `process-session`
3. Click Run
4. Fill required parameters (subject/session ids)
5. Monitor under Flow Runs

## Dev vs production

- Dev: `w2t-bkin server start --dev` executes runs inside the server process (no worker)
- Production: `w2t-bkin server start` requires a worker (typically Docker)
