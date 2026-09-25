"""Source-only overview/publishing tests; injected outcomes are not M1 proof."""

from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading

import pytest

from rocell.application import arrival_wizard_service as arrival
from rocell.application import physical_source_preflight_service as preflight
from rocell.application.wizard_actions import ACTION_BY_ID, WizardError
from test_arrival_wizard_device_selection_ui import _HARNESS
from test_arrival_wizard_service import make_service  # noqa: F401
from test_wizard_camera_configuration_publication import pending


WORKSPACE = Path(__file__).resolve().parents[3]
ACTION = "physical_source_preflight"


def projection(status="NOT_STARTED"):
    # The actual inert service provides the exact projected contract.
    value = preflight.PhysicalSourcePreflightService(
        WORKSPACE, launch_id="wizard-" + "1" * 32, source_sha256="a" * 64
    ).view()
    value["status"] = status
    value["source_observation_current"] = status == "FILE_CHECKS_COHERENT"
    return value


def summary():
    return {
        "schema": "rocell.physical_source_preflight_summary.v1",
        "outcome": "FILE_CHECKS_COHERENT",
        "report_sha256": "a" * 64,
        "file_count": 59,
        "checks": [{"check_id": "fixed_source_closure", "passed": True}],
        "canonical_stage_holds": [
            "DISCONNECTED_REQUIRED_NOT_OBSERVED",
            "HZ_012_CANONICAL_EVIDENCE_NOT_CLOSED",
        ],
        "canonical_stage_pass": False,
        "physical_authority": False,
        "power_state": "UNKNOWN",
        "device_io_performed": False,
        "meaning": "Injected UI observation, not a durable evidence fixture",
    }


def snapshot(value, *, mode="physical"):
    definition = ACTION_BY_ID[ACTION]
    return {
        "revision": 1,
        "mode": mode,
        "session_id": "wizard-" + "1" * 32,
        "cell_id": "test-cell",
        "status": "READY_FOR_DIAGNOSTICS",
        "physical_authority": False,
        "camera": {"status": "NOT_CONNECTED"},
        "arm": {"status": "NOT_CONNECTED"},
        "stages": [],
        "operations": [],
        "physical_source_preflight": value,
        "actions": [
            {
                "action_id": ACTION,
                "label": definition.label,
                "description": definition.description,
                "section": "overview",
                "fields": deepcopy(list(definition.fields)),
                "enabled": mode == "physical",
                "blocked_reasons": [] if mode == "physical" else ["Physical mode only"],
            }
        ],
    }


