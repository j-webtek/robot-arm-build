"""Pure metadata fixtures only: never spawn a child, inspect OS state or read pixels."""

from copy import deepcopy
from dataclasses import replace, FrozenInstanceError
import base64
import hashlib
import json
from pathlib import Path
from types import MappingProxyType

import pytest

import rocell.application.rehearsal_owned_camera_evidence as evidence
import rocell.application.windows_camera_capture_ingest as ingest
from rocell.application.camera_capture_dataset import (
    PLAN_SCHEMA,
    _DECLARATIONS,
    DatasetReceipt,
    DatasetVerification,
    DatasetQuotas,
    FramePlan,
)
from rocell.application.rehearsal_owned_camera_evidence import (
    OwnedCameraEvidenceError,
    retain_owned_camera_evidence,
    verify_owned_camera_evidence,
)
from rocell.application.windows_camera_capture_ingest import (
    NativeCaptureIngestReceipt,
    prepare_windows_camera_ingest,
)
from rocell.providers.windows.camera_worker_client import (
    CameraActivationRequest,
    CameraCampaignBudget,
    CameraCandidate,
    CameraEndpointBinding,
    NativeCameraMode,
    NativeCameraReceipt,
    NativeFrameArtifact,
)
from rocell.providers.windows.owned_worker_process import (
    OwnedWorkerResult,
    OwnedWindowsWorker,
)
from rocell.providers.windows.owned_camera_codec import FRAME_BYTES, MODE, PROVENANCE


def canonical(value, *, newline=False):
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("ascii") + (b"\n" if newline else b"")


def digest(value, *, newline=False):
    return hashlib.sha256(canonical(value, newline=newline)).hexdigest()


