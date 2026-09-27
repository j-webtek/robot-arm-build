from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import jsonschema


ROOT = Path(__file__).resolve().parents[2]
RECEIPT = ROOT / "ai/eval/arm064_active_feedback_qualification_20260927.json"
INTAKE = ROOT / "ai/eval/arm063_active_feedback_intake.json"


def documents():
    return (
        json.loads(RECEIPT.read_text(encoding="utf-8")),
        json.loads(INTAKE.read_text(encoding="utf-8")),
    )


def test_retained_receipt_validates_and_binds_exact_intake():
    receipt, intake = documents()
    schema = json.loads((ROOT / "ai/schemas" /
                         "native_t105_active_feedback_qualification_v1.schema.json").read_text(
                             encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(receipt)
    assert receipt["intake_sha256"] == intake["intake_sha256"]
    assert receipt["endpoint_sha256"] == intake["endpoint_sha256"]
    assert receipt["request_sha256"] == intake["request_sha256"]
    assert hashlib.sha256(RECEIPT.read_bytes()).hexdigest() == (
        "8bf9d1d5fc3f523918953633ef24b51bcf59c44b8d6df8e7fc7fbd8426c3c1d1")


def test_one_attempt_closed_cleanly_with_no_disallowed_effects():
    receipt, _ = documents()
    assert receipt["open_attempts"] == 1
    assert receipt["open_succeeded"] is True
    assert receipt["pre_request_buffered_bytes"] == 0
    assert receipt["write_attempts"] == 1
    assert receipt["outbound_bytes"] == 10
    assert receipt["active_requests"] == 1
    assert receipt["read_attempts"] == 1
    assert receipt["close_attempts"] == 1
    assert receipt["close_confirmed"] is True
    for field in (
        "movement_commands", "torque_commands", "t102_commands",
        "retry_count", "purge_count", "fallback_count",
    ):
        assert receipt[field] == 0
    assert receipt["dtr_asserted"] is False
    assert receipt["rts_asserted"] is False
    assert receipt["controller_start_performed"] is False


def test_response_is_exact_terminal_not_ready_fault_not_t1051():
    receipt, _ = documents()
    raw = base64.b64decode(receipt["response_base64"], validate=True)
    assert raw == b"FAULT:NOT_READY\r\n"
    assert len(raw) == receipt["response_bytes"] == 17
    assert hashlib.sha256(raw).hexdigest() == receipt["response_sha256"]
    assert receipt["response"] is None
    assert receipt["status"] == "ACTIVE_FEEDBACK_FAILED_TERMINAL"
    assert receipt["execution_authorized"] is False
    assert receipt["physical_authority"] is False


def test_repository_source_match_is_evidence_of_consistency_not_attestation():
    source = (ROOT / "firmware/diagnostics/ghost_typing_b_board.h").read_text(
        encoding="utf-8")
    assert 'Serial.println("FAULT:NOT_READY")' in source
    assert "if(next_leg_>=5||sent_||faulted_||!snapshot_valid_)" in source
