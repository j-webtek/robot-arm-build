"""Passive request parser only; no serial, registry, process, clock or file I/O."""

from copy import deepcopy
import json

import pytest

from rocell.application.arm_bench_qualification_contract import (
    PassiveBenchRequest,
    BenchContractError,
    SCHEMA,
    PURPOSE,
    _LIMITS,
    _REFERENCE_NAMES,
)


def document():
    return dict(
        schema=SCHEMA,
        purpose=PURPOSE,
        attempt_id="test-attempt",
        launch_id="test-launch",
        mode="rehearsal",
        references={key: "a" * 64 for key in _REFERENCE_NAMES},
        parent_deadline_monotonic_ns=20_000_000_000,
        limits=dict(_LIMITS),
    )


def encoded(value):
    return json.dumps(value).encode()


def test_canonical_detached_bytes_never_imply_admission():
    value = document()
    request = PassiveBenchRequest(encoded(value))
    other = PassiveBenchRequest(json.dumps(value, sort_keys=True, indent=2).encode())
    assert request.request_sha256 == other.request_sha256
    detached = request.to_dict()
    detached["limits"]["maximum_outbound_bytes"] = 100
    assert request.to_dict() == value
    assert request.summary()["references_authenticated"] is False
    assert request.summary()["physical_dispatch_available"] is False
    value["mode"] = "physical"
    summary = PassiveBenchRequest(encoded(value)).summary()
    assert summary["physical_authority"] is summary["connected"] is False


@pytest.mark.parametrize(
    "field", ["command", "port", "force", "physical_authority", "power_disconnected"]
)
def test_no_extra_transport_or_authority_fields(field):
    value = document()
    value[field] = True
    with pytest.raises(BenchContractError):
        PassiveBenchRequest(encoded(value))


@pytest.mark.parametrize("field", sorted(_REFERENCE_NAMES))
def test_each_independent_reference_required(field):
    value = document()
    del value["references"][field]
    with pytest.raises(BenchContractError):
        PassiveBenchRequest(encoded(value))


@pytest.mark.parametrize("field", sorted(_LIMITS))
def test_limits_are_not_caller_configurable(field):
    value = document()
    value["limits"][field] += 1
    with pytest.raises(BenchContractError):
        PassiveBenchRequest(encoded(value))


@pytest.mark.parametrize(
    "payload",
    [b"", b"x" * 8193, b"[]", b"{", b"\xff", b'{"schema":1,"schema":2}', b'{"x":NaN}'],
)
def test_invalid_or_unbounded_json(payload):
    with pytest.raises(BenchContractError):
        PassiveBenchRequest(payload)


def test_bool_not_a_count_or_deadline():
    for field in ("limits", "parent_deadline_monotonic_ns"):
        value = document()
        if field == "limits":
            value[field]["maximum_open_attempts"] = True
        else:
            value[field] = True
        with pytest.raises(BenchContractError):
            PassiveBenchRequest(encoded(value))


def test_absolute_deadline_reserves_cleanup_and_is_not_extended():
    request = PassiveBenchRequest(encoded(document()))
    before = deepcopy(request.to_dict())
    request.require_time_available(13_000_000_000)
    for now in (13_000_000_001, 20_000_000_000, True, 0):
        with pytest.raises(BenchContractError):
            request.require_time_available(now)
    assert request.to_dict() == before
