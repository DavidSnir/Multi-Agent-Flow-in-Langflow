\set ON_ERROR_STOP on
\connect support_demo

REVOKE CREATE ON SCHEMA public FROM PUBLIC;

CREATE TABLE IF NOT EXISTS support_requests (
    id SERIAL PRIMARY KEY,
    customer_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    priority VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_support_requests_customer_name
ON support_requests (customer_name);

CREATE INDEX IF NOT EXISTS idx_support_requests_email
ON support_requests (email);

CREATE INDEX IF NOT EXISTS idx_support_requests_priority_status
ON support_requests (priority, status);
