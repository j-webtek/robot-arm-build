from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json

import pytest

from rocell.application.zero_write_sole_writer_v1 import (
    ZeroWriteSoleWriterError,
    ZeroWriteSoleWriterJournalV1,
    ZeroWriteWriterFault,
    run_zero_write_sole_writer_rehearsal_v1,
)
from rocell.application.zero_write_waveshare_adapter_v1 import (
    ZeroWriteWaveshareAdapterV1,
)

import test_zero_write_waveshare_adapter_v1 as preview


def _receipt():
    envelope = preview._envelope()
    profile = preview._profile(envelope)
    return ZeroWriteWaveshareAdapterV1().preview(
        envelope, preview._permit(envelope, profile), profile,
        now_monotonic_ns=100)


def _journal(receipt, writer="writer-instance-1"):
    return ZeroWriteSoleWriterJournalV1(
        preview_receipt_sha256=receipt.receipt_sha256,
        correlation_id=receipt.correlation_id,
        writer_instance_id=writer)


def test_successful_rehearsal_closes_without_transport_or_write():
    receipt = _receipt()
    journal = _journal(receipt)
    report = run_zero_write_sole_writer_rehearsal_v1(receipt, journal)
    document = report.to_dict()

    assert document["status"] == "ZERO_WRITE_REHEARSAL_COMPLETE"
    assert document["recovery_disposition"] == "TERMINAL_NO_REPLAY"
    assert document["would_submit_command_count"] == 1
    assert document["transport_open_count"] == 0
    assert document["physical_write_count"] == 0
    assert document["submitted_bytes"] == []
    assert document["acknowledgements"] == []
    assert document["feedback_samples"] == []
    assert document["automatic_retry"] is False
    assert document["hardware_access"] is document["physical_authority"] is False
    assert [event.kind for event in journal.events] == ["RESERVED", "CLOSED"]
    assert len(document["report_sha256"]) == 64


@pytest.mark.parametrize("fault", [
    ZeroWriteWriterFault.PARTIAL_WRITE,
    ZeroWriteWriterFault.ACK_TIMEOUT,
    ZeroWriteWriterFault.FEEDBACK_TIMEOUT,
    ZeroWriteWriterFault.TRANSPORT_CLOSE_UNCERTAIN,
])
def test_ambiguous_faults_close_terminal_without_resend_or_physical_write(fault):
    receipt = _receipt()
    journal = _journal(receipt)
    report = run_zero_write_sole_writer_rehearsal_v1(
        receipt, journal, fault=fault).to_dict()
    assert report["status"] == "AMBIGUOUS_NO_RETRY"
    assert report["recovery_disposition"] == "TERMINAL_NO_REPLAY"
    assert report["automatic_retry"] is False
    assert report["transport_open_count"] == report["physical_write_count"] == 0
    assert report["submitted_bytes"] == []
    expected_timeouts = (
        [fault.value] if fault in {
            ZeroWriteWriterFault.ACK_TIMEOUT,
            ZeroWriteWriterFault.FEEDBACK_TIMEOUT,
        } else [])
    assert report["timeout_events"] == expected_timeouts


def test_restart_after_reservation_requires_reconciliation_and_never_replays():
    receipt = _receipt()
    journal = _journal(receipt)
    report = run_zero_write_sole_writer_rehearsal_v1(
        receipt, journal,
        fault=ZeroWriteWriterFault.PROCESS_RESTART_AFTER_RESERVATION).to_dict()
    assert report["status"] == "RECONCILIATION_REQUIRED"
    assert report["recovery_disposition"] == "RECONCILIATION_REQUIRED_NO_RETRY"
    assert report["writer_closed"] is False
    assert len(journal.events) == 1

    recovered = ZeroWriteSoleWriterJournalV1.from_bytes(journal.export_bytes())
    assert recovered.recovery_disposition == "RECONCILIATION_REQUIRED_NO_RETRY"
    with pytest.raises(ZeroWriteSoleWriterError, match="already reserved"):
        run_zero_write_sole_writer_rehearsal_v1(receipt, recovered)


def test_closed_journal_round_trips_as_terminal_no_replay():
    receipt = _receipt()
    journal = _journal(receipt)
    run_zero_write_sole_writer_rehearsal_v1(
        receipt, journal, fault=ZeroWriteWriterFault.ACK_TIMEOUT)
    recovered = ZeroWriteSoleWriterJournalV1.from_bytes(journal.export_bytes())
    assert recovered.journal_sha256 == journal.journal_sha256
    assert recovered.recovery_disposition == "TERMINAL_NO_REPLAY"
    with pytest.raises(ZeroWriteSoleWriterError, match="already reserved"):
        run_zero_write_sole_writer_rehearsal_v1(receipt, recovered)


def test_journal_tampering_and_duplicate_json_fields_are_rejected():
    receipt = _receipt()
    journal = _journal(receipt)
    run_zero_write_sole_writer_rehearsal_v1(receipt, journal)
    document = json.loads(journal.export_bytes())
    document["events"][0]["details"]["physical_write_count"] = 1
    with pytest.raises(ZeroWriteSoleWriterError, match="event hash"):
        ZeroWriteSoleWriterJournalV1.from_bytes(json.dumps(document).encode())
    raw = journal.export_bytes().decode()
    duplicated = raw.replace(
        '"schema":"rocell.zero_write_sole_writer_journal.v1"',
        '"schema":"rocell.zero_write_sole_writer_journal.v1","schema":"x"')
    with pytest.raises(ZeroWriteSoleWriterError, match="duplicate JSON"):
        ZeroWriteSoleWriterJournalV1.from_bytes(duplicated.encode())


def test_wrong_receipt_cannot_use_an_existing_writer_reservation():
    first = _receipt()
    second = _receipt()
    # Same synthetic correlation and content are identical, so create a journal
    # with a deliberately different exact receipt identity instead.
    journal = ZeroWriteSoleWriterJournalV1(
        preview_receipt_sha256="f" * 64,
        correlation_id=second.correlation_id,
        writer_instance_id="writer-instance-1")
    with pytest.raises(ZeroWriteSoleWriterError, match="different preview"):
        run_zero_write_sole_writer_rehearsal_v1(second, journal)


def test_concurrent_claims_allow_exactly_one_owner_and_no_retry():
    receipt = _receipt()
    journal = _journal(receipt)

    def attempt():
        try:
            run_zero_write_sole_writer_rehearsal_v1(receipt, journal)
            return "PASS"
        except ZeroWriteSoleWriterError:
            return "REJECTED"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _index: attempt(), range(2)))
    assert sorted(outcomes) == ["PASS", "REJECTED"]
    assert journal.recovery_disposition == "TERMINAL_NO_REPLAY"


def test_unknown_fault_is_rejected_before_reservation():
    receipt = _receipt()
    journal = _journal(receipt)
    with pytest.raises(ZeroWriteSoleWriterError, match="unsupported fault"):
        run_zero_write_sole_writer_rehearsal_v1(
            receipt, journal, fault="RETRY" )  # type: ignore[arg-type]
    assert journal.recovery_disposition == "UNUSED"
