"""Real feedback/native-owner code, incapable API, modeled process receipts only."""

import ctypes
from dataclasses import replace
import hashlib
import json
import subprocess
from threading import Event

import pytest

from rocell.application.rehearsal_arm_feedback_evidence import (
    retain_rehearsal_arm_feedback_evidence,
)
from rocell.application.physical_connection_contracts import EvidenceOrigin
from rocell.providers.windows.arm_feedback_worker import ArmFeedbackWorker
from rocell.providers.windows.arm_nonpurging_adapter import NonPurgingArmFeedbackBackend
from rocell.providers.windows.nonpurging_serial_api import (
    IncapableWin32Scenario,
    IncapableWin32SerialApi,
)
from rocell.providers.windows.owned_worker_process import OwnedWorkerResult
from rocell.providers.windows.arm_owned_protocol import (
    ArmOwnedRequest,
    LEGACY_REQUEST_SCHEMA,
    PREVIOUS_REQUEST_SCHEMA,
    LEGACY_RESULT_SCHEMA,
    ArmOwnedProtocolError,
    ArmOwnedResult,
    build_arm_owned_ready,
    arm_owned_release,
    build_arm_owned_result,
    parse_arm_owned_result,
)
from rocell.providers.windows.arm_owned_evidence import (
    ArmOwnedEvidence,
    retain_arm_owned_evidence,
    verify_arm_owned_evidence,
    MAX_EVIDENCE_BYTES,
    MAX_STDOUT_BYTES,
    MAX_STDERR_BYTES,
)
from test_arm_owned_protocol import canonical, make_request, rehash


