"""Real NTFS audits/capacity with explicitly MODELED semantic admission.

Only the original semantic-authentication and admission-construction seams are
modeled. The production callback, scoped original checks, complete family audit,
record quotas and disk observer run normally. No device or process is available;
these fixtures cannot qualify hardware or prove the full reviewed history.
"""

from dataclasses import replace
import json
from threading import Event
from time import monotonic_ns
from types import SimpleNamespace

import pytest

from rocell.application import camera_probe_admission as admission
from rocell.application import camera_probe_capacity as capacity
from rocell.application import camera_probe_original_scope as original
from rocell.application.cell_commissioning_coordinator import RegisteredActionRequest
from rocell.application.commissioning_camera_persistence import (
    PhysicalCameraAdmissionFacts,
)
from rocell.application.commissioning_m1_persistence import (
    M1CommissioningPersistenceError,
)
from rocell.providers.windows.native_camera_protocol import canonical, digest
from test_commissioning_camera_persistence import (
    LEASES,
    SOURCE,
    WINDOWS,
    forbid_device_and_process_calls,
    records_root,
    runtime_and_adapter,
)
from test_physical_camera_activation_campaign import campaign


def modeled_owner(tmp_path, monkeypatch, runtime, tx):
    """Construct no authority; keep the actual leased snapshot and real reader."""
    plan = campaign(tmp_path, "probe").plan()
    plan["assigned_parent_directory"] = str(
        runtime.deployment_root / "native-camera-output"
    )
    snapshot = tx.snapshot()
    state = SimpleNamespace(source=SOURCE, guard=None, enrollment={"MODELED": "one"})
    monkeypatch.setattr(original, "source_fingerprint", lambda _: state.source)
    now = monotonic_ns()
    setup = original.VerifiedCameraProbeOriginal(
        _snapshot=snapshot,
        _workflow=canonical({"MODELED": "semantic authentication seam"}),
        _binding=canonical({"directory": str(runtime.deployment_root)}),
        _preparation=SimpleNamespace(sha256="1" * 64),
        _review=SimpleNamespace(sha256="2" * 64),
        _workspace=tmp_path,
        _source_sha256=SOURCE,
        _launch_id="wizard-" + "3" * 32,
        _cancellation=Event(),
        _read_completed_at_ns=now,
        _deadline_ns=now + original.MAX_CONTEXT_NS,
        _validate_current_context=lambda: state.guard,
        _read_provenance=original._ORIGINAL_READ,
    )
    request = RegisteredActionRequest(
        snapshot.header.cell_id,
        snapshot.header.session_id,
        capacity.ACTION_IDS["probe"],
        "MODELED-audit-reuse",
        digest(canonical(plan)),
    )
    # Constructor semantics are separately tested with complete modeled history.
    # This fixture isolates the real callback against actual immutable NTFS data.
    owner = object.__new__(admission.CameraProbeAdmission)
    owner._original = setup
    owner._request = request
    owner._plan = canonical(plan)
    owner._enrollment = SimpleNamespace(export_snapshot=lambda: state.enrollment)
    owner._enrollment_bytes = canonical(state.enrollment)
    owner._facts = PhysicalCameraAdmissionFacts(
        {"MODELED": "semantic admission seam, not a physical assessment"},
        tuple({"MODELED_epoch": number} for number in range(8)),
        {"MODELED": "no selected physical device"},
    )
    return SimpleNamespace(
        owner=owner,
        setup=setup,
        request=request,
        snapshot=snapshot,
        state=state,
        plan=plan,
    )


@WINDOWS
def test_callback_shares_headroom_audit_but_keeps_final_full_audit(
    tmp_path, monkeypatch, record_testsuite_property
):
    runtime, adapter = runtime_and_adapter(tmp_path)
    with adapter.transaction(LEASES) as tx:
        c = modeled_owner(tmp_path, monkeypatch, runtime, tx)
        delegated_audit = tx._audit_records
        durations = []
        audited_records = []

        def measured_audit(*, include_family=False):
            assert include_family is True
            started = monotonic_ns()
            try:
                records = delegated_audit(include_family=include_family)
                audited_records.append(records)
                return records
            finally:
                durations.append(monotonic_ns() - started)

        monkeypatch.setattr(tx, "_audit_records", measured_audit)
        delegated_headroom = capacity._record_headroom
        headroom_records = []

        def observed_headroom(records, request_key):
            headroom_records.append(records)
            return delegated_headroom(records, request_key)

        monkeypatch.setattr(capacity, "_record_headroom", observed_headroom)
        delegated_disk = capacity.shutil.disk_usage
        disk_observations = []

        def measured_disk(path):
            value = delegated_disk(path)
            disk_observations.append(value.free)
            return value

        monkeypatch.setattr(capacity.shutil, "disk_usage", measured_disk)
        facts = c.owner(tx, c.request, c.snapshot)
        first_count = len(durations)
        assert c.owner(tx, c.request, c.snapshot) is facts
        # Timings are observations only: no fake clocks, deadline overrides or
        # hardware-latency claims, and no brittle wall-clock acceptance threshold.
        record_testsuite_property(
            "actual_family_audit_duration_ns", json.dumps(durations)
        )
        assert first_count == 2
        assert len(durations) == 4
        assert headroom_records[0] is audited_records[0]
        assert headroom_records[1] is audited_records[2]
        assert headroom_records[0] is not headroom_records[1]
        assert len(disk_observations) == 2
        assert tx.snapshot() == c.snapshot
        assert not (runtime.deployment_root / "native-camera-output").exists()


