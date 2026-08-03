#!/bin/sh
set -eu

compose="docker compose"

$compose exec -T postgres psql -v ON_ERROR_STOP=1 -U support_admin -d support_db <<'SQL'
SELECT column_name, data_type, character_maximum_length, column_default
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'support_requests'
ORDER BY ordinal_position;

SELECT id, customer_name, email, category, priority, status, created_at IS NOT NULL AS created_at_populated
FROM public.support_requests
ORDER BY id;
SQL

$compose exec -T postgres psql -v ON_ERROR_STOP=1 -U support_admin -d support_db <<'SQL'
SET ROLE support_reader;
SELECT id, customer_name, email, category, priority, status
FROM public.support_requests
WHERE id = 1 AND email = 'john@example.com'
LIMIT 50;

SELECT id, status
FROM public.support_requests
WHERE id = 1 AND email = 'sarah@example.com'
LIMIT 50;
SQL

if $compose exec -T postgres psql -v ON_ERROR_STOP=1 -U support_admin -d support_db <<'SQL'
SET ROLE support_reader;
UPDATE public.support_requests SET status = 'Closed' WHERE id = 1;
SQL
then
    echo "ERROR: support_reader unexpectedly updated a record" >&2
    exit 1
fi

if $compose exec -T postgres psql -v ON_ERROR_STOP=1 -U support_admin -d support_db <<'SQL'
SET ROLE support_reader;
DELETE FROM public.support_requests WHERE id = 1;
SQL
then
    echo "ERROR: support_reader unexpectedly deleted a record" >&2
    exit 1
fi

if $compose exec -T postgres psql -v ON_ERROR_STOP=1 -U support_admin -d support_db >/dev/null 2>&1 <<'SQL'
SET ROLE support_reader;
SELECT missing_test_column FROM public.support_requests LIMIT 1;
SQL
then
    echo "ERROR: controlled invalid query unexpectedly succeeded" >&2
    exit 1
fi

echo "Stage 1 database validation passed; controlled error and reader writes were rejected."
