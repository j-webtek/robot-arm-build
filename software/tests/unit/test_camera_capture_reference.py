"""Full-resolution metadata and synthetic hashes; no pixel or device operations.

These tests validate the pure contract, not durable original storage. The native
codecs/observation joins are real; physical producers and pixel hashes are modeled.
"""

from dataclasses import asdict, replace
import json

import pytest

from rocell.application import camera_capture_reference as module
from rocell.providers.windows.camera_worker_client import NativeFrameArtifact
from rocell.providers.windows.native_camera_protocol import canonical, digest
from test_camera_operating_evidence_preflight import case
from test_physical_camera_configuration import forbid_process_and_devices
from test_native_camera_activation_supervisor import no_physical_owner

KEY = "operation-" + "7" * 32


def inputs(tmp_path, monkeypatch, *, version="v2", fault=None, fraction=1):
    values, capture = case(tmp_path, monkeypatch, version=version, fraction=fraction)
    native = capture(
        "capture-reference", fault=fault, observed_fraction=fraction
    ).native
    observed = module._verified_observation(
        native.evidence,
        prepared=native.preparation,
        expected_evidence_sha256=native.expected_evidence_sha256,
        expected_supervision_sha256=native.expected_supervision_sha256,
    )
    frames = observed.native_receipt.frames
    frame = (
        NativeFrameArtifact(**asdict(frames[0]), sha256="e" * 64) if frames else None
    )
    return dict(
        native=native,
        configuration_payload=values["configuration_payload"],
        expected_settings_epoch=values["expected_settings_epoch"],
        request_key=KEY,
        frame=frame,
        manifest_sha256="c" * 64,
        ingest_envelope_sha256="d" * 64,
    )


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    args = inputs(tmp_path, monkeypatch)
    return args, module.build_capture_reference(**args)


def verify(args, reference, **overrides):
    values = dict(
        expected_reference_sha256=reference.sha256,
        expected_request_key=args["request_key"],
        native=args["native"],
        configuration_payload=args["configuration_payload"],
        expected_settings_epoch=args["expected_settings_epoch"],
    )
    values.update(overrides)
    return module.verify_capture_reference(reference.payload, **values)


def test_capture_reference_rebuilds_native_metadata_without_store_authority(prepared):
    args, reference = prepared
    assert verify(args, reference) == reference
    data = reference.to_dict()
    assert data["frame"]["length_bytes"] == 5472 * 3648 * 2
    assert data["frame"]["sha256"] == "e" * 64
    assert all(data[key] is False for key in module.FALSE_FIELDS)
    assert data["origin"] == module.ORIGIN
    assert "NOT_EXPOSURE_TIME" in data["timestamp_semantics"]
    assert len(reference.payload) < module.MAX_BYTES
    data["frame"]["sha256"] = "f" * 64
    assert reference.to_dict()["frame"]["sha256"] == "e" * 64


def test_exact_driver_rational_is_preserved_not_rewritten(tmp_path, monkeypatch):
    args = inputs(tmp_path, monkeypatch, fraction=1000)
    reference = module.build_capture_reference(**args)
    assert verify(args, reference) == reference
    assert reference.to_dict()["readback"]["observed_mode"]["fps_denominator"] == 1000


@pytest.mark.parametrize(
    "field,value",
    [
        ("filename", "../../elsewhere"),
        ("host_sequence", 1),
        ("length_bytes", 16),
        ("stride_bytes", -10944),
        ("row0_offset_bytes", 4),
        ("media_timestamp_100ns", 987654),
        ("host_arrival_qpc", 987654),
        ("qpc_frequency", 987654),
        ("discontinuity", True),
    ],
)
def test_artifact_cannot_disagree_with_native_metadata(prepared, field, value):
    args, _ = prepared
    if getattr(args["frame"], field) == value:
        value = False if field == "discontinuity" else 987655
    args["frame"] = replace(args["frame"], **{field: value})
    with pytest.raises(module.CameraCaptureReferenceError):
        module.build_capture_reference(**args)


@pytest.mark.parametrize(
    "field", ["sha256", "manifest_sha256", "ingest_envelope_sha256"]
)
@pytest.mark.parametrize("value", ["0" * 64, "", True, "F" * 64])
def test_no_missing_or_placeholder_capture_hash(prepared, field, value):
    args, _ = prepared
    if field == "sha256":
        args["frame"] = replace(args["frame"], sha256=value)
    else:
        args[field] = value
    with pytest.raises(module.CameraCaptureReferenceError):
        module.build_capture_reference(**args)


