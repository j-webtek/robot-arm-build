"""Every serial API in these tests is incapable memory, never a COM device."""

from __future__ import annotations

from dataclasses import replace
import importlib
import json
from types import SimpleNamespace
from threading import Event
from typing import Any

import pytest

from rocell.application.physical_connection_contracts import (
    EvidenceOrigin,
    RoArmUsbSerialIdentity,
    SingleT105FeedbackRequest,
    UsbDriverIdentity,
)
from rocell.providers.windows.arm_feedback_worker import (
    ArmFeedbackBudget,
    ArmFeedbackCampaignRequest,
    ArmFeedbackOutcome,
    ArmFeedbackWorker,
    ArmFeedbackWorkerError,
    IncapableSerialBackend,
    IncapableSerialScenario,
    PHYSICAL_HOLD,
    ReviewedControllerBinding,
    WindowsPySerialBackend,
    parse_arm_feedback_request,
    rehearse_arm_feedback_campaign,
)


class Clock:
    def __init__(self) -> None:
        self.value = 1_000_000_000

    def __call__(self) -> int:
        self.value += 1
        return self.value

    def wait(self, event: Event, seconds: float) -> bool:
        assert 0 <= seconds <= 0.01
        self.value += int(seconds * 1_000_000_000)
        return event.is_set()


def _request(
    clock: Clock, *, origin: EvidenceOrigin = EvidenceOrigin.SYNTHETIC_REHEARSAL
) -> ArmFeedbackCampaignRequest:
    identity = RoArmUsbSerialIdentity(
        "ffff",
        "0002",
        "SYNTHETIC-NOT-PHYSICAL",
        "USB\\VID_FFFF&PID_0002\\SYNTHETIC-NOT-PHYSICAL",
        "usb-unit:ffff:0002:SYNTHETIC-NOT-PHYSICAL",
        "COM404",
        UsbDriverIdentity("SYNTHETIC", "synthetic", "1.0", "synthetic-driver.inf"),
    )
    binding = ReviewedControllerBinding(
        identity, "1" * 64, "2" * 64, "3" * 64, "4" * 64, "5" * 64, origin
    )
    feedback = SingleT105FeedbackRequest(
        "rehearsal-test",
        binding.identity_receipt_sha256,
        identity.identity_sha256,
        "6" * 64,
        "7" * 64,
        "controller-session-fixture",
        clock.value,
        maximum_line_bytes=2048,
    )
    return ArmFeedbackCampaignRequest(
        "campaign-fixture",
        "8" * 64,
        "9" * 64,
        "a" * 64,
        binding,
        feedback,
        clock.value + 30_000_000_000,
    )


def _worker(
    *,
    scenario: IncapableSerialScenario = IncapableSerialScenario(),
    authorizer: Any = None,
    identity_resolver: Any = None,
) -> tuple[
    ArmFeedbackWorker,
    IncapableSerialBackend,
    Clock,
    ArmFeedbackCampaignRequest,
    list[str],
]:
    clock = Clock()
    request = _request(clock)
    backend = IncapableSerialBackend(scenario)
    calls: list[str] = []

    def authorize(exact: ArmFeedbackCampaignRequest) -> None:
        assert exact is request
        calls.append("authorized-exact-once")

    worker = ArmFeedbackWorker(
        authorizer=authorize if authorizer is None else authorizer,
        identity_resolver=(
            (lambda expected: expected)
            if identity_resolver is None
            else identity_resolver
        ),
        backend=backend,
        monotonic_ns=clock,
        wait=clock.wait,
    )
    return worker, backend, clock, request, calls


def test_constructor_and_status_never_import_serial_or_resolve_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("construction/status must be inert")

    monkeypatch.setattr(importlib, "import_module", forbidden)
    worker = ArmFeedbackWorker(authorizer=forbidden, identity_resolver=forbidden)
    assert worker.status()["phase"] == "IDLE"
    assert worker.status()["physical_hold"] == PHYSICAL_HOLD
    assert worker.status()["hardware_accessed_by_status"] is False
    assert not worker.status()["consumed"]


