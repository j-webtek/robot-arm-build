"""Pure retention of an incapable camera process and its diagnostic artifacts.

No method launches a process, reads files or verifies pixel content. The caller
must separately audit the exact coordinator permit and reverify the retained
dataset's bytes. Process-tree cleanup is never physical device cleanup.
"""

from __future__ import annotations

import base64
from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from rocell.application.camera_capture_dataset import (
    PLAN_SCHEMA,
    DatasetQuotas,
    FramePlan,
    PreviewTransform,
    _DECLARATIONS,
)
from rocell.application.windows_camera_capture_ingest import (
    COLOR_POLICY,
    CONTRACT_SCHEMA,
    RESAMPLE_POLICY,
    NativeCaptureIngestPlan,
    NativeCaptureIngestReceipt,
    _validate_receipt,
    activation_request_sha256,
)
from rocell.providers.windows.camera_worker_client import (
    CameraActivationRequest,
    CameraCampaignBudget,
    CameraCandidate,
    CameraControlSetting,
    CameraEndpointBinding,
    NativeCameraMode,
    NativeCameraReceipt,
    NativeControlObservation,
    NativeFrameArtifact,
)
from rocell.providers.windows.owned_worker_process import OwnedWorkerResult
from rocell.providers.windows.owned_camera_codec import (
    FRAME_BYTES,
    MODE,
    PROVENANCE,
    SCENARIOS,
    validate_control_observations,
)

SCHEMA = "rocell.rehearsal_owned_camera_evidence.v1"
SUMMARY_SCHEMA = "rocell.rehearsal_owned_camera_summary.v1"
MAX_EVIDENCE_BYTES = 128 * 1024
MAX_STDOUT_BYTES = 32 * 1024
MAX_STDERR_BYTES = 8 * 1024
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\Z")
_BINDING_FIELDS = {
    "session_id",
    "attempt_id",
    "source_sha256",
    "permit_sha256",
    "operation_sha256",
    "selected_identity_sha256",
    "settings_epoch",
}
_COUNTS = {
    "source_activation_attempts",
    "source_opened",
    "control_set_attempts",
    "samples_received",
    "frames_written",
    "source_shutdown_attempts",
}
_EVIDENCE_FIELDS = {
    "schema",
    "domain",
    "binding",
    "activation_request",
    "process_result",
    "stdout",
    "stderr",
    "native_receipt",
    "capture",
    "capture_envelope",
    "source_contract",
    "error",
    "physical_authority",
    "qualified",
}
_MEANING = (
    "Retained incapable camera-process rehearsal evidence only. OS process cleanup "
    "and synthetic native cleanup are separate. Capture metadata matches do not "
    "reverify file content. No physical device cleanup, camera qualification, "
    "power-state observation or physical authority is established."
)


class OwnedCameraEvidenceError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def _require(condition: bool, code: str = "INVALID_EVIDENCE") -> None:
    if not condition:
        raise OwnedCameraEvidenceError(
            code, "Owned camera evidence failed its bounded exact contract."
        )


def _sha(value: object) -> None:
    _require(type(value) is str and _SHA.fullmatch(value) is not None)


def _text(value: object, maximum: int = 4096) -> None:
    _require(type(value) is str and bool(value) and len(value) <= maximum)
    assert isinstance(value, str)
    _require(
        len(value.encode("utf-8")) <= maximum
        and not any(ord(character) < 32 or ord(character) == 127 for character in value)
    )


def _int(value: object, minimum: int = 0, maximum: int = 2**63 - 1) -> None:
    _require(type(value) is int and minimum <= value <= maximum)


def _exact(value: object, names: set[str]) -> dict[str, Any]:
    _require(type(value) is dict and set(value) == names)
    assert isinstance(value, dict)
    return value


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def _hash(value: object, *, ingest: bool = False) -> str:
    return hashlib.sha256(_canonical(value) + (b"\n" if ingest else b"")).hexdigest()


def _same(left: object, right: object) -> bool:
    """JSON equality must distinguish bool from int, unlike Python equality."""
    return _canonical(left) == _canonical(right)


