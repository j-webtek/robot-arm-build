"""Pure installed v2 codecs: no subprocess, camera, original store or pixel I/O."""

from copy import deepcopy
from dataclasses import FrozenInstanceError
import json
from pathlib import Path

import pytest

from rocell.providers.windows.native_camera_activation_protocol import (
    NativeCameraActivationRequest,
    activation_release,
    parse_owned_activation_result,
    RESULT_SCHEMA,
)
from rocell.providers.windows.native_camera_protocol import (
    NativeCameraAdmissionRequest,
    NativeCameraReady,
    READY_SCHEMA,
    canonical,
    digest,
    parse_native_camera_ready,
    parse_owned_native_camera_result,
)
from rocell.providers.windows.native_camera_capture_protocol import (
    NativeCameraCaptureAdmissionRequest,
)
from rocell.providers.windows.camera_worker_client import (
    CameraWorkerError,
    WindowsCameraWorkerClient,
)
from test_native_camera_activation_expectation import build, enrollment
from test_native_camera_activation_observation import fixture as modeled_observation
from test_windows_camera_worker import receipt as modeled_receipt


def modeled_request(directory, purpose):
    expected = build(enrollment())
    endpoint = expected.to_dict()["endpoint"]
    capture = purpose == "capture"
    value = dict(
        schema=(
            "rocell.native_camera_capture_admission_request.v2"
            if capture
            else "rocell.native_camera_admission_request.v2"
        ),
        attempt_id="attempt-1",
        session_id="MODELED-pipe-session",
        endpoint=endpoint,
        endpoint_sha256=digest(endpoint.encode()),
        native_duration_ms=5000,
        admission_timeout_ms=5000 if capture else 2000,
        activation_identity_json=expected.payload.decode("ascii"),
    )
    value.update(
        {
            key: "a" * 64
            for key in (
                "source_sha256",
                "operation_sha256",
                "selected_identity_sha256",
                "helper_sha256",
                "runtime_registration_sha256",
                "camera_request_sha256",
                "permit_sha256",
            )
        }
    )
    if capture:
        value["capture_json"] = canonical(
            dict(
                width=5472,
                height=3648,
                fps_numerator=9,
                fps_denominator=1,
                subtype="YUY2",
                frame_count=1,
                max_frame_bytes=39_923_712,
                max_total_bytes=39_923_712,
                output_directory=str(directory / "capture-attempt-1"),
                controls="brightness,-3,manual;gain,0,auto",
                requested_stride_bytes="-10944",
            )
        ).decode("ascii")
    return value, expected


def request(purpose="probe"):
    fields, _ = modeled_request(Path(r"C:\MODELED-absent-output"), purpose)
    if purpose == "capture":
        config = json.loads(fields["capture_json"])
        config.update(
            width=4,
            height=2,
            max_frame_bytes=16,
            max_total_bytes=16,
            controls="",
            requested_stride_bytes="8",
        )
        fields["capture_json"] = canonical(config).decode("ascii")
    return NativeCameraActivationRequest(canonical(fields))


def ready_for(req, pid=123):
    return NativeCameraReady(
        canonical(
            dict(
                schema=READY_SCHEMA,
                request_sha256=req.request_sha256,
                child_pid=pid,
                challenge="1" * 64,
            )
        )
    )


def fixture(purpose="probe"):
    req = request(purpose)
    ready = ready_for(req)
    expected, observation = modeled_observation()
    assert expected.payload == req.expectation.payload
    body = modeled_receipt(purpose)
    endpoint = req.to_dict()["endpoint"]
    body["selected_endpoint"] = body["devices"][0]["symbolic_link"] = endpoint
    if purpose == "capture":
        body["requested_mode"]["stride_bytes"] = 8
    return (
        req,
        ready,
        dict(
            schema=RESULT_SCHEMA,
            request_sha256=req.request_sha256,
            child_pid=123,
            challenge_sha256=ready.challenge_sha256,
            permit_sha256=req.to_dict()["permit_sha256"],
            activation_identity=observation,
            native_receipt=body,
        ),
    )


