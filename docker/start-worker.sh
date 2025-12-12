#!/bin/bash
# Prefect Worker Entrypoint Script
# Connects to Prefect server and executes pipeline tasks

set -euo pipefail

echo "🔧 Starting Prefect worker..."

# Configuration
PREFECT_API_URL="${PREFECT_API_URL:-http://server:4200/api}"
WORK_POOL="${WORK_POOL:-docker-pool}"
WORKER_NAME="${WORKER_NAME:-worker-$(hostname)}"

echo "   API URL: ${PREFECT_API_URL}"
echo "   Work Pool: ${WORK_POOL}"
echo "   Worker Name: ${WORKER_NAME}"

# Handle shutdown signals gracefully
shutdown() {
    echo ""
    echo "🛑 Received shutdown signal, stopping worker..."
    if [ -n "${WORKER_PID:-}" ]; then
        kill -TERM "$WORKER_PID" 2>/dev/null || true
        wait "$WORKER_PID" 2>/dev/null || true
    fi
    echo "✅ Worker stopped"
    exit 0
}

trap shutdown SIGTERM SIGINT

# Wait for Prefect server to be available
echo "⏳ Waiting for Prefect server at ${PREFECT_API_URL}..."

MAX_RETRIES=60
RETRY_COUNT=0
HEALTH_URL="${PREFECT_API_URL}/health"

until curl -sf "$HEALTH_URL" > /dev/null 2>&1; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "❌ Failed to connect to Prefect server after ${MAX_RETRIES} attempts"
        echo "   Please ensure the server is running and accessible at ${PREFECT_API_URL}"
        exit 1
    fi
    
    # Log every 10 attempts to avoid spam
    if [ $((RETRY_COUNT % 10)) -eq 0 ]; then
        echo "   Still waiting... (${RETRY_COUNT}/${MAX_RETRIES})"
    fi
    
    sleep 2
done

echo "✅ Connected to Prefect server"

# Verify work pool exists
echo "📋 Verifying work pool '${WORK_POOL}'..."
if prefect work-pool inspect "${WORK_POOL}" > /dev/null 2>&1; then
    echo "✅ Work pool '${WORK_POOL}' found"
else
    echo "⚠️  Work pool '${WORK_POOL}' not found, attempting to create..."
    if prefect work-pool create --type docker "${WORK_POOL}" 2>/dev/null; then
        echo "✅ Work pool '${WORK_POOL}' created"
    else
        echo "❌ Failed to create work pool '${WORK_POOL}'"
        echo "   Please create it manually: prefect work-pool create --type docker ${WORK_POOL}"
        exit 1
    fi
fi

echo "🏃 Starting worker: ${WORKER_NAME}"
echo ""

# Start Prefect worker (exec replaces shell, no need for & or wait)
exec prefect worker start \
    --pool "${WORK_POOL}" \
    --name "${WORKER_NAME}" \
    --type docker \
    --limit 1
