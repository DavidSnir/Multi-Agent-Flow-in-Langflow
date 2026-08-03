import json
from pathlib import Path


FLOW_PATH = Path("flows/jeen-part3-flow-skeleton-v01-2026-08-03.json")
PROJECT_PATH = Path("projects/jeen-part3-multi-agent-v01.json")

flow_text = FLOW_PATH.read_text(encoding="utf-8")
if flow_text != PROJECT_PATH.read_text(encoding="utf-8"):
    raise AssertionError("Flow and project exports differ")

flow = json.loads(flow_text)
nodes = flow["data"]["nodes"]
sql_nodes = [node for node in nodes if node["data"]["node"]["display_name"] == "support_requests_sql"]
if len(sql_nodes) != 1:
    raise AssertionError("Expected exactly one support_requests_sql node")

sql_node = sql_nodes[0]
definition = sql_node["data"]["node"]
if definition["tool_mode"] is not True:
    raise AssertionError("support_requests_sql is not in Tool Mode")
if len(definition["outputs"]) != 1 or definition["outputs"][0]["name"] != "component_as_tool":
    raise AssertionError("support_requests_sql does not expose component_as_tool")
if definition["outputs"][0]["types"] != ["Tool"]:
    raise AssertionError("support_requests_sql Tool output has the wrong type")

template = definition["template"]
tool_arguments = sorted(
    name
    for name, field in template.items()
    if isinstance(field, dict) and field.get("tool_mode") is True
)
if tool_arguments != ["query"]:
    raise AssertionError(f"Unexpected SQL Tool arguments: {tool_arguments}")
if "add_error" in template or "include_columns" in template:
    raise AssertionError("Unsafe generic SQL options remain in the guarded Tool")
if template["database_url"].get("trace_as_input") is not False:
    raise AssertionError("Database URL remains enabled as a trace input")
if template["database_url"].get("trace_as_metadata") is not False:
    raise AssertionError("Database URL remains enabled as trace metadata")
if template["database_url"]["value"] != "SUPPORT_DB_URL":
    raise AssertionError("Flow does not use the SUPPORT_DB_URL reference")

nodes_by_id = {node["id"]: node for node in nodes}
sql_edges = [edge for edge in flow["data"]["edges"] if edge["source"] == sql_node["id"]]
if len(sql_edges) != 1:
    raise AssertionError("SQL Tool must have exactly one outgoing edge")
edge = sql_edges[0]
target_name = nodes_by_id[edge["target"]]["data"]["node"]["display_name"]
if target_name != "P3 Analysis":
    raise AssertionError("SQL Tool is connected to an Agent other than P3 Analysis")
if edge["data"]["sourceHandle"]["output_types"] != ["Tool"]:
    raise AssertionError("SQL edge source is not a Tool")
if edge["data"]["targetHandle"]["fieldName"] != "tools":
    raise AssertionError("SQL Tool is not connected to the Analysis tools input")

for forbidden in ("postgresql://support_reader:", "SUPPORT_DB_READER_PASSWORD"):
    if forbidden in flow_text:
        raise AssertionError("Flow export contains a database secret or secret variable")

print("flow_tool_mode=passed")
print("flow_tool_arguments=query_only")
print("flow_sql_access=P3 Analysis only")
print("flow_secret_scan=passed")
