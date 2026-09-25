"""Actual browser/terminal rendering with modeled data; no hardware or live UI."""

from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from rocell.application.camera_operating_proposal_projection import (
    validate_proposal_projection,
)
from rocell.application.camera_operating_proposal_wizard import ACTION
from rocell.ui.terminal import _TerminalWizard
from test_arrival_wizard_service import make_service, _run
from test_camera_operating_proposal_wizard import configured_draft, VALUES
from test_wizard_camera_next_step_ui import render, offered


def test_browser_and_terminal_reject_the_same_malformed_drafts(configured_draft):
    app, _, _, _, _ = configured_draft
    empty = app.view()["camera_operating_proposal"]
    assert _run(app, ACTION, VALUES)["status"] == "SUCCEEDED"
    view = app.view()
    good = view["camera_operating_proposal"]
    cases = [empty, good]
    pending = deepcopy(good)
    pending.update(
        state="PENDING_PUBLICATION", current_operation_id=None, proposal=None
    )
    cases.append(pending)
    historical = deepcopy(pending)
    historical["state"] = "HISTORICAL_HELD"
    cases.append(historical)
    expected = [True] * 4
    for key, value in (
        ("physical_authority", True),
        ("approved_operating_policy", True),
        ("original_stage_record_retained", True),
        ("connected", True),
        ("hardware_qualified", 0),
        ("source_sha256", "f" * 64),
        ("launch_session_id", "other"),
        ("current_operation_id", "NEVER_RENDER"),
        ("attempted", True),
        ("attempted", 0),
        ("maximum_attempts", 9),
        ("proposal", None),
        ("state", "APPROVED"),
        ("meaning", "NEVER_RENDER"),
        ("raw_private", "NEVER_RENDER"),
    ):
        changed = deepcopy(good)
        changed[key] = value
        cases.append(changed)
        expected.append(False)
    for field, value in (
        ("fps_numerator", 9),
        ("fps_denominator", 0),
        ("stride_bytes", 0),
        ("subtype", "MJPG"),
        ("width", 4),
        ("fps_numerator", 8.5),
        ("extra", True),
    ):
        changed = deepcopy(good)
        changed["proposal"]["target_mode"][field] = value
        cases.append(changed)
        expected.append(False)
    equivalent = deepcopy(good)
    equivalent["proposal"]["target_mode"].update(
        fps_numerator=8000, fps_denominator=1000
    )
    cases.append(equivalent)
    expected.append(True)
    results = [
        validate_proposal_projection(
            x,
            source_sha256=view["source_binding_sha256"],
            launch_session_id=view["session_id"],
        )
        is not None
        for x in cases
    ]
    assert results == expected
    script = (
        Path(__file__).resolve().parents[2] / "src/rocell/ui/static/app.js"
    ).read_text(encoding="utf-8")
    section = script[
        script.index("  function cameraOperatingProposalValid(") : script.index(
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
const valid=input.cases.map(x=>cameraOperatingProposalValid(x,input.view));
state.view.camera_operating_proposal=input.cases[1];const good=cameraOperatingProposal();
state.view.camera_operating_proposal=input.cases[17];const bad=cameraOperatingProposal();
process.stdout.write(JSON.stringify({valid,good,bad}));`);
"""
    node = shutil.which("node")
    assert node, "Node required for actual JavaScript renderer coverage"
    completed = subprocess.run(
        [node, "-e", harness],
        input=json.dumps(dict(script=section, view=view, cases=cases)),
        text=True,
        capture_output=True,
        timeout=10,
        check=True,
    )
    observed = json.loads(completed.stdout)
    assert observed["valid"] == expected
    assert "DRAFT ONLY" in json.dumps(observed["good"])
    assert "NOT_VERIFIED" in json.dumps(observed["bad"])
    assert "NEVER_RENDER" not in json.dumps(observed["bad"])

    # Exercise the actual terminal method without an interactive app or stdin.
    lines = []
    sink = type("TerminalSink", (), {"write": lambda self, x: lines.append(str(x))})()
    _TerminalWizard.show_camera_operating_proposal(sink, good, view)
    assert "DRAFT ONLY" in " ".join(lines)
    lines.clear()
    _TerminalWizard.show_camera_operating_proposal(sink, cases[17], view)
    assert "NOT_VERIFIED" in " ".join(lines) and "NEVER_RENDER" not in " ".join(lines)


def test_whole_camera_page_exposes_navigation_but_does_not_run_proposal(
    configured_draft,
):
    app, _, _, _, _ = configured_draft
    view = app.view()
    view["actions"] = [offered(ACTION)]
    view["camera_configuration_attempt"]["settings_reference_retained"] = True
    page = render(view, ACTION)
    assert [link["id"] for link in page["links"]] == [ACTION]
    assert "DRAFT ONLY" in page["text"]
    assert "camera-action-" + ACTION in page["cards"]
    assert not app._operating_proposal.packet()["attempts"]
