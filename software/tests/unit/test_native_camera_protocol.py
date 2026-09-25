"""Pure native admission contracts; no process, files or camera is accessed."""

from dataclasses import asdict, FrozenInstanceError, replace
import json
from pathlib import Path

import pytest

from rocell.providers.windows.camera_worker_client import (
    CameraCampaignBudget,
    CameraWorkerError,
    WindowsCameraWorkerClient,
)
from rocell.providers.windows.native_camera_protocol import (
    NativeCameraAdmissionRequest,
    NativeCameraReady,
    NativeCameraProtocolError,
    READY_SCHEMA,
    RESULT_SCHEMA,
    canonical,
    digest,
    native_camera_release,
    parse_native_camera_ready,
    parse_owned_native_camera_result,
)
from rocell.providers.windows.native_camera_registration import (
    NativeCameraRuntimeRegistration,
    PreparedOwnedNativeProbe,
    create_native_camera_runtime_registration,
    prepare_owned_native_probe,
    HELPER_RELATIVE_PATH,
)
from rocell.providers.windows.owned_worker_process import WorkerProcessBudget
from test_windows_camera_worker import BINDING, receipt


def prepared(tmp_path):
    runtime = create_native_camera_runtime_registration(
        tmp_path,
        source_sha256="a" * 64,
        catalog_sha256="b" * 64,
        helper_sha256="c" * 64,
        build_record_sha256="d" * 64,
    )
    client = WindowsCameraWorkerClient(tmp_path / HELPER_RELATIVE_PATH, "c" * 64)
    plan = client.prepare_probe(
        BINDING,
        source_sha256="a" * 64,
        campaign_id="attempt-1",
        budget=CameraCampaignBudget(5000, 1, 39923712, 39923712),
    )
    args = dict(
        session_id="session-1",
        operation_sha256="e" * 64,
        permit_sha256="f" * 64,
        working_directory=tmp_path / "working",
    )
    return runtime, plan, args


def joined(tmp_path):
    runtime, plan, args = prepared(tmp_path)
    return prepare_owned_native_probe(runtime, plan, **args)


def ready_for(request):
    return NativeCameraReady(
        canonical(
            dict(
                schema=READY_SCHEMA,
                request_sha256=request.request_sha256,
                child_pid=123,
                challenge="1" * 64,
            )
        )
    )


def result_for(request, ready):
    return dict(
        schema=RESULT_SCHEMA,
        request_sha256=request.request_sha256,
        child_pid=123,
        challenge_sha256=ready.challenge_sha256,
        permit_sha256=request.to_dict()["permit_sha256"],
        native_receipt=receipt("probe"),
    )


def test_preparation_and_all_properties_are_filesystem_and_process_inert(
    tmp_path, monkeypatch
):
    def forbidden(*a, **kw):
        pytest.fail("Inert native preparation attempted an effect")

    with monkeypatch.context() as patch:
        for method in ("open", "stat", "lstat", "mkdir", "resolve"):
            patch.setattr(Path, method, forbidden)
        for method in (
            "probe",
            "capture",
            "enumerate_metadata",
            "resolve_identity_metadata",
        ):
            patch.setattr(WindowsCameraWorkerClient, method, forbidden)
        value = joined(tmp_path)
        assert value.runtime.to_dict()["dispatch_enabled"] is False
        assert value.registration.composition == "PHYSICAL_UNQUALIFIED"
        assert value.registration.argv == (
            "--owned-probe",
            "--request-sha256",
            value.admission_request.request_sha256,
        )
        assert value.required_lifetime_ns == 12_000_000_000
        assert value.camera_plan.request.operation == "probe"
        assert value.camera_plan.request.output_directory is None
        assert value.camera_plan.request.controls == ()
        assert value.admission_request.to_dict()["camera_request_sha256"] == digest(
            canonical(asdict(value.camera_plan.request))
        )
        assert value.registration.executable.path == tmp_path / HELPER_RELATIVE_PATH


