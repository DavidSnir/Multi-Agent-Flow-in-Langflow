import gzip
import json
import os
import time
import urllib.parse
import urllib.request
import uuid
from urllib.error import HTTPError


BASE_URL = os.environ.get("LANGFLOW_BASE_URL", "http://localhost:7860")
FLOW_NAME = "jeen-part3-multi-agent-v01"


def api(path, *, data=None, method=None):
    headers = {
        "Accept-Encoding": "gzip",
        "x-api-key": os.environ["LANGFLOW_API_KEY"],
    }
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(BASE_URL + path, body, headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            raw = response.read()
            if response.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
            return json.loads(raw) if raw else None
    except HTTPError as exc:
        exc.read()
        raise RuntimeError(f"Langflow API request failed with HTTP {exc.code}") from exc


def all_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for nested in value.values():
            yield from all_strings(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from all_strings(nested)


def scan_for_secrets(value):
    serialized = json.dumps(value, default=str)
    fingerprints = {
        "SUPPORT_DB_URL": os.environ.get("SUPPORT_DB_URL", ""),
        "LANGFLOW_API_KEY": os.environ.get("LANGFLOW_API_KEY", ""),
        "GOOGLE_API_KEY": os.environ.get("GOOGLE_API_KEY", ""),
        "LANGFLOW_SUPERUSER_PASSWORD": os.environ.get("LANGFLOW_SUPERUSER_PASSWORD", ""),
    }
    parsed_url = urllib.parse.urlparse(os.environ.get("SUPPORT_DB_URL", ""))
    if parsed_url.password:
        fingerprints["SUPPORT_DB_READER_PASSWORD"] = urllib.parse.unquote(parsed_url.password)
    exposed = [name for name, secret in fingerprints.items() if secret and secret in serialized]
    if exposed:
        raise AssertionError(f"Trace or response exposed secret fields: {', '.join(exposed)}")


def fetch_trace(flow_id, session_id):
    query = urllib.parse.urlencode(
        {"flow_id": flow_id, "session_id": session_id, "page": 1, "size": 20}
    )
    for _ in range(20):
        summaries = api(f"/api/v1/monitor/traces?{query}")
        traces = summaries.get("traces", [])
        if traces:
            return api(f"/api/v1/monitor/traces/{traces[0]['id']}")
        time.sleep(1)
    raise AssertionError(f"No Langflow Trace found for session {session_id}")


def span_names(spans):
    names = []
    for span in spans:
        names.append(span["name"])
        names.extend(span_names(span.get("children", [])))
    return names


def labeled_component_names(spans):
    names = []
    for span in spans:
        name = span["name"]
        system_prompt = (span.get("inputs") or {}).get("system_prompt", "")
        if "You are the Analysis Agent" in system_prompt:
            name = "P3 Analysis"
        elif name == "Agent":
            name = "P3 Orchestrator"
        names.append(name)
    return names


def tool_use_blocks(content_blocks):
    blocks = []
    for block in content_blocks:
        if block.get("type") == "tool_use":
            blocks.append(block)
        blocks.extend(tool_use_blocks(block.get("contents", [])))
    return blocks


flows = api("/api/v1/flows/?get_all=true")
matches = [flow for flow in flows if flow.get("name") == FLOW_NAME]
if len(matches) != 1:
    raise AssertionError(f"Expected exactly one live Flow named {FLOW_NAME}")
flow_id = matches[0]["id"]

mode = os.environ.get("STAGE1_E2E_MODE", "lookups")
if mode == "database_failure":
    scenarios = [
        (
            "database_failure",
            "Look up support request ID 1 for john@example.com and report its status.",
            ("temporarily unavailable",),
            ("postgresql", "psycopg", "support_reader"),
        )
    ]
else:
    scenarios = [
        (
            "valid",
            "Look up support request ID 1 for john@example.com and report its status.",
            ("john", "open"),
            (),
        ),
        (
            "empty",
            "Look up support request ID 1 for sarah@example.com. Do not broaden the search.",
            (),
            ("john smith", "john@example.com", "login issue"),
        ),
    ]

for label, prompt, required_text, forbidden_text in scenarios:
    session_id = f"stage1-{label}-{uuid.uuid4()}"
    response = api(
        f"/api/v1/run/{flow_id}",
        method="POST",
        data={
            "input_value": prompt,
            "input_type": "chat",
            "output_type": "chat",
            "session_id": session_id,
        },
    )
    trace = fetch_trace(flow_id, session_id)
    scan_for_secrets(response)
    scan_for_secrets(trace)

    combined_text = " ".join(all_strings(response)).lower()
    for expected in required_text:
        if expected not in combined_text:
            raise AssertionError(f"{label} response did not contain expected text: {expected}")
    for forbidden in forbidden_text:
        if forbidden in combined_text:
            raise AssertionError(f"{label} response exposed mismatched customer data")

    spans = trace.get("spans", [])
    names = span_names(spans)
    labeled_names = labeled_component_names(spans)
    analysis_spans = [
        span
        for span in spans
        if "You are the Analysis Agent" in (span.get("inputs") or {}).get("system_prompt", "")
    ]
    if len(analysis_spans) != 1:
        raise AssertionError(f"{label} Trace does not uniquely identify P3 Analysis")
    response_output = (analysis_spans[0].get("outputs") or {}).get("response", {})
    tool_blocks = tool_use_blocks(response_output.get("content_blocks", []))
    invoked_tools = [block.get("name") for block in tool_blocks]
    if "support_requests_sql" not in invoked_tools:
        raise AssertionError(f"{label} Trace does not show P3 Analysis invoking support_requests_sql")
    if "support requests sql" not in " ".join(names).lower():
        raise AssertionError(f"{label} Trace does not contain the SQL Tool component")

    support_block = next(block for block in tool_blocks if block.get("name") == "support_requests_sql")
    artifact = (support_block.get("output") or {}).get("artifact") or {}
    if label == "valid":
        if not artifact.get("succeeded") or not artifact.get("records_found"):
            raise AssertionError("Valid Trace does not contain a successful found-record Tool result")
    elif label == "empty":
        if not artifact.get("succeeded") or artifact.get("records_found") or artifact.get("records") != []:
            raise AssertionError("Empty Trace does not contain a safe zero-record Tool result")
    elif artifact.get("failure_category") != "database_query_failed":
        raise AssertionError("Failure Trace does not contain a normalized database failure")

    print(f"trace_{label}_id={trace['id']}")
    print(f"trace_{label}_status={trace['status']}")
    print(f"trace_{label}_components={','.join(labeled_names)}")
    print(f"trace_{label}_analysis_tools={','.join(invoked_tools)}")

print("langflow_trace_secret_scan=passed")
print("langflow_analysis_sql_tool_invocation=passed")