def parse(raw, req, ready, *, pid=123, code=0):
    return parse_owned_activation_result(
        canonical(raw),
        request=req,
        ready=ready,
        expected_child_pid=pid,
        returncode=code,
    )


@pytest.mark.parametrize("purpose", ["probe", "capture"])
def test_codec_is_immutable_and_filesystem_provider_inert(monkeypatch, purpose):
    req, ready, raw = fixture(purpose)
    before = deepcopy(raw)

    def forbidden(*args, **kwargs):
        pytest.fail("Pure wire codec attempted an effect")

    with monkeypatch.context() as patch:
        for name in ("open", "stat", "lstat", "mkdir", "resolve"):
            patch.setattr(Path, name, forbidden)
        for name in (
            "probe",
            "capture",
            "enumerate_metadata",
            "resolve_identity_metadata",
        ):
            patch.setattr(WindowsCameraWorkerClient, name, forbidden)
        value = parse(raw, req, ready)
        assert value.receipt.operation == purpose and value.receipt.cleanup_confirmed
        assert value.activation.independently_matches is True
        assert value.to_dict() == raw
        copy = value.to_dict()
        copy["native_receipt"]["status"] = "changed"
        assert value.to_dict() == before
        with pytest.raises(FrozenInstanceError):
            value.wire = b"{}"
        assert not hasattr(value, "physical_authority")
        assert not hasattr(value, "permit")
        assert json.loads(activation_release(req, ready, expected_child_pid=123))[
            "request_sha256"
        ] == digest(req.payload)
    assert raw == before


@pytest.mark.parametrize("purpose", ["probe", "capture"])
@pytest.mark.parametrize(
    "fault",
    [
        "schema",
        "extra",
        "missing",
        "zero-hash",
        "upper-hash",
        "endpoint",
        "duration",
        "admission",
        "identity-type",
        "identity-utf8",
        "identity-extra",
        "id",
        "bool-duration",
        "capture-field",
    ],
)
def test_v2_request_rejects_malformed_or_downgraded_contract(purpose, fault):
    fields = request(purpose).to_dict()
    if fault == "schema":
        fields["schema"] = fields["schema"][:-1] + "1"
    elif fault == "extra":
        fields["grant"] = True
    elif fault == "missing":
        fields.pop("activation_identity_json")
    elif fault == "zero-hash":
        fields["source_sha256"] = "0" * 64
    elif fault == "upper-hash":
        fields["source_sha256"] = "A" * 64
    elif fault == "endpoint":
        fields["endpoint"] += "changed"
    elif fault == "duration":
        fields["native_duration_ms"] = 5001
    elif fault == "admission":
        fields["admission_timeout_ms"] = 2001
    elif fault == "identity-type":
        fields["activation_identity_json"] = {}
    elif fault == "identity-utf8":
        fields["activation_identity_json"] += "é"
    elif fault == "identity-extra":
        expected = json.loads(fields["activation_identity_json"])
        expected["physical_authority"] = True
        fields["activation_identity_json"] = canonical(expected).decode("ascii")
    elif fault == "id":
        fields["attempt_id"] = "../not-an-id"
    elif fault == "bool-duration":
        fields["native_duration_ms"] = True
    elif purpose == "probe":
        fields["capture_json"] = "{}"
    else:
        fields.pop("capture_json")
    with pytest.raises(ValueError):
        NativeCameraActivationRequest(canonical(fields))


@pytest.mark.parametrize("purpose", ["probe", "capture"])
def test_old_request_and_result_codecs_are_not_a_downgrade_lane(purpose):
    req, ready, raw = fixture(purpose)
    for old_type in (NativeCameraAdmissionRequest, NativeCameraCaptureAdmissionRequest):
        with pytest.raises(ValueError):
            old_type(req.payload)
    with pytest.raises(ValueError):
        parse_owned_native_camera_result(
            canonical(raw), request=req, ready=ready, returncode=0
        )