def _owned(value: object) -> Any:
    """Copy bounded JSON, including bounded base64, without arbitrary hooks."""
    nodes = 0
    chars = 0

    def copy(item: object, depth: int) -> Any:
        nonlocal nodes, chars
        nodes += 1
        _require(nodes <= 16384 and depth <= 24, "EVIDENCE_LIMIT")
        if item is None or type(item) is bool:
            return item
        if type(item) is int:
            _int(item, -(2**63), 2**64 - 1)
            return item
        if type(item) is str:
            chars += len(item)
            _require(
                len(item) <= 65536 and chars <= MAX_EVIDENCE_BYTES, "EVIDENCE_LIMIT"
            )
            item.encode("utf-8")
            return item
        if type(item) is list:
            _require(len(item) <= 512, "EVIDENCE_LIMIT")
            return [copy(child, depth + 1) for child in item]
        if type(item) is dict:
            _require(
                len(item) <= 64 and all(type(k) is str and len(k) <= 128 for k in item)
            )
            return {copy(k, depth + 1): copy(v, depth + 1) for k, v in item.items()}
        raise OwnedCameraEvidenceError(
            "INVALID_EVIDENCE", "Evidence requires bounded plain JSON."
        )

    try:
        result = copy(value, 0)
        _require(len(_canonical(result)) <= MAX_EVIDENCE_BYTES, "EVIDENCE_LIMIT")
        return result
    except (UnicodeError, RuntimeError) as error:
        raise OwnedCameraEvidenceError(
            "INVALID_EVIDENCE", "Evidence is not stable bounded JSON."
        ) from error


def _plain(value: Any) -> Any:
    # Deliberately avoids dataclasses.asdict: native counts may be MappingProxyType.
    if is_dataclass(value):
        return {
            field.name: _plain(getattr(value, field.name)) for field in fields(value)
        }
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if type(value) in {tuple, list}:
        return [_plain(item) for item in value]
    return value


def _binding(value: object) -> dict[str, Any]:
    result = _exact(_owned(value), _BINDING_FIELDS)
    for key, item in result.items():
        if key in {"session_id", "attempt_id"}:
            _require(type(item) is str and _ID.fullmatch(item) is not None)
        else:
            _sha(item)
    return result


def _typed(kind: type, value: object) -> Any:
    return kind(**_exact(value, {field.name for field in fields(kind)}))


def _request(value: object, binding: dict[str, Any]) -> CameraActivationRequest:
    raw = dict(_exact(value, {field.name for field in fields(CameraActivationRequest)}))
    raw["binding"] = _typed(CameraEndpointBinding, raw["binding"])
    raw["mode"] = None if raw["mode"] is None else _typed(NativeCameraMode, raw["mode"])
    raw["budget"] = _typed(CameraCampaignBudget, raw["budget"])
    _require(type(raw["controls"]) is list and len(raw["controls"]) <= 6)
    raw["controls"] = tuple(_typed(CameraControlSetting, c) for c in raw["controls"])
    request = CameraActivationRequest(**raw)
    activation_request_sha256(request)  # Existing pure type/schema/geometry contract.
    _require(
        _plain(request.mode) == MODE
        and 1 <= request.budget.max_frames <= 4
        and request.budget.max_frame_bytes == FRAME_BYTES
        and request.budget.max_total_bytes == FRAME_BYTES * request.budget.max_frames
        and request.budget.duration_ms <= 55000,
        "UNREGISTERED_CAMERA_FIXTURE_REQUEST",
    )
    _require(
        request.campaign_id == binding["attempt_id"]
        and request.source_sha256 == binding["source_sha256"]
        and request.binding.binding_sha256 == binding["selected_identity_sha256"],
        "REQUEST_BINDING_MISMATCH",
    )
    return request


def _blob(data: bytes, maximum: int) -> dict[str, Any]:
    _require(type(data) is bytes and len(data) <= maximum, "WIRE_LIMIT")
    return {
        "encoding": "BASE64",
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "data": base64.b64encode(data).decode("ascii"),
    }


