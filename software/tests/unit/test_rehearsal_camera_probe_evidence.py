"""Pure typed probe fixtures; no process, file, M1 store or device is accessed."""

import base64
from copy import deepcopy
from dataclasses import replace
import hashlib
from pathlib import Path

import pytest

from rocell.application import rehearsal_camera_probe_evidence as evidence
from rocell.application.rehearsal_owned_camera_evidence import _canonical, _plain
from rocell.providers.windows.camera_worker_client import (
    CameraCampaignBudget,
    CameraEndpointBinding,
    WindowsCameraWorkerClient,
)
from rocell.providers.windows.owned_camera_codec import (
    CAMERA_FIXTURE_PATH,
    CONFIG_PAYLOAD_SCHEMA,
    CONFIG_RESULT_SCHEMA,
    FRAME_BYTES,
    MODE,
    PROVENANCE,
    fixture_control_observations,
)
from rocell.providers.windows.owned_worker_process import OwnedWorkerResult


def probe_inputs():
    """Actual native parser/closed descriptors, explicitly unexecuted process data."""
    binding = {
        "session_id": "rehearsal-" + "1" * 32,
        "attempt_id": "attempt-" + "2" * 32,
        "source_sha256": "3" * 64,
        "permit_sha256": "4" * 64,
        "operation_sha256": "5" * 64,
        "selected_identity_sha256": "6" * 64,
    }
    endpoint = "incapable-fixture-only"
    reviewed = CameraEndpointBinding(
        endpoint,
        hashlib.sha256(endpoint.encode()).hexdigest(),
        binding["selected_identity_sha256"],
    )
    client = WindowsCameraWorkerClient(CAMERA_FIXTURE_PATH, "7" * 64)
    prepared = client.prepare_probe(
        reviewed,
        source_sha256=binding["source_sha256"],
        campaign_id=binding["attempt_id"],
        budget=CameraCampaignBudget(5000, 1, FRAME_BYTES, FRAME_BYTES),
    )
    native_wire = {
        "schema": "rocell.windows_camera.v1",
        "operation": "probe",
        "status": "OK",
        "reason_code": None,
        "selected_endpoint": endpoint,
        "devices": [
            {"symbolic_link": endpoint, "friendly_name": "Explicit pure fixture"}
        ],
        "modes": [dict(MODE)],
        "requested_mode": None,
        "observed_mode": None,
        "controls": list(fixture_control_observations()),
        "frames": [],
        "counts": {
            "source_activation_attempts": 1,
            "source_opened": 1,
            "control_set_attempts": 0,
            "samples_received": 0,
            "frames_written": 0,
            "source_shutdown_attempts": 1,
        },
        "cleanup": {
            "source_shutdown_hr": 0,
            "source_released": True,
            "mf_shutdown_hr": 0,
            "com_uninitialized": True,
        },
        "limitations": [PROVENANCE],
    }
    native = WindowsCameraWorkerClient._parse_receipt(
        native_wire, "probe", reviewed, None, (prepared.request.budget, None), ()
    )
    payload = {
        "schema": CONFIG_PAYLOAD_SCHEMA,
        "provenance": PROVENANCE,
        "scenario": "nominal",
        "camera_request": _plain(prepared.request),
        "native_arguments": list(prepared.arguments),
        "templates": [],
        "working_directory": "C:/explicit-uncreated-probe-fixture",
    }
    wire = {
        "schema": CONFIG_RESULT_SCHEMA,
        "request_sha256": "8" * 64,
        "attempt_id": binding["attempt_id"],
        "physical_authority": False,
        "fixture_result": {
            "scenario": "nominal",
            "provenance": PROVENANCE,
            "camera_request_sha256": hashlib.sha256(
                _canonical(_plain(prepared.request))
            ).hexdigest(),
            "template_sha256s": [],
            "native_receipt": native_wire,
        },
    }
    process = OwnedWorkerResult(
        "SUCCEEDED",
        None,
        (),
        wire["request_sha256"],
        binding["attempt_id"],
        True,
        True,
        True,
        0,
        123456,
        1024,
        20,
        1,
        _canonical(wire) + b"\n",
        b"pure fixture stderr\n",
        wire,
    )
    return dict(
        binding=binding,
        activation_request=prepared.request,
        process_result=process,
        native_receipt=native,
        owned_payload=payload,
        error=None,
    )


def retained_probe():
    inputs = probe_inputs()
    return inputs, evidence.retain_rehearsal_camera_probe_evidence(**inputs)


