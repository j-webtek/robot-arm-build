"""Fresh original observations, not cross-boundary snapshot caching.

Uses fresh isolated NTFS storage and explicitly modeled zero-I/O prerequisite
subjects. No native/device/CIM helper or process is executed. The modeled cost
assertions count full V2 loads; they do not claim measured production speedups.
"""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from rocell.application.cell_commissioning_coordinator import (
    CommissioningCoordinatorError,
    RegisteredActionRequest,
    USB_IDENTITY_ACTION_ID,
)
from rocell.application.commissioning_m1_persistence import (
    M1CommissioningPersistenceError,
    _M1CoordinatorTransaction,
)
from rocell.application.commissioning_usb_identity_persistence import (
    M1PhysicalUsbIdentityTransaction,
)
from rocell.application.physical_onboarding import EvidenceReference
from rocell.application.physical_onboarding_durability import (
    canonical_bytes,
    canonical_sha256,
)
from rocell.application.physical_onboarding_m1 import PhysicalOnboardingM1Runtime
from rocell.application.physical_onboarding_quarantine import (
    PhysicalOnboardingQuarantineLedger,
)
from rocell.providers.windows.usb_identity_protocol import canonical as usb_canonical

from test_commissioning_usb_identity import (
    CELL,
    LEASES,
    SESSION,
    STAGE,
    WINDOWS,
    actual_request,
    actual_usb_fixture,
    no_device_calls,
    usb_core,
)
from test_m1_fresh_snapshot_open import (
    add_modeled_zero_io_intent,
    count_loads,
)
from test_physical_onboarding_m1 import _runtime


pytestmark = WINDOWS


@pytest.fixture(scope="module")
def original_pair(tmp_path_factory):
    runtime = _runtime(tmp_path_factory.mktemp("fresh-usb-observation"))
    runtime.create_session("session-1", created_at_ns=2000)
    return runtime._verify_with_snapshot("session-1")


def scoped_pair(callback):
    """Only the hook's scope is modeled; its typed originals remain unchanged."""
    tx = object.__new__(M1PhysicalUsbIdentityTransaction)
    tx._active = True
    tx._held = SimpleNamespace(closed=False)
    tx._guard = lambda: None
    tx._fresh_snapshot_verification = callback
    return tx


def test_pair_exact_original_hashes_and_public_wrapper(original_pair):
    snapshot, verified = original_pair
    rows = [ref.to_dict() for ref in snapshot.evidence]
    assert canonical_bytes(rows) == usb_canonical(rows) + b"\n"
    assert verified.evidence_inventory_sha256 == canonical_sha256(rows)
    tx = scoped_pair(lambda: original_pair)
    assert tx._admission_observation() == original_pair


@pytest.mark.parametrize(
    "field,value",
    [
        ("session_id", "another-session"),
        ("session_header_sha256", "1" * 64),
        ("session_head_sha256", "2" * 64),
        ("qualification_anchor_sha256", "3" * 64),
        ("session_reconciliation_required", True),
        ("evidence_inventory_sha256", "4" * 64),
    ],
)
def test_mixed_verification_pair_is_refused(original_pair, field, value):
    snapshot, verified = original_pair
    tx = scoped_pair(lambda: (snapshot, replace(verified, **{field: value})))
    with pytest.raises(M1CommissioningPersistenceError, match="verification differ"):
        tx._admission_observation()


@pytest.mark.parametrize("field", ["cell_id", "source_binding_sha256"])
def test_mixed_runtime_identity_pair_is_refused(original_pair, field):
    snapshot, verified = original_pair
    changed = replace(
        verified.cell,
        **{field: "other-cell" if field == "cell_id" else "5" * 64},
    )
    tx = scoped_pair(lambda: (snapshot, replace(verified, cell=changed)))
    with pytest.raises(M1CommissioningPersistenceError, match="verification differ"):
        tx._admission_observation()


