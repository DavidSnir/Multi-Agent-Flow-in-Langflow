\set ON_ERROR_STOP on
\connect support_demo

REVOKE ALL PRIVILEGES ON DATABASE support_demo FROM support_reader;
REVOKE ALL PRIVILEGES ON SCHEMA public FROM support_reader;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM support_reader;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM support_reader;

GRANT CONNECT ON DATABASE support_demo TO support_reader;
GRANT USAGE ON SCHEMA public TO support_reader;
GRANT SELECT ON TABLE support_requests TO support_reader;
