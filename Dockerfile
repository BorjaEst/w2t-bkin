# Multi-stage Dockerfile for w2t-bkin
# Supports both server (Prefect orchestrator) and worker (pipeline executor) targets

# =============================================================================
# Base Stage: Common dependencies for both server and worker
# =============================================================================
FROM python:3.10-slim AS base

LABEL maintainer="BorjaEst <https://github.com/BorjaEst>"
LABEL org.opencontainers.image.source="https://github.com/BorjaEst/w2t-bkin"
LABEL org.opencontainers.image.description="W2T Body Kinematics Pipeline - Containerized"
LABEL org.opencontainers.image.licenses="Apache-2.0"

# Install system dependencies
# - ffmpeg: Video processing
# - libgl1-mesa-glx: OpenGL support for video analysis
# - libglib2.0-0: GLib for various libraries
# - curl: Health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1-mesa-glx \
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

# Copy Python package files
COPY --chown=w2t:w2t pyproject.toml README.md LICENSE ./
COPY --chown=w2t:w2t src/ ./src/

# Install Python package and dependencies
# Using --no-cache-dir to reduce image size
RUN pip install --no-cache-dir -e .[prefect] && \
    pip cache purge

# Verify installation
RUN python -m w2t_bkin.cli --version && \
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

# Switch back to root to install additional packages
USER root

# Install Prefect server dependencies
RUN pip install --no-cache-dir \
    prefect[server]>=3.0.0 \
    asyncpg>=0.29.0 \
    && pip cache purge

# Copy server entrypoint script
COPY --chown=w2t:w2t --chmod=755 docker/start-server.sh /usr/local/bin/start-server.sh

# Switch back to non-root user
USER w2t

# Expose Prefect UI port
EXPOSE 4200

# Environment variables for Prefect server
ENV PREFECT_SERVER_API_HOST=0.0.0.0
ENV PREFECT_SERVER_API_PORT=4200
ENV PREFECT_HOME=/app/.prefect
ENV PREFECT_LOGGING_LEVEL=INFO

# Create Prefect home directory
RUN mkdir -p /app/.prefect

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
