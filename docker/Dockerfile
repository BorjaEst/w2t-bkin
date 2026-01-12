# Dockerfile for w2t-bkin worker
# Single-stage build for pipeline execution with Prefect worker

FROM python:3.10-slim

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
# BUILD OPTIMIZATION: Layer Ordering Strategy (Least → Most Frequently Changing)
# =============================================================================
# Docker caches layers and reuses them if the instruction hasn't changed.
# Optimal ordering minimizes cache invalidation:
#
# 1. NWB Extensions (git submodules)     → Changes rarely (external repos)
# 2. pyproject.toml (dependencies)       → Changes occasionally (add/update deps)
# 3. Dummy package + pip install         → Rebuilds only when deps change (10+ min)
# 4. Source code (src/)                  → Changes frequently (development)
# 5. Final installation                  → Fast (30 sec) since deps cached
#
# Result: Editing src/ code triggers only steps 4-5 (fast rebuild)
#         Editing pyproject.toml triggers steps 2-5 (full rebuild)
# =============================================================================

# Step 1: Copy NWB extensions FIRST (change least frequently)
# These are git submodules - external repositories that rarely change
COPY --chown=w2t:w2t nwb-extensions/ ./nwb-extensions/

# Verify submodules are complete (fail fast if submodules not initialized)
RUN test -f ./nwb-extensions/ndx-events/pyproject.toml || \
    (echo "ERROR: ndx-events submodule incomplete. Run 'git submodule update --init --recursive'" && exit 1) && \
    test -f ./nwb-extensions/ndx-pose/pyproject.toml || \
    (echo "ERROR: ndx-pose submodule incomplete. Run 'git submodule update --init --recursive'" && exit 1) && \
    test -f ./nwb-extensions/ndx-structured-behavior/pyproject.toml || \
    (echo "ERROR: ndx-structured-behavior submodule incomplete. Run 'git submodule update --init --recursive'" && exit 1) && \
    echo "✓ All NWB extension submodules verified"

# Step 2: Install NWB extensions (local packages not on PyPI)
# These must be installed before main package since they're listed in dependencies
RUN pip install --no-cache-dir \
    -e ./nwb-extensions/ndx-events \
    -e ./nwb-extensions/ndx-pose \
    -e ./nwb-extensions/ndx-structured-behavior \
    && pip cache purge

# Step 3: Copy ONLY pyproject.toml and LICENSE (NOT README.md!)
# CRITICAL: README.md changes frequently and would invalidate the 2-hour dependency cache
# We create a dummy README.md in Step 4, then copy the real one in Step 5
COPY --chown=w2t:w2t pyproject.toml LICENSE ./

# Step 4: Install ALL heavy dependencies WITHOUT source code
# =============================================================================
# KEY OPTIMIZATION: Create minimal dummy package to satisfy pip install -e .[full,prefect]
# This allows installing all dependencies from pyproject.toml without needing src/ code.
#
# Why this works:
# - Flit (build backend) only needs __init__.py with __version__ for editable install
# - We extract version dynamically from pyproject.toml (no hardcoding)
# - We create a dummy README.md to satisfy Flit (real README copied in Step 5)
# - Dependencies are resolved and installed (PyTorch, DeepLabCut, etc.)
# - Layer is cached until pyproject.toml changes
#
# Cache behavior:
# - pyproject.toml unchanged → Layer cached (instant) ✅
# - README.md changed        → Layer still cached (README not copied yet) ✅ CRITICAL!
# - pyproject.toml changed   → Full rebuild (10+ min for heavy deps)
# - src/ code changed        → This layer still cached (fast rebuild)
# =============================================================================
RUN mkdir -p src/w2t_bkin && \
    # Create dummy README.md for Flit (real README copied in Step 5)
    echo "# w2t-bkin" > README.md && \
    echo "Dummy README for dependency installation. Real README copied later." >> README.md && \
    # Extract version dynamically from pyproject.toml (no hardcoding)
    PACKAGE_VERSION=$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/') && \
    echo "Building w2t-bkin version: $PACKAGE_VERSION" && \
    echo "__version__ = \"$PACKAGE_VERSION\"" > src/w2t_bkin/__init__.py && \
    echo 'def main(): pass' > src/w2t_bkin/cli.py && \
    set -e; \
    # Set architecture-specific compiler flags
    if [ "$(uname -m)" != "x86_64" ]; then \
    CFLAGS="-O2"; \
    echo "Building for $(uname -m) with generic optimizations"; \
    else \
    CFLAGS=""; \
    fi; \
    # Install base dependencies + worker extras (full installation)
    # Base includes: CLI, config, NWB, Prefect
    # Worker adds: Heavy ML/video processing libraries
    CFLAGS="$CFLAGS" pip install --no-cache-dir --prefer-binary -e .[worker] && \
    pip cache purge && \
    # Clean up build artifacts to reduce image size
    find /usr/local -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true && \
    find /usr/local -type f -name '*.pyc' -delete 2>/dev/null || true && \
    find /usr/local -type f -name '*.pyo' -delete 2>/dev/null || true

# Step 5: NOW copy the actual source code AND real README.md, then reinstall
# This step is FAST because all dependencies are already installed
# Only rebuilds when src/ or README.md changes (30 seconds)
# CRITICAL: Use --no-deps to prevent reinstalling dependencies (e.g., torch)
# All deps were installed in Step 4; this only updates the editable package code
COPY --chown=w2t:w2t src/ ./src/
COPY --chown=w2t:w2t README.md ./
RUN pip install --no-cache-dir --no-deps -e . && \
    pip cache purge

# Remove build dependencies to reduce image size
RUN apt-get purge -y --auto-remove build-essential && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Verify installation and version consistency
RUN EXPECTED_VERSION=$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/') && \
    INSTALLED_VERSION=$(python -c "import importlib.metadata; print(importlib.metadata.version('w2t-bkin'))" 2>/dev/null || echo "unknown") && \
    echo "Expected version: $EXPECTED_VERSION" && \
    echo "Installed version: $INSTALLED_VERSION" && \
    if [ "$INSTALLED_VERSION" != "$EXPECTED_VERSION" ]; then \
    echo "ERROR: Version mismatch detected!" && exit 1; \
    fi && \
    echo "✓ Version verification passed" && \
    echo "✓ Package installed successfully" && \
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

# Prefect worker environment variables
ENV PREFECT_API_URL=http://host.docker.internal:4200/api
ENV WORK_POOL=docker-pool
ENV WORKER_NAME=docker-worker
ENV LIMIT=1
ENV PREFECT_LOGGING_LEVEL=INFO

# Copy worker entrypoint script (from docker/ subdirectory since build context is repo root)
# This script is included in the image but not set as ENTRYPOINT
# Use Dockerfile.worker to build a worker-specific image
COPY --chown=w2t:w2t --chmod=755 docker/start-worker.sh /usr/local/bin/start-worker.sh

# Volume mount points (documentation)
VOLUME ["/data", "/models", "/configs", "/output"]

# Default CMD for flow-run containers (Prefect will override this)
# This image is designed to be used as the deployment image (image=...) for Prefect flows
# For a long-lived worker container, use Dockerfile.worker instead
CMD ["python", "-m", "w2t_bkin.cli", "version"]
