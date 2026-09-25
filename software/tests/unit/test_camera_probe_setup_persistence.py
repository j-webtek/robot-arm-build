"""Real NTFS M1/V2 preparation/review storage; predecessors/devices MODELED.

Tests generic stage mutation at WAITING/BLOCKED, exact readback and fresh lease
reopen. The synthetic predecessor is NOT accepted original application evidence.
"""

from pathlib import Path
from copy import deepcopy

import pytest

from rocell.application.camera_probe_preparation import (
    build_camera_probe_preparation_review,
    camera_probe_event,
    camera_probe_label,
)
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.application.physical_onboarding_v2 import (
    V2StageState,
    PhysicalOnboardingV2Error,
)
from rocell.application.commissioning_camera_persistence import (
    M1CommissioningPersistenceError,
)
from rocell.application.camera_probe_preparation import CameraProbePreparationReview
from rocell.providers.windows.native_camera_protocol import canonical
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


@WINDOWS
def test_actual_m1_probe_records_roundtrip_across_separate_transactions(tmp_path):
    _, adapter = runtime_and_adapter(tmp_path, ready=False)
    bound = dict(
        workspace=str(tmp_path),
        directory=str(
            tmp_path / "software/runs/physical-camera-acquisition" / PROBE_LAUNCH
        ),
        cell_id=CELL,
        session_id=SESSION,
        source_sha256=SOURCE,
    )
    with adapter.stage_transaction(
        SESSION,
        expected_challenge_sha256=adapter.verification(SESSION).challenge_sha256,
    ) as tx:
        before = predecessor(tx)
        entry = entry_for(before)
        ref = tx.store_camera_mode_entry(
            entry.payload,
            captured_at_ns=10001,
            expected_head_sha256=before.head.head_sha256,
        )
        entered = open_entry(tx, before, entry, ref)
        original = dict(
            camera_mode_entry=dict(
                entry=dict(evidence_sha256=entry.sha256),
                events=[entered.committed_events[-1].to_dict()],
            ),
            usb_qualification_reboot=dict(
                enrollment=dict(document=enrollment().export_snapshot())
            ),
        )
        preparation = prepared_subject(original, bound)
        identifier = preparation.to_dict()["preparation_id"]
        prepared_ref = tx.store_evidence(
            STAGE_ORDER[4],
            preparation.payload,
            label=camera_probe_label("preparation", identifier),
            media_type="application/json",
            captured_at_ns=10004,
            expected_head_sha256=entered.head.head_sha256,
        )
        assert tx.read_stage_evidence(prepared_ref) == preparation.payload
        blocked = tx.commit_stage_state(
            STAGE_ORDER[4],
            V2StageState.BLOCKED,
            occurred_at_ns=10005,
            detail_code=camera_probe_event("PREPARED", identifier),
            expected_head_sha256=entered.head.head_sha256,
            evidence=(prepared_ref,),
        )
        assert blocked.stages[4].state is V2StageState.BLOCKED
    with pytest.raises(M1CommissioningPersistenceError):
        tx.read_stage_evidence(prepared_ref)
    with adapter.stage_transaction(
        SESSION,
        expected_challenge_sha256=adapter.verification(SESSION).challenge_sha256,
    ) as review_tx:
        assert review_tx.read_stage_evidence(prepared_ref) == preparation.payload
        review = build_camera_probe_preparation_review(
            preparation, reviewer_id="MODELED reviewer", reviewed_at_utc_ns=10006
        )
        wrong = review.to_dict()
        wrong["preparation_sha256"] = "f" * 64
        with pytest.raises(M1CommissioningPersistenceError, match="exact entry"):
            review_tx.store_camera_probe_review(
                CameraProbePreparationReview(canonical(wrong)).payload,
                captured_at_ns=10007,
                expected_head_sha256=blocked.head.head_sha256,
            )
        for capture_time in (True, 10005, 2**63):
            with pytest.raises(M1CommissioningPersistenceError):
                review_tx.store_camera_probe_review(
                    review.payload,
                    captured_at_ns=capture_time,
                    expected_head_sha256=blocked.head.head_sha256,
                )
        with pytest.raises(PhysicalOnboardingV2Error, match="stale"):
            review_tx.store_camera_probe_review(
                review.payload, captured_at_ns=10007, expected_head_sha256="f" * 64
            )
        with pytest.raises(PhysicalOnboardingV2Error, match="active reviewed stage"):
            review_tx.store_evidence(
                STAGE_ORDER[4],
                review.payload,
                label=camera_probe_label("review", identifier),
                media_type="application/json",
                captured_at_ns=10007,
                expected_head_sha256=blocked.head.head_sha256,
            )
        reviewed_ref = review_tx.store_camera_probe_review(
            review.payload,
            captured_at_ns=10007,
            expected_head_sha256=blocked.head.head_sha256,
        )
        assert review_tx.read_stage_evidence(reviewed_ref) == review.payload
        with pytest.raises(M1CommissioningPersistenceError, match="partial review"):
            review_tx.store_camera_probe_review(
                review.payload,
                captured_at_ns=10007,
                expected_head_sha256=blocked.head.head_sha256,
            )
        waiting = review_tx.commit_stage_state(
            STAGE_ORDER[4],
            V2StageState.WAITING_OPERATOR,
            occurred_at_ns=10008,
            detail_code=camera_probe_event("REVIEWED", identifier),
            expected_head_sha256=blocked.head.head_sha256,
            evidence=tuple(
                sorted((prepared_ref, reviewed_ref), key=lambda r: r.evidence_id)
            ),
        )
        assert waiting.stages[4].state is V2StageState.WAITING_OPERATOR
        with pytest.raises(PhysicalOnboardingV2Error):
            review_tx.commit_stage_state(
                STAGE_ORDER[4],
                V2StageState.WAITING_OPERATOR,
                occurred_at_ns=10009,
                detail_code="MODELED_NO_DUPLICATE_TRANSITION",
                expected_head_sha256=waiting.head.head_sha256,
            )
    with adapter.stage_transaction(
        SESSION,
        expected_challenge_sha256=adapter.verification(SESSION).challenge_sha256,
    ) as reopened:
        assert reopened.snapshot() == waiting
        assert reopened.read_stage_evidence(prepared_ref) == preparation.payload
        assert reopened.read_stage_evidence(reviewed_ref) == review.payload
        assert all(row.state is V2StageState.PENDING for row in waiting.stages[5:])
        assert waiting.header.to_dict()["device_io_authorized"] is False
