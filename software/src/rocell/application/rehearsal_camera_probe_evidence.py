"""Pure full retention of a bounded incapable capability-probe campaign.

No method dispatches a child, touches a file or activates a provider. The caller
owns audited M1 permit/registration/hash checks. Successful probing is neither
capture, applied configuration, received-device qualification nor calibration.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
import hashlib
import json
from typing import Any

from rocell.application.camera_configuration import (
    CameraCapabilities,
    CameraConfigurationError,
    _binding,
    _capabilities_from_verified_probe,
    _control,
    _mode,
)
from rocell.application.rehearsal_owned_camera_evidence import (
    MAX_STDERR_BYTES,
    MAX_STDOUT_BYTES,
    OwnedCameraEvidenceError,
    _blob,
    _canonical,
    _decode_blob,
    _exact,
    _int,
    _json_wire,
    _owned,
    _plain,
    _process,
    _same,
    _text,
)
from rocell.providers.windows.camera_worker_client import (
    CameraActivationRequest,
    CameraCampaignBudget,
    CameraCandidate,
    CameraEndpointBinding,
    CameraWorkerError,
    NativeCameraReceipt,
    WindowsCameraWorkerClient,
)
from rocell.providers.windows.owned_camera_codec import (
    CAMERA_FIXTURE_PATH,
    CONFIG_PAYLOAD_SCHEMA,
    FRAME_BYTES,
    PROVENANCE,
    validate_camera_result,
)
from rocell.providers.windows.owned_worker_process import OwnedWorkerResult

SCHEMA = "rocell.rehearsal_camera_probe_evidence.v1"
SUMMARY_SCHEMA = "rocell.rehearsal_camera_probe_summary.v1"
MAX_EVIDENCE_BYTES = 128 * 1024
_FIELDS = {
    "schema",
    "domain",
    "binding",
    "activation_request",
    "owned_payload",
    "process_result",
    "stdout",
    "stderr",
    "native_receipt",
    "error",
    "physical_authority",
    "qualified",
}
_COUNTS = {
    "source_activation_attempts",
    "source_opened",
    "control_set_attempts",
    "samples_received",
    "frames_written",
    "source_shutdown_attempts",
}
_MEANING = (
    "Retained incapable capability-probe rehearsal only. OS process cleanup and "
    "modeled native cleanup are separate. No frames, control writes, applied "
    "configuration, received-device qualification or calibration is established."
)


class CameraProbeEvidenceError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def _require(condition: bool, code: str = "INVALID_CAMERA_PROBE_EVIDENCE") -> None:
    if not condition:
        raise CameraProbeEvidenceError(
            code, "Camera probe evidence failed its exact bounded contract."
        )


def _request(value: object, binding: dict[str, Any]) -> CameraActivationRequest:
    raw = dict(_exact(value, {field.name for field in fields(CameraActivationRequest)}))
    raw["binding"] = CameraEndpointBinding(
        **_exact(
            raw["binding"], {field.name for field in fields(CameraEndpointBinding)}
        )
    )
    raw["budget"] = CameraCampaignBudget(
        **_exact(raw["budget"], {field.name for field in fields(CameraCampaignBudget)})
    )
    _require(
        raw["operation"] == "probe"
        and raw["mode"] is None
        and raw["controls"] == []
        and raw["output_directory"] is None,
        "PROBE_HAS_CAPTURE_INPUTS",
    )
    raw["controls"] = ()
    request = CameraActivationRequest(**raw)
    _require(
        request.campaign_id == binding["attempt_id"]
        and request.source_sha256 == binding["source_sha256"]
        and request.binding.binding_sha256 == binding["selected_identity_sha256"],
        "PROBE_BINDING_MISMATCH",
    )
    _require(
        request.budget.max_frames == 1
        and request.budget.max_frame_bytes == FRAME_BYTES
        and request.budget.max_total_bytes == FRAME_BYTES
        and request.budget.duration_ms <= 55000,
        "PROBE_BUDGET_MISMATCH",
    )
    # This existing builder is documented filesystem-inert. Rebuilding only the
    # argv/request checks exact fixed helper path and argument hash, without any
    # execute/capture/probe call or inferred working directory.
    prepared = WindowsCameraWorkerClient(
        CAMERA_FIXTURE_PATH, request.helper_sha256
    ).prepare_probe(
        request.binding,
        source_sha256=request.source_sha256,
        campaign_id=request.campaign_id,
        budget=request.budget,
    )
    _require(
        _same(_plain(request), _plain(prepared.request)), "PROBE_ARGUMENTS_MISMATCH"
    )
    return request


def _native_snapshot(value: object) -> NativeCameraReceipt:
    """Validate typed probe metadata independently of the saved raw-wire join."""
    raw = dict(_exact(value, {field.name for field in fields(NativeCameraReceipt)}))
    _require(raw["operation"] == "probe" and raw["status"] in {"OK", "FAILED"})
    _require((raw["status"] == "OK") == (raw["reason_code"] is None))
    if raw["reason_code"] is not None:
        _text(raw["reason_code"], 96)
    _text(raw["selected_endpoint"], 4096)
    _require(type(raw["cleanup_confirmed"]) is bool)
    _require(type(raw["candidates"]) is list and len(raw["candidates"]) <= 64)
    candidates = []
    for value in raw["candidates"]:
        item = _exact(value, {"symbolic_link", "friendly_name"})
        _text(item["symbolic_link"], 4096)
        _text(item["friendly_name"], 1024)
        candidates.append(CameraCandidate(**item))
    _require(len({c.symbolic_link for c in candidates}) == len(candidates))
    raw["candidates"] = tuple(candidates)
    _require(type(raw["modes"]) is list and len(raw["modes"]) <= 128)
    raw["modes"] = tuple(_mode(item) for item in raw["modes"])
    _require(
        raw["requested_mode"] is None and raw["frames"] == [],
        "PROBE_HAS_CAPTURE_OUTPUTS",
    )
    raw["observed_mode"] = (
        None if raw["observed_mode"] is None else _mode(raw["observed_mode"])
    )
    raw["frames"] = ()
    _require(type(raw["controls"]) is list and len(raw["controls"]) <= 6)
    raw["controls"] = tuple(_control(item) for item in raw["controls"])
    _require(len({item.control_id for item in raw["controls"]}) == len(raw["controls"]))
    counts = _exact(raw["counts"], _COUNTS)
    for key, count in counts.items():
        _int(
            count,
            0,
            (
                1
                if key
                in {
                    "source_activation_attempts",
                    "source_opened",
                    "source_shutdown_attempts",
                }
                else 0
            ),
        )
    _require(
        counts["source_opened"] <= counts["source_activation_attempts"]
        and counts["source_shutdown_attempts"] <= counts["source_activation_attempts"]
    )
    _require(type(raw["limitations"]) is list and len(raw["limitations"]) <= 24)
    for limitation in raw["limitations"]:
        _text(limitation, 128)
    raw["limitations"] = tuple(raw["limitations"])
    return NativeCameraReceipt(**raw)


def _wire_valid(
    document: dict[str, Any],
    request: CameraActivationRequest | None,
    process: dict[str, Any] | None,
    native: NativeCameraReceipt | None,
    stdout: bytes,
) -> bool:
    """Reuse both the closed owned codec and the unchanged pure native parser."""
    if request is None or process is None or native is None:
        return False
    wire = _json_wire(stdout)
    payload = document["owned_payload"]
    if (
        wire is None
        or type(payload) is not dict
        or payload.get("schema") != CONFIG_PAYLOAD_SCHEMA
    ):
        return False
    try:
        _require(_same(process["parsed_result"], wire))
        _require(_same(payload.get("camera_request"), _plain(request)))
        _require(
            payload.get("templates") == [] and payload.get("provenance") == PROVENANCE
        )
        prepared = WindowsCameraWorkerClient(
            CAMERA_FIXTURE_PATH, request.helper_sha256
        ).prepare_probe(
            request.binding,
            source_sha256=request.source_sha256,
            campaign_id=request.campaign_id,
            budget=request.budget,
        )
        _require(_same(payload.get("native_arguments"), list(prepared.arguments)))
        validate_camera_result(
            wire,
            payload=payload,
            request_sha256=process["request_sha256"],
            attempt_id=request.campaign_id,
            returncode=process["returncode"],
        )
        native_wire = wire["fixture_result"]["native_receipt"]
        # A frame is rejected before reaching the parser; no parser branch that
        # opens image paths can ever be reached during this pure probe verify.
        _require(native_wire.get("frames") == [])
        parsed = WindowsCameraWorkerClient._parse_receipt(
            native_wire,
            "probe",
            request.binding,
            None,
            (request.budget, None),
            (),
        )
        return _same(_plain(parsed), _plain(native))
    except (ValueError, RuntimeError, TypeError, KeyError, AttributeError):
        return False


def _derive(document: dict[str, Any]) -> dict[str, Any]:
    _exact(document, _FIELDS)
    _require(
        document["schema"] == SCHEMA
        and document["domain"] == "INCAPABLE_CAMERA_PROBE_REHEARSAL"
        and document["physical_authority"] is False
        and document["qualified"] is False
    )
    binding = _binding(document["binding"])
    request = (
        None
        if document["activation_request"] is None
        else _request(document["activation_request"], binding)
    )
    stdout = _decode_blob(document["stdout"], MAX_STDOUT_BYTES)
    stderr = _decode_blob(document["stderr"], MAX_STDERR_BYTES)
    process = (
        None
        if document["process_result"] is None
        else _process(document["process_result"], stdout, stderr, binding)
    )
    _require(process is not None or (not stdout and not stderr))
    _require(
        document["owned_payload"] is None or type(document["owned_payload"]) is dict
    )
    native = (
        None
        if document["native_receipt"] is None
        else _native_snapshot(document["native_receipt"])
    )
    error = document["error"]
    if error is not None:
        _require(
            type(error) is dict
            and {"code", "message"} <= set(error) <= {"code", "message", "error_type"}
        )
        _text(error["code"], 128)
        _text(error["message"], 2048)
        if "error_type" in error:
            _text(error["error_type"], 128)
    blockers = []
    if request is None:
        blockers.append("PROBE_REQUEST_UNAVAILABLE")
    if document["owned_payload"] is None:
        blockers.append("OWNED_PAYLOAD_UNAVAILABLE")
    if process is None:
        blockers.append("OWNED_PROCESS_RESULT_UNAVAILABLE")
    process_ok = bool(
        process is not None
        and process["status"] == "SUCCEEDED"
        and process["primary_error"] is None
        and not process["cleanup_errors"]
        and process["process_created"]
        and process["initial_thread_resumed"]
        and process["tree_exit_confirmed"]
        and process["returncode"] == 0
    )
    if process is not None and not process_ok:
        blockers.append("OWNED_PROCESS_NOT_CONFIRMED_SUCCESSFUL")
    native_valid = _wire_valid(document, request, process, native, stdout)
    if not native_valid:
        blockers.append("PROBE_WIRE_OR_REQUEST_BINDING_UNVERIFIED")
    native_ok = bool(
        native is not None
        and native.status == "OK"
        and native.cleanup_confirmed
        and native.counts["source_activation_attempts"]
        == native.counts["source_opened"]
        == native.counts["source_shutdown_attempts"]
        == 1
    )
    if not native_ok:
        blockers.append("SYNTHETIC_NATIVE_PROBE_NOT_CONFIRMED")
    if error is not None:
        blockers.append("CALLER_REPORTED_ERROR")
    return {
        "schema": SUMMARY_SCHEMA,
        "status": (
            "COMPLETE_PROBE_REHEARSAL" if not blockers else "INCOMPLETE_PROBE_REHEARSAL"
        ),
        "binding": binding,
        "process": (
            None
            if process is None
            else {
                "status": process["status"],
                "created": process["process_created"],
                "resumed": process["initial_thread_resumed"],
                "tree_exit_confirmed": process["tree_exit_confirmed"],
                "cleanup_errors": process["cleanup_errors"][:16],
                "cleanup_error_count": len(process["cleanup_errors"]),
                "cleanup_errors_omitted": max(0, len(process["cleanup_errors"]) - 16),
                "primary_error": process["primary_error"],
                "returncode": process["returncode"],
                "stdout_bytes": len(stdout),
                "stderr_bytes": len(stderr),
                "request_sha256": process["request_sha256"],
            }
        ),
        "native": (
            None
            if native is None
            else {
                "receipt_valid": native_valid,
                "status": native.status,
                "cleanup_confirmed": native.cleanup_confirmed,
                "counts": dict(native.counts),
                "mode_count": len(native.modes),
                "control_count": len(native.controls),
            }
        ),
        "blockers": blockers,
        "device_cleanup_proven": False,
        "physical_authority": False,
        "qualified": False,
        "meaning": _MEANING,
    }


@dataclass(frozen=True, slots=True)
class RehearsalCameraProbeEvidence:
    payload: bytes

    def __post_init__(self) -> None:
        _require(
            type(self.payload) is bytes and 0 < len(self.payload) <= MAX_EVIDENCE_BYTES,
            "PROBE_EVIDENCE_LIMIT",
        )

    @property
    def evidence_sha256(self) -> str:
        return hashlib.sha256(self.payload).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self.payload)

    def view(self) -> dict[str, Any]:
        return {**_derive(self.to_dict()), "evidence_sha256": self.evidence_sha256}

    def capabilities(self) -> CameraCapabilities:
        _require(
            self.view()["status"] == "COMPLETE_PROBE_REHEARSAL", "PROBE_INCOMPLETE"
        )
        document = self.to_dict()
        return _capabilities_from_verified_probe(
            binding=document["binding"],
            probe_evidence_sha256=self.evidence_sha256,
            request=_request(document["activation_request"], document["binding"]),
            receipt=_native_snapshot(document["native_receipt"]),
        )


def retain_rehearsal_camera_probe_evidence(
    *,
    binding: dict[str, Any],
    activation_request: CameraActivationRequest | None,
    process_result: OwnedWorkerResult | None,
    native_receipt: NativeCameraReceipt | None,
    error: dict[str, Any] | None = None,
    owned_payload: dict[str, Any] | None = None,
) -> RehearsalCameraProbeEvidence:
    for value, kind in (
        (activation_request, CameraActivationRequest),
        (process_result, OwnedWorkerResult),
        (native_receipt, NativeCameraReceipt),
    ):
        _require(value is None or type(value) is kind)
    try:
        document = _owned(
            {
                "schema": SCHEMA,
                "domain": "INCAPABLE_CAMERA_PROBE_REHEARSAL",
                "binding": _binding(binding),
                "activation_request": (
                    None if activation_request is None else _plain(activation_request)
                ),
                "owned_payload": owned_payload,
                "process_result": (
                    None if process_result is None else _plain(process_result.to_dict())
                ),
                "stdout": _blob(
                    b"" if process_result is None else process_result.stdout,
                    MAX_STDOUT_BYTES,
                ),
                "stderr": _blob(
                    b"" if process_result is None else process_result.stderr,
                    MAX_STDERR_BYTES,
                ),
                "native_receipt": (
                    None if native_receipt is None else _plain(native_receipt)
                ),
                "error": error,
                "physical_authority": False,
                "qualified": False,
            }
        )
        _derive(document)
        return RehearsalCameraProbeEvidence(_canonical(document))
    except (
        OwnedCameraEvidenceError,
        CameraConfigurationError,
        CameraWorkerError,
        TypeError,
        UnicodeError,
    ) as error:
        raise CameraProbeEvidenceError(
            getattr(error, "code", "INVALID_CAMERA_PROBE_EVIDENCE"), str(error)
        ) from error


def verify_rehearsal_camera_probe_evidence(
    payload: bytes, expected_binding: dict[str, Any]
) -> RehearsalCameraProbeEvidence:
    _require(
        type(payload) is bytes and 0 < len(payload) <= MAX_EVIDENCE_BYTES,
        "PROBE_EVIDENCE_LIMIT",
    )
    try:
        document = _json_wire(payload)
        _require(
            document is not None and _canonical(document) == payload,
            "PROBE_NONCANONICAL_BYTES",
        )
        assert document is not None
        _require(
            _same(document.get("binding"), _binding(expected_binding)),
            "PROBE_BINDING_MISMATCH",
        )
        _derive(document)
    except (
        OwnedCameraEvidenceError,
        CameraConfigurationError,
        CameraWorkerError,
        TypeError,
        UnicodeError,
    ) as error:
        raise CameraProbeEvidenceError(
            getattr(error, "code", "INVALID_CAMERA_PROBE_EVIDENCE"), str(error)
        ) from error
    return RehearsalCameraProbeEvidence(payload)
