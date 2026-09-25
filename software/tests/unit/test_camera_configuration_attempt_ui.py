"""Actual JavaScript status rendering; modeled state, never provider access."""

from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from test_arrival_wizard_service import make_service
from test_wizard_camera_next_step_ui import render, offered


def test_cached_settings_card_never_reads_full_attempts_or_source(
    make_service, monkeypatch
):
    app, runner, source = make_service(mode="physical")

    def forbidden(*a, **kw):
        pytest.fail("Polling attempted a full diagnostic or source read")

    monkeypatch.setattr(
        app._physical_camera, "retained_configuration_diagnostics", forbidden
    )
    monkeypatch.setattr(app._configuration_wizard, "packet", forbidden)
    before = source["calls"]
    for _ in range(4):
        card = app.view()["camera_configuration_attempt"]
        assert card["attempts"] == [] and card["settings_reference_retained"] is False
    assert (
        source["calls"] == before
        and not runner.calls
        and not app.export_directory.exists()
    )


def test_actual_card_rejects_changed_identity_authority_raw_data_and_inconsistent_outcome(
    make_service,
):
    app, _, _ = make_service(mode="physical")
    view = app.view()
    empty = view["camera_configuration_attempt"]
    good = deepcopy(empty)
    good.update(
        settings_reference_retained=True,
        export_available=True,
        attempts=[
            dict(
                operation_id="operation-" + "1" * 32,
                claimed=True,
                phase="CAPTURE_PUBLISHED_UNQUALIFIED",
                outcome="SUCCEEDED",
            )
        ],
    )
    cases, expected = [empty, good], [True, True]
    for key, value in (
        ("physical_authority", True),
        ("hardware_qualified", True),
        ("connected", True),
        ("source_sha256", "f" * 64),
        ("launch_session_id", "other"),
        ("maximum_attempts", 9),
        ("export_available", False),
        ("attempts", good["attempts"] * 2),
        ("capture_action", "physical_camera_capture"),
        ("export_action", "physical_camera_probe_attempt_export"),
        ("raw_original", "NEVER_RENDER"),
    ):
        changed = deepcopy(good)
        changed[key] = value
        cases.append(changed)
        expected.append(False)
    for key, value in (
        ("claimed", False),
        ("phase", "CONNECTED"),
        ("outcome", "FAILED"),
        ("operation_id", "camera-path"),
    ):
        changed = deepcopy(good)
        changed["attempts"][0][key] = value
        cases.append(changed)
        expected.append(False)
    script = (
        Path(__file__).resolve().parents[2] / "src/rocell/ui/static/app.js"
    ).read_text(encoding="utf-8")
    section = script[
        script.index("  function cameraConfigurationAttemptValid(") : script.index(
            "  function physicalCameraSetup()"
        )
    ]
    harness = r"""
const fs=require('fs'), input=JSON.parse(fs.readFileSync(0,'utf8'));
function cameraConfigurationValidators(){return {exact:(x,k)=>x!==null&&typeof x==='object'&&!Array.isArray(x)&&Object.keys(x).length===k.length&&k.every(n=>Object.hasOwn(x,n)),digest:x=>typeof x==='string'&&/^[0-9a-f]{64}$/.test(x)}}
let state={view:input.view};
function element(tag,cls,text){return {tag,text,children:[],append(...x){this.children.push(...x)}}}
function card(t){return element('section','',t)}
function facts(v){return element('div','',JSON.stringify(v))}
eval(input.script+`
const valid=input.cases.map(x=>cameraConfigurationAttemptValid(x,input.view));
state.view.camera_configuration_attempt=input.cases[1]; const good=cameraConfigurationAttempt();
state.view.camera_configuration_attempt=input.cases[12]; const bad=cameraConfigurationAttempt();
process.stdout.write(JSON.stringify({valid,good,bad}));`);
"""
    node = shutil.which("node")
    assert node, "Node required to execute the actual browser renderer"
    run = subprocess.run(
        [node, "-e", harness],
        input=json.dumps(dict(script=section, cases=cases, view=view)),
        text=True,
        capture_output=True,
        timeout=10,
        check=True,
    )
    result = json.loads(run.stdout)
    assert result["valid"] == expected
    assert "NO CALIBRATION OR ARM AUTHORITY" in json.dumps(result["good"])
    assert "NOT_VERIFIED" in json.dumps(result["bad"])
    assert "NEVER_RENDER" not in json.dumps(result["bad"])


@pytest.mark.parametrize("phase", ["settings", "failed", "held"])
def test_whole_browser_guidance_only_navigates_to_explicit_eligible_forms(
    make_service, phase
):
    app, _, _ = make_service(mode="physical")
    view = app.view()
    card = view["camera_configuration_attempt"]
    card["settings_reference_retained"] = True
    capture, export = card["capture_action"], card["export_action"]
    if phase == "failed":
        card.update(
            export_available=True,
            attempts=[
                dict(
                    operation_id="operation-" + "1" * 32,
                    claimed=True,
                    phase="FAILED_HELD",
                    outcome="FAILED",
                )
            ],
        )
    view["actions"] = [
        offered(capture, enabled=phase == "settings"),
        offered(export, enabled=phase == "failed"),
    ]
    clicked = capture if phase == "settings" else export if phase == "failed" else None
    page = render(view, clicked)
    assert [x["id"] for x in page["links"]] == ([] if clicked is None else [clicked])
    assert "No automatic capture or retry" in page["text"]
    if phase == "held":
        assert "do not initialize a replacement store" in page["text"]
