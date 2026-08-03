import copy
import gzip
import json
import os
import urllib.parse
import urllib.request
import uuid
from pathlib import Path


BASE_URL = "http://localhost:7860"
FLOW_NAME = "jeen-part3-multi-agent-v01"
EXPORT_PATH = Path("flows/jeen-part3-flow-skeleton-v01-2026-08-03.json")
PROJECT_PATH = Path("projects/jeen-part3-multi-agent-v01.json")


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
    with urllib.request.urlopen(req, timeout=300) as response:
        raw = response.read()
        if response.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        return json.loads(raw) if raw else None


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


def edge(source, target, label=None):
    result = {
        "id": f"edge-{uuid.uuid4()}",
        "source": source["id"],
        "target": target["id"],
        "type": "default",
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
    router = node(catalog["flow_controls"]["ConditionalRouter"], "ConditionalRouter", "Conditional Routing", 900, 300)
    analysis = node(catalog["models_and_agents"]["Agent"], "Agent", "P3 Analysis", 1200, 100)
    response = node(catalog["models_and_agents"]["Agent"], "Agent", "P3 Response", 1500, 300)
    sql = node(catalog["flow_controls"]["Pass"], "Pass", "Support Requests SQL", 1500, 50)
    gmail = node(catalog["flow_controls"]["Pass"], "Pass", "Support Handoff Gmail", 1800, 450)
    memory = node(catalog["models_and_agents"]["Memory"], "Memory", "Conversation Memory", 300, 600)
    chat_output = node(catalog["input_output"]["ChatOutput"], "ChatOutput", "Chat Output", 2100, 300)

    nodes = [chat_input, orchestrator, parser, router, analysis, response, sql, gmail, memory, chat_output]
    edges = [
        edge(chat_input, orchestrator),
        edge(orchestrator, parser),
        edge(parser, router),
        edge(router, chat_output, "direct / clarification"),
        edge(router, analysis, "analysis"),
        edge(router, response, "response / handoff"),
        edge(analysis, sql, "SQL when needed"),
        edge(sql, response, "complex response"),
        edge(sql, chat_output, "template response"),
        edge(response, gmail, "explicit approval only"),
        edge(response, chat_output),
        edge(gmail, chat_output),
    ]
    payload = {
        "name": FLOW_NAME,
        "description": "Stage 0 dynamic-routing skeleton; SQL and Gmail are non-functional placeholders.",
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
