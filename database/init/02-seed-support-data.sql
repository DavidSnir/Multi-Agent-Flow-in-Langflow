\set ON_ERROR_STOP on
\connect support_demo

INSERT INTO support_requests
(customer_name, email, category, priority, status)
SELECT seed.customer_name, seed.email, seed.category, seed.priority, seed.status
FROM (
    VALUES
        ('John Smith', 'john@example.com', 'Login Issue', 'High', 'Open'),
        ('Sarah Cohen', 'sarah@example.com', 'Billing', 'Medium', 'In Progress'),
        ('David Levi', 'david@example.com', 'Technical Support', 'Low', 'Closed'),
        ('Emma Johnson', 'emma@example.com', 'Account Access', 'High', 'Open'),
        ('Michael Brown', 'michael@example.com', 'Subscription', 'Medium', 'Open')
) AS seed(customer_name, email, category, priority, status)
WHERE NOT EXISTS (SELECT 1 FROM support_requests);
