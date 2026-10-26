# Environment Variables

Real values belong in the ignored `.env` file. `.env.example` contains placeholders only. Never place credentials in SQL, Python, documentation screenshots, or Flow JSON.

## Variable Contract

| Variable | Consumer | Purpose |
| --- | --- | --- |
| `POSTGRES_ADMIN_USER` | PostgreSQL | Initialization administrator |
| `POSTGRES_ADMIN_PASSWORD` | PostgreSQL | Administrator password |
| `LANGFLOW_DB_NAME` | PostgreSQL tooling | Must be `langflow_internal` |
| `LANGFLOW_DB_USER` | PostgreSQL tooling | Must be `langflow_app` |
| `LANGFLOW_DB_PASSWORD` | PostgreSQL initialization | Langflow database role password |
| `LANGFLOW_DATABASE_URL` | Langflow | Internal application database URL |
| `SUPPORT_DB_NAME` | PostgreSQL tooling | Must be `support_demo` |
| `SUPPORT_DB_USER` | PostgreSQL tooling | Must be `support_reader` |
| `SUPPORT_DB_PASSWORD` | PostgreSQL initialization | Read-only role password |
| `SUPPORT_DATABASE_URL` | Langflow and SQL Tool | Read-only support database URL |
| `LANGFLOW_SUPERUSER` | Langflow | Initial administrator username |
| `LANGFLOW_SUPERUSER_PASSWORD` | Langflow | Initial administrator password |
| `LANGFLOW_SECRET_KEY` | Langflow | Encrypts stored secrets and variables |
| `LANGFLOW_CONFIG_DIR` | Langflow | Persistent path, `/app/langflow` |
| `GEMINI_API_KEY` | Future model component | Gemini authentication |
| `COMPOSIO_API_KEY` | Future Gmail component | Composio authentication |

`LANGFLOW_AUTO_LOGIN=false`, the Global Variable import list, and `LANGFLOW_SSRF_ALLOWED_HOSTS=postgres` are fixed non-secret settings in `docker-compose.yml`. The SSRF allowlist permits the SQL Tool to reach only the internal PostgreSQL service while retaining Langflow's protection for other private hosts. Compose exposes `GOOGLE_API_KEY` as an alias of `GEMINI_API_KEY` because Langflow's Google/Gemini components use the standard Google variable name.

## Generate Secrets

Generate a different URL-safe value for every password. For example:

```bash
openssl rand -hex 24
```

Generate the Langflow encryption key inside the running Langflow container:

```bash
docker compose exec langflow python -c \
  'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

This returns the 32-byte URL-safe base64 Fernet key required by Langflow. The container can be published on host port `17860`; `docker compose exec` does not require the port because it addresses the `langflow` service directly.

Do not reuse passwords between the PostgreSQL administrator, database roles, or Langflow administrator.

The password embedded in each URL must match its standalone password variable. If non-URL-safe characters are used, percent-encode the username and password in the URL. Hex-generated values need no encoding.

Expected internal URLs have these forms:

```text
postgresql://langflow_app:<password>@postgres:5432/langflow_internal
postgresql://support_reader:<password>@postgres:5432/support_demo
```

## Validate Configuration

```bash
python3 scripts/verify_environment.py --env-file .env
```

Successful output is:

```text
Environment configuration: valid
Required variables found: 16
Placeholder values found: 0
```

The script reports names of missing, placeholder, or inconsistent variables. It never prints their values.

## Global Variables

After Langflow becomes healthy, sign in and open **Settings > Global Variables**. Confirm these names exist:

```text
SUPPORT_DATABASE_URL
GEMINI_API_KEY
GOOGLE_API_KEY
COMPOSIO_API_KEY
```

Environment-imported variables are created for the user during sign-in, use credential type, and are masked in the visual editor. Google/Gemini components should select `GOOGLE_API_KEY`. Components must select these Global Variables instead of receiving copied values.

Changing `LANGFLOW_SECRET_KEY` after variables have been stored can make encrypted values unreadable. Preserve it with the deployment secrets and rotate it only with a planned migration.
