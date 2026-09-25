"""Real NTFS/M1 compound storage, with MODELED predecessors/native assessment.

Tests the narrow storage guard and immutable read/reopen/fault behavior, not the
future full v17 original reader, public wizard or camera hardware qualification.
No captured pixels, native process, device admission or stage approval is made.
"""

from copy import deepcopy
import json

import pytest

from rocell.application.camera_operating_submission import (
    build_camera_operating_submission,
    CameraOperatingSubmission,
    camera_operating_submission_event,
)
from rocell.application.camera_probe_preparation import (
    build_camera_probe_preparation_review,
    camera_probe_event,
    camera_probe_label,
)
from rocell.application.commissioning_camera_persistence import (
    M1CommissioningPersistenceError,
    M1PhysicalCameraPersistence,
    physical_camera_source_binding,
)
from rocell.application.physical_camera_session import _denied_facts
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.application.physical_onboarding_m1 import PhysicalOnboardingM1Runtime
from rocell.application.physical_onboarding_v2 import V2StageState as S
from rocell.providers.windows.native_camera_protocol import canonical, digest
from test_commissioning_camera_persistence import (
    runtime_and_adapter,
    WINDOWS,
    SESSION,
    CELL,
    SOURCE,
    forbid_device_and_process_calls,
)
from test_camera_mode_entry_persistence import predecessor, entry_for, open_entry
from test_camera_probe_preparation_readback import prepared_subject, PROBE_LAUNCH
from test_native_camera_activation_expectation import enrollment
from test_camera_operating_submission import seed

pytestmark = WINDOWS


def stage(adapter):
    return adapter.stage_transaction(
        SESSION,
        expected_challenge_sha256=adapter.verification(SESSION).challenge_sha256,
    )


def ready_store(tmp_path, seed, *, native_output_in_store=False):
    runtime, adapter = runtime_and_adapter(tmp_path, ready=False)
    bound = dict(
        workspace=str(tmp_path),
        directory=str(
            runtime.deployment_root
            if native_output_in_store
            else tmp_path / "software/runs/physical-camera-acquisition" / PROBE_LAUNCH
        ),
        cell_id=CELL,
        session_id=SESSION,
        source_sha256=SOURCE,
    )
    with stage(adapter) as tx:
        before = predecessor(tx)
        entry = entry_for(before)
        ref = tx.store_camera_mode_entry(
            entry.payload,
            captured_at_ns=10001,
            expected_head_sha256=before.head.head_sha256,
        )
        entered = open_entry(tx, before, entry, ref)
        preparation = prepared_subject(
            dict(
                camera_mode_entry=dict(
                    entry=dict(evidence_sha256=entry.sha256),
                    events=[entered.committed_events[-1].to_dict()],
                ),
                usb_qualification_reboot=dict(
                    enrollment=dict(document=enrollment().export_snapshot())
                ),
            ),
            bound,
        )
        identifier = preparation.to_dict()["preparation_id"]
        prep_ref = tx.store_evidence(
            STAGE_ORDER[4],
            preparation.payload,
            label=camera_probe_label("preparation", identifier),
            media_type="application/json",
            captured_at_ns=10004,
            expected_head_sha256=entered.head.head_sha256,
        )
        blocked = tx.commit_stage_state(
            STAGE_ORDER[4],
            S.BLOCKED,
            occurred_at_ns=10005,
            detail_code=camera_probe_event("PREPARED", identifier),
            expected_head_sha256=entered.head.head_sha256,
            evidence=(prep_ref,),
        )
        review = build_camera_probe_preparation_review(
            preparation, reviewer_id="MODELED reviewer", reviewed_at_utc_ns=10006
        )
        review_ref = tx.store_camera_probe_review(
            review.payload,
            captured_at_ns=10007,
            expected_head_sha256=blocked.head.head_sha256,
        )
        waiting = tx.commit_stage_state(
            STAGE_ORDER[4],
            S.WAITING_OPERATOR,
            occurred_at_ns=10008,
            detail_code=camera_probe_event("REVIEWED", identifier),
            expected_head_sha256=blocked.head.head_sha256,
            evidence=tuple(
                sorted((prep_ref, review_ref), key=lambda ref: ref.evidence_id)
            ),
        )
        records_sha = digest(canonical(tx._audit_records(include_family=True)))
    proposal = json.loads(seed["proposal_payload"])
    proposal["entry_binding"] = entry.to_dict()["binding"]
    proposal["subjects"]["entry_sha256"] = entry.sha256
    for key in ("source_sha256", "session_id"):
        proposal["probe_binding"][key] = proposal["entry_binding"][key]
    report = json.loads(seed["assessment_payload"])
    report["proposal_sha256"] = digest(canonical(proposal))
    report["preflight"]["proposal_sha256"] = report["proposal_sha256"]
    report["preflight_sha256"] = digest(canonical(report["preflight"]))
    report.update(
        session_id=SESSION,
        header_sha256=waiting.header.header_sha256,
        journal_head_sha256=waiting.head.head_sha256,
        original_records_sha256=records_sha,
    )
    binding = dict(
        **{
            k: proposal["entry_binding"][k]
            for k in ("source_sha256", "cell_id", "session_id", "header_sha256")
        },
        entry_sha256=entry.sha256,
        probe_preparation_sha256=preparation.sha256,
        probe_review_sha256=review.sha256,
        journal_head_sha256=waiting.head.head_sha256,
        original_records_sha256=records_sha,
    )
    subject = build_camera_operating_submission(
        **{k: seed[k] for k in ("submission_id", "operator_id")},
        recorded_at_utc_ns=10009,
        binding=binding,
        proposal_payload=canonical(proposal),
        assessment_payload=canonical(report),
    )
    return runtime, adapter, subject, waiting


