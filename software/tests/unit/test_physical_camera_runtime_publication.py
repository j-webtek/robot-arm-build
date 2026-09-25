"""Late publication joins for actual file reports; never device qualification.

Reuse the independent installed-file fixture with a modeled workspace fingerprint.
The fixture forbids process, device and M1 operations; faults below change only
in-memory application state or isolated diagnostic logging.
"""

from pathlib import Path
import threading

import pytest

from rocell.application.wizard_actions import WizardError
from test_wizard_physical_camera_runtime_review import (
    INSPECT,
    INSPECT_INPUT,
    REVIEW,
    REVIEW_INPUT,
    action,
    runtime_view,
    setup,
    successful,
)


def test_authoritative_review_rejects_case_only_operator_change(setup):
    service, calls, *_ = setup()
    successful(service, INSPECT, INSPECT_INPUT)
    owner = service._physical_camera
    context = owner.runtime_context_sha256()
    owner.begin_runtime_action(REVIEW, context)
    with pytest.raises(WizardError, match="different from"):
        owner.perform_runtime_action(
            REVIEW,
            expected_context_sha256=context,
            actor_id=INSPECT_INPUT["operator_id"].upper(),
            operation_id="operation-" + "1" * 32,
            cancellation=threading.Event(),
            progress=lambda _: None,
        )
    assert owner.runtime_view()["review"] is None
    assert len(calls) == 1


def test_review_and_cached_projection_need_no_filesystem(setup, monkeypatch):
    service, calls, *_ = setup()
    successful(service, INSPECT, INSPECT_INPUT)
    owner = service._physical_camera
    context = owner.runtime_context_sha256()
    owner.begin_runtime_action(REVIEW, context)

    def forbidden(*_a, **_k):
        pytest.fail("Pure review/projection attempted filesystem access")

    with monkeypatch.context() as guard:
        for method in ("open", "stat", "lstat", "mkdir"):
            guard.setattr(Path, method, forbidden)
        result = owner.perform_runtime_action(
            REVIEW,
            expected_context_sha256=context,
            actor_id=REVIEW_INPUT["reviewer_id"],
            operation_id="operation-" + "2" * 32,
            cancellation=threading.Event(),
            progress=lambda _: pytest.fail("Pure review emitted file progress"),
        )
        owner.validate_runtime_publication("operation-" + "2" * 32, result)
        assert owner.runtime_view()["publication"]["status"] == "PENDING"
        assert owner.view()["runtime_inspection"]["review"] is None
    # No simulated outer log: the direct staged review must remain unpublished.
    assert len(calls) == 1
    assert owner.retained_runtime_diagnostics()["review"] is None


def test_withdrawal_during_inspection_retains_returned_original_only_as_history(setup):
    service, calls, reports, hook, *_ = setup()
    hook["after"] = lambda *_: service._physical_camera.invalidate_runtime()
    result = action(service, INSPECT, INSPECT_INPUT)
    assert result["status"] == "FAILED"
    assert runtime_view(service)["status"] == "HISTORICAL_HELD"
    assert (
        service._physical_camera.retained_runtime_diagnostics()["inspection"]
        == reports[0].to_dict()
    )
    assert len(calls) == 1


@pytest.mark.parametrize("fault", ["in_place_result", "context", "late_stop"])
def test_final_publication_rechecks_original_result_and_current_context(
    setup, monkeypatch, fault
):
    service, calls, reports, *_ = setup()
    validate = service._validated_result

    def altered(action_id, value):
        if action_id != INSPECT:
            return validate(action_id, value)
        if fault == "in_place_result":
            # Even an in-place mutation, invisible to original != clean, cannot
            # replace the independently retained exact report binding.
            value["steps"][0]["report"]["inspection_sha256"] = "f" * 64
        elif fault == "context":
            service._physical_camera.source_sha256 = "b" * 64
        else:
            service._cancel.set()
        return validate(action_id, value)

    monkeypatch.setattr(service, "_validated_result", altered)
    result = action(service, INSPECT, INSPECT_INPUT)
    assert result["status"] in {"FAILED", "CANCELLED"}
    assert runtime_view(service)["status"] == "HISTORICAL_HELD"
    retained = service._physical_camera.retained_runtime_diagnostics()
    assert retained["inspection"] == reports[0].to_dict()
    assert retained["inspection_sha256"] == reports[0].sha256
    assert retained["review"] is None and len(calls) == 1


def test_failed_new_inspection_intent_keeps_last_logged_review_as_history(
    setup, monkeypatch
):
    service, calls, reports, *_ = setup()
    successful(service, INSPECT, INSPECT_INPUT)
    successful(service, REVIEW, REVIEW_INPUT)
    old_review = runtime_view(service)["review"]
    append = service._log.append

    def fail(kind, details):
        if kind == "ACTION_EXECUTED":
            raise OSError("Isolated intent-log failure")
        return append(kind, details)

    monkeypatch.setattr(service._log, "append", fail)
    result = action(service, INSPECT, INSPECT_INPUT)
    assert result["status"] == "FAILED"
    state = runtime_view(service)
    assert state["status"] == "HISTORICAL_HELD"
    assert state["review"] == old_review
    assert state["inspection"]["report_sha256"] == reports[0].sha256
    assert len(calls) == 1
