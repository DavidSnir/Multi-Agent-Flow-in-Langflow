import copy
import gzip
import json
import os
import urllib.parse
import urllib.request
from urllib.error import HTTPError
import uuid
from pathlib import Path


BASE_URL = os.environ.get("LANGFLOW_BASE_URL", "http://localhost:7860")
FLOW_NAME = "jeen-part3-multi-agent-v01"
EXPORT_PATH = Path("flows/jeen-part3-flow-skeleton-v01-2026-08-03.json")
PROJECT_PATH = Path("projects/jeen-part3-multi-agent-v01.json")
MODEL_NAME = "gemini-3.1-flash-lite"
MODEL_CONFIG = [{"name": MODEL_NAME, "icon": "GoogleGenerativeAI", "provider": "Google Generative AI"}]
ANALYSIS_PROMPT = """You are the Analysis Agent. Use the support_requests_sql tool only when support-request data is required.

When the request includes a support request ID and customer email, you MUST call support_requests_sql before answering. The tool is available to you; never claim that database access is unavailable unless the tool itself returns database_query_failed.

Available schema: support_requests(id integer primary key, customer_name varchar(100), email varchar(255), category varchar(100), priority varchar(50), status varchar(50), created_at timestamp). id is the support request identifier; customer_name is the customer's full name; email is the customer's email; category describes the issue; priority is the stored business priority; status is the current request status; created_at is the creation timestamp.

Database access is read-only. Each tool invocation must contain exactly one SELECT statement against support_requests only. Select only fields needed for the current request. Never use SELECT *, UNION, CTEs, system tables, database/system information functions, unnecessary subqueries, or any write/schema/permission statement. Non-aggregate record queries must include LIMIT 50 or less. Use WHERE for supplied identifiers, and require both id and email when verifying a customer's request. Never broaden a lookup or disclose partial/other-customer data when they do not match.

Return a normalized result with succeeded, records_found, failure_category, handoff_recommended, safe_explanation, and only the requested record fields. Empty results are not errors. On tool failure, do not return raw SQL/driver errors, stack traces, credentials, host details, connection details, or tool logs; return a general actionable safe_explanation and recommend handoff only when appropriate. Never expose database credentials or internal connection details."""
ORCHESTRATOR_SCHEMA = [
    {"name": "intent", "description": "Classified user intent", "type": "str", "multiple": False},
    {"name": "route", "description": "One of direct_response, analysis, human_handoff, or clarification", "type": "str", "multiple": False},
    {"name": "required_agents", "description": "Agents needed after orchestration", "type": "str", "multiple": True},
    {"name": "response_mode", "description": "One of orchestrator, template, or response_agent", "type": "str", "multiple": False},
    {"name": "response", "description": "Direct response when the orchestrator can answer", "type": "str", "multiple": False},
    {"name": "required_tools", "description": "Tools required for the selected route", "type": "str", "multiple": True},
    {"name": "required_context", "description": "Context required by downstream components", "type": "str", "multiple": True},
    {"name": "missing_information", "description": "Information that must be requested from the user", "type": "str", "multiple": True},
    {"name": "routing_reason", "description": "Short internal routing explanation", "type": "str", "multiple": False},
]


