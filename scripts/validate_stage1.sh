#!/bin/sh
set -eu

compose() {
    if [ -n "${COMPOSE_ENV_FILE:-}" ]; then
        docker compose --env-file "$COMPOSE_ENV_FILE" "$@"
    else
        docker compose "$@"
    fi
}

compose exec -T postgres psql -v ON_ERROR_STOP=1 -U support_admin -d support_db <<'SQL'
SELECT column_name, data_type, character_maximum_length, column_default
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'support_requests'
ORDER BY ordinal_position;

SELECT id, customer_name, email, category, priority, status, created_at IS NOT NULL AS created_at_populated
FROM public.support_requests
ORDER BY id;

DO $validation$
BEGIN
    IF (SELECT COUNT(*) FROM public.support_requests) <> 5 THEN
        RAISE EXCEPTION 'support_requests must contain exactly five fixtures in a fresh environment';
    END IF;
    IF EXISTS (
        (SELECT id, customer_name, email, category, priority, status FROM public.support_requests)
        EXCEPT
        (VALUES
            (1, 'John Smith', 'john@example.com', 'Login Issue', 'High', 'Open'),
            (2, 'Sarah Cohen', 'sarah@example.com', 'Billing', 'Medium', 'In Progress'),
            (3, 'David Levi', 'david@example.com', 'Technical Support', 'Low', 'Closed'),
            (4, 'Emma Johnson', 'emma@example.com', 'Account Access', 'High', 'Open'),
            (5, 'Michael Brown', 'michael@example.com', 'Subscription', 'Medium', 'Open')
        )
    ) OR EXISTS (SELECT FROM public.support_requests WHERE created_at IS NULL) THEN
        RAISE EXCEPTION 'support_requests fixtures do not match the Stage 1 assignment';
    END IF;
END
$validation$;
SQL

compose exec -T langflow /app/.venv/bin/python /app/stage1-scripts/validate_reader_connection.py

echo "Stage 1 database validation passed with the actual support_reader connection."
