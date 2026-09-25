"""Exercise the pre-build pack through real algorithms and the wizard HTTP API.

Image observations are synthetic. Host inventory, device adapters and process
launches are forbidden in these tests; the HTTP runner calls the real diagnostic
worker in-process. Production subprocess lifecycle has separate coverage.
"""

from copy import deepcopy
from pathlib import Path
import subprocess
import time
from typing import Any

import pytest

from rocell.application import wizard_worker as worker
from rocell.application.wizard_actions import (
    ACTION_BY_ID,
    CAMERA_FAULTS,
    WizardError,
    validate_action_input,
)
from rocell.application.wizard_diagnostic_export import verify_export

from test_wizard_worker import no_devices  # noqa: F401 - shared deny-I/O fixture
from test_arrival_wizard_integration import (
    WORKSPACE,
    complete,
    execute,
    make_workbench,  # noqa: F401 - shared HTTP fixture
    prepare,
    request,
    view,
)


ACTION = "prebuild_vision_checks"


@pytest.fixture(autouse=True)
def forbid_processes(monkeypatch: pytest.MonkeyPatch, no_devices: Any) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Pre-build pack attempted a subprocess/device helper")

    monkeypatch.setattr(subprocess, "Popen", forbidden)


@pytest.mark.parametrize("mode", ["rehearsal", "physical"])
def test_pack_is_explicit_available_and_has_no_device_input(mode: str) -> None:
    action = ACTION_BY_ID[ACTION]
    assert action.view(mode=mode, busy=False)["enabled"] is True
    assert action.view(mode=mode, busy=True)["enabled"] is False
    assert action.fields == ()
    assert action.timeout_s == 120
    assert "No camera/arm access" in action.description
    assert validate_action_input(action, {}) == {}
    for field in ("device_alias", "camera_index", "path", "port", "fault"):
        with pytest.raises(WizardError):
            validate_action_input(action, {field: "anything"})


def test_all_registered_scenarios_run_and_failed_steps_stay_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    def cli(workspace: Path, args: list[str]) -> dict[str, Any]:
        calls.append(args)
        failed = "wrong-camera-mode" in args
        return {
            "exit_code": 2 if failed else 0,
            "report": {"status": "INJECTED_CHECK_FAILURE" if failed else "FIXTURE"},
            "stderr": "retained failure detail" if failed else "",
        }

    monkeypatch.setattr(worker, "_cli", cli)
    result = worker.run(WORKSPACE, ACTION, {}, "CELL-A")
    assert calls[0] == ["rehearse-b0477-stack", "--require-pass", "--json"]
    assert [args[2] for args in calls[1:]] == list(CAMERA_FAULTS)
    assert all("--require-expected" in args for args in calls[1:])
    assert len(result["steps"]) == 7
    assert result["status"] == "FAILED"
    assert result["steps"][3]["stderr"] == "retained failure detail"
    assert result["physical_authority"] is False


def test_actual_vision_fault_pack_http_export_and_no_stage_advancement(
    make_workbench: Any, monkeypatch: pytest.MonkeyPatch, no_devices: list[str]
) -> None:
    server, service, runner, logs, exports, _ = make_workbench()
    calls: list[str] = []

    def run(action_id: str, values: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        calls.append(action_id)
        assert action_id == ACTION
        return worker.run(WORKSPACE, action_id, values, kwargs["cell_id"])

    monkeypatch.setattr(runner, "run", run)
    before = deepcopy(view(server))
    ticket = prepare(server, ACTION)
    assert not logs.exists() and not exports.exists() and not calls
    operation = execute(server, ticket)
    deadline = time.monotonic() + 60
    while True:
        status, result = request(server, "/api/operations/" + operation["operation_id"])
        assert status == 200
        if result["status"] in {"SUCCEEDED", "FAILED", "TIMED_OUT", "CANCELLED"}:
            break
        assert time.monotonic() < deadline, "Synthetic pack exceeded test deadline"
        time.sleep(0.02)
    assert result["status"] == "SUCCEEDED", result
    report = result["result"]
    assert len(report["steps"]) == 7
    pixels = report["steps"][0]["report"]["pixel_vision"]
    assert pixels["executed"] is True
    assert pixels["normal"]["detected_tag_ids"]
    # The four pose-fit markers are occluded; two held-out station markers
    # remain visible. Marker loss must reject registration, not erase detections.
    assert pixels["tag_loss"]["detected_tag_ids"] == [4, 5]
    assert pixels["tag_loss"]["status"] == "REJECTED"
    assert (
        pixels["tag_loss"]["detail_code"] == "B0477_STATIC_TAG_LOSS_NATURALLY_REJECTED"
    )
    assert not pixels["tag_loss"]["inlier_tag_ids"]
    for step in report["steps"][1:]:
        assert step["exit_code"] == 0
        assert step["report"]["expected_outcome_observed"] is True
        assert step["report"]["hardware_accessed"] is False
    assert report["metadata_inventory_performed"] is False
    assert report["physical_authority"] is False
    assert no_devices == []

    # The same ticket cannot repeat even an incapable campaign. A successful
    # software check does not turn on the camera or become calibration evidence.
    assert execute(server, ticket)["operation_id"] == operation["operation_id"]
    assert calls == [ACTION]
    after = view(server)
    assert after["stages"] == before["stages"]
    assert after["camera"]["status"] == "NOT_CONNECTED"
    assert after["camera"]["last_test"]["action_id"] == ACTION
    assert after["camera"]["image_id"] is None
    for action_id in ("camera_connect", "arm_connect", "execute_task"):
        assert not next(a for a in after["actions"] if a["action_id"] == action_id)[
            "enabled"
        ]

    exported = complete(server, execute(server, prepare(server, "export_logs")))
    assert exported["status"] == "SUCCEEDED", exported
    target = Path(exported["result"]["receipt"]["path"])
    assert target.parent == exports
    assert verify_export(target)["valid"] is True
    # Inspect the published files, not just the current in-memory result.
    documents = [p.read_text(encoding="utf-8") for p in target.rglob("*.json")]
    assert any(
        ACTION in document and "expected_outcome_observed" in document
        for document in documents
    )
    assert calls == [ACTION]
    assert view(server)["stages"] == before["stages"]