def _decode_blob(value: object, maximum: int) -> bytes:
    raw = _exact(value, {"encoding", "bytes", "sha256", "data"})
    _int(raw["bytes"], 0, maximum)
    _sha(raw["sha256"])
    _require(
        raw["encoding"] == "BASE64"
        and type(raw["data"]) is str
        and len(raw["data"]) <= ((maximum + 2) // 3) * 4
    )
    try:
        data = base64.b64decode(raw["data"], validate=True)
    except (ValueError, TypeError) as error:
        raise OwnedCameraEvidenceError(
            "INVALID_WIRE", "Invalid retained base64 bytes."
        ) from error
    _require(_blob(data, maximum) == raw, "INVALID_WIRE")
    return data


def _json_wire(data: bytes) -> dict[str, Any] | None:
    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result = {}
        for key, value in values:
            _require(key not in result)
            result[key] = value
        return result

    try:
        value = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
        )
        return _owned(value) if type(value) is dict else None
    except (ValueError, UnicodeError, RecursionError):
        return None


def _process(
    value: object, stdout: bytes, stderr: bytes, binding: dict[str, Any]
) -> dict[str, Any]:
    names = {field.name for field in fields(OwnedWorkerResult)} - {"stdout", "stderr"}
    extras = {
        "stdout_bytes",
        "stdout_sha256",
        "stderr_bytes",
        "stderr_sha256",
        "schema",
        "physical_authority",
        "physical_provider_qualified",
        "device_cleanup_confirmed",
        "final_power_state",
        "handle_limit_kind",
        "retries",
    }
    result = _exact(value, names | extras)
    _require(
        result["schema"] == "rocell.owned_worker_process_result.v1"
        and result["status"] in {"SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT"}
        and result["attempt_id"] == binding["attempt_id"]
    )
    for key in (
        "physical_authority",
        "physical_provider_qualified",
        "device_cleanup_confirmed",
    ):
        _require(result[key] is False)
    _require(
        result["final_power_state"] == "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION"
        and result["handle_limit_kind"] == "SAMPLED_NOT_KERNEL_ENFORCED"
        and type(result["retries"]) is int
        and result["retries"] == 0
    )
    _sha(result["request_sha256"])
    for key in ("process_created", "initial_thread_resumed", "tree_exit_confirmed"):
        _require(type(result[key]) is bool)
    _require(not result["initial_thread_resumed"] or result["process_created"])
    if result["primary_error"] is not None:
        _text(result["primary_error"], 128)
    _require(
        type(result["cleanup_errors"]) is list and len(result["cleanup_errors"]) <= 512
    )
    for item in result["cleanup_errors"]:
        _text(item, 128)
    if result["returncode"] is not None:
        _int(result["returncode"], -(2**31), 2**32 - 1)
    for key in (
        "elapsed_ns",
        "stdin_bytes_written",
        "peak_observed_handles",
        "peak_active_processes",
    ):
        _int(result[key])
    for key, data in (("stdout", stdout), ("stderr", stderr)):
        _require(
            type(result[key + "_bytes"]) is int
            and result[key + "_bytes"] == len(data)
            and result[key + "_sha256"] == hashlib.sha256(data).hexdigest()
        )
    _require(result["parsed_result"] is None or type(result["parsed_result"]) is dict)
    return result