@pytest.mark.parametrize("purpose", ["probe", "capture"])
@pytest.mark.parametrize(
    "field,value",
    [
        ("schema", "rocell.owned_native_camera_result.v1"),
        ("request_sha256", "f" * 64),
        ("child_pid", 124),
        ("child_pid", True),
        ("challenge_sha256", "f" * 64),
        ("permit_sha256", "f" * 64),
        ("physical_authority", True),
    ],
)
def test_result_requires_exact_child_full_request_and_permit(purpose, field, value):
    req, ready, raw = fixture(purpose)
    raw[field] = value
    with pytest.raises(ValueError):
        parse(raw, req, ready)


@pytest.mark.parametrize("purpose", ["probe", "capture"])
@pytest.mark.parametrize(
    "fault",
    [
        "ready-pid",
        "ready-request",
        "expected-pid",
        "exit",
        "bool-exit",
        "missing-count",
        "activation-unchecked",
        "wrong-identity",
        "wrong-operation",
        "cleanup",
        "empty",
        "oversize",
        "duplicate",
        "nonfinite",
        "trailing",
    ],
)
def test_independent_result_layers_cannot_contradict_each_other(purpose, fault):
    req, ready, raw = fixture(purpose)
    pid, code = 123, 0
    if fault == "ready-pid":
        ready = ready_for(req, 124)
    elif fault == "ready-request":
        other = ready.to_dict()
        other["request_sha256"] = "f" * 64
        ready = NativeCameraReady(canonical(other))
    elif fault == "expected-pid":
        pid = 124
    elif fault == "exit":
        code = 1
    elif fault == "bool-exit":
        code = False
    elif fault == "missing-count":
        raw["native_receipt"]["counts"].pop("source_opened")
    elif fault == "activation-unchecked":
        raw["activation_identity"]["activation_callback_entered"] = False
    elif fault == "wrong-identity":
        raw["activation_identity"]["original_identity_sha256"] = "f" * 64
    elif fault == "wrong-operation":
        raw["native_receipt"]["operation"] = "inventory"
    elif fault == "cleanup":
        raw["native_receipt"]["cleanup"]["source_shutdown_hr"] = -1
    wire = canonical(raw)
    if fault == "empty":
        wire = b""
    elif fault == "oversize":
        wire += b" " * (256 * 1024)
    elif fault == "duplicate":
        wire = wire.replace(b'"child_pid":123', b'"child_pid":123,"child_pid":123')
    elif fault == "nonfinite":
        wire = wire.replace(b'"child_pid":123', b'"child_pid":NaN')
    elif fault == "trailing":
        wire += b"{}"
    with pytest.raises((ValueError, CameraWorkerError)):
        parse_owned_activation_result(
            wire, request=req, ready=ready, expected_child_pid=pid, returncode=code
        )


@pytest.mark.parametrize(
    "fault",
    [
        "requested-rational",
        "observed-stride",
        "frame-traversal",
        "frame-length",
        "control-write",
        "readback",
    ],
)
def test_capture_mode_controls_and_frame_metadata_are_validated_without_pixel_io(fault):
    req, ready, raw = fixture("capture")
    body = raw["native_receipt"]
    if fault == "requested-rational":
        body["requested_mode"].update(fps_numerator=18, fps_denominator=2)
    elif fault == "observed-stride":
        body["observed_mode"]["stride_bytes"] = -8
    elif fault == "frame-traversal":
        body["frames"][0]["filename"] = "../frame.yuy2"
    elif fault == "frame-length":
        body["frames"][0]["length_bytes"] = 17
    elif fault == "control-write":
        body["counts"]["control_set_attempts"] = 1
    else:
        fields = req.to_dict()
        config = json.loads(fields["capture_json"])
        config["controls"] = "brightness,0,manual"
        fields["capture_json"] = canonical(config).decode("ascii")
        req = NativeCameraActivationRequest(canonical(fields))
        ready = ready_for(req)
        raw["request_sha256"] = req.request_sha256
        body["counts"]["control_set_attempts"] = 1
    with pytest.raises((ValueError, CameraWorkerError)):
        parse(raw, req, ready)