def test_same_head_extra_or_changed_reference_cannot_mix_with_old_pair(original_pair):
    snapshot, verified = original_pair
    ref = EvidenceReference("modeled-reference", STAGE, "1" * 64, "2" * 64, "3" * 64, 4)
    first = replace(snapshot, evidence=(ref,))
    first_verification = replace(
        verified, evidence_inventory_sha256=canonical_sha256([ref.to_dict()])
    )
    assert scoped_pair(
        lambda: (first, first_verification)
    )._admission_observation() == (
        first,
        first_verification,
    )
    for evidence in (
        (),
        (replace(ref, manifest_sha256="4" * 64),),
        (ref, replace(ref, evidence_id="modeled-extra")),
    ):
        changed = replace(first, evidence=evidence)
        assert changed.head == first.head
        with pytest.raises(
            M1CommissioningPersistenceError, match="verification differ"
        ):
            scoped_pair(lambda: (changed, first_verification))._admission_observation()


@pytest.mark.parametrize("bad", ["snapshot", "verification", "missing"])
def test_exact_pair_types_required(original_pair, bad):
    snapshot, verified = original_pair
    pair = (
        None if bad == "missing" else object() if bad == "snapshot" else snapshot,
        object() if bad == "verification" else verified,
    )
    with pytest.raises(M1CommissioningPersistenceError, match="verification differ"):
        scoped_pair(lambda: pair)._admission_observation()


@pytest.mark.parametrize("expired", ["before", "during", "guard"])
def test_live_scope_checked_before_and_after_fresh_callback(original_pair, expired):
    calls = []

    def fresh():
        calls.append("fresh")
        if expired == "during":
            tx._held.closed = True
        elif expired == "guard":
            tx._guard = lambda: (_ for _ in ()).throw(RuntimeError("source changed"))
        return original_pair

    tx = scoped_pair(fresh)
    if expired == "before":
        tx.close_scope()
    with pytest.raises((M1CommissioningPersistenceError, RuntimeError)):
        tx._admission_observation()
    assert calls == ([] if expired == "before" else ["fresh"])


@pytest.mark.parametrize("usb", [False, True])
def test_default_legacy_hook_retains_separate_reads(original_pair, usb):
    tx = object.__new__(
        M1PhysicalUsbIdentityTransaction if usb else _M1CoordinatorTransaction
    )
    tx._fresh_snapshot_verification = None
    calls = []
    tx.snapshot = lambda: (calls.append("snapshot"), original_pair[0])[1]
    tx.verification = lambda: (calls.append("verification"), original_pair[1])[1]
    assert tx._admission_observation() == original_pair
    assert calls == ["snapshot", "verification"]


def test_verify_pair_preserves_independent_global_and_selected_loads(
    tmp_path, monkeypatch
):
    runtime = _runtime(tmp_path)
    runtime.create_session("session-1", created_at_ns=2000)
    add_modeled_zero_io_intent(runtime)
    loads = count_loads(monkeypatch)
    globals_seen = []
    original = PhysicalOnboardingQuarantineLedger.verified_snapshots

    def counted(ledger, attempts):
        globals_seen.append(ledger)
        return original(ledger, attempts)

    monkeypatch.setattr(
        PhysicalOnboardingQuarantineLedger, "verified_snapshots", counted
    )
    session = runtime._open_session("session-1")
    loads.clear()
    old_pair = (session.snapshot(), runtime.verify("session-1"))
    assert len(loads) == 3 and len(globals_seen) == 2
    loads.clear()
    globals_seen.clear()
    pair = runtime._verify_with_snapshot("session-1")
    assert pair == old_pair
    assert len(loads) == 2 and loads[0] == loads[1]
    assert len(globals_seen) == 2
    assert pair[1].unresolved_attempt_ids == ("attempt-1",)
    assert not pair[1].effects_allowed
    # Cost model only: unchanged one-second-per-load assumption, no sleeps.
    assert 3 * 1_000_000_000 - len(loads) * 1_000_000_000 == 1_000_000_000
    loads.clear()
    assert runtime.verify("session-1") == pair[1]
    assert len(loads) == 2
    assert runtime._verify_with_snapshot(None)[0] is None
    assert runtime.verify(None) == runtime._verify_with_snapshot(None)[1]