def _native(value: object, request: CameraActivationRequest) -> NativeCameraReceipt:
    raw = dict(_exact(value, {field.name for field in fields(NativeCameraReceipt)}))
    for key, kind, limit in (
        ("candidates", CameraCandidate, 64),
        ("modes", NativeCameraMode, 128),
        ("controls", NativeControlObservation, 6),
        ("frames", NativeFrameArtifact, 32),
    ):
        _require(type(raw[key]) is list and len(raw[key]) <= limit)
        raw[key] = tuple(_typed(kind, item) for item in raw[key])
    for key in ("requested_mode", "observed_mode"):
        raw[key] = None if raw[key] is None else _typed(NativeCameraMode, raw[key])
    _require(type(raw["limitations"]) is list and len(raw["limitations"]) <= 24)
    for item in raw["limitations"]:
        _text(item, 128)
    raw["limitations"] = tuple(raw["limitations"])
    receipt = NativeCameraReceipt(**raw)
    _require(
        receipt.operation == "capture"
        and receipt.status in {"OK", "FAILED"}
        and (receipt.status == "OK") == (receipt.reason_code is None)
        and receipt.selected_endpoint == request.binding.symbolic_link
        and type(receipt.cleanup_confirmed) is bool
    )
    if receipt.reason_code is not None:
        _text(receipt.reason_code, 96)
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
                else (
                    6
                    if key == "control_set_attempts"
                    else 32 if key == "frames_written" else 100000
                )
            ),
        )
    _require(
        counts["source_opened"] <= counts["source_activation_attempts"]
        and counts["source_shutdown_attempts"] <= counts["source_activation_attempts"]
        and counts["control_set_attempts"] <= len(request.controls)
        and counts["frames_written"] == len(receipt.frames)
        and counts["samples_received"] >= len(receipt.frames)
    )
    for candidate in receipt.candidates:
        _text(candidate.symbolic_link)
        _text(candidate.friendly_name, 1024)
    _require(
        len({c.symbolic_link for c in receipt.candidates}) == len(receipt.candidates)
    )
    if counts["source_opened"]:
        _require(
            sum(
                c.symbolic_link == receipt.selected_endpoint for c in receipt.candidates
            )
            == 1
        )
    _require(receipt.requested_mode is not None and request.mode is not None)
    assert receipt.requested_mode is not None and request.mode is not None
    _require(receipt.requested_mode.same_format(request.mode))
    controls = {}
    for control in receipt.controls:
        _require(
            control.control_id
            in {
                "exposure",
                "gain",
                "white_balance",
                "brightness",
                "contrast",
                "saturation",
            }
            and control.control_id not in controls
        )
        controls[control.control_id] = control
        for key in ("minimum", "maximum", "default", "value"):
            _int(getattr(control, key), -(2**31), 2**31 - 1)
        _int(control.step, 1, 2**31 - 1)
        _int(control.flags, 1, 3)
        _int(control.capability_flags, 1, 3)
        _text(control.unit, 64)
        _require(
            control.minimum <= control.default <= control.maximum
            and control.minimum <= control.value <= control.maximum
        )
    total_bytes = 0
    for index, frame in enumerate(receipt.frames):
        _require(
            frame.filename == f"frame-{index:06d}.yuy2"
            and receipt.observed_mode is not None
        )
        _sha(frame.sha256)
        _int(frame.length_bytes, 1, request.budget.max_frame_bytes)
        _int(frame.stride_bytes, -1048576, 1048576)
        _int(frame.row0_offset_bytes, 0, frame.length_bytes - 1)
        _int(frame.host_sequence, 0, 31)
        _int(frame.media_timestamp_100ns, -(2**63), 2**63 - 1)
        _int(frame.host_arrival_qpc)
        _int(frame.qpc_frequency, 1)
        _require(frame.discontinuity is None or type(frame.discontinuity) is bool)
        assert receipt.observed_mode is not None
        last_row = frame.row0_offset_bytes + frame.stride_bytes * (
            receipt.observed_mode.height - 1
        )
        _require(
            abs(frame.stride_bytes) >= receipt.observed_mode.width * 2
            and min(last_row, frame.row0_offset_bytes) >= 0
            and max(last_row, frame.row0_offset_bytes) + receipt.observed_mode.width * 2
            <= frame.length_bytes
            and frame.host_sequence == index
        )
        total_bytes += frame.length_bytes
    _require(
        total_bytes <= request.budget.max_total_bytes
        and len(receipt.frames) <= request.budget.max_frames
    )
    if receipt.status == "OK":
        _require(receipt.cleanup_confirmed and receipt.observed_mode is not None)
        assert receipt.observed_mode is not None
        _require(
            receipt.observed_mode.same_format(request.mode)
            and any(mode.same_format(receipt.observed_mode) for mode in receipt.modes)
            and counts["source_activation_attempts"]
            == counts["source_opened"]
            == counts["source_shutdown_attempts"]
            == 1
            and counts["control_set_attempts"] == len(request.controls)
            and counts["samples_received"]
            == counts["frames_written"]
            == request.budget.max_frames
        )
        for setting in request.controls:
            actual = controls.get(setting.control_id)
            _require(
                actual is not None
                and actual.flags == (1 if setting.mode == "auto" else 2)
                and (setting.mode == "auto" or actual.value == setting.value)
            )
    return receipt


