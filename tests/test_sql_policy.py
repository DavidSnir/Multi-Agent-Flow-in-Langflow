import unittest

from support_runtime.sql_policy import QueryPolicyError, validate_support_query


class SupportSQLPolicyTests(unittest.TestCase):
    def assert_rejected(self, query):
        with self.assertRaises(QueryPolicyError):
            validate_support_query(query)

    def test_accepts_explicit_limited_lookup(self):
        validated = validate_support_query(
            "SELECT id, status FROM support_requests "
            "WHERE id = 1 AND email = 'john@example.com' LIMIT 50"
        )
        self.assertFalse(validated.aggregate)
        self.assertIn("LIMIT 50", validated.sql)

    def test_accepts_public_schema_alias_and_ordering(self):
        validate_support_query(
            "SELECT sr.id, sr.created_at FROM public.support_requests AS sr "
            "WHERE sr.status = 'Open' ORDER BY sr.created_at DESC LIMIT 10"
        )

    def test_semicolon_in_string_is_not_a_second_statement(self):
        validate_support_query(
            "SELECT id FROM support_requests WHERE category = 'Login; Issue' LIMIT 1"
        )

    def test_accepts_approved_aggregate(self):
        validated = validate_support_query(
            "SELECT status, COUNT(id) FROM support_requests GROUP BY status ORDER BY status"
        )
        self.assertTrue(validated.aggregate)

    def test_rejects_unsafe_or_unbounded_queries(self):
        rejected = [
            "SELECT * FROM support_requests LIMIT 1",
            "SELECT id FROM support_requests",
            "SELECT id FROM support_requests LIMIT 51",
            "SELECT id FROM support_requests; SELECT email FROM support_requests",
            "UPDATE support_requests SET status = 'Closed' WHERE id = 1",
            "WITH requests AS (SELECT id FROM support_requests) SELECT id FROM requests LIMIT 1",
            "SELECT id FROM support_requests UNION SELECT id FROM support_requests",
            "SELECT id FROM pg_catalog.pg_tables LIMIT 1",
            "SELECT current_database(), id FROM support_requests LIMIT 1",
            "SELECT id FROM support_requests WHERE id IN (SELECT id FROM support_requests) LIMIT 1",
            "SELECT id FROM support_requests JOIN other_table USING (id) LIMIT 1",
            "SELECT missing_column FROM support_requests LIMIT 1",
            'SELECT "id" FROM support_requests LIMIT 1',
            "SELECT COUNT(*) FROM support_requests",
            "SELECT id FROM support_requests TABLESAMPLE SYSTEM (10) LIMIT 1",
            "SELECT id, COUNT(id) OVER () FROM support_requests LIMIT 1",
            "SELECT id FROM support_requests LIMIT 1 FOR UPDATE",
        ]
        for query in rejected:
            with self.subTest(query=query):
                self.assert_rejected(query)


if __name__ == "__main__":
    unittest.main()
