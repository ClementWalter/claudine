# GitHub Secrets for Environment Variables

Never store production secrets manually on servers. Generate env files from
GitHub Secrets in CI.

## Pattern

```yaml
- name: Create production env file
  run: |
    cat > .env.production << 'ENVFILE'
    DATABASE_URL=postgresql://user:${{ secrets.DB_PASSWORD }}@postgres:5432/db
    JWT_SECRET=${{ secrets.JWT_SECRET }}
    S3_ACCESS_KEY=${{ secrets.S3_ACCESS_KEY }}
    # ... other secrets
    ENVFILE

    scp .env.production server:/path/.env.production
```

## Why

1. **Single source of truth** - Secrets in GitHub, not scattered across servers
2. **Auditability** - GitHub tracks secret changes
3. **Reproducibility** - New deploys always get correct secrets
4. **No manual errors** - Can't forget to update server env file

## Required Secrets for This Project

| Secret               | Purpose                                             |
| -------------------- | --------------------------------------------------- |
| `DB_PASSWORD`        | PostgreSQL password                                 |
| `JWT_SECRET`         | Auth token signing                                  |
| `JWT_REFRESH_SECRET` | Refresh token signing                               |
| `S3_ENDPOINT`        | Scaleway S3 endpoint                                |
| `S3_BUCKET`          | Object storage bucket                               |
| `S3_ACCESS_KEY`      | Scaleway access key                                 |
| `S3_SECRET_KEY`      | Scaleway secret key                                 |
| `CDN_URL`            | CDN/public URL for assets                           |
| `APP_URL`            | Public app URL                                      |
| `RESEND_API_KEY`     | Resend email service API key                        |
| `EMAIL_FROM`         | Sender email address (e.g., noreply@yourdomain.com) |
| `EMAIL_FROM_NAME`    | Sender name (e.g., Noom)                            |
| `SSH_PRIVATE_KEY`    | Deploy SSH key                                      |
| `SERVER_HOST`        | Target server IP                                    |

## Extracting Existing Secrets

If secrets exist on running container but not in GitHub:

```bash
# Run extract-secrets workflow or:
ssh root@server 'docker exec api env' | grep -E '^(JWT_|S3_|DB_)'
```

## Source Session

- 2026-01-15: Fixed deployment that failed silently due to missing
  .env.production on server