def fresh_store(runtime):
    fresh = PhysicalOnboardingM1Runtime.open(
        runtime.deployment_root,
        source_binding_sha256=physical_camera_source_binding(SOURCE),
        cell_id=CELL,
    )
    return M1PhysicalCameraPersistence(
        fresh, workspace_source_sha256=SOURCE, admission_facts=_denied_facts
    )


def write(tx, subject, head):
    return tx.store_camera_operating_submission(
        subject.payload,
        captured_at_ns=10010,
        expected_head_sha256=head,
    )


def test_actual_record_commits_then_reopens_without_approval_or_replay(tmp_path, seed):
    runtime, adapter, subject, waiting = ready_store(tmp_path, seed)
    with stage(adapter) as tx:
        for changed in (True, 10008, 2**63):
            with pytest.raises(M1CommissioningPersistenceError):
                tx.store_camera_operating_submission(
                    subject.payload,
                    captured_at_ns=changed,
                    expected_head_sha256=waiting.head.head_sha256,
                )
            assert tx.snapshot() == waiting
        with pytest.raises(M1CommissioningPersistenceError):
            write(tx, subject, "f" * 64)
        for key in (
            "probe_preparation_sha256",
            "probe_review_sha256",
            "original_records_sha256",
        ):
            data = subject.to_dict()
            data["binding"][key] = "f" * 64
            if key == "original_records_sha256":
                data["assessment"][key] = "f" * 64
                data["assessment_sha256"] = digest(canonical(data["assessment"]))
            with pytest.raises(M1CommissioningPersistenceError):
                write(
                    tx,
                    CameraOperatingSubmission(canonical(data)),
                    waiting.head.head_sha256,
                )
            assert tx.snapshot() == waiting
        ref = write(tx, subject, waiting.head.head_sha256)
        assert tx.read_stage_evidence(ref) == subject.payload
        partial = tx.snapshot()
        assert partial.head == waiting.head and partial.stages == waiting.stages
        with pytest.raises(M1CommissioningPersistenceError):
            write(tx, subject, waiting.head.head_sha256)
        # The modeled producer completes its two writes in the SAME owned
        # transaction. Fresh reopening below never resumes an incomplete write.
        committed = tx.commit_stage_state(
            STAGE_ORDER[4],
            S.REVIEW_PENDING,
            occurred_at_ns=10011,
            detail_code=camera_operating_submission_event(
                subject.to_dict()["submission_id"]
            ),
            expected_head_sha256=partial.head.head_sha256,
            evidence=(ref,),
        )
    with pytest.raises(M1CommissioningPersistenceError):
        tx.read_stage_evidence(ref)
    with stage(fresh_store(runtime)) as tx:
        assert tx.snapshot() == committed
        assert tx.read_stage_evidence(ref) == subject.payload
        assert all(row.state is S.PENDING for row in committed.stages[5:])
        assert committed.header.to_dict()["device_io_authorized"] is False
        assert (
            CameraOperatingSubmission(tx.read_stage_evidence(ref)).to_dict()[
                "stage_passed"
            ]
            is False
        )


def test_fresh_store_keeps_partial_submission_incomplete_without_repair(tmp_path, seed):
    runtime, adapter, subject, waiting = ready_store(tmp_path, seed)
    with stage(adapter) as tx:
        ref = write(tx, subject, waiting.head.head_sha256)
        partial = tx.snapshot()
    with stage(fresh_store(runtime)) as tx:
        assert tx.snapshot() == partial
        assert partial.head == waiting.head and partial.stages == waiting.stages
        assert tx.read_stage_evidence(ref) == subject.payload
        with pytest.raises(M1CommissioningPersistenceError):
            write(tx, subject, partial.head.head_sha256)
        assert tx.snapshot() == partial  # No appended/repaired event.


def test_changed_original_payload_is_rejected_without_rehashing_or_repair(
    tmp_path, seed
):
    runtime, adapter, subject, waiting = ready_store(tmp_path, seed)
    with stage(adapter) as tx:
        ref = write(tx, subject, waiting.head.head_sha256)
        path = tx._session.directory / "evidence" / ref.evidence_id / "payload.bin"
    # Only corrupt this disposable pytest fixture's own known package.
    path.write_bytes(b"MODELED altered original")
    with pytest.raises(ValueError):
        fresh_store(runtime).verification(SESSION)
    assert path.read_bytes() == b"MODELED altered original"


@pytest.mark.parametrize("fault", ["publication", "closing-readback"])
def test_retention_failure_does_not_commit_or_publish_success(
    tmp_path, monkeypatch, seed, fault
):
    runtime, adapter, subject, waiting = ready_store(tmp_path, seed)
    with stage(adapter) as tx:
        if fault == "publication":

            def failed(*args, **kwargs):
                raise OSError("MODELED disk publication failure")

            monkeypatch.setattr(type(tx._session.publication), "write_new_file", failed)
        else:
            from contextlib import contextmanager

            original = tx._original_evidence_readback

            @contextmanager
            def failed(**kwargs):
                with original(**kwargs) as batch:
                    yield batch
                raise M1CommissioningPersistenceError("MODELED late readback failure")

            monkeypatch.setattr(tx, "_original_evidence_readback", failed)
        with pytest.raises((OSError, M1CommissioningPersistenceError)):
            write(tx, subject, waiting.head.head_sha256)
        assert tx.snapshot() == waiting
    with stage(fresh_store(runtime)) as reopened:
        assert reopened.snapshot() == waiting
