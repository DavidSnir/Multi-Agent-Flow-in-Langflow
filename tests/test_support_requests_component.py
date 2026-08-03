import unittest
from unittest.mock import patch

from support_tools.support_requests_sql import SQLComponent


class SupportRequestsSQLComponentTests(unittest.TestCase):
    def test_only_query_is_agent_controlled(self):
        tool_inputs = [
            field.name
            for field in SQLComponent.inputs
            if getattr(field, "tool_mode", False)
        ]
        self.assertEqual(tool_inputs, ["query"])
        self.assertNotIn("add_error", [field.name for field in SQLComponent.inputs])
        self.assertNotIn("include_columns", [field.name for field in SQLComponent.inputs])

    @patch("support_tools.support_requests_sql.create_engine")
    def test_policy_rejection_never_connects(self, create_engine):
        component = SQLComponent(
            database_url="postgresql://support_reader:secret@postgres:5432/support_db",
            query="SELECT * FROM support_requests LIMIT 1",
        )
        result = component.run_sql_query().data
        create_engine.assert_not_called()
        self.assertEqual(result["failure_category"], "query_policy_rejected")
        self.assertNotIn("SELECT", str(result))
        self.assertNotIn("secret", str(result))

    @patch("support_tools.support_requests_sql.validate_connector_database_url_for_ssrf")
    @patch("support_tools.support_requests_sql.create_engine")
    def test_database_failure_is_normalized(self, create_engine, validate_url):
        del validate_url
        create_engine.side_effect = RuntimeError(
            "could not connect to postgresql://support_reader:secret@10.0.0.4/support_db"
        )
        component = SQLComponent(
            database_url="postgresql://support_reader:secret@postgres:5432/support_db",
            query="SELECT id FROM support_requests LIMIT 1",
        )
        result = component.run_sql_query().data
        self.assertEqual(result["failure_category"], "database_query_failed")
        self.assertNotIn("postgres", str(result))
        self.assertNotIn("secret", str(result))


if __name__ == "__main__":
    unittest.main()
