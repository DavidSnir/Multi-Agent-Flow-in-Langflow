# Gmail Setup Through Composio

## Current Status

Gmail connection implementation was intentionally deferred. No test account is currently connected, no OAuth consent has been granted, and no delivery smoke test has been performed. The following procedure is the handoff for completing that external setup later.

## Test Account Policy

Create a Gmail account dedicated to this assignment. Do not use a personal or production mailbox. Record only a non-secret account label in project records; do not commit its password, recovery information, OAuth tokens, or full mailbox screenshots.

Send only to controlled, allow-listed test recipients. Never invent a recipient or send when recipient, subject, or body is absent or unsafe.

## Connect Gmail

1. Create or select a Composio project.
2. Enable the Gmail toolkit.
3. Create a connected account and complete Google OAuth with the dedicated test mailbox.
4. Confirm the connected account is active in Composio.
5. Retrieve the project API key and store it only as `COMPOSIO_API_KEY` in the ignored `.env`.
6. Restart Langflow and confirm `COMPOSIO_API_KEY` appears under **Settings > Global Variables**.

The Composio API key authenticates Langflow to Composio. Google OAuth credentials and refresh tokens are managed by Composio and must not be copied into Langflow or this repository.

## Restrict Actions

When the Flow is implemented, use the single-service Composio Gmail component and expose only `GMAIL_SEND_EMAIL` (shown as **Send email**). Do not expose inbox reading, search, label modification, draft deletion, message deletion, or bulk operations.

The sending policy must reject:

- Missing or non-allow-listed recipients
- Missing subject or body
- Requests for arbitrary or mass mailing
- Provider errors that cannot be safely summarized

Provider errors should be converted to a controlled result such as:

```json
{
  "success": false,
  "error_type": "authentication_error",
  "message": "Email could not be sent."
}
```

Do not return raw authorization headers, tokens, or provider diagnostics to customer-facing output.

## Independent Smoke Test

Before Flow wiring, use Composio's dashboard or supported test interface to invoke only `GMAIL_SEND_EMAIL` with:

```text
To: <controlled test address>
Subject: Jeen Langflow Gmail Integration Test
Body: This is a test email generated during the Part 3 implementation.
```

Record only:

- UTC timestamp
- Recipient or approved redacted recipient label
- Success or failure status
- Returned Gmail message identifier, if available

Verify delivery in the controlled recipient mailbox, including the spam folder. Do not record API keys, access tokens, refresh tokens, authorization headers, or OAuth callback URLs containing codes.

## Reconnect Expired OAuth

If Composio reports an inactive account or Gmail calls return `401`, revoke the stale connected account in Composio and repeat the Gmail connection flow with the same dedicated test user. Common causes include password changes, revoked Google access, Workspace administrator policy, or refresh-token limits.

After reconnecting, repeat the independent smoke test before enabling the action in Langflow.

## Known Failures

| Failure | Response |
| --- | --- |
| Invalid `COMPOSIO_API_KEY` | Rotate the key in `.env`, restart Langflow, and recheck the Global Variable |
| OAuth account inactive | Reconnect the dedicated Gmail account in Composio |
| Google app blocked | Remove unnecessary scopes or use an approved custom Google OAuth app |
| Gmail API disabled | Enable Gmail API in the Google Cloud project used by custom OAuth credentials |
| Recipient not allow-listed | Reject without calling Gmail |
| Missing subject or body | Reject without calling Gmail |
| Rate or quota exceeded | Return a controlled temporary failure; do not retry unboundedly |

The custom Gmail API fallback is not implemented. It should be considered only if Composio cannot meet the assignment requirements.