def _wire_matches(
    wire: dict[str, Any] | None,
    process: dict[str, Any],
    request: CameraActivationRequest,
    native: NativeCameraReceipt | None,
) -> bool:
    """Pure wire/typed join. Raw failed or malformed stdout is always retained."""
    if wire is None or native is None:
        return False
    try:
        _exact(
            wire,
            {
                "schema",
                "request_sha256",
                "attempt_id",
                "physical_authority",
                "fixture_result",
            },
        )
        _require(
            wire["schema"]
            == (
                "rocell.owned_camera_fixture_result.v2"
                if request.controls
                else "rocell.owned_camera_fixture_result.v1"
            )
            and wire["request_sha256"] == process["request_sha256"]
            and wire["attempt_id"] == request.campaign_id
            and wire["physical_authority"] is False
        )
        result = _exact(
            wire["fixture_result"],
            {
                "scenario",
                "provenance",
                "camera_request_sha256",
                "template_sha256s",
                "native_receipt",
            },
        )
        _require(type(result["scenario"]) is str and result["scenario"] in SCENARIOS)
        _require(
            result["provenance"] == "INCAPABLE_CAMERA_PROCESS_FIXTURE"
            and result["camera_request_sha256"] == _hash(_plain(request))
        )
        _require(
            type(result["template_sha256s"]) is list
            and len(result["template_sha256s"]) == request.budget.max_frames
        )
        for item in result["template_sha256s"]:
            _sha(item)
        raw = _exact(
            result["native_receipt"],
            {
                "schema",
                "operation",
                "status",
                "reason_code",
                "selected_endpoint",
                "devices",
                "modes",
                "requested_mode",
                "observed_mode",
                "controls",
                "frames",
                "counts",
                "cleanup",
                "limitations",
            },
        )
        typed = _plain(native)
        if request.controls:
            validate_control_observations(raw["controls"])
        else:
            _require(raw["controls"] == [])
        _require(
            PROVENANCE in native.limitations
            and type(process["returncode"]) is int
            and process["returncode"] == (0 if native.status == "OK" else 1)
        )
        expected = {
            key: item
            for key, item in typed.items()
            if key not in {"candidates", "cleanup_confirmed", "frames"}
        }
        expected.update(
            schema="rocell.windows_camera.v1",
            devices=typed["candidates"],
            frames=[
                {key: item for key, item in frame.items() if key != "sha256"}
                for frame in typed["frames"]
            ],
        )
        _require(
            _same(
                {key: item for key, item in raw.items() if key != "cleanup"}, expected
            )
        )
        cleanup = _exact(
            raw["cleanup"],
            {
                "source_shutdown_hr",
                "source_released",
                "mf_shutdown_hr",
                "com_uninitialized",
            },
        )
        for key in ("source_shutdown_hr", "mf_shutdown_hr"):
            if cleanup[key] is not None:
                _int(cleanup[key], -(2**31), 2**31 - 1)
        _require(
            type(cleanup["source_released"]) is bool
            and type(cleanup["com_uninitialized"]) is bool
        )
        confirmed = (
            cleanup["source_released"]
            and cleanup["com_uninitialized"]
            and cleanup["mf_shutdown_hr"] == 0
            and (
                native.counts["source_activation_attempts"] == 0
                or (
                    native.counts["source_shutdown_attempts"] == 1
                    and cleanup["source_shutdown_hr"] == 0
                )
            )
        )
        _require(confirmed == native.cleanup_confirmed)
        _require(
            process["parsed_result"] is not None
            and _same(process["parsed_result"], wire)
        )
        return True
    except (OwnedCameraEvidenceError, ValueError, TypeError, KeyError):
        return False


