"""Readiness projection and both presentations; incapable public runner only."""

from copy import deepcopy

import pytest

from rocell.application.arm_wizard_readiness import arm_wizard_readiness
from rocell.application.wizard_actions import ACTION_BY_ID
from test_wizard_native_arm_integration import setup, generic_review, inspect
from test_wizard_native_arm_ui import render, produced
from test_arrival_wizard_device_selection_ui import browser


def test_current_public_flow_and_ui_are_inert(setup):
    service, runner, _, _ = setup("physical")
    before = service.view()
    assert before["arm_readiness"]["state"] == "INSPECT_METADATA"
    assert runner.calls == []
    generic_review(service)
    assert service.view()["arm_readiness"]["state"] == "INSPECT_NATIVE_METADATA"
    inspect(service)
    view = service.view()
    assert view["arm_readiness"]["state"] == "PHYSICAL_BACKEND_PENDING"
    count = len(runner.calls)
    assert arm_wizard_readiness(view) == view["arm_readiness"]
    assert len(runner.calls) == count


def test_worklist_reflects_approved_basis_without_claiming_measurement(setup):
    service, runner, _, _ = setup("physical")
    work = {
        item["id"]: item["required"]
        for item in service.view()["arm_readiness"]["physical_connection_worklist"]
    }
    assert "ROCELL-ARM-USB-PASSIVE-ENTRY-002" in work["power_and_startup"]
    assert "Measured isolation remains unknown" in work["power_and_startup"]
    assert "Do not repeat model identification" in work["received_board"]
    assert runner.calls == []


def test_browser_and_terminal_render_shared_guidance_without_dispatch():
    view, _ = produced()
    view["status"] = "READY_FOR_DIAGNOSTICS"
    view["exports"] = {"directory": "SYNTHETIC-EXPORT-FOLDER", "items": []}
    view["actions"] = [ACTION_BY_ID["export_logs"].view(mode="rehearsal", busy=False)]
    view["arm_readiness"] = arm_wizard_readiness(view)
    for output in render(view):
        assert "Arm onboarding: next step" in output
        assert "REHEARSAL_ONLY" in output
        assert "SYNTHETIC-EXPORT-FOLDER" in output
        assert "automatic joint motion on power-up" in output
        assert "original" in output


def test_guided_action_does_not_duplicate_field_ids():
    view, _ = produced()
    view["status"] = "READY_FOR_DIAGNOSTICS"
    view["exports"] = {"directory": "SYNTHETIC-EXPORT-FOLDER", "items": []}
    view["device_selection"]["status"] = "NO_INVENTORY"
    view["actions"] = [
        ACTION_BY_ID["rehearse_device_inventory"].view(mode="rehearsal", busy=False)
    ]
    view["arm_readiness"] = arm_wizard_readiness(view)
    page = browser(view["device_selection"], "arm", snapshot=view)
    ids = [
        control["id"]
        for control in page["controls"]
        if "rehearse_device_inventory" in control["id"]
    ]
    assert ids and len(ids) == len(set(ids))
    assert page["requests"] == [{"path": "/api/view", "method": "GET", "body": None}]


@pytest.mark.parametrize(
    "mode,expected",
    [("physical", "PHYSICAL_BACKEND_PENDING"), ("rehearsal", "REHEARSAL_ONLY")],
)
def test_matched_metadata_never_enables_serial(setup, mode, expected):
    service, _, _, _ = setup(mode)
    generic_review(service)
    inspect(service)
    result = service.view()["arm_readiness"]
    assert result["state"] == expected
    assert result["next_action_id"] == "export_logs"
    assert result["connected"] is result["physical_authority"] is False
    if mode == "physical":
        assert "general Connect and motion remain held" in result["message"]
        assert "separately gated diagnostics" in result["message"]


@pytest.mark.parametrize(
    "status,expected",
    [
        ("DIAGNOSTIC_RUNNING", "WAIT_FOR_OPERATION"),
        ("DIAGNOSTIC_HOLD", "REVIEW_SERVICE_HOLD"),
        ("SHUTTING_DOWN", "REVIEW_SERVICE_HOLD"),
    ],
)
def test_global_holds_override_metadata(setup, status, expected):
    service, _, _, _ = setup("physical")
    view = service.view()
    view["status"] = status
    original = deepcopy(view)
    assert arm_wizard_readiness(view)["state"] == expected
    assert view == original


def test_historical_native_result_requires_fresh_inspection(setup):
    service, _, _, _ = setup("physical")
    generic_review(service)
    inspect(service)
    view = service.view()
    view["native_arm_metadata"]["status"] = "HISTORICAL_HELD"
    result = arm_wizard_readiness(view)
    assert result["state"] == "INSPECT_NATIVE_METADATA"


def test_held_mapping_recommends_export_not_retry(setup):
    service, _, _, _ = setup("physical")
    generic_review(service)
    inspect(service)
    view = service.view()
    view["native_arm_metadata"]["report"]["status"] = "HELD"
    result = arm_wizard_readiness(view)
    assert result["state"] == "REVIEW_METADATA_HOLD"
    assert result["next_action_id"] == "export_logs"


def test_no_review_requires_explicit_candidate_selection(setup):
    service, _, _, _ = setup("physical")
    generic_review(service)
    view = service.view()
    view["device_selection"]["devices"]["SERIAL"]["review"] = None
    assert arm_wizard_readiness(view)["state"] == "REVIEW_CANDIDATE"


def test_worklist_is_detached_non_authorizing_guidance(setup):
    service, runner, _, _ = setup("physical")
    first = service.view()["arm_readiness"]
    work = first["physical_connection_worklist"]
    assert len(work) == 6
    assert {item["id"] for item in work} == {
        "received_board",
        "power_and_startup",
        "original_admission",
        "qualified_lifecycle",
        "explicit_passive_start",
        "feedback_then_calibration",
    }
    assert all(set(item) == {"id", "owner", "milestone", "required"} for item in work)
    work[0]["required"] = "caller changed this"
    work.clear()
    fresh = service.view()["arm_readiness"]
    assert len(fresh["physical_connection_worklist"]) == 6
    assert fresh["connected"] is fresh["physical_authority"] is False
    assert runner.calls == []
