# Stage 1 Validation

Run `sh scripts/validate_stage1.sh` after `docker compose up -d`.

The script reports the schema and ordered fixtures, checks every `created_at`,
tests ID `1` with `john@example.com`, and confirms ID `1` with
`sarah@example.com` returns zero rows. It switches to `support_reader` before
the read and write tests and fails unless PostgreSQL rejects both `UPDATE` and
`DELETE`.

For a controlled Tool error, select a misspelled explicit column from
`support_requests` in a development run. `add_error` is disabled. The Analysis
Agent must suppress raw errors and normalize the result as:

```json
{
  "succeeded": false,
  "records_found": false,
  "failure_category": "database_query_failed",
  "handoff_recommended": false,
  "safe_explanation": "Support request data is temporarily unavailable. Please try again."
}
```

The exported Flow may contain the literal variable name `SUPPORT_DB_URL`, but
never its resolved connection string.