def _capture_valid(
    capture: dict[str, Any],
    envelope: object,
    source: object,
    request: CameraActivationRequest,
    native: NativeCameraReceipt,
    binding: dict[str, Any],
) -> bool:
    """Rebuild metadata contracts only; never read the paths retained here."""
    try:
        _exact(
            capture,
            {
                "schema",
                "status",
                "domain",
                "dataset",
                "verification",
                "latest_preview",
                "envelope_path",
                "envelope_sha256",
                "source_contract_sha256",
                "physical_authority",
                "m1_qualified",
                "received_hardware_accepted",
                "native_power_loss_qualification",
            },
        )
        _require(
            capture["schema"] == "rocell.windows_camera_capture_ingest.v1"
            and capture["status"] == "CONTENT_VERIFIED_DIAGNOSTIC_ONLY"
            and capture["domain"] == "INCAPABLE_NATIVE_FIXTURE"
            and capture["native_power_loss_qualification"] == "NOT_RUN"
        )
        for key in ("physical_authority", "m1_qualified", "received_hardware_accepted"):
            _require(capture[key] is False)
        shared = set(capture) - {"envelope_path", "envelope_sha256"}
        raw_envelope = _exact(
            envelope, shared | {"activation_request_sha256", "native_receipt_sha256"}
        )
        _require(
            _same(
                {key: raw_envelope[key] for key in shared},
                {key: capture[key] for key in shared},
            )
            and _hash(envelope, ingest=True) == capture["envelope_sha256"]
        )
        raw_source = _exact(
            source,
            {
                "schema",
                "plan",
                "activation_request",
                "native_receipt",
                "native_receipt_sha256",
                "capture_plan",
                "timing_conversion",
                "media_conversion",
                "color_policy",
                "resample_policy",
                "physical_authority",
                "m1_qualified",
            },
        )
        _require(
            _hash(source, ingest=True) == capture["source_contract_sha256"]
            and raw_source["schema"] == CONTRACT_SCHEMA
            and raw_source["physical_authority"] is False
            and raw_source["m1_qualified"] is False
            and _same(raw_source["activation_request"], _plain(request))
            and _same(raw_source["native_receipt"], _plain(native))
            and raw_source["timing_conversion"]
            == "QPC_POINT_FLOOR_CEIL_NS_NOT_CAPTURE_INTERVAL_OR_WALL_TIME"
            and raw_source["media_conversion"]
            == "EXACT_100NS_TO_NS_NOT_SENSOR_EXPOSURE"
            and raw_source["color_policy"] == COLOR_POLICY
            and raw_source["resample_policy"] == RESAMPLE_POLICY
        )
        raw_plan = dict(
            _exact(
                raw_source["plan"],
                {field.name for field in fields(NativeCaptureIngestPlan)},
            )
        )
        _require(
            raw_plan["domain"] == "INCAPABLE_NATIVE_FIXTURE"
            and raw_plan["source_sha256"] == binding["source_sha256"]
            and raw_plan["settings_epoch"] == binding["settings_epoch"]
            and raw_plan["capture_directory"] == request.output_directory
            and raw_plan["activation_request_sha256"]
            == activation_request_sha256(request)
            == raw_envelope["activation_request_sha256"]
            and raw_source["native_receipt_sha256"]
            == _hash(_plain(native), ingest=True)
            == raw_envelope["native_receipt_sha256"]
        )
        raw_plan["capture_directory"] = Path(raw_plan["capture_directory"])
        raw_plan["dataset_root"] = Path(raw_plan["dataset_root"])
        raw_plan["quotas"] = _typed(DatasetQuotas, raw_plan["quotas"])
        frame_plans = []
        _require(
            type(raw_plan["frames"]) is list and 1 <= len(raw_plan["frames"]) <= 32
        )
        for item in raw_plan["frames"]:
            item = dict(_exact(item, {field.name for field in fields(FramePlan)}))
            item["preview"] = (
                None
                if item["preview"] is None
                else _typed(PreviewTransform, item["preview"])
            )
            frame_plans.append(FramePlan(**item))
        raw_plan["frames"] = tuple(frame_plans)
        plan = NativeCaptureIngestPlan(**raw_plan)
        derived, _ = _validate_receipt(request, native, plan)
        verification = _exact(
            capture["verification"],
            {
                "path",
                "manifest_sha256",
                "plan",
                "frames",
                "logical_bytes",
                "content_verified",
                "requested_mode_matches",
                "physical_authority",
                "m1_qualified",
            },
        )
        dataset = _exact(
            capture["dataset"],
            {
                "path",
                "manifest_sha256",
                "plan_sha256",
                "frames",
                "logical_bytes",
                "physical_authority",
            },
        )
        _require(
            _same(verification["plan"], _plain(derived))
            and _same(raw_source["capture_plan"], _plain(derived))
            and verification["content_verified"] is True
            and verification["requested_mode_matches"] is True
            and verification["physical_authority"] is False
            and verification["m1_qualified"] is False
            and dataset["physical_authority"] is False
        )
        for key in ("path", "manifest_sha256", "frames", "logical_bytes"):
            _require(_same(verification[key], dataset[key]))
        for key in ("manifest_sha256", "plan_sha256"):
            _sha(dataset[key])
        _require(
            dataset["plan_sha256"]
            == _hash(
                {
                    "schema": PLAN_SCHEMA,
                    "plan": _plain(derived),
                    "declarations": _DECLARATIONS,
                },
                ingest=True,
            )
        )
        _int(dataset["frames"], 1, 32)
        _int(dataset["logical_bytes"], 1, 2**53 - 1)
        _require(dataset["frames"] == len(native.frames))
        _require(
            sum(frame.length_bytes for frame in native.frames)
            <= dataset["logical_bytes"]
            <= sum(frame.length_bytes for frame in native.frames)
            + sum(
                frame.preview.maximum_bytes if frame.preview else 0
                for frame in plan.frames
            )
        )
        envelope_path, dataset_path = Path(capture["envelope_path"]), Path(
            dataset["path"]
        )
        _require(
            envelope_path.name == "ingest-receipt.json"
            and re.fullmatch(r"ingest-[0-9a-f]{32}", envelope_path.parent.name)
            is not None
            and dataset_path.parent == envelope_path.parent
            and re.fullmatch(r"capture-[0-9a-f]{32}", dataset_path.name) is not None
            and envelope_path.parent.parent == plan.dataset_root
        )
        return True
    except (ValueError, TypeError, KeyError, AttributeError, AssertionError):
        return False


