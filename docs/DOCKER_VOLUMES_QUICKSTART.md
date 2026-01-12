# Quick Start: Docker Volume Mounting

## For New Projects

```bash
# 1. Initialize experiment
cd /path/to/your/experiment
w2t-bkin data init . --lab "Your Lab" --institution "Your Org" --experimenters "Your Name" -y

# 2. Add subjects and sessions
w2t-bkin data add-subject . subject-001 -y
w2t-bkin data add-session . subject-001 session-001 -y

# 3. Build Docker images (if using local build)
cd /path/to/w2t-bkin/repo
docker build -f docker/Dockerfile -t w2t-bkin:local .

# 4. Configure Docker image in .workers/.env
cd /path/to/your/experiment
echo "W2T_DOCKER_IMAGE=w2t-bkin:local" > .workers/.env

# 5. Start Prefect server (creates work pool with volume mounts)
w2t-bkin server start

# 6. In a new terminal, start worker
cd /path/to/your/experiment
w2t-bkin worker start --pool docker-pool --type docker

# 7. Trigger flows via Prefect UI at http://localhost:4200
```

## For Existing Projects (Migration)

```bash
# 1. Delete old work pool (if it exists)
cd /path/to/your/experiment
prefect work-pool delete docker-pool

# 2. Restart server (recreates pool with volume mounts)
w2t-bkin server start

# 3. Verify volume mounts
prefect work-pool inspect docker-pool | grep -A 10 volumes

# Expected output:
#   "volumes": [
#     "/path/to/your/experiment/data:/data:rw",
#     "/path/to/your/experiment/models:/models:ro",
#     "/path/to/your/experiment/output:/output:rw"
#   ]
```

## Verification

Test that volume mounting works:

```bash
# Trigger a test flow run and check logs
# The container should:
# 1. NOT show errors like: FileNotFoundError: '/home/user/...'
# 2. Successfully read from /data/raw
# 3. Successfully write to /output
# 4. Create files visible on host in your/experiment/output/
```

## Troubleshooting

### Container can't find data

**Check 1: Work pool has volume mounts**

```bash
prefect work-pool inspect docker-pool | grep volumes
```

If no volumes shown, recreate the pool:

```bash
prefect work-pool delete docker-pool
w2t-bkin server start
```

**Check 2: Running in production mode**

```bash
# NOT: w2t-bkin server start --dev
w2t-bkin server start  # Production mode required
```

**Check 3: Data directories exist on host**

```bash
ls -la /path/to/experiment/data/raw
ls -la /path/to/experiment/models
ls -la /path/to/experiment/output
```

### Permission denied errors

Container runs as UID 1000. Fix host permissions:

```bash
sudo chown -R 1000:1000 /path/to/experiment/data
sudo chown -R 1000:1000 /path/to/experiment/output
```

Or use permissive mode (less secure):

```bash
chmod -R 777 /path/to/experiment/data
chmod -R 777 /path/to/experiment/output
```

## Key Concepts

- **Work pool configures mounts** - set once when pool is created
- **Container uses fixed paths** - always `/data`, `/models`, `/output`
- **Host paths are mounted** - your `experiment/data` → container `/data`
- **No manual docker run -v** - worker handles volume mounting automatically

## See Also

- [Docker Volumes and Paths Guide](../user-guide/docker-volumes-and-paths.md) - Detailed documentation
- [Implementation Details](../development/docker-volume-mounting-implementation.md) - Technical overview
