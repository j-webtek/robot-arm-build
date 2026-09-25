"""Actual isolated M1 snapshots/packages; modeled predecessor qualifications.

The positive path wraps but never replaces admission, family audit, package
verification or payload readers. Negative cases inject changed snapshot/reader
observations only after genuine reads; no original file is modified, no permit
is issued/consumed, and no worker/process/device API may run.
"""

from dataclasses import replace

import pytest

from rocell.application import commissioning_camera_persistence as camera
from rocell.application import commissioning_m1_persistence as base
from rocell.application import commissioning_usb_presence_persistence as presence
from rocell.application.physical_onboarding import PhysicalOnboardingStage
from rocell.application.physical_onboarding_v2 import V2StageState
from test_commissioning_usb_presence_persistence import (
    actual_case,
    workspace,
    no_process_or_device,
    RegisteredActionRequest,
    USB_PRESENCE_ACTION_ID,
    UsbPresenceAdmissionSnapshot,
    CELL,
    SESSION,
    LEASES,
    WINDOWS,
)


def changed_snapshot(snapshot, fault, reference):
    """Negative observations, never changes to the real committed test store."""
    if fault == "header":
        return replace(
            snapshot, header=replace(snapshot.header, header_sha256="9" * 64)
        )
    if fault == "review_event_missing":
        return replace(
            snapshot,
            committed_events=snapshot.committed_events[:-2]
            + snapshot.committed_events[-1:],
        )
    if fault in {"review_reference_missing", "package_snapshot_reference_missing"}:
        return replace(
            snapshot, evidence=tuple(r for r in snapshot.evidence if r != reference)
        )
    if fault == "query_missing":
        return replace(snapshot, committed_events=snapshot.committed_events[:-1])
    query = snapshot.committed_events[-1]
    changes = {
        "query_sequence": {"sequence": query.sequence + 1},
        "query_stage": {"stage": PhysicalOnboardingStage.CAMERA_MODE_CONTROLS},
        "query_previous": {"previous_state": V2StageState.REVIEW_PENDING},
        "query_state": {"state": V2StageState.BLOCKED},
        "query_code": {
            "detail_code": "CAMERA_USB_PRESENCE_QUERY_REQUESTED_" + "0" * 32
        },
        "query_reference": {"evidence": ()},
    }
    return replace(
        snapshot,
        committed_events=(
            *snapshot.committed_events[:-1],
            replace(query, **changes[fault]),
        ),
    )


@WINDOWS
def test_actual_post_super_context_and_independent_package_snapshot_remain_fresh(
    workspace, monkeypatch
):
    runtime, _, store, subject = actual_case(workspace, monkeypatch)
    request = RegisteredActionRequest(
        CELL, SESSION, USB_PRESENCE_ACTION_ID, "read-only-context-regression", "1" * 64
    )
    observed = dict(
        post_super=False, snapshots=[], events=[], in_package=False, fault=None
    )
    original_super = base._M1CoordinatorTransaction._fresh_admission
    original_verify = camera._verify_evidence_directory
    original_payload = camera.read_bounded_regular_file

    def super_admission(transaction, item):
        observed["post_super"] = False
        result = original_super(transaction, item)
        observed["post_super"] = True
        observed["events"].append("super_complete")
        return result

    def verify_package(*args, **kwargs):
        result = original_verify(*args, **kwargs)
        if observed["in_package"]:
            observed["events"].append("verified_package")
        return result

    def payload(*args, **kwargs):
        result = original_payload(*args, **kwargs)
        if (
            observed["in_package"]
            and kwargs.get("label") == "original camera stage evidence"
        ):
            observed["events"].append("bounded_payload")
        return result

    monkeypatch.setattr(
        base._M1CoordinatorTransaction, "_fresh_admission", super_admission
    )
    monkeypatch.setattr(camera, "_verify_evidence_directory", verify_package)
    monkeypatch.setattr(camera, "read_bounded_regular_file", payload)
    with store.transaction(LEASES) as tx:
        original_snapshot = tx.snapshot
        original_audit = tx._audit_records
        original_read = tx._read_original_evidence
        before = original_snapshot()

        def snapshot():
            result = original_snapshot()
            if observed["post_super"]:
                observed["snapshots"].append(result)
                observed["events"].append("snapshot")
                ordinal = len(observed["snapshots"])
                fault = observed["fault"]
                if fault == "package_snapshot_reference_missing" and ordinal == 2:
                    return changed_snapshot(result, fault, subject.reference)
                if ordinal == 1 and fault not in {
                    None,
                    "review_bytes",
                    "package_snapshot_reference_missing",
                }:
                    return changed_snapshot(result, fault, subject.reference)
            return result

        def audit(*args, **kwargs):
            result = original_audit(*args, **kwargs)
            if observed["post_super"]:
                observed["events"].append("family_audit")
            return result

        def read(reference, current):
            assert reference == subject.reference
            if observed["post_super"]:
                # The package reader must receive its own second fresh result,
                # not the first context snapshot reused by the USB subclass.
                if observed["fault"] != "package_snapshot_reference_missing":
                    assert current is observed["snapshots"][1]
                observed["events"].append("original_package_read")
            observed["in_package"] = True
            try:
                result = original_read(reference, current)
            finally:
                observed["in_package"] = False
            if observed["fault"] == "review_bytes":
                return result + b" "
            return result

        monkeypatch.setattr(tx, "snapshot", snapshot)
        monkeypatch.setattr(tx, "_audit_records", audit)
        monkeypatch.setattr(tx, "_read_original_evidence", read)
        facts, admission, verified = tx._fresh_admission(request)
        assert type(admission) is UsbPresenceAdmissionSnapshot
        assert admission.runtime_review_sha256 == subject.review.sha256
        assert facts._review == subject.review.payload
        assert verified.cell.cell_id == CELL
        assert len(observed["snapshots"]) == 2
        assert observed["snapshots"][0] is not observed["snapshots"][1]
        assert observed["snapshots"][0] == observed["snapshots"][1] == before
        assert observed["events"] == [
            "super_complete",
            "snapshot",
            "snapshot",
            "family_audit",
            "original_package_read",
            "verified_package",
            "bounded_payload",
            "verified_package",
        ]

        # These checks call the genuine super admission each time, then inject
        # one bad post-super observation. None can produce a successful result.
        for fault in (
            "header",
            "review_event_missing",
            "review_reference_missing",
            "query_missing",
            "query_sequence",
            "query_stage",
            "query_previous",
            "query_state",
            "query_code",
            "query_reference",
            "review_bytes",
            "package_snapshot_reference_missing",
        ):
            observed.update(post_super=False, snapshots=[], events=[], fault=fault)
            try:
                tx._fresh_admission(request)
            except presence.M1CommissioningPersistenceError:
                pass
            else:
                pytest.fail(
                    "Changed post-super original observation accepted: " + fault
                )
            assert 1 <= len(observed["snapshots"]) <= 2, fault
        observed["post_super"] = False
        observed["fault"] = None
        assert original_snapshot() == before
        assert original_audit() == {}
        assert not runtime._attempts.snapshot().events
    print(
        "FRESH_CONTEXT_PACKAGE_SNAPSHOTS=2; NEGATIVE_OBSERVATIONS=12; WORKER_CALLS=0",
        flush=True,
    )