def test_complete_probe_lossless_full_bytes_and_exact_capability_projection():
    inputs, artifact = retained_probe()
    view, full = artifact.view(), artifact.to_dict()
    assert view["status"] == "COMPLETE_PROBE_REHEARSAL"
    assert view["blockers"] == []
    assert view["native"]["mode_count"] == 1
    assert view["native"]["control_count"] == 6
    assert view["native"]["counts"]["frames_written"] == 0
    assert (
        view["device_cleanup_proven"]
        is view["physical_authority"]
        is view["qualified"]
        is False
    )
    assert "capture" not in view
    for channel in ("stdout", "stderr"):
        raw = getattr(inputs["process_result"], channel)
        assert base64.b64decode(full[channel]["data"], validate=True) == raw
        assert full[channel]["sha256"] == hashlib.sha256(raw).hexdigest()
        assert full[channel]["bytes"] == len(raw)
    assert full["owned_payload"] == inputs["owned_payload"]
    caps = artifact.capabilities()
    assert caps.to_dict()["modes"] == [dict(MODE)]
    assert caps.to_dict()["controls"] == list(fixture_control_observations())
    assert caps.view()["unavailable_controls"] == []
    assert caps.to_dict()["probe_evidence_sha256"] == artifact.evidence_sha256
    verified = evidence.verify_rehearsal_camera_probe_evidence(
        artifact.payload, inputs["binding"]
    )
    assert verified.payload == artifact.payload
    assert verified.capabilities().payload == caps.payload


@pytest.mark.parametrize(
    "missing",
    ["activation_request", "process_result", "native_receipt", "owned_payload"],
)
def test_missing_observation_retained_as_incomplete_without_capabilities(missing):
    inputs = probe_inputs()
    inputs[missing] = None
    artifact = evidence.retain_rehearsal_camera_probe_evidence(**inputs)
    assert artifact.view()["status"] == "INCOMPLETE_PROBE_REHEARSAL"
    with pytest.raises(evidence.CameraProbeEvidenceError, match="exact bounded"):
        artifact.capabilities()


@pytest.mark.parametrize(
    "key",
    [
        "session_id",
        "attempt_id",
        "source_sha256",
        "permit_sha256",
        "operation_sha256",
        "selected_identity_sha256",
    ],
)
def test_every_expected_binding_is_required(key):
    inputs, artifact = retained_probe()
    changed = deepcopy(inputs["binding"])
    changed[key] = "other-session" if key.endswith("_id") else "9" * 64
    with pytest.raises(ValueError):
        evidence.verify_rehearsal_camera_probe_evidence(artifact.payload, changed)


@pytest.mark.parametrize(
    "changed",
    [
        "request_hash",
        "attempt",
        "native_endpoint",
        "native_cleanup",
        "camera_request_hash",
        "templates",
        "unknown_field",
        "mode_count",
        "controls",
    ],
)
def test_well_bounded_wrong_wire_is_retained_but_never_complete(changed):
    inputs = probe_inputs()
    process = inputs["process_result"]
    wire = deepcopy(process.parsed_result)
    native = wire["fixture_result"]["native_receipt"]
    if changed == "request_hash":
        wire["request_sha256"] = "a" * 64
    elif changed == "attempt":
        wire["attempt_id"] = "other-attempt"
    elif changed == "native_endpoint":
        native["selected_endpoint"] = "not-selected"
    elif changed == "native_cleanup":
        native["cleanup"]["source_released"] = False
    elif changed == "camera_request_hash":
        wire["fixture_result"]["camera_request_sha256"] = "a" * 64
    elif changed == "templates":
        wire["fixture_result"]["template_sha256s"] = ["a" * 64]
    elif changed == "unknown_field":
        native["unregistered"] = True
    elif changed == "mode_count":
        native["modes"] = []
    elif changed == "controls":
        native["controls"][0]["value"] = -5
    inputs["process_result"] = replace(
        process, stdout=_canonical(wire), parsed_result=wire
    )
    artifact = evidence.retain_rehearsal_camera_probe_evidence(**inputs)
    assert artifact.view()["status"] == "INCOMPLETE_PROBE_REHEARSAL"
    assert base64.b64decode(artifact.to_dict()["stdout"]["data"]) == _canonical(wire)


