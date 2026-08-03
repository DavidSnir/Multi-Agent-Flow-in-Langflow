# Stage 1 Architecture

## Stage 1 Executable Path

```text
Chat Input
    down
P3 Orchestrator
    down
P3 Analysis <- support_requests_sql Tool
    down
Chat Output
```

Stage 1 deliberately executes only Orchestrator and Analysis. Conditional
routing, Response, memory, and Gmail nodes remain disconnected placeholders
because final routing is out of scope. The final assignment has three Agents
with separate duties:

| Component | Name | Responsibility |
| --- | --- | --- |
| Orchestrator Agent | `P3 Orchestrator` | Classify intent and select route, Agents, Tools, and required context. Never generate SQL, return database results, or write final email content. |
| Analysis Agent | `P3 Analysis` | Resolve support-data questions and decide whether SQL is needed. Receives only relevant request context. |
| Response Agent | `P3 Response` | Produce user-facing complex responses or handoff drafts and invoke Gmail only after explicit approval. |
| SQL Tool | `support_requests_sql` | Read-only, restricted support-data access available only to P3 Analysis. |
| Gmail Tool | `Support Handoff Gmail` | Later sends an approved handoff draft. |
| Routing parser | `Route Parser` | Validate and expose structured Orchestrator output. |
| Session memory | `Conversation Memory` | Current-session messages only. |

## Later Routing Matrix

| Request type | Components |
| --- | --- |
| Greeting or simple answer | Orchestrator only |
| Missing information | Orchestrator only |
| Simple support status lookup | Orchestrator -> Analysis -> SQL -> Template |
| Complex analysis | Orchestrator -> Analysis -> SQL when needed -> Response |
| Prepare human handoff | Orchestrator -> Analysis when needed -> Response |
| Approve an existing draft | Orchestrator -> Response -> Gmail |

Stage 1 implements the SQL behavior and Analysis schema policy. Final routing,
Gmail authorization, and remaining production prompts belong to later stages.

## SQL Enforcement

The `support_reader` PostgreSQL role provides the database write boundary. The
guarded SQL Tool additionally parses every statement with pinned SQLGlot before
opening a connection. It accepts one explicit-column `SELECT` against only
`public.support_requests`, rejects subqueries/CTEs/set operations/functions
outside the aggregate allowlist, and requires `LIMIT 1..50` for record queries.
Only `query` is exposed to the Agent. Database URL and error-control settings
are not Tool arguments.

## Shared Context Boundary

`docs/context-contract.json` defines logical state, not a payload that every
component receives wholesale. Each Agent receives only fields necessary for its
responsibility. `Conversation Memory` must filter on the current `session_id`.
There is no cross-session user memory and no vector store.

The shared context and Agent inputs must never include:

- API keys, OAuth tokens, or database connection strings
- Raw SQL logs or raw Tool traces
- Prompts belonging to another Agent
- Unrelated database records
- Internal reasoning or chain of thought

Errors crossing component boundaries must be reduced to a safe summary in
`safe_error`.

## Storage And Secrets

Langflow uses its internal SQLite database persisted in the `langflow_data`
Docker volume. The separate `support_db` PostgreSQL service is reserved for
business data. The SQL Tool resolves the `SUPPORT_DB_URL` environment-variable
reference at runtime; its resolved value must not be stored in exported Flow
JSON.