def request(path, *, token=None, data=None, form=False, method=None):
    headers = {"Accept-Encoding": "gzip"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if data is not None:
        if form:
            body = urllib.parse.urlencode(data).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            body = json.dumps(data).encode()
            headers["Content-Type"] = "application/json"
    else:
        body = None
    req = urllib.request.Request(BASE_URL + path, body, headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=300) as response:
            raw = response.read()
            if response.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
            return json.loads(raw) if raw else None
    except HTTPError as exc:
        exc.read()
        raise RuntimeError(f"Langflow API request failed with HTTP {exc.code}") from exc


def node(component, component_type, name, x, y):
    node_id = f"{component_type}-{uuid.uuid4()}"
    definition = copy.deepcopy(component)
    definition["display_name"] = name
    definition["description"] = definition.get("description", "")
    return {
        "id": node_id,
        "type": "genericNode",
        "position": {"x": x, "y": y},
        "data": {
            "type": component_type,
            "node": definition,
            "id": node_id,
        },
    }


def set_value(component, field, value):
    component["data"]["node"]["template"][field]["value"] = value


def catalog_component(catalog, component_name, *, category_name=None):
    categories = (
        [catalog[category_name]]
        if category_name is not None
        else catalog.values()
    )
    for category in categories:
        if not isinstance(category, dict):
            continue
        if component_name in category:
            return component_name, category[component_name]
        for key, definition in category.items():
            if isinstance(definition, dict) and definition.get("name") == component_name:
                return key, definition
    raise KeyError(f"Langflow catalog does not contain {component_name}")


def enable_component_as_tool(component, token, *, tool_name, tool_description):
    definition = component["data"]["node"]
    updated = request(
        "/api/v1/custom_component/update",
        token=token,
        data={
            "code": definition["template"]["code"]["value"],
            "template": definition["template"],
            "field": "tool_mode",
            "field_value": True,
            "tool_mode": True,
        },
        method="POST",
    )
    updated["display_name"] = definition["display_name"]
    component["data"]["node"] = updated

    actions = updated["template"]["tools_metadata"]["value"]
    if len(actions) != 1:
        raise ValueError("Expected exactly one support SQL tool action")
    actions[0]["name"] = tool_name
    actions[0]["description"] = tool_description

    output = updated["outputs"]
    if not updated["tool_mode"] or len(output) != 1 or output[0]["name"] != "component_as_tool":
        raise ValueError("Langflow did not enable the support SQL component as a Tool")
    if output[0]["types"] != ["Tool"]:
        raise ValueError("Support SQL Tool output has an unexpected type")


def handle(value):
    return json.dumps(value, separators=(",", ":")).replace('"', "œ")


def edge(source, source_output, target, target_input, label=None):
    output = next(item for item in source["data"]["node"]["outputs"] if item["name"] == source_output)
    input_field = target["data"]["node"]["template"][target_input]
    source_handle = {
        "dataType": source["data"]["type"],
        "id": source["id"],
        "name": source_output,
        "output_types": output["types"],
    }
    target_handle = {
        "fieldName": target_input,
        "id": target["id"],
        "inputTypes": input_field["input_types"],
        "type": input_field["type"],
    }
    source_handle_text = handle(source_handle)
    target_handle_text = handle(target_handle)
    result = {
        "animated": False,
        "className": "",
        "data": {"sourceHandle": source_handle, "targetHandle": target_handle},
        "id": f"reactflow__edge-{source['id']}{source_handle_text}-{target['id']}{target_handle_text}",
        "selected": False,
        "source": source["id"],
        "sourceHandle": source_handle_text,
        "target": target["id"],
        "targetHandle": target_handle_text,
    }
    if label:
        result["label"] = label
    return result


def main():
    token = request(
        "/api/v1/login",
        data={
            "username": os.environ.get("LANGFLOW_SUPERUSER", "admin"),
            "password": os.environ["LANGFLOW_SUPERUSER_PASSWORD"],
        },
        form=True,
        method="POST",
    )["access_token"]
    catalog = request("/api/v1/all", token=token)

    chat_input = node(catalog["input_output"]["ChatInput"], "ChatInput", "Chat Input", 0, 300)
    orchestrator = node(catalog["models_and_agents"]["Agent"], "Agent", "P3 Orchestrator", 300, 300)
    parser = node(catalog["processing"]["OutputParser"], "OutputParser", "Route Parser", 600, 300)
    direct_router = node(catalog["flow_controls"]["ConditionalRouter"], "ConditionalRouter", "Direct or Clarification?", 900, 300)
    analysis_router = node(catalog["flow_controls"]["ConditionalRouter"], "ConditionalRouter", "Analysis Required?", 1200, 400)
    analysis = node(catalog["models_and_agents"]["Agent"], "Agent", "P3 Analysis", 1500, 100)
    response = node(catalog["models_and_agents"]["Agent"], "Agent", "P3 Response", 1800, 400)
    _, sql_definition = catalog_component(catalog, "SQLComponent", category_name="support_tools")
    sql = node(
        sql_definition,
        "SQLComponent",
        "support_requests_sql",
        1800,
        50,
    )
    gmail = node(catalog["flow_controls"]["Pass"], "Pass", "Support Handoff Gmail", 2100, 550)
    memory = node(catalog["models_and_agents"]["Memory"], "Memory", "Conversation Memory", 300, 600)
    chat_output = node(catalog["input_output"]["ChatOutput"], "ChatOutput", "Chat Output", 2400, 300)

    for agent, temperature in ((orchestrator, 0), (analysis, 0), (response, 0.2)):
        set_value(agent, "model", copy.deepcopy(MODEL_CONFIG))
        if "temperature" in agent["data"]["node"]["template"]:
            set_value(agent, "temperature", temperature)
        if "add_current_date_tool" in agent["data"]["node"]["template"]:
            set_value(agent, "add_current_date_tool", False)
        if "add_calculator_tool" in agent["data"]["node"]["template"]:
            set_value(agent, "add_calculator_tool", False)
    set_value(orchestrator, "output_schema", ORCHESTRATOR_SCHEMA)
    set_value(orchestrator, "system_prompt", "Classify the request and return only the configured structured routing fields. Use direct_response or clarification when no downstream agent is needed; otherwise use analysis or human_handoff.")
    set_value(analysis, "system_prompt", ANALYSIS_PROMPT)
    set_value(sql, "database_url", "SUPPORT_DB_URL")
    sql["data"]["node"]["template"]["database_url"]["load_from_db"] = True
    sql["data"]["node"]["template"]["database_url"]["trace_as_input"] = False
    sql["data"]["node"]["template"]["database_url"]["trace_as_metadata"] = False
    enable_component_as_tool(
        sql,
        token,
        tool_name="support_requests_sql",
        tool_description="Run one approved read-only query against the support_requests table.",
    )
    set_value(direct_router, "operator", "regex")
    set_value(direct_router, "match_text", r'"route"\s*:\s*"(direct_response|clarification)"')
    set_value(analysis_router, "operator", "regex")
    set_value(analysis_router, "match_text", r'"route"\s*:\s*"analysis"')

    # Tool providers are top-level dependencies of the Analysis Agent.
    nodes = [sql, chat_input, orchestrator, parser, direct_router, analysis_router, analysis, response, gmail, memory, chat_output]
    edges = [
        edge(chat_input, "message", orchestrator, "input_value"),
        edge(parser, "format_instructions", orchestrator, "format_instructions"),
        edge(orchestrator, "response", analysis, "input_value", "Stage 1 analysis"),
        edge(sql, "component_as_tool", analysis, "tools", "Analysis tool only"),
        edge(analysis, "response", chat_output, "input_value", "Stage 1 response"),
    ]
    payload = {
        "name": FLOW_NAME,
        "description": "Stage 1 flow with read-only support_requests SQL access for P3 Analysis only.",
        "data": {"nodes": nodes, "edges": edges, "viewport": {"x": 0, "y": 0, "zoom": 0.7}},
        "is_component": False,
    }

    existing = request("/api/v1/flows/?get_all=true", token=token)
    for flow in existing:
        if flow.get("name") == FLOW_NAME:
            request(f"/api/v1/flows/{flow['id']}", token=token, method="DELETE")

    created = request("/api/v1/flows/", token=token, data=payload, method="POST")
    export = {
        "name": created["name"],
        "description": created.get("description"),
        "data": created["data"],
        "is_component": created.get("is_component", False),
    }
    content = json.dumps(export, indent=2) + "\n"
    EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROJECT_PATH.parent.mkdir(parents=True, exist_ok=True)
    EXPORT_PATH.write_text(content, encoding="utf-8")
    PROJECT_PATH.write_text(content, encoding="utf-8")
    print(f"Created flow {created['id']}")
    print(f"Exported {EXPORT_PATH}")
    print(f"Exported {PROJECT_PATH}")


if __name__ == "__main__":
    main()
