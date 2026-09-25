"""Real local M1 storage, incapable cameras: never enumerate or open hardware."""

from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import threading

import pytest

from rocell.application.commissioning_rehearsal_service import (
    CommissioningRehearsalService,
)
from rocell.application.wizard_actions import WizardError


WORKSPACE = Path(__file__).resolve().parents[3]
pytestmark = pytest.mark.skipif(
    os.name != "nt", reason="Actual M1 publication requires local Windows NTFS"
)


def invoke(
    service: CommissioningRehearsalService, action: str, **values: object
) -> dict:
    inputs = service.bind("rehearsal_" + action, values)
    return service.perform(
        "rehearsal_" + action,
        inputs,
        cancellation=threading.Event(),
        progress=lambda _: None,
    )


@pytest.fixture
def service(tmp_path: Path) -> CommissioningRehearsalService:
    return CommissioningRehearsalService(
        WORKSPACE, tmp_path / "separate-store", source_sha256="a" * 64
    )


def collect(
    service: CommissioningRehearsalService, candidate: str = "synthetic-b0477"
) -> None:
    invoke(service, "collect", operator_id="operator-a", candidate=candidate)
    if service.blocked_reason("rehearsal_camera_settings") is None:
        assert service.blocked_reason("rehearsal_camera_campaign") is not None
        invoke(service, "camera_settings", brightness_offset=0)


def assess_review(service: CommissioningRehearsalService) -> None:
    invoke(service, "assess")
    invoke(service, "review", reviewer_id="reviewer-b", accept_assessment=True)


def through_identity(service: CommissioningRehearsalService) -> None:
    invoke(service, "initialize")
    for _ in range(4):
        collect(service)
        assess_review(service)


def test_construction_view_bind_have_no_storage_or_workers(
    service: CommissioningRehearsalService,
) -> None:
    assert not service.directory.exists()
    before = service.view()
    before["status"] = "FORGED"
    assert service.view()["status"] == "NOT_STARTED"
    service.bind("rehearsal_initialize", {})
    assert not service.directory.exists()
    with pytest.raises(WizardError, match="Initialize"):
        service.bind("rehearsal_collect", {})


def test_real_store_has_immutable_rehearsal_mode_and_rejects_initialization_replay(
    service: CommissioningRehearsalService,
) -> None:
    result = invoke(service, "initialize")
    assert result["status"] == "SUCCEEDED"
    assert result["device_open_count"] == 0
    assert service._store.snapshot(service.session_id).header.mode == "REHEARSAL"
    assert service.view()["stage"] == "workspace_sources"
    with pytest.raises(WizardError, match="already attempted"):
        invoke(service, "initialize")


# Full qualified-NTFS stage progression and retained camera datasets take minutes.
@pytest.mark.slow
def test_complete_first_six_stage_workflow_uses_real_ledgers_and_stops_before_optics(
    service: CommissioningRehearsalService,
) -> None:
    through_identity(service)
    assert service.view()["selected_camera"]["model"] == "B0477"
    for index in range(2):
        collect(service)
        assert service.latest_preview() is None
        assert service.view().get("capture_dataset") is None
        assert service.blocked_reason("rehearsal_assess") is not None
        result = invoke(service, "camera_campaign", frame_count=1, fault="none")
        assert result["status"] == "SUCCEEDED"
        assert service.latest_preview().startswith(b"\x89PNG")
        assert service.view()["capture_dataset"]["physical_authority"] is False
        assert service.blocked_reason("rehearsal_camera_settings") is not None
        assert service.view()["attempt_event_count"] == 5 * (index + 1)
        assert not service.view()["unresolved_attempt_ids"]
        assert service.blocked_reason("rehearsal_camera_campaign") is not None
        assess_review(service)
    view = service.view()
    assert [stage["state"] for stage in view["stages"][:6]] == ["PASS"] * 6
    assert all(stage["state"] == "PENDING" for stage in view["stages"][6:])
    assert view["stage"] == "optics_intrinsics"
    assert service.blocked_reason("rehearsal_collect") is None
    assert view["physical_authority"] is False
    snapshot = service._store.snapshot(service.session_id)
    assert len(snapshot.committed_events) == 18
    assert all(
        event.detail_code.startswith("REHEARSAL_")
        for event in snapshot.committed_events
    )
    assert not snapshot.diagnostic_complete


@pytest.mark.slow
def test_wrong_camera_is_assessed_blocked_not_overridden_by_review(
    service: CommissioningRehearsalService,
) -> None:
    invoke(service, "initialize")
    for _ in range(3):
        collect(service)
        assess_review(service)
    collect(service, "synthetic-wrong-camera")
    invoke(service, "assess")
    assert service.view()["assessment"]["outcome"] == "BLOCKED"
    invoke(service, "review", reviewer_id="reviewer-b", accept_assessment=True)
    assert service.view()["stage_state"] == "BLOCKED"
    assert service.view()["selected_camera"] is None
    prior_evidence = service._store.snapshot(service.session_id).evidence
    collect(service)
    assess_review(service)
    assert len(service._store.snapshot(service.session_id).evidence) > len(
        prior_evidence
    )
    assert service.view()["selected_camera"]["candidate_id"] == "synthetic-b0477"


