import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


WEB_ROOT = Path(__file__).resolve().parent
LANGFLOW_URL = os.environ.get("LANGFLOW_URL", "http://langflow:7860").rstrip("/")
MAX_BODY_SIZE = 1_000_000


class RelayHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_ROOT, **kwargs)

    def do_POST(self):
        if self.path not in {"/api/chat", "/api/resume"}:
            self.send_error(404)
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length <= 0 or content_length > MAX_BODY_SIZE:
                raise ValueError("Invalid request size")
            request_data = json.loads(self.rfile.read(content_length))
            api_key = str(request_data.get("apiKey", "")).strip()
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            self.send_json(400, {"error": str(error)})
            return

        if self.path == "/api/resume":
            self.resume_workflow(request_data, api_key)
            return

        flow_id = str(request_data.get("flowId", "")).strip()
        message = str(request_data.get("message", "")).strip()
        if not flow_id or not message:
            self.send_json(400, {"error": "Flow ID and message are required"})
            return

        payload = json.dumps({
            "flow_id": flow_id,
            "input_value": message,
            "mode": "background",
        }).encode()
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["x-api-key"] = api_key

        request = urllib.request.Request(
            f"{LANGFLOW_URL}/api/v2/workflows",
            data=payload,
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                langflow_data = json.loads(response.read())
            job_id = langflow_data.get("job_id")
            if not job_id:
                raise ValueError("Langflow did not return a workflow job ID")
            langflow_data = poll_workflow(job_id, headers)
            self.send_workflow_result(langflow_data, job_id, headers)
        except urllib.error.HTTPError as error:
            detail = read_error(error)
            self.send_json(error.code, {"error": f"Langflow: {detail}"})
        except urllib.error.URLError as error:
            self.send_json(502, {"error": f"Could not reach Langflow: {error.reason}"})
        except (TimeoutError, json.JSONDecodeError):
            self.send_json(502, {"error": "Langflow returned an invalid or timed-out response"})
        except ValueError as error:
            self.send_json(409, {"error": str(error)})

    def resume_workflow(self, request_data, api_key):
        job_id = str(request_data.get("jobId", "")).strip()
        request_id = str(request_data.get("requestId", "")).strip()
        decision = request_data.get("decision")
        if not job_id or not request_id or not isinstance(decision, dict):
            self.send_json(400, {"error": "Job ID, request ID, and decision are required"})
            return

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["x-api-key"] = api_key
        payload = json.dumps({"request_id": request_id, "decision": decision}).encode()
        request = urllib.request.Request(
            f"{LANGFLOW_URL}/api/v2/workflows/{urllib.parse.quote(job_id)}/resume",
            data=payload,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                resume_data = json.loads(response.read())
            resumed_job_id = str(resume_data.get("job_id") or job_id)
            result = poll_workflow(resumed_job_id, headers)
            self.send_workflow_result(result, resumed_job_id, headers)
        except urllib.error.HTTPError as error:
            self.send_json(error.code, {"error": f"Langflow: {read_error(error)}"})
        except urllib.error.URLError as error:
            self.send_json(502, {"error": f"Could not reach Langflow: {error.reason}"})
        except (TimeoutError, json.JSONDecodeError):
            self.send_json(502, {"error": "Langflow returned an invalid or timed-out response"})

    def send_workflow_result(self, data, job_id, headers):
        status = data.get("status")
        if status == "suspended":
            human_request = data.get("human_request") or {}
            if not find_request_id(human_request):
                human_request = get_pending_request(data.get("flow_id"), job_id, headers) or human_request
            request_id = find_request_id(human_request)
            if request_id:
                human_request["request_id"] = request_id
            self.send_json(200, {
                "status": "approval_required",
                "jobId": job_id,
                "request": human_request,
            })
            return
        if status != "completed":
            errors = data.get("errors") or []
            detail = errors[0].get("error") if errors else status or "unknown"
            self.send_json(409, {"error": f"Workflow did not complete: {detail}"})
            return
        message = extract_message(data)
        self.send_json(200, {
            "status": "completed",
            "message": extract_tagged_content(message),
            "fullMessage": message,
            "raw": data,
        })

    def send_json(self, status, data):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def find_request_id(value):
    if isinstance(value, list):
        for item in value:
            found = find_request_id(item)
            if found:
                return found
        return None
    if not isinstance(value, dict):
        return None
    for key in ("request_id", "requestId"):
        if value.get(key):
            return str(value[key])
    for nested in value.values():
        found = find_request_id(nested)
        if found:
            return found
    if value.get("id"):
        return str(value["id"])
    return None

def extract_message(data):
    output = data.get("output") or {}
    if output.get("text") is not None:
        return output["text"]
    try:
        output = data["outputs"][0]["outputs"][0]
        message = output.get("results", {}).get("message", {})
        return message.get("text") or message.get("message") or output.get("message", "")
    except (KeyError, IndexError, TypeError, AttributeError):
        return ""


def extract_tagged_content(message):
    if not isinstance(message, str):
        return message
    for tag in ("response", "analysis", "orchestrator"):
        match = re.search(
            rf"<{tag}>\s*(.*?)\s*</{tag}>",
            message,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if match:
            return match.group(1).strip()
    return message


def poll_workflow(job_id, headers):
    deadline = time.monotonic() + 115
    url = f"{LANGFLOW_URL}/api/v2/workflows?job_id={urllib.parse.quote(str(job_id))}"
    while time.monotonic() < deadline:
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.loads(response.read())
        if data.get("status") not in {"queued", "in_progress"}:
            return data
        time.sleep(1)
    raise TimeoutError


def get_pending_request(flow_id, job_id, headers):
    if not flow_id:
        return None
    url = f"{LANGFLOW_URL}/api/v2/workflows/pending?flow_id={urllib.parse.quote(str(flow_id))}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            pending = json.loads(response.read())
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError):
        return None
    for item in pending if isinstance(pending, list) else []:
        item_job_id = item.get("job_id") or item.get("jobId")
        if str(item_job_id) == str(job_id):
            return item.get("human_request") or item.get("request") or item
    return None


def read_error(error):
    try:
        body = json.loads(error.read())
        detail = body.get("detail") or body
        if isinstance(detail, dict):
            return detail.get("message") or detail.get("error") or json.dumps(detail)
        return detail or body.get("message") or json.dumps(body)
    except (json.JSONDecodeError, AttributeError):
        return error.reason


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    print(f"Relay listening on http://0.0.0.0:{port}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), RelayHandler).serve_forever()
