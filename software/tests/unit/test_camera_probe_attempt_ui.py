"""Actual browser status rendering and inert navigation; modeled state only."""

from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from test_arrival_wizard_service import make_service
from test_arrival_wizard_service import _run


def test_polling_does_not_copy_native_originals_or_observe_files(
    make_service, monkeypatch
):
    app, runner, source = make_service(mode="physical")
    app._physical_camera._original_probe_attempted = True
    app._physical_camera._original_probe_diagnostics = dict(
        status="FAILED_HELD", failed_phase="AUTHENTICATING_ORIGINALS"
    )
    monkeypatch.setattr(
        app._physical_camera,
        "retained_capture_diagnostics",
        lambda: pytest.fail("Status polling copied full native originals"),
    )
    before = source["calls"]
    for _ in range(5):
        value = app.view()["camera_probe_attempt"]
        assert value["status"] == "FAILED_HELD" and value["export_available"] is True
    assert before == source["calls"] and not runner.calls
    assert not app.export_directory.exists()


def test_general_export_contains_a_pointer_not_native_originals(
    make_service, monkeypatch
):
    app, _, _ = make_service(mode="physical")
    app._physical_camera._original_probe_attempted = True
    app._physical_camera._original_probe_diagnostics = dict(status="FAILED_HELD")
    # Deliberately over the general string limit: only the bounded pointer may
    # enter that export. The dedicated codec has independent buffer tests.
    monkeypatch.setattr(
        app._physical_camera,
        "retained_capture_diagnostics",
        lambda: {
            "original_probe": {"status": "FAILED_HELD"},
            "dispatch": {"raw_original": "NATIVE_ORIGINAL_NOT_IN_GENERAL_LOG" * 4000},
        },
    )
    result = _run(app, "export_logs")
    assert result["status"] == "SUCCEEDED", result
    root = Path(result["result"]["receipt"]["path"])
    data = json.loads((root / "attachment-native-camera-data.json").read_bytes())
    assert data["original_bytes_preserved"] is False
    assert data["complete_native_diagnostics_included"] is False
    assert data["separate_export_action"] == "physical_camera_probe_attempt_export"
    assert "NATIVE_ORIGINAL_NOT_IN_GENERAL_LOG" not in json.dumps(data)


def test_browser_card_rejects_changed_flags_context_and_raw_payloads(make_service):
    app, _, _ = make_service(mode="physical")
    view = app.view()
    value = view["camera_probe_attempt"]
    cases, expected = [deepcopy(value)], [True]
    queued = deepcopy(value)
    queued.update(
        queued=True, operation_id="operation-" + "1" * 32, export_available=True
    )
    cases.append(queued)
    expected.append(True)
    for key, change in (
        ("physical_authority", True),
        ("hardware_qualified", True),
        ("connected", True),
        ("source_sha256", "f" * 64),
        ("launch_session_id", "other-launch"),
        ("claimed", True),
        ("operation_id", "arbitrary-path"),
        ("outcome", "CONNECTED"),
        ("export_action", "physical_camera_probe"),
        ("raw_original", "NEVER_RENDER"),
        ("failed_phase", "ADMISSION_DERIVED"),
        ("export_available", True),
    ):
        changed = deepcopy(value)
        changed[key] = change
        cases.append(changed)
        expected.append(False)
    script = (
        Path(__file__).resolve().parents[2] / "src/rocell/ui/static/app.js"
    ).read_text(encoding="utf-8")
    section = script[
        script.index("  function cameraProbeAttemptValid(") : script.index(
            "  function physicalCameraSetup()"
        )
    ]
    harness = r"""
const fs=require('fs'), input=JSON.parse(fs.readFileSync(0,'utf8'));
function cameraConfigurationValidators(){return {exact:(x,k)=>x!==null&&typeof x==='object'&&!Array.isArray(x)&&Object.keys(x).length===k.length&&k.every(n=>Object.hasOwn(x,n)),digest:x=>typeof x==='string'&&/^[0-9a-f]{64}$/.test(x)}}
let state={view:input.view}, navigation=[];
function element(tag,cls,text){return {tag,text,children:[],events:{},append(...x){this.children.push(...x)},addEventListener(k,f){this.events[k]=f}}}
function card(t){return element('section','',t)}
function facts(v){return element('div','',JSON.stringify(v))}
function navigate(page){navigation.push(page)}
eval(input.script+`
const valid=input.cases.map(v=>cameraProbeAttemptValid(v,input.view));
state.view.camera_probe_attempt=input.cases[1];
const rendered=cameraProbeAttempt();
rendered.children.find(x=>x.tag==='button').events.click();
state.view.camera_probe_attempt=input.cases[input.cases.length-3];
const invalid=cameraProbeAttempt();
process.stdout.write(JSON.stringify({valid,navigation,invalid}));
`);
"""
    node = shutil.which("node")
    assert node is not None, "Node required for browser contract validation"
    result = subprocess.run(
        [node, "-e", harness],
        input=json.dumps(dict(script=section, cases=cases, view=view)),
        text=True,
        capture_output=True,
        timeout=10,
        check=True,
    )
    data = json.loads(result.stdout)
    assert data["valid"] == expected
    assert data["navigation"] == ["diagnostics"]
    assert "NEVER_RENDER" not in json.dumps(data["invalid"])
    assert "NOT_VERIFIED" in json.dumps(data["invalid"])


def test_operation_renderer_shows_retained_cause_without_running_an_action():
    """Use the entire shipped renderer, not an extracted function's old signature."""
    from test_wizard_activity_ui import render, result_reads, view

    message = (
        "CAMERA_ATTEMPT_NOT_KNOWN: Native supervision reported "
        "ADMISSION_DEADLINE_EXPIRED. Native effect accounting is unavailable; "
        "do not infer zero effects."
    )
    remediation = "Export the exact camera attempt; do not replay it."
    operation = dict(
        operation_id="operation-" + "1" * 32,
        action_id="physical_camera_probe",
        status="FAILED",
        message=message,
        error=dict(
            code="CAMERA_ATTEMPT_NOT_KNOWN", message=message, remediation=remediation
        ),
        result=dict(
            camera_attempt_failure=dict(
                reported_primary_error="ADMISSION_DEADLINE_EXPIRED",
                native_accounting_available=False,
                automatic_replay=False,
                physical_authority=False,
            )
        ),
    )
    summary = {key: value for key, value in operation.items() if key != "result"}
    initial = render(view([summary]))
    assert not result_reads(initial)
    assert message in initial["text"] and remediation in initial["text"]
    rendered = render(
        view([summary]),
        results={operation["operation_id"]: operation},
        steps=[dict(load=operation["operation_id"]), dict(page="activity")],
    )
    assert result_reads(rendered) == [f'/api/operations/{operation["operation_id"]}']
    for observation in rendered["observations"][1:]:
        assert message in observation["text"] and remediation in observation["text"]
        assert '"automatic_replay": false' in observation["text"]
