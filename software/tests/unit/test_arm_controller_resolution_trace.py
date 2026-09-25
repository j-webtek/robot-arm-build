"""Actual CM ABI parser/resolver/non-purging worker; all OS APIs incapable."""

from dataclasses import replace
import ctypes
import hashlib
import json
from pathlib import Path
from threading import Event

import pytest

from rocell.application import arm_controller_resolution as resolution
from rocell.application import physical_device_inventory as inventory
from rocell.application.physical_connection_contracts import EvidenceOrigin
from rocell.application.wizard_native_arm_metadata import (
    decode_controller_snapshot as wizard_decode,
)
from rocell.providers.windows import controller_metadata as cm
from rocell.providers.windows.arm_feedback_worker import (
    ArmFeedbackWorker,
    ArmFeedbackOutcome,
)
from rocell.providers.windows.arm_nonpurging_adapter import NonPurgingArmFeedbackBackend
from rocell.providers.windows.incapable_controller_metadata import (
    IncapableControllerMetadataProducer,
    synthetic_native_identity,
)
from rocell.providers.windows.nonpurging_serial_api import IncapableWin32SerialApi
from test_arm_feedback_worker import Clock, _request


def canonical(value):
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


@pytest.fixture(autouse=True)
def no_host_or_device_calls(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("No files, DLLs, inventory or devices in this pure composition")

    monkeypatch.setattr(ctypes, "WinDLL", forbidden, raising=False)
    monkeypatch.setattr(inventory, "inventory_serial_ports_with_pyserial", forbidden)
    monkeypatch.setattr(cm, "inventory_serial_ports_with_pyserial", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)


def execution(scenario="nominal", *, clock=None, cancel=None, wrap=None, api=None):
    clock, cancel = clock or Clock(), cancel or Event()
    original = _request(clock)
    identity = synthetic_native_identity(original.controller)
    exact = replace(
        original,
        controller=replace(original.controller, identity=identity),
        feedback=replace(
            original.feedback, arm_identity_sha256=identity.identity_sha256
        ),
    )
    producer = IncapableControllerMetadataProducer(exact.controller, scenario=scenario)
    acquirer = producer.acquirer(
        deadline_ns=exact.expires_monotonic_ns, cancellation=cancel, monotonic_ns=clock
    )
    callback = acquirer if wrap is None else wrap(acquirer, clock, cancel, exact)
    resolver = resolution.ExplicitArmControllerResolver(
        exact.controller,
        callback,
        deadline_ns=exact.expires_monotonic_ns,
        cancellation=cancel,
        monotonic_ns=clock,
    )
    api = api or IncapableWin32SerialApi()
    backend = NonPurgingArmFeedbackBackend(exact.controller, api=api)
    worker = ArmFeedbackWorker(
        authorizer=lambda _: None,
        identity_resolver=resolver,
        backend=backend,
        monotonic_ns=clock,
        wait=clock.wait,
    )
    result = worker.run(exact, cancellation=cancel)
    trace = resolver.retained_trace()
    verified = resolution.verify_controller_resolution_trace(
        trace,
        reviewed=exact.controller,
        expected_deadline_ns=exact.expires_monotonic_ns,
        expected_trace_sha256=trace.sha256,
        expected_result=result,
    )
    assert verified.payload == trace.payload
    return exact, result, trace, acquirer, backend, api


@pytest.mark.parametrize(
    "scenario,count,opens,writes,error",
    [
        ("nominal", 2, 1, 1, None),
        ("identity-change-preopen", 1, 0, 0, "CONTROLLER_METADATA_HELD"),
        ("identity-change", 2, 1, 0, "CONTROLLER_METADATA_HELD"),
        ("malformed-metadata", 1, 0, 0, "CM_PROPERTY_STRING_INVALID"),
    ],
)
def test_actual_three_layer_composition_retains_success_and_refusal(
    scenario, count, opens, writes, error
):
    exact, result, trace, acquirer, backend, api = execution(scenario)
    assert result.api_counts.identity_checks == count
    assert result.api_counts.open_attempts == opens
    assert result.api_counts.write_attempts == writes
    assert result.api_counts.closes_confirmed == opens
    assert api.open_handles == ()
    assert acquirer.status()["metadata_api_calls"] > 0
    assert acquirer.status()["native_source"] == "INJECTED_CM_METADATA"
    rows = trace.to_dict()["attempts"]
    assert len(rows) == count
    assert rows[-1]["error_code"] == error
    assert trace.safe_summary()["status"] == (
        "PRE_WRITE_MATCHED" if error is None else "HELD"
    )
    if scenario == "malformed-metadata":
        assert rows[0]["snapshot"] is rows[0]["resolution"] is None
    else:
        assert all(row["snapshot"] and row["resolution"] for row in rows)
    if error:
        assert result.primary_error.code == error
    else:
        assert result.outcome is ArmFeedbackOutcome.SUCCEEDED_DIAGNOSTIC
        assert rows[0]["snapshot_sha256"] != rows[1]["snapshot_sha256"]
        assert (
            rows[0]["snapshot"]["serial_inventory"]["source"]
            == "INJECTED_SERIAL_ENUMERATOR"
        )
    native = backend.retain_evidence(exact, result)
    assert native.view()["physical_authority"] is False
    assert len(trace.payload) < resolution.MAX_TRACE_BYTES
    summary = canonical(trace.safe_summary())
    for raw in (
        exact.controller.identity.port_name,
        exact.controller.identity.unit_serial,
        exact.controller.identity.persistent_port_path,
        exact.controller.identity.driver.version,
    ):
        assert raw.encode() not in summary


@pytest.mark.parametrize("late_phase", [1, 2])
@pytest.mark.parametrize("fault", ["stop", "deadline"])
def test_complete_snapshot_retained_before_late_refusal(late_phase, fault):
    def wrap(acquire, clock, cancel, exact):
        calls = 0

        def callback():
            nonlocal calls
            calls += 1
            observed = acquire()
            if calls == late_phase:
                if fault == "stop":
                    cancel.set()
                else:
                    clock.value = exact.expires_monotonic_ns
            return observed

        return callback

    _, result, trace, _, _, _ = execution(wrap=wrap)
    rows = trace.to_dict()["attempts"]
    assert len(rows) == late_phase
    assert rows[-1]["snapshot"] is not None
    assert rows[-1]["resolution"] is None
    assert rows[-1]["status"] == "HELD"
    assert result.api_counts.write_attempts == 0


def test_source_types_domains_and_constructor_are_inert():
    clock = Clock()
    original = _request(clock)
    with pytest.raises(resolution.ControllerResolutionError):
        synthetic_native_identity(
            replace(original.controller, origin=EvidenceOrigin.PHYSICAL_OBSERVATION)
        )
    with pytest.raises(resolution.ControllerResolutionError):
        IncapableControllerMetadataProducer(original.controller)
    with pytest.raises(resolution.ControllerResolutionError):
        IncapableControllerMetadataProducer(
            replace(
                original.controller,
                identity=synthetic_native_identity(original.controller),
            ),
            scenario="arbitrary",
        )
    binding = replace(
        original.controller, identity=synthetic_native_identity(original.controller)
    )
    producer = IncapableControllerMetadataProducer(binding)
    before = clock.value
    acquirer = producer.acquirer(
        deadline_ns=original.expires_monotonic_ns,
        cancellation=Event(),
        monotonic_ns=clock,
    )
    resolver = resolution.ExplicitArmControllerResolver(
        binding,
        acquirer,
        deadline_ns=original.expires_monotonic_ns,
        cancellation=Event(),
        monotonic_ns=clock,
    )
    assert resolver.retained_trace().safe_summary()["status"] == "NOT_ATTEMPTED"
    assert resolver.status()["acquisition_attempts"] == 0
    assert acquirer.status()["metadata_api_calls"] == 0 and clock.value == before
    with pytest.raises(resolution.ControllerResolutionError):
        producer.acquirer(
            deadline_ns=original.expires_monotonic_ns, cancellation=Event()
        )


def test_snapshot_shared_decoder_has_exact_original_bytes():
    _, _, trace, _, _, _ = execution()
    for row in trace.to_dict()["attempts"]:
        raw = row["snapshot"]
        assert (
            resolution.decode_controller_snapshot(raw, "rehearsal").payload()
            == wizard_decode(raw, "rehearsal").payload()
            == canonical(raw)
        )


def test_detached_trace_and_summary_and_expected_hash_are_strict():
    exact, result, trace, _, _, _ = execution()
    raw, summary = trace.to_dict(), trace.safe_summary()
    raw["attempts"][0]["snapshot"]["native_source"] = "WINDOWS_CM_METADATA"
    summary["attempts"].clear()
    assert len(trace.safe_summary()["attempts"]) == 2
    with pytest.raises(resolution.ControllerResolutionError):
        resolution.verify_controller_resolution_trace(
            trace,
            reviewed=exact.controller,
            expected_deadline_ns=exact.expires_monotonic_ns,
            expected_trace_sha256="0" * 64,
            expected_result=result,
        )
    with pytest.raises(resolution.ControllerResolutionError):
        resolution.ControllerResolutionTrace(bytearray(trace.payload))
    with pytest.raises(resolution.ControllerResolutionError):
        resolution.ControllerResolutionTrace(b'{"schema":"x","schema":"x"}')


def verify_mutation(exact, result, trace, mutate):
    obj = trace.to_dict()
    mutate(obj)
    payload = canonical(obj)
    with pytest.raises(resolution.ControllerResolutionError):
        resolution.verify_controller_resolution_trace(
            payload,
            reviewed=exact.controller,
            expected_deadline_ns=exact.expires_monotonic_ns,
            expected_trace_sha256=hashlib.sha256(payload).hexdigest(),
            expected_result=result,
        )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda x: x.update(extra=True),
        lambda x: x.update(physical_authority=True),
        lambda x: x.update(deadline_monotonic_ns=x["deadline_monotonic_ns"] + 1),
        lambda x: x.update(reviewed_binding_sha256="0" * 64),
        lambda x: x.update(origin="PHYSICAL_OBSERVATION"),
        lambda x: x["attempts"].pop(),
        lambda x: x["attempts"][0].update(phase="PRE_WRITE"),
        lambda x: x["attempts"][0].update(error_code="untrusted endpoint text"),
        lambda x: x["attempts"][0].update(snapshot_sha256="0" * 64),
        lambda x: x["attempts"][0].update(
            finished_monotonic_ns=x["deadline_monotonic_ns"]
        ),
        lambda x: x["attempts"][1].update(started_monotonic_ns=1),
        lambda x: x["attempts"][1].update(
            finished_monotonic_ns=x["deadline_monotonic_ns"] - 1
        ),
    ],
)
def test_rehashed_trace_tampering_is_denied(mutate):
    exact, result, trace, _, _, _ = execution()
    verify_mutation(exact, result, trace, mutate)


