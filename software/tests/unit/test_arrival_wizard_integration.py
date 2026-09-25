"""Real service/HTTP/log/export integration with incapable injected workers.

No subprocess, host inventory, camera source or serial endpoint is used. The
source fingerprint is fixed to isolate these tests from concurrent developer
edits; board geometry still comes through the actual source-bound loader.
"""

from __future__ import annotations

from copy import deepcopy
import http.client
import io
import json
from pathlib import Path
import shutil
import subprocess
import threading
import time
from typing import Any

from PIL import Image
import pytest

import rocell.application.arrival_wizard_service as service_module
from rocell.application.arrival_wizard_service import ArrivalWizardService
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.ui.server import WizardHTTPServer, create_wizard_server


WORKSPACE = Path(__file__).resolve().parents[3]


class PureRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.result_changes: dict[str, Any] = {}

    def run(
        self,
        action_id: str,
        values: dict[str, Any],
        *,
        cell_id: str,
        cancel: threading.Event,
        progress: Any,
    ) -> dict[str, Any]:
        self.calls.append((action_id, deepcopy(values)))
        progress("Pure integration fixture; no hardware used.")
        return {
            "schema": "rocell.wizard_worker_result.v1",
            "action_id": action_id,
            "status": "SUCCEEDED",
            "steps": [
                {
                    "name": "pure-fixture",
                    "exit_code": 0,
                    "report": {
                        "status": "COMPLETE_SYNTHETIC",
                        "nested": {"test_detail": "retained-only-in-full-result"},
                    },
                }
            ],
            "device_open_count": 0,
            "serial_write_count": 0,
            "power_event_count": 0,
            "motion_command_count": 0,
            "contact_command_count": 0,
            "metadata_inventory_performed": False,
            "physical_authority": False,
            **self.result_changes,
        }


