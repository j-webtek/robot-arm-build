"""Real JavaScript/terminal rendering; explicitly modeled display metadata."""

from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess

from rocell.application.camera_operating_submission_projection import (
    validate_submission_projection,
)
from rocell.ui.terminal import _TerminalWizard
from test_camera_operating_submission_wizard import (
    submission_ready,
    configured_draft,
    make_service,
    SUBMIT,
)
from test_arrival_wizard_service import _run
from rocell.application.camera_operating_submission_wizard import ACTION


def test_closed_python_browser_and_terminal_projections_agree(submission_ready):
    app = submission_ready[0]
    before = app._operating_submission.view()
    before["publication"] = dict(status="NOT_PUBLISHED", operation_id=None)
    assert _run(app, ACTION, SUBMIT)["status"] == "SUCCEEDED"
    view = app.view()
    good = view["camera_operating_submission"]
    # Model the closed reference shape; this public fixture has no M1 backend.
    good["reference"] = dict(
        evidence_id="evidence-" + "d" * 64,
        stage="camera_mode_controls",
        package_sha256="d" * 64,
        manifest_sha256="e" * 64,
        payload_sha256=good["submission_sha256"],
        payload_bytes=12345,
    )
    cases, expected = [before, good], [True, True]
    partial = deepcopy(good)
    partial.update(state="INCOMPLETE", attempted=0)
    cases.append(partial)
    expected.append(True)
    for key, value in (
        ("stage_passed", True),
        ("approved_operating_policy", True),
        ("connected", True),
        ("physical_authority", True),
        ("hardware_qualified", 0),
        ("review_required", False),
        ("original_stage_authenticated", 1),
        ("original_stage_authenticated", False),
        ("source_sha256", "f" * 64),
        ("launch_session_id", "wrong"),
        ("state", "APPROVED"),
        ("attempted", True),
        ("maximum_attempts", 4),
        ("submission_id", "NEVER_RENDER"),
        ("submission_sha256", "0" * 64),
        ("proposal_sha256", None),
        ("assessment_sha256", 4),
        ("reference", None),
        ("retention", "M1_PUBLICATION_UNCONFIRMED"),
        ("capture_requests", ["one", "one"]),
        ("capture_requests", ["only-one"]),
        ("pixel_check_semantics", "CURRENT_VERIFIED"),
        ("meaning", "NEVER_RENDER"),
        ("extra", "NEVER_RENDER"),
    ):
        changed = deepcopy(good)
        changed[key] = value
        cases.append(changed)
        expected.append(False)
    for key, value in (
        ("payload_bytes", True),
        ("payload_bytes", 81921),
        ("stage", "camera_frame_freshness"),
        ("payload_sha256", "f" * 64),
        ("evidence_id", "NEVER_RENDER"),
        ("manifest_sha256", "0" * 64),
    ):
        changed = deepcopy(good)
        changed["reference"][key] = value
        cases.append(changed)
        expected.append(False)
    actual = [
        validate_submission_projection(
            v,
            source_sha256=view["source_binding_sha256"],
            launch_session_id=view["session_id"],
        )
        is not None
        for v in cases
    ]
    assert actual == expected
    script = (
        Path(__file__).resolve().parents[2] / "src/rocell/ui/static/app.js"
    ).read_text(encoding="utf-8")
    section = script[
        script.index("  function cameraOperatingSubmissionValid(") : script.index(
            "  function cameraConfigurationAttemptValid("
        )
    ]
    harness = r"""
const fs=require('fs'),input=JSON.parse(fs.readFileSync(0,'utf8'));
let state={view:input.view};
function element(tag,cls,text){return {tag,text,children:[],append(...x){this.children.push(...x)}}}
function card(t){return element('section','',t)}
function facts(v){return element('div','',JSON.stringify(v))}
eval(input.script+`
const valid=input.cases.map(x=>cameraOperatingSubmissionValid(x,input.view));
state.view.camera_operating_submission=input.cases[1];const good=cameraOperatingSubmission();
state.view.camera_operating_submission=input.cases[16];const bad=cameraOperatingSubmission();
process.stdout.write(JSON.stringify({valid,good,bad}));`);
"""
    node = shutil.which("node")
    assert node, "Node is required for JavaScript renderer coverage"
    done = subprocess.run(
        [node, "-e", harness],
        input=json.dumps(dict(script=section, cases=cases, view=view)),
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    observed = json.loads(done.stdout)
    assert observed["valid"] == expected
    assert "UNREVIEWED" in json.dumps(observed["good"])
    assert "in Camera actions or Control Center" in json.dumps(observed["good"])
    assert "review below" not in json.dumps(observed["good"])
    assert "NOT_VERIFIED" in json.dumps(
        observed["bad"]
    ) and "NEVER_RENDER" not in json.dumps(observed["bad"])
    lines = []
    sink = type("Sink", (), {"write": lambda self, text: lines.append(str(text))})()
    _TerminalWizard.show_camera_operating_submission(sink, good, view)
    assert "UNREVIEWED" in " ".join(lines)
    lines.clear()
    _TerminalWizard.show_camera_operating_submission(sink, cases[16], view)
    assert "NOT_VERIFIED" in " ".join(lines) and "NEVER_RENDER" not in " ".join(lines)