def test_canonical_owned_payloads_are_immutable_and_copy_isolated(tmp_path):
    value = joined(tmp_path)
    for item in (
        value,
        value.runtime,
        value.admission_request,
        ready_for(value.admission_request),
    ):
        snapshot = item.to_dict()
        snapshot["schema"] = "changed"
        assert item.to_dict()["schema"] != "changed"
        with pytest.raises(FrozenInstanceError):
            item.payload = b"{}"
    assert (
        PreparedOwnedNativeProbe(value.payload).preparation_sha256
        == value.preparation_sha256
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("dispatch_enabled", True),
        ("physical_authority", True),
        ("driver_qualified", True),
        ("status", "APPROVED"),
        ("purpose", "CAPTURE"),
        ("allowed_operations", ["inventory", "probe"]),
        ("source_sha256", "A" * 64),
        ("workspace", "relative"),
        ("extra", False),
    ],
)
def test_runtime_candidate_never_becomes_approval(tmp_path, field, value):
    runtime, _, _ = prepared(tmp_path)
    body = runtime.to_dict()
    body[field] = value
    with pytest.raises(ValueError):
        NativeCameraRuntimeRegistration(canonical(body))


@pytest.mark.parametrize("pin", ["helper", "build_record"])
def test_runtime_fixed_pins_cannot_be_repointed(tmp_path, pin):
    body = prepared(tmp_path)[0].to_dict()
    body[pin]["path"] = str(tmp_path / "another.exe")
    with pytest.raises(ValueError, match="FIXED_NATIVE_BUILD_PINS"):
        NativeCameraRuntimeRegistration(canonical(body))


@pytest.mark.parametrize(
    "fault",
    [
        "request-subclass",
        "request-extra",
        "plan-extra",
        "list-args",
        "list-controls",
        "helper",
        "source",
        "arguments",
        "capture",
        "output",
        "budget",
        "process-budget",
    ],
)
def test_exact_prepared_plan_denies_mutated_nested_contracts(tmp_path, fault):
    runtime, plan, args = prepared(tmp_path)
    request = plan.request
    if fault == "request-subclass":

        class Subtype(type(request)):
            pass

        plan = replace(plan, request=Subtype(**vars(request)))
    elif fault == "request-extra":
        object.__setattr__(request, "unexpected", 0)
    elif fault == "plan-extra":
        object.__setattr__(plan, "unexpected", 0)
    elif fault == "list-args":
        plan = replace(plan, arguments=list(plan.arguments))
    elif fault == "list-controls":
        plan = replace(plan, request=replace(request, controls=[]))
    elif fault == "helper":
        plan = replace(plan, request=replace(request, helper_sha256="0" * 64))
    elif fault == "source":
        plan = WindowsCameraWorkerClient(
            tmp_path / HELPER_RELATIVE_PATH, "c" * 64
        ).prepare_probe(
            request.binding,
            source_sha256="0" * 64,
            campaign_id=request.campaign_id,
            budget=request.budget,
        )
    elif fault == "arguments":
        plan = replace(plan, arguments=plan.arguments + ("--extra",))
    elif fault == "capture":
        plan = replace(plan, request=replace(request, operation="capture"))
    elif fault == "output":
        plan = replace(plan, request=replace(request, output_directory=str(tmp_path)))
    elif fault == "budget":
        plan = WindowsCameraWorkerClient(
            tmp_path / HELPER_RELATIVE_PATH, "c" * 64
        ).prepare_probe(
            request.binding,
            source_sha256=request.source_sha256,
            campaign_id=request.campaign_id,
            budget=CameraCampaignBudget(500, 1, 39923712, 39923712),
        )
    else:
        args["process_budget"] = WorkerProcessBudget(run_timeout_ms=9000)
    with pytest.raises(ValueError):
        prepare_owned_native_probe(runtime, plan, **args)


@pytest.mark.parametrize(
    "field,value",
    [
        ("native_duration_ms", True),
        ("native_duration_ms", 5001),
        ("admission_timeout_ms", 0),
        ("attempt_id", "bad id"),
        ("session_id", "x" * 97),
        ("endpoint", "bad\nendpoint"),
        ("endpoint_sha256", "0" * 64),
        ("permit_sha256", "A" * 64),
        ("selected_identity_sha256", None),
        ("authorized", True),
        ("schema", "other"),
    ],
)
def test_request_strict_fields_and_bindings(tmp_path, field, value):
    body = joined(tmp_path).admission_request.to_dict()
    body[field] = value
    with pytest.raises(ValueError):
        NativeCameraAdmissionRequest(canonical(body))


