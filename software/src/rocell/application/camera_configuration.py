"""Pure reported camera capabilities, staged requests and readback comparison.

No function enumerates devices, opens a provider, applies a setting or grants
authority. A settings epoch identifies an electronic *request*, never the
separate composite dataset epoch or proof that a received camera was configured.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
import hashlib
import json
import re
from typing import Any

from rocell.application.rehearsal_owned_camera_evidence import (
    _canonical,
    _owned,
    _plain,
    _same,
)
from rocell.providers.windows.camera_worker_client import (
    CameraActivationRequest,
    CameraControlSetting,
    NativeCameraMode,
    NativeCameraReceipt,
    NativeControlObservation,
)

CAPABILITIES_SCHEMA = "rocell.camera_capabilities.v1"
CONFIGURATION_SCHEMA = "rocell.camera_configuration.v1"
READBACK_SCHEMA = "rocell.camera_readback.v1"
DOMAIN = "INCAPABLE_CAMERA_CONFIGURATION_REHEARSAL"
CONTROL_IDS = (
    "exposure",
    "gain",
    "white_balance",
    "brightness",
    "contrast",
    "saturation",
)
MAX_CONFIGURATION_BYTES = 96 * 1024
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\Z")
BINDING_FIELDS = frozenset(
    {
        "session_id",
        "attempt_id",
        "source_sha256",
        "permit_sha256",
        "operation_sha256",
        "selected_identity_sha256",
    }
)
_CAP_FIELDS = {
    "schema",
    "domain",
    "binding",
    "probe_evidence_sha256",
    "endpoint_sha256",
    "modes",
    "controls",
    "physical_authority",
    "qualified",
}
_CONFIG_FIELDS = {
    "schema",
    "domain",
    "capabilities_sha256",
    "probe_evidence_sha256",
    "session_id",
    "source_sha256",
    "selected_identity_sha256",
    "endpoint_sha256",
    "mode_choice_id",
    "mode",
    "controls",
    "control_capabilities",
    "applied",
    "physical_authority",
    "qualified",
}


class CameraConfigurationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def _require(condition: bool, code: str = "INVALID_CAMERA_CONFIGURATION") -> None:
    if not condition:
        raise CameraConfigurationError(
            code, "Camera configuration failed its exact bounded contract."
        )


def _sha(value: object) -> None:
    _require(type(value) is str and _HASH.fullmatch(value) is not None)


def _text(value: object, maximum: int) -> None:
    _require(type(value) is str and bool(value))
    assert isinstance(value, str)
    _require(
        len(value.encode("utf-8")) <= maximum
        and not any(ord(c) < 32 or ord(c) == 127 for c in value)
    )


def _int(value: object, low: int, high: int) -> None:
    _require(type(value) is int and low <= value <= high)


def _exact(value: object, names: set[str] | frozenset[str]) -> dict[str, Any]:
    _require(type(value) is dict and set(value) == names)
    assert isinstance(value, dict)
    return value


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _binding(value: object) -> dict[str, Any]:
    result = _exact(_owned(value), BINDING_FIELDS)
    for key, item in result.items():
        if key in {"session_id", "attempt_id"}:
            _require(type(item) is str and _ID.fullmatch(item) is not None)
        else:
            _sha(item)
    return result


def _load(payload: bytes) -> dict[str, Any]:
    _require(type(payload) is bytes and 0 < len(payload) <= MAX_CONFIGURATION_BYTES)
    try:
        value = _owned(json.loads(payload))
        _require(_canonical(value) == payload, "NONCANONICAL_CONFIGURATION")
    except (UnicodeError, ValueError, TypeError, RecursionError) as error:
        raise CameraConfigurationError(
            "INVALID_CONFIGURATION_BYTES",
            "Invalid bounded canonical configuration bytes.",
        ) from error
    _require(type(value) is dict)
    return value


def _mode(value: object) -> NativeCameraMode:
    raw = _exact(value, {f.name for f in fields(NativeCameraMode)})
    try:
        return NativeCameraMode(**raw)
    except (TypeError, ValueError, RuntimeError) as error:
        raise CameraConfigurationError(
            "INVALID_REPORTED_MODE", "Reported mode violates the native typed contract."
        ) from error


def _control(value: object) -> NativeControlObservation:
    raw = _exact(value, {f.name for f in fields(NativeControlObservation)})
    _require(raw["control_id"] in CONTROL_IDS)
    for name in ("minimum", "maximum", "default", "value"):
        _int(raw[name], -(2**31), 2**31 - 1)
    _int(raw["step"], 1, 2**31 - 1)
    _int(raw["capability_flags"], 1, 3)
    _int(raw["flags"], 1, 3)
    _text(raw["unit"], 64)
    _require(
        raw["minimum"] <= raw["default"] <= raw["maximum"]
        and raw["minimum"] <= raw["value"] <= raw["maximum"]
    )
    return NativeControlObservation(**raw)


def _mode_blockers(mode: NativeCameraMode) -> list[str]:
    blockers = []
    if mode.subtype != "YUY2":
        blockers.append("UNSUPPORTED_PIXEL_FORMAT")
    if mode.width % 2:
        blockers.append("ODD_YUY2_WIDTH")
    if mode.width * mode.height * 2 > 64 * 1024 * 1024:
        blockers.append("FRAME_BUDGET_EXCEEDED")
    if mode.stride_bytes is not None:
        if abs(mode.stride_bytes) < mode.width * 2:
            blockers.append("INVALID_REPORTED_STRIDE")
        elif (
            abs(mode.stride_bytes) * mode.height > 64 * 1024 * 1024
            and "FRAME_BUDGET_EXCEEDED" not in blockers
        ):
            blockers.append("FRAME_BUDGET_EXCEEDED")
    return blockers


def _choice(probe_sha256: str, index: int, mode: dict[str, Any]) -> str:
    return (
        "mode-"
        + _digest(
            {"probe_evidence_sha256": probe_sha256, "index": index, "mode": mode}
        )[:24]
    )


def _validate_capabilities(document: dict[str, Any]) -> None:
    _exact(document, _CAP_FIELDS)
    _require(document["schema"] == CAPABILITIES_SCHEMA and document["domain"] == DOMAIN)
    _binding(document["binding"])
    _sha(document["probe_evidence_sha256"])
    _sha(document["endpoint_sha256"])
    _require(document["physical_authority"] is False and document["qualified"] is False)
    _require(type(document["modes"]) is list and len(document["modes"]) <= 128)
    for mode in document["modes"]:
        _mode(mode)
    _require(type(document["controls"]) is list and len(document["controls"]) <= 6)
    observed = [_control(control) for control in document["controls"]]
    _require(
        len({c.control_id for c in observed}) == len(observed), "DUPLICATE_CONTROL"
    )


@dataclass(frozen=True, slots=True)
class CameraCapabilities:
    payload: bytes

    def __post_init__(self) -> None:
        _validate_capabilities(_load(self.payload))

    @property
    def capabilities_sha256(self) -> str:
        return hashlib.sha256(self.payload).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self.payload)

    @classmethod
    def from_payload(
        cls,
        payload: bytes,
        *,
        expected_probe_evidence_sha256: str,
        expected_binding: dict[str, Any],
    ) -> CameraCapabilities:
        _sha(expected_probe_evidence_sha256)
        expected = _binding(expected_binding)
        result = cls(payload)
        data = result.to_dict()
        _require(
            data["probe_evidence_sha256"] == expected_probe_evidence_sha256
            and _same(data["binding"], expected),
            "STALE_PROBE_BINDING",
        )
        return result

    def view(self) -> dict[str, Any]:
        data = self.to_dict()
        modes = []
        for index, mode in enumerate(data["modes"]):
            blockers = _mode_blockers(_mode(mode))
            modes.append(
                {
                    "choice_id": _choice(data["probe_evidence_sha256"], index, mode),
                    "mode": mode,
                    "selectable": not blockers,
                    "blockers": blockers,
                }
            )
        return {
            "schema": CAPABILITIES_SCHEMA,
            "status": "REPORTED_REHEARSAL_ONLY",
            "capabilities_sha256": self.capabilities_sha256,
            "probe_evidence_sha256": data["probe_evidence_sha256"],
            "binding": data["binding"],
            "endpoint_sha256": data["endpoint_sha256"],
            "modes": modes,
            "controls": data["controls"],
            "unavailable_controls": [
                c
                for c in CONTROL_IDS
                if c not in {item["control_id"] for item in data["controls"]}
            ],
            "physical_authority": False,
            "qualified": False,
            "meaning": "Exact reported synthetic capabilities only; unavailable controls are not inferred. No received-unit support, default selection, setting application or qualification is established.",
        }


def _capabilities_from_verified_probe(
    *,
    binding: dict[str, Any],
    probe_evidence_sha256: str,
    request: CameraActivationRequest,
    receipt: NativeCameraReceipt,
) -> CameraCapabilities:
    """Internal join after the separate retained probe verifier succeeds."""
    expected = _binding(binding)
    _sha(probe_evidence_sha256)
    _require(
        type(request) is CameraActivationRequest
        and type(receipt) is NativeCameraReceipt
    )
    _require(
        request.operation == receipt.operation == "probe"
        and receipt.status == "OK"
        and receipt.cleanup_confirmed is True
    )
    _require(
        request.campaign_id == expected["attempt_id"]
        and request.source_sha256 == expected["source_sha256"]
        and request.binding.binding_sha256 == expected["selected_identity_sha256"]
    )
    _require(
        receipt.selected_endpoint == request.binding.symbolic_link
        and not receipt.frames
        and not request.controls
        and request.mode is None
    )
    return CameraCapabilities(
        _canonical(
            {
                "schema": CAPABILITIES_SCHEMA,
                "domain": DOMAIN,
                "binding": expected,
                "probe_evidence_sha256": probe_evidence_sha256,
                "endpoint_sha256": request.binding.endpoint_sha256,
                "modes": _plain(receipt.modes),
                "controls": _plain(receipt.controls),
                "physical_authority": False,
                "qualified": False,
            }
        )
    )


def _configuration_document(
    capabilities: CameraCapabilities,
    mode_choice_id: str,
    controls: tuple[CameraControlSetting, ...],
) -> dict[str, Any]:
    _require(type(capabilities) is CameraCapabilities)
    # Revalidate bytes, not only the nominal frozen Python type.
    capabilities = CameraCapabilities(capabilities.payload)
    _text(mode_choice_id, 96)
    selected = next(
        (
            item
            for item in capabilities.view()["modes"]
            if item["choice_id"] == mode_choice_id
        ),
        None,
    )
    _require(selected is not None, "UNKNOWN_MODE_CHOICE")
    assert selected is not None
    _require(selected["selectable"], "UNSUPPORTED_CAPTURE_MODE")
    _require(type(controls) is tuple and len(controls) <= 6)
    requested = []
    for item in controls:
        _require(type(item) is CameraControlSetting)
        try:
            requested.append(CameraControlSetting(**_plain(item)))
        except (ValueError, TypeError, RuntimeError) as error:
            raise CameraConfigurationError(
                "INVALID_CONTROL_REQUEST",
                "Control setting is not an exact supported typed request.",
            ) from error
    _require(
        len({item.control_id for item in requested}) == len(requested),
        "DUPLICATE_CONTROL",
    )
    data = capabilities.to_dict()
    reported = {item["control_id"]: item for item in data["controls"]}
    pinned_controls = []
    for item in requested:
        _require(item.control_id in reported, "CONTROL_NOT_REPORTED")
        observed = reported[item.control_id]
        flag = 1 if item.mode == "auto" else 2
        _require(bool(observed["capability_flags"] & flag), "CONTROL_MODE_UNSUPPORTED")
        _require(
            observed["minimum"] <= item.value <= observed["maximum"],
            "CONTROL_OUT_OF_RANGE",
        )
        _require(
            (item.value - observed["minimum"]) % observed["step"] == 0,
            "CONTROL_OFF_STEP",
        )
        pinned_controls.append(observed)
    return {
        "schema": CONFIGURATION_SCHEMA,
        "domain": DOMAIN,
        "capabilities_sha256": capabilities.capabilities_sha256,
        "probe_evidence_sha256": data["probe_evidence_sha256"],
        "session_id": data["binding"]["session_id"],
        "source_sha256": data["binding"]["source_sha256"],
        "selected_identity_sha256": data["binding"]["selected_identity_sha256"],
        "endpoint_sha256": data["endpoint_sha256"],
        "mode_choice_id": mode_choice_id,
        "mode": selected["mode"],
        "controls": _plain(tuple(requested)),
        "control_capabilities": pinned_controls,
        "applied": False,
        "physical_authority": False,
        "qualified": False,
    }


@dataclass(frozen=True, slots=True)
class StagedCameraConfiguration:
    payload: bytes

    def __post_init__(self) -> None:
        data = _exact(_load(self.payload), _CONFIG_FIELDS)
        _require(data["schema"] == CONFIGURATION_SCHEMA and data["domain"] == DOMAIN)
        for key in (
            "capabilities_sha256",
            "probe_evidence_sha256",
            "source_sha256",
            "selected_identity_sha256",
            "endpoint_sha256",
        ):
            _sha(data[key])
        _require(
            type(data["session_id"]) is str
            and _ID.fullmatch(data["session_id"]) is not None
        )
        _text(data["mode_choice_id"], 96)
        _require(re.fullmatch(r"mode-[0-9a-f]{24}", data["mode_choice_id"]) is not None)
        _require(not _mode_blockers(_mode(data["mode"])), "UNSUPPORTED_CAPTURE_MODE")
        _require(type(data["controls"]) is list and len(data["controls"]) <= 6)
        _require(
            type(data["control_capabilities"]) is list
            and len(data["control_capabilities"]) == len(data["controls"])
        )
        seen = set()
        for requested, observed in zip(data["controls"], data["control_capabilities"]):
            setting = CameraControlSetting(
                **_exact(requested, {f.name for f in fields(CameraControlSetting)})
            )
            capability = _control(observed)
            _require(setting.control_id == capability.control_id)
            _require(setting.control_id not in seen, "DUPLICATE_CONTROL")
            seen.add(setting.control_id)
            _require(
                bool(
                    capability.capability_flags & (1 if setting.mode == "auto" else 2)
                ),
                "CONTROL_MODE_UNSUPPORTED",
            )
            _require(
                capability.minimum <= setting.value <= capability.maximum,
                "CONTROL_OUT_OF_RANGE",
            )
            _require(
                (setting.value - capability.minimum) % capability.step == 0,
                "CONTROL_OFF_STEP",
            )
        _require(
            data["applied"] is False
            and data["physical_authority"] is False
            and data["qualified"] is False
        )

    @property
    def settings_epoch(self) -> str:
        return hashlib.sha256(self.payload).hexdigest()

    @property
    def mode(self) -> NativeCameraMode:
        return _mode(self.to_dict()["mode"])

    @property
    def controls(self) -> tuple[CameraControlSetting, ...]:
        return tuple(
            CameraControlSetting(**item) for item in self.to_dict()["controls"]
        )

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self.payload)

    def view(self) -> dict[str, Any]:
        data = self.to_dict()
        del data["domain"], data["control_capabilities"]
        return {
            **data,
            "status": "STAGED_NOT_APPLIED_REHEARSAL",
            "settings_epoch": self.settings_epoch,
            "meaning": "Immutable electronic setting request only, not applied state or the composite dataset epoch. A separately admitted capture must retain exact requested-versus-observed readback.",
        }


def stage_camera_configuration(
    capabilities: CameraCapabilities,
    mode_choice_id: str,
    controls: tuple[CameraControlSetting, ...],
    *,
    expected_probe_evidence_sha256: str,
    expected_source_sha256: str,
    expected_selected_identity_sha256: str,
) -> StagedCameraConfiguration:
    for digest in (
        expected_probe_evidence_sha256,
        expected_source_sha256,
        expected_selected_identity_sha256,
    ):
        _sha(digest)
    _require(type(capabilities) is CameraCapabilities)
    data = capabilities.to_dict()
    _require(
        data["probe_evidence_sha256"] == expected_probe_evidence_sha256
        and data["binding"]["source_sha256"] == expected_source_sha256
        and data["binding"]["selected_identity_sha256"]
        == expected_selected_identity_sha256,
        "STALE_PROBE_BINDING",
    )
    return StagedCameraConfiguration(
        _canonical(_configuration_document(capabilities, mode_choice_id, controls))
    )


def verify_camera_configuration(
    payload: bytes, *, expected_capabilities: CameraCapabilities
) -> StagedCameraConfiguration:
    result = StagedCameraConfiguration(payload)
    data = result.to_dict()
    expected = _configuration_document(
        expected_capabilities, data["mode_choice_id"], result.controls
    )
    _require(_same(data, expected), "CONFIGURATION_BINDING_MISMATCH")
    return result


def compare_camera_readback(
    configuration: StagedCameraConfiguration,
    receipt: NativeCameraReceipt,
    *,
    expected_settings_epoch: str,
) -> dict[str, Any]:
    """Compare typed capture observations, never read image files or apply controls.

    Source/request/process and dataset bindings must be checked independently by
    the retained capture verifier; a native receipt alone cannot authenticate them.
    """
    _sha(expected_settings_epoch)
    _require(
        type(configuration) is StagedCameraConfiguration
        and configuration.settings_epoch == expected_settings_epoch,
        "STALE_SETTINGS_EPOCH",
    )
    configuration = StagedCameraConfiguration(configuration.payload)
    _require(type(receipt) is NativeCameraReceipt)
    raw = _owned(_plain(receipt))
    _require(
        type(receipt.operation) is str
        and receipt.operation in {"capture", "probe", "inventory"}
    )
    _require(
        receipt.status in {"OK", "FAILED"} and type(receipt.cleanup_confirmed) is bool
    )
    _require(type(raw["controls"]) is list and len(raw["controls"]) <= 6)
    observed_controls = [_control(item) for item in raw["controls"]]
    _require(
        len({c.control_id for c in observed_controls}) == len(observed_controls),
        "DUPLICATE_CONTROL",
    )
    _require(
        receipt.selected_endpoint is None or type(receipt.selected_endpoint) is str
    )
    observed_modes = {}
    for key in ("requested_mode", "observed_mode"):
        observed_modes[key] = None if raw[key] is None else _mode(raw[key])
    data = configuration.to_dict()
    reasons = []
    if (
        receipt.operation != "capture"
        or receipt.status != "OK"
        or not receipt.cleanup_confirmed
    ):
        reasons.append("CAPTURE_NOT_SUCCESSFULLY_CLOSED")
    if (
        receipt.selected_endpoint is None
        or hashlib.sha256(receipt.selected_endpoint.encode("utf-8")).hexdigest()
        != data["endpoint_sha256"]
    ):
        reasons.append("ENDPOINT_MISMATCH")
    mode_match = all(
        mode is not None and configuration.mode.same_format(mode)
        for mode in observed_modes.values()
    )
    if not mode_match:
        reasons.append("MODE_READBACK_MISMATCH")
    actual_by_id = {item.control_id: item for item in observed_controls}
    rows = []
    for requested, pinned in zip(data["controls"], data["control_capabilities"]):
        actual = actual_by_id.get(requested["control_id"])
        failures = []
        if actual is None:
            failures.append("CONTROL_READBACK_MISSING")
        else:
            expected_flag = 1 if requested["mode"] == "auto" else 2
            if actual.flags != expected_flag:
                failures.append("CONTROL_MODE_READBACK_MISMATCH")
            if requested["mode"] == "manual" and actual.value != requested["value"]:
                failures.append("MANUAL_VALUE_READBACK_MISMATCH")
            if not all(
                getattr(actual, key) == pinned[key]
                for key in (
                    "minimum",
                    "maximum",
                    "step",
                    "default",
                    "capability_flags",
                    "unit",
                )
            ):
                failures.append("CONTROL_CAPABILITY_DRIFT")
        rows.append(
            {
                "control_id": requested["control_id"],
                "requested": {"value": requested["value"], "mode": requested["mode"]},
                "observed": (
                    None
                    if actual is None
                    else {
                        "value": actual.value,
                        "flags": actual.flags,
                        "unit": actual.unit,
                    }
                ),
                "matched": not failures,
                "reasons": failures,
            }
        )
    if any(not row["matched"] for row in rows):
        reasons.append("CONTROL_READBACK_MISMATCH")
    return {
        "schema": READBACK_SCHEMA,
        "status": (
            "REQUESTED_SETTINGS_OBSERVED_REHEARSAL"
            if not reasons
            else "READBACK_MISMATCH_REHEARSAL"
        ),
        "settings_epoch": configuration.settings_epoch,
        "probe_evidence_sha256": data["probe_evidence_sha256"],
        "source_sha256": data["source_sha256"],
        "selected_identity_sha256": data["selected_identity_sha256"],
        "native_receipt_sha256": _digest(raw),
        "requested_mode": data["mode"],
        "observed_mode": raw["observed_mode"],
        "mode_matched": mode_match,
        "controls": rows,
        "reasons": reasons,
        "physical_authority": False,
        "qualified": False,
        "meaning": "Modeled readback comparison only. Auto mode requires an observed auto flag, not a fixed-value promise; manual values must match exactly. This does not authenticate capture provenance or qualify a received camera.",
    }
