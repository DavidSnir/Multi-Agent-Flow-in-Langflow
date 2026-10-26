# Operations Runbook

## Initial Setup

1. Create the local `.env` from `.env.example`.
2. Replace every placeholder with a distinct secret or valid provider key.
3. Keep database names, users, host, and port unchanged.
4. Validate configuration.
5. Validate Compose rendering.
6. Start the services.

```bash
python3 scripts/verify_environment.py --env-file .env
docker compose config
docker compose up -d
```

Do not publish `docker compose config` output because it contains resolved secrets.

## Health and Status

```bash
docker compose ps
docker compose logs langflow
docker compose logs postgres
curl --fail --silent http://localhost:7860/health_check
```

Healthy Langflow returns a response containing `"status":"ok"`, `"chat":"ok"`, and `"db":"ok"`.

Open <http://localhost:7860> and confirm a login is required. Sign in with the local `LANGFLOW_SUPERUSER` credentials.

## Verify Global Variables

Sign in, then open **Settings > Global Variables** and confirm the names `SUPPORT_DATABASE_URL`, `GEMINI_API_KEY`, `GOOGLE_API_KEY`, and `COMPOSIO_API_KEY` are present and masked. Langflow materializes environment-backed variables for the user during login. Use `GOOGLE_API_KEY` for Google/Gemini components. Do not paste values into components.

## Verify Support Data

```bash
docker compose exec langflow python /app/project-scripts/db_smoke_test.py
```

The command must report five initial records, two high-priority open requests, and read-only permissions.

## Normal Restart and Persistence

```bash
docker compose down
docker compose up -d
docker compose ps
docker compose exec langflow python /app/project-scripts/db_smoke_test.py
```

The same named volumes are reattached. PostgreSQL initialization scripts do not rerun because the data directory is not empty.

## Stop Services

```bash
docker compose down
```

This removes containers and networks but preserves data volumes.

## Destructive Reset

Use this only for disposable local data. It deletes Langflow users, Flows, traces, Global Variables, and both PostgreSQL databases:

```bash
docker compose down --volumes
docker compose up -d
```

After a reset, PostgreSQL runs all scripts in `database/init/` again.

## Changed Database Passwords

Changing role passwords in `.env` does not update an already initialized PostgreSQL volume because entrypoint scripts run only on first initialization. For a disposable environment, reset the volumes. For retained data, rotate each PostgreSQL role password administratively and update the matching URL in the same maintenance window.

## Diagnostics

### PostgreSQL unhealthy

Inspect `docker compose logs postgres` for invalid initialization SQL, storage errors, or password-variable issues. Confirm the volume is writable and the administrator variables are present.

### Langflow database errors

Confirm `LANGFLOW_DATABASE_URL` uses `langflow_app`, host `postgres`, port `5432`, and database `langflow_internal`. Confirm its password matches `LANGFLOW_DB_PASSWORD`.

### Support smoke test fails to connect

Confirm `SUPPORT_DATABASE_URL` uses `support_reader`, host `postgres`, port `5432`, and database `support_demo`. Run the test inside the Langflow container rather than directly on the host.

If the SQL Tool reports that `postgres` resolves to a blocked private IP, confirm the running Langflow container has `LANGFLOW_SSRF_ALLOWED_HOSTS=postgres` and recreate it after configuration changes. Do not disable SSRF protection globally.

### Initialization changes do not appear

SQL files are first-start initialization, not migrations. Existing volumes retain their prior schema. Apply an explicit migration or reset disposable volumes.

## Secret Review Before Delivery

Review tracked and changed files:

```bash
git status --short
git diff -- . ':(exclude).env'
git log -p --all
```

Search tracked project content for suspicious assignments and private-key markers. Review every match; `.env.example` is expected to contain obvious placeholders only.

```bash
rg -n --hidden --glob '!.git/**' --glob '!.env' '(api[_-]?key|password|client[_-]?secret|refresh[_-]?token|BEGIN [A-Z ]*PRIVATE KEY|postgresql://[^[:space:]]+:[^@[:space:]]+@)'
```

Inspect any future `flow/*.json` export separately and confirm it references Global Variable names without containing values.
