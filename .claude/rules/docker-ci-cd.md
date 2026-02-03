# Docker CI/CD Best Practices

Rules learned from debugging silent deployment failures.

## Always Use Fresh Builds in CI

```bash
# CORRECT - Force fresh builds and container recreation
docker compose build --no-cache
docker compose up -d --force-recreate --remove-orphans

# WRONG - May use cached layers and skip container restart
docker compose build
docker compose up -d
```

**Why:** Docker caches layers aggressively. Without `--no-cache`, code changes
may not be included. Without `--force-recreate`, containers may not restart even
with new images.

## Verify Deployment Actually Happened

After deploying, check container uptime to confirm restart:

```bash
# CORRECT - Use docker inspect to get actual container start time
CONTAINER=$(docker ps -qf name=api | head -1)
START=$(docker inspect --format '{{.State.StartedAt}}' $CONTAINER)
START_SEC=$(date -d "$START" +%s)
NOW_SEC=$(date +%s)
echo "Container uptime: $((NOW_SEC - START_SEC)) seconds"

# Or check docker ps status (shows "Up X seconds/minutes")
docker ps --format "{{.Names}}: {{.Status}}"

# WRONG - /proc/uptime shows HOST uptime, not container uptime!
# docker exec api cat /proc/uptime  # Don't use this!
```

If uptime shows hours after a "successful" deploy, containers weren't actually
restarted.

## Explicit Env File Checks

Docker compose only warns (doesn't fail) on missing env files:

```yaml
# This silently continues with empty vars if file is missing
--env-file .env.production
```

**Always add explicit checks:**

```bash
if [ ! -f .env.production ]; then
  echo "ERROR: .env.production not found"
  exit 1
fi
```

## Source Session

- 2026-01-15: Debugged noom.life deployment showing old code despite
  "successful" CI runs
