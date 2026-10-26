\set ON_ERROR_STOP on

\getenv langflow_password LANGFLOW_DB_PASSWORD
\getenv support_password SUPPORT_DB_PASSWORD

SELECT 'CREATE ROLE langflow_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'langflow_app')
\gexec

SELECT 'CREATE ROLE support_reader LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'support_reader')
\gexec

SELECT format('ALTER ROLE langflow_app PASSWORD %L', :'langflow_password')
\gexec

SELECT format('ALTER ROLE support_reader PASSWORD %L', :'support_password')
\gexec

SELECT 'CREATE DATABASE langflow_internal OWNER langflow_app'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'langflow_internal')
\gexec

SELECT 'CREATE DATABASE support_demo'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'support_demo')
\gexec

REVOKE CONNECT, TEMPORARY ON DATABASE langflow_internal FROM PUBLIC;
REVOKE CONNECT, TEMPORARY ON DATABASE support_demo FROM PUBLIC;

GRANT CONNECT, TEMPORARY ON DATABASE langflow_internal TO langflow_app;
GRANT CONNECT ON DATABASE support_demo TO support_reader;

ALTER ROLE support_reader SET default_transaction_read_only = on;