def complete_inputs(count=1):
    """Build typed full-resolution metadata; this helper makes no pixel/file claim.

    Parent integration tests separately provide real incapable-process files and
    ingestion receipts. Here content_verified is an explicit input observation,
    and the pure module must label its own conclusion only a metadata join.
    """
    binding = {
        "session_id": "rehearsal-session",
        "attempt_id": "attempt-camera",
        "source_sha256": "a" * 64,
        "permit_sha256": "b" * 64,
        "operation_sha256": "c" * 64,
        "selected_identity_sha256": "d" * 64,
        "settings_epoch": "e" * 64,
    }
    root = Path("C:/incapable-owned-camera-evidence-fixture")
    endpoint = "incapable://owned-camera-fixture"
    mode = NativeCameraMode(**MODE)
    request = CameraActivationRequest(
        binding["attempt_id"],
        binding["source_sha256"],
        "capture",
        CameraEndpointBinding(
            endpoint,
            hashlib.sha256(endpoint.encode()).hexdigest(),
            binding["selected_identity_sha256"],
        ),
        mode,
        (),
        CameraCampaignBudget(10000, count, FRAME_BYTES, FRAME_BYTES * count),
        "1" * 64,
        "2" * 64,
        str(root / "native-input"),
    )
    frames = tuple(
        NativeFrameArtifact(
            f"frame-{i:06d}.yuy2",
            FRAME_BYTES,
            10944,
            0,
            i,
            i * 10000,
            1000 + i * 100,
            10000000,
            False,
            str(i + 3) * 64,
        )
        for i in range(count)
    )
    native = NativeCameraReceipt(
        "capture",
        "OK",
        None,
        endpoint,
        (CameraCandidate(endpoint, "Incapable fixture"),),
        (mode,),
        mode,
        mode,
        (),
        frames,
        MappingProxyType(
            {
                "source_activation_attempts": 1,
                "source_opened": 1,
                "control_set_attempts": 0,
                "samples_received": count,
                "frames_written": count,
                "source_shutdown_attempts": 1,
            }
        ),
        True,
        (PROVENANCE,),
    )
    plan = prepare_windows_camera_ingest(
        request,
        capture_directory=root / "native-input",
        dataset_root=root / "datasets",
        source_sha256=binding["source_sha256"],
        settings_epoch=binding["settings_epoch"],
        domain="INCAPABLE_NATIVE_FIXTURE",
        frames=tuple(FramePlan(f"frame-{i:06d}") for i in range(count)),
        quotas=DatasetQuotas(disk_reserve_bytes=0),
    )
    capture_plan, _ = ingest._validate_receipt(request, native, plan)
    capture_root = plan.dataset_root / ("ingest-" + "1" * 32)
    dataset_path = capture_root / ("capture-" + "2" * 32)
    plan_digest = digest(
        {
            "schema": PLAN_SCHEMA,
            "plan": evidence._plain(capture_plan),
            "declarations": _DECLARATIONS,
        },
        newline=True,
    )
    dataset = DatasetReceipt(
        dataset_path, "f" * 64, plan_digest, count, FRAME_BYTES * count
    )
    verification = DatasetVerification(
        dataset_path,
        dataset.manifest_sha256,
        capture_plan,
        count,
        dataset.logical_bytes,
        True,
        True,
    )
    source = {
        "schema": ingest.CONTRACT_SCHEMA,
        "plan": evidence._plain(plan),
        "activation_request": evidence._plain(request),
        "native_receipt": evidence._plain(native),
        "native_receipt_sha256": digest(evidence._plain(native), newline=True),
        "capture_plan": evidence._plain(capture_plan),
        "timing_conversion": "QPC_POINT_FLOOR_CEIL_NS_NOT_CAPTURE_INTERVAL_OR_WALL_TIME",
        "media_conversion": "EXACT_100NS_TO_NS_NOT_SENSOR_EXPOSURE",
        "color_policy": ingest.COLOR_POLICY,
        "resample_policy": ingest.RESAMPLE_POLICY,
        "physical_authority": False,
        "m1_qualified": False,
    }
    source_digest = digest(source, newline=True)
    provisional = NativeCaptureIngestReceipt(
        dataset,
        verification,
        None,
        capture_root / "ingest-receipt.json",
        "0" * 64,
        source_digest,
        "INCAPABLE_NATIVE_FIXTURE",
    )
    envelope = {
        key: value
        for key, value in provisional.to_dict().items()
        if key not in {"envelope_path", "envelope_sha256"}
    }
    envelope.update(
        activation_request_sha256=ingest.activation_request_sha256(request),
        native_receipt_sha256=source["native_receipt_sha256"],
    )
    capture = replace(provisional, envelope_sha256=digest(envelope, newline=True))
    native_raw = evidence._plain(native)
    wire_native = {
        key: value
        for key, value in native_raw.items()
        if key not in {"candidates", "frames", "cleanup_confirmed"}
    }
    wire_native.update(
        schema="rocell.windows_camera.v1",
        devices=native_raw["candidates"],
        frames=[
            {key: value for key, value in f.items() if key != "sha256"}
            for f in native_raw["frames"]
        ],
        cleanup={
            "source_shutdown_hr": 0,
            "source_released": True,
            "mf_shutdown_hr": 0,
            "com_uninitialized": True,
        },
    )
    wire = {
        "schema": "rocell.owned_camera_fixture_result.v1",
        "request_sha256": "9" * 64,
        "attempt_id": binding["attempt_id"],
        "physical_authority": False,
        "fixture_result": {
            "scenario": "nominal",
            "provenance": PROVENANCE,
            "camera_request_sha256": digest(evidence._plain(request)),
            "template_sha256s": ["8" * 64] * count,
            "native_receipt": wire_native,
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
        canonical(wire) + b"\n",
        b"fixture stderr\n",
        wire,
    )
    return dict(
        binding=binding,
        activation_request=request,
        process_result=process,
        native_receipt=native,
        capture=capture,
        error=None,
        capture_envelope=envelope,
        source_contract=source,
    )


def retained(count=1):
    inputs = complete_inputs(count)
    return inputs, retain_owned_camera_evidence(**inputs)


def test_complete_rehearsal_retains_lossless_raw_process_and_full_metadata():
    inputs, result = retained()
    doc, view = result.to_dict(), result.view()
    assert view["status"] == "RETAINED_COMPLETE_REHEARSAL"
    assert view["blockers"] == []
    assert (
        view["device_cleanup_proven"]
        is view["qualified"]
        is view["physical_authority"]
        is False
    )
    assert view["process"]["created"] is True
    assert view["process"]["tree_exit_confirmed"] is True
    assert view["native"]["cleanup_confirmed"] is True
    assert view["native"]["receipt_valid"] is True
    assert view["capture"]["metadata_binding_valid"] is True
    assert doc["capture"] == inputs["capture"].to_dict()
    assert doc["capture_envelope"] == inputs["capture_envelope"]
    assert doc["source_contract"] == inputs["source_contract"]
    for key in ("stdout", "stderr"):
        raw = getattr(inputs["process_result"], key)
        assert base64.b64decode(doc[key]["data"], validate=True) == raw
        assert doc[key]["sha256"] == hashlib.sha256(raw).hexdigest()
        assert doc[key]["bytes"] == len(raw)
    assert (
        verify_owned_camera_evidence(result.payload, inputs["binding"]).payload
        == result.payload
    )
    assert result.evidence_sha256 == hashlib.sha256(result.payload).hexdigest()


@pytest.mark.parametrize("count", [1, 2, 3, 4])
def test_fixed_full_resolution_contract_fits_without_truncation(count):
    _, result = retained(count)
    assert len(result.payload) < 128 * 1024
    assert result.view()["capture"]["frames"] == count
    assert result.view()["capture"]["logical_bytes"] == FRAME_BYTES * count
    assert len(result.to_dict()["native_receipt"]["frames"]) == count
    assert result.view()["status"] == "RETAINED_COMPLETE_REHEARSAL"


def test_missing_all_results_is_a_retained_hold_not_success():
    binding = complete_inputs()["binding"]
    result = retain_owned_camera_evidence(
        binding=binding,
        activation_request=None,
        process_result=None,
        native_receipt=None,
        capture=None,
        error={"code": "PREPARATION_FAILED", "message": "No process dispatched."},
    )
    view = result.view()
    assert view["status"] == "RETAINED_INCOMPLETE_REHEARSAL"
    assert view["process"] is view["native"] is view["capture"] is None
    assert view["device_cleanup_proven"] is False
    assert verify_owned_camera_evidence(result.payload, binding).view() == view


@pytest.mark.parametrize(
    "raw",
    [
        b"not-json",
        b"\xff\x00",
        b'{"duplicate":1,"duplicate":2}',
        b'{"value":NaN}',
        b"{}\n{}",
    ],
)
def test_malformed_stdout_is_retained_exactly_without_native_acceptance(raw):
    inputs = complete_inputs()
    inputs.update(
        process_result=replace(
            inputs["process_result"],
            status="FAILED",
            primary_error="MALFORMED_RESULT",
            stdout=raw,
            parsed_result=None,
        ),
        native_receipt=None,
        capture=None,
        capture_envelope=None,
        source_contract=None,
    )
    result = retain_owned_camera_evidence(**inputs)
    assert base64.b64decode(result.to_dict()["stdout"]["data"]) == raw
    assert result.view()["status"] == "RETAINED_INCOMPLETE_REHEARSAL"
    assert (
        verify_owned_camera_evidence(result.payload, inputs["binding"]).payload
        == result.payload
    )


def test_process_failure_and_cleanup_are_independent_from_synthetic_native_cleanup():
    inputs = complete_inputs()
    errors = tuple(f"CLOSE_FAILED:handle-{i}" for i in range(20))
    inputs["process_result"] = replace(
        inputs["process_result"],
        status="FAILED",
        primary_error="TIMING_FAILURE",
        cleanup_errors=errors,
        tree_exit_confirmed=False,
    )
    result = retain_owned_camera_evidence(**inputs)
    view = result.view()
    assert view["status"] == "RETAINED_INCOMPLETE_REHEARSAL"
    assert view["native"]["cleanup_confirmed"] is True
    assert view["process"]["tree_exit_confirmed"] is False
    assert view["process"]["cleanup_errors"] == list(errors[:16])
    assert view["process"]["cleanup_error_count"] == 20
    assert view["process"]["cleanup_errors_omitted"] == 4
    assert result.to_dict()["process_result"]["cleanup_errors"] == list(errors)


@pytest.mark.parametrize(
    "status,error", [("CANCELLED", "CANCELLED"), ("TIMED_OUT", "TIMED_OUT")]
)
def test_cancelled_or_timed_out_process_never_becomes_complete(status, error):
    inputs = complete_inputs()
    inputs["process_result"] = replace(
        inputs["process_result"], status=status, primary_error=error
    )
    assert (
        retain_owned_camera_evidence(**inputs).view()["status"]
        == "RETAINED_INCOMPLETE_REHEARSAL"
    )


@pytest.mark.parametrize("part", ["capture_envelope", "source_contract"])
def test_missing_ingest_provenance_holds_capture_without_discarding_receipt(part):
    inputs = complete_inputs()
    inputs[part] = None
    result = retain_owned_camera_evidence(**inputs)
    assert result.to_dict()["capture"] == inputs["capture"].to_dict()
    assert result.view()["capture"]["metadata_binding_valid"] is False
    assert result.view()["status"] == "RETAINED_INCOMPLETE_REHEARSAL"


@pytest.mark.parametrize(
    "field",
    [
        "source_sha256",
        "permit_sha256",
        "operation_sha256",
        "selected_identity_sha256",
        "settings_epoch",
        "session_id",
        "attempt_id",
    ],
)
def test_verifier_requires_exact_expected_binding(field):
    inputs, result = retained()
    changed = dict(inputs["binding"])
    changed[field] = "wrong-id" if field in {"session_id", "attempt_id"} else "0" * 64
    with pytest.raises(OwnedCameraEvidenceError, match="contract"):
        verify_owned_camera_evidence(result.payload, changed)


@pytest.mark.parametrize(
    "part,key",
    [
        ("source_contract", "activation_request"),
        ("source_contract", "native_receipt"),
        ("capture_envelope", "activation_request_sha256"),
        ("capture_envelope", "native_receipt_sha256"),
    ],
)
def test_changed_ingest_request_or_native_references_are_not_complete(part, key):
    inputs = complete_inputs()
    inputs[part][key] = {} if part == "source_contract" else "0" * 64
    result = retain_owned_camera_evidence(**inputs)
    assert result.view()["capture"]["metadata_binding_valid"] is False
    assert result.view()["status"] == "RETAINED_INCOMPLETE_REHEARSAL"


@pytest.mark.parametrize(
    "change",
    [
        lambda x: x.update(physical_authority=True),
        lambda x: x.update(unexpected=False),
        lambda x: x["stdout"].update(bytes=True),
        lambda x: x["stdout"].update(sha256="0" * 64),
        lambda x: x["stdout"].update(data="%%%"),
        lambda x: x["process_result"].update(stdout_bytes=0),
        lambda x: x["process_result"].update(process_created=1),
        lambda x: x["process_result"].update(physical_provider_qualified=True),
        lambda x: x["process_result"].update(device_cleanup_confirmed=True),
        lambda x: x["process_result"].update(retries=True),
    ],
)
def test_canonical_tampering_does_not_survive_structural_verification(change):
    inputs, result = retained()
    doc = result.to_dict()
    change(doc)
    with pytest.raises(OwnedCameraEvidenceError):
        verify_owned_camera_evidence(canonical(doc), inputs["binding"])


@pytest.mark.parametrize(
    "key,value", [("source_sha256", "0" * 64), ("campaign_id", "other-attempt")]
)
def test_request_source_and_attempt_cannot_cross_binding(key, value):
    inputs = complete_inputs()
    inputs["activation_request"] = replace(inputs["activation_request"], **{key: value})
    with pytest.raises(OwnedCameraEvidenceError):
        retain_owned_camera_evidence(**inputs)


def test_selected_endpoint_binding_is_not_just_an_unrelated_endpoint_hash():
    inputs = complete_inputs()
    request = inputs["activation_request"]
    inputs["activation_request"] = replace(
        request, binding=replace(request.binding, binding_sha256="0" * 64)
    )
    with pytest.raises(OwnedCameraEvidenceError):
        retain_owned_camera_evidence(**inputs)


@pytest.mark.parametrize("key,maximum", [("stdout", 32768), ("stderr", 8192)])
def test_raw_wire_caps_reject_without_truncation(key, maximum):
    inputs = complete_inputs()
    inputs["process_result"] = replace(
        inputs["process_result"], **{key: b"x" * (maximum + 1)}
    )
    with pytest.raises(OwnedCameraEvidenceError) as error:
        retain_owned_camera_evidence(**inputs)
    assert error.value.code == "WIRE_LIMIT"


def test_exact_maximum_wire_lengths_remain_losslessly_retained_on_failure():
    inputs = complete_inputs()
    inputs.update(
        process_result=replace(
            inputs["process_result"],
            status="FAILED",
            primary_error="OUTPUT_INVALID",
            stdout=b"x" * 32768,
            stderr=b"y" * 8192,
            parsed_result=None,
        ),
        native_receipt=None,
        capture=None,
        capture_envelope=None,
        source_contract=None,
    )
    result = retain_owned_camera_evidence(**inputs)
    assert len(base64.b64decode(result.to_dict()["stdout"]["data"])) == 32768
    assert len(base64.b64decode(result.to_dict()["stderr"]["data"])) == 8192
    assert result.view()["status"] == "RETAINED_INCOMPLETE_REHEARSAL"


def test_total_evidence_limit_rejects_instead_of_truncating_complete_records():
    inputs = complete_inputs()
    inputs["process_result"] = replace(
        inputs["process_result"],
        status="FAILED",
        primary_error="OUTPUT_INVALID",
        cleanup_errors=("x" * 128,) * 512,
        stdout=b"x" * 32768,
        stderr=b"y" * 8192,
        parsed_result=None,
    )
    with pytest.raises(OwnedCameraEvidenceError) as error:
        retain_owned_camera_evidence(**inputs)
    assert error.value.code == "EVIDENCE_LIMIT"


def test_boolean_wire_count_cannot_equal_integer_native_count():
    inputs = complete_inputs()
    wire = deepcopy(inputs["process_result"].parsed_result)
    wire["fixture_result"]["native_receipt"]["counts"]["source_opened"] = True
    inputs["process_result"] = replace(
        inputs["process_result"], stdout=canonical(wire), parsed_result=wire
    )
    view = retain_owned_camera_evidence(**inputs).view()
    assert view["native"]["receipt_valid"] is False
    assert view["status"] == "RETAINED_INCOMPLETE_REHEARSAL"


def test_boolean_source_contract_field_cannot_equal_typed_integer_even_rehashed():
    inputs = complete_inputs()
    inputs["source_contract"]["native_receipt"]["counts"]["source_opened"] = True
    source_hash = digest(inputs["source_contract"], newline=True)
    inputs["capture_envelope"]["source_contract_sha256"] = source_hash
    inputs["capture"] = replace(
        inputs["capture"],
        source_contract_sha256=source_hash,
        envelope_sha256=digest(inputs["capture_envelope"], newline=True),
    )
    assert (
        retain_owned_camera_evidence(**inputs).view()["capture"][
            "metadata_binding_valid"
        ]
        is False
    )


@pytest.mark.parametrize("field", ["physical_authority", "m1_qualified"])
def test_typed_capture_authority_cannot_be_erased_by_to_dict_projection(field):
    inputs = complete_inputs()
    inputs["capture"] = replace(inputs["capture"], **{field: True})
    with pytest.raises(OwnedCameraEvidenceError):
        retain_owned_camera_evidence(**inputs)


def test_failed_native_cleanup_retains_exact_native_wire_and_distinct_process_cleanup():
    inputs = complete_inputs()
    native = replace(
        inputs["native_receipt"],
        status="FAILED",
        reason_code="CLEANUP_UNCERTAIN",
        cleanup_confirmed=False,
    )
    wire = deepcopy(inputs["process_result"].parsed_result)
    wire["fixture_result"]["scenario"] = "cleanup-uncertain"
    wire_native = wire["fixture_result"]["native_receipt"]
    wire_native.update(status="FAILED", reason_code="CLEANUP_UNCERTAIN")
    wire_native["cleanup"]["source_shutdown_hr"] = -1
    inputs.update(
        native_receipt=native,
        capture=None,
        capture_envelope=None,
        source_contract=None,
        process_result=replace(
            inputs["process_result"],
            status="FAILED",
            primary_error="WORKER_EXIT_FAILED",
            returncode=1,
            stdout=canonical(wire),
            parsed_result=wire,
        ),
    )
    result = retain_owned_camera_evidence(**inputs)
    view = result.view()
    assert view["native"]["receipt_valid"] is True
    assert view["native"]["cleanup_confirmed"] is False
    assert view["process"]["tree_exit_confirmed"] is True
    assert view["process"]["cleanup_errors"] == []
    assert view["device_cleanup_proven"] is False
    assert (
        verify_owned_camera_evidence(result.payload, inputs["binding"]).view() == view
    )


@pytest.mark.parametrize(
    "change",
    [
        lambda raw: raw.update(request_sha256="0" * 64),
        lambda raw: raw.update(attempt_id="other-attempt"),
        lambda raw: raw["fixture_result"].update(camera_request_sha256="0" * 64),
        lambda raw: raw["fixture_result"].update(scenario="unknown"),
        lambda raw: raw["fixture_result"].update(provenance="PHYSICAL"),
        lambda raw: raw["fixture_result"].update(template_sha256s=[]),
        lambda raw: raw["fixture_result"]["native_receipt"].update(
            selected_endpoint="other"
        ),
    ],
)
def test_well_formed_but_wrong_outer_or_native_wire_is_retained_held(change):
    inputs = complete_inputs()
    raw = deepcopy(inputs["process_result"].parsed_result)
    change(raw)
    inputs["process_result"] = replace(
        inputs["process_result"], stdout=canonical(raw), parsed_result=raw
    )
    result = retain_owned_camera_evidence(**inputs)
    assert result.view()["native"]["receipt_valid"] is False
    assert result.view()["status"] == "RETAINED_INCOMPLETE_REHEARSAL"
    assert base64.b64decode(result.to_dict()["stdout"]["data"]) == canonical(raw)


def test_immutable_artifact_and_defensive_report_views():
    inputs, result = retained()
    original = result.payload
    inputs["binding"]["source_sha256"] = "0" * 64
    inputs["process_result"].parsed_result.clear()
    inputs["source_contract"].clear()
    result.to_dict()["process_result"].clear()
    result.view()["native"]["counts"].clear()
    assert result.payload == original
    assert result.view()["status"] == "RETAINED_COMPLETE_REHEARSAL"
    with pytest.raises(FrozenInstanceError):
        result.payload = b"{}"


def test_pure_retention_and_verification_never_read_paths_or_start_workers(monkeypatch):
    inputs = complete_inputs()

    def forbidden(*args, **kwargs):
        raise AssertionError("No filesystem/process/device work in pure evidence")

    with monkeypatch.context() as patch:
        patch.setattr(Path, "open", forbidden)
        patch.setattr(Path, "read_bytes", forbidden)
        patch.setattr(Path, "stat", forbidden)
        patch.setattr(OwnedWindowsWorker, "run", forbidden)
        patch.setattr(ingest, "verify_windows_capture_ingest", forbidden)
        patch.setattr(ingest, "ingest_windows_capture", forbidden)
        result = retain_owned_camera_evidence(**inputs)
        assert (
            verify_owned_camera_evidence(result.payload, inputs["binding"]).view()[
                "status"
            ]
            == "RETAINED_COMPLETE_REHEARSAL"
        )


@pytest.mark.parametrize(
    "native_change",
    [
        lambda n: replace(n, counts={**n.counts, "source_opened": True}),
        lambda n: replace(n, cleanup_confirmed=1),
        lambda n: replace(n, frames=(replace(n.frames[0], filename="../other.yuy2"),)),
        lambda n: replace(n, frames=(replace(n.frames[0], host_sequence=1),)),
        lambda n: replace(n, frames=(replace(n.frames[0], stride_bytes=0),)),
        lambda n: replace(n, frames=(replace(n.frames[0], sha256="unknown"),)),
        lambda n: replace(n, observed_mode=None),
    ],
)
def test_typed_native_dataclass_is_not_itself_proof_of_valid_observations(
    native_change,
):
    inputs = complete_inputs()
    inputs["native_receipt"] = native_change(inputs["native_receipt"])
    with pytest.raises(OwnedCameraEvidenceError):
        retain_owned_camera_evidence(**inputs)
