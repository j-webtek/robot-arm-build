from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from rocell.application.native_t102_owner_ai_review_acceptance_v1 import (
    parse_native_t102_owner_ai_review_acceptance_v1,
)
from rocell.application.native_t102_production_transport_v1 import (
    PinnedNativeT102EndpointV1,
)
from rocell.application.native_t102_read_only_endpoint_intake_v1 import (
    OPERATIONS,
    NativeT102ReadOnlyEndpointIntakeError,
    build_native_t102_read_only_endpoint_intake_v1,
    parse_native_t102_read_only_endpoint_intake_v1,
)


ROOT = Path(__file__).resolve().parents[2]


def acceptance():
    document = json.loads((
        ROOT / "ai/eval/arm059_owner_ai_review_acceptance.json"
    ).read_text(encoding="utf-8"))
    return parse_native_t102_owner_ai_review_acceptance_v1(document)


def endpoint(**changes):
    values = {
        "port_name": "COM7",
        "usb_vid": "10C4",
        "usb_pid": "EA60",
        "usb_serial_number": "SYNTHETIC-ARM060-UNIT",
    }
    values.update(changes)
    return PinnedNativeT102EndpointV1(**values)


def intake(**changes):
    values = {
        "owner_acceptance": acceptance(),
        "endpoint": endpoint(),
        "intake_id": "arm060-read-only-intake-fixture",
        "host_id": "synthetic-windows-host",
        "created_utc": "2026-09-27T12:20:00Z",
    }
    values.update(changes)
    return build_native_t102_read_only_endpoint_intake_v1(**values)


def test_intake_binds_owner_review_and_exact_zero_write_policy():
    result = intake()
    document = result.to_dict()
    assert document["status"] == "READY_FOR_SEPARATE_READ_ONLY_AUTHORIZATION"
    assert document["operations"] == list(OPERATIONS)
    assert document["owner_acceptance_sha256"] == acceptance().acceptance_sha256
    assert document["endpoint"] == endpoint().to_dict()
    assert document["transport_write_count_limit"] == 0
    assert document["active_request_count_limit"] == 0
    assert document["movement_command_count_limit"] == 0
    assert document["torque_command_count_limit"] == 0
    assert document["ready_for_separate_read_only_authorization"] is True
    for name in (
        "read_only_endpoint_authorized", "endpoint_open_authorized",
        "controller_start_authorized", "transport_write_authorized",
        "execution_authorized", "hardware_access", "physical_authority",
    ):
        assert document[name] is False


def test_schema_and_strict_round_trip():
    original = intake()
    document = original.to_dict()
    schema = json.loads((
        ROOT / "ai/schemas/native_t102_read_only_endpoint_intake_v1.schema.json"
    ).read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(document)
    assert parse_native_t102_read_only_endpoint_intake_v1(document) == original


def test_retained_arm061_intake_is_strict_and_non_authorizing():
    document = json.loads((
        ROOT / "ai/eval/arm061_read_only_endpoint_intake.json"
    ).read_text(encoding="utf-8"))
    schema = json.loads((
        ROOT / "ai/schemas/native_t102_read_only_endpoint_intake_v1.schema.json"
    ).read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(document)
    parsed = parse_native_t102_read_only_endpoint_intake_v1(document)
    assert parsed.intake_sha256 == document["intake_sha256"]
    assert parsed.endpoint.endpoint_sha256 == document["endpoint_sha256"]
    assert document["status"] == "READY_FOR_SEPARATE_READ_ONLY_AUTHORIZATION"
    assert document["read_only_endpoint_authorized"] is False
    assert document["endpoint_open_authorized"] is False
    assert document["transport_write_count_limit"] == 0
    assert document["movement_command_count_limit"] == 0


@pytest.mark.parametrize("field,value", [
    ("transport_write_count_limit", 1),
    ("active_request_count_limit", 1),
    ("movement_command_count_limit", 1),
    ("torque_command_count_limit", 1),
    ("automatic_retry_allowed", True),
    ("fallback_endpoint_allowed", True),
    ("endpoint_open_authorized", True),
    ("hardware_access", True),
])
def test_policy_or_authority_promotion_rejects(field, value):
    document = intake().to_dict()
    document[field] = value
    with pytest.raises(NativeT102ReadOnlyEndpointIntakeError,
                       match="policy or authority"):
        parse_native_t102_read_only_endpoint_intake_v1(document)


def test_crossed_endpoint_or_content_hash_rejects():
    document = intake().to_dict()
    document["endpoint"]["usb_serial_number"] = "CROSSED"
    with pytest.raises(NativeT102ReadOnlyEndpointIntakeError):
        parse_native_t102_read_only_endpoint_intake_v1(document)
    document = intake().to_dict()
    document["intake_sha256"] = "0" * 64
    with pytest.raises(NativeT102ReadOnlyEndpointIntakeError, match="content hash"):
        parse_native_t102_read_only_endpoint_intake_v1(document)


@pytest.mark.parametrize("changes", [
    {"passive_read_timeout_s": 0},
    {"passive_read_timeout_s": 10.1},
    {"maximum_passive_lines": 0},
    {"maximum_passive_lines": 17},
    {"maximum_line_bytes": 63},
    {"maximum_line_bytes": 4097},
])
def test_unbounded_passive_capture_rejects(changes):
    with pytest.raises(NativeT102ReadOnlyEndpointIntakeError):
        intake(**changes)


def test_intake_cannot_predate_owner_acceptance():
    with pytest.raises(NativeT102ReadOnlyEndpointIntakeError, match="predate"):
        intake(created_utc="2026-09-27T12:09:59Z")


def test_material_changes_change_hash():
    original = intake()
    assert intake().intake_sha256 == original.intake_sha256
    assert intake(host_id="another-host").intake_sha256 != original.intake_sha256
    assert intake(endpoint=endpoint(port_name="COM8")).intake_sha256 != (
        original.intake_sha256)


def test_module_has_no_hardware_opener_or_writer():
    source = (ROOT / "src/rocell/application" /
              "native_t102_read_only_endpoint_intake_v1.py").read_text(
                  encoding="utf-8")
    for prohibited in (
        "import serial", "serial.tools", ".open()", ".write(",
        "list_ports", "comports", "feedback_request(",
    ):
        assert prohibited not in source
