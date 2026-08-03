#!/bin/sh
set -eu

compose() {
    if [ -n "${COMPOSE_ENV_FILE:-}" ]; then
        docker compose --env-file "$COMPOSE_ENV_FILE" "$@"
    else
        docker compose "$@"
    fi
}

cleanup() {
    compose unpause postgres >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

compose pause postgres >/dev/null
compose exec -T -e STAGE1_E2E_MODE=database_failure langflow \
    /app/.venv/bin/python /app/stage1-scripts/validate_stage1_e2e.py