@pytest.mark.parametrize(
    "wire",
    [
        b"{}",
        b"{}\n",
        b'{"x":1,"x":1}',
        b'{"x":NaN}',
        b" " + b"{}",
        b"[" * 2000,
        b"x" * 16384,
    ],
)
def test_request_bounded_json_fail_closed(wire):
    with pytest.raises(ValueError):
        NativeCameraAdmissionRequest(wire)


def test_ready_and_release_bind_actual_child_challenge_and_permit(tmp_path):
    request = joined(tmp_path).admission_request
    ready = ready_for(request)
    parsed = parse_native_camera_ready(
        ready.payload + b"\n",
        expected_request_sha256=request.request_sha256,
        expected_child_pid=123,
    )
    assert parsed == ready
    release = json.loads(native_camera_release(request, ready))
    assert release == dict(
        schema="rocell.native_camera_admission_release.v1",
        request_sha256=request.request_sha256,
        child_pid=123,
        challenge_sha256=digest(("1" * 64).encode()),
        permit_sha256="f" * 64,
    )
    for pid, sha in [
        (124, request.request_sha256),
        (True, request.request_sha256),
        (123, "0" * 64),
    ]:
        with pytest.raises(ValueError):
            parse_native_camera_ready(
                ready.payload + b"\n",
                expected_request_sha256=sha,
                expected_child_pid=pid,
            )
    for wire in [
        ready.payload,
        ready.payload + b"\n\n",
        ready.payload + b"\r\n",
        b"x" * 1025,
    ]:
        with pytest.raises(ValueError):
            parse_native_camera_ready(
                wire,
                expected_request_sha256=request.request_sha256,
                expected_child_pid=123,
            )


def test_release_cannot_mix_ready_from_another_request(tmp_path):
    request = joined(tmp_path).admission_request
    altered = request.to_dict()
    altered["permit_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="RELEASE_REQUEST_MISMATCH"):
        native_camera_release(
            NativeCameraAdmissionRequest(canonical(altered)), ready_for(request)
        )


def test_probe_result_keeps_actual_native_counts_cleanup_and_is_pure(
    tmp_path, monkeypatch
):
    request = joined(tmp_path).admission_request
    ready = ready_for(request)
    body = result_for(request, ready)

    def forbidden(*a, **kw):
        pytest.fail("Probe parser attempted filesystem access")

    monkeypatch.setattr(Path, "open", forbidden)
    observed, parsed = parse_owned_native_camera_result(
        canonical(body), request=request, ready=ready, returncode=0
    )
    assert parsed.cleanup_confirmed and parsed.counts["source_opened"] == 1
    assert parsed.counts["samples_received"] == 0 and parsed.frames == ()
    assert observed == body
    body["native_receipt"]["cleanup"]["source_shutdown_hr"] = -1
    body["native_receipt"]["status"] = "FAILED"
    body["native_receipt"]["reason_code"] = "SOURCE_SHUTDOWN_FAILED"
    _, failed = parse_owned_native_camera_result(
        canonical(body), request=request, ready=ready, returncode=1
    )
    assert not failed.cleanup_confirmed and failed.effect_uncertain


@pytest.mark.parametrize(
    "fault",
    [
        "pid",
        "bool-pid",
        "challenge",
        "permit",
        "request",
        "schema",
        "extra",
        "native-operation",
        "native-frames",
        "native-endpoint",
        "exit",
        "bool-exit",
    ],
)
def test_probe_result_rejects_misbinding_and_nonprobe_payloads(tmp_path, fault):
    request = joined(tmp_path).admission_request
    ready = ready_for(request)
    body = result_for(request, ready)
    exitcode = 0
    if fault == "pid":
        body["child_pid"] = 124
    elif fault == "bool-pid":
        body["child_pid"] = True
    elif fault in ("challenge", "permit", "request"):
        body[fault + "_sha256"] = "0" * 64
    elif fault == "schema":
        body["schema"] = "other"
    elif fault == "extra":
        body["extra"] = 0
    elif fault == "native-operation":
        body["native_receipt"]["operation"] = "capture"
    elif fault == "native-frames":
        body["native_receipt"]["frames"] = receipt("capture")["frames"]
    elif fault == "native-endpoint":
        body["native_receipt"]["selected_endpoint"] = "other"
    elif fault == "exit":
        exitcode = 1
    else:
        exitcode = True
    with pytest.raises((ValueError, CameraWorkerError)):
        parse_owned_native_camera_result(
            canonical(body), request=request, ready=ready, returncode=exitcode
        )