@pytest.mark.slow
def test_binary_dataset_tamper_after_assessment_prevents_review(
    service: CommissioningRehearsalService,
) -> None:
    """An unchanged M1 assessment cannot accept changed standalone pixel bytes."""
    through_identity(service)
    collect(service)
    invoke(service, "camera_campaign", frame_count=1, fault="none")
    invoke(service, "assess")
    dataset = Path(service.view()["capture_dataset"]["dataset"]["path"])
    chunk = next((dataset / "chunks").glob("*.bin"))
    with chunk.open("r+b") as stream:
        original = stream.read(1)
        stream.seek(0)
        stream.write(bytes([original[0] ^ 1]))
    with pytest.raises(ValueError):
        invoke(service, "review", reviewer_id="reviewer-b", accept_assessment=True)
    assert service.view()["status"] == "HELD"
    assert service.latest_preview() is None
    assert service.view()["capture_dataset"] is None
    assert (
        service._store.snapshot(service.session_id).next_action.stage_state.value
        == "REVIEW_PENDING"
    )
    assert service.blocked_reason("rehearsal_camera_campaign") is not None


@pytest.mark.slow
@pytest.mark.parametrize("fault", ["identity-mismatch", "cleanup-uncertain"])
def test_camera_uncertainty_latches_real_cell_quarantine(
    service: CommissioningRehearsalService, fault: str
) -> None:
    through_identity(service)
    collect(service)
    result = invoke(service, "camera_campaign", frame_count=1, fault=fault)
    assert result["status"] == "FAILED"
    assert service.view()["quarantined"] is True
    assert service.view()["status"] == "HELD"
    assert service.blocked_reason("rehearsal_assess") is not None
    invoke(service, "refresh")
    assert service.view()["quarantined"] is True
    verification = service._store.verification(service.session_id)
    assert verification.quarantine_count >= 1


def test_review_binding_distinct_actor_stale_view_and_no_review_replay(
    service: CommissioningRehearsalService,
) -> None:
    invoke(service, "initialize")
    collect(service)
    invoke(service, "assess")
    with pytest.raises(WizardError, match="differ"):
        service.bind(
            "rehearsal_review", {"reviewer_id": "operator-a", "accept_assessment": True}
        )
    prepared = service.bind(
        "rehearsal_review", {"reviewer_id": "reviewer-b", "accept_assessment": True}
    )
    forged = {**prepared, "_view_sha256": "0" * 64}
    with pytest.raises(WizardError, match="changed"):
        service.perform(
            "rehearsal_review",
            forged,
            cancellation=threading.Event(),
            progress=lambda _: None,
        )
    service.perform(
        "rehearsal_review",
        prepared,
        cancellation=threading.Event(),
        progress=lambda _: None,
    )
    with pytest.raises(WizardError, match="changed"):
        service.perform(
            "rehearsal_review",
            prepared,
            cancellation=threading.Event(),
            progress=lambda _: None,
        )


def test_cancel_before_mutation_is_inert(
    service: CommissioningRehearsalService,
) -> None:
    values = service.bind("rehearsal_initialize", {})
    cancelled = threading.Event()
    cancelled.set()
    with pytest.raises(WizardError, match="Cancelled"):
        service.perform(
            "rehearsal_initialize",
            values,
            cancellation=cancelled,
            progress=lambda _: None,
        )
    assert not service.directory.exists()


def test_cancel_during_progress_is_inert(
    service: CommissioningRehearsalService,
) -> None:
    values = service.bind("rehearsal_initialize", {})
    cancelled = threading.Event()
    with pytest.raises(WizardError, match="progress"):
        service.perform(
            "rehearsal_initialize",
            values,
            cancellation=cancelled,
            progress=lambda _: cancelled.set(),
        )
    assert not service.directory.exists()


def test_refresh_never_rebases_pending_review_after_external_evidence_change(
    service: CommissioningRehearsalService,
) -> None:
    invoke(service, "initialize")
    collect(service)
    invoke(service, "assess")
    before = service.view()
    with service._store.stage_transaction(
        service.session_id, expected_challenge_sha256=before["challenge_sha256"]
    ) as tx:
        snapshot = tx.snapshot()
        tx.store_evidence(
            snapshot.next_action.stage,
            b'{"note":"external fixture"}',
            label="External test evidence",
            media_type="application/json",
            captured_at_ns=service._time(snapshot),
            expected_head_sha256=snapshot.head.head_sha256,
        )
    invoke(service, "refresh")
    assert service.view()["status"] == "HELD"
    assert service.view()["assessment"] is None
    assert service.blocked_reason("rehearsal_review") is not None
    assert (
        service._store.snapshot(service.session_id).next_action.stage_state.value
        == "REVIEW_PENDING"
    )


@pytest.mark.parametrize("actor", ["", "../operator", "\noperator", "a" * 65, True])
def test_actor_is_bounded_server_side(
    service: CommissioningRehearsalService, actor: object
) -> None:
    invoke(service, "initialize")
    with pytest.raises(WizardError, match="identifier"):
        service.bind(
            "rehearsal_collect", {"operator_id": actor, "candidate": "synthetic-b0477"}
        )
