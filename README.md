# Jeen Part 3: Multi-Agent Flow

Stage 1 establishes a reproducible Langflow 1.11.1 environment with a separate,
read-only PostgreSQL support-data layer.

## Prerequisites

- Docker with Docker Compose
- A Google API key for the optional live model check

## Start

1. Copy `.env.example` to `.env` and set strong local values. `.env` is ignored
   by Git. Generate the required Fernet key with:

   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

   Store the result as `LANGFLOW_SECRET_KEY`. Set separate admin and reader
   database passwords, and URL-encode the reader password in `SUPPORT_DB_URL`.
2. Start the services:

   ```bash
   docker compose up -d
   ```

3. Wait until both services report healthy:

   ```bash
   docker compose ps
   ```

4. Open <http://localhost:7860> and sign in with the values configured in
   `LANGFLOW_SUPERUSER` and `LANGFLOW_SUPERUSER_PASSWORD`.

Langflow stores Flows and configuration in its internal SQLite database at
`/app/langflow/langflow.db` on the `langflow_data` volume. The explicit SQLite
URL prevents the image from placing its default database outside the mounted
volume. PostgreSQL stores future business data in `support_postgres_data` and
is not Langflow's application database.

## Health And Connectivity

The Langflow container checks `http://localhost:7860/api/v1/version`. PostgreSQL
uses `pg_isready` against `support_db`.

Validate the schema, fixtures, matching and empty lookups, and denied writes:

```bash
sh scripts/validate_stage1.sh
```

Check persistence by noting the Flow in the UI, restarting only Langflow, and
confirming the Flow remains:

```bash
docker compose restart langflow
docker compose ps
```

Do not use `docker compose down -v` unless persistent local data should be
deleted.

## Flow Skeleton

Run `python scripts/create_flow_skeleton.py` against the healthy stack. The SQL
Database component operates as a Tool connected only to `P3 Analysis`; Gmail
remains a later-stage placeholder.

The Flow stores only the `SUPPORT_DB_URL` variable reference. Secret values must
never be embedded directly in a Flow export.

## Model Validation

The Stage 0 target is Google Generative AI model `gemini-3.1-flash-lite` with
temperature `0`, using a temporary `Chat Input -> Agent -> Chat Output` path
that returns `playground-ok`. If the model is unavailable, retain the configured
identifier and record the provider's exact error; do not silently substitute a
different model.

The executed model and environment checks are recorded in
`docs/stage0-validation.md`.

Planned production temperatures are:

| Agent | Model | Temperature |
| --- | --- | ---: |
| `P3 Orchestrator` | `gemini-3.1-flash-lite` | 0 |
| `P3 Analysis` | `gemini-3.1-flash-lite` | 0 |
| `P3 Response` | `gemini-3.1-flash-lite` | 0.2 |

## Stop

```bash
docker compose down
```
