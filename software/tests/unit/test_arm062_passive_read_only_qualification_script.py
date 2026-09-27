from __future__ import annotations

from pathlib import Path

import hashlib
import json

import jsonschema


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/run_arm062_passive_read_only_qualification.ps1"


def test_script_is_exactly_one_open_zero_write_and_bounded():
    source = SCRIPT.read_text(encoding="utf-8")
    assert source.count("$serialPort.Open()") == 1
    assert source.count("$serialPort.Close()") == 1
    assert "ReadByte()" in source
    assert "Elapsed.TotalSeconds -lt 1.0" in source
    assert "$lines.Count -lt 4" in source
    assert "$partial.Count -gt 2048" in source
    assert "DtrEnable = $false" in source
    assert "RtsEnable = $false" in source
    for prohibited in (
        "$serialPort.Write", "$serialPort.WriteLine", "DiscardInBuffer",
        "DiscardOutBuffer", "DtrEnable = $true", "RtsEnable = $true",
        "Start-Process", "while ($true)",
    ):
        assert prohibited not in source


def test_script_binds_the_authorized_intake_and_non_authority_receipt():
    source = SCRIPT.read_text(encoding="utf-8")
    for required in (
        "AuthorizedIntakeSha256", "Get-HostBinding",
        "Get-ExactEndpointIdentity", "READY_FOR_SEPARATE_READ_ONLY_AUTHORIZATION",
        "transport_write_count_limit", "active_request_count_limit",
        "movement_command_count_limit", "torque_command_count_limit",
        "outbound_bytes = 0", "active_requests = 0", "movement_commands = 0",
        "torque_commands = 0", "retry_count = 0", "purge_count = 0",
        "physical_authority = $false", "FileMode]::CreateNew",
    ):
        assert required in source


def test_retained_receipt_is_exact_bounded_and_non_authorizing():
    path = ROOT / "ai/eval/arm062_passive_read_only_qualification_20260927.json"
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (
        "ac84722855d43e66e07d512bd60c3d19b2c468c0defe1505303f233bc4148aea")
    receipt = json.loads(raw)
    schema = json.loads((
        ROOT / "ai/schemas/native_t102_read_only_endpoint_qualification_v1.schema.json"
    ).read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(receipt)
    intake = json.loads((
        ROOT / "ai/eval/arm061_read_only_endpoint_intake.json"
    ).read_text(encoding="utf-8"))
    assert receipt["intake_sha256"] == intake["intake_sha256"]
    assert receipt["endpoint_sha256"] == intake["endpoint_sha256"]
    assert receipt["status"] == "PASSIVE_CAPTURE_COMPLETED"
    assert receipt["identity_before"] == receipt["identity_after"]
    assert receipt["open_attempts"] == receipt["close_attempts"] == 1
    assert receipt["open_succeeded"] is receipt["close_confirmed"] is True
    assert receipt["captured_line_count"] == len(receipt["captured_lines"]) == 0
    assert receipt["failure"] is None
    for field in (
        "outbound_bytes", "active_requests", "movement_commands",
        "torque_commands", "retry_count", "purge_count",
    ):
        assert receipt[field] == 0
    for field in (
        "dtr_asserted", "rts_asserted", "controller_start_authorized",
        "transport_write_authorized", "execution_authorized",
        "physical_authority",
    ):
        assert receipt[field] is False