@pytest.fixture(autouse=True)
def forbid_native_and_process(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("owned evidence test attempted actual process or native access")

    monkeypatch.setattr(ctypes, "WinDLL", forbidden, raising=False)
    monkeypatch.setattr(subprocess, "Popen", forbidden)


def owned_fixture(
    scenario=IncapableWin32Scenario(), *, legacy=False, metadata_scenario="nominal"
):
    """Actual worker/native companion; OS process observations explicitly modeled."""
    request, inner, clock = make_request(native_identity=not legacy)
    if legacy:
        document = request.to_dict()
        schema = LEGACY_REQUEST_SCHEMA if legacy is True else legacy
        document.update(
            schema=schema,
            admission_timeout_ms=2000 if schema == LEGACY_REQUEST_SCHEMA else 5000,
        )
        request = ArmOwnedRequest(rehash(document))
    api = IncapableWin32SerialApi(scenario)
    backend = NonPurgingArmFeedbackBackend(inner.controller, api=api)
    acknowledgements = []

    def authorize(exact):
        assert exact == inner
        acknowledgements.append(exact.request_sha256)

    resolver = None
    cancellation = Event()
    if not legacy:
        from rocell.application.arm_controller_resolution import (
            ExplicitArmControllerResolver,
        )
        from rocell.providers.windows.incapable_controller_metadata import (
            IncapableControllerMetadataProducer,
        )

        producer = IncapableControllerMetadataProducer(
            inner.controller, scenario=metadata_scenario
        )
        resolver = ExplicitArmControllerResolver(
            inner.controller,
            producer.acquirer(
                deadline_ns=inner.expires_monotonic_ns,
                cancellation=cancellation,
                monotonic_ns=clock,
            ),
            deadline_ns=inner.expires_monotonic_ns,
            cancellation=cancellation,
            monotonic_ns=clock,
        )
    worker = ArmFeedbackWorker(
        authorizer=authorize,
        identity_resolver=(lambda expected: expected) if legacy else resolver,
        backend=backend,
        monotonic_ns=clock,
        wait=clock.wait,
    )
    actual = worker.run(inner, cancellation=cancellation)
    native = backend.retain_evidence(inner, actual)
    feedback = retain_rehearsal_arm_feedback_evidence(
        inner,
        actual,
        binding_sha256=request.request_sha256,
        source_sha256=inner.source_sha256,
    )
    if legacy:
        # Explicit modeled historical record, not a current builder/admission.
        result = ArmOwnedResult(
            canonical(
                {
                    "schema": LEGACY_RESULT_SCHEMA,
                    "request_sha256": request.request_sha256,
                    "status": "FEEDBACK_RETAINED",
                    "feedback_evidence": feedback.to_dict(),
                    "feedback_evidence_sha256": feedback.evidence_sha256,
                    "native_evidence": native.to_dict(),
                    "native_evidence_sha256": native.evidence_sha256,
                    "error_code": None,
                    "physical_authority": False,
                }
            ),
            request,
        )
    else:
        result = build_arm_owned_result(
            request,
            feedback_evidence=feedback,
            native_evidence=native,
            resolution_trace=resolver.retained_trace(),
        )
    ready = build_arm_owned_ready(request, child_pid=1234, challenge_sha256="d" * 64)
    release = arm_owned_release(request, ready)
    process = OwnedWorkerResult(
        "SUCCEEDED",
        None,
        (),
        request.request_sha256,
        inner.campaign_id,
        True,
        True,
        True,
        0,
        clock.value - inner.feedback.requested_monotonic_ns,
        len(request.wire()) + len(release),
        12,
        1,
        ready.wire() + result.wire(),
        b"",
        result.to_dict(),
    )
    evidence = retain_arm_owned_evidence(
        request=request, process_result=process, ready=ready, release_wire=release
    )
    return (
        request,
        inner,
        actual,
        native,
        feedback,
        result,
        ready,
        release,
        process,
        evidence,
        api,
        acknowledgements,
    )


def test_actual_worker_and_native_companion_are_retained_losslessly():
    (
        request,
        inner,
        actual,
        native,
        feedback,
        result,
        ready,
        release,
        process,
        evidence,
        api,
        calls,
    ) = owned_fixture()
    verified = verify_arm_owned_evidence(
        evidence.payload,
        expected_request=request,
        expected_evidence_sha256=evidence.evidence_sha256,
    )
    assert verified.request == inner and verified.feedback.result == actual
    assert verified.feedback.canonical_bytes() == feedback.canonical_bytes()
    assert verified.native.payload == native.payload
    assert verified.resolution.payload == result.resolution_trace.payload
    assert verified.safe_summary()["schema"] == "rocell.arm_owned_evidence_summary.v2"
    assert verified.safe_summary()["resolution"]["status"] == "PRE_WRITE_MATCHED"
    assert calls == [inner.request_sha256]
    assert len([name for name, _ in api.trace if name == "submit_write"]) == 1
    assert len(evidence.payload) < MAX_EVIDENCE_BYTES
    assert (
        parse_arm_owned_result(
            result.wire(), expected_request=request, returncode=0
        ).result
        == actual
    )
    view = verified.safe_summary()
    assert view["status"] == "COMPLETE_INCAPABLE_EVIDENCE"
    assert view["feedback"]["technical_response_valid"] is True
    assert view["native"]["native_cleanup_confirmed"] is True
    assert view["device_cleanup_proven"] is False
    assert view["final_power_state"] == "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION"
    assert process.stdout.hex().encode() not in canonical(view)
    detached = verified.to_dict()
    detached["process"]["report"]["parsed_result"]["native_evidence"][
        "physical_authority"
    ] = True
    assert verified.native.payload == native.payload


@pytest.mark.parametrize(
    "fault,opens,attempts",
    [
        ("identity-change-preopen", 0, 1),
        ("identity-change", 1, 2),
        ("malformed-metadata", 0, 1),
    ],
)
def test_real_cm_parser_faults_retain_full_trace_without_any_write(
    fault, opens, attempts
):
    fixture = owned_fixture(metadata_scenario=fault)
    actual, result, evidence = fixture[2], fixture[5], fixture[9]
    assert actual.api_counts.open_attempts == opens
    assert actual.api_counts.write_attempts == 0
    trace = result.resolution_trace
    assert len(trace.to_dict()["attempts"]) == attempts
    assert trace.to_dict()["attempts"][-1]["status"] == "HELD"
    assert evidence.resolution.payload == trace.payload
    assert evidence.safe_summary()["process"]["status"] == "SUCCEEDED"
    assert evidence.safe_summary()["feedback"]["technical_response_valid"] is False
    assert evidence.safe_summary()["resolution"]["status"] != "PRE_WRITE_MATCHED"
    assert (
        len(result.payload) <= 48 * 1024 and len(evidence.payload) <= MAX_EVIDENCE_BYTES
    )


@pytest.mark.parametrize(
    "defect",
    [
        "missing",
        "hash",
        "binding",
        "deadline",
        "omit-second",
        "preopen-held",
        "prewrite-held",
        "phase",
        "legacy-schema",
        "unknown-field",
    ],
)
def test_trace_cannot_be_removed_rehashed_or_relabelled_around_actual_worker_counts(
    defect,
):
    request, _, _, _, _, result, *_ = owned_fixture()
    doc = result.to_dict()
    trace = doc["resolution_trace"]
    if defect == "missing":
        doc["resolution_trace"] = None
        doc["resolution_trace_sha256"] = None
    elif defect == "hash":
        doc["resolution_trace_sha256"] = "f" * 64
    elif defect == "legacy-schema":
        doc["schema"] = LEGACY_RESULT_SCHEMA
        del doc["resolution_trace"], doc["resolution_trace_sha256"]
    elif defect == "unknown-field":
        trace["physical_qualified"] = True
    elif defect == "binding":
        trace["reviewed_binding_sha256"] = "f" * 64
    elif defect == "deadline":
        trace["deadline_monotonic_ns"] += 1
    elif defect == "omit-second":
        trace["attempts"].pop()
    elif defect == "phase":
        trace["attempts"][0]["phase"] = "PRE_WRITE"
    else:
        index = 0 if defect == "preopen-held" else 1
        trace["attempts"][index].update(
            status="HELD", error_code="CONTROLLER_RESOLUTION_CANCELLED"
        )
    if defect not in {"missing", "hash", "legacy-schema"}:
        doc["resolution_trace_sha256"] = hashlib.sha256(canonical(trace)).hexdigest()
    with pytest.raises((ValueError, RuntimeError)):
        ArmOwnedResult(canonical(doc), request)


def test_current_builder_refuses_missing_trace_instead_of_echoing_expected_identity():
    request, _, _, native, feedback, *_ = owned_fixture()
    with pytest.raises(ArmOwnedProtocolError):
        build_arm_owned_result(
            request, feedback_evidence=feedback, native_evidence=native
        )


@pytest.mark.parametrize(
    "schema,duration", [(LEGACY_REQUEST_SCHEMA, 2000), (PREVIOUS_REQUEST_SCHEMA, 5000)]
)
def test_historical_complete_evidence_remains_purely_verifiable(schema, duration):
    fixture = owned_fixture(legacy=schema)
    request, evidence = fixture[0], fixture[9]
    verified = verify_arm_owned_evidence(
        evidence.payload,
        expected_request=request,
        expected_evidence_sha256=evidence.evidence_sha256,
    )
    assert verified.outer_request.to_dict()["schema"] == schema
    assert verified.outer_request.to_dict()["admission_timeout_ms"] == duration
    assert verified.feedback.result == fixture[2]
    assert verified.native.payload == fixture[3].payload
    assert verified.to_dict()["physical_authority"] is False
    assert verified.resolution is None
    assert verified.safe_summary()["schema"] == "rocell.arm_owned_evidence_summary.v1"
    assert "resolution" not in verified.safe_summary()


@pytest.mark.parametrize(
    "scenario",
    [
        IncapableWin32Scenario(startup_bytes=b"BOOT:1234\n"),
        IncapableWin32Scenario(
            pending_kind="read", pending_outcome="timeout", cancel_outcome="completed"
        ),
        IncapableWin32Scenario(short_write=4),
        IncapableWin32Scenario(response_bytes=b""),
        IncapableWin32Scenario(response_bytes=b"malformed response\n"),
        IncapableWin32Scenario(response_bytes=b'{"T":1051,"x":0,"y":0,"z":0}\n{}\n'),
        IncapableWin32Scenario(fail_operations=("close_event:1",)),
        IncapableWin32Scenario(
            pending_kind="read", pending_outcome="timeout", cancel_outcome="stuck"
        ),
    ],
)
def test_serial_faults_retain_actual_bytes_and_cleanup_without_process_success_confusion(
    scenario,
):
    request, _, actual, native, _, _, _, _, _, evidence, _, _ = owned_fixture(scenario)
    verified = verify_arm_owned_evidence(
        evidence.payload,
        expected_request=request,
        expected_evidence_sha256=evidence.evidence_sha256,
    )
    assert verified.feedback.result == actual
    assert verified.native.payload == native.payload
    assert actual.outcome.value != "SUCCEEDED_DIAGNOSTIC"
    assert verified.safe_summary()["status"] == "COMPLETE_INCAPABLE_EVIDENCE"
    assert verified.safe_summary()["feedback"]["status"] == actual.outcome.value
    assert verified.safe_summary()["process"]["status"] == "SUCCEEDED"
    assert verified.safe_summary()["device_cleanup_proven"] is False


@pytest.mark.parametrize(
    "defect",
    [
        "request",
        "process-hash",
        "stdout",
        "release",
        "ready",
        "raw-hash",
        "cleanup-success",
        "unknown-field",
        "native-substitution",
        "feedback-substitution",
    ],
)
def test_mutated_full_records_are_rejected_even_with_new_outer_hash(defect):
    request, _, _, _, _, _, _, _, _, evidence, _, _ = owned_fixture()
    doc = evidence.to_dict()
    report = doc["process"]["report"]
    if defect == "request":
        doc["request_sha256"] = "e" * 64
    elif defect == "process-hash":
        report["request_sha256"] = "e" * 64
    elif defect == "stdout":
        doc["process"]["stdout"]["base64"] = "e30="
    elif defect == "release":
        doc["release"] = None
    elif defect == "ready":
        doc["ready"]["child_pid"] = 4321
    elif defect == "raw-hash":
        report["stdout_sha256"] = "e" * 64
    elif defect == "cleanup-success":
        report["cleanup_errors"] = ["CLOSE_FAILED:job"]
    elif defect == "unknown-field":
        doc["physical_qualified"] = True
    elif defect == "native-substitution":
        report["parsed_result"]["native_evidence"]["native"][
            "cleanup_confirmed"
        ] = False
    else:
        report["parsed_result"]["feedback_evidence"]["source_sha256"] = "e" * 64
    payload = canonical(doc)
    with pytest.raises((ValueError, RuntimeError)):
        verify_arm_owned_evidence(
            payload,
            expected_request=request,
            expected_evidence_sha256=hashlib.sha256(payload).hexdigest(),
        )


def test_process_cleanup_failure_preserves_serial_records_but_is_not_complete():
    request, _, actual, _, _, _, ready, release, process, _, _, _ = owned_fixture()
    failed = replace(
        process,
        status="FAILED",
        cleanup_errors=("CLOSE_FAILED:job",),
        tree_exit_confirmed=False,
    )
    evidence = retain_arm_owned_evidence(
        request=request, process_result=failed, ready=ready, release_wire=release
    )
    assert evidence.feedback.result == actual
    view = evidence.safe_summary()
    assert view["status"] == "INCOMPLETE"
    assert view["native"]["native_cleanup_confirmed"] is True
    assert view["process"]["tree_exit_confirmed"] is False
    assert view["device_cleanup_proven"] is False


@pytest.mark.parametrize("status", ["FAILED", "CANCELLED", "TIMED_OUT"])
def test_partial_or_malformed_stdout_stays_raw_only_and_never_becomes_serial_receipt(
    status,
):
    request, inner, _ = make_request()
    raw = b'{"partial":not-json\x00\xff'
    process = OwnedWorkerResult(
        status,
        "OUTPUT_OR_WORKER_FAILED",
        (),
        request.request_sha256,
        inner.campaign_id,
        True,
        True,
        True,
        1,
        100,
        len(request.wire()),
        12,
        1,
        raw,
        b"private stderr",
        None,
    )
    evidence = retain_arm_owned_evidence(request=request, process_result=process)
    assert evidence.feedback is evidence.native is None
    assert evidence.safe_summary()["status"] == "INCOMPLETE"
    assert (
        evidence.to_dict()["process"]["stdout"]["sha256"]
        == hashlib.sha256(raw).hexdigest()
    )
    assert b"private stderr" not in canonical(evidence.safe_summary())


def test_primary_cleanup_text_is_private_and_raw_counts_are_never_truncated():
    request, inner, _ = make_request()
    process = OwnedWorkerResult(
        "FAILED",
        "endpoint COM999 private detail",
        tuple("CLOSE_FAILED:job" for _ in range(20)),
        request.request_sha256,
        inner.campaign_id,
        False,
        False,
        False,
        None,
        100,
        0,
        0,
        0,
        b"",
        b"",
        None,
    )
    evidence = retain_arm_owned_evidence(request=request, process_result=process)
    view = evidence.safe_summary()
    assert view["process"]["primary_error"] == "RETAINED_PROCESS_ERROR"
    assert len(view["process"]["cleanup_errors"]) == 16
    assert view["process"]["cleanup_errors_omitted"] == 4
    assert len(evidence.to_dict()["process"]["report"]["cleanup_errors"]) == 20
    with pytest.raises((ValueError, RuntimeError)):
        retain_arm_owned_evidence(
            request=request,
            process_result=replace(
                process,
                process_created=True,
                initial_thread_resumed=True,
                stdout=b"x" * (MAX_STDOUT_BYTES + 1),
            ),
        )


def test_trusted_outer_request_and_evidence_hash_are_both_required():
    request, _, _, _, _, _, _, _, _, evidence, _, _ = owned_fixture()
    with pytest.raises((ValueError, RuntimeError)):
        verify_arm_owned_evidence(
            evidence.payload,
            expected_request=request,
            expected_evidence_sha256="e" * 64,
        )
    other, _, _ = make_request(scenario="boot-bytes")
    with pytest.raises((ValueError, RuntimeError)):
        verify_arm_owned_evidence(
            evidence.payload,
            expected_request=other,
            expected_evidence_sha256=evidence.evidence_sha256,
        )
    with pytest.raises((ValueError, RuntimeError)):
        ArmOwnedEvidence(evidence.payload + b" ")


def test_individual_maxima_do_not_silently_bypass_full_aggregate_cap():
    request, inner, _ = make_request()
    process = OwnedWorkerResult(
        "FAILED",
        "MALFORMED_OUTPUT",
        tuple("E" * 512 for _ in range(64)),
        request.request_sha256,
        inner.campaign_id,
        True,
        True,
        True,
        1,
        100,
        len(request.wire()),
        12,
        1,
        b"x" * MAX_STDOUT_BYTES,
        b"y" * MAX_STDERR_BYTES,
        None,
    )
    before = (process.stdout, process.stderr, process.cleanup_errors)
    with pytest.raises((ValueError, RuntimeError)):
        retain_arm_owned_evidence(request=request, process_result=process)
    # Oversize remains a refusal. No truncation changes the retained observation
    # or manufactures an artifact whose apparent completeness fits the limit.
    assert (process.stdout, process.stderr, process.cleanup_errors) == before


def test_distinct_physical_held_result_never_acquires_rehearsal_feedback():
    request, inner, _ = make_request(
        origin=EvidenceOrigin.PHYSICAL_OBSERVATION, scenario="physical-held"
    )
    result = build_arm_owned_result(request)
    process = OwnedWorkerResult(
        "FAILED",
        "ARM_NONPURGING_PHYSICAL_ACTIVATION_HELD",
        (),
        request.request_sha256,
        inner.campaign_id,
        True,
        True,
        True,
        2,
        100,
        len(request.wire()),
        12,
        1,
        result.wire(),
        b"",
        result.to_dict(),
    )
    evidence = retain_arm_owned_evidence(request=request, process_result=process)
    verified = verify_arm_owned_evidence(
        evidence.payload,
        expected_request=request,
        expected_evidence_sha256=evidence.evidence_sha256,
    )
    assert verified.feedback is verified.native is None
    summary = verified.safe_summary()
    assert summary["status"] == "PHYSICAL_HELD"
    assert summary["provenance"] == "PHYSICAL_NONPURGING_ARM_HELD"
    assert summary["physical_authority"] is summary["arm_connected"] is False
    assert summary["final_power_state"] == "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION"