@pytest.mark.parametrize(
    "key,value",
    [
        ("expected_reference_sha256", "f" * 64),
        ("expected_request_key", "operation-" + "8" * 32),
        ("expected_settings_epoch", "f" * 64),
        ("native", {}),
        ("configuration_payload", b"{}"),
    ],
)
def test_reconstruction_rejects_another_original_context(prepared, key, value):
    args, reference = prepared
    with pytest.raises(module.CameraCaptureReferenceError):
        verify(args, reference, **{key: value})


def test_legacy_native_pair_cannot_be_promoted(tmp_path, monkeypatch):
    args = inputs(tmp_path, monkeypatch, version="legacy")
    with pytest.raises(module.CameraCaptureReferenceError):
        module.build_capture_reference(**args)


@pytest.mark.parametrize(
    "fault", ["value", "auto", "native_cleanup", "missing_control"]
)
def test_failed_or_mismatched_capture_has_no_reference(tmp_path, monkeypatch, fault):
    args = inputs(tmp_path, monkeypatch, fault=fault)
    with pytest.raises(module.CameraCaptureReferenceError):
        module.build_capture_reference(**args)


@pytest.mark.parametrize(
    "fault",
    [
        "extra",
        "missing",
        "schema",
        "origin",
        "stage",
        "request",
        "native_hash",
        "native_extra",
        "readback_hash",
        "frame_extra",
        "frame_bool",
        "frame_bounds",
        "row0",
        "timestamp",
        "clock",
        "authority",
        "noncanonical",
    ],
)
def test_closed_record_rejects_malformed_serialization(prepared, fault):
    _, reference = prepared
    data = reference.to_dict()
    if fault == "extra":
        data["unexpected"] = True
    elif fault == "missing":
        data.pop("frame_freshness_assessed")
    elif fault in ("schema", "origin", "stage"):
        data[fault] = "wrong"
    elif fault == "request":
        data["request_key"] = "../../file"
    elif fault == "native_hash":
        data["native_evidence"]["supervision_sha256"] = None
    elif fault == "native_extra":
        data["native_evidence"]["extra"] = "e" * 64
    elif fault == "readback_hash":
        data["readback_sha256"] = "f" * 64
    elif fault == "frame_extra":
        data["frame"]["path"] = "not-allowed"
    elif fault == "frame_bool":
        data["frame"]["host_sequence"] = False
    elif fault == "frame_bounds":
        data["frame"]["length_bytes"] = 2**50
    elif fault == "row0":
        data["frame"]["row0_offset_bytes"] = 1
    elif fault == "timestamp":
        data["frame"]["media_timestamp_100ns"] = 2**63
    elif fault == "clock":
        data["frame"]["qpc_frequency"] = 0
    elif fault == "authority":
        data["original_store_authenticated"] = True
    raw = json.dumps(data).encode() if fault == "noncanonical" else canonical(data)
    with pytest.raises(module.CameraCaptureReferenceError):
        module.CameraCaptureReference(raw)


def test_payload_bytes_and_depth_are_bounded(prepared):
    _, reference = prepared
    for raw in (
        reference.payload.decode(),
        b" " * (module.MAX_BYTES + 1),
        b'{"schema":1,"schema":2}',
        b'{"schema":NaN}',
        b"[]",
        b"{",
    ):
        with pytest.raises(module.CameraCaptureReferenceError):
            module.CameraCaptureReference(raw)


@pytest.mark.parametrize("field", module.FALSE_FIELDS)
@pytest.mark.parametrize("value", [True, 0, "false"])
def test_reference_cannot_claim_authority_or_nonliteral_flags(prepared, field, value):
    _, reference = prepared
    data = reference.to_dict()
    data[field] = value
    with pytest.raises(module.CameraCaptureReferenceError):
        module.CameraCaptureReference(canonical(data))


def test_matching_serialized_self_hash_is_not_independent_original_verification(
    prepared,
):
    args, reference = prepared
    data = reference.to_dict()
    data["frame"]["media_timestamp_100ns"] += 1
    changed = module.CameraCaptureReference(canonical(data))
    with pytest.raises(module.CameraCaptureReferenceError):
        verify(args, changed)
