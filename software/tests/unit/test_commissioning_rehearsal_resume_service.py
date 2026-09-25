"""Resume the same real NTFS journal through service APIs, with no device I/O."""

from pathlib import Path
import os
import threading

import pytest

from rocell.application.commissioning_rehearsal_service import (
    CommissioningRehearsalService,
)
from rocell.application.wizard_actions import WizardError
from test_commissioning_rehearsal_service import invoke, collect, through_identity

WORKSPACE = Path(__file__).resolve().parents[3]
pytestmark = pytest.mark.skipif(
    os.name != "nt", reason="Actual M1 requires Windows NTFS"
)


def create(root: Path, name: str, source: str = "a") -> CommissioningRehearsalService:
    return CommissioningRehearsalService(
        WORKSPACE, root / name, source_sha256=source * 64
    )


def discover(service):
    invoke(service, "discover")
    return service.view()["discovery"]["choices"]


def test_discovery_is_explicit_and_does_not_create_a_session(tmp_path):
    value = create(tmp_path, "uncreated")
    assert value.view()["discovery"]["status"] == "NOT_DISCOVERED"
    assert value.blocked_reason("rehearsal_reopen")
    value.bind("rehearsal_discover", {})
    assert list(tmp_path.iterdir()) == []
    assert discover(value) == []
    assert not value.directory.exists()
    assert value.view()["status"] == "NOT_STARTED"


def test_reopen_restores_exact_pending_review_and_continues_original_journal(tmp_path):
    original = create(tmp_path, "original")
    invoke(original, "initialize")
    collect(original)
    invoke(original, "assess")
    before = original.view()
    resumed = create(tmp_path, "unused-new")
    choice = discover(resumed)[0]
    assert not resumed.directory.exists()
    bound = resumed.bind("rehearsal_reopen", {"choice_id": choice["choice_id"]})
    assert resumed.view()["status"] == "NOT_STARTED"
    assert not resumed.directory.exists()
    result = resumed.perform(
        "rehearsal_reopen",
        bound,
        cancellation=threading.Event(),
        progress=lambda _: None,
    )
    assert result["status"] == "SUCCEEDED"
    after = resumed.view()
    assert after["session_origin"] == "REOPENED_EXISTING"
    assert (resumed.directory, resumed.cell_id, resumed.session_id) == (
        original.directory,
        original.cell_id,
        original.session_id,
    )
    assert after["assessment"] == before["assessment"]
    assert after["journal_head_sha256"] == before["journal_head_sha256"]
    assert after["operator_id"] == "operator-a"
    assert after["reopen_result"]["disposition"] == "REVIEW_PENDING"
    assert resumed.latest_preview() is None
    assert not (tmp_path / "unused-new").exists()
    with pytest.raises(WizardError, match="differ"):
        resumed.bind(
            "rehearsal_review", {"reviewer_id": "operator-a", "accept_assessment": True}
        )
    invoke(resumed, "review", reviewer_id="new-reviewer", accept_assessment=True)
    assert resumed.view()["stage"] == "static_camera_contract"
    assert original._store.snapshot(original.session_id).stages[0].state.value == "PASS"
    assert resumed.blocked_reason("rehearsal_reopen")
    assert resumed.blocked_reason("rehearsal_discover")
    assert resumed.blocked_reason("rehearsal_initialize")
    # The old service cannot silently accept this other process's journal change.
    invoke(original, "refresh")
    assert original.view()["status"] == "HELD"
    assert original.view()["assessment"] is None


def test_held_choice_is_not_replayed_or_silently_replaced(tmp_path):
    wrong = create(tmp_path, "source-b", "b")
    invoke(wrong, "initialize")
    resumed = create(tmp_path, "unused-new")
    choice = discover(resumed)[0]
    assert choice["source_matches"] is False
    result = invoke(resumed, "reopen", choice_id=choice["choice_id"])
    assert result["status"] == "FAILED"
    assert resumed.view()["reopen_result"]["status"] == "READ_ONLY_HOLD"
    assert resumed._store is None
    assert resumed.view()["reopen_result"]["reasons"][0]["code"] == "SOURCE_DRIFT"
    assert not resumed.directory.exists()
    discover(resumed)
    assert resumed.reopen_choices() == []
    with pytest.raises(WizardError):
        invoke(resumed, "reopen", choice_id=choice["choice_id"])
    with pytest.raises(WizardError):
        invoke(resumed, "initialize")