def browser(view, *, prepare=False):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Optional Node runtime unavailable")
    # Reuse the existing DOM harness but match the actual server-owned label.
    harness = _HARNESS.replace("input.action.replaceAll('_',' ')", "input.label")
    harness = harness.replace(
        "controls:nodes.filter",
        "scriptTags:nodes.filter(node=>node.tagName==='SCRIPT').length,controls:nodes.filter",
    )
    result = subprocess.run(
        [node, "-e", harness],
        input=json.dumps(
            {
                "script": (
                    WORKSPACE / "software/src/rocell/ui/static/app.js"
                ).read_text(encoding="utf-8"),
                "snapshot": view,
                "page": "overview",
                "prepare": prepare,
                "action": ACTION,
                "label": ACTION_BY_ID[ACTION].label,
                "values": {"operator_id": "operator-a"},
            }
        ),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=5,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    value = json.loads(result.stdout)
    assert value["status"] == "Local service connected", value
    return value


@pytest.mark.parametrize(
    "status",
    [
        "NOT_STARTED",
        "RUNNING",
        "HELD",
        "FILE_CHECKS_COHERENT",
        "PUBLICATION_PENDING",
        "PUBLICATION_HELD",
    ],
)
def test_closed_physical_source_states_render_without_actions(status):
    value = projection(status)
    if status != "NOT_STARTED":
        value["report"] = summary()
        value["attempt"] = {
            "state": "SEALED_KNOWN",
            "composition": "PHYSICAL_DIAGNOSTIC_NO_DEVICE_IO",
            "physical_authority": "NONE",
        }
    result = browser(snapshot(value))
    assert result["requests"] == [{"path": "/api/view", "method": "GET", "body": None}]
    assert "Actual source preflight" in result["text"]
    assert "does not complete a physical stage" in result["text"]
    assert "UNKNOWN" in result["text"]
    assert "SOURCE PREFLIGHT SUMMARY UNAVAILABLE" not in result["text"]
    assert status.replace("_", " ") in result["text"]
    assert result["scriptTags"] == 0


@pytest.mark.parametrize("value", [None, {}, [], {"schema": "wrong"}])
def test_missing_projection_is_safe_and_does_not_dispatch(value):
    result = browser(snapshot(value))
    assert "SOURCE PREFLIGHT SUMMARY UNAVAILABLE" in result["text"]
    assert result["requests"] == [{"path": "/api/view", "method": "GET", "body": None}]


@pytest.mark.parametrize(
    "changes",
    [
        {"physical_authority": True},
        {"canonical_stage_pass": True},
        {"device_io_performed": True},
        {"power_state": "DEENERGIZED"},
        {"status": "PASS"},
        {"status": {"claim": "QUALIFIED"}},
        {"composition": "HARDWARE_INCAPABLE_REHEARSAL"},
        {"replay_allowed": True},
    ],
)
def test_malformed_or_authority_changing_projection_is_withheld(changes):
    value = projection("FILE_CHECKS_COHERENT")
    value.update(changes)
    result = browser(snapshot(value))
    assert "SOURCE PREFLIGHT SUMMARY UNAVAILABLE" in result["text"]
    assert "FILE CHECKS COHERENT" not in result["text"]
    assert result["scriptTags"] == 0


def test_report_and_error_text_are_escaped_not_executed():
    value = projection("HELD")
    value["report"] = summary()
    marker = "<script>throw new Error('executed')</script>"
    value["error"] = {"code": "SOURCE_FILE_UNAVAILABLE", "detail": marker}
    result = browser(snapshot(value))
    assert marker in result["text"]
    assert result["scriptTags"] == 0
    assert len(result["requests"]) == 1


def test_preview_requests_only_preparation_no_execute_or_file_action():
    result = browser(snapshot(projection()), prepare=True)
    assert [row["path"] for row in result["requests"]] == ["/api/view", "/api/prepare"]
    assert result["requests"][1]["body"] == {
        "action_id": ACTION,
        "input": {"operator_id": "operator-a"},
        "expected_revision": 1,
    }
    assert result["dialogOpen"]


def test_rehearsal_view_does_not_mislabel_its_reports_as_actual_source():
    result = browser(snapshot(projection("FILE_CHECKS_COHERENT"), mode="rehearsal"))
    assert "Actual source preflight" not in result["text"]
    assert "FILE CHECKS COHERENT" not in result["text"]
    assert len(result["requests"]) == 1


def forbidden(*args, **kwargs):
    raise AssertionError("Constructor/status/preview must not dispatch or qualify")


def test_actual_preflight_constructor_and_view_are_inert(monkeypatch):
    monkeypatch.setattr(preflight, "source_fingerprint", forbidden)
    monkeypatch.setattr(preflight, "source_preflight_registration", forbidden)
    monkeypatch.setattr(preflight.PhysicalOnboardingM1Runtime, "initialize", forbidden)
    service = preflight.PhysicalSourcePreflightService(
        WORKSPACE, launch_id="wizard-" + "9" * 32, source_sha256="a" * 64
    )
    assert service.view()["status"] == "NOT_STARTED"
    assert service.retained_report() is None
    service.view()["status"] = "CORRUPTED_RETURNED_COPY"
    assert service.view()["status"] == "NOT_STARTED"


def test_action_is_physical_only_and_preview_does_not_initialize(
    make_service, monkeypatch
):
    rehearsal, _, _ = make_service()
    with pytest.raises(WizardError, match="physical"):
        rehearsal.prepare_action(
            ACTION, {"operator_id": "operator"}, rehearsal.view()["revision"]
        )
    physical, runner, _ = make_service(mode="physical")
    monkeypatch.setattr(physical._source_preflight, "perform", forbidden)
    monkeypatch.setattr(physical._source_preflight, "blocked_reason", lambda: None)
    view = physical.view()
    ticket = physical.prepare_action(
        ACTION, {"operator_id": "operator-a"}, view["revision"]
    )
    assert "power remains UNKNOWN" in " ".join(ticket["effects"])
    assert "PHYSICAL_DIAGNOSTIC" in " ".join(ticket["effects"])
    assert physical._source_preflight.view()["status"] == "NOT_STARTED"
    assert not physical._source_preflight._used
    assert not runner.calls and physical._events == []


def seed(service):
    source = service._source_preflight
    source._cached.update(status="FILE_CHECKS_COHERENT", report=summary())
    source._retained_report = {
        "retained_source_report": {"private_evidence": "original"},
        "physical_authority": False,
    }
    return deepcopy(source._cached), source._retained_report


def test_inner_coherent_report_is_historical_until_finished_log(make_service):
    service, runner, _ = make_service(mode="physical")
    original, retained = seed(service)
    assert service.view()["physical_source_preflight"]["status"] == "PUBLICATION_HELD"
    operation_id = pending(service, ACTION)
    value = service.view()["physical_source_preflight"]
    assert value["status"] == "PUBLICATION_PENDING"
    assert value["source_observation_current"] is False
    with service._lock:
        service._finish(operation_id, "SUCCEEDED", {"physical_authority": False})
    value = service.view()["physical_source_preflight"]
    assert value["status"] == "FILE_CHECKS_COHERENT"
    assert value["source_observation_current"] is True
    assert service._source_preflight.view() == original
    assert service._source_preflight._retained_report is retained
    assert not runner.calls


@pytest.mark.parametrize("hold", ["source", "log", "failed", "closed"])
def test_current_source_publication_holds_preserve_private_evidence(
    make_service, monkeypatch, hold
):
    service, runner, _ = make_service(mode="physical")
    original, retained = seed(service)
    operation_id = pending(service, ACTION)
    if hold == "log":

        def fail(*args, **kwargs):
            raise OSError("injected diagnostic log loss")

        monkeypatch.setattr(service._log, "append", fail)
    with service._lock:
        service._finish(
            operation_id,
            "FAILED" if hold == "failed" else "SUCCEEDED",
            {"physical_authority": False},
        )
    if hold == "source":
        service._source_changed = True
    elif hold == "closed":
        service._closed = True
    value = service.view()["physical_source_preflight"]
    assert value["status"] == "PUBLICATION_HELD"
    assert value["source_observation_current"] is False
    assert value["report"] == original["report"]
    assert service._source_preflight.view() == original
    assert service._source_preflight._retained_report is retained
    assert not runner.calls


def test_status_reads_neither_source_files_nor_preflight_worker(
    make_service, monkeypatch
):
    service, runner, _ = make_service(mode="physical")
    seed(service)
    monkeypatch.setattr(arrival, "source_fingerprint", forbidden)
    monkeypatch.setattr(preflight, "source_fingerprint", forbidden)
    monkeypatch.setattr(preflight, "source_preflight_registration", forbidden)
    monkeypatch.setattr(service._source_preflight, "perform", forbidden)
    for _ in range(3):
        assert (
            service.view()["physical_source_preflight"]["source_observation_current"]
            is False
        )
    assert not runner.calls


def test_once_per_launch_hold_uses_cached_state_only(make_service, monkeypatch):
    service, _, _ = make_service(mode="physical")
    service._source_preflight._used = True
    monkeypatch.setattr(preflight, "source_fingerprint", forbidden)
    action = next(
        row for row in service.view()["actions"] if row["action_id"] == ACTION
    )
    assert not action["enabled"]
    assert "already attempted" in " ".join(action["blocked_reasons"])
