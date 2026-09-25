"""Fresh camera observations with real NTFS storage and no device capability.

The small scoped-pair cases model only the transaction guard. Integration cases
use actual readers, source-bound stores and OS leases with explicitly modeled
stage subjects. Timings compare the two read paths on one host, not hardware
startup qualification or a real-time guarantee.
"""

from dataclasses import replace
import json
import sys
from time import monotonic_ns
from types import SimpleNamespace

import pytest

from rocell.application.commissioning_camera_persistence import (
    M1PhysicalCameraTransaction,
)
from rocell.application.commissioning_m1_persistence import (
    M1CommissioningPersistenceError,
)
from test_camera_probe_admission_audit_reuse import modeled_owner
from test_commissioning_camera_persistence import (
    LEASES,
    STAGE,
    WINDOWS,
    forbid_device_and_process_calls,
    records_root,
    runtime_and_adapter,
)
from test_m1_fresh_snapshot_open import count_loads
from test_usb_identity_coherent_observation import original_pair


pytestmark = WINDOWS


def scoped_pair(callback):
    """Model scope only; validation receives actual typed original observations."""
    tx = object.__new__(M1PhysicalCameraTransaction)
    tx._active = True
    tx._held = SimpleNamespace(closed=False)
    tx._guard = lambda: None
    tx._fresh_snapshot_verification = callback
    return tx


@pytest.mark.parametrize(
    "field,value",
    [
        ("session_id", "different-session"),
        ("session_header_sha256", "1" * 64),
        ("session_head_sha256", "2" * 64),
        ("qualification_anchor_sha256", "3" * 64),
        ("session_reconciliation_required", True),
        ("evidence_inventory_sha256", "4" * 64),
    ],
)
def test_camera_refuses_mixed_verification(original_pair, field, value):
    snapshot, verified = original_pair
    tx = scoped_pair(lambda: (snapshot, replace(verified, **{field: value})))
    with pytest.raises(M1CommissioningPersistenceError, match="verification differ"):
        tx._admission_observation()


@pytest.mark.parametrize("field", ["cell_id", "source_binding_sha256"])
def test_camera_refuses_mixed_cell_source(original_pair, field):
    snapshot, verified = original_pair
    cell = replace(
        verified.cell, **{field: "different-cell" if field == "cell_id" else "5" * 64}
    )
    with pytest.raises(M1CommissioningPersistenceError, match="verification differ"):
        scoped_pair(
            lambda: (snapshot, replace(verified, cell=cell))
        )._admission_observation()


@pytest.mark.parametrize("bad", ["snapshot", "verification", "missing"])
def test_camera_requires_exact_pair_types(original_pair, bad):
    snapshot, verified = original_pair
    pair = (
        None if bad == "missing" else object() if bad == "snapshot" else snapshot,
        object() if bad == "verification" else verified,
    )
    with pytest.raises(M1CommissioningPersistenceError, match="verification differ"):
        scoped_pair(lambda: pair)._admission_observation()


@pytest.mark.parametrize("expired", ["before", "during", "guard"])
def test_camera_scope_is_live_on_both_sides_of_observation(original_pair, expired):
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


def test_camera_legacy_composition_still_reads_independently(original_pair):
    tx = scoped_pair(None)
    calls = []
    tx.snapshot = lambda: (calls.append("snapshot"), original_pair[0])[1]
    tx.verification = lambda: (calls.append("verification"), original_pair[1])[1]
    assert tx._admission_observation() == original_pair
    assert calls == ["snapshot", "verification"]


def test_actual_camera_uses_fresh_pair_and_never_caches_inventory(
    tmp_path, monkeypatch
):
    runtime, adapter = runtime_and_adapter(tmp_path)
    loads = count_loads(monkeypatch)
    with adapter.transaction(LEASES) as tx:
        assert callable(tx._fresh_snapshot_verification)
        c = modeled_owner(tmp_path, monkeypatch, runtime, tx)
        loads.clear()
        first = tx._fresh_admission(c.request)
        assert len(loads) == 1
        before = tx.snapshot()
        ref = tx.store_evidence(
            STAGE,
            b'{"provenance":"MODELED_NO_DEVICE_ADDED_ORIGINAL"}',
            label="modeled coherent observation",
            media_type="application/json",
            captured_at_ns=4000,
            expected_head_sha256=before.head.head_sha256,
        )
        loads.clear()
        newer = tx._fresh_admission(c.request)
        assert len(loads) == 1
        assert newer[1].journal_head_sha256 == first[1].journal_head_sha256
        assert newer[1].evidence_inventory_sha256 != first[1].evidence_inventory_sha256
        assert newer[1].challenge_sha256 != first[1].challenge_sha256
        assert ref in tx._admission_observation()[0].evidence
    with pytest.raises(M1CommissioningPersistenceError, match="scope has ended"):
        tx._admission_observation()


