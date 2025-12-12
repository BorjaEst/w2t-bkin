# Docker Compose Files for CI/CD Testing

This directory contains Docker Compose configurations used **exclusively for CI/CD testing**. These files are **NOT for production use**.

## ⚠️ Important: Not for Users

If you're a user looking to deploy w2t-bkin, **do not use these files**. They are designed for automated testing in GitHub Actions only.

For production deployment, see:

- [Migration Guide](../../docs/MIGRATION_GUIDE.md)
- [Docker README](../../docker/README.md)

## Files

### `docker-compose.test.yml`

Used by `.github/workflows/test-containers.yml` for integration testing.

**Services:**

- `postgres`: Ephemeral PostgreSQL database for Prefect (uses tmpfs for speed)
- `worker`: Containerized worker for testing flow execution

**Usage in CI:**

```bash
# From repository root
docker compose -f .github/compose/docker-compose.test.yml build
docker compose -f .github/compose/docker-compose.test.yml up -d
docker compose -f .github/compose/docker-compose.test.yml logs
docker compose -f .github/compose/docker-compose.test.yml down -v
```

## Why Separate Directory?

Docker Compose files are placed in `.github/compose/` to:

1. **Clearly separate CI concerns from user-facing code**
2. **Prevent confusion** - users won't accidentally find and use test configs
3. **Keep test infrastructure organized** with other GitHub Actions files
4. **Make it obvious** these are for automation, not production

## Production Deployment (For Users)

Users should **NOT** use docker-compose. Instead:

```bash
# 1. Start Prefect server on host
w2t-bkin server start --config configs/standard.toml

# 2. Run worker container manually
docker build -f docker/Dockerfile -t w2t-bkin:worker .
docker run -d \
  --name w2t-worker \
  -v $(pwd)/data:/data \
  -v $(pwd)/models:/models \
  -v $(pwd)/configs:/configs \
  -e PREFECT_API_URL=http://host.docker.internal:4200/api \
  -e WORK_POOL=process-pool \
  w2t-bkin:worker
```

Or run workers locally (requires `pip install -e .[worker]`):

```bash
prefect worker start --pool process-pool
```

## Testing Locally

Developers can use this compose file to test the containerized setup:

```bash
# From repository root
cd .github/compose

# Start Prefect server on host first
prefect server start &

# Build and run test environment
docker compose -f docker-compose.test.yml up

# In another terminal, check logs
docker compose -f docker-compose.test.yml logs -f worker

# Cleanup
docker compose -f docker-compose.test.yml down -v
```

## Network Configuration

The test compose file creates an isolated network (`w2t-test-network`) and uses `extra_hosts` to ensure the worker can connect to services running on the host (Prefect server at `http://host.docker.internal:4200/api`).

This mirrors the production deployment pattern where:

- Prefect server runs on the host
- Workers run in Docker containers and connect to the host server
