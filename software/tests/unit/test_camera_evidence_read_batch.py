"""Camera-only readback batching; models and fresh NTFS, never device access."""

from dataclasses import replace
import json
from types import SimpleNamespace
from time import perf_counter_ns

import pytest

from rocell.application.commissioning_camera_persistence import (
    M1PhysicalCameraTransaction,
)
from rocell.application.commissioning_m1_persistence import (
    M1CommissioningPersistenceError,
)
from rocell.application.physical_onboarding import (
    EvidenceReference,
    MAX_EVIDENCE_BYTES,
    STAGE_ORDER,
)
from rocell.application.physical_onboarding_leases import LeaseLevel, LeaseSpec
from test_commissioning_camera_persistence import (
    CELL,
    SESSION,
    LEASES,
    STAGE,
    WINDOWS,
    runtime_and_adapter,
    forbid_device_and_process_calls,
)
from test_physical_camera_prerequisites import workspace


@pytest.fixture
def modeled_batch(monkeypatch):
    """Explicitly modeled storage/scope; real batching logic, no IO proof."""
    ref = EvidenceReference(
        "evidence-" + "1" * 64, STAGE_ORDER[0], "1" * 64, "2" * 64, "3" * 64, 4
    )
    snapshot = SimpleNamespace(
        header=SimpleNamespace(cell_id=CELL, session_id=SESSION),
        evidence=(ref,),
    )
    stage_leases = (
        LeaseSpec(LeaseLevel.CELL, CELL),
        LeaseSpec(LeaseLevel.SESSION, SESSION),
    )
    state = dict(
        snapshot=snapshot,
        attempts=1,
        quarantine=1,
        records={},
        snapshots=0,
        audits=0,
        reads=0,
        leases=stage_leases,
        closed=False,
    )
    tx = object.__new__(M1PhysicalCameraTransaction)

    def scope():
        if state["closed"]:
            raise M1CommissioningPersistenceError("MODELED scope ended")

    def current_snapshot():
        state["snapshots"] += 1
        return state["snapshot"]

    def records(*, include_family=False):
        assert include_family is True
        state["audits"] += 1
        return state["records"]

    def payload(reference, observed):
        if reference not in observed.evidence:
            raise M1CommissioningPersistenceError("MODELED missing original reference")
        state["reads"] += 1
        return b"data"

    tx._check_scope, tx.snapshot, tx._audit_records = scope, current_snapshot, records
    tx._read_original_evidence = payload
    tx._attempts = SimpleNamespace(snapshot=lambda: state["attempts"])
    tx._quarantine = SimpleNamespace(snapshot=lambda: state["quarantine"])
    monkeypatch.setattr(type(tx), "held_leases", property(lambda _: state["leases"]))
    return tx, ref, state


@pytest.mark.parametrize("camera_scope", [False, True])
def test_scope_brackets_reads_and_cannot_be_reused(modeled_batch, camera_scope):
    tx, ref, state = modeled_batch
    if camera_scope:
        state["leases"] = LEASES
    with tx._original_evidence_readback(camera_scope=camera_scope) as (snapshot, read):
        assert snapshot is state["snapshot"]
        assert read(ref) == b"data"
        with pytest.raises(M1CommissioningPersistenceError, match="non-nested"):
            with tx._original_evidence_readback(camera_scope=camera_scope):
                pytest.fail("nested scope entered")
    assert state["snapshots"] == state["audits"] == 2
    with pytest.raises(M1CommissioningPersistenceError, match="ended"):
        read(ref)
    # A later batch performs new reads; neither snapshots nor seen IDs persist.
    with tx._original_evidence_readback(camera_scope=camera_scope) as (_, later):
        assert later(ref) == b"data"
    assert state["snapshots"] == state["audits"] == 4


@pytest.mark.parametrize(
    "fault", ["snapshot", "records", "attempts", "quarantine", "leases", "closed"]
)
def test_closing_mutations_reject_even_after_payload_returned(modeled_batch, fault):
    tx, ref, state = modeled_batch
    with pytest.raises(M1CommissioningPersistenceError):
        with tx._original_evidence_readback(camera_scope=False) as (_, read):
            assert read(ref) == b"data"
            if fault == "snapshot":
                state["snapshot"] = SimpleNamespace(changed=True)
            elif fault == "records":
                # Mutate the original mapping, not merely a replacement mapping:
                # the retained canonical bytes must not alias a mutable input.
                state["records"]["MODELED sibling record"] = dict(changed=True)
            elif fault in {"attempts", "quarantine"}:
                state[fault] += 1
            elif fault == "leases":
                state["leases"] = ()
            else:
                state["closed"] = True
    with pytest.raises(M1CommissioningPersistenceError, match="ended"):
        read(ref)
    assert tx._original_readback_active is False


@pytest.mark.parametrize(
    "fault",
    [
        "type",
        "oversize",
        "missing",
        "duplicate",
        "lease-before-read",
        "scope-before-read",
    ],
)
def test_bad_reference_or_lost_ownership_cannot_read(modeled_batch, fault):
    tx, ref, state = modeled_batch
    with pytest.raises(M1CommissioningPersistenceError):
        with tx._original_evidence_readback(camera_scope=False) as (_, read):
            candidate = ref
            if fault == "type":
                candidate = ref.to_dict()
            elif fault == "oversize":
                candidate = replace(ref, payload_bytes=MAX_EVIDENCE_BYTES + 1)
            elif fault == "missing":
                candidate = replace(ref, payload_sha256="f" * 64)
            elif fault == "duplicate":
                assert read(ref) == b"data"
            elif fault == "lease-before-read":
                state["leases"] = ()
            else:
                state["closed"] = True
            read(candidate)
    assert state["reads"] == (1 if fault == "duplicate" else 0)