def _derive(document: dict[str, Any]) -> dict[str, Any]:
    _exact(document, _EVIDENCE_FIELDS)
    _require(
        document["schema"] == SCHEMA
        and document["domain"] == "INCAPABLE_CAMERA_PROCESS_REHEARSAL"
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
    native = None
    if document["native_receipt"] is not None:
        _require(request is not None)
        assert request is not None
        native = _native(document["native_receipt"], request)
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
        blockers.append("ACTIVATION_REQUEST_UNAVAILABLE")
    if process is None:
        blockers.append("OWNED_PROCESS_RESULT_UNAVAILABLE")
    process_ok = (
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
    native_valid = bool(
        request is not None
        and process is not None
        and _wire_matches(_json_wire(stdout), process, request, native)
    )
    if not native_valid:
        blockers.append("NATIVE_WIRE_OR_REQUEST_BINDING_UNVERIFIED")
    if native is None or native.status != "OK" or not native.cleanup_confirmed:
        blockers.append("SYNTHETIC_NATIVE_CAPTURE_NOT_CONFIRMED")
    capture = document["capture"]
    capture_valid = bool(
        capture is not None
        and request is not None
        and native is not None
        and native_valid
        and _capture_valid(
            capture,
            document["capture_envelope"],
            document["source_contract"],
            request,
            native,
            binding,
        )
    )
    if not capture_valid:
        blockers.append("CAPTURE_METADATA_BINDING_UNVERIFIED")
    if error is not None:
        blockers.append("CALLER_REPORTED_ERROR")
    capture_view = None
    if capture is not None:
        # Display only bounded typed hashes/counts, even when the join is held.
        _require(type(capture) is dict and type(capture.get("dataset")) is dict)
        dataset = capture["dataset"]
        capture_view = {"metadata_binding_valid": capture_valid}
        for key, container in (
            ("manifest_sha256", dataset),
            ("plan_sha256", dataset),
            ("envelope_sha256", capture),
            ("source_contract_sha256", capture),
        ):
            _sha(container.get(key))
            capture_view[key] = container[key]
        for key in ("frames", "logical_bytes"):
            _int(dataset.get(key), 0, 32 if key == "frames" else 2**53 - 1)
            capture_view[key] = dataset[key]
    return {
        "schema": SUMMARY_SCHEMA,
        "status": (
            "RETAINED_COMPLETE_REHEARSAL"
            if not blockers
            else "RETAINED_INCOMPLETE_REHEARSAL"
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
                "frame_count": len(native.frames),
            }
        ),
        "capture": capture_view,
        "blockers": blockers,
        "device_cleanup_proven": False,
        "physical_authority": False,
        "qualified": False,
        "meaning": _MEANING,
    }


@dataclass(frozen=True, slots=True)
class RehearsalOwnedCameraEvidence:
    payload: bytes

    def __post_init__(self) -> None:
        _require(
            type(self.payload) is bytes and len(self.payload) <= MAX_EVIDENCE_BYTES,
            "EVIDENCE_LIMIT",
        )

    @property
    def evidence_sha256(self) -> str:
        return hashlib.sha256(self.payload).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self.payload)

    def view(self) -> dict[str, Any]:
        return {**_derive(self.to_dict()), "evidence_sha256": self.evidence_sha256}


