"""Public history inspection: no device acquisition or automatic resumption."""

import pytest
from rocell.application.wizard_actions import WizardError
from test_arrival_wizard_service import make_service, _ticket
from test_wizard_passive_arm_rehearsal import perform
from test_wizard_native_arm_ui import render

ACTION = "inspect_passive_arm_history"


def test_restart_explicit_inspection_renders_historical_result(make_service):
    original, _, _ = make_service()
    perform(original, "rehearse_passive_arm_connection", {"scenario": "nominal"})
    session_id = original.session_id
    original.shutdown()
    service, runner, _ = make_service()
    assert service.view()["passive_arm_history"] is None
    preview = _ticket(service, ACTION, {"session_id": session_id})
    assert service.view()["passive_arm_history"] is None
    assert not runner.calls
    operation = perform(service, ACTION, {"session_id": session_id})
    assert operation["status"] == "SUCCEEDED", operation
    view = service.view()
    assert view["passive_arm_history"]["pair_status"] == "HISTORICAL_PAIR_VERIFIED"
    assert view["passive_arm_history"]["connected"] is False
    assert view["passive_arm_rehearsal"] is None
    for text in render(view):
        assert "Saved passive arm attempt" in text
        assert "HISTORICAL_PAIR_VERIFIED" in text or "HISTORICAL PAIR VERIFIED" in text
    assert not runner.calls
    assert perform(service, "export_logs", {})["status"] == "SUCCEEDED"


@pytest.mark.parametrize(
    "invalid", ["../other", "C:\\other", "wizard-abc", "WIZARD-" + "a" * 32]
)
def test_paths_and_invalid_ids_rejected_at_preview(make_service, invalid):
    service, runner, _ = make_service()
    with pytest.raises(WizardError):
        _ticket(service, ACTION, {"session_id": invalid})
    assert service.view()["operations"] == []
    assert not runner.calls


def test_missing_history_does_not_create_or_connect(make_service):
    service, runner, _ = make_service(mode="physical")
    operation = perform(service, ACTION, {"session_id": "wizard-" + "f" * 32})
    assert operation["status"] == "FAILED"
    assert (
        service.view()["passive_arm_history"]["pair_status"] == "UNVERIFIED_NO_REPLAY"
    )
    assert not runner.calls


def test_failed_test_and_old_source_remain_historical(make_service):
    original, _, source = make_service()
    attempt = perform(
        original, "rehearse_passive_arm_connection", {"scenario": "open-failed"}
    )
    assert attempt["status"] == "FAILED"
    session_id = original.session_id
    original.shutdown()
    source["hash"] = "b" * 64
    service, runner, _ = make_service()
    operation = perform(service, ACTION, {"session_id": session_id})
    assert operation["status"] == "SUCCEEDED"  # File association, not the test.
    history = service.view()["passive_arm_history"]
    assert history["source_matches_current"] is False
    assert history["passive_summary"]["status"] == "FAILED_KNOWN"
    assert history["authenticated"] is history["connected"] is False
    assert not runner.calls


def test_failed_reinspection_replaces_previously_verified_display(make_service):
    original, _, _ = make_service()
    perform(original, "rehearse_passive_arm_connection", {"scenario": "nominal"})
    service, _, _ = make_service()
    assert (
        perform(service, ACTION, {"session_id": original.session_id})["status"]
        == "SUCCEEDED"
    )
    path = service._log.root / (original.session_id + "-passive-intent.json")
    path.write_bytes(b"damaged fixture")
    assert (
        perform(service, ACTION, {"session_id": original.session_id})["status"]
        == "FAILED"
    )
    assert (
        service.view()["passive_arm_history"]["pair_status"] == "UNVERIFIED_NO_REPLAY"
    )
