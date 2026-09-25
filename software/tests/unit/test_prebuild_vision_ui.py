"""Run the actual generic Camera renderer; no browser or device is opened."""

import pytest

from rocell.application.wizard_actions import ACTION_BY_ID
from test_wizard_camera_next_step_ui import fresh, render


@pytest.mark.parametrize("mode", ["rehearsal", "physical"])
@pytest.mark.parametrize("busy", [False, True])
def test_prebuild_pack_is_visible_with_scope_and_never_runs_on_page_load(mode, busy):
    action = ACTION_BY_ID["prebuild_vision_checks"].view(mode=mode, busy=busy)
    snapshot = fresh([action])
    snapshot["mode"] = mode
    page = render(snapshot)
    assert "camera-action-prebuild_vision_checks" in page["cards"]
    assert "Run pre-build vision checks (no devices)" in page["text"]
    assert "No camera/arm access" in page["text"]
    assert "Expected fault rejection is success" in page["text"]
    assert page["dialogOpen"] is False
    assert page["requests"] == [{"path": "/api/view", "method": "GET", "body": None}]
    if busy:
        assert "A diagnostic action is running" in page["text"]