def test_usb_header_observation_loads_once_instead_of_three(tmp_path, monkeypatch):
    runtime, _, _ = actual_usb_fixture(tmp_path)
    loads = count_loads(monkeypatch)
    old = runtime._open_session(SESSION).snapshot()
    assert len(loads) == 3
    loads.clear()

    class StopBeforeLease(Exception):
        pass

    def stop(self, selected):
        assert selected == SESSION
        raise StopBeforeLease

    monkeypatch.setattr(PhysicalOnboardingM1Runtime, "verify", stop)
    with pytest.raises(StopBeforeLease):
        with runtime.physical_usb_identity_transaction(SESSION):
            pytest.fail("test must stop before lease admission")
    assert len(loads) == 1
    assert old.header.session_id == SESSION


def test_actual_usb_admissions_are_fresh_audited_and_not_cached(tmp_path, monkeypatch):
    runtime, _, adapter = actual_usb_fixture(tmp_path)
    request = RegisteredActionRequest(
        CELL, SESSION, USB_IDENTITY_ACTION_ID, "fresh-only", "1" * 64
    )
    loads = count_loads(monkeypatch)
    with adapter.transaction(LEASES) as tx:
        callback = tx._fresh_snapshot_verification
        assert callback is not None
        audits = []
        actual_audit = tx._audit_records

        def audited(*args, **kwargs):
            audits.append("family-audit")
            return actual_audit(*args, **kwargs)

        monkeypatch.setattr(tx, "_audit_records", audited)
        loads.clear()
        first = tx._fresh_admission(request)
        assert len(loads) == 1 and audits == ["family-audit"]
        loads.clear()
        tx._fresh_snapshot_verification = None
        legacy = tx._fresh_admission(request)
        assert legacy == first and len(loads) == 2
        tx._fresh_snapshot_verification = callback
        current = tx.snapshot()
        ref = tx.store_evidence(
            STAGE,
            b'{"provenance":"MODELED_NO_DEVICE_NEW_ORIGINAL"}',
            label="modeled fresh observation",
            media_type="application/json",
            captured_at_ns=4000,
            expected_head_sha256=current.head.head_sha256,
        )
        loads.clear()
        newer = tx._fresh_admission(request)
        assert len(loads) == 1 and len(audits) >= 4
        assert newer[1].journal_head_sha256 == first[1].journal_head_sha256
        assert newer[1].evidence_inventory_sha256 != first[1].evidence_inventory_sha256
        assert newer[1].challenge_sha256 != first[1].challenge_sha256
        assert ref in callback()[0].evidence
    with pytest.raises(M1CommissioningPersistenceError, match="scope has ended"):
        tx._admission_observation()


def test_prepared_usb_permit_rejects_changed_original_inventory_before_worker(tmp_path):
    runtime, camera, adapter = actual_usb_fixture(tmp_path)
    core, worker = usb_core(adapter)
    permit = core.prepare(actual_request(adapter))
    with camera.stage_transaction(
        SESSION, expected_challenge_sha256=camera.verification(SESSION).challenge_sha256
    ) as tx:
        tx.store_evidence(
            STAGE,
            b'{"provenance":"MODELED_EXTRA_ORIGINAL_AFTER_PREPARE"}',
            label="modeled changed original",
            media_type="application/json",
            captured_at_ns=4000,
            expected_head_sha256=tx.snapshot().head.head_sha256,
        )
    with pytest.raises(
        CommissioningCoordinatorError,
        match="stale source/revision/head/identity/epoch challenge",
    ):
        core.execute(permit)
    assert worker.calls == 0
    assert not runtime._attempts.snapshot().events