def test_fully_rehashed_changed_native_comparison_cannot_claim_match():
    exact, result, trace, _, _, _ = execution()

    def mutate(obj):
        row = obj["attempts"][1]
        row["snapshot"]["native_observations"][0]["driver_version"] = "DRIFT"
        snapshot = resolution.decode_controller_snapshot(row["snapshot"], "rehearsal")
        compared = resolution.resolve_controller_metadata(exact.controller, snapshot)
        row.update(
            snapshot_sha256=snapshot.snapshot_sha256,
            resolution=compared.to_dict(),
            resolution_sha256=compared.sha256,
        )

    verify_mutation(exact, result, trace, mutate)


def test_rehashed_held_trace_cannot_disagree_with_worker_effects():
    exact, result, trace, _, _, _ = execution("identity-change-preopen")
    forged = replace(result, api_counts=replace(result.api_counts, open_attempts=1))
    with pytest.raises(resolution.ControllerResolutionError):
        resolution.verify_controller_resolution_trace(
            trace,
            reviewed=exact.controller,
            expected_deadline_ns=exact.expires_monotonic_ns,
            expected_trace_sha256=trace.sha256,
            expected_result=forged,
        )


@pytest.mark.parametrize("interrupt", [KeyboardInterrupt, SystemExit])
def test_interruption_preserves_base_exception_and_trace(interrupt):
    clock = Clock()
    exact = _request(clock)

    def acquire():
        raise interrupt()

    resolver = resolution.ExplicitArmControllerResolver(
        exact.controller,
        acquire,
        deadline_ns=exact.expires_monotonic_ns,
        cancellation=Event(),
        monotonic_ns=clock,
    )
    with pytest.raises(interrupt):
        resolver(exact.controller.identity)
    assert (
        resolver.retained_trace().to_dict()["attempts"][0]["error_code"]
        == "CONTROLLER_RESOLUTION_INTERRUPTED"
    )


