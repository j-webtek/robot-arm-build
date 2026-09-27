from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import jsonschema
import pytest

from rocell.application.native_t102_read_only_endpoint_intake_v1 import (
    parse_native_t102_read_only_endpoint_intake_v1,
)
from rocell.application.native_t105_active_feedback_intake_v1 import (
    OPERATIONS,
    REQUEST_BYTES,
    REQUEST_SHA256,
    NativeT105ActiveFeedbackIntakeError,
    build_native_t105_active_feedback_intake_v1,
    parse_native_t105_active_feedback_intake_v1,
)


ROOT = Path(__file__).resolve().parents[2]
PASSIVE_SHA256 = "ac84722855d43e66e07d512bd60c3d19b2c468c0defe1505303f233bc4148aea"


def read_only_intake():
    document = json.loads((
        ROOT / "ai/eval/arm061_read_only_endpoint_intake.json"
    ).read_text(encoding="utf-8"))
    return parse_native_t102_read_only_endpoint_intake_v1(document)


def intake(**changes):
    values = {
        "read_only_intake": read_only_intake(),
        "passive_qualification_sha256": PASSIVE_SHA256,
        "intake_id": "arm063-active-feedback-intake-fixture",
        "created_utc": "2026-09-27T13:00:00Z",
    }
    values.update(changes)
    return build_native_t105_active_feedback_intake_v1(**values)


def test_intake_freezes_exact_t105_and_one_shot_non_motion_policy():
    document = intake().to_dict()
    assert REQUEST_BYTES == b'{"T":105}\n'
    assert len(REQUEST_BYTES) == 10
    assert REQUEST_SHA256 == hashlib.sha256(REQUEST_BYTES).hexdigest()
    assert base64.b64decode(document["request_bytes_base64"]) == REQUEST_BYTES
    assert document["operations"] == list(OPERATIONS)
    assert document["transport_write_count_limit"] == 1
    assert document["active_request_count_limit"] == 1
    assert document["maximum_response_lines"] == 1
    assert document["movement_command_count_limit"] == 0
    assert document["torque_command_count_limit"] == 0
    assert document["t102_command_count_limit"] == 0
    assert document["automatic_retry_allowed"] is False
    assert document["controller_start_allowed"] is False
    assert document["ready_for_separate_active_feedback_authorization"] is True
    for field in (
        "active_feedback_authorized", "endpoint_open_authorized",
        "transport_write_authorized", "execution_authorized",
        "hardware_access", "physical_authority",
    ):
        assert document[field] is False


def test_schema_and_strict_round_trip():
    original = intake()
    document = original.to_dict()
    schema = json.loads((
        ROOT / "ai/schemas/native_t105_active_feedback_intake_v1.schema.json"
    ).read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(document)
    assert parse_native_t105_active_feedback_intake_v1(document) == original


def test_retained_arm063_intake_is_hash_bound_and_non_authorizing():
    path = ROOT / "ai/eval/arm063_active_feedback_intake.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    schema = json.loads((
        ROOT / "ai/schemas/native_t105_active_feedback_intake_v1.schema.json"
    ).read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(document)
    parsed = parse_native_t105_active_feedback_intake_v1(document)
    assert parsed.intake_sha256 == (
        "3b44d5e011d8c44afda1bb6deb1cc479b1fc0c45e59e39308d285cde416b8fcc")
    assert document["read_only_intake_sha256"] == read_only_intake().intake_sha256
    passive = ROOT / "ai/eval/arm062_passive_read_only_qualification_20260927.json"
    assert hashlib.sha256(passive.read_bytes()).hexdigest() == (
        document["passive_qualification_sha256"])
    assert document["active_feedback_authorized"] is False
    assert document["transport_write_authorized"] is False
    assert document["hardware_access"] is False


@pytest.mark.parametrize("field,value", [
    ("request_bytes_base64", "eyJUIjoxMDJ9Cg=="),
    ("request_command_type", 102),
    ("maximum_response_lines", 2),
    ("movement_command_count_limit", 1),
    ("torque_command_count_limit", 1),
    ("t102_command_count_limit", 1),
    ("automatic_retry_allowed", True),
    ("controller_start_allowed", True),
    ("active_feedback_authorized", True),
    ("endpoint_open_authorized", True),
    ("transport_write_authorized", True),
    ("hardware_access", True),
])
def test_request_policy_or_authority_promotion_rejects(field, value):
    document = intake().to_dict()
    document[field] = value
    with pytest.raises(
        NativeT105ActiveFeedbackIntakeError,
        match="request, policy, or authority",
    ):
        parse_native_t105_active_feedback_intake_v1(document)


def test_crossed_endpoint_or_content_hash_rejects():
    document = intake().to_dict()
    document["endpoint"]["port_name"] = "COM8"
    with pytest.raises(NativeT105ActiveFeedbackIntakeError):
        parse_native_t105_active_feedback_intake_v1(document)
    document = intake().to_dict()
    document["intake_sha256"] = "0" * 64
    with pytest.raises(NativeT105ActiveFeedbackIntakeError, match="content hash"):
        parse_native_t105_active_feedback_intake_v1(document)


@pytest.mark.parametrize("changes", [
    {"response_timeout_s": 0}, {"response_timeout_s": 5.1},
    {"maximum_response_line_bytes": 63},
    {"maximum_response_line_bytes": 4097},
])
def test_unbounded_response_policy_rejects(changes):
    with pytest.raises(NativeT105ActiveFeedbackIntakeError):
        intake(**changes)


def test_intake_cannot_predate_read_only_intake():
    with pytest.raises(NativeT105ActiveFeedbackIntakeError, match="predate"):
        intake(created_utc="2026-09-27T12:00:00Z")


def test_module_has_no_hardware_opener_or_writer():
    source = (ROOT / "src/rocell/application" /
              "native_t105_active_feedback_intake_v1.py").read_text(
                  encoding="utf-8")
    for prohibited in (
        "import serial", "serial.tools", ".open()", ".write(",
        "list_ports", "comports",
    ):
        assert prohibited not in source
