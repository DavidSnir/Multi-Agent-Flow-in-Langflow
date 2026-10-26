# External Architecture

```text
HTTP Client / Playground
          |
          v
       Langflow
       /      \
      v        v
PostgreSQL   Gmail / Composio
```

## Responsibility Boundary

Langflow runs the visual editor and API. Future Flow definitions, users, settings, encrypted Global Variables, and traces are application state managed by Langflow. Agent prompts, routing, SQL Tool wiring, and Gmail Tool wiring are not implemented in this repository.

PostgreSQL is a single server containing two isolated databases:

| Database | User | Purpose |
| --- | --- | --- |
| `langflow_internal` | `langflow_app` | Langflow users, Flows, settings, variables, and traces |
| `support_demo` | `support_reader` | Read-only assignment support-request queries |

`support_reader` has only `CONNECT`, schema `USAGE`, and `SELECT` on `support_requests`. It is not the owner of the database or table and has no write or DDL privileges.

## Container Networking

Both services share the Docker `backend` network, which is marked internal. Langflow reaches PostgreSQL at `postgres:5432`; `localhost` would refer to the Langflow container itself and must not be used.

Langflow SSRF protection remains enabled. The runtime allowlists only the `postgres` service name so SQL Database components can connect to the private backend address without granting access to arbitrary private hosts.

PostgreSQL has no published host port. Langflow also joins the `outbound` network so future Gemini and Composio requests can reach their external APIs. The Langflow UI is published only on `127.0.0.1:7860`.

## Gmail Authentication

Composio is the intended Gmail authentication boundary. `COMPOSIO_API_KEY` authenticates Langflow to Composio, while Google OAuth grants a dedicated test mailbox to a Composio connected account. OAuth access and refresh tokens must remain in the provider platforms and must not be committed or embedded in a Flow export.

No Gmail account is connected by the current implementation.

## Environment Variables

The ignored `.env` is the local source for database credentials, Langflow authentication, encryption, and provider API keys. Docker Compose passes only the variables each service needs.

Langflow imports `SUPPORT_DATABASE_URL`, `GEMINI_API_KEY`, its Langflow-compatible `GOOGLE_API_KEY` alias, and `COMPOSIO_API_KEY` as credential-type Global Variables. Their values are encrypted in Langflow's internal database using `LANGFLOW_SECRET_KEY` and masked in the editor.

## Persistent Storage

The `postgres_data` volume stores both PostgreSQL databases. The `langflow_data` volume stores Langflow configuration and filesystem data under `/app/langflow`.

These volumes survive:

```bash
docker compose down
docker compose up -d
```

Removing volumes deletes local application and database state. The `runtime-data/` directory is reserved for ignored local artifacts and is not a substitute for the named volumes.
