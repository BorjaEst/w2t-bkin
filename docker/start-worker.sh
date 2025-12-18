#!/bin/bash
set -e

echo "=================================================="
echo "W2T-BKIN Prefect Worker"
echo "=================================================="
echo "Work Pool:       ${WORK_POOL:-docker-pool}"
echo "Worker Name:     ${WORKER_NAME:-docker-worker}"
echo "Worker Limit:    ${LIMIT:-1}"
echo "Prefect API:     ${PREFECT_API_URL:-http://host.docker.internal:4200/api}"
echo "Logging Level:   ${PREFECT_LOGGING_LEVEL:-INFO}"
echo "Data Root:       ${DATA_ROOT:-/data}"
echo "Models Root:     ${MODELS_ROOT:-/models}"
echo "Config Root:     ${CONFIG_ROOT:-/configs}"
echo "Output Root:     ${OUTPUT_ROOT:-/output}"
echo "=================================================="

# Verify Prefect server connection
echo "Checking Prefect server connectivity..."
until curl -sf "${PREFECT_API_URL}/health" > /dev/null 2>&1; do
  echo "Waiting for Prefect server at ${PREFECT_API_URL}..."
  sleep 2
done
echo "✓ Prefect server is ready"

# Start Prefect worker
echo "Starting Prefect worker..."
exec prefect worker start \
  --pool "${WORK_POOL:-docker-pool}" \
  --type docker \
  --name "${WORKER_NAME:-docker-worker}" \
  --limit "${LIMIT:-1}"
