import os

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from support_tools.support_requests_sql import SQLComponent


def require(condition, message):
    if not condition:
        raise AssertionError(message)


database_url = os.environ["SUPPORT_DB_URL"]
parsed_url = make_url(database_url)
require(parsed_url.username == "support_reader", "SUPPORT_DB_URL must use support_reader")
require(parsed_url.host == "postgres", "SUPPORT_DB_URL must use the Docker postgres hostname")
require(parsed_url.database == "support_db", "SUPPORT_DB_URL must use support_db")

engine = create_engine(database_url, pool_pre_ping=True)
with engine.connect() as connection:
    identity = connection.execute(
        text("SELECT current_user, session_user, current_database(), current_setting('transaction_read_only')")
    ).one()
    require(identity[0] == "support_reader", "Connection did not authenticate as support_reader")
    require(identity[1] == "support_reader", "Session user is not support_reader")
    require(identity[2] == "support_db", "Connection reached the wrong database")
    require(identity[3] == "on", "Reader transactions are not read-only")

valid_query = (
    "SELECT id, customer_name, email, category, priority, status "
    "FROM support_requests WHERE id = 1 AND email = 'john@example.com' LIMIT 50"
)
valid_result = SQLComponent(database_url=database_url, query=valid_query).run_sql_query().data
require(valid_result["succeeded"], "Valid guarded query failed")
require(valid_result["records_found"], "Valid guarded query returned no record")
require(len(valid_result["records"]) == 1, "Valid guarded query did not return exactly one record")
require(valid_result["records"][0]["customer_name"] == "John Smith", "Valid lookup returned the wrong customer")

empty_query = (
    "SELECT id, status FROM support_requests "
    "WHERE id = 1 AND email = 'sarah@example.com' LIMIT 50"
)
empty_result = SQLComponent(database_url=database_url, query=empty_query).run_sql_query().data
require(empty_result["succeeded"], "Empty guarded query was treated as an error")
require(not empty_result["records_found"], "Mismatched identity lookup exposed a record")
require(empty_result["records"] == [], "Mismatched identity lookup returned customer data")

for statement in (
    "UPDATE support_requests SET status = 'Closed' WHERE id = 1",
    "DELETE FROM support_requests WHERE id = 1",
):
    try:
        with engine.begin() as connection:
            connection.execute(text(statement))
    except SQLAlchemyError:
        continue
    raise AssertionError("support_reader unexpectedly executed a write")

with engine.connect() as connection:
    status = connection.execute(text("SELECT status FROM support_requests WHERE id = 1")).scalar_one()
require(status == "Open", "Denied writes changed the fixture")

failure_url = parsed_url.set(database="controlled_missing_database").render_as_string(hide_password=False)
failure_result = SQLComponent(database_url=failure_url, query=valid_query).run_sql_query().data
require(not failure_result["succeeded"], "Controlled database failure unexpectedly succeeded")
require(failure_result["failure_category"] == "database_query_failed", "Database failure was not normalized")
serialized_failure = str(failure_result)
for forbidden in (parsed_url.password or "", "postgres", "support_reader", "controlled_missing_database"):
    if forbidden:
        require(forbidden not in serialized_failure, "Normalized failure exposed internal connection details")

print("reader_authentication=passed")
print("valid_lookup=1:john@example.com:John Smith")
print("empty_lookup=1:sarah@example.com:0_records")
print("reader_update=denied")
print("reader_delete=denied")
print("controlled_database_failure=normalized")