@pytest.mark.parametrize("scope", [None, 0, 1, "camera", True])
def test_invalid_scope_or_lease_set_fails_before_records(modeled_batch, scope):
    tx, _, state = modeled_batch
    with pytest.raises(M1CommissioningPersistenceError):
        with tx._original_evidence_readback(camera_scope=scope):
            pytest.fail("wrong scope entered")
    assert state["audits"] == state["reads"] == 0


def test_body_exception_is_not_masked_and_invalidates_reader(modeled_batch):
    tx, ref, state = modeled_batch
    sentinel = RuntimeError("MODELED primary validation failure")
    with pytest.raises(RuntimeError) as caught:
        with tx._original_evidence_readback(camera_scope=False) as (_, read):
            state["closed"] = True
            raise sentinel
    assert caught.value is sentinel and state["audits"] == 1
    with pytest.raises(M1CommissioningPersistenceError, match="ended"):
        read(ref)


@WINDOWS
@pytest.mark.parametrize("camera_scope", [False, True])
def test_actual_ntfs_batch_preserves_bytes_with_two_full_audits(
    tmp_path, monkeypatch, camera_scope
):
    runtime, adapter = runtime_and_adapter(tmp_path)
    context = (
        adapter.transaction(LEASES)
        if camera_scope
        else adapter.stage_transaction(
            SESSION,
            expected_challenge_sha256=adapter.verification(SESSION).challenge_sha256,
        )
    )
    with context as tx:
        for index in range(8):
            tx.store_evidence(
                STAGE,
                json.dumps({"MODELED file-only sample": index}).encode(),
                label="camera batch development fixture",
                media_type="application/json",
                captured_at_ns=5000 + index,
                expected_head_sha256=tx.snapshot().head.head_sha256,
            )
        original = tx.snapshot()
        counts = dict(snapshots=0, audits=0)
        snapshot, audit = tx.snapshot, tx._audit_records

        def counted_snapshot():
            counts["snapshots"] += 1
            return snapshot()

        def counted_audit(**kwargs):
            counts["audits"] += 1
            return audit(**kwargs)

        monkeypatch.setattr(tx, "snapshot", counted_snapshot)
        monkeypatch.setattr(tx, "_audit_records", counted_audit)
        single = tx.read_camera_evidence if camera_scope else tx.read_stage_evidence
        start = perf_counter_ns()
        baseline = [single(ref) for ref in original.evidence]
        baseline_ns = perf_counter_ns() - start
        baseline_counts = dict(counts)
        counts.update(snapshots=0, audits=0)
        start = perf_counter_ns()
        with tx._original_evidence_readback(camera_scope=camera_scope) as (
            observed,
            read,
        ):
            candidate = [read(ref) for ref in original.evidence]
        candidate_ns = perf_counter_ns() - start
        assert observed == original and candidate == baseline
        assert counts == dict(snapshots=2, audits=2)
        assert baseline_counts["snapshots"] == len(original.evidence)
        assert baseline_counts["audits"] == (
            len(original.evidence) if camera_scope else 0
        )
        assert snapshot() == original
        (tmp_path / "batch-measurement.json").write_text(
            json.dumps(
                dict(
                    schema="rocell.test_camera_batch_measurement.v1",
                    camera_scope=camera_scope,
                    evidence_count=len(original.evidence),
                    baseline_ns=baseline_ns,
                    candidate_ns=candidate_ns,
                    baseline_calls=baseline_counts,
                    candidate_calls=counts,
                    identical_payloads=True,
                    actual_ntfs=True,
                    physical_authority=False,
                    meaning="One local sample, not full-history speedup or hardware qualification",
                ),
                indent=2,
            )
        )
    assert adapter.verification(SESSION).to_dict()["leases"] == {
        "active_or_stale_owners": [],
        "reconciliation_required": False,
    }


@WINDOWS
@pytest.mark.parametrize("when", ["before-read", "after-read"])
def test_actual_original_corruption_rejects_batch(tmp_path, when):
    _, adapter = runtime_and_adapter(tmp_path)
    with adapter.transaction(LEASES) as tx:
        reference = tx.snapshot().evidence[0]
        payload = (
            tx._session.directory / "evidence" / reference.evidence_id / "payload.bin"
        )
        before = payload.read_bytes()
        with pytest.raises(ValueError):
            with tx._original_evidence_readback(camera_scope=True) as (_, read):
                if when == "after-read":
                    assert read(reference) == before
                # Only a newly created test store is corrupted, never historical data.
                payload.write_bytes(before + b" ")
                if when == "before-read":
                    read(reference)


@WINDOWS
def test_actual_sibling_record_corruption_is_not_hidden_by_same_session(
    workspace, monkeypatch
):
    from rocell.application.commissioning_m1_persistence import (
        _PHYSICAL_USB_IDENTITY_DOMAIN,
    )
    from test_camera_storage_reader_profile import _mixed_history

    _, adapter = _mixed_history(workspace, monkeypatch)
    with adapter.transaction(LEASES) as tx:
        original = tx.snapshot()
        records = tx._audit_records(include_family=True)
        sibling_root = tx._cell_root / _PHYSICAL_USB_IDENTITY_DOMAIN.record_directory
        sibling = next(
            sibling_root / name for name in records if (sibling_root / name).is_file()
        )
        with pytest.raises(ValueError):
            with tx._original_evidence_readback(camera_scope=True) as (_, read):
                read(original.evidence[0])
                sibling.write_bytes(b'{"MODELED_CORRUPTION":true}')
                assert tx.snapshot() == original
