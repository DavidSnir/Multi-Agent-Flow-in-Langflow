# Jeen Part 3 External Infrastructure

This repository provides the Docker runtime, PostgreSQL support data, environment-variable handling, and external-service setup guidance for the Jeen Langflow multi-agent assignment. The Langflow Flow, agent prompts, routing, and tool wiring are intentionally out of scope.

## Prerequisites

- Docker Engine or Docker Desktop with Docker Compose v2
- Python 3.10 or newer for `scripts/verify_environment.py`
- `openssl` for generating local secrets
- Gemini and Composio API keys for complete external-variable configuration

## Repository Layout

```text
.
|-- docker-compose.yml
|-- database/init/       PostgreSQL first-start initialization
|-- scripts/             Environment and database smoke tests
|-- flow/                Future Langflow Flow exports
|-- docs/                Architecture and operating instructions
`-- runtime-data/        Ignored local runtime artifacts
```

## Environment Setup

Create a local `.env` from `.env.example`. The `.env` file is ignored by Git.

Generate a different value for each password and secret. Hex values avoid URL-encoding problems in PostgreSQL connection strings:

```bash
openssl rand -hex 24
openssl rand -hex 24
openssl rand -hex 24
openssl rand -hex 24
docker compose exec langflow python -c \
  'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

Use the generated values for:

- `POSTGRES_ADMIN_PASSWORD`
- `LANGFLOW_DB_PASSWORD`
- `SUPPORT_DB_PASSWORD`
- `LANGFLOW_SUPERUSER_PASSWORD`
- `LANGFLOW_SECRET_KEY`

`LANGFLOW_SECRET_KEY` is different from the passwords: Langflow `1.11.1` requires a 32-byte URL-safe base64 Fernet key. The final command generates it inside the running Langflow container. Docker `exec` targets the container directly, so the host mapping to port `17860` is not part of the command.

Update each database URL so its password exactly matches the corresponding password variable. Add valid provider keys for `GEMINI_API_KEY` and `COMPOSIO_API_KEY` when those integrations are available.

Validate the file without displaying its values:

```bash
python3 scripts/verify_environment.py --env-file .env
```

See [Environment Variables](docs/environment-variables.md) for the complete variable contract.

## Start Docker

```bash
docker compose config
docker compose up -d
docker compose ps
```

Langflow is available at <http://localhost:7860>. Automatic login is disabled; use `LANGFLOW_SUPERUSER` and `LANGFLOW_SUPERUSER_PASSWORD` from the local `.env`.

The Relay agent interface is available at <http://localhost:8080>. Open it, enter the Flow ID from the Langflow flow URL, and optionally add a Langflow API key. Relay starts each message through `POST /api/v2/workflows` in background mode and polls the job until it completes. This supports flows containing approval-capable tools; an approval that is actually reached is reported in the conversation. Connection settings remain in browser local storage.

Inspect logs when startup is incomplete:

```bash
docker compose logs langflow
docker compose logs postgres
```

## Database Verification

Run the smoke test inside the Langflow container, where the internal `postgres` hostname and PostgreSQL driver are available:

```bash
docker compose exec langflow python /app/project-scripts/db_smoke_test.py
```

Expected output:

```text
Database connection: OK
support_requests table: OK
Initial records: 5
John Smith lookup: OK
High-priority open requests: 2
Read-only permissions: OK
```

The SQL Database Tool in a future Flow must use the `SUPPORT_DATABASE_URL` Global Variable. It must not use the administrator or `langflow_app` credentials.

## Langflow Global Variables

At startup, Langflow receives these environment variables and materializes them as masked credential-type Global Variables when the user signs in:

- `SUPPORT_DATABASE_URL`
- `GEMINI_API_KEY`
- `GOOGLE_API_KEY` (Langflow-compatible alias of `GEMINI_API_KEY`)
- `COMPOSIO_API_KEY`

Verify their names under **Settings > Global Variables** after signing in. Langflow creates environment-backed variables for each user during login. Google/Gemini components should use `GOOGLE_API_KEY`; both names resolve to the same runtime secret. Flow components should reference the variables rather than storing values in Flow JSON.

## Gmail

The repository is prepared for the Langflow Composio Gmail integration, but no Gmail account has been connected and no email smoke test has been performed. Follow [Gmail Setup](docs/gmail-setup.md) when Stage 5 external authentication is authorized.

## Stop and Restart

```bash
docker compose down
docker compose up -d
```

Normal `down` and `up` operations preserve both named volumes. Do not add `--volumes` unless all local Langflow and PostgreSQL data should be deleted.

## Troubleshooting

### Compose reports a missing variable

Create `.env`, replace every placeholder, and run the environment verifier. Compose intentionally fails fast when required values are absent.

### PostgreSQL starts but tables are missing

Initialization scripts run only when `postgres_data` is first created. Review `docker compose logs postgres`. For a disposable environment only, use the reset procedure in the [Runbook](docs/runbook.md).

### Langflow cannot connect to PostgreSQL

Confirm both database URLs use host `postgres`, not `localhost`, and that URL passwords match their password variables.

### SQL Tool reports that `postgres` resolves to a blocked IP

The Compose runtime sets `LANGFLOW_SSRF_ALLOWED_HOSTS=postgres`, allowing only the internal PostgreSQL service through Langflow's SSRF guard. Recreate the Langflow container after pulling this configuration; a browser refresh alone does not update container environment variables.

### Langflow remains unhealthy

Initial component loading can take several minutes. Check `docker compose logs langflow`; the health check uses `/health_check`, which validates Langflow's database and chat services.

If another local service already owns port `7860`, set `LANGFLOW_HOST_PORT` for that command, for example `LANGFLOW_HOST_PORT=17860 docker compose up -d`. The submitted default remains `7860`.

### Database smoke test cannot import psycopg

Confirm the pinned official Langflow image is running. It includes the PostgreSQL extra required by `LANGFLOW_DATABASE_URL`.

### Gmail authentication fails

No Gmail connection is established by this repository. Review the reconnection and failure guidance in [Gmail Setup](docs/gmail-setup.md).
