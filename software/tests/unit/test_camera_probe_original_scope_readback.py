"""Complete semantic originals under MODELED camera ownership/store/clock.

Every historical subject verifier runs on the same full typed snapshot. Device
observations and storage are modeled, not physical or real-filesystem approval.
"""

from pathlib import Path
from threading import Event

import pytest

from rocell.application import camera_probe_original_scope as m
from rocell.application import physical_camera_session as session
from rocell.application import camera_probe_admission as admission_impl
from rocell.application.camera_probe_admission import CameraProbeAdmission
from rocell.application.cell_commissioning_coordinator import RegisteredActionRequest
from test_camera_probe_preparation_readback import (
    ready,
    received_ready,
    identity_ready,
    source_model,
    intake_model,
    model,
    no_devices,
    workspace,
    empty_campaigns,
    prepare_reviewed,
    PROBE_LAUNCH,
)


def test_same_full_originals_are_authenticated_under_camera_scope(ready, monkeypatch):
    _, prep, review, current = prepare_reviewed(
        ready, monkeypatch, return_enrollment=True
    )
    owner, _, state = ready
    bound = owner.descriptor()
    monkeypatch.setattr(m, "source_fingerprint", lambda _: state["source"])
    monkeypatch.setattr(m, "monotonic_ns", lambda: state["now"])
    kwargs = dict(
        workspace=Path(bound["workspace"]),
        source_sha256=bound["source_sha256"],
        launch_session_id=PROBE_LAUNCH,
        expected_header_sha256=state["header"].header_sha256,
        expected_preparation_sha256=prep.sha256,
        expected_review_sha256=review.sha256,
        cancellation=Event(),
        deadline_ns=state["now"] + m.MAX_CONTEXT_NS,
        validate_current_context=lambda: None,
    )
    with owner._store.stage_transaction() as tx:
        # Adapt ONLY the modeled ownership/storage seams. The new shared reader
        # and every original subject verifier below are production functions.
        tx._check_scope = lambda: None
        tx._session.directory = Path(bound["directory"]) / bound["session_id"]
        tx.read_camera_evidence = tx.read_stage_evidence
        monkeypatch.setattr(
            type(tx),
            "held_leases",
            property(lambda _: m._leases(bound["cell_id"], bound["session_id"])),
        )
        with pytest.raises(
            session.PhysicalCameraSessionError,
            match="EXACT_CAMERA_TRANSACTION_REQUIRED",
        ):
            session._read_original_evidence_under_lease(
                tx,
                bound=bound,
                expected_header_sha256=kwargs["expected_header_sha256"],
                strict_workflow=True,
                check=lambda: None,
            )
        before = state["snapshot"]()
        reads_before = state["reads"]
        handle = m.read_camera_probe_originals(tx, **kwargs)
        assert state["snapshot"]() == before
        assert state["reads"] - reads_before == len(before.evidence)
        summary = handle.summary()
        assert summary["preparation_sha256"] == prep.sha256
        assert summary["review_sha256"] == review.sha256
        assert summary["journal_head_sha256"] == before.head.head_sha256
        reads_after = state["reads"]
        request = RegisteredActionRequest(
            bound["cell_id"],
            bound["session_id"],
            m.ACTION_IDS["probe"],
            "MODELED-no-execution-request",
            "f" * 64,
        )
        handle.assert_current(tx, request, before)
        assert state["reads"] == reads_after  # No repeat of the semantic audit.

        # Real facts composition using those complete authenticated MODELED
        # originals. Capacity is separately tested against genuine NTFS; here
        # the scope/store has no files and its observation is explicitly modeled.
        capacity_calls = []

        def modeled_capacity(transaction, **kwargs):
            assert transaction is tx
            capacity_calls.append(kwargs)
            return dict(
                schema="MODELED_CAPACITY_NOT_PHYSICAL_QUALIFICATION",
                capacity_reserved=False,
                frame_output_bytes=0,
            )

        monkeypatch.setattr(admission_impl, "observe_probe_capacity", modeled_capacity)
        monkeypatch.setattr(
            admission_impl, "_capacity_from_current_records", modeled_capacity
        )
        assert current.export_snapshot() == prep.to_dict()["enrollment"]
        facts_owner = CameraProbeAdmission(
            handle,
            tx,
            enrollment=current,
            operator_id="MODELED current operator",
            arm_actuator_supply_disconnected=True,
            bounded_probe_consent=True,
            request_key=request.request_key,
            expected_plan_sha256=m.digest(m.canonical(prep.to_dict()["plan"])),
        )
        facts = facts_owner(tx, request, before)
        originals = facts_owner.retained_documents()
        assert len(originals["configuration_epochs"]) == 8
        conditions = originals["hazard_assessment"]["current_condition_report"]
        assert conditions["provenance"] == "CURRENT_OPERATOR_REPORT"
        assert conditions["instrument_verified"] is False
        assert conditions["observed_power_state"] == "UNKNOWN"
        assert facts.selected_identity_document == prep.to_dict()["plan"]["selection"]
        assert facts_owner(tx, request, before) is facts  # Stable permit dependencies.
        assert len(capacity_calls) == 3  # Current capacity still checked every time.
        assert state["reads"] == reads_after

        # Corrupt an original payload while retaining its old manifest/hash.
        # The full reader must refuse before any new handoff is produced.
        reference = before.evidence[0]
        state["payloads"][reference.evidence_id] += b" "
        with pytest.raises(ValueError):
            m.read_camera_probe_originals(tx, **kwargs)
