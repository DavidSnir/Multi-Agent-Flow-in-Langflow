# Stage 1 Validation

Run `sh scripts/validate_stage1.sh` after `docker compose up -d`.

The script reports and asserts the exact schema and five ordered fixtures. It
then runs inside the Langflow container and authenticates through the actual
`SUPPORT_DB_URL` as `support_reader`. It tests ID `1` with
`john@example.com`, confirms ID `1` with `sarah@example.com` returns zero rows,
and fails unless PostgreSQL rejects both `UPDATE` and `DELETE`.

The guarded Tool has no `add_error` argument. A controlled unavailable-database
run returns this fixed shape without a raw exception:

```json
{
  "succeeded": false,
  "records_found": false,
  "failure_category": "database_query_failed",
  "handoff_recommended": false,
  "safe_explanation": "Support request data is temporarily unavailable. Please try again.",
  "records": []
}
```

The exported Flow may contain the literal variable name `SUPPORT_DB_URL`, but
never its resolved connection string.

## Executed Evidence

Validation was executed on 2026-08-03 against Langflow 1.11.1 and PostgreSQL
16 using Docker-network hostname `postgres`.

| Scenario | Result | Sanitized Trace ID |
| --- | --- | --- |
| ID `1`, `john@example.com` | One record; status `Open` | `a3a40d6b-e746-4b78-9dd7-cde2839be573` |
| ID `1`, `sarah@example.com` | Successful zero-record result; no John data | `bb0d4ce3-371b-4ea7-94fc-63f0933640d7` |
| PostgreSQL paused | Normalized `database_query_failed`; Flow status `ok` | `0b173ea8-aca9-414e-bbcf-e026ed3424c2` |

Each Trace contained `P3 Orchestrator`, `P3 Analysis`, and the guarded SQL Tool.
The Analysis response content blocks recorded an invocation of
`support_requests_sql`; the Orchestrator has no SQL Tool edge. Recursive scans
of API responses and Trace payloads found no database URL, reader password,
Langflow API key, Google API key, or superuser password.

Direct connection evidence:

```text
reader_authentication=passed
valid_lookup=1:john@example.com:John Smith
empty_lookup=1:sarah@example.com:0_records
reader_update=denied
reader_delete=denied
controlled_database_failure=normalized
```

The initializer was rerun after inserting a sixth administrative test row. The
row remained present, fixture ID `1` remained `Open`, and the initializer only
advanced the sequence. The test row was removed after this check.