def test_native_backend_stays_held_even_with_noop_authorizer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def no_native_import(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("physical qualification hold must precede native imports")

    monkeypatch.setattr(importlib, "import_module", no_native_import)
    clock = Clock()
    calls: list[str] = []
    worker = ArmFeedbackWorker(
        authorizer=lambda request: calls.append("unsafe-noop"),
        identity_resolver=lambda identity: calls.append("identity"),
        monotonic_ns=clock,
        wait=clock.wait,
    )
    result = worker.run(_request(clock, origin=EvidenceOrigin.PHYSICAL_OBSERVATION))
    assert result.outcome is ArmFeedbackOutcome.BLOCKED_PRE_OPEN
    assert result.primary_error and result.primary_error.code == PHYSICAL_HOLD
    assert result.api_counts.object_creations == 0 and not calls
    with pytest.raises(ArmFeedbackWorkerError, match=PHYSICAL_HOLD):
        WindowsPySerialBackend().create_closed()


def test_nominal_exact_wire_preopen_settings_identity_and_close_accounting() -> None:
    worker, backend, _, request, calls = _worker()
    result = worker.run(request)
    assert result.outcome is ArmFeedbackOutcome.SUCCEEDED_DIAGNOSTIC
    assert calls == ["authorized-exact-once"]
    assert result.feedback_receipt is not None
    assert result.feedback_receipt.request_bytes == b'{"T":105}\n'
    assert result.api_counts.open_attempts == result.api_counts.opens_confirmed == 1
    assert result.api_counts.write_attempts == result.api_counts.writes_confirmed == 1
    assert result.api_counts.close_attempts == result.api_counts.closes_confirmed == 1
    assert result.api_counts.identity_checks == 2
    trace = list(backend.trace)
    opened = trace.index(("open", None))
    for setting in (
        ("set:rts", False),
        ("set:dtr", False),
        ("set:baudrate", 115200),
        ("set:bytesize", 8),
        ("set:parity", "N"),
        ("set:stopbits", 1),
        ("set:xonxoff", False),
        ("set:rtscts", False),
        ("set:dsrdtr", False),
        ("set:write_timeout", 1.0),
    ):
        assert trace.index(setting) < opened
    assert [value for action, value in trace if action == "write"] == [b'{"T":105}\n']
    assert trace[-1] == ("close", None)
    projection = result.to_dict()
    assert all(count == 0 for count in projection["physical_operation_counts"].values())
    assert projection["physical_authority"] is False
    assert projection["final_power_state"] == "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION"
    assert projection["feedback"]["x_mm"] == 120
    assert projection["installed_firmware_proven_by_packet"] is False
    assert not result.effect_uncertain
    assert worker.status()["consumed"]


def test_worker_is_one_use_after_success_and_failure() -> None:
    for scenario in (
        IncapableSerialScenario(),
        IncapableSerialScenario(fail_at=("open",)),
    ):
        worker, backend, _, request, _ = _worker(scenario=scenario)
        worker.run(request)
        trace = backend.trace
        for duplicate in (request, replace(request, campaign_id="different-request")):
            with pytest.raises(ArmFeedbackWorkerError, match="CAMPAIGN_ALREADY_USED"):
                worker.run(duplicate)
        assert backend.trace == trace


@pytest.mark.parametrize("dirty", [b"ets ESP32 reset banner\n", b'{"T":1051,"x":99}\n'])
@pytest.mark.parametrize("delayed", [False, True])
def test_boot_or_stale_valid_bytes_are_retained_without_any_write(
    dirty: bytes, delayed: bool
) -> None:
    scenario = IncapableSerialScenario(
        **{"delayed_preexisting_bytes" if delayed else "preexisting_bytes": dirty}
    )
    worker, backend, _, request, _ = _worker(scenario=scenario)
    result = worker.run(request)
    assert result.outcome is ArmFeedbackOutcome.FAILED_UNCERTAIN
    assert (
        result.primary_error
        and result.primary_error.code == "STALE_OR_EXTRA_BUFFERED_BYTES"
    )
    assert result.unexpected_bytes == dirty
    assert (
        result.api_counts.write_attempts == 0 and result.api_counts.close_attempts == 1
    )
    assert not any(action == "write" for action, _ in backend.trace)
    assert result.effect_uncertain


@pytest.mark.parametrize("phase", ["configure", "open", "buffer", "write", "read"])
def test_primary_and_cleanup_failures_are_both_retained(phase: str) -> None:
    worker, _, _, request, _ = _worker(
        scenario=IncapableSerialScenario(fail_at=(phase, "close"))
    )
    result = worker.run(request)
    assert result.primary_error is not None and result.cleanup_errors
    assert result.cleanup_errors[0].code == "SERIAL_CLOSE_FAILED"
    assert (
        result.api_counts.close_attempts == 1
        and result.api_counts.closes_confirmed == 0
    )
    assert result.api_counts.write_attempts <= 1
    assert result.feedback_receipt is None


@pytest.mark.parametrize(
    "reply,code",
    [
        (b"", "RESPONSE_TIMEOUT_OR_TRUNCATED"),
        (b'{"T":1051,"x":1}', "RESPONSE_TIMEOUT_OR_TRUNCATED"),
        (b"ets unexpected reset\n", "RESET_BANNER"),
        (b'{"T":104,"x":1}\n', "WRONG_RESPONSE_TYPE"),
        (b'{"T":1051,"T":1051}\n', "MALFORMED_JSON"),
        (b'{"T":1051,"x":true}\n', "INVALID_TYPED_FEEDBACK"),
        (b'{"T":1051,"x":NaN}\n', "MALFORMED_JSON"),
        (b'{"T":true}\n', "MALFORMED_JSON"),
        (b"\xff\n", "MALFORMED_JSON"),
        (b'{"T":1051}\n{"T":1051}\n', "MALFORMED_JSON"),
    ],
)
def test_strict_shared_wire_validator_and_no_retry(reply: bytes, code: str) -> None:
    worker, backend, _, request, _ = _worker(
        scenario=IncapableSerialScenario(response_bytes=reply)
    )
    result = worker.run(request)
    assert result.outcome is ArmFeedbackOutcome.FAILED_UNCERTAIN
    assert result.primary_error and result.primary_error.code == code
    assert result.response_bytes == reply
    assert (
        result.api_counts.write_attempts == 1 and result.api_counts.close_attempts == 1
    )
    assert result.feedback_receipt is None
    assert len([action for action, _ in backend.trace if action == "write"]) == 1


@pytest.mark.parametrize("written", [0, 1, 9, 11])
def test_short_or_oversized_write_count_never_causes_a_second_write(
    written: int,
) -> None:
    worker, _, _, request, _ = _worker(
        scenario=IncapableSerialScenario(short_write_count=written)
    )
    result = worker.run(request)
    assert (
        result.primary_error and result.primary_error.code == "SHORT_OR_AMBIGUOUS_WRITE"
    )
    assert (
        result.api_counts.write_attempts == 1 and result.api_counts.read_attempts == 0
    )
    assert result.api_counts.closes_confirmed == 1


def test_identity_changed_after_open_prevents_write() -> None:
    checks = 0

    def changed_identity(expected: RoArmUsbSerialIdentity) -> RoArmUsbSerialIdentity:
        nonlocal checks
        checks += 1
        return expected if checks == 1 else replace(expected, port_name="COM405")

    worker, _, _, request, _ = _worker(identity_resolver=changed_identity)
    result = worker.run(request)
    assert (
        result.primary_error
        and result.primary_error.code == "CONTROLLER_IDENTITY_CHANGED"
    )
    assert (
        result.api_counts.open_attempts == 1 and result.api_counts.write_attempts == 0
    )
    assert result.connection_closed and result.effect_uncertain


def test_identity_changed_before_open_never_constructs_serial_object() -> None:
    worker, backend, _, request, _ = _worker(
        identity_resolver=lambda expected: replace(
            expected, unit_serial="different-unit"
        )
    )
    result = worker.run(request)
    assert result.outcome is ArmFeedbackOutcome.BLOCKED_PRE_OPEN
    assert not backend.trace and result.api_counts.object_creations == 0


def test_cancel_before_open_and_during_quiet_observation() -> None:
    worker, backend, _, request, _ = _worker()
    cancel = Event()
    cancel.set()
    before = worker.run(request, cancellation=cancel)
    assert before.outcome is ArmFeedbackOutcome.CANCELLED_PRE_OPEN
    assert not backend.trace
    worker, backend, clock, request, _ = _worker()
    cancel = Event()

    def wait_then_cancel(event: Event, seconds: float) -> bool:
        clock.wait(event, seconds)
        event.set()
        return True

    worker = ArmFeedbackWorker(
        authorizer=lambda request: None,
        identity_resolver=lambda identity: identity,
        backend=backend,
        monotonic_ns=clock,
        wait=wait_then_cancel,
    )
    during = worker.run(request, cancellation=cancel)
    assert during.outcome is ArmFeedbackOutcome.FAILED_UNCERTAIN
    assert during.api_counts.write_attempts == 0 and during.connection_closed


def test_expired_and_denied_campaigns_have_no_serial_objects() -> None:
    worker, backend, clock, request, _ = _worker()
    clock.value = request.expires_monotonic_ns
    assert worker.run(request).outcome is ArmFeedbackOutcome.BLOCKED_PRE_OPEN
    assert not backend.trace

    def deny(exact: ArmFeedbackCampaignRequest) -> None:
        raise PermissionError("denied secret must not leak")

    worker, backend, _, request, _ = _worker(authorizer=deny)
    result = worker.run(request)
    assert result.api_counts.object_creations == 0 and not backend.trace
    assert "secret" not in json.dumps(result.to_dict())
    worker, backend, _, request, _ = _worker(authorizer=lambda request: True)
    result = worker.run(request)
    assert (
        result.primary_error and result.primary_error.code == "INVALID_AUTHORIZER_ACK"
    )
    assert not backend.trace


def test_response_byte_and_read_call_budgets_fail_closed() -> None:
    worker, _, _, request, _ = _worker(
        scenario=IncapableSerialScenario(response_bytes=b"x" * 4000 + b"\n")
    )
    result = worker.run(request)
    assert len(result.response_bytes) == request.feedback.maximum_line_bytes + 1
    assert result.api_counts.write_attempts == 1 and result.connection_closed
    worker, _, _, request, _ = _worker(
        scenario=IncapableSerialScenario(read_fragment_bytes=1),
        authorizer=lambda exact: None,
    )
    request = replace(request, budget=ArmFeedbackBudget(maximum_read_calls=2))
    # This separate fixture authorizer checks the full replacement request.
    result = worker.run(request)
    assert (
        result.primary_error
        and result.primary_error.code == "READ_CALL_BUDGET_EXCEEDED"
    )
    assert result.api_counts.read_attempts == 2 and len(result.response_bytes) == 2


def test_extra_response_suffix_is_not_a_successful_packet() -> None:
    line = b'{"T":1051}\n'
    worker, _, _, request, _ = _worker(
        scenario=IncapableSerialScenario(
            response_bytes=line + b"junk", read_fragment_bytes=len(line)
        )
    )
    result = worker.run(request)
    assert (
        result.primary_error
        and result.primary_error.code == "STALE_OR_EXTRA_BUFFERED_BYTES"
    )
    assert result.response_bytes == line and result.unexpected_bytes == b"junk"
    assert result.feedback_receipt is None and result.connection_closed


def test_close_unconfirmed_and_factory_already_open_are_uncertain() -> None:
    for scenario in (
        IncapableSerialScenario(close_remains_open=True),
        IncapableSerialScenario(already_open=True),
    ):
        worker, _, _, request, _ = _worker(scenario=scenario)
        result = worker.run(request)
        assert result.outcome is ArmFeedbackOutcome.FAILED_UNCERTAIN
        assert result.effect_uncertain and result.feedback_receipt is None
        assert result.api_counts.close_attempts == 1


def test_raw_boot_secrets_and_unknown_reply_fields_are_not_in_status_projection() -> (
    None
):
    worker, _, _, request, _ = _worker(
        scenario=IncapableSerialScenario(preexisting_bytes=b"password=DO-NOT-LOG\n")
    )
    result = worker.run(request)
    assert result.unexpected_bytes == b"password=DO-NOT-LOG\n"
    assert "DO-NOT-LOG" not in json.dumps(result.to_dict())
    assert result.unexpected_bytes.hex() not in json.dumps(result.to_dict())
    worker, _, _, request, _ = _worker(
        scenario=IncapableSerialScenario(
            response_bytes=b'{"T":1051,"password":"DO-NOT-LOG"}\n'
        )
    )
    result = worker.run(request)
    assert result.feedback_receipt is not None
    assert b"DO-NOT-LOG" in result.feedback_receipt.response_bytes
    assert "DO-NOT-LOG" not in json.dumps(result.to_dict())


def test_contracts_reject_unknown_fields_wrong_identity_and_provenance() -> None:
    clock = Clock()
    request = _request(clock)
    with pytest.raises(TypeError):
        ArmFeedbackBudget(allow_hardware=True)
    with pytest.raises(ArmFeedbackWorkerError):
        replace(
            request,
            controller=replace(
                request.controller,
                identity=replace(
                    request.controller.identity, port_name="rfc2217://host:1234"
                ),
            ),
        )
    with pytest.raises(ArmFeedbackWorkerError):
        replace(
            request, feedback=replace(request.feedback, arm_identity_sha256="f" * 64)
        )
    with pytest.raises(ArmFeedbackWorkerError):
        replace(request, expires_monotonic_ns=True)
    with pytest.raises(ArmFeedbackWorkerError):
        ArmFeedbackWorker(authorizer=None, identity_resolver=lambda identity: identity)

    class PretendNativeBackend:
        composition = "HARDWARE_INCAPABLE_REHEARSAL"

    with pytest.raises(ArmFeedbackWorkerError):
        ArmFeedbackWorker(
            authorizer=lambda request: None,
            identity_resolver=lambda identity: identity,
            backend=PretendNativeBackend(),
        )
    backend = IncapableSerialBackend()
    with pytest.raises(AttributeError):
        backend.origin = EvidenceOrigin.PHYSICAL_OBSERVATION
    worker = ArmFeedbackWorker(
        authorizer=lambda request: None,
        identity_resolver=lambda identity: identity,
        backend=backend,
        monotonic_ns=clock,
        wait=clock.wait,
    )
    result = worker.run(_request(clock, origin=EvidenceOrigin.PHYSICAL_OBSERVATION))
    assert result.primary_error and result.primary_error.code == "PROVENANCE_MISMATCH"
    assert not backend.trace


def test_no_motion_initialization_reset_or_raw_command_surface() -> None:
    worker, _, _, _, _ = _worker()
    for name in (
        "connect",
        "send",
        "write",
        "initialize",
        "reset",
        "send_motion",
        "torque",
        "park",
        "home",
    ):
        assert not hasattr(worker, name)


def test_process_request_roundtrip_and_closed_malformed_json_cases() -> None:
    request = _request(Clock())
    encoded = json.dumps(request.to_dict(), indent=2).encode()
    restored = parse_arm_feedback_request(encoded)
    assert restored == request and restored.request_sha256 == request.request_sha256
    for mutation in (
        "extra",
        "identity-constant",
        "settings-float",
        "command",
        "profile",
    ):
        document = request.to_dict()
        if mutation == "extra":
            document["allow_hardware"] = True
        elif mutation == "identity-constant":
            document["controller"]["identity"]["controller"] = "other-controller"
        elif mutation == "settings-float":
            document["serial_settings"]["baudrate"] = 115200.0
        elif mutation == "command":
            document["wire_request_type"] = 104
        else:
            document["controller"]["serial_profile_sha256"] = None
        with pytest.raises(ArmFeedbackWorkerError):
            parse_arm_feedback_request(json.dumps(document).encode())
    for malformed in (
        b"",
        b"x" * 65537,
        b"[]",
        b"\xff",
        b'{"schema":NaN}',
        b'{"schema":"rocell.arm_feedback_campaign.v1","schema":"duplicate"}',
    ):
        with pytest.raises(ArmFeedbackWorkerError):
            parse_arm_feedback_request(malformed)


def test_native_unopened_constructor_code_uses_no_endpoint_when_exercised_with_fake_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import rocell.providers.windows.arm_feedback_worker as module

    calls: list[Any] = []
    unopened = object()

    def fake_serial(*, port: None) -> object:
        assert port is None
        calls.append("closed-object-only")
        return unopened

    # Test-only source substitution exercises the code below the permanent
    # release hold; the imported module and factory are wholly in-memory.
    monkeypatch.setattr(
        module, "_require_independent_physical_qualification", lambda: None
    )
    monkeypatch.setattr(module.os, "name", "nt")

    def fake_import(name: str) -> Any:
        assert name == "serial"
        return SimpleNamespace(VERSION="3.5", Serial=fake_serial)

    monkeypatch.setattr(importlib, "import_module", fake_import)
    assert WindowsPySerialBackend().create_closed() is unopened
    assert calls == ["closed-object-only"]


def test_cancellation_immediately_after_write_preserves_one_write_and_closes() -> None:
    clock = Clock()
    request = _request(clock)
    backend = IncapableSerialBackend()
    cancel = Event()

    def cancel_after_write() -> int:
        if any(action == "write" for action, _ in backend.trace):
            cancel.set()
        return clock()

    worker = ArmFeedbackWorker(
        authorizer=lambda request: None,
        identity_resolver=lambda expected: expected,
        backend=backend,
        monotonic_ns=cancel_after_write,
        wait=clock.wait,
    )
    result = worker.run(request, cancellation=cancel)
    assert result.effect_uncertain and result.connection_closed
    assert (
        result.api_counts.write_attempts == 1 and result.api_counts.read_attempts == 0
    )
    assert result.primary_error and result.primary_error.code == "CANCELLED"


def test_quiet_deadline_and_frozen_clock_are_bounded() -> None:
    for stuck in (True, False):
        clock = Clock()
        request = _request(clock)
        backend = IncapableSerialBackend()

        def wait(event: Event, seconds: float) -> bool:
            if not stuck:
                clock.value += 10_000_000_000
            return False

        worker = ArmFeedbackWorker(
            authorizer=lambda request: None,
            identity_resolver=lambda expected: expected,
            backend=backend,
            monotonic_ns=clock,
            wait=wait,
        )
        result = worker.run(request)
        assert result.primary_error and result.primary_error.code == (
            "QUIET_WINDOW_INCOMPLETE" if stuck else "CAMPAIGN_DEADLINE_EXCEEDED"
        )
        assert (
            result.api_counts.write_attempts == 0
            and result.api_counts.close_attempts == 1
        )
        assert len(backend.trace) < 160


def test_unexpected_prefix_omissions_and_malformed_read_are_explicit() -> None:
    worker, _, _, request, _ = _worker(
        scenario=IncapableSerialScenario(preexisting_bytes=b"b" * 4000)
    )
    result = worker.run(request)
    assert result.unexpected_bytes == b"b" * 256
    assert result.unexpected_bytes_unretained == 3744
    assert result.api_counts.write_attempts == 0
    worker, _, _, request, _ = _worker(
        scenario=IncapableSerialScenario(read_returns_nonbytes=True)
    )
    result = worker.run(request)
    assert result.primary_error and result.primary_error.code == "INVALID_SERIAL_READ"
    assert result.api_counts.write_attempts == 1 and result.connection_closed


@pytest.mark.parametrize(
    "scenario",
    [
        "nominal",
        "boot-bytes",
        "short-write",
        "timeout",
        "identity-change",
        "close-failure",
    ],
)
def test_closed_public_rehearsal_scenarios_match_without_hardware(
    scenario: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden_import(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("closed rehearsal must not import a native provider")

    monkeypatch.setattr(importlib, "import_module", forbidden_import)
    report = rehearse_arm_feedback_campaign(scenario)
    assert report["expected_outcome_matched"] is True
    assert report["physical_authority"] is False and report["arm_connected"] is False
    assert all(value == 0 for value in report["actual_effect_counts"].values())
    assert report["observed"]["serial_api_counts"]["write_attempts"] <= 1
    assert "PYSERIAL_WINDOWS_OPEN_PURGES_INPUT" in str(report["observed"]["limits"])
    assert "PROCESS_CONTAINMENT_NOT_QUALIFIED" in report["observed"]["limits"]
    assert len(json.dumps(report).encode()) < 16 * 1024


def test_public_rehearsal_cannot_select_endpoints_or_other_backends() -> None:
    for unknown in ("COM1", "physical", "http://controller", [], True):
        with pytest.raises(ArmFeedbackWorkerError, match="UNKNOWN_REHEARSAL_SCENARIO"):
            rehearse_arm_feedback_campaign(unknown)