@pytest.fixture
def make_workbench(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    from rocell.application import physical_device_inventory as inventory
    from rocell.arm.serial_transport import SerialTransport
    from rocell.vision.usb_opencv import UsbOpenCvCamera

    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("HTTP integration attempted device access")

    monkeypatch.setattr(SerialTransport, "connect", forbidden)
    monkeypatch.setattr(UsbOpenCvCamera, "open", forbidden)
    for name in (
        "inventory_windows_pnp_cameras",
        "inventory_linux_video_cameras_from_sysfs",
        "inventory_serial_ports_with_pyserial",
    ):
        monkeypatch.setattr(inventory, name, forbidden)
    fingerprint_calls: list[Path] = []

    def fingerprint(workspace: Path) -> str:
        fingerprint_calls.append(workspace)
        return "d" * 64

    monkeypatch.setattr(service_module, "source_fingerprint", fingerprint)
    servers: list[tuple[WizardHTTPServer, threading.Thread]] = []

    def create(
        mode: str = "rehearsal",
    ) -> tuple[
        WizardHTTPServer, ArrivalWizardService, PureRunner, Path, Path, list[Path]
    ]:
        root = tmp_path / f"workbench-{len(servers)}"
        # The assigned directories require an existing approved parent. This
        # fixture setup is not an application startup write.
        root.mkdir()
        log_directory, export_directory = root / "logs", root / "exports"
        runner = PureRunner()
        service = ArrivalWizardService(
            WORKSPACE,
            mode=mode,
            runner=runner,
            log_directory=log_directory,
            export_directory=export_directory,
        )
        server = create_wizard_server(service)
        servers.append((server, server.start_in_thread()))
        return (
            server,
            service,
            runner,
            log_directory,
            export_directory,
            fingerprint_calls,
        )

    yield create
    for server, thread in servers:
        server.close()
        thread.join(timeout=3)


def request(
    server: WizardHTTPServer,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    authenticated: bool = True,
) -> tuple[int, Any]:
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    headers = {"Host": server.expected_host}
    if authenticated:
        headers["X-RoCell-Token"] = server.session_token
    payload = None
    if body is not None:
        headers.update(
            {
                "Origin": server.origin,
                "X-RoCell-CSRF": server.csrf_token,
                "Content-Type": "application/json",
            }
        )
        payload = json.dumps(body)
    try:
        connection.request(
            "POST" if body is not None else "GET", path, body=payload, headers=headers
        )
        response = connection.getresponse()
        value = response.read()
        if response.getheader("Content-Type", "").startswith("application/json"):
            return response.status, json.loads(value)
        return response.status, value
    finally:
        connection.close()


def view(server: WizardHTTPServer) -> dict[str, Any]:
    status, snapshot = request(server, "/api/view")
    assert status == 200
    return snapshot


def prepare(
    server: WizardHTTPServer, action_id: str, values: dict[str, Any] | None = None
) -> dict[str, Any]:
    status, ticket = request(
        server,
        "/api/prepare",
        body={
            "action_id": action_id,
            "input": values or {},
            "expected_revision": view(server)["revision"],
        },
    )
    assert status == 200, ticket
    return ticket


def execute(server: WizardHTTPServer, ticket: dict[str, Any]) -> dict[str, Any]:
    status, operation = request(
        server, "/api/execute", body={"ticket_id": ticket["ticket_id"]}
    )
    assert status == 200, operation
    return operation


def complete(server: WizardHTTPServer, operation: dict[str, Any]) -> dict[str, Any]:
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        status, result = request(server, "/api/operations/" + operation["operation_id"])
        assert status == 200
        if result["status"] in {"SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT"}:
            return result
        threading.Event().wait(0.005)
    pytest.fail("pure worker did not complete inside test deadline")


def test_startup_static_pages_status_and_missing_image_are_write_free(
    make_workbench: Any,
) -> None:
    server, service, runner, logs, exports, hashes = make_workbench()
    initial_hash_reads = len(hashes)
    for _ in range(4):
        snapshot = view(server)
        assert snapshot["authority"] == "NO_PHYSICAL_AUTHORITY"
        assert snapshot["camera"]["image_id"] is None
        assert snapshot["diagnostics"]["log_state"] == "NOT_STARTED"
    assert request(server, "/", authenticated=False)[0] == 200
    assert request(server, "/assets/app.js", authenticated=False)[0] == 200
    status, error = request(server, "/api/images/image-missing")
    assert status == 409
    assert error["error"]["code"] == "UNKNOWN_IMAGE"
    assert len(hashes) == initial_hash_reads
    assert runner.calls == []
    assert not logs.exists()
    assert not exports.exists()
    server.close()
    assert not logs.exists()
    assert not exports.exists()


@pytest.mark.parametrize("scenario", ["nominal", "missing-helper", "hash-drift"])
def test_helper_inspection_review_and_export_over_actual_http(
    make_workbench: Any, monkeypatch: pytest.MonkeyPatch, scenario: str
) -> None:
    from rocell.providers.windows.camera_worker_client import WindowsCameraWorkerClient

    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("HTTP helper rehearsal must never invoke native code")

    monkeypatch.setattr(WindowsCameraWorkerClient, "_registered_arguments", forbidden)
    server, service, runner, logs, exports, _ = make_workbench()
    pending = prepare(
        server,
        "camera_helper_inspect",
        {
            "operator_id": "http-inspection-operator",
            "scenario": scenario,
            "metadata_only": True,
        },
    )
    assert not logs.exists()
    assert view(server)["camera_helper_registration"]["inspection"] is None
    inspected = complete(server, execute(server, pending))
    assert inspected["status"] == "SUCCEEDED", inspected
    assert inspected["result"]["steps"][0]["report"]["inspection_report"]
    reviewed = complete(
        server,
        execute(
            server,
            prepare(
                server,
                "camera_helper_review",
                {
                    "reviewer_id": "http-helper-reviewer",
                    "metadata_only": True,
                },
            ),
        ),
    )
    assert reviewed["status"] == "SUCCEEDED", reviewed
    snapshot = view(server)
    assert snapshot["camera_helper_registration"]["status"] == (
        "METADATA_HELPER_REGISTERED" if scenario == "nominal" else "REVIEW_HELD"
    )
    assert all(row["state"] == "PHYSICAL_PENDING" for row in snapshot["stages"])
    assert snapshot["camera"]["status"] == "NOT_CONNECTED"
    assert runner.calls == []
    exported = complete(server, execute(server, prepare(server, "export_logs")))
    assert exported["status"] == "SUCCEEDED", exported
    target = Path(exported["result"]["receipt"]["path"])
    assert target.parent == exports
    assert verify_export(target)["valid"]


def test_preparation_is_write_free_execution_produces_one_retrievable_result(
    make_workbench: Any,
) -> None:
    server, service, runner, logs, exports, _ = make_workbench()
    ticket = prepare(server, "camera_rehearsal", {"fault": "none"})
    assert ticket["physical_authority"] is False
    assert runner.calls == []
    assert not logs.exists()
    operation = execute(server, ticket)
    full = complete(server, operation)
    assert full["status"] == "SUCCEEDED"
    assert (
        full["result"]["steps"][0]["report"]["nested"]["test_detail"]
        == "retained-only-in-full-result"
    )
    assert logs.is_dir()
    assert not exports.exists()
    summary = view(server)["operations"][-1]
    assert "result" not in summary
    assert summary["result_retention"] == "FULL_JSON_RETAINED"
    assert summary["steps"][0]["report_status"] == "COMPLETE_SYNTHETIC"
    assert runner.calls == [("camera_rehearsal", {"fault": "none"})]
    assert execute(server, ticket)["operation_id"] == operation["operation_id"]
    assert len(runner.calls) == 1
    assert view(server)["camera"]["physical_capture_available"] is False


def test_nominal_image_and_geometry_are_served_without_camera_claims(
    make_workbench: Any,
) -> None:
    server, service, runner, _, _, _ = make_workbench()
    before = view(server)
    result = complete(server, execute(server, prepare(server, "board_preview")))
    assert result["status"] == "SUCCEEDED"
    after = view(server)
    assert after["camera"]["image_provenance"] == "NOMINAL_SCHEMATIC_NOT_CAMERA_CAPTURE"
    assert after["board"]["coordinate_state"] == "NOMINAL_UNMEASURED"
    assert after["board"]["installed_calibration"] == "NOT_VERIFIED"
    geometry = after["board"]["geometry"]
    assert geometry["width_mm"] > 0
    assert geometry["height_mm"] > 0
    assert {item["name"] for item in geometry["devices"]} == {"keyboard", "phone"}
    assert geometry["source_hashes"]
    status, pixels = request(server, "/api/images/" + after["camera"]["image_id"])
    assert status == 200
    with Image.open(io.BytesIO(pixels)) as image:
        assert image.format == "PNG"
        assert image.size == (1000, 820)
    assert after["stages"] == before["stages"]
    assert all(stage["state"] == "PHYSICAL_PENDING" for stage in after["stages"])
    assert len(runner.calls) == 1


def test_note_and_verified_export_preserve_diagnostic_results_under_assigned_folder(
    make_workbench: Any,
) -> None:
    server, service, runner, logs, exports, _ = make_workbench()
    stages = view(server)["stages"]
    complete(
        server,
        execute(
            server, prepare(server, "plan_task", {"device": "phone", "text": "hi"})
        ),
    )
    note = complete(
        server,
        execute(
            server,
            prepare(
                server,
                "record_note",
                {"note": "USB cable checklist reviewed; physical test still pending."},
            ),
        ),
    )
    assert note["status"] == "SUCCEEDED"
    assert len(runner.calls) == 1
    assert any(event["kind"] == "OPERATOR_NOTE" for event in view(server)["events"])
    exported = complete(server, execute(server, prepare(server, "export_logs")))
    assert exported["status"] == "SUCCEEDED", exported
    receipt = exported["result"]["receipt"]
    target = Path(receipt["path"])
    assert target.is_dir()
    assert target.parent == exports
    assert verify_export(target)["valid"] is True
    assert view(server)["exports"]["items"][-1]["path"] == str(target)
    assert view(server)["stages"] == stages
    assert logs.is_dir()
    assert exported["result"]["physical_authority"] is False
    repeated = complete(server, execute(server, prepare(server, "export_logs")))
    assert repeated["result"]["receipt"]["path"] != str(target)
    assert target.is_dir()


@pytest.mark.parametrize("mode", ["rehearsal", "physical"])
@pytest.mark.parametrize("action_id", ["camera_connect", "arm_connect", "execute_task"])
def test_physical_actions_are_held_end_to_end(
    mode: str, action_id: str, make_workbench: Any
) -> None:
    server, service, runner, logs, exports, _ = make_workbench(mode)
    snapshot = view(server)
    selected = next(
        action for action in snapshot["actions"] if action["action_id"] == action_id
    )
    assert selected["enabled"] is False
    status, result = request(
        server,
        "/api/prepare",
        body={
            "action_id": action_id,
            "input": {},
            "expected_revision": snapshot["revision"],
        },
    )
    assert status == 409
    assert result["error"]["code"] == "ACTION_BLOCKED"
    assert result["error"]["message"]
    assert runner.calls == []
    assert not logs.exists()
    assert not exports.exists()


def test_physical_metadata_confirmation_failure_never_calls_runner(
    make_workbench: Any,
) -> None:
    server, service, runner, logs, _, _ = make_workbench("physical")
    status, error = request(
        server,
        "/api/prepare",
        body={
            "action_id": "inventory_devices",
            "input": {"power_disconnected": False},
            "expected_revision": view(server)["revision"],
        },
    )
    assert status == 409
    assert error["error"]["code"] == "CONFIRMATION_REQUIRED"
    assert not logs.exists()
    assert runner.calls == []


def test_export_destination_cannot_be_reassigned_from_http(make_workbench: Any) -> None:
    server, service, runner, logs, exports, _ = make_workbench()
    status, error = request(
        server,
        "/api/prepare",
        body={
            "action_id": "export_logs",
            "input": {"directory": "C:/outside"},
            "expected_revision": view(server)["revision"],
        },
    )
    assert status == 409
    assert error["error"]["code"] == "UNKNOWN_INPUT_FIELD"
    assert runner.calls == []
    assert not logs.exists()
    assert not exports.exists()


def test_stale_revision_reason_reaches_http_client(make_workbench: Any) -> None:
    server, service, runner, _, _, _ = make_workbench()
    original = view(server)["revision"]
    complete(
        server,
        execute(
            server,
            prepare(
                server, "record_note", {"note": "Recorded diagnostic observation."}
            ),
        ),
    )
    status, error = request(
        server,
        "/api/prepare",
        body={
            "action_id": "camera_profile",
            "input": {},
            "expected_revision": original,
        },
    )
    assert status == 409
    assert error["error"]["code"] == "STALE_REVISION"
    assert "refresh" in error["error"]["message"]
    assert runner.calls == []


def test_worker_failure_is_visible_and_note_does_not_erase_failure(
    make_workbench: Any,
) -> None:
    server, service, runner, _, _, _ = make_workbench()
    runner.result_changes = {
        "status": "FAILED",
        "steps": [
            {
                "name": "pure-fixture",
                "exit_code": 1,
                "report": {
                    "status": "EXPECTED_FAILURE",
                    "code": "SYNTHETIC_TEST_FAILURE",
                    "message": "Synthetic test failed; inspect retained fixture details.",
                },
            }
        ],
    }
    result = complete(
        server, execute(server, prepare(server, "arm_rehearsal", {"fault": "none"}))
    )
    assert result["status"] == "FAILED"
    assert result["error"]["code"] == "DIAGNOSTIC_FAILED"
    assert result["result"]["steps"][0]["report"]["code"] == "SYNTHETIC_TEST_FAILURE"
    assert result["error"]["remediation"]
    failed_id = result["operation_id"]
    complete(
        server,
        execute(
            server,
            prepare(
                server,
                "record_note",
                {"note": "Investigation logged, test not yet rerun."},
            ),
        ),
    )
    status, retained = request(server, "/api/operations/" + failed_id)
    assert status == 200
    assert retained["status"] == "FAILED"
    assert retained["result"]["steps"][0]["report"]["code"] == "SYNTHETIC_TEST_FAILURE"
    assert len(runner.calls) == 1
    assert view(server)["physical_authority"] is False


def test_worker_authority_claim_is_rejected_without_promoting_stages(
    make_workbench: Any,
) -> None:
    server, service, runner, _, _, _ = make_workbench()
    runner.result_changes = {"physical_authority": True}
    original = view(server)["stages"]
    operation = complete(
        server, execute(server, prepare(server, "camera_rehearsal", {"fault": "none"}))
    )
    assert operation["status"] == "FAILED"
    assert operation["error"]["code"] == "INVALID_WORKER_RESULT"
    assert view(server)["stages"] == original
    assert view(server)["physical_authority"] is False


def test_assets_support_real_service_result_and_source_shapes(
    make_workbench: Any,
) -> None:
    server, service, runner, _, _, _ = make_workbench()
    status, script = request(server, "/assets/app.js", authenticated=False)
    assert status == 200
    for required in (
        b"/api/operations/",
        b"Load latest full result",
        b"image_provenance",
        b"source_binding_sha256",
        b"event.kind",
        b"event.details",
    ):
        assert required in script
    assert runner.calls == []


_DOM_HARNESS = r"""
const fs = require('fs');
const vm = require('vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const nodes = [], ids = new Map(), requests = [];
let periodic;
class Element {
  constructor(tag) {
    this.tagName = tag.toUpperCase(); this.children = []; this.textContent = '';
    this.listeners = {}; this.hidden = false; this.value = ''; this.className = '';
    this.classList = {add() {}, toggle() {}}; nodes.push(this);
  }
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this.children = items; }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  setAttribute(name, value) { this[name] = value; }
  removeAttribute(name) { delete this[name]; }
  focus() {}
  showModal() { this.open = true; }
  close() { this.open = false; }
  reportValidity() { return true; }
}
function find(id) { if (!ids.has(id)) ids.set(id, new Element('div')); return ids.get(id); }
global.document = {
  querySelector: find, querySelectorAll: () => [],
  createElement: tag => new Element(tag),
  createElementNS: (namespace, tag) => new Element(tag),
  createTextNode: text => { const value = new Element('text'); value.textContent = text; return value; },
  createDocumentFragment: () => new Element('fragment'),
  activeElement: null, hidden: false,
};
find('#error-banner').hidden = true;
global.location = {hash: '#session=fixture&csrf=fixture', pathname: '/'};
global.history = {replaceState() {}};
global.sessionStorage = {setItem() {}, getItem() {return null;}};
global.setInterval = callback => { periodic = callback; return 1; };
global.fetch = async (path, options) => {
  requests.push({path, method: options.method || 'GET'});
  if (path === '/api/view') return {ok: true, json: async () => input.snapshot};
  if (path.startsWith('/api/operations/')) return {ok: true, json: async () => input.operation};
  throw new Error('Unexpected test fetch ' + path);
};
(async () => {
  vm.runInThisContext(input.script, {filename: 'app.js'});
  await new Promise(resolve => setTimeout(resolve, 20));
  if (input.loadFull) {
    const button = nodes.find(node => node.textContent === 'Load latest full result');
    if (!button) throw new Error('Full result button was not rendered');
    await button.listeners.click();
  }
  const beforeTick = requests.length;
  if (input.tick && periodic) {
    periodic(); await new Promise(resolve => setTimeout(resolve, 20));
  }
  process.stdout.write(JSON.stringify({
    status: find('#connection-status').textContent,
    error: find('#error-banner').textContent,
    errorHidden: find('#error-banner').hidden,
    requests, beforeTick, afterTick: requests.length,
    resultRendered: nodes.some(node => String(node.textContent).includes('retained-only-in-full-result')),
  }));
})().catch(error => { process.stderr.write(error.stack); process.exitCode = 1; });
"""


def run_javascript(
    snapshot: dict[str, Any],
    *,
    operation: dict[str, Any] | None = None,
    load_full: bool = False,
    tick: bool = False,
) -> dict[str, Any]:
    node = shutil.which("node")
    if node is None:
        pytest.skip(
            "Optional Node runtime is unavailable for DOM adapter regression tests"
        )
    script = (WORKSPACE / "software/src/rocell/ui/static/app.js").read_text(
        encoding="utf-8"
    )
    # This is a pure DOM test: fetch is replaced above; neither the script nor
    # the test Node process can contact an actual browser/service/device.
    outcome = subprocess.run(
        [node, "-e", _DOM_HARNESS],
        input=json.dumps(
            {
                "script": script,
                "snapshot": snapshot,
                "operation": operation,
                "loadFull": load_full,
                "tick": tick,
            }
        ),
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=5,
        check=False,
    )
    assert outcome.returncode == 0, outcome.stderr
    return json.loads(outcome.stdout)


def test_javascript_renders_actual_null_error_and_loads_full_result_read_only(
    make_workbench: Any,
) -> None:
    server, service, runner, _, _, _ = make_workbench()
    result = complete(server, execute(server, prepare(server, "run_baseline")))
    assert result["error"] is None
    snapshot = view(server)
    assert snapshot["operations"][-1]["error"] is None
    rendered = run_javascript(snapshot, operation=result, load_full=True)
    assert rendered["status"] == "Local service connected"
    assert rendered["errorHidden"] is True
    assert rendered["resultRendered"] is True
    assert rendered["requests"] == [
        {"path": "/api/view", "method": "GET"},
        {"path": "/api/operations/" + result["operation_id"], "method": "GET"},
    ]


def test_javascript_render_failure_is_not_transport_failure_or_automatic_retry(
    make_workbench: Any,
) -> None:
    server, service, runner, _, _, _ = make_workbench()
    snapshot = view(server)
    # Model unexpected service/schema drift without touching operational data.
    snapshot["stages"] = [None]
    rendered = run_javascript(snapshot, tick=True)
    assert rendered["status"].startswith("Interface error")
    assert "backend action may still be running" in rendered["error"]
    assert "Check diagnostics before retrying" in rendered["error"]
    assert "Service unavailable" not in rendered["status"]
    assert rendered["errorHidden"] is False
    assert rendered["afterTick"] == rendered["beforeTick"] == 1
    assert runner.calls == []