def test_original_snapshot_acquirer_and_clock_are_not_replayed_on_verification(
    monkeypatch,
):
    exact, result, trace, _, _, _ = execution()

    def forbidden(*args, **kwargs):
        pytest.fail("retained verification must not reacquire or read time")

    monkeypatch.setattr(cm.WindowsControllerMetadataAcquirer, "__call__", forbidden)
    monkeypatch.setattr(IncapableControllerMetadataProducer, "acquirer", forbidden)
    monkeypatch.setattr(resolution.time, "monotonic_ns", forbidden)
    verified = resolution.verify_controller_resolution_trace(
        trace,
        reviewed=exact.controller,
        expected_deadline_ns=exact.expires_monotonic_ns,
        expected_trace_sha256=trace.sha256,
        expected_result=result,
    )
    assert verified.payload == trace.payload


def test_unknown_provider_exception_never_leaks_message_or_code():
    clock = Clock()
    exact = _request(clock)

    def acquire():
        raise resolution.ControllerResolutionError(
            "USB\\PRIVATE-DEVICE", "raw endpoint secret"
        )

    resolver = resolution.ExplicitArmControllerResolver(
        exact.controller,
        acquire,
        deadline_ns=exact.expires_monotonic_ns,
        cancellation=Event(),
        monotonic_ns=clock,
    )
    with pytest.raises(resolution.ControllerResolutionError):
        resolver(exact.controller.identity)
    trace = resolver.retained_trace()
    assert (
        trace.to_dict()["attempts"][0]["error_code"]
        == "CONTROLLER_METADATA_ACQUISITION_FAILED"
    )
    assert trace.to_dict()["attempts"][0]["finished_monotonic_ns"] is None
    assert b"PRIVATE" not in trace.payload and b"secret" not in trace.payload


def test_complete_trace_size_limit_refuses_instead_of_trimming(monkeypatch):
    # Deliberately tighter test-only aggregate; neither successful identity nor
    # a rewritten/truncated trace may escape the original full-record limit.
    monkeypatch.setattr(resolution, "MAX_TRACE_BYTES", 1200)
    with pytest.raises(resolution.ControllerResolutionError) as error:
        execution()
    assert error.value.code == "CONTROLLER_METADATA_BYTE_LIMIT"


def test_rehashed_held_observation_after_worker_close_is_refused():
    exact, result, trace, _, _, _ = execution("identity-change")

    def mutate(obj):
        row = obj["attempts"][1]
        row["finished_monotonic_ns"] = result.closed_monotonic_ns + 1

    verify_mutation(exact, result, trace, mutate)


def test_worker_elapsed_cannot_understate_retained_metadata_interval():
    exact, result, trace, _, _, _ = execution()
    with pytest.raises(resolution.ControllerResolutionError):
        resolution.verify_controller_resolution_trace(
            trace,
            reviewed=exact.controller,
            expected_deadline_ns=exact.expires_monotonic_ns,
            expected_trace_sha256=trace.sha256,
            expected_result=replace(result, elapsed_ns=0),
        )
