"""Exact-request result checks with synthetic bytes; no runtime/device access."""

import base64
import hashlib
import json

import pytest

from rocell.application.arm_bench_qualification_contract import (
    PassiveBenchRequest,
    BenchContractError,
)
from rocell.application.arm_bench_qualification_result import PassiveBenchResult, SCHEMA
from test_arm_bench_qualification_contract import document


def fixture(raw=b"boot observation\r\n"):
    request = PassiveBenchRequest(json.dumps(document()).encode())
    expected = request.to_dict()
    value = dict(
        schema=SCHEMA,
        request_sha256=request.request_sha256,
        attempt_id=expected["attempt_id"],
        launch_id=expected["launch_id"],
        runtime_sha256=expected["references"]["runtime_sha256"],
        origin="SYNTHETIC_REHEARSAL",
        open_state="SUCCEEDED",
        close_state="CONFIRMED",
        settings_verified=True,
        observation_complete=True,
        started_monotonic_ns=1_000_000_000,
        observation_finished_monotonic_ns=6_000_000_000,
        finished_monotonic_ns=6_010_000_000,
        outbound_bytes=0,
        startup=dict(
            base64=base64.b64encode(raw).decode(),
            bytes=len(raw),
            sha256=hashlib.sha256(raw).hexdigest(),
            unretained_bytes=0,
        ),
        errors=[],
    )
    return request, value


def result(request, value):
    return PassiveBenchResult(json.dumps(value).encode(), request)


def test_exact_result_retains_bytes_but_does_not_authenticate_hardware():
    request, value = fixture()
    retained = result(request, value)
    assert retained.to_dict() == value
    summary = retained.summary()
    assert summary["status"] == "OBSERVED_CLOSED"
    assert summary["holds"] == []
    assert summary["reported_port_close_confirmed"] is True
    for field in (
        "qualified",
        "connected",
        "physical_authority",
        "runtime_authenticated",
    ):
        assert summary[field] is False
    assert "base64" not in summary
    value["outbound_bytes"] = 1
    assert retained.to_dict()["outbound_bytes"] == 0


@pytest.mark.parametrize(
    "field",
    ["request_sha256", "attempt_id", "launch_id", "runtime_sha256", "origin", "schema"],
)
def test_substituted_binding_rejected(field):
    request, value = fixture()
    value[field] = "substituted"
    with pytest.raises(BenchContractError):
        result(request, value)


@pytest.mark.parametrize(
    "amount,state", [(None, "SIDE_EFFECT_UNCERTAIN"), (1, "INCIDENT_HOLD")]
)
def test_unknown_or_unexpected_effect_is_retained_not_zeroed(amount, state):
    request, value = fixture()
    value["outbound_bytes"] = amount
    retained = result(request, value)
    assert retained.to_dict()["outbound_bytes"] == amount
    assert retained.summary()["status"] == state


def test_unresolved_cleanup_dominates_other_outcomes():
    request, value = fixture()
    value.update(close_state="UNKNOWN", outbound_bytes=None)
    summary = result(request, value).summary()
    assert summary["status"] == "CLEANUP_UNCERTAIN"
    assert summary["reported_port_close_confirmed"] is False


@pytest.mark.parametrize(
    "field", ["observation_finished_monotonic_ns", "finished_monotonic_ns"]
)
def test_late_result_preserved_as_deadline_hold(field):
    request, value = fixture()
    if field == "observation_finished_monotonic_ns":
        value[field] = 8_000_000_000
        value["finished_monotonic_ns"] = 8_010_000_000
    else:
        value[field] = 25_000_000_000
    summary = result(request, value).summary()
    assert summary["status"] == "FAILED_KNOWN"
    assert "DEADLINE_EXCEEDED" in summary["holds"]


def test_truncated_startup_preserves_prefix_and_lost_count():
    request, value = fixture(b"x" * 65536)
    value["startup"]["unretained_bytes"] = 200
    summary = result(request, value).summary()
    assert summary["startup_bytes"] == 65536
    assert summary["startup_unretained_bytes"] == 200
    assert "STARTUP_DATA_LIMIT" in summary["holds"]


def test_unknown_unretained_startup_bytes_are_not_assumed_zero():
    request, value = fixture()
    value["startup"]["unretained_bytes"] = None
    summary = result(request, value).summary()
    assert summary["startup_unretained_bytes"] is None
    assert "STARTUP_DATA_UNACCOUNTED" in summary["holds"]
    assert summary["status"] != "OBSERVED_CLOSED"


@pytest.mark.parametrize(
    "field,new",
    [
        ("bytes", True),
        ("bytes", 65537),
        ("sha256", "a" * 64),
        ("base64", "???"),
        ("unretained_bytes", -1),
    ],
)
def test_invalid_startup_evidence_rejected(field, new):
    request, value = fixture()
    value["startup"][field] = new
    with pytest.raises(BenchContractError):
        result(request, value)


@pytest.mark.parametrize(
    "opened,closed",
    [
        ("UNKNOWN", "CONFIRMED"),
        ("FAILED", "CONFIRMED"),
        ("NOT_ATTEMPTED", "UNKNOWN"),
        ("SUCCEEDED", "NOT_REQUIRED"),
    ],
)
def test_contradictory_cleanup_rejected(opened, closed):
    request, value = fixture()
    value.update(open_state=opened, close_state=closed)
    with pytest.raises(BenchContractError):
        result(request, value)


def test_failed_open_is_not_a_successful_close():
    request, value = fixture(b"")
    value.update(
        open_state="FAILED",
        close_state="NOT_REQUIRED",
        settings_verified=False,
        observation_complete=False,
        errors=["OPEN_FAILED"],
    )
    summary = result(request, value).summary()
    assert summary["status"] == "FAILED_KNOWN"
    assert summary["reported_port_close_confirmed"] is False


@pytest.mark.parametrize(
    "field,new",
    [
        ("started_monotonic_ns", True),
        ("finished_monotonic_ns", 1),
        ("errors", ["invented"]),
        ("errors", ["CANCELLED", "CANCELLED"]),
        ("settings_verified", 1),
        ("outbound_bytes", False),
    ],
)
def test_strict_types_and_timing(field, new):
    request, value = fixture()
    value[field] = new
    with pytest.raises(BenchContractError):
        result(request, value)


@pytest.mark.parametrize(
    "payload",
    [b"", b"x" * (96 * 1024 + 1), b"[]", b'{"x":1,"x":2}', b'{"x":NaN}'],
    ids=["empty", "oversized", "array", "duplicate", "nonfinite"],
)
def test_bounded_strict_document(payload):
    request, _ = fixture()
    with pytest.raises(BenchContractError):
        PassiveBenchResult(payload, request)