def retain_owned_camera_evidence(
    *,
    binding: dict,
    activation_request: CameraActivationRequest | None,
    process_result: OwnedWorkerResult | None,
    native_receipt: NativeCameraReceipt | None,
    capture: NativeCaptureIngestReceipt | None,
    error: dict | None,
    capture_envelope: dict | None = None,
    source_contract: dict | None = None,
) -> RehearsalOwnedCameraEvidence:
    """Retain exact bounded returned observations; no file/process/device I/O."""
    for value, kind in (
        (activation_request, CameraActivationRequest),
        (process_result, OwnedWorkerResult),
        (native_receipt, NativeCameraReceipt),
        (capture, NativeCaptureIngestReceipt),
    ):
        _require(value is None or type(value) is kind)
    if capture is not None:
        # to_dict() declares false flags; do not let that projection erase a
        # contradictory typed caller value before checking it.
        _require(capture.physical_authority is False and capture.m1_qualified is False)
    document = _owned(
        {
            "schema": SCHEMA,
            "domain": "INCAPABLE_CAMERA_PROCESS_REHEARSAL",
            "binding": _binding(binding),
            "activation_request": (
                None if activation_request is None else _plain(activation_request)
            ),
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
            "capture": None if capture is None else capture.to_dict(),
            "capture_envelope": capture_envelope,
            "source_contract": source_contract,
            "error": error,
            "physical_authority": False,
            "qualified": False,
        }
    )
    _derive(document)
    return RehearsalOwnedCameraEvidence(_canonical(document))


def verify_owned_camera_evidence(
    payload: bytes, expected_binding: dict
) -> RehearsalOwnedCameraEvidence:
    """Pure canonical/semantic verification; caller owns trusted M1 digest check."""
    _require(
        type(payload) is bytes and 1 <= len(payload) <= MAX_EVIDENCE_BYTES,
        "EVIDENCE_LIMIT",
    )
    document = _json_wire(payload)
    _require(document is not None and _canonical(document) == payload)
    assert document is not None
    _require(document.get("binding") == _binding(expected_binding), "BINDING_MISMATCH")
    _derive(document)
    return RehearsalOwnedCameraEvidence(payload)
