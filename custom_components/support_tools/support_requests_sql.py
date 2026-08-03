from sqlalchemy import create_engine, text

from lfx.custom.custom_component.component import Component
from lfx.io import MultilineInput, Output, SecretStrInput
from lfx.schema.data import Data
from lfx.utils.ssrf_protection import validate_connector_database_url_for_ssrf

from support_runtime.sql_policy import QueryPolicyError, validate_support_query


class SQLComponent(Component):
    display_name = "Support Requests SQL"
    description = "Safely reads approved fields from the support_requests table."
    name = "SQLComponent"
    icon = "database"

    inputs = [
        SecretStrInput(name="database_url", display_name="Database URL", required=True),
        MultilineInput(
            name="query",
            display_name="SQL Query",
            required=True,
            tool_mode=True,
            info="One policy-compliant SELECT statement against support_requests.",
        ),
    ]

    outputs = [
        Output(display_name="Support Request Result", name="run_sql_query", method="run_sql_query"),
    ]

    @staticmethod
    def _result(*, succeeded, records_found, failure_category, safe_explanation, records=None):
        return {
            "succeeded": succeeded,
            "records_found": records_found,
            "failure_category": failure_category,
            "handoff_recommended": False,
            "safe_explanation": safe_explanation,
            "records": records or [],
        }

    def run_sql_query(self) -> Data:
        try:
            validated = validate_support_query(self.query)
        except QueryPolicyError:
            result = self._result(
                succeeded=False,
                records_found=False,
                failure_category="query_policy_rejected",
                safe_explanation="The data request could not be run because it does not meet the read-only query policy.",
            )
            self.status = result
            return Data(data=result)

        try:
            validate_connector_database_url_for_ssrf(self.database_url)
            engine = create_engine(
                self.database_url,
                pool_pre_ping=True,
                connect_args={"connect_timeout": 3},
            )
            with engine.connect() as connection:
                rows = [dict(row) for row in connection.execute(text(validated.sql)).mappings().all()]
        except Exception:
            result = self._result(
                succeeded=False,
                records_found=False,
                failure_category="database_query_failed",
                safe_explanation="Support request data is temporarily unavailable. Please try again.",
            )
            self.status = result
            return Data(data=result)

        result = self._result(
            succeeded=True,
            records_found=bool(rows),
            failure_category=None,
            safe_explanation=(
                "Support request data was retrieved."
                if rows
                else "No matching support requests were found."
            ),
            records=rows,
        )
        self.status = result
        return Data(data=result)
