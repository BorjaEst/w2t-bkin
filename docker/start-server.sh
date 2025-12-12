#!/bin/bash
# Prefect Server Entrypoint Script
# Starts Prefect server, waits for health, and creates default work pool

set -euo pipefail

echo "🚀 Starting Prefect server..."
echo "   Host: ${PREFECT_SERVER_API_HOST:-0.0.0.0}"
echo "   Port: ${PREFECT_SERVER_API_PORT:-4200}"

# Handle shutdown signals gracefully
shutdown() {
    echo ""
    echo "🛑 Received shutdown signal, stopping Prefect server..."
    if [ -n "${SERVER_PID:-}" ]; then
        kill -TERM "$SERVER_PID" 2>/dev/null || true
        wait "$SERVER_PID" 2>/dev/null || true
    fi
    echo "✅ Server stopped"
    exit 0
}

trap shutdown SIGTERM SIGINT

# Start Prefect server in background
prefect server start \
    --host "${PREFECT_SERVER_API_HOST:-0.0.0.0}" \
    --port "${PREFECT_SERVER_API_PORT:-4200}" &
SERVER_PID=$!

echo "⏳ Waiting for server to be ready..."

# Wait for server health check
MAX_RETRIES=30
RETRY_COUNT=0
HEALTH_URL="http://localhost:${PREFECT_SERVER_API_PORT:-4200}/api/health"

until curl -sf "$HEALTH_URL" > /dev/null 2>&1; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "❌ Server failed to start after ${MAX_RETRIES} attempts"
        kill "$SERVER_PID" 2>/dev/null || true
        exit 1
    fi
    
    # Check if server process is still running
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
        echo "❌ Server process died unexpectedly"
        exit 1
    fi
    
    echo "   Retry ${RETRY_COUNT}/${MAX_RETRIES}..."
    sleep 2
done

echo "✅ Server ready at http://localhost:${PREFECT_SERVER_API_PORT:-4200}"

# Create default work pool if it doesn't exist
echo "📋 Setting up default work pool..."
if prefect work-pool inspect docker-pool > /dev/null 2>&1; then
    echo "✅ Work pool 'docker-pool' already exists"
else
    echo "📦 Creating docker work pool 'docker-pool'..."
    # Use docker type since workers ARE in containers and need to spawn flow runs
    prefect work-pool create docker-pool --type docker > /dev/null 2>&1 || true
    if prefect work-pool inspect docker-pool > /dev/null 2>&1; then
        echo "✅ Work pool 'docker-pool' created"
    else
        echo "⚠️  Failed to create work pool (will retry)"
    fi
fi

# Deploy flows using Python API
echo "📦 Deploying flows..."
if python /usr/local/bin/deploy_flows.py; then
    echo "✅ Flows deployed successfully"
else
    echo "⚠️  Flow deployment failed (server will continue)"
fi

echo "🎉 Prefect server fully initialized"
echo "📊 Web UI: http://localhost:${PREFECT_SERVER_API_PORT:-4200}"
echo ""

# Keep server running and forward signals
wait "$SERVER_PID"