@pytest.mark.parametrize(
    "family",
    [
        "physical-camera-records",
        "physical-usb-identity-records",
        "physical-usb-presence-records",
    ],
)
def test_new_family_corruption_is_not_hidden_by_coherent_observation(
    tmp_path, monkeypatch, family
):
    runtime, adapter = runtime_and_adapter(tmp_path)
    with adapter.transaction(LEASES) as tx:
        c = modeled_owner(tmp_path, monkeypatch, runtime, tx)
        tx._fresh_admission(c.request)
        target = (
            records_root(runtime).parent / family / ("request-" + "e" * 64 + ".json")
        )
        assert not target.exists()
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(b"{}\n")
        assert tx.snapshot() == c.snapshot
        with pytest.raises(M1CommissioningPersistenceError, match="record schema"):
            tx._fresh_admission(c.request)
        assert target.read_bytes() == b"{}\n"  # Preserve this isolated fault.


@pytest.mark.parametrize("extra_references", [0, 48])
def test_compare_complete_camera_callback_reads_without_relaxing_guards(
    tmp_path, monkeypatch, record_testsuite_property, extra_references
):
    runtime, adapter = runtime_and_adapter(tmp_path)
    with adapter.transaction(LEASES) as tx:
        for number in range(extra_references):
            tx.store_evidence(
                STAGE,
                json.dumps({"MODELED_FILE_ONLY": number}).encode(),
                label="modeled growing history",
                media_type="application/json",
                captured_at_ns=5000 + number,
                expected_head_sha256=tx.snapshot().head.head_sha256,
            )
        c = modeled_owner(tmp_path, monkeypatch, runtime, tx)
        tx._facts_provider = lambda request, snapshot: c.owner(tx, request, snapshot)
        fresh = tx._fresh_snapshot_verification
        assert callable(fresh)
        loads = count_loads(monkeypatch)
        delegated = tx._audit_records
        audits = []

        def audited(*args, **kwargs):
            audits.append("family")
            return delegated(*args, **kwargs)

        monkeypatch.setattr(tx, "_audit_records", audited)
        observations = []
        expected = None
        # Alternate order to expose cache/host-order assumptions. Both branches
        # use current production readers; None is the unchanged legacy path.
        for mode in ("legacy", "coherent", "coherent", "legacy"):
            tx._fresh_snapshot_verification = fresh if mode == "coherent" else None
            loads.clear()
            audits.clear()
            started = monotonic_ns()
            value = tx._fresh_admission(c.request)
            elapsed = monotonic_ns() - started
            assert len(audits) == 3  # Core plus BOTH original/capacity audits.
            assert len(loads) == (3 if mode == "coherent" else 4)
            assert expected is None or value == expected
            expected = value
            observations.append(
                dict(
                    mode=mode,
                    duration_ns=elapsed,
                    full_v2_loads=len(loads),
                    family_audits=len(audits),
                )
            )
        tx._fresh_snapshot_verification = fresh
        assert expected is not None
        report = dict(
            schema="rocell.test_camera_coherent_observation.v1",
            # platform.platform() can spawn `ver` on Windows. Process creation
            # stays forbidden even for test-report metadata; use interpreter data.
            platform=sys.platform,
            windows_version=list(sys.getwindowsversion()[:3]),
            python=sys.version.split()[0],
            reference_count=len(c.snapshot.evidence),
            reference_bytes=sum(ref.payload_bytes for ref in c.snapshot.evidence),
            record_files=0,
            history="NEW_MODELED_FILE_ONLY_PREDECESSORS_NO_PRIOR_CAMPAIGNS",
            results=observations,
            timings="WHOLE_CALLBACK_ELAPSED_NOT_ISOLATED_BENCHMARK",
            hardware_qualified=False,
            physical_authority=False,
        )
        (tmp_path / "camera-coherent-observation.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        record_testsuite_property(
            f"camera_coherent_history_{extra_references}", json.dumps(report)
        )
        assert not (runtime.deployment_root / "native-camera-output").exists()