def test_cancelled_open_does_not_attach_or_replay(tmp_path, monkeypatch):
    original = create(tmp_path, "original")
    invoke(original, "initialize")
    resumed = create(tmp_path, "unused-new")
    choice = discover(resumed)[0]
    bound = resumed.bind("rehearsal_reopen", {"choice_id": choice["choice_id"]})
    cancel = threading.Event()
    open_store = resumed._registry.open

    def cancel_after_open(*args, **kwargs):
        result = open_store(*args, **kwargs)
        cancel.set()
        return result

    monkeypatch.setattr(resumed._registry, "open", cancel_after_open)
    result = resumed.perform(
        "rehearsal_reopen", bound, cancellation=cancel, progress=lambda _: None
    )
    assert result["status"] == "FAILED"
    assert resumed._store is None
    assert resumed.directory.name == "unused-new"
    assert (
        resumed.view()["reopen_result"]["reasons"][0]["code"]
        == "OPEN_CANCELLED_NOT_ATTACHED"
    )
    assert not resumed.directory.exists()


def test_opaque_choice_and_cached_discovery_are_not_caller_authority(tmp_path):
    original = create(tmp_path, "original")
    invoke(original, "initialize")
    resumed = create(tmp_path, "unused-new")
    choices = discover(resumed)
    choices[0]["discovery_sha256"] = "0" * 64
    assert resumed.view()["discovery"]["choices"][0]["discovery_sha256"] != "0" * 64
    with pytest.raises(WizardError, match="server-issued"):
        resumed.bind("rehearsal_reopen", {"choice_id": str(original.directory)})
    values = resumed.bind("rehearsal_reopen", {"choice_id": choices[0]["choice_id"]})
    values["_discovery_sha256"] = "0" * 64
    result = resumed.perform(
        "rehearsal_reopen",
        values,
        cancellation=threading.Event(),
        progress=lambda _: None,
    )
    assert result["status"] == "FAILED"
    assert resumed.view()["reopen_result"]["reasons"][0]["code"] == "STALE_DISCOVERY"


# Real first-four-stage setup, binary capture and repeated original-store opens.
@pytest.mark.slow
def test_legacy_camera_wait_requires_new_operator_and_can_capture_after_reopen(
    tmp_path,
):
    from rocell.application.physical_onboarding_v2 import V2StageState

    original = create(tmp_path, "legacy-wait")
    through_identity(original)
    # Model the older persisted stage opening, which did not retain an operator.
    with original._transaction() as tx:
        snapshot = tx.snapshot()
        tx.commit_stage_state(
            snapshot.next_action.stage,
            V2StageState.WAITING_OPERATOR,
            occurred_at_ns=original._time(snapshot),
            detail_code="REHEARSAL_STAGE_OPENED",
            expected_head_sha256=snapshot.head.head_sha256,
        )
    original._refresh()
    resumed = create(tmp_path, "unused-new")
    choice = discover(resumed)[0]
    invoke(resumed, "reopen", choice_id=choice["choice_id"])
    assert resumed.view()["operator_id"] is None
    assert resumed.blocked_reason("rehearsal_camera_settings")
    assert resumed.blocked_reason("rehearsal_camera_campaign")
    invoke(resumed, "record_operator", operator_id="arrival-operator")
    assert resumed.blocked_reason("rehearsal_record_operator")
    invoke(resumed, "camera_settings", brightness_offset=-8)
    invoke(resumed, "camera_campaign", frame_count=1, fault="none")
    invoke(resumed, "assess")
    assert resumed.view()["assessment"]["outcome"] == "PASS"
    # Reopening a pending camera review retains metadata, but never loads pixels.
    again = create(tmp_path, "second-unused")
    choice = discover(again)[0]
    invoke(again, "reopen", choice_id=choice["choice_id"])
    assert again.view()["capture_dataset"] == resumed.view()["capture_dataset"]
    assert again.latest_preview() is None
    invoke(again, "review", reviewer_id="arrival-reviewer", accept_assessment=True)
    assert again.view()["stage"] == "camera_frame_freshness"
    assert again.directory == original.directory


def test_another_verified_choice_can_be_opened_after_a_read_only_hold(tmp_path):
    bad = create(tmp_path, "old-source", "b")
    good = create(tmp_path, "current-source")
    invoke(bad, "initialize")
    invoke(good, "initialize")
    resumed = create(tmp_path, "unused-new")
    choices = discover(resumed)
    invalid = next(item for item in choices if not item["source_matches"])
    valid = next(item for item in choices if item["source_matches"])
    assert (
        invoke(resumed, "reopen", choice_id=invalid["choice_id"])["status"] == "FAILED"
    )
    assert (
        invoke(resumed, "reopen", choice_id=valid["choice_id"])["status"] == "SUCCEEDED"
    )
    assert resumed.directory == good.directory
    assert not (tmp_path / "unused-new").exists()
