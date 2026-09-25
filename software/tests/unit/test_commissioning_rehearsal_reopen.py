"""Existing real NTFS sessions only; no enumeration, activation or replay."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import threading
from typing import Any

import pytest

import rocell.application.commissioning_rehearsal_reopen as reopen_module
from rocell.application.commissioning_rehearsal_reopen import (
    KnownRehearsalRoot,
    RehearsalReopenError,
    RehearsalReopenRegistry,
)
from rocell.application.commissioning_rehearsal_service import (
    CommissioningRehearsalService,
)
from rocell.application.physical_onboarding_stage_catalog import (
    load_physical_onboarding_stage_catalog,
)
from rocell.application.physical_onboarding_v2 import V2StageState


WORKSPACE = Path(__file__).resolve().parents[3]
SOURCE = "a" * 64
CATALOG = load_physical_onboarding_stage_catalog(WORKSPACE).source_sha256
NTFS = pytest.mark.skipif(
    os.name != "nt", reason="Actual qualified M1 requires Windows NTFS"
)


def invoke(service: CommissioningRehearsalService, action: str, **values: Any) -> dict:
    return service.perform(
        "rehearsal_" + action,
        service.bind("rehearsal_" + action, values),
        cancellation=threading.Event(),
        progress=lambda _: None,
    )


def registry(
    parent: Path, *, source: str = SOURCE, catalog: str = CATALOG
) -> RehearsalReopenRegistry:
    return RehearsalReopenRegistry(
        (KnownRehearsalRoot("assigned", parent),),
        workspace_source_sha256=source,
        catalog_sha256=catalog,
    )


def open_existing(
    service: CommissioningRehearsalService,
    selected: RehearsalReopenRegistry | None = None,
):
    selected = selected or registry(service.directory.parent)
    discovery = selected.discover()
    assert not discovery.issues, discovery.issues
    assert len(discovery.choices) == 1
    choice = discovery.choices[0]
    return selected.open(
        choice.choice_id,
        expected_discovery_sha256=choice.discovery_sha256,
        admission_facts=service._facts,
    )


def durable_files(directory: Path) -> dict[str, str]:
    # Requalification and lease-owner metadata are explicit opening effects.
    # Original session evidence, journals, cells and attempt files must not change.
    return {
        str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in directory.rglob("*")
        if path.is_file() and not path.name.startswith("lease-")
    }


@pytest.fixture
def service(tmp_path: Path) -> CommissioningRehearsalService:
    return CommissioningRehearsalService(
        WORKSPACE, tmp_path / "prior-launch", source_sha256=SOURCE
    )


def test_constructor_view_unknown_selection_never_qualify_or_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Unexpected qualified-storage activation")

    monkeypatch.setattr(reopen_module.PhysicalOnboardingM1Runtime, "open", forbidden)
    selected = registry(tmp_path / "missing")
    assert selected.view().choices == ()
    result = selected.open(
        "C:\\arbitrary-path",
        expected_discovery_sha256="0" * 64,
        admission_facts=forbidden,
    )
    assert result.status == "READ_ONLY_HOLD"
    assert result.reasons[0].code == "UNKNOWN_CHOICE"
    assert not (tmp_path / "missing").exists()
    assert selected.discover().issues[0].code == "ROOT_NOT_CREATED"


def test_registry_and_discovery_bounds_are_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(RehearsalReopenError):
        KnownRehearsalRoot("../escape", tmp_path)
    with pytest.raises(RehearsalReopenError):
        KnownRehearsalRoot("valid", Path("relative"))
    monkeypatch.setattr(reopen_module, "MAX_STORES_PER_ROOT", 2)
    for index in range(3):
        (tmp_path / f"store-{index}").mkdir()
    result = registry(tmp_path).discover()
    assert result.choices == ()
    assert result.issues[0].code == "DISCOVERY_LIMIT"


@NTFS
def test_discovery_is_read_only_and_reopens_same_empty_session(
    service: CommissioningRehearsalService, monkeypatch: pytest.MonkeyPatch
) -> None:
    invoke(service, "initialize")
    selected = registry(service.directory.parent)
    before = durable_files(service.directory)
    original = reopen_module.PhysicalOnboardingM1Runtime.open
    monkeypatch.setattr(
        reopen_module.PhysicalOnboardingM1Runtime,
        "open",
        lambda *args, **kwargs: pytest.fail("Discovery qualified storage"),
    )
    choice = selected.discover().choices[0]
    assert durable_files(service.directory) == before
    assert choice.session_id == service.session_id
    monkeypatch.setattr(reopen_module.PhysicalOnboardingM1Runtime, "open", original)
    result = open_existing(service, selected)
    assert result.status == "OPENED", result.reasons
    assert result.restored.session_id == service.session_id
    assert result.restored.disposition == "DUE_STAGE"
    assert result.restored.stage_state is V2StageState.PENDING
    assert result.restored.operator_id is None
    assert result.store is not None
    assert durable_files(service.directory) == before


@NTFS
@pytest.mark.parametrize("assessed", [False, True])
def test_restores_exact_receipt_operator_and_pending_assessment(
    service: CommissioningRehearsalService, assessed: bool
) -> None:
    invoke(service, "initialize")
    invoke(service, "collect", operator_id="operator-a", candidate="synthetic-b0477")
    if assessed:
        invoke(service, "assess")
    before = durable_files(service.directory)
    result = open_existing(service)
    assert result.status == "OPENED", result.reasons
    restored = result.restored
    assert restored.operator_id == "operator-a"
    assert restored.receipt.document() == service._receipt
    assert restored.receipt_reference == service._receipt_reference
    assert restored.disposition == ("REVIEW_PENDING" if assessed else "RECEIPT_READY")
    assert (
        restored.assessment.document() if restored.assessment else None
    ) == service._assessment
    assert restored.journal_head_sha256 == service.view()["journal_head_sha256"]
    assert (
        restored.evidence_inventory_sha256
        == service.view()["evidence_inventory_sha256"]
    )
    assert durable_files(service.directory) == before


@NTFS
def test_source_catalog_and_selection_drift_hold(
    service: CommissioningRehearsalService,
) -> None:
    invoke(service, "initialize")
    invoke(service, "collect", operator_id="operator-a", candidate="synthetic-b0477")
    changed = registry(service.directory.parent, source="b" * 64)
    assert open_existing(service, changed).reasons[0].code == "SOURCE_DRIFT"
    changed_catalog = registry(service.directory.parent, catalog="b" * 64)
    assert (
        open_existing(service, changed_catalog).reasons[0].code
        == "CATALOG_OR_CELL_DRIFT"
    )
    selected = registry(service.directory.parent)
    choice = selected.discover().choices[0]
    result = selected.open(
        choice.choice_id,
        expected_discovery_sha256="0" * 64,
        admission_facts=service._facts,
    )
    assert result.reasons[0].code == "STALE_DISCOVERY"


@NTFS
def test_prior_wait_without_receipt_does_not_invent_operator(
    service: CommissioningRehearsalService,
) -> None:
    invoke(service, "initialize")
    # The historical durable boundary after stage-open but before receipt write.
    with service._transaction() as tx:
        snapshot = tx.snapshot()
        tx.commit_stage_state(
            snapshot.next_action.stage,
            V2StageState.WAITING_OPERATOR,
            occurred_at_ns=service._time(snapshot),
            detail_code="REHEARSAL_STAGE_OPENED",
            expected_head_sha256=snapshot.head.head_sha256,
        )
    result = open_existing(service)
    assert result.status == "OPENED", result.reasons
    assert result.restored.disposition == "WAITING_NO_RECEIPT"
    assert result.restored.receipt is result.restored.operator_id is None


@NTFS
def test_orphan_assessment_and_corrupt_bytes_hold(
    service: CommissioningRehearsalService,
) -> None:
    invoke(service, "initialize")
    invoke(service, "collect", operator_id="operator-a", candidate="synthetic-b0477")
    with service._transaction() as tx:
        service._store_json(
            tx,
            tx.snapshot().next_action.stage,
            {
                "schema": "unrecognized",
                "composition": "HARDWARE_INCAPABLE_REHEARSAL",
                "session_id": service.session_id,
                "stage": tx.snapshot().next_action.stage.value,
            },
            "Unrecognized retained package",
        )
    result = open_existing(service)
    assert result.status == "READ_ONLY_HOLD"
    assert result.reasons[0].code == "UNKNOWN_REHEARSAL_EVIDENCE"
    payload = next(service.directory.glob("onboarding-*/evidence/*/payload.bin"))
    payload.write_bytes(b"corrupt fixture")
    assert open_existing(service).status == "READ_ONLY_HOLD"


# Full first-four-stage NTFS progression plus capture and repeated binary audits.
@pytest.mark.slow
@NTFS
def test_restores_camera_operator_settings_review_and_rechecks_binary_provenance(
    service: CommissioningRehearsalService,
) -> None:
    invoke(service, "initialize")
    for _ in range(4):
        invoke(
            service, "collect", operator_id="operator-a", candidate="synthetic-b0477"
        )
        invoke(service, "assess")
        invoke(service, "review", reviewer_id="reviewer-b", accept_assessment=True)
    invoke(service, "collect", operator_id="camera-operator")
    waiting = open_existing(service)
    assert waiting.status == "OPENED", waiting.reasons
    assert waiting.restored.disposition == "WAITING_NO_RECEIPT"
    assert waiting.restored.operator_id == "camera-operator"
    assert waiting.restored.selected_camera.document()["candidate"] == service._selected
    invoke(service, "camera_settings", brightness_offset=12)
    configured = open_existing(service)
    assert configured.status == "OPENED", configured.reasons
    assert configured.restored.camera_settings.document() == service._camera_settings
    invoke(service, "camera_campaign", frame_count=1, fault="none")
    invoke(service, "assess")
    restored = open_existing(service)
    assert restored.status == "OPENED", restored.reasons
    assert restored.restored.disposition == "REVIEW_PENDING"
    assert (
        restored.restored.latest_capture.document()["capture_dataset"]
        == service._latest_capture
    )
    assert restored.restored.assessment.document() == service._assessment
    # An inner dataset can still be intact while its separately retained source
    # envelope is corrupted. Pending review must verify both before reopening.
    envelope = Path(service._latest_capture["envelope_path"])
    envelope.write_bytes(b"corrupted fixture provenance")
    result = open_existing(service)
    assert result.status == "READ_ONLY_HOLD"
    assert result.store is None and result.restored is None


@NTFS
@pytest.mark.parametrize(
    "flag,code",
    [
        ("quarantined", "CELL_QUARANTINED"),
        ("unresolved_attempt_ids", "UNRESOLVED_ATTEMPTS"),
        ("session_reconciliation_required", "RECONCILIATION_REQUIRED"),
    ],
)
def test_retained_uncertainty_blocks_before_any_stage_transaction(
    service: CommissioningRehearsalService,
    monkeypatch: pytest.MonkeyPatch,
    flag: str,
    code: str,
) -> None:
    from dataclasses import replace

    invoke(service, "initialize")
    original = reopen_module.M1CommissioningPersistence.verification

    def uncertainty(adapter, session_id):
        value = ("unresolved-attempt",) if flag == "unresolved_attempt_ids" else True
        return replace(original(adapter, session_id), **{flag: value})

    monkeypatch.setattr(
        reopen_module.M1CommissioningPersistence, "verification", uncertainty
    )
    monkeypatch.setattr(
        reopen_module.M1CommissioningPersistence,
        "stage_transaction",
        lambda *args, **kwargs: pytest.fail("Held state entered a transaction"),
    )
    result = open_existing(service)
    assert result.status == "READ_ONLY_HOLD"
    assert result.reasons[0].code == code


def test_store_preflight_counts_empty_directories_and_rejects_links(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(reopen_module, "MAX_STORE_FILES", 3)
    for name in ("first", "second"):
        directory = tmp_path / name
        directory.mkdir()
        (directory / "child").mkdir()
    with pytest.raises(RehearsalReopenError, match="total file/directory"):
        reopen_module._preflight_store(tmp_path)
