# Database Volume and Secret Rotation

PostgreSQL stores credentials in the data volume. Changing secrets doesn't
automatically update the database.

## The Problem

```bash
# This doesn't change the password in an existing database:
gh secret set DB_PASSWORD --body "new_password"
# Then deploy...
# Result: API can't connect - volume still has old password
```

## Solutions

### Option 1: Reset Database (Data Loss)

Use when you can afford to lose data:

```bash
# Remove volume
docker compose down -v
docker volume rm docker_postgres_data

# Redeploy - fresh database with new password
docker compose up -d
```

### Option 2: Update Password in Running DB

```bash
# Connect to postgres and change password
docker exec postgres psql -U user -d postgres -c \
  "ALTER USER moon PASSWORD 'new_password';"

# Restart API to pick up new credentials
docker restart api
```

### Option 3: Use fix-db-password Workflow

This project has a workflow for this:

```bash
# Update password only
gh workflow run fix-db-password.yml

# Reset entire database (data loss)
gh workflow run fix-db-password.yml -f reset_db=true
```

## Prevention

When rotating DB_PASSWORD:

1. First update password in running database
2. Then update GitHub Secret
3. Then deploy

Or use the fix-db-password workflow which handles this.

## Source Session

- 2026-01-15: Deploy failed after setting new DB_PASSWORD - old volume had
  different password
