"""Pure owned IPC contracts; no process, DLL or device is started."""

import ctypes
from dataclasses import replace
import hashlib
import json
import subprocess

import pytest

from rocell.application.physical_connection_contracts import EvidenceOrigin
from rocell.providers.windows.arm_owned_protocol import (
    ADMISSION_TIMEOUT_MS,
    CLEANUP_TIMEOUT_MS,
    LEGACY_REQUEST_SCHEMA,
    PREVIOUS_REQUEST_SCHEMA,
    REQUEST_SCHEMA,
    ArmOwnedChildGate,
    ArmOwnedProtocolError,
    ArmOwnedReady,
    ArmOwnedRequest,
    INCAPABLE_PROVENANCE,
    PHYSICAL_HELD_PROVENANCE,
    build_arm_owned_request,
    build_arm_owned_ready,
    arm_owned_release,
    parse_arm_owned_ready,
    build_arm_owned_result,
    parse_arm_owned_result,
)
from test_arm_feedback_worker import Clock, _request


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def make_request(
    *,
    origin=EvidenceOrigin.SYNTHETIC_REHEARSAL,
    scenario="nominal",
    native_identity=True,
):
    clock = Clock()
    original = _request(clock, origin=origin)
    if native_identity and origin is EvidenceOrigin.SYNTHETIC_REHEARSAL:
        from rocell.providers.windows.incapable_controller_metadata import (
            synthetic_native_identity,
        )

        identity = synthetic_native_identity(original.controller)
        original = replace(
            original,
            controller=replace(original.controller, identity=identity),
            feedback=replace(
                original.feedback, arm_identity_sha256=identity.identity_sha256
            ),
        )
    inner = replace(
        original,
        campaign_id="attempt-" + "a" * 32,
        feedback=replace(original.feedback, run_id="rehearsal-" + "b" * 32),
    )
    request = build_arm_owned_request(
        session_id=inner.feedback.run_id,
        attempt_id=inner.campaign_id,
        source_sha256=inner.source_sha256,
        operation_sha256=inner.operation_sha256,
        permit_sha256=inner.feedback.safety_permit_sha256,
        selected_identity_sha256=inner.controller.identity.identity_sha256,
        worker_registration_sha256="c" * 64,
        feedback_request=inner,
        provenance=(
            INCAPABLE_PROVENANCE
            if origin is EvidenceOrigin.SYNTHETIC_REHEARSAL
            else PHYSICAL_HELD_PROVENANCE
        ),
        scenario=scenario,
        parent_deadline_monotonic_ns=clock.value + 20_000_000_000,
    )
    return request, inner, clock


def rehash(document):
    document["request_sha256"] = hashlib.sha256(
        canonical({k: v for k, v in document.items() if k != "request_sha256"})
    ).hexdigest()
    return canonical(document)