@WINDOWS
@pytest.mark.parametrize(
    "change",
    ["source", "context", "enrollment", "cancel", "snapshot", "leases", "scope"],
)
def test_late_changes_during_disk_observation_still_reject(
    tmp_path, monkeypatch, change
):
    runtime, adapter = runtime_and_adapter(tmp_path)
    with adapter.transaction(LEASES) as tx:
        c = modeled_owner(tmp_path, monkeypatch, runtime, tx)
        delegated_disk = capacity.shutil.disk_usage
        with monkeypatch.context() as patch:

            def changed_during_disk(path):
                observed = delegated_disk(path)
                if change == "source":
                    c.state.source = "f" * 64
                elif change == "context":
                    c.state.guard = True
                elif change == "enrollment":
                    c.state.enrollment = {"MODELED": "changed"}
                elif change == "cancel":
                    c.setup._cancellation.set()
                elif change == "snapshot":
                    patch.setattr(tx, "snapshot", lambda: None)
                elif change == "leases":
                    patch.setattr(
                        type(tx), "held_leases", property(lambda _: LEASES[:2])
                    )
                else:

                    def closed_scope():
                        raise M1CommissioningPersistenceError("MODELED scope ended")

                    patch.setattr(tx, "_check_scope", closed_scope)
                return observed

            patch.setattr(capacity.shutil, "disk_usage", changed_during_disk)
            with pytest.raises((ValueError, M1CommissioningPersistenceError)):
                c.owner(tx, c.request, c.snapshot)


@WINDOWS
@pytest.mark.parametrize(
    "family",
    [
        "physical-camera-records",
        "physical-usb-identity-records",
        "physical-usb-presence-records",
    ],
)
def test_final_audit_rejects_new_family_corruption_after_disk_read(
    tmp_path, monkeypatch, family
):
    runtime, adapter = runtime_and_adapter(tmp_path)
    with adapter.transaction(LEASES) as tx:
        c = modeled_owner(tmp_path, monkeypatch, runtime, tx)
        delegated_disk = capacity.shutil.disk_usage
        target = (
            records_root(runtime).parent / family / ("request-" + "e" * 64 + ".json")
        )
        assert not target.exists()

        def corrupt_during_disk(path):
            observed = delegated_disk(path)
            target.parent.mkdir(exist_ok=True)
            target.write_bytes(capacity.canonical_json_bytes({}))
            assert tx.snapshot() == c.snapshot  # Session-only checks cannot catch it.
            return observed

        monkeypatch.setattr(capacity.shutil, "disk_usage", corrupt_during_disk)
        with pytest.raises(M1CommissioningPersistenceError, match="record schema"):
            c.owner(tx, c.request, c.snapshot)
        # Retain the disposable newly introduced fault; never repair/remove it.
        assert target.read_bytes() == capacity.canonical_json_bytes({})


@WINDOWS
def test_wrong_request_rejects_without_audit_or_disk_observation(tmp_path, monkeypatch):
    runtime, adapter = runtime_and_adapter(tmp_path)
    with adapter.transaction(LEASES) as tx:
        c = modeled_owner(tmp_path, monkeypatch, runtime, tx)

        def unexpected(*args, **kwargs):
            pytest.fail("different request reached the original/capacity observation")

        monkeypatch.setattr(tx, "_audit_records", unexpected)
        monkeypatch.setattr(capacity.shutil, "disk_usage", unexpected)
        with pytest.raises(ValueError, match="REQUEST_CHANGED"):
            c.owner(
                tx, replace(c.request, request_key="MODELED-other-request"), c.snapshot
            )
