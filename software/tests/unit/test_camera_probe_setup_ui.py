"""Actual browser projection/renderer, modeled setup context and no I/O."""

from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from test_arrival_wizard_service import make_service


def model(app, state="PREPARED_REVIEW_REQUIRED"):
    value = app._physical_camera_setup.probe_record_view()
    publication = dict(status="CURRENT", operation_id="MODELED-file-only-result")
    value.update(
        publication=publication,
        state=state,
        preparation_sha256="a" * 64,
        review_sha256="b" * 64 if state == "REVIEWED_FOR_ADMISSION" else None,
        export_available=True,
    )
    setup = dict(
        source_sha256=value["source_sha256"],
        launch_session_id=value["launch_session_id"],
        publication=deepcopy(publication),
        session=dict(
            stages=[
                dict(
                    state=(
                        "PASS"
                        if i < 4
                        else (
                            (
                                "BLOCKED"
                                if state == "PREPARED_REVIEW_REQUIRED"
                                else "WAITING_OPERATOR"
                            )
                            if i == 4
                            else "PENDING"
                        )
                    )
                )
                for i in range(15)
            ]
        ),
    )
    return dict(value=value, setup=setup)


def test_closed_projection_and_navigation_never_start_actions(make_service):
    app, runner, _ = make_service(mode="physical")
    cases = [model(app), model(app, "REVIEWED_FOR_ADMISSION")]
    expected = [True, True]
    for path, replacement in [
        (("value", "physical_authority"), True),
        (("value", "connected"), True),
        (("value", "hardware_qualified"), True),
        (("value", "schema"), "unknown"),
        (("value", "export_action"), "physical_camera_probe"),
        (("value", "review_sha256"), "b" * 64),
        (("value", "preparation_sha256"), None),
        (("value", "publication", "status"), "CURRENT_HARDWARE"),
        (("value", "source_sha256"), "f" * 64),
        (("value", "raw_original"), "NEVER_RENDER_THIS"),
        (("setup", "session", "stages", 4, "state"), "PASS"),
        (("setup", "session", "stages", 5, "state"), "WAITING_OPERATOR"),
    ]:
        case = model(app)
        target = case
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = replacement
        cases.append(case)
        expected.append(False)
    pending = model(app)
    pending["value"].update(state="PENDING_PUBLICATION", preparation_sha256=None)
    pending["value"]["publication"]["status"] = pending["setup"]["publication"][
        "status"
    ] = "PENDING"
    cases.append(pending)
    expected.append(True)
    script = (
        Path(__file__).resolve().parents[2] / "src/rocell/ui/static/app.js"
    ).read_text(encoding="utf-8")
    section = script[
        script.index("  function cameraProbeSetupValid(") : script.index(
            "  function physicalCameraSetup()"
        )
    ]
    harness = r"""
const fs=require('fs'), input=JSON.parse(fs.readFileSync(0,'utf8'));
function cameraConfigurationValidators(){return {exact:(x,keys)=>x!==null&&typeof x==='object'&&!Array.isArray(x)&&Object.keys(x).length===keys.length&&keys.every(k=>Object.hasOwn(x,k)),digest:x=>typeof x==='string'&&/^[0-9a-f]{64}$/.test(x)}}
let state={view:{}}, navigation=[];
function element(tag,cls,text){return {tag,text,children:[],events:{},append(...items){this.children.push(...items)},addEventListener(name,fn){this.events[name]=fn}}}
function card(title){return element('section','',title)}
function facts(value){return element('div','',JSON.stringify(value))}
function heading(text){return element('h3','',text)}
function human(text){return text}
function physicalSetupValidators(){return {setup:x=>x}}
function navigate(page){navigation.push(page)}
eval(input.script+`
const valid=input.cases.map(c=>cameraProbeSetupValid(c.value,c.setup));
state.view={camera_probe_setup:input.cases[0].value,physical_camera_setup:input.cases[0].setup};
const rendered=cameraProbeSetup();
const button=rendered.children.find(x=>x.tag==='button');
button.events.click();
process.stdout.write(JSON.stringify({valid,navigation,text:JSON.stringify(rendered)}));
`);
"""
    node = shutil.which("node")
    assert node
    result = subprocess.run(
        [node, "-e", harness],
        input=json.dumps(dict(script=section, cases=cases)),
        encoding="utf-8",
        capture_output=True,
        timeout=20,
        check=True,
    )
    actual = json.loads(result.stdout)
    assert actual["valid"] == expected
    assert actual["navigation"] == ["diagnostics"]
    assert "NO CAMERA OR ARM ACCESS" in actual["text"]
    assert "A preparation review does not run the probe" in actual["text"]
    assert not app._physical_camera_setup._probe_queues and not runner.calls


def test_startup_view_does_not_probe_create_records_or_export(make_service):
    app, runner, source = make_service(mode="physical")
    reads = source["calls"]
    for _ in range(3):
        value = app.view()["camera_probe_setup"]
        assert value["state"] == "NOT_PREPARED"
        assert value["export_available"] is False
        assert value["attempts"] == {}
    assert source["calls"] == reads and not runner.calls
    assert not app.export_directory.exists()
