"""ARM-051 executor qualification; in-memory only, with zero device I/O."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path

import jsonschema
import pytest

from rocell.application.native_t102_executor_rehearsal_v1 import (
    IncapableNativeT102TransportV1,
    IncapableNativeTransportFault,
    NativeT102ExecutorRehearsalError,
    execute_native_t102_rehearsal_v1,
    issue_native_t102_execution_authority_rehearsal_v1,
)
from rocell.application.native_t102_handoff_journal_v1 import (
    DurableNativeT102HandoffV1,
    NativeT102HandoffJournalError,
)
from rocell.application.production_controller_runtime_contract_v1 import (
    RuntimeCommandFrameV1,
)
from rocell.application.reviewed_motion_permit_bridge_v1 import (
    ReviewedMotionPermitAdmissionV1,
)
from rocell.arm.all_joint_command import all_joint_command
from rocell.arm.protocol import encode_line
from rocell.rc03.build_snapshot import Capability
from rocell.safety.permit import goal_hash


WORKSPACE = Path(__file__).resolve().parents[3]
ADAPTER = "f" * 64
APPROVAL = "9" * 64
ENDPOINT = "8" * 64


def _hash(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


def _message(offset=0.0):
    return all_joint_command(
        [offset + value for value in (.1, .2, .3, .4, .5, .6)],
        speed=20, acceleration=1,
    )


def _frame(message=None, **changes):
    values = dict(
        sequence=1,
        correlation_id="arm051-correlation-1",
        writer_instance_id="arm051-writer",
        controller_session_id="arm051-controller-session",
        configuration_epoch_sha256="d" * 64,
        encoding_profile_sha256="e" * 64,
        issued_monotonic_ns=900,
        expires_monotonic_ns=2_000,
        wire_bytes=encode_line(message or _message()),
    )
    values.update(changes)
    return RuntimeCommandFrameV1(**values)


def _admission(message=None):
    review = "a" * 64
    values = dict(
        review_sha256=review,
        consumption_sha256="b" * 64,
        capability=Capability.KEYBOARD_CONTACT,
        snapshot_sha256="c" * 64,
        ordered_goal_sha256=(goal_hash(message or _message()),),
        permit_expires_at_monotonic=102.0,
    )
    binding = _hash({
        "review_sha256": values["review_sha256"],
        "consumption_sha256": values["consumption_sha256"],
        "capability": values["capability"].value,
        "snapshot_sha256": values["snapshot_sha256"],
        "plan_hash": values["review_sha256"],
        "ordered_goal_sha256": list(values["ordered_goal_sha256"]),
        "permit_expires_at_monotonic": values["permit_expires_at_monotonic"],
    })
    return ReviewedMotionPermitAdmissionV1(
        **values, permit_binding_sha256=binding)


def _claimed(tmp_path):
    message = _message()
    frame = _frame(message)
    admission = _admission(message)
    journal = DurableNativeT102HandoffV1.prepare(
        tmp_path, frame, admission, adapter_candidate_sha256=ADAPTER,
        created_monotonic_ns=950,
    )
    journal.claim_writer(
        frame, admission, adapter_candidate_sha256=ADAPTER,
        claimed_monotonic_ns=1_000,
    )
    return journal, frame, admission


def _authority(journal, frame, admission, **changes):
    values = dict(
        adapter_candidate_sha256=ADAPTER,
        approval_record_sha256=APPROVAL,
        authority_id="arm051-authority-1",
        issued_monotonic_ns=1_050,
        expires_monotonic_ns=1_900,
    )
    values.update(changes)
    return issue_native_t102_execution_authority_rehearsal_v1(
        journal, frame, admission, **values)


def _schema(name):
    return json.loads((WORKSPACE / "software/ai/schemas" / name).read_text(
        encoding="utf-8"))


def test_exact_claim_and_fresh_authority_produce_byte_accounted_receipt(tmp_path):
    journal, frame, admission = _claimed(tmp_path)
    authority = _authority(journal, frame, admission)
    jsonschema.Draft202012Validator(_schema(
        "native_t102_execution_authority_rehearsal_v1.schema.json"
    )).validate(authority.to_dict())
    transport = IncapableNativeT102TransportV1(
        pinned_endpoint_sha256=ENDPOINT)
    receipt = execute_native_t102_rehearsal_v1(
        journal, frame, admission, authority, transport,
        adapter_candidate_sha256=ADAPTER, now_monotonic_ns=1_100,
    ).to_dict()
    assert receipt["status"] == (
        "INCAPABLE_BYTES_CONFIRMED_NOT_CONTROLLER_RECEIVED")
    assert receipt["requested_bytes"] == len(frame.wire_bytes)
    assert receipt["confirmed_bytes"] == len(frame.wire_bytes)
    assert receipt["open_attempts"] == receipt["write_attempts"] == 1
    assert receipt["close_attempts"] == 1
    assert receipt["automatic_retry_allowed"] is False
    assert receipt["hardware_access"] is False
    assert receipt["physical_authority"] is False
    assert receipt["authentic_controller_receipt"] is False
    assert transport.recorded_payload_sha256 == frame.wire_bytes_sha256
    jsonschema.Draft202012Validator(_schema(
        "native_t102_executor_rehearsal_receipt_v1.schema.json"
    )).validate(receipt)


@pytest.mark.parametrize("fault, status, confirmed, writes", [
    (IncapableNativeTransportFault.OPEN_FAILURE,
     "NOT_OPENED_AUTHORITY_CONSUMED_NO_RETRY", 0, 0),
    (IncapableNativeTransportFault.ZERO_WRITE,
     "WRITE_UNCERTAIN_NO_RETRY", 0, 1),
    (IncapableNativeTransportFault.PARTIAL_WRITE,
     "WRITE_UNCERTAIN_NO_RETRY", -1, 1),
    (IncapableNativeTransportFault.INVALID_COUNT,
     "WRITE_UNCERTAIN_NO_RETRY", 0, 1),
    (IncapableNativeTransportFault.WRITE_EXCEPTION,
     "WRITE_UNCERTAIN_NO_RETRY", 0, 1),
    (IncapableNativeTransportFault.CLOSE_FAILURE,
     "CLOSE_UNCERTAIN_NO_RETRY", None, 1),
])
def test_every_transport_fault_is_terminal_and_never_retries(
    tmp_path, fault, status, confirmed, writes,
):
    journal, frame, admission = _claimed(tmp_path)
    authority = _authority(journal, frame, admission)
    transport = IncapableNativeT102TransportV1(
        pinned_endpoint_sha256=ENDPOINT, fault=fault)
    receipt = execute_native_t102_rehearsal_v1(
        journal, frame, admission, authority, transport,
        adapter_candidate_sha256=ADAPTER, now_monotonic_ns=1_100,
    ).to_dict()
    assert receipt["status"] == status
    expected = (len(frame.wire_bytes) if confirmed is None else
                len(frame.wire_bytes) + confirmed if confirmed < 0 else confirmed)
    assert receipt["confirmed_bytes"] == expected
    assert receipt["write_attempts"] == writes
    assert receipt["automatic_retry_allowed"] is False
    with pytest.raises(NativeT102ExecutorRehearsalError, match="already consumed"):
        execute_native_t102_rehearsal_v1(
            journal, frame, admission, authority, transport,
            adapter_candidate_sha256=ADAPTER, now_monotonic_ns=1_101,
        )


def test_concurrent_execution_has_exactly_one_authority_consumer(tmp_path):
    journal, frame, admission = _claimed(tmp_path)
    authority = _authority(journal, frame, admission)

    def run(index):
        transport = IncapableNativeT102TransportV1(
            pinned_endpoint_sha256=ENDPOINT)
        try:
            execute_native_t102_rehearsal_v1(
                journal, frame, admission, authority, transport,
                adapter_candidate_sha256=ADAPTER,
                now_monotonic_ns=1_100 + index,
            )
            return "CONSUMED"
        except NativeT102ExecutorRehearsalError:
            return "REJECTED"

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(run, range(8)))
    assert outcomes.count("CONSUMED") == 1
    assert outcomes.count("REJECTED") == 7


def test_unclaimed_stale_and_crossed_inputs_reject_before_transport_open(tmp_path):
    message = _message()
    frame = _frame(message)
    admission = _admission(message)
    journal = DurableNativeT102HandoffV1.prepare(
        tmp_path, frame, admission, adapter_candidate_sha256=ADAPTER,
        created_monotonic_ns=950,
    )
    with pytest.raises(NativeT102HandoffJournalError, match="committed"):
        journal.verify_claimed_inputs(
            frame, admission, adapter_candidate_sha256=ADAPTER,
            now_monotonic_ns=1_000,
        )
    journal.claim_writer(
        frame, admission, adapter_candidate_sha256=ADAPTER,
        claimed_monotonic_ns=1_000,
    )
    with pytest.raises(NativeT102HandoffJournalError, match="stale"):
        journal.verify_claimed_inputs(
            frame, admission, adapter_candidate_sha256=ADAPTER,
            now_monotonic_ns=2_000,
        )
    crossed = _frame(message, controller_session_id="crossed-session")
    with pytest.raises(NativeT102HandoffJournalError, match="differ"):
        journal.verify_claimed_inputs(
            crossed, admission, adapter_candidate_sha256=ADAPTER,
            now_monotonic_ns=1_100,
        )


def test_expired_or_crossed_authority_rejects_without_open(tmp_path):
    journal, frame, admission = _claimed(tmp_path)
    authority = _authority(journal, frame, admission,
                           expires_monotonic_ns=1_080)
    transport = IncapableNativeT102TransportV1(
        pinned_endpoint_sha256=ENDPOINT)
    with pytest.raises(NativeT102ExecutorRehearsalError, match="lifetime"):
        execute_native_t102_rehearsal_v1(
            journal, frame, admission, authority, transport,
            adapter_candidate_sha256=ADAPTER, now_monotonic_ns=1_100,
        )
    assert transport.open_attempts == 0


def test_real_or_subclassed_transport_cannot_enter_rehearsal_boundary(tmp_path):
    journal, frame, admission = _claimed(tmp_path)
    authority = _authority(journal, frame, admission)

    class PretendNativeTransport(IncapableNativeT102TransportV1):
        pass

    transport = PretendNativeTransport(pinned_endpoint_sha256=ENDPOINT)
    with pytest.raises(TypeError, match="incapable"):
        execute_native_t102_rehearsal_v1(
            journal, frame, admission, authority, transport,
            adapter_candidate_sha256=ADAPTER, now_monotonic_ns=1_100,
        )
    assert transport.open_attempts == 0
