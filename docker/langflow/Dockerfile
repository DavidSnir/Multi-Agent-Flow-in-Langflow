FROM langflowai/langflow:1.11.1

RUN uv pip install --python /app/.venv/bin/python "sqlglot==27.29.0"

COPY support_runtime /app/.venv/lib/python3.14/site-packages/support_runtime
