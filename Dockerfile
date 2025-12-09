# Multi-stage Dockerfile for w2t-bkin
# Supports both server (Prefect orchestrator) and worker (pipeline executor) targets

# =============================================================================
# Base Stage: Common dependencies for both server and worker
# =============================================================================
FROM python:3.10-slim AS base

# Get target platform for conditional compilation flags
ARG TARGETPLATFORM
ARG BUILDPLATFORM

LABEL maintainer="BorjaEst <https://github.com/BorjaEst>"
LABEL org.opencontainers.image.source="https://github.com/BorjaEst/w2t-bkin"
LABEL org.opencontainers.image.description="W2T Body Kinematics Pipeline - Containerized"
LABEL org.opencontainers.image.licenses="Apache-2.0"

# Install system dependencies
# - build-essential: GCC, G++, make for compiling Python packages (numcodecs, etc.)
# - ffmpeg: Video processing
# - libgl1: OpenGL support for video analysis (replaces libgl1-mesa-glx in newer Debian)
# - libglib2.0-0: GLib for various libraries
# - curl: Health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
# Using uid 1000 for compatibility with most host systems
RUN useradd -m -u 1000 -s /bin/bash w2t && \
    mkdir -p /app /data /models /configs /output && \
    chown -R w2t:w2t /app /data /models /configs /output

# Set working directory
WORKDIR /app

# Set environment variables for cross-platform builds
# Disable x86-specific optimizations to avoid build failures on ARM
# These prevent numcodecs and other packages from using -msse2, -mavx2 flags on ARM
ENV DISABLE_NUMCODECS_AVX2=1 \
    DISABLE_NUMCODECS_SSE2=1

# =============================================================================
# BUILD OPTIMIZATION: Install dependencies BEFORE copying source code
# This creates cached layers for heavy packages (PyTorch, DeepLabCut, etc.)
# Rebuilds only take 30 seconds instead of 10+ minutes when code changes
# =============================================================================

# Step 1: Copy only pyproject.toml to detect dependency changes
COPY --chown=w2t:w2t pyproject.toml README.md LICENSE ./

# Step 2: Copy NWB extensions (required for [full] extras installation)
COPY --chown=w2t:w2t nwb-extensions/ ./nwb-extensions/

# Step 3: Copy source code (required for editable installation)
COPY --chown=w2t:w2t src/ ./src/

# Step 4: Install with [full,prefect] extras
# [full] includes all heavy dependencies: deeplabcut[tf], pynwb, h5py, scipy, pandas, tables, etc.
# [prefect] includes Prefect orchestration (optional for server/worker)
# This layer is cached and only rebuilds when pyproject.toml changes
# Use --prefer-binary to avoid building from source when wheels are available
# Set CFLAGS conditionally to avoid x86-specific flags on ARM
# Aggressive cleanup to reduce layer size
RUN set -e; \
    if [ "$(uname -m)" != "x86_64" ]; then \
    CFLAGS="-O2"; \
    echo "Building for $(uname -m) with generic optimizations"; \
    else \
    CFLAGS=""; \
    fi; \
    CFLAGS="$CFLAGS" pip install --no-cache-dir --prefer-binary -e .[full,prefect] && \
    pip cache purge && \
    # Clean up build artifacts to save space
    find /usr/local -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true && \
    find /usr/local -type f -name '*.pyc' -delete 2>/dev/null || true && \
    find /usr/local -type f -name '*.pyo' -delete 2>/dev/null || true && \
    # Remove test files and examples that take up space
    find /usr/local/lib/python3.10/site-packages -type d -name 'tests' -exec rm -rf {} + 2>/dev/null || true && \
    find /usr/local/lib/python3.10/site-packages -type d -name 'test' -exec rm -rf {} + 2>/dev/null || true

# Remove build dependencies to reduce image size
RUN apt-get purge -y --auto-remove build-essential && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Verify installation
RUN python -m w2t_bkin.cli version && \
    ffmpeg -version | head -n 1

# Switch to non-root user
USER w2t

# Set Python unbuffered mode for better logging
ENV PYTHONUNBUFFERED=1

# Default environment variables (can be overridden)
ENV DATA_ROOT=/data
ENV MODELS_ROOT=/models
ENV CONFIG_ROOT=/configs
ENV OUTPUT_ROOT=/output

# =============================================================================
# Server Stage: Prefect server and UI
# =============================================================================
FROM base AS server

# Stay as root to fix permissions for Prefect UI
USER root

# Prefect v3 is already installed in base layer
# Just install asyncpg for PostgreSQL support
RUN pip install --no-cache-dir asyncpg>=0.29.0 && \
    pip cache purge

# Fix permissions for Prefect UI directory (Prefect v3 needs write access)
RUN mkdir -p /usr/local/lib/python3.10/site-packages/prefect/server/ui_build && \
    chown -R w2t:w2t /usr/local/lib/python3.10/site-packages/prefect/server/ui_build && \
    chmod -R 755 /usr/local/lib/python3.10/site-packages/prefect/server/ui_build

# Copy server scripts
COPY --chown=w2t:w2t --chmod=755 docker/start-server.sh /usr/local/bin/start-server.sh
COPY --chown=w2t:w2t --chmod=755 docker/deploy_flows.py /usr/local/bin/deploy_flows.py

# Create Prefect home directory with correct permissions
RUN mkdir -p /app/.prefect && chown -R w2t:w2t /app/.prefect

# Switch to non-root user
USER w2t

# Expose Prefect UI port
EXPOSE 4200

# Environment variables for Prefect server
ENV PREFECT_SERVER_API_HOST=0.0.0.0
ENV PREFECT_SERVER_API_PORT=4200
ENV PREFECT_UI_API_URL=/api
ENV PREFECT_HOME=/app/.prefect
ENV PREFECT_LOGGING_LEVEL=INFO

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:4200/api/health || exit 1

ENTRYPOINT ["/usr/local/bin/start-server.sh"]

# =============================================================================
# Worker Stage: Pipeline executor
# =============================================================================
FROM base AS worker

# Copy worker entrypoint script
COPY --chown=w2t:w2t --chmod=755 docker/start-worker.sh /usr/local/bin/start-worker.sh

# Environment variables for Prefect worker
ENV PREFECT_API_URL=http://server:4200/api
ENV WORK_POOL=docker-pool
ENV WORKER_NAME=worker
ENV PREFECT_LOGGING_LEVEL=INFO

# Volume mount points (documentation)
VOLUME ["/data", "/models", "/configs", "/output"]

ENTRYPOINT ["/usr/local/bin/start-worker.sh"]

# =============================================================================
# Development Stage: For local development with hot-reload
# =============================================================================
FROM worker AS dev

USER root

# Install development tools
RUN pip install --no-cache-dir \
    black~=25.9.0 \
    isort~=7.0.0 \
    pytest~=9.0.0 \
    ipython \
    && pip cache purge

USER w2t

# Override entrypoint for interactive development
ENTRYPOINT ["/bin/bash"]