@pytest.mark.parametrize("data", [b"not-json", b'{"a":1,"a":2}', b"{", b"\xff"])
def test_malformed_exact_stdout_is_not_dropped(data):
    inputs = probe_inputs()
    inputs["process_result"] = replace(
        inputs["process_result"], stdout=data, parsed_result=None
    )
    artifact = evidence.retain_rehearsal_camera_probe_evidence(**inputs)
    assert base64.b64decode(artifact.to_dict()["stdout"]["data"]) == data
    assert artifact.view()["status"] == "INCOMPLETE_PROBE_REHEARSAL"


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "CANCELLED"),
        ("status", "TIMED_OUT"),
        ("tree_exit_confirmed", False),
        ("cleanup_errors", ("CLOSE_FAILED:stdout",)),
        ("primary_error", "WORKER_FAILED"),
        ("initial_thread_resumed", False),
    ],
)
def test_process_cleanup_and_native_cleanup_cannot_substitute(field, value):
    inputs = probe_inputs()
    inputs["process_result"] = replace(inputs["process_result"], **{field: value})
    view = evidence.retain_rehearsal_camera_probe_evidence(**inputs).view()
    assert view["status"] == "INCOMPLETE_PROBE_REHEARSAL"
    assert view["native"]["cleanup_confirmed"] is True
    assert "OWNED_PROCESS_NOT_CONFIRMED_SUCCESSFUL" in view["blockers"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("mode", dict(MODE)),
        ("controls", [{}]),
        ("operation", "capture"),
        ("output_directory", "C:/output"),
        ("arguments_sha256", "a" * 64),
    ],
)
def test_probe_request_cannot_hide_capture_or_different_arguments(field, value):
    inputs = probe_inputs()
    inputs["activation_request"] = replace(
        inputs["activation_request"], **{field: value}
    )
    with pytest.raises(ValueError):
        evidence.retain_rehearsal_camera_probe_evidence(**inputs)


@pytest.mark.parametrize(
    "field,value",
    [
        ("control_set_attempts", 1),
        ("frames_written", 1),
        ("samples_received", 1),
        ("source_opened", True),
    ],
)
def test_probe_typed_counts_reject_effects_and_boolean_coercion(field, value):
    inputs = probe_inputs()
    native = inputs["native_receipt"]
    inputs["native_receipt"] = replace(native, counts={**native.counts, field: value})
    with pytest.raises(ValueError):
        evidence.retain_rehearsal_camera_probe_evidence(**inputs)


def test_forged_payload_request_is_held_and_full_payload_stays_available():
    inputs = probe_inputs()
    inputs["owned_payload"]["camera_request"]["helper_sha256"] = "b" * 64
    artifact = evidence.retain_rehearsal_camera_probe_evidence(**inputs)
    assert artifact.view()["status"] == "INCOMPLETE_PROBE_REHEARSAL"
    assert artifact.to_dict()["owned_payload"] == inputs["owned_payload"]


@pytest.mark.parametrize("channel,maximum", [("stdout", 32768), ("stderr", 8192)])
def test_wire_caps_refuse_instead_of_truncate(channel, maximum):
    inputs = probe_inputs()
    inputs["process_result"] = replace(
        inputs["process_result"], **{channel: b"x" * (maximum + 1)}
    )
    with pytest.raises(ValueError):
        evidence.retain_rehearsal_camera_probe_evidence(**inputs)


def test_canonical_hash_tamper_and_extra_authority_refused():
    inputs, artifact = retained_probe()
    for change in (
        lambda d: d.update(physical_authority=True),
        lambda d: d.update(extra=True),
        lambda d: d["stdout"].update(bytes=0),
    ):
        raw = artifact.to_dict()
        change(raw)
        with pytest.raises(ValueError):
            evidence.verify_rehearsal_camera_probe_evidence(
                _canonical(raw), inputs["binding"]
            )
    with pytest.raises(ValueError):
        evidence.verify_rehearsal_camera_probe_evidence(
            artifact.payload + b"\n", inputs["binding"]
        )


def test_all_build_verify_view_capabilities_are_inert_and_detached(monkeypatch):
    inputs = probe_inputs()

    def forbidden(*args, **kwargs):
        pytest.fail("Pure evidence must not perform filesystem/provider work")

    for name in ("probe", "capture", "enumerate_metadata", "_campaign"):
        monkeypatch.setattr(WindowsCameraWorkerClient, name, forbidden)
    for name in ("open", "read_bytes", "stat", "mkdir", "resolve"):
        monkeypatch.setattr(Path, name, forbidden)
    artifact = evidence.retain_rehearsal_camera_probe_evidence(**inputs)
    artifact.view()["native"]["counts"]["source_opened"] = 0
    artifact.to_dict()["owned_payload"].clear()
    inputs["owned_payload"].clear()
    verified = evidence.verify_rehearsal_camera_probe_evidence(
        artifact.payload, inputs["binding"]
    )
    assert verified.view()["status"] == "COMPLETE_PROBE_REHEARSAL"
    assert len(verified.capabilities().view()["controls"]) == 6
