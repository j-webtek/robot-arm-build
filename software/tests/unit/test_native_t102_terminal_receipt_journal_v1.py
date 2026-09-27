"""ARM-052 durable terminal receipt tests; filesystem and memory only."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import jsonschema
import pytest
from referencing import Registry, Resource

from rocell.application.native_t102_executor_rehearsal_v1 import (
    IncapableNativeT102TransportV1,
    IncapableNativeTransportFault,
    execute_native_t102_rehearsal_v1,
    issue_native_t102_execution_authority_rehearsal_v1,
)
from rocell.application.native_t102_handoff_journal_v1 import (
    DurableNativeT102HandoffV1,
)
from rocell.application.native_t102_terminal_receipt_journal_v1 import (
    DurableNativeT102TerminalReceiptV1,
    NativeT102TerminalReceiptJournalError,
    NativeT102TerminalReceiptPhase,
    NativeT102TerminalRecoveryDisposition,
    execute_durable_native_t102_rehearsal_v1,
    load_native_t102_terminal_receipt_v1,
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


def _message():
    return all_joint_command(
        [.1, .2, .3, .4, .5, .6], speed=20, acceleration=1)


def _frame(message):
    return RuntimeCommandFrameV1(
        sequence=1,
        correlation_id="arm052-correlation-1",
        writer_instance_id="arm052-writer",
        controller_session_id="arm052-controller-session",
        configuration_epoch_sha256="d" * 64,
        encoding_profile_sha256="e" * 64,
        issued_monotonic_ns=900,
        expires_monotonic_ns=3_000,
        wire_bytes=encode_line(message),
    )


def _admission(message):
    values = dict(
        review_sha256="a" * 64,
        consumption_sha256="b" * 64,
        capability=Capability.KEYBOARD_CONTACT,
        snapshot_sha256="c" * 64,
        ordered_goal_sha256=(goal_hash(message),),
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


def _setup(tmp_path):
    message = _message()
    frame = _frame(message)
    admission = _admission(message)
    handoff_root = tmp_path / "handoff"
    receipt_root = tmp_path / "receipts"
    handoff_root.mkdir()
    receipt_root.mkdir()
    handoff = DurableNativeT102HandoffV1.prepare(
        handoff_root, frame, admission, adapter_candidate_sha256=ADAPTER,
        created_monotonic_ns=950,
    )
    handoff.claim_writer(
        frame, admission, adapter_candidate_sha256=ADAPTER,
        claimed_monotonic_ns=1_000,
    )
    authority = issue_native_t102_execution_authority_rehearsal_v1(
        handoff, frame, admission, adapter_candidate_sha256=ADAPTER,
        approval_record_sha256=APPROVAL,
        authority_id="arm052-authority-1",
        issued_monotonic_ns=1_050,
        expires_monotonic_ns=2_900,
    )
    return receipt_root, handoff, frame, admission, authority


def _begin(tmp_path):
    values = _setup(tmp_path)
    receipt_root, handoff, frame, admission, authority = values
    journal = DurableNativeT102TerminalReceiptV1.begin(
        receipt_root, handoff, frame, admission, authority,
        adapter_candidate_sha256=ADAPTER,
        pinned_endpoint_sha256=ENDPOINT,
        started_monotonic_ns=1_100,
    )
    return journal, values


def _schema(name):
    return json.loads((WORKSPACE / "software/ai/schemas" / name).read_text(
        encoding="utf-8"))


def test_started_marker_is_durable_and_restart_is_retry_forbidden(tmp_path):
    journal, _ = _begin(tmp_path)
    snapshot = load_native_t102_terminal_receipt_v1(journal.directory)
    assert snapshot.phase is NativeT102TerminalReceiptPhase.EXECUTION_STARTED
    assert snapshot.recovery_disposition is (
        NativeT102TerminalRecoveryDisposition
        .RETRY_FORBIDDEN_EXECUTION_UNCERTAIN)
    assert {item.name for item in journal.directory.iterdir()} == {"started.json"}
    document = snapshot.to_dict()
    assert document["automatic_retry_allowed"] is False
    assert document["hardware_access"] is False
    assert document["physical_authority"] is False
    jsonschema.Draft202012Validator(_schema(
        "native_t102_terminal_receipt_snapshot_v1.schema.json"
    )).validate(document)
    jsonschema.Draft202012Validator(_schema(
        "native_t102_execution_started_v1.schema.json"
    )).validate(json.loads((journal.directory / "started.json").read_text(
        encoding="utf-8")))


def test_durable_wrapper_seals_exact_terminal_receipt(tmp_path):
    receipt_root, handoff, frame, admission, authority = _setup(tmp_path)
    transport = IncapableNativeT102TransportV1(
        pinned_endpoint_sha256=ENDPOINT)
    journal, receipt, snapshot = execute_durable_native_t102_rehearsal_v1(
        receipt_root, handoff, frame, admission, authority, transport,
        adapter_candidate_sha256=ADAPTER,
        started_monotonic_ns=1_100,
        completed_monotonic_ns=1_200,
    )
    reopened = journal.snapshot()
    assert snapshot == reopened
    assert snapshot.phase is NativeT102TerminalReceiptPhase.TERMINAL_RECORDED
    assert snapshot.recovery_disposition is (
        NativeT102TerminalRecoveryDisposition.TERMINAL_NO_REPLAY)
    assert snapshot.receipt_sha256 == receipt.receipt_sha256
    assert {item.name for item in journal.directory.iterdir()} == {
        "started.json", "terminal.json"}
    terminal = json.loads((journal.directory / "terminal.json").read_text(
        encoding="utf-8"))
    assert terminal["executor_receipt"] == receipt.to_dict()
    receipt_schema = _schema(
        "native_t102_executor_rehearsal_receipt_v1.schema.json")
    registry = Registry().with_resource(
        receipt_schema["$id"], Resource.from_contents(receipt_schema))
    jsonschema.Draft202012Validator(
        _schema("native_t102_execution_terminal_v1.schema.json"),
        registry=registry,
    ).validate(terminal)


@pytest.mark.parametrize("fault", list(IncapableNativeTransportFault))
def test_every_executor_outcome_can_be_terminally_sealed(tmp_path, fault):
    receipt_root, handoff, frame, admission, authority = _setup(tmp_path)
    transport = IncapableNativeT102TransportV1(
        pinned_endpoint_sha256=ENDPOINT, fault=fault)
    _, receipt, snapshot = execute_durable_native_t102_rehearsal_v1(
        receipt_root, handoff, frame, admission, authority, transport,
        adapter_candidate_sha256=ADAPTER,
        started_monotonic_ns=1_100,
        completed_monotonic_ns=1_200,
    )
    assert snapshot.phase is NativeT102TerminalReceiptPhase.TERMINAL_RECORDED
    assert receipt.to_dict()["automatic_retry_allowed"] is False


def test_crossed_or_duplicate_terminal_receipt_rejects(tmp_path):
    journal, values = _begin(tmp_path)
    _, handoff, frame, admission, authority = values
    receipt = execute_native_t102_rehearsal_v1(
        handoff, frame, admission, authority,
        IncapableNativeT102TransportV1(pinned_endpoint_sha256=ENDPOINT),
        adapter_candidate_sha256=ADAPTER, now_monotonic_ns=1_100,
    )
    crossed = replace(receipt, pinned_endpoint_sha256="7" * 64)
    with pytest.raises(NativeT102TerminalReceiptJournalError, match="binding"):
        journal.commit_terminal(crossed, completed_monotonic_ns=1_200)
    assert journal.snapshot().phase is (
        NativeT102TerminalReceiptPhase.EXECUTION_STARTED)
    journal.commit_terminal(receipt, completed_monotonic_ns=1_200)
    with pytest.raises(NativeT102TerminalReceiptJournalError, match="already"):
        journal.commit_terminal(receipt, completed_monotonic_ns=1_201)


def test_internally_inconsistent_receipt_rejects_even_when_rehashed(tmp_path):
    journal, values = _begin(tmp_path)
    _, handoff, frame, admission, authority = values
    receipt = execute_native_t102_rehearsal_v1(
        handoff, frame, admission, authority,
        IncapableNativeT102TransportV1(pinned_endpoint_sha256=ENDPOINT),
        adapter_candidate_sha256=ADAPTER, now_monotonic_ns=1_100,
    )
    fabricated = replace(
        receipt, status="WRITE_UNCERTAIN_NO_RETRY",
        error_code="PARTIAL_WRITE", confirmed_bytes=0,
    )
    with pytest.raises(NativeT102TerminalReceiptJournalError, match="content"):
        journal.commit_terminal(fabricated, completed_monotonic_ns=1_200)
    assert journal.snapshot().phase is (
        NativeT102TerminalReceiptPhase.EXECUTION_STARTED)


def test_concurrent_begin_has_exactly_one_winner(tmp_path):
    values = _setup(tmp_path)
    receipt_root, handoff, frame, admission, authority = values

    def begin(_):
        try:
            DurableNativeT102TerminalReceiptV1.begin(
                receipt_root, handoff, frame, admission, authority,
                adapter_candidate_sha256=ADAPTER,
                pinned_endpoint_sha256=ENDPOINT,
                started_monotonic_ns=1_100,
            )
            return "STARTED"
        except (NativeT102TerminalReceiptJournalError, OSError):
            return "REJECTED"

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(begin, range(8)))
    assert outcomes.count("STARTED") == 1
    assert outcomes.count("REJECTED") == 7
    directories = [item for item in receipt_root.iterdir()
                   if not item.name.startswith(".partial-")]
    assert len(directories) == 1
    assert load_native_t102_terminal_receipt_v1(directories[0]).phase is (
        NativeT102TerminalReceiptPhase.EXECUTION_STARTED)


def test_durable_wrapper_rejects_transport_subclass_before_publication(tmp_path):
    receipt_root, handoff, frame, admission, authority = _setup(tmp_path)

    class PretendNativeTransport(IncapableNativeT102TransportV1):
        pass

    with pytest.raises(TypeError, match="incapable"):
        execute_durable_native_t102_rehearsal_v1(
            receipt_root, handoff, frame, admission, authority,
            PretendNativeTransport(pinned_endpoint_sha256=ENDPOINT),
            adapter_candidate_sha256=ADAPTER,
            started_monotonic_ns=1_100,
            completed_monotonic_ns=1_200,
        )
    assert list(receipt_root.iterdir()) == []


@pytest.mark.parametrize("target", ["started", "terminal"])
def test_truncated_records_fail_closed(tmp_path, target):
    journal, values = _begin(tmp_path)
    if target == "terminal":
        _, handoff, frame, admission, authority = values
        receipt = execute_native_t102_rehearsal_v1(
            handoff, frame, admission, authority,
            IncapableNativeT102TransportV1(pinned_endpoint_sha256=ENDPOINT),
            adapter_candidate_sha256=ADAPTER, now_monotonic_ns=1_100,
        )
        journal.commit_terminal(receipt, completed_monotonic_ns=1_200)
    (journal.directory / f"{target}.json").write_bytes(b'{"schema":')
    with pytest.raises(NativeT102TerminalReceiptJournalError, match="invalid JSON"):
        journal.snapshot()


def test_unexpected_entry_and_symlink_root_fail_closed(tmp_path):
    journal, values = _begin(tmp_path)
    (journal.directory / "unexpected.txt").write_text("x", encoding="utf-8")
    with pytest.raises(NativeT102TerminalReceiptJournalError, match="entries"):
        journal.snapshot()

    receipt_root, handoff, frame, admission, authority = values
    link = tmp_path / "linked-receipts"
    try:
        link.symlink_to(receipt_root, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks are unavailable")
    with pytest.raises(NativeT102TerminalReceiptJournalError, match="root"):
        DurableNativeT102TerminalReceiptV1.begin(
            link, handoff, frame, admission, authority,
            adapter_candidate_sha256=ADAPTER,
            pinned_endpoint_sha256=ENDPOINT,
            started_monotonic_ns=1_100,
        )
