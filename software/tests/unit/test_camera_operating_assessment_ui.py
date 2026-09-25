"""Actual inert browser rendering of the original-assessment action."""

import shutil

from rocell.application.camera_operating_assessment_wizard import ACTION
from rocell.application.camera_operating_proposal_wizard import ACTION as PROPOSAL
from test_arrival_wizard_service import make_service, _run
from test_camera_operating_proposal_wizard import configured_draft, VALUES
from test_wizard_camera_next_step_ui import render


def test_assessment_form_exposes_explicit_captures_without_executing(configured_draft):
    assert shutil.which("node"), "Node is required for this UI test"
    app, runner, _, _, _ = configured_draft
    assert _run(app, PROPOSAL, VALUES)["status"] == "SUCCEEDED"
    page = render(app.view(), ACTION)
    assert "camera-action-" + ACTION in page["cards"]
    assert "Check proposal against saved original evidence" in page["text"]
    assert "Saved settings capture 1" in page["text"]
    assert "Saved settings capture 2" in page["text"]
    assert page["navigations"] == [
        dict(kind="scroll", id="camera-action-" + ACTION),
        dict(kind="focus", id="camera-action-" + ACTION),
    ]
    assert not app._operating_assessment.packet()["attempts"] and not runner.calls
