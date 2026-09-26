"""Published zero-write S4 schemas and deterministic synthetic golden bytes.

This suite opens no transport and performs no controller, serial, network, or
hardware operation.  The T=102 bytes are an encoding fixture, not evidence that
the installed controller mapping or firmware has been qualified.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import jsonschema
import pytest

from rocell.application.zero_write_sole_writer_v1 import (
    ZeroWriteSoleWriterJournalV1,
    run_zero_write_sole_writer_rehearsal_v1,
)
from rocell.application.zero_write_waveshare_adapter_v1 import (
    ZeroWriteWaveshareAdapterV1,
)

import test_zero_write_waveshare_adapter_v1 as preview


WORKSPACE = Path(__file__).resolve().parents[3]
SCHEMA_ROOT = WORKSPACE / "software" / "ai" / "schemas"
FIXTURE = (
    WORKSPACE / "software" / "tests" / "fixtures"
    / "zero_write_waveshare_v1" / "t102_waypoint_1.jsonl"
)


def _schema(name: str) -> dict[str, object]:
    return json.loads((SCHEMA_ROOT / name).read_text(encoding="utf-8"))


def _validate(name: str, document: dict[str, object]) -> None:
    jsonschema.Draft202012Validator(_schema(name)).validate(document)


def _documents():
    envelope = preview._envelope()
    profile = preview._profile(envelope)
    permit = preview._permit(envelope, profile)
    receipt = ZeroWriteWaveshareAdapterV1().preview(
        envelope, permit, profile, now_monotonic_ns=100)
    journal = ZeroWriteSoleWriterJournalV1(
        preview_receipt_sha256=receipt.receipt_sha256,
        correlation_id=receipt.correlation_id,
        writer_instance_id="writer-instance-1",
    )
    report = run_zero_write_sole_writer_rehearsal_v1(receipt, journal)
    return profile, permit, receipt, journal, report


def test_runtime_documents_validate_against_all_published_schemas():
    profile, permit, receipt, journal, report = _documents()
    documents = {
        "zero_write_waveshare_t102_profile_v1.schema.json": profile.to_dict(),
        "zero_write_waveshare_preview_permit_v1.schema.json": permit.to_dict(),
        "zero_write_waveshare_preview_receipt_v1.schema.json": receipt.to_dict(),
        "zero_write_sole_writer_journal_v1.schema.json": json.loads(
            journal.export_bytes()),
        "zero_write_sole_writer_report_v1.schema.json": report.to_dict(),
    }
    for schema_name, document in documents.items():
        _validate(schema_name, document)


def test_golden_wire_bytes_are_exact_runtime_output_and_hash_bound():
    _, _, receipt, _, _ = _documents()
    golden = FIXTURE.read_bytes()
    assert golden == receipt.commands[0].wire_bytes
    assert golden.endswith(b"\n")
    assert hashlib.sha256(golden).hexdigest() == (
        receipt.commands[0].to_dict()["wire_bytes_sha256"])
    assert json.loads(golden) == receipt.commands[0].message


def test_hashes_and_journal_round_trip_recompute_from_runtime_documents():
    profile, permit, receipt, journal, report = _documents()
    assert profile.profile_sha256 == hashlib.sha256(
        json.dumps(profile.unsigned_dict(), sort_keys=True, separators=(",", ":"))
        .encode("utf-8")
    ).hexdigest()
    assert permit.permit_id == hashlib.sha256(
        json.dumps(permit.unsigned_dict(), sort_keys=True, separators=(",", ":"))
        .encode("utf-8")
    ).hexdigest()
    assert receipt.receipt_sha256 == hashlib.sha256(
        json.dumps(receipt.unsigned_dict(), sort_keys=True, separators=(",", ":"))
        .encode("utf-8")
    ).hexdigest()
    assert report.report_sha256 == hashlib.sha256(
        json.dumps(report.unsigned_dict(), sort_keys=True, separators=(",", ":"))
        .encode("utf-8")
    ).hexdigest()
    recovered = ZeroWriteSoleWriterJournalV1.from_bytes(journal.export_bytes())
    assert recovered.journal_sha256 == journal.journal_sha256
    assert recovered.recovery_disposition == "TERMINAL_NO_REPLAY"


@pytest.mark.parametrize(("schema_name", "document_key"), [
    ("zero_write_waveshare_t102_profile_v1.schema.json", "profile"),
    ("zero_write_waveshare_preview_permit_v1.schema.json", "permit"),
    ("zero_write_waveshare_preview_receipt_v1.schema.json", "receipt"),
    ("zero_write_sole_writer_journal_v1.schema.json", "journal"),
    ("zero_write_sole_writer_report_v1.schema.json", "report"),
])
def test_schemas_reject_authority_or_unpublished_fields(schema_name, document_key):
    profile, permit, receipt, journal, report = _documents()
    documents = {
        "profile": profile.to_dict(),
        "permit": permit.to_dict(),
        "receipt": receipt.to_dict(),
        "journal": json.loads(journal.export_bytes()),
        "report": report.to_dict(),
    }
    document = deepcopy(documents[document_key])
    document["unpublished_transport_authority"] = True
    with pytest.raises(jsonschema.ValidationError):
        _validate(schema_name, document)
    if "hardware_access" in documents[document_key]:
        document = deepcopy(documents[document_key])
        document["hardware_access"] = True
        with pytest.raises(jsonschema.ValidationError):
            _validate(schema_name, document)