@pytest.fixture(autouse=True)
def forbid_devices_and_processes(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("pure IPC test attempted native/process access")

    monkeypatch.setattr(ctypes, "WinDLL", forbidden, raising=False)
    monkeypatch.setattr(subprocess, "Popen", forbidden)


def test_request_is_exact_bytes_backed_and_defensive():
    request, inner, _ = make_request()
    assert request.feedback_request == inner
    assert request.wire() == request.payload + b"\n"
    document = request.to_dict()
    document["source_sha256"] = "d" * 64
    assert request.to_dict()["source_sha256"] == inner.source_sha256
    assert ArmOwnedRequest(request.payload) == request


def test_new_version_binds_five_seconds_without_changing_other_deadlines():
    from rocell.providers.windows.native_camera_protocol import (
        ADMISSION_TIMEOUT_MS as CAMERA_ADMISSION_TIMEOUT_MS,
    )

    request, inner, clock = make_request()
    document = request.to_dict()
    assert document["schema"] == REQUEST_SCHEMA == "rocell.arm_owned_request.v3"
    assert document["admission_timeout_ms"] == ADMISSION_TIMEOUT_MS == 5000
    assert document["cleanup_timeout_ms"] == CLEANUP_TIMEOUT_MS == 2000
    assert CAMERA_ADMISSION_TIMEOUT_MS == 2000
    assert document["parent_deadline_monotonic_ns"] == clock.value + 20_000_000_000
    assert request.feedback_request == inner


@pytest.mark.parametrize(
    "schema,duration",
    [
        (LEGACY_REQUEST_SCHEMA, 5000),
        (REQUEST_SCHEMA, 2000),
        (PREVIOUS_REQUEST_SCHEMA, 2000),
        ("rocell.arm_owned_request.v4", 5000),
    ],
)
def test_version_cannot_borrow_another_admission_budget_even_rehashed(schema, duration):
    request, _, _ = make_request()
    document = request.to_dict()
    document.update(schema=schema, admission_timeout_ms=duration)
    with pytest.raises(ArmOwnedProtocolError):
        ArmOwnedRequest(rehash(document))


@pytest.mark.parametrize(
    "schema,duration,delay,accepted",
    [
        (REQUEST_SCHEMA, 5000, 3_000_000_000, True),
        (REQUEST_SCHEMA, 5000, 4_999_999_999, True),
        (REQUEST_SCHEMA, 5000, 5_000_000_000, False),
    ],
)
def test_current_gate_keeps_original_bound(schema, duration, delay, accepted):
    request, inner, clock = make_request()
    document = request.to_dict()
    document.update(schema=schema, admission_timeout_ms=duration)
    historical = ArmOwnedRequest(rehash(document))
    assert historical.feedback_request == inner
    assert (
        historical.to_dict()["parent_deadline_monotonic_ns"]
        == document["parent_deadline_monotonic_ns"]
    )
    gate = ArmOwnedChildGate(
        historical,
        child_pid=1234,
        challenge_sha256="d" * 64,
        started_monotonic_ns=clock.value,
    )
    release = arm_owned_release(historical, gate.ready)
    if accepted:
        gate.accept_release(release, now_ns=clock.value + delay, stdin_eof=True)
    else:
        with pytest.raises(ArmOwnedProtocolError):
            gate.accept_release(release, now_ns=clock.value + delay, stdin_eof=True)
    with pytest.raises(ArmOwnedProtocolError, match="ALREADY"):
        gate.accept_release(release, now_ns=clock.value + 1, stdin_eof=True)


@pytest.mark.parametrize(
    "schema,duration",
    [
        (LEGACY_REQUEST_SCHEMA, 2000),
        (PREVIOUS_REQUEST_SCHEMA, 5000),
    ],
)
def test_historical_requests_remain_readable_but_gate_never_re_admits(schema, duration):
    request, inner, clock = make_request()
    doc = request.to_dict()
    doc.update(schema=schema, admission_timeout_ms=duration)
    historical = ArmOwnedRequest(rehash(doc))
    assert historical.feedback_request == inner
    assert historical.to_dict()["admission_timeout_ms"] == duration
    with pytest.raises(ArmOwnedProtocolError, match="ARM_REQUEST_VERSION_HELD"):
        ArmOwnedChildGate(
            historical,
            child_pid=1234,
            challenge_sha256="d" * 64,
            started_monotonic_ns=clock.value,
        )
    with pytest.raises(ArmOwnedProtocolError, match="ARM_REQUEST_VERSION_HELD"):
        build_arm_owned_result(historical)


@pytest.mark.parametrize("scenario", ["identity-change-preopen", "malformed-metadata"])
@pytest.mark.parametrize(
    "schema,duration",
    [
        (LEGACY_REQUEST_SCHEMA, 2000),
        (PREVIOUS_REQUEST_SCHEMA, 5000),
    ],
)
def test_new_fault_roster_does_not_mutate_historical_request_contract(
    schema, duration, scenario
):
    request, _, _ = make_request(scenario=scenario)
    doc = request.to_dict()
    doc.update(schema=schema, admission_timeout_ms=duration)
    with pytest.raises(ArmOwnedProtocolError):
        ArmOwnedRequest(rehash(doc))


def test_five_second_release_wait_never_renews_original_parent_lifetime():
    request, inner, clock = make_request()
    document = request.to_dict()
    document["parent_deadline_monotonic_ns"] = clock.value + 10_000_000_000
    request = ArmOwnedRequest(rehash(document))
    assert inner.budget.duration_ms == 5000
    gate = ArmOwnedChildGate(
        request,
        child_pid=1234,
        challenge_sha256="d" * 64,
        started_monotonic_ns=clock.value,
    )
    # Four seconds is within the new wait, but 4 + 5 inner + 2 cleanup exceeds
    # the original ten-second deadline. No new expiry may be substituted.
    with pytest.raises(ArmOwnedProtocolError, match="FULL_LIFETIME_EXPIRED"):
        gate.accept_release(
            arm_owned_release(request, gate.ready),
            now_ns=clock.value + 4_000_000_000,
            stdin_eof=True,
        )
    assert (
        request.to_dict()["parent_deadline_monotonic_ns"]
        == clock.value + 10_000_000_000
    )


def test_child_ready_is_the_original_read_only_identity_challenge():
    request, _, clock = make_request()
    gate = ArmOwnedChildGate(
        request,
        child_pid=123,
        challenge_sha256="a" * 64,
        started_monotonic_ns=clock.value,
    )
    original = gate.ready
    with pytest.raises(AttributeError):
        gate.ready = build_arm_owned_ready(
            request, child_pid=456, challenge_sha256="b" * 64
        )
    detached = gate.ready.to_dict()
    detached["child_pid"] = 456
    assert gate.ready == original
    gate.accept_release(
        arm_owned_release(request, original), now_ns=clock.value, stdin_eof=True
    )


@pytest.mark.parametrize(
    "field",
    [
        "source_sha256",
        "operation_sha256",
        "permit_sha256",
        "selected_identity_sha256",
        "session_id",
        "attempt_id",
        "provenance",
        "scenario",
        "physical_authority",
        "admission_timeout_ms",
        "cleanup_timeout_ms",
        "parent_deadline_monotonic_ns",
    ],
)
def test_request_rejects_binding_or_fixed_field_substitution_even_rehashed(field):
    request, _, _ = make_request()
    document = request.to_dict()
    replacement = {
        "provenance": PHYSICAL_HELD_PROVENANCE,
        "scenario": "raw-command",
        "physical_authority": True,
        "admission_timeout_ms": True,
        "cleanup_timeout_ms": 0,
        "parent_deadline_monotonic_ns": 2**63 - 1,
        "session_id": "different",
        "attempt_id": "different",
    }.get(field, "d" * 64)
    document[field] = replacement
    with pytest.raises((ArmOwnedProtocolError, ValueError, RuntimeError)):
        ArmOwnedRequest(rehash(document))


@pytest.mark.parametrize(
    "mutation",
    [
        "extra",
        "duplicate",
        "newline",
        "pretty",
        "oversize",
        "hash",
        "fixed-command",
        "line-limit",
    ],
)
def test_request_rejects_malformed_and_unbounded_documents(mutation):
    request, _, _ = make_request()
    document = request.to_dict()
    if mutation == "extra":
        document["raw_command"] = {"T": 104}
        payload = rehash(document)
    elif mutation == "duplicate":
        payload = request.payload[:-1] + b',"schema":"rocell.arm_owned_request.v1"}'
    elif mutation == "newline":
        payload = request.wire()
    elif mutation == "pretty":
        payload = json.dumps(document, indent=2).encode()
    elif mutation == "oversize":
        payload = b" " * (60 * 1024 + 1)
    elif mutation == "hash":
        document["request_sha256"] = "d" * 64
        payload = canonical(document)
    else:
        if mutation == "fixed-command":
            document["feedback_request"]["wire_request_type"] = 104
        else:
            document["feedback_request"]["feedback"]["maximum_line_bytes"] = 2049
        payload = rehash(document)
    with pytest.raises((ArmOwnedProtocolError, ValueError, RuntimeError)):
        ArmOwnedRequest(payload)


def test_actual_pid_challenge_release_and_eof_are_one_use_without_io():
    request, _, clock = make_request()
    gate = ArmOwnedChildGate(
        request,
        child_pid=1234,
        challenge_sha256="d" * 64,
        started_monotonic_ns=clock.value,
    )
    ready = parse_arm_owned_ready(
        gate.ready.wire(),
        expected_request_sha256=request.request_sha256,
        expected_child_pid=1234,
    )
    release = arm_owned_release(request, ready)
    gate.accept_release(release, now_ns=clock.value + 1, stdin_eof=True)
    with pytest.raises(ArmOwnedProtocolError, match="ALREADY"):
        gate.accept_release(release, now_ns=clock.value + 2, stdin_eof=True)


@pytest.mark.parametrize(
    "defect",
    [
        "pid",
        "challenge",
        "request",
        "permit",
        "ready-hash",
        "deadline",
        "extra",
        "eof",
        "late",
        "regressed",
        "trailing",
    ],
)
def test_failed_release_cannot_be_retried(defect):
    request, _, clock = make_request()
    gate = ArmOwnedChildGate(
        request,
        child_pid=1234,
        challenge_sha256="d" * 64,
        started_monotonic_ns=clock.value,
    )
    release = arm_owned_release(request, gate.ready)
    wire = release
    now = clock.value + 1
    eof = True
    if defect in {
        "pid",
        "challenge",
        "request",
        "permit",
        "ready-hash",
        "deadline",
        "extra",
    }:
        doc = json.loads(wire)
        key = {
            "pid": "child_pid",
            "challenge": "challenge_sha256",
            "request": "request_sha256",
            "permit": "permit_sha256",
            "ready-hash": "ready_sha256",
            "deadline": "parent_deadline_monotonic_ns",
            "extra": "extra",
        }[defect]
        doc[key] = 999 if defect in {"pid", "deadline"} else "e" * 64
        wire = canonical(doc) + b"\n"
    elif defect == "eof":
        eof = False
    elif defect == "late":
        now = clock.value + ADMISSION_TIMEOUT_MS * 1_000_000
    elif defect == "regressed":
        now = clock.value - 1
    else:
        wire += b"{}\n"
    with pytest.raises(ArmOwnedProtocolError):
        gate.accept_release(wire, now_ns=now, stdin_eof=eof)
    with pytest.raises(ArmOwnedProtocolError, match="ALREADY"):
        gate.accept_release(release, now_ns=clock.value + 2, stdin_eof=True)


def test_ready_requires_owned_pid_not_a_label_or_boolean():
    request, _, _ = make_request()
    ready = build_arm_owned_ready(request, child_pid=1234, challenge_sha256="d" * 64)
    for pid in (1235, True, 0):
        with pytest.raises(ArmOwnedProtocolError):
            parse_arm_owned_ready(
                ready.wire(),
                expected_request_sha256=request.request_sha256,
                expected_child_pid=pid,
            )
    with pytest.raises(ArmOwnedProtocolError):
        ArmOwnedReady(ready.payload + b" ")


def test_physical_request_is_distinct_and_never_releases_worker():
    request, _, clock = make_request(
        origin=EvidenceOrigin.PHYSICAL_OBSERVATION, scenario="physical-held"
    )
    gate = ArmOwnedChildGate(
        request,
        child_pid=1234,
        challenge_sha256="d" * 64,
        started_monotonic_ns=clock.value,
    )
    with pytest.raises(ArmOwnedProtocolError, match="ACTIVATION_HELD"):
        gate.accept_release(
            arm_owned_release(request, gate.ready),
            now_ns=clock.value + 1,
            stdin_eof=True,
        )
    held = build_arm_owned_result(request)
    assert (
        parse_arm_owned_result(
            held.wire(), expected_request=request, returncode=2
        ).feedback_evidence
        is None
    )
    assert held.native_evidence is None
    with pytest.raises(ArmOwnedProtocolError):
        parse_arm_owned_result(held.wire(), expected_request=request, returncode=0)
