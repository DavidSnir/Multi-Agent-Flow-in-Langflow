# Stage 0 Architecture

## Intended Flow

```text
Chat Input
    down
P3 Orchestrator
    down
Structured Output Parser / JSON Operations (Route Parser)
    down
Conditional If-Else routing
    |-- Direct response or clarification
    |-- P3 Analysis -> Support Requests SQL -> Text Template
    |-- P3 Analysis -> Support Requests SQL -> P3 Response
    |-- P3 Response -> handoff draft
    `-- P3 Response -> Support Handoff Gmail after explicit approval
```

The routing is dynamic. A request activates only the Agents and Tools selected
by the Orchestrator output; the final Flow must not run all three Agents for
every message. The assignment has exactly three Agents with separate duties:

| Component | Name | Responsibility |
| --- | --- | --- |
| Orchestrator Agent | `P3 Orchestrator` | Classify intent and select route, Agents, Tools, and required context. Never generate SQL, return database results, or write final email content. |
| Analysis Agent | `P3 Analysis` | Resolve support-data questions and decide whether SQL is needed. Receives only relevant request context. |
| Response Agent | `P3 Response` | Produce user-facing complex responses or handoff drafts and invoke Gmail only after explicit approval. |
| SQL Tool | `Support Requests SQL` | Stage 1 placeholder for restricted support-data access. |
| Gmail Tool | `Support Handoff Gmail` | Later sends an approved handoff draft. |
| Routing parser | `Route Parser` | Validate and expose structured Orchestrator output. |
| Session memory | `Conversation Memory` | Current-session messages only. |

## Routing Matrix

| Request type | Components |
| --- | --- |
| Greeting or simple answer | Orchestrator only |
| Missing information | Orchestrator only |
| Simple support status lookup | Orchestrator -> Analysis -> SQL -> Template |
| Complex analysis | Orchestrator -> Analysis -> SQL when needed -> Response |
| Prepare human handoff | Orchestrator -> Analysis when needed -> Response |
| Approve an existing draft | Orchestrator -> Response -> Gmail |

Stage 0 provides branch placeholders only. Conditions, SQL behavior, Gmail
authorization, and production prompts belong to later stages.

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
business data beginning in Stage 1. Environment values can be imported into
Langflow Global Variables or Credentials, but their resolved values must not be
stored in exported Flow JSON.
