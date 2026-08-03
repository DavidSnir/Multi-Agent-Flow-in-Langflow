#!/bin/sh
set -eu

: "${SUPPORT_DB_READER_PASSWORD:?SUPPORT_DB_READER_PASSWORD is required}"

psql --set=ON_ERROR_STOP=1 --set=reader_password="$SUPPORT_DB_READER_PASSWORD" <<'SQL'
SELECT format(
    'CREATE ROLE support_reader LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION',
    :'reader_password'
)
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'support_reader') \gexec
SELECT format('ALTER ROLE support_reader PASSWORD %L', :'reader_password') \gexec

ALTER ROLE support_reader SET default_transaction_read_only = on;
REVOKE CONNECT ON DATABASE postgres FROM PUBLIC;
REVOKE CONNECT ON DATABASE template1 FROM PUBLIC;
REVOKE ALL ON DATABASE support_db FROM support_reader;
GRANT CONNECT ON DATABASE support_db TO support_reader;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM support_reader;
GRANT USAGE ON SCHEMA public TO support_reader;

CREATE TABLE IF NOT EXISTS public.support_requests (
    id SERIAL PRIMARY KEY,
    customer_name varchar(100),
    email varchar(255),
    category varchar(100),
    priority varchar(50),
    status varchar(50),
    created_at timestamp DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO public.support_requests
    (id, customer_name, email, category, priority, status)
VALUES
    (1, 'John Smith', 'john@example.com', 'Login Issue', 'High', 'Open'),
    (2, 'Sarah Cohen', 'sarah@example.com', 'Billing', 'Medium', 'In Progress'),
    (3, 'David Levi', 'david@example.com', 'Technical Support', 'Low', 'Closed'),
    (4, 'Emma Johnson', 'emma@example.com', 'Account Access', 'High', 'Open'),
    (5, 'Michael Brown', 'michael@example.com', 'Subscription', 'Medium', 'Open')
ON CONFLICT (id) DO NOTHING;

SELECT setval(
    pg_get_serial_sequence('public.support_requests', 'id'),
    GREATEST(
        (SELECT last_value FROM public.support_requests_id_seq),
        (SELECT COALESCE(MAX(id), 1) FROM public.support_requests)
    ),
    true
);

REVOKE ALL ON TABLE public.support_requests FROM PUBLIC, support_reader;
GRANT SELECT ON TABLE public.support_requests TO support_reader;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM support_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM support_reader;
SQL
