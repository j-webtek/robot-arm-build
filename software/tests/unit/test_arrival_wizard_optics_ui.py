"""Cached optics presentation only; using the existing pure DOM harness."""

from test_arrival_wizard_reopen_ui import ReopenService, browser, commissioning
from test_arrival_wizard_terminal import run, dispatched


def projection():
    value = commissioning()
    value["optics_evaluation"] = {
        "stage": "static_registration",
        "outcome": "BLOCKED",
        "evaluation_sha256": "a" * 64,
        "selected_inputs_sha256": "b" * 64,
        "meaning": "Substantive synthetic checks only; no installed calibration.",
        "checks": [
            {
                "check_id": "nominal_pose_policy",
                "passed": False,
                "observed": {"translation_error_mm": 2.0},
                "meaning": "Nominal residual must pass.",
            },
            {
                "check_id": "tag_loss_rejected",
                "passed": True,
                "observed": {"estimate_available": False},
                "meaning": "Expected negative test only.",
            },
            None,
        ],
        "reports": {"large_fixture": "NEVER_RENDER_RAW_FIXTURE"},
    }
    return value


def test_browser_shows_substantive_results_not_generic_raw_documents():
    result = browser(projection())
    assert result["status"] == "Local service connected"
    assert "Retained synthetic optics checks" in result["text"]
    assert "2" in result["text"]
    assert "Expected negative test only" in result["text"]
    assert "not the evaluated pixels" in result["text"]
    assert "NEVER_RENDER_RAW_FIXTURE" not in result["text"]
    assert result["requests"] == [{"path": "/api/view", "method": "GET", "body": None}]


def test_terminal_show_quit_never_dispatches_evaluation():
    service = ReopenService(projection())
    result, output, _ = run(service, ["quit"])
    output = "\n".join(str(item) for item in output)
    assert result == 0
    assert "Retained synthetic optics checks" in output
    assert "nominal_pose_policy" in output
    assert "dependency only" in output
    assert "NEVER_RENDER_RAW_FIXTURE" not in output
    assert dispatched(service, "prepare") == []
    assert dispatched(service, "execute") == []
