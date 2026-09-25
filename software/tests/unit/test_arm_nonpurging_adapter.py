"""Actual feedback worker + exact memory Win32 facade; never physical serial."""

import base64
import ctypes
from dataclasses import replace
import hashlib
import json
from threading import Event

import pytest

from rocell.application.physical_connection_contracts import EvidenceOrigin
from rocell.providers.windows.arm_feedback_worker import (
    ArmFeedbackOutcome,
    ArmFeedbackWorker,
    ArmFeedbackWorkerError,
    _settings,
)
from rocell.providers.windows.arm_nonpurging_adapter import (
    ArmNativeLifecycleEvidence,
    NonPurgingArmFeedbackBackend,
    verify_arm_native_lifecycle_evidence,
    MAX_EVIDENCE_BYTES,
)
from rocell.providers.windows.nonpurging_serial_api import (
    FIXED_QUERY,
    IncapableWin32Scenario,
    IncapableWin32SerialApi,
    NATIVE_HOLD,
    WindowsNativeSerialApi,
)
from test_arm_feedback_worker import Clock, _request


@pytest.fixture(autouse=True)
def no_native_calls(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("This suite never loads a native DLL or opens a device")

    monkeypatch.setattr(ctypes, "WinDLL", forbidden, raising=False)
    monkeypatch.setattr(WindowsNativeSerialApi, "_kernel", forbidden)


def setup(
    scenario=IncapableWin32Scenario(), *, origin=EvidenceOrigin.SYNTHETIC_REHEARSAL
):
    clock = Clock()
    request = _request(clock, origin=origin)
    api = (
        IncapableWin32SerialApi(scenario)
        if origin is EvidenceOrigin.SYNTHETIC_REHEARSAL
        else None
    )
    backend = NonPurgingArmFeedbackBackend(request.controller, api=api)
    calls = []

    def authorize(exact):
        assert exact is request
        calls.append("authorized")

    worker = ArmFeedbackWorker(
        authorizer=authorize,
        identity_resolver=lambda expected: expected,
        backend=backend,
        monotonic_ns=clock,
        wait=clock.wait,
    )
    return worker, backend, request, api, clock, calls


def execute(scenario=IncapableWin32Scenario()):
    worker, backend, request, api, clock, calls = setup(scenario)
    result = worker.run(request)
    evidence = backend.retain_evidence(request, result)
    assert evidence.view()["physical_authority"] is False
    assert (
        evidence.view()["final_power_state"] == "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION"
    )
    assert len(evidence.payload) < MAX_EVIDENCE_BYTES
    return worker, backend, request, api, clock, calls, result, evidence


def canonical(value):
    return json.dumps(
        value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False
    ).encode()


def verify_changed(doc, request, result):
    payload = canonical(doc)
    return verify_arm_native_lifecycle_evidence(
        payload,
        expected_request=request,
        expected_result=result,
        expected_evidence_sha256=hashlib.sha256(payload).hexdigest(),
    )


def test_construction_status_inert_and_no_unadmitted_factory_or_evidence():
    worker, backend, request, api, _, calls = setup()
    assert api.trace == () and calls == []
    assert worker.status()["native_buffer_preservation_hold"] == NATIVE_HOLD
    assert backend.status()["request_bound"] is False
    with pytest.raises(ArmFeedbackWorkerError):
        backend.create_closed()
    with pytest.raises(ArmFeedbackWorkerError):
        backend.retain_evidence(request, None)
    assert api.trace == ()


def test_native_path_held_before_authorizer_factory_or_any_native_call():
    worker, backend, request, _, _, calls = setup(
        origin=EvidenceOrigin.PHYSICAL_OBSERVATION
    )
    result = worker.run(request)
    assert result.outcome is ArmFeedbackOutcome.BLOCKED_PRE_OPEN
    assert result.primary_error.code == NATIVE_HOLD
    assert result.api_counts.object_creations == result.api_counts.open_attempts == 0
    assert calls == []
    evidence = backend.retain_evidence(request, result)
    assert evidence.to_dict()["native"] is None
    assert evidence.view()["native_cleanup_confirmed"] is None


def test_nominal_actual_worker_uses_nonpurging_owner_and_retains_exact_native_join():
    worker, backend, request, api, _, calls, result, evidence = execute()
    assert result.outcome is ArmFeedbackOutcome.SUCCEEDED_DIAGNOSTIC
    assert result.feedback_receipt.request_bytes == FIXED_QUERY
    assert calls == ["authorized"]
    assert result.api_counts.identity_checks == 2
    assert result.api_counts.write_attempts == result.api_counts.writes_confirmed == 1
    assert result.api_counts.close_attempts == result.api_counts.closes_confirmed == 1
    native = evidence.to_dict()["native"]
    assert native["confirmed_write_bytes"] == 10
    assert native["resource_counts"] == {
        "acquired": 3,
        "close_attempted": 3,
        "close_confirmed": 3,
        "unresolved": 0,
    }
    assert api.open_handles == ()
    operations = [name for name, _ in api.trace]
    assert operations.count("create_file") == operations.count("submit_write") == 1
    assert not any(
        "purge" in name.lower() or "flush" in name.lower() or "reset" in name.lower()
        for name in operations
    )
    assert (
        operations.index("get_state")
        < operations.index("set_state")
        < operations.index("submit_write")
    )
    assert result.settings_before_open == result.settings_after_open
    assert evidence.view()["device_cleanup_proven"] is False
    assert (
        verify_arm_native_lifecycle_evidence(
            evidence.payload,
            expected_request=request,
            expected_result=result,
            expected_evidence_sha256=evidence.evidence_sha256,
        ).payload
        == evidence.payload
    )
    with pytest.raises(ArmFeedbackWorkerError):
        worker.run(request)
    with pytest.raises(ArmFeedbackWorkerError):
        backend.create_closed()
    assert operations.count("submit_write") == 1


@pytest.mark.parametrize("count", [0, 1, 9])
def test_partial_write_preserves_api_count_and_never_resubmits(count):
    _, _, _, api, _, _, result, evidence = execute(
        IncapableWin32Scenario(short_write=count)
    )
    assert result.outcome is ArmFeedbackOutcome.FAILED_UNCERTAIN
    assert result.primary_error.code == "SHORT_OR_AMBIGUOUS_WRITE"
    assert (
        result.write_api_returned_count
        == result.api_counts.write_bytes_confirmed
        == count
    )
    assert evidence.to_dict()["native"]["confirmed_write_bytes"] == count
    assert (
        evidence.to_dict()["native"]["primary_error"]["code"] == "SHORT_WRITE_NO_RETRY"
    )
    assert sum(name == "submit_write" for name, _ in api.trace) == 1


def test_startup_bytes_retained_without_write_and_not_in_safe_projection():
    secret = b"password=fixture-private\n"
    _, _, _, api, _, _, result, evidence = execute(
        IncapableWin32Scenario(startup_bytes=secret)
    )
    assert result.outcome is ArmFeedbackOutcome.FAILED_UNCERTAIN
    assert result.unexpected_bytes == secret
    assert result.api_counts.write_attempts == 0
    assert evidence.to_dict()["native"]["startup_input_observed"] is True
    assert (
        evidence.to_dict()["worker_wire"]["unexpected_sha256"]
        == hashlib.sha256(secret).hexdigest()
    )
    assert not any(name == "submit_write" for name, _ in api.trace)
    assert secret.decode().strip() not in json.dumps(evidence.view())


@pytest.mark.parametrize("cancel_outcome", ["completed", "not_found_completed"])
def test_late_read_after_timeout_is_retained_not_misclassified_as_success(
    cancel_outcome,
):
    response = b'{"T":1051,"x":0}\n'
    _, _, _, api, _, _, result, evidence = execute(
        IncapableWin32Scenario(
            response_bytes=response,
            pending_kind="read",
            pending_outcome="timeout",
            cancel_outcome=cancel_outcome,
        )
    )
    assert result.outcome is ArmFeedbackOutcome.FAILED_UNCERTAIN
    assert result.response_bytes == b""
    doc = evidence.to_dict()
    assert base64.b64decode(doc["late_read"]["base64"]) == response
    assert doc["native"]["retained_read_bytes"] == len(response)
    assert doc["native"]["cleanup_confirmed"] is True
    assert sum(name == "cancel_io" for name, _ in api.trace) == 1
    assert "base64" not in json.dumps(evidence.view())


def test_unresolved_pending_io_and_failed_close_remain_distinct_uncertainty():
    _, _, _, api, _, _, result, evidence = execute(
        IncapableWin32Scenario(
            pending_kind="read", pending_outcome="timeout", cancel_outcome="stuck"
        )
    )
    assert result.outcome is ArmFeedbackOutcome.FAILED_UNCERTAIN
    assert result.connection_closed is False
    assert result.cleanup_errors
    native = evidence.to_dict()["native"]
    assert native["pending_io_unresolved"] is True
    assert native["cleanup_confirmed"] is False
    assert native["resource_counts"]["unresolved"] == 3
    assert len(api.open_handles) == 3
    assert not any(name.startswith("close_") for name, _ in api.trace)


@pytest.mark.parametrize("fault", ["close_port", "close_event:1", "close_event:2"])
def test_failed_handle_close_is_not_hidden_by_port_closed_state(fault):
    _, _, _, api, _, _, result, evidence = execute(
        IncapableWin32Scenario(fail_operations=(fault,))
    )
    assert result.outcome is ArmFeedbackOutcome.FAILED_UNCERTAIN
    assert result.connection_closed is False
    assert result.api_counts.closes_confirmed == 0
    native = evidence.to_dict()["native"]
    assert native["resource_counts"] == {
        "acquired": 3,
        "close_attempted": 3,
        "close_confirmed": 2,
        "unresolved": 1,
    }
    assert len(native["cleanup_errors"]) == 1
    assert sum(name.startswith("close_") for name, _ in api.trace) == 3


@pytest.mark.parametrize(
    "fault",
    [
        "create_file",
        "create_event:1",
        "create_event:2",
        "get_state",
        "set_state",
        "get_timeouts",
        "set_timeouts",
        "queue_status",
        "submit_write",
        "submit_read",
    ],
)
def test_each_native_fault_retains_primary_and_attempt_accounting(fault):
    _, _, _, api, _, _, result, evidence = execute(
        IncapableWin32Scenario(fail_operations=(fault,))
    )
    assert result.outcome is ArmFeedbackOutcome.FAILED_UNCERTAIN
    assert evidence.to_dict()["native"]["primary_error"] is not None
    assert sum(name == "submit_write" for name, _ in api.trace) <= 1
    assert result.feedback_receipt is None


@pytest.mark.parametrize(
    "scenario",
    [
        IncapableWin32Scenario(state_mismatch=True),
        IncapableWin32Scenario(timeout_mismatch=True),
        IncapableWin32Scenario(communication_error=1),
    ],
)
def test_configuration_or_communication_error_never_submits_query(scenario):
    _, _, _, api, _, _, result, evidence = execute(scenario)
    assert result.outcome is ArmFeedbackOutcome.FAILED_UNCERTAIN
    assert result.api_counts.write_attempts == 0
    assert not any(name == "submit_write" for name, _ in api.trace)


def test_wrong_controller_and_second_worker_cannot_use_bound_backend():
    _, backend, request, api, clock, _ = setup()
    wrong = replace(
        request,
        controller=replace(request.controller, boot_policy_evidence_sha256="b" * 64),
    )
    worker = ArmFeedbackWorker(
        authorizer=lambda request: None,
        identity_resolver=lambda x: x,
        backend=backend,
        monotonic_ns=clock,
        wait=clock.wait,
    )
    with pytest.raises(
        ArmFeedbackWorkerError, match="NATIVE_CONTROLLER_BINDING_MISMATCH"
    ):
        worker.run(wrong)
    assert api.trace == ()
    # A rejected controller did not create a connection; the failed worker,
    # however, remains consumed by the original worker's one-use contract.
    with pytest.raises(ArmFeedbackWorkerError):
        worker.run(request)


def test_authorization_denied_or_boolean_ack_never_creates_connection():
    for acknowledgement in [True, False]:
        _, backend, request, api, clock, _ = setup()
        worker = ArmFeedbackWorker(
            authorizer=lambda request: acknowledgement,
            identity_resolver=lambda x: x,
            backend=backend,
            monotonic_ns=clock,
            wait=clock.wait,
        )
        result = worker.run(request)
        assert result.outcome is ArmFeedbackOutcome.BLOCKED_PRE_OPEN
        assert api.trace == ()
        assert backend.retain_evidence(request, result).to_dict()["native"] is None


def test_cancellation_before_open_and_during_quiet_window():
    for early in [True, False]:
        _, backend, request, api, clock, _ = setup()
        cancel = Event()
        if early:
            cancel.set()

        def wait(event, seconds):
            event.set()
            return clock.wait(event, seconds)

        worker = ArmFeedbackWorker(
            authorizer=lambda request: None,
            identity_resolver=lambda x: x,
            backend=backend,
            monotonic_ns=clock,
            wait=wait,
        )
        result = worker.run(request, cancellation=cancel)
        assert result.api_counts.write_attempts == 0
        assert result.outcome is (
            ArmFeedbackOutcome.CANCELLED_PRE_OPEN
            if early
            else ArmFeedbackOutcome.FAILED_UNCERTAIN
        )
        assert not any(name == "submit_write" for name, _ in api.trace)
        assert (
            backend.retain_evidence(request, result).view()["physical_authority"]
            is False
        )


@pytest.mark.parametrize(
    "name,value",
    [
        ("port", "COM405"),
        ("baudrate", 9600),
        ("rts", True),
        ("dtr", True),
        ("bytesize", True),
        ("unknown", False),
        ("timeout", True),
        ("timeout", 0.0009),
        ("timeout", float("nan")),
    ],
)
def test_closed_adapter_rejects_nonfixed_or_coerced_options(name, value):
    _, backend, request, api, _, _ = setup()
    backend._bind_request(request)
    connection = backend.create_closed()
    with pytest.raises(ArmFeedbackWorkerError):
        setattr(connection, name, value)
    assert api.trace == ()


def test_read_timeout_is_floored_to_remaining_milliseconds(monkeypatch):
    _, backend, request, api, _, _ = setup(IncapableWin32Scenario(pending_kind="read"))
    backend._bind_request(request)
    connection = backend.create_closed()
    connection.port = request.controller.identity.port_name
    for name, value in _settings().items():
        setattr(connection, name, value)
    connection.open()
    connection.write(FIXED_QUERY)
    connection.timeout = 0.0019
    assert connection.read(1) == b"{"
    assert [args[1] for name, args in api.trace if name == "complete_io"] == [1]
    connection.close()


def test_result_mutation_unrelated_result_or_changed_native_snapshot_refuses_retention():
    _, backend, request, _, _, _, result, evidence = execute()
    with pytest.raises(ArmFeedbackWorkerError):
        backend.retain_evidence(request, replace(result))
    object.__setattr__(result, "elapsed_ns", result.elapsed_ns + 1)
    with pytest.raises(ArmFeedbackWorkerError):
        backend.retain_evidence(request, result)
    doc = evidence.to_dict()
    doc["native"]["resource_counts"]["acquired"] = 100
    assert evidence.to_dict()["native"]["resource_counts"]["acquired"] == 3


@pytest.mark.parametrize(
    "change",
    [
        "cleanup",
        "settings",
        "phase",
        "write_count",
        "read_hash",
        "pending",
        "primary",
        "unknown",
        "coerced",
        "source",
        "late_hash",
    ],
)
def test_forged_native_companion_fails_even_with_recomputed_outer_hash(change):
    _, _, request, _, _, _, result, evidence = execute()
    doc = evidence.to_dict()
    native = doc["native"]
    if change == "cleanup":
        native["cleanup_confirmed"] = False
        native["resource_counts"].update(close_confirmed=2, unresolved=1)
    elif change == "settings":
        native["settings_readback_verified"] = False
    elif change == "phase":
        native["phase"] = "FAILED"
    elif change == "write_count":
        native["confirmed_write_bytes"] = 9
    elif change == "read_hash":
        native["read_bytes_sha256"] = "a" * 64
    elif change == "pending":
        native["pending_io_unresolved"] = True
    elif change == "primary":
        native["primary_error"] = {
            "code": "IO_DEADLINE_EXPIRED",
            "operation": "read",
            "winerror": 0,
        }
    elif change == "unknown":
        native["extra"] = True
    elif change == "coerced":
        native["confirmed_write_bytes"] = True
    elif change == "source":
        doc["source_sha256"] = "c" * 64
    elif change == "late_hash":
        doc["late_read"]["sha256"] = "a" * 64
    with pytest.raises(ArmFeedbackWorkerError):
        verify_changed(doc, request, result)


def test_malformed_oversized_and_noncanonical_artifacts_refused():
    for payload in (
        b"{}",
        b"[]",
        b"NaN",
        b"{" * (MAX_EVIDENCE_BYTES + 1),
        b'{"schema":1,"schema":2}',
    ):
        with pytest.raises(ArmFeedbackWorkerError):
            ArmNativeLifecycleEvidence(payload)


def test_late_completed_write_stays_uncertain_with_native_confirmed_bytes():
    _, _, _, api, _, _, result, evidence = execute(
        IncapableWin32Scenario(
            pending_kind="write", pending_outcome="timeout", cancel_outcome="completed"
        )
    )
    assert result.outcome is ArmFeedbackOutcome.FAILED_UNCERTAIN
    assert result.write_api_returned_count is None
    assert result.api_counts.write_bytes_confirmed == 0
    assert evidence.to_dict()["native"]["confirmed_write_bytes"] == 10
    assert sum(name == "submit_write" for name, _ in api.trace) == 1
    assert sum(name == "submit_read" for name, _ in api.trace) == 0


def test_primary_and_all_cleanup_errors_preserved_together():
    _, _, _, _, _, _, result, evidence = execute(
        IncapableWin32Scenario(
            fail_operations=(
                "submit_read",
                "close_event:1",
                "close_event:2",
                "close_port",
            )
        )
    )
    native = evidence.to_dict()["native"]
    assert result.primary_error is not None and result.cleanup_errors
    assert native["primary_error"]["operation"] == "read"
    assert len(native["cleanup_errors"]) == 3
    assert native["resource_counts"]["unresolved"] == 3


def test_identity_changes_after_open_prevent_native_write():
    _, backend, request, api, clock, _ = setup()
    count = 0

    def resolve(expected):
        nonlocal count
        count += 1
        return expected if count == 1 else replace(expected, port_name="COM405")

    worker = ArmFeedbackWorker(
        authorizer=lambda request: None,
        identity_resolver=resolve,
        backend=backend,
        monotonic_ns=clock,
        wait=clock.wait,
    )
    result = worker.run(request)
    assert result.primary_error.code == "CONTROLLER_IDENTITY_CHANGED"
    assert result.api_counts.write_attempts == 0
    assert not any(name == "submit_write" for name, _ in api.trace)
    assert (
        backend.retain_evidence(request, result).view()["native_cleanup_confirmed"]
        is True
    )


def test_full_one_second_write_must_still_fit_current_budget():
    _, backend, request, api, clock, _ = setup()
    calls = 0

    def resolve(expected):
        nonlocal calls
        calls += 1
        if calls == 2:
            clock.value += 4_000_000_000
        return expected

    worker = ArmFeedbackWorker(
        authorizer=lambda request: None,
        identity_resolver=resolve,
        backend=backend,
        monotonic_ns=clock,
        wait=clock.wait,
    )
    result = worker.run(request)
    assert result.primary_error.code == "INSUFFICIENT_WRITE_DEADLINE"
    assert result.api_counts.write_attempts == 0
    assert not any(name == "submit_write" for name, _ in api.trace)
    backend.retain_evidence(request, result)


def test_cancellation_after_completed_native_read_retains_bytes_and_no_retry(
    monkeypatch,
):
    _, backend, request, api, clock, _ = setup()
    cancel = Event()
    original = IncapableWin32SerialApi.submit_io

    def complete_then_cancel(self, handle, token):
        completion = original(self, handle, token)
        if token.kind == "read":
            cancel.set()
        return completion

    monkeypatch.setattr(IncapableWin32SerialApi, "submit_io", complete_then_cancel)
    worker = ArmFeedbackWorker(
        authorizer=lambda request: None,
        identity_resolver=lambda x: x,
        backend=backend,
        monotonic_ns=clock,
        wait=clock.wait,
    )
    result = worker.run(request, cancellation=cancel)
    evidence = backend.retain_evidence(request, result)
    assert result.outcome is ArmFeedbackOutcome.FAILED_UNCERTAIN
    assert result.response_bytes == IncapableWin32Scenario().response_bytes
    assert evidence.to_dict()["native"]["retained_read_bytes"] == len(
        result.response_bytes
    )
    assert any(
        issue.code == "CANCELLATION_AFTER_OPEN" for issue in result.cleanup_errors
    )
    assert sum(name == "submit_write" for name, _ in api.trace) == 1


def test_deadline_after_native_open_preserves_cleanup_and_refuses_write(monkeypatch):
    _, backend, request, api, clock, _ = setup()
    original = IncapableWin32SerialApi.set_timeouts

    def configure_then_expire(self, handle, settings):
        result = original(self, handle, settings)
        clock.value += 5_000_000_000
        return result

    monkeypatch.setattr(IncapableWin32SerialApi, "set_timeouts", configure_then_expire)
    worker = ArmFeedbackWorker(
        authorizer=lambda request: None,
        identity_resolver=lambda x: x,
        backend=backend,
        monotonic_ns=clock,
        wait=clock.wait,
    )
    result = worker.run(request)
    evidence = backend.retain_evidence(request, result)
    assert result.outcome is ArmFeedbackOutcome.FAILED_UNCERTAIN
    assert result.primary_error.code == "CAMPAIGN_DEADLINE_EXCEEDED"
    assert any(
        item.code == "CAMPAIGN_DEADLINE_EXCEEDED" for item in result.cleanup_errors
    )
    assert evidence.view()["native_cleanup_confirmed"] is True
    assert not any(name == "submit_write" for name, _ in api.trace)


def test_wrong_request_consumes_backend_admission_too():
    _, backend, request, api, _, _ = setup()
    wrong = replace(
        request,
        controller=replace(request.controller, boot_policy_evidence_sha256="b" * 64),
    )
    with pytest.raises(ArmFeedbackWorkerError):
        backend._bind_request(wrong)
    with pytest.raises(ArmFeedbackWorkerError, match="NATIVE_BACKEND_ALREADY_USED"):
        backend._bind_request(request)
    assert backend.status()["admission_consumed"] is True
    assert api.trace == ()


def test_changed_bound_request_refuses_next_owner_io_but_close_still_works():
    _, backend, request, api, _, _ = setup()
    backend._bind_request(request)
    connection = backend.create_closed()
    connection.port = request.controller.identity.port_name
    for name, value in _settings().items():
        setattr(connection, name, value)
    connection.open()
    object.__setattr__(request, "source_sha256", "c" * 64)
    with pytest.raises(
        ArmFeedbackWorkerError, match="NATIVE_REQUEST_CHANGED_AFTER_ADMISSION"
    ):
        connection.write(FIXED_QUERY)
    connection.close()
    assert api.open_handles == ()
    assert not any(name == "submit_write" for name, _ in api.trace)


@pytest.mark.parametrize("invalid", [object(), "COM404"])
def test_unknown_backend_facade_and_origin_mixing_rejected(invalid):
    request = _request(Clock())
    with pytest.raises(ArmFeedbackWorkerError):
        NonPurgingArmFeedbackBackend(request.controller, api=invalid)
    with pytest.raises(ArmFeedbackWorkerError):
        NonPurgingArmFeedbackBackend(request.controller)
    physical = replace(request.controller, origin=EvidenceOrigin.PHYSICAL_OBSERVATION)
    with pytest.raises(ArmFeedbackWorkerError):
        NonPurgingArmFeedbackBackend(physical, api=IncapableWin32SerialApi())


def test_complete_native_companion_pairs_with_existing_lossless_worker_evidence():
    from rocell.application.rehearsal_arm_feedback_evidence import (
        retain_rehearsal_arm_feedback_evidence,
        verify_rehearsal_arm_feedback_evidence,
    )

    _, _, request, _, _, _, result, native = execute()
    feedback = retain_rehearsal_arm_feedback_evidence(
        request, result, binding_sha256="b" * 64, source_sha256=request.source_sha256
    )
    restored = verify_rehearsal_arm_feedback_evidence(
        feedback.canonical_bytes(),
        expected_request=request,
        expected_binding_sha256="b" * 64,
        expected_evidence_sha256=feedback.evidence_sha256,
        expected_source_sha256=request.source_sha256,
    )
    native_restored = verify_arm_native_lifecycle_evidence(
        native.payload,
        expected_request=request,
        expected_result=restored.result,
        expected_evidence_sha256=native.evidence_sha256,
    )
    assert native_restored.payload == native.payload
    assert len(feedback.canonical_bytes()) + len(native.payload) < 128 * 1024


def test_decoded_evidence_and_view_are_detached_and_pure_after_capture(monkeypatch):
    _, backend, request, _, _, _, result, artifact = execute()

    def forbidden(*args, **kwargs):
        pytest.fail("Pure retained verification must not execute a worker or provider")

    monkeypatch.setattr(ArmFeedbackWorker, "run", forbidden)
    monkeypatch.setattr(NonPurgingArmFeedbackBackend, "create_closed", forbidden)
    for name in ("create_file", "queue_status", "submit_io", "close_handle"):
        monkeypatch.setattr(IncapableWin32SerialApi, name, forbidden)
    snapshot = artifact.to_dict()
    snapshot["native"]["phase"] = "TAMPERED"
    view = artifact.view()
    view["resource_counts"]["unresolved"] = 100
    assert artifact.to_dict()["native"]["phase"] == "CLOSED"
    assert artifact.view()["resource_counts"]["unresolved"] == 0
    assert backend.retain_evidence(request, result).payload == artifact.payload


def test_connection_admission_and_exact_fixed_write_have_no_arbitrary_command_route():
    _, backend, request, api, _, _ = setup()
    backend._bind_request(request)
    connection = backend.create_closed()
    with pytest.raises(ArmFeedbackWorkerError, match="CLOSED_SETTINGS_NOT_COMPLETE"):
        connection.open()
    assert api.trace == ()
    connection.port = request.controller.identity.port_name
    for name, value in _settings().items():
        setattr(connection, name, value)
    connection.open()
    for wire in (b'{"T":0}\n', b'{"T":105}', b'{"T":105}\r\n', '{"T":105}\n'):
        with pytest.raises(Exception):
            connection.write(wire)
    assert not any(name == "submit_write" for name, _ in api.trace)
    connection.close()
