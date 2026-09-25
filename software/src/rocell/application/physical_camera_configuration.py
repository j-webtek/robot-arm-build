"""Pure native capability -> operator intent -> retained readback joins.

These distinct physical-shaped contracts never activate a provider, apply a
setting or qualify a received unit. Independent trusted M1 hashes are required
at evidence admission. Probe and capture have different purpose-specific helper
builds; the service, not this numerical/settings layer, reviews that runtime pair.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields, replace
import re
from typing import Any

from .camera_operating_mode_guidance import (
    intent_guidance,
    probe_guidance,
    readback_guidance,
)

from rocell.providers.windows.camera_worker_client import (
    CameraControlSetting,
    NativeCameraMode,
    NativeCameraReceipt,
    NativeCameraReceiptMetadata,
    NativeControlObservation,
)
from rocell.providers.windows.native_camera_capture_registration import (
    PreparedOwnedNativeCapture,
)
from rocell.providers.windows.native_camera_registration import PreparedOwnedNativeProbe
from rocell.providers.windows.native_camera_activation_registration import (
    PreparedOwnedNativeActivation,
)
from .camera_activation_campaign_evidence import (
    CameraActivationArtifact,
    validate_camera_activation_evidence,
)
from rocell.providers.windows.native_camera_protocol import canonical, digest
from rocell.providers.windows.owned_native_camera_evidence import (
    OwnedNativeCameraRunEvidence,
    verify_owned_native_camera_run_evidence,
)
from rocell.providers.windows.owned_worker_process import decode_owned_json

CAPABILITIES_SCHEMA = "rocell.physical_camera_capabilities.v1"
CONFIGURATION_SCHEMA = "rocell.physical_camera_configuration.v1"
READBACK_SCHEMA = "rocell.physical_camera_readback.v1"
PROVENANCE = "PHYSICAL_UNQUALIFIED"
MAX_BYTES = 96 * 1024
CONTROL_IDS = (
    "brightness",
    "contrast",
    "exposure",
    "gain",
    "saturation",
    "white_balance",
)
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\Z")
_BINDING = {
    "session_id",
    "attempt_id",
    "source_sha256",
    "operation_sha256",
    "permit_sha256",
    "selected_identity_sha256",
    "endpoint_sha256",
    "helper_sha256",
    "runtime_registration_sha256",
    "probe_preparation_sha256",
    "probe_evidence_sha256",
}
_CAP = {
    "schema",
    "provenance",
    "status",
    "binding",
    "modes",
    "controls",
    "physical_authority",
    "hardware_qualified",
}
_CONFIG = {
    "schema",
    "provenance",
    "status",
    "capabilities_sha256",
    "binding",
    "mode_choice_id",
    "mode",
    "controls",
    "control_capabilities",
    "applied",
    "physical_authority",
    "hardware_qualified",
}
_RANGE_FIELDS = ("minimum", "maximum", "step", "default", "capability_flags", "unit")


class PhysicalCameraConfigurationError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class _VerifiedObservation:
    """Common data only after version-specific verification; no schema downgrade."""

    document: dict[str, Any]
    evidence_sha256: str
    native_receipt: NativeCameraReceipt | NativeCameraReceiptMetadata | None
    raw_native_receipt: dict[str, Any] | None
    status: str
    process_cleanup_confirmed: bool

    def to_dict(self) -> dict[str, Any]:
        return self.document


def _verified_observation(
    evidence, *, prepared, expected_evidence_sha256, expected_supervision_sha256=None
) -> _VerifiedObservation:
    """Caller supplies original M1 hashes, independently of these private bytes."""
    _sha(expected_evidence_sha256)
    if type(prepared) is PreparedOwnedNativeActivation:
        _sha(expected_supervision_sha256)
        checked = validate_camera_activation_evidence(evidence)
        _require(
            checked.prepared.payload == prepared.payload
            and evidence[0].payload_sha256 == expected_evidence_sha256
            and evidence[1].payload_sha256 == expected_supervision_sha256,
            "ORIGINAL_ACTIVATION_PAIR_BINDING",
        )
        assessed = checked.run.assessment()
        native = assessed.native
        return _VerifiedObservation(
            {
                "schema": "rocell.camera_activation_observation_pair.v2",
                "run": checked.run.to_dict(),
                "supervision": decode_owned_json(
                    checked.supervision_payload, maximum=1024 * 1024
                ),
            },
            checked.run.evidence_sha256,
            None if native is None else native.receipt,
            None if native is None else native.to_dict()["native_receipt"],
            assessed.status,
            assessed.process_cleanup_confirmed,
        )
    _require(
        type(prepared) in (PreparedOwnedNativeProbe, PreparedOwnedNativeCapture)
        and expected_supervision_sha256 is None,
        "EXACT_NATIVE_OBSERVATION_VERSION",
    )
    legacy = verify_owned_native_camera_run_evidence(
        evidence,
        expected_preparation_sha256=prepared.preparation_sha256,
        expected_evidence_sha256=expected_evidence_sha256,
    )
    data = legacy.to_dict()
    _require(
        canonical(data["preparation"]) == prepared.payload
        and data["provenance"] == PROVENANCE
        and data["fixture_preparation"] is None,
        "NATIVE_OBSERVATION_PREPARATION_DOMAIN",
    )
    receipt = legacy.native_receipt
    return _VerifiedObservation(
        data,
        legacy.evidence_sha256,
        receipt,
        None if receipt is None else data["validated_result"]["native_receipt"],
        data["status"],
        legacy.safe_summary()["process_cleanup_confirmed"] is True,
    )


def _require(value: bool, code: str = "PHYSICAL_CAMERA_CONFIGURATION_CONTRACT") -> None:
    if not value:
        raise PhysicalCameraConfigurationError(code)


def _sha(value: Any) -> None:
    _require(
        type(value) is str and bool(_SHA.fullmatch(value)),
        "EXACT_TRUSTED_HASH_REQUIRED",
    )


def _exact(value: Any, names: set[str]) -> dict[str, Any]:
    _require(type(value) is dict and set(value) == names, "EXACT_CONFIGURATION_FIELDS")
    return value


def _load(payload: bytes) -> dict[str, Any]:
    value = decode_owned_json(payload, maximum=MAX_BYTES)
    _require(canonical(value) == payload, "CANONICAL_CONFIGURATION_BYTES")
    return value


def _binding(value: Any) -> dict[str, Any]:
    value = _exact(value, _BINDING)
    for name, item in value.items():
        if name in {"session_id", "attempt_id"}:
            _require(
                type(item) is str and bool(_ID.fullmatch(item)), "EXACT_BINDING_ID"
            )
        else:
            _sha(item)
    return value


def _held(value: dict[str, Any]) -> None:
    _require(
        value["provenance"] == PROVENANCE
        and value["physical_authority"] is False
        and value["hardware_qualified"] is False,
        "NATIVE_QUALIFICATION_REMAINS_HELD",
    )


def _mode(value: Any) -> NativeCameraMode:
    return NativeCameraMode(
        **_exact(value, {field.name for field in fields(NativeCameraMode)})
    )


def _control(value: Any) -> NativeControlObservation:
    raw = _exact(value, {field.name for field in fields(NativeControlObservation)})
    _require(raw["control_id"] in CONTROL_IDS, "UNREPORTED_CONTROL_ID")
    for key in ("minimum", "maximum", "default", "value"):
        _require(
            type(raw[key]) is int and -(2**31) <= raw[key] < 2**31, "CONTROL_INTEGER"
        )
    _require(type(raw["step"]) is int and 1 <= raw["step"] < 2**31, "CONTROL_STEP")
    for key in ("capability_flags", "flags"):
        _require(type(raw[key]) is int and 1 <= raw[key] <= 3, "CONTROL_FLAGS")
    _require(
        type(raw["unit"]) is str
        and 0 < len(raw["unit"].encode("utf-8")) <= 64
        and not any(ord(c) < 32 or ord(c) == 127 for c in raw["unit"]),
        "CONTROL_UNIT",
    )
    _require(
        raw["minimum"] <= raw["default"] <= raw["maximum"]
        and raw["minimum"] <= raw["value"] <= raw["maximum"],
        "CONTROL_RANGE",
    )
    return NativeControlObservation(**raw)


def _controls(value: Any) -> tuple[NativeControlObservation, ...]:
    _require(type(value) is list and len(value) <= 6, "CONTROL_COUNT")
    result = tuple(_control(item) for item in value)
    _require(
        len({item.control_id for item in result}) == len(result), "DUPLICATE_CONTROL"
    )
    return result


def _blockers(mode: NativeCameraMode) -> list[str]:
    result = []
    if mode.subtype != "YUY2":
        result.append("UNSUPPORTED_PIXEL_FORMAT")
    if mode.width < 2 or mode.width % 2:
        result.append("UNSUPPORTED_YUY2_WIDTH")
    span = mode.width * mode.height * 2
    if mode.stride_bytes is not None:
        if abs(mode.stride_bytes) < mode.width * 2:
            result.append("INVALID_REPORTED_STRIDE")
        span = max(span, (mode.height - 1) * abs(mode.stride_bytes) + mode.width * 2)
    if span > 64 * 1024 * 1024:
        result.append("FRAME_BUDGET_EXCEEDED")
    return result


@dataclass(frozen=True, slots=True)
class PhysicalCameraCapabilities:
    payload: bytes

    def __post_init__(self) -> None:
        data = _exact(_load(self.payload), _CAP)
        _require(
            data["schema"] == CAPABILITIES_SCHEMA
            and data["status"] == "OBSERVED_NATIVE_UNQUALIFIED"
        )
        _held(data)
        _binding(data["binding"])
        _require(
            type(data["modes"]) is list and len(data["modes"]) <= 128, "MODE_COUNT"
        )
        for item in data["modes"]:
            _mode(item)
        _controls(data["controls"])

    def to_dict(self) -> dict[str, Any]:
        return _load(self.payload)

    @property
    def capabilities_sha256(self) -> str:
        return digest(self.payload)

    def view(self) -> dict[str, Any]:
        data = self.to_dict()
        rows = []
        for index, raw in enumerate(data["modes"]):
            blockers = _blockers(_mode(raw))
            choice = digest(
                canonical(
                    {
                        "capabilities_sha256": self.capabilities_sha256,
                        "index": index,
                        "mode": raw,
                    }
                )
            )[:24]
            rows.append(
                {
                    "choice_id": "mode-" + choice,
                    "mode": raw,
                    "selectable": not blockers,
                    "blockers": blockers,
                }
            )
        return {
            **data,
            "capabilities_sha256": self.capabilities_sha256,
            "modes": rows,
            "unavailable_controls": [
                name
                for name in CONTROL_IDS
                if name not in {c["control_id"] for c in data["controls"]}
            ],
            "meaning": probe_guidance(
                tuple(_mode(raw) for raw in data["modes"]), _controls(data["controls"])
            ),
        }


def derive_physical_camera_capabilities(
    evidence: OwnedNativeCameraRunEvidence | tuple[CameraActivationArtifact, ...],
    *,
    expected_preparation: PreparedOwnedNativeProbe | PreparedOwnedNativeActivation,
    expected_evidence_sha256: str,
    expected_source_sha256: str,
    expected_supervision_sha256: str | None = None,
) -> PhysicalCameraCapabilities:
    _require(
        type(expected_preparation) is PreparedOwnedNativeProbe
        or (
            type(expected_preparation) is PreparedOwnedNativeActivation
            and expected_preparation.admission_request.purpose == "probe"
        ),
        "EXACT_NATIVE_PROBE_PREPARATION",
    )
    expected = type(expected_preparation)(expected_preparation.payload)
    _sha(expected_source_sha256)
    checked = _verified_observation(
        evidence,
        prepared=expected,
        expected_evidence_sha256=expected_evidence_sha256,
        expected_supervision_sha256=expected_supervision_sha256,
    )
    request = expected.admission_request.to_dict()
    _require(
        request["source_sha256"] == expected_source_sha256,
        "PROBE_SOURCE_PREPARATION_MISMATCH",
    )
    receipt = checked.native_receipt
    _require(
        checked.status == "SUCCEEDED_NATIVE_DIAGNOSTIC"
        and checked.process_cleanup_confirmed
        and (
            type(receipt) is NativeCameraReceipt
            or (
                type(expected) is PreparedOwnedNativeActivation
                and type(receipt) is NativeCameraReceiptMetadata
            )
        ),
        "COMPLETE_NATIVE_PROBE_REQUIRED",
    )
    assert receipt is not None
    _require(
        receipt.operation == "probe"
        and receipt.status == "OK"
        and receipt.cleanup_confirmed
        and not receipt.frames
        and receipt.requested_mode is None
        and receipt.observed_mode is None,
        "SUCCESSFULLY_CLOSED_PROBE_REQUIRED",
    )
    binding = {
        name: request[name]
        for name in _BINDING - {"probe_preparation_sha256", "probe_evidence_sha256"}
    }
    binding.update(
        probe_preparation_sha256=expected.preparation_sha256,
        probe_evidence_sha256=checked.evidence_sha256,
    )
    return PhysicalCameraCapabilities(
        canonical(
            {
                "schema": CAPABILITIES_SCHEMA,
                "provenance": PROVENANCE,
                "status": "OBSERVED_NATIVE_UNQUALIFIED",
                "binding": binding,
                "modes": [asdict(mode) for mode in receipt.modes],
                "controls": [asdict(control) for control in receipt.controls],
                "physical_authority": False,
                "hardware_qualified": False,
            }
        )
    )


def verify_physical_camera_capabilities(
    payload: bytes,
    *,
    evidence: OwnedNativeCameraRunEvidence | tuple[CameraActivationArtifact, ...],
    expected_preparation: PreparedOwnedNativeProbe | PreparedOwnedNativeActivation,
    expected_evidence_sha256: str,
    expected_source_sha256: str,
    expected_capabilities_sha256: str,
    expected_supervision_sha256: str | None = None,
) -> PhysicalCameraCapabilities:
    _sha(expected_capabilities_sha256)
    result = PhysicalCameraCapabilities(payload)
    _require(
        result.capabilities_sha256 == expected_capabilities_sha256,
        "CAPABILITIES_TRUSTED_HASH_MISMATCH",
    )
    expected = derive_physical_camera_capabilities(
        evidence,
        expected_preparation=expected_preparation,
        expected_evidence_sha256=expected_evidence_sha256,
        expected_source_sha256=expected_source_sha256,
        expected_supervision_sha256=expected_supervision_sha256,
    )
    _require(result.payload == expected.payload, "CAPABILITIES_RETAINED_PROBE_MISMATCH")
    return result


def _validate_settings(
    controls: tuple[CameraControlSetting, ...],
    reported: tuple[NativeControlObservation, ...],
) -> tuple[CameraControlSetting, ...]:
    _require(type(controls) is tuple and len(controls) <= 6, "EXACT_CONTROL_REQUESTS")
    copied = []
    for item in controls:
        _require(
            type(item) is CameraControlSetting
            and set(vars(item)) == {f.name for f in fields(CameraControlSetting)},
            "EXACT_CONTROL_SETTING",
        )
        copied.append(replace(item))
    _require(
        len({item.control_id for item in copied}) == len(copied), "DUPLICATE_CONTROL"
    )
    by_id = {item.control_id: item for item in reported}
    for setting in copied:
        observed = by_id.get(setting.control_id)
        _require(observed is not None, "CONTROL_NOT_REPORTED")
        assert observed is not None
        _require(
            bool(observed.capability_flags & (1 if setting.mode == "auto" else 2)),
            "CONTROL_MODE_UNSUPPORTED",
        )
        _require(
            observed.minimum <= setting.value <= observed.maximum,
            "CONTROL_OUT_OF_RANGE",
        )
        _require(
            (setting.value - observed.minimum) % observed.step == 0, "CONTROL_OFF_STEP"
        )
    return tuple(sorted(copied, key=lambda item: item.control_id))


def _configuration(
    capabilities: PhysicalCameraCapabilities,
    choice_id: str,
    controls: tuple[CameraControlSetting, ...],
) -> dict[str, Any]:
    _require(
        type(capabilities) is PhysicalCameraCapabilities, "EXACT_NATIVE_CAPABILITIES"
    )
    capabilities = PhysicalCameraCapabilities(capabilities.payload)
    _require(
        type(choice_id) is str and bool(re.fullmatch(r"mode-[0-9a-f]{24}", choice_id)),
        "EXACT_MODE_CHOICE",
    )
    selected = next(
        (
            item
            for item in capabilities.view()["modes"]
            if item["choice_id"] == choice_id
        ),
        None,
    )
    _require(
        selected is not None and selected["selectable"],
        "UNKNOWN_OR_UNSUPPORTED_MODE_CHOICE",
    )
    assert selected is not None
    data = capabilities.to_dict()
    settings = _validate_settings(controls, _controls(data["controls"]))
    by_id = {item["control_id"]: item for item in data["controls"]}
    return {
        "schema": CONFIGURATION_SCHEMA,
        "provenance": PROVENANCE,
        "status": "STAGED_NOT_APPLIED_NATIVE",
        "capabilities_sha256": capabilities.capabilities_sha256,
        "binding": data["binding"],
        "mode_choice_id": choice_id,
        "mode": selected["mode"],
        "controls": [asdict(item) for item in settings],
        "control_capabilities": [by_id[item.control_id] for item in settings],
        "applied": False,
        "physical_authority": False,
        "hardware_qualified": False,
    }


@dataclass(frozen=True, slots=True)
class StagedPhysicalCameraConfiguration:
    payload: bytes

    def __post_init__(self) -> None:
        data = _exact(_load(self.payload), _CONFIG)
        _require(
            data["schema"] == CONFIGURATION_SCHEMA
            and data["status"] == "STAGED_NOT_APPLIED_NATIVE"
            and data["applied"] is False,
            "NATIVE_INTENT_ONLY",
        )
        _held(data)
        _binding(data["binding"])
        _sha(data["capabilities_sha256"])
        _require(
            type(data["mode_choice_id"]) is str
            and bool(re.fullmatch(r"mode-[0-9a-f]{24}", data["mode_choice_id"])),
            "EXACT_MODE_CHOICE",
        )
        _require(not _blockers(_mode(data["mode"])), "UNSUPPORTED_CAPTURE_MODE")
        reported = _controls(data["control_capabilities"])
        _require(
            type(data["controls"]) is list and len(data["controls"]) == len(reported),
            "REQUESTED_CONTROL_COUNT",
        )
        controls = tuple(
            CameraControlSetting(
                **_exact(item, {f.name for f in fields(CameraControlSetting)})
            )
            for item in data["controls"]
        )
        _require(
            _validate_settings(controls, reported) == controls
            and [c.control_id for c in controls] == [c.control_id for c in reported],
            "CANONICAL_CONTROL_ORDER",
        )

    def to_dict(self) -> dict[str, Any]:
        return _load(self.payload)

    @property
    def settings_epoch(self) -> str:
        return digest(self.payload)

    @property
    def mode(self) -> NativeCameraMode:
        return _mode(self.to_dict()["mode"])

    @property
    def controls(self) -> tuple[CameraControlSetting, ...]:
        return tuple(
            CameraControlSetting(**item) for item in self.to_dict()["controls"]
        )

    def view(self) -> dict[str, Any]:
        data = self.to_dict()
        del data["control_capabilities"]
        return {
            **data,
            "settings_epoch": self.settings_epoch,
            "meaning": intent_guidance(self.mode, self.controls),
        }


def stage_physical_camera_configuration(
    capabilities: PhysicalCameraCapabilities,
    mode_choice_id: str,
    controls: tuple[CameraControlSetting, ...],
    *,
    expected_capabilities_sha256: str,
    expected_source_sha256: str,
    expected_session_id: str,
    expected_selected_identity_sha256: str,
) -> StagedPhysicalCameraConfiguration:
    for sha in (
        expected_capabilities_sha256,
        expected_source_sha256,
        expected_selected_identity_sha256,
    ):
        _sha(sha)
    _require(
        type(capabilities) is PhysicalCameraCapabilities, "EXACT_NATIVE_CAPABILITIES"
    )
    checked = PhysicalCameraCapabilities(capabilities.payload)
    binding = checked.to_dict()["binding"]
    _require(
        checked.capabilities_sha256 == expected_capabilities_sha256
        and binding["source_sha256"] == expected_source_sha256
        and binding["session_id"] == expected_session_id
        and binding["selected_identity_sha256"] == expected_selected_identity_sha256,
        "STALE_NATIVE_CAPABILITIES",
    )
    return StagedPhysicalCameraConfiguration(
        canonical(_configuration(checked, mode_choice_id, controls))
    )


def verify_physical_camera_configuration(
    payload: bytes,
    *,
    expected_capabilities: PhysicalCameraCapabilities,
    expected_settings_epoch: str,
) -> StagedPhysicalCameraConfiguration:
    _sha(expected_settings_epoch)
    result = StagedPhysicalCameraConfiguration(payload)
    _require(
        result.settings_epoch == expected_settings_epoch,
        "SETTINGS_TRUSTED_HASH_MISMATCH",
    )
    expected = _configuration(
        expected_capabilities, result.to_dict()["mode_choice_id"], result.controls
    )
    _require(
        result.payload == canonical(expected), "CONFIGURATION_CAPABILITIES_MISMATCH"
    )
    return result


_READBACK = {
    "schema",
    "provenance",
    "status",
    "settings_epoch",
    "capabilities_sha256",
    "probe_binding",
    "capture_binding",
    "capture_preparation_sha256",
    "capture_evidence_sha256",
    "capture_request_sha256",
    "native_receipt_valid",
    "native_status",
    "native_requested_mode",
    "requested_mode",
    "observed_mode",
    "mode_matched",
    "controls",
    "reasons",
    "process_status",
    "process_cleanup_confirmed",
    "native_cleanup_confirmed",
    "frame_content_verified",
    "physical_authority",
    "hardware_qualified",
    "final_power_state",
}
_REQUEST_BINDING = _BINDING - {"probe_preparation_sha256", "probe_evidence_sha256"}


def _reasons(value: Any) -> None:
    _require(
        type(value) is list
        and len(value) <= 16
        and all(
            type(code) is str and bool(re.fullmatch(r"[A-Z_]{1,96}", code))
            for code in value
        )
        and len(set(value)) == len(value),
        "READBACK_REASONS",
    )


@dataclass(frozen=True, slots=True)
class PhysicalCameraReadback:
    """Comparison report only. Its verifier re-joins exact retained evidence."""

    payload: bytes

    def __post_init__(self) -> None:
        data = _exact(_load(self.payload), _READBACK)
        _require(data["schema"] == READBACK_SCHEMA, "PHYSICAL_READBACK_SCHEMA")
        _held(data)
        _binding(data["probe_binding"])
        _exact(data["capture_binding"], _REQUEST_BINDING)
        _binding(
            {
                **data["capture_binding"],
                "probe_preparation_sha256": data["probe_binding"][
                    "probe_preparation_sha256"
                ],
                "probe_evidence_sha256": data["probe_binding"]["probe_evidence_sha256"],
            }
        )
        for name in (
            "settings_epoch",
            "capabilities_sha256",
            "capture_preparation_sha256",
            "capture_evidence_sha256",
            "capture_request_sha256",
        ):
            _sha(data[name])
        for name in (
            "native_receipt_valid",
            "mode_matched",
            "process_cleanup_confirmed",
            "native_cleanup_confirmed",
        ):
            _require(type(data[name]) is bool, "READBACK_LITERAL_BOOL")
        _require(
            data["frame_content_verified"] is False
            and data["final_power_state"] == "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION",
            "READBACK_NO_PIXEL_OR_POWER_PROOF",
        )
        _require(
            (
                data["native_status"] is None
                or type(data["native_status"]) is str
                and data["native_status"] in {"OK", "FAILED"}
            )
            and data["native_receipt_valid"] == (data["native_status"] is not None),
            "READBACK_NATIVE_STATUS",
        )
        _require(
            type(data["process_status"]) is str
            and data["process_status"]
            in {
                "HELD",
                "CANCELLED",
                "TIMED_OUT",
                "FAILED",
                "SUCCEEDED_NATIVE_DIAGNOSTIC",
            },
            "READBACK_PROCESS_STATUS",
        )
        _mode(data["requested_mode"])
        for name in ("native_requested_mode", "observed_mode"):
            if data[name] is not None:
                _mode(data[name])
        _require(
            type(data["controls"]) is list and len(data["controls"]) <= 6,
            "READBACK_CONTROL_COUNT",
        )
        ids = []
        for row in data["controls"]:
            _exact(row, {"control_id", "requested", "observed", "matched", "reasons"})
            _exact(row["requested"], {"value", "mode"})
            CameraControlSetting(row["control_id"], **row["requested"])
            ids.append(row["control_id"])
            if row["observed"] is not None:
                _require(
                    _control(row["observed"]).control_id == row["control_id"],
                    "READBACK_CONTROL_ID",
                )
            _reasons(row["reasons"])
            _require(
                type(row["matched"]) is bool and row["matched"] == (not row["reasons"]),
                "READBACK_CONTROL_MATCH",
            )
        _require(ids == sorted(set(ids)), "READBACK_CONTROL_ORDER")
        _reasons(data["reasons"])
        _require(
            data["status"]
            == (
                "REQUESTED_SETTINGS_OBSERVED_UNQUALIFIED"
                if not data["reasons"]
                else "READBACK_MISMATCH_UNQUALIFIED"
            ),
            "READBACK_STATUS_DERIVATION",
        )

    def to_dict(self) -> dict[str, Any]:
        return _load(self.payload)

    @property
    def readback_sha256(self) -> str:
        return digest(self.payload)

    def view(self) -> dict[str, Any]:
        data = self.to_dict()
        return {
            **data,
            "readback_sha256": self.readback_sha256,
            "meaning": readback_guidance(
                None if data["observed_mode"] is None else _mode(data["observed_mode"]),
                data["controls"],
                matched=data["status"] == "REQUESTED_SETTINGS_OBSERVED_UNQUALIFIED",
            ),
        }


def compare_physical_camera_readback(
    configuration: StagedPhysicalCameraConfiguration,
    capture_evidence: (
        OwnedNativeCameraRunEvidence | tuple[CameraActivationArtifact, ...]
    ),
    *,
    expected_preparation: PreparedOwnedNativeCapture | PreparedOwnedNativeActivation,
    expected_capture_evidence_sha256: str,
    expected_settings_epoch: str,
    expected_supervision_sha256: str | None = None,
) -> PhysicalCameraReadback:
    _require(
        type(configuration) is StagedPhysicalCameraConfiguration
        and (
            type(expected_preparation) is PreparedOwnedNativeCapture
            or (
                type(expected_preparation) is PreparedOwnedNativeActivation
                and expected_preparation.admission_request.purpose == "capture"
            )
        ),
        "EXACT_NATIVE_READBACK_INPUTS",
    )
    _sha(expected_settings_epoch)
    config = StagedPhysicalCameraConfiguration(configuration.payload)
    _require(
        config.settings_epoch == expected_settings_epoch, "STALE_NATIVE_SETTINGS_EPOCH"
    )
    prepared = type(expected_preparation)(expected_preparation.payload)
    checked = _verified_observation(
        capture_evidence,
        prepared=prepared,
        expected_evidence_sha256=expected_capture_evidence_sha256,
        expected_supervision_sha256=expected_supervision_sha256,
    )
    intent, request = (
        config.to_dict(),
        prepared.admission_request.to_dict(),
    )
    # These join unit and reviewed source context, not helper identity. Probe and
    # capture intentionally use separate binaries; their pair review is external.
    for key in (
        "session_id",
        "source_sha256",
        "selected_identity_sha256",
        "endpoint_sha256",
    ):
        _require(
            request[key] == intent["binding"][key],
            "CAPTURE_CONFIGURATION_CONTEXT_MISMATCH",
        )
    native_request = prepared.camera_plan.request
    _require(
        native_request.mode == config.mode
        and native_request.controls == config.controls,
        "CAPTURE_REQUESTED_SETTINGS_MISMATCH",
    )
    receipt = checked.native_receipt
    reasons = []
    process_cleanup = checked.process_cleanup_confirmed
    native_cleanup = receipt is not None and receipt.cleanup_confirmed is True
    if checked.status != "SUCCEEDED_NATIVE_DIAGNOSTIC":
        reasons.append("CAPTURE_CAMPAIGN_NOT_SUCCESSFUL")
    if not process_cleanup:
        reasons.append("PROCESS_CLEANUP_UNCONFIRMED")
    if receipt is None:
        reasons.append("NATIVE_RECEIPT_UNAVAILABLE")
    elif receipt.status != "OK":
        reasons.append("NATIVE_CAPTURE_FAILED")
    if not native_cleanup:
        reasons.append("NATIVE_CLEANUP_UNCONFIRMED")
    mode_match = (
        receipt is not None
        and receipt.requested_mode == config.mode
        and receipt.observed_mode is not None
    )
    if mode_match:
        assert receipt is not None and receipt.observed_mode is not None
        mode_match = config.mode.same_format(receipt.observed_mode)
        if config.mode.stride_bytes is not None:
            mode_match = (
                mode_match
                and receipt.observed_mode.stride_bytes == config.mode.stride_bytes
                and all(
                    frame.stride_bytes == config.mode.stride_bytes
                    for frame in receipt.frames
                )
            )
    if not mode_match:
        reasons.append("MODE_READBACK_MISMATCH")
    actual_by_id = (
        {} if receipt is None else {item.control_id: item for item in receipt.controls}
    )
    rows = []
    for setting, pinned in zip(config.controls, intent["control_capabilities"]):
        actual = actual_by_id.get(setting.control_id)
        failures = []
        if actual is None:
            failures.append("CONTROL_READBACK_MISSING")
        else:
            if actual.flags != (1 if setting.mode == "auto" else 2):
                failures.append("CONTROL_MODE_READBACK_MISMATCH")
            if setting.mode == "manual" and actual.value != setting.value:
                failures.append("MANUAL_VALUE_READBACK_MISMATCH")
            if any(getattr(actual, key) != pinned[key] for key in _RANGE_FIELDS):
                failures.append("CONTROL_CAPABILITY_DRIFT")
        rows.append(
            {
                "control_id": setting.control_id,
                "requested": {"value": setting.value, "mode": setting.mode},
                "observed": None if actual is None else asdict(actual),
                "matched": not failures,
                "reasons": failures,
            }
        )
    if any(not row["matched"] for row in rows):
        reasons.append("CONTROL_READBACK_MISMATCH")
    return PhysicalCameraReadback(
        canonical(
            {
                "schema": READBACK_SCHEMA,
                "provenance": PROVENANCE,
                "status": (
                    "READBACK_MISMATCH_UNQUALIFIED"
                    if reasons
                    else "REQUESTED_SETTINGS_OBSERVED_UNQUALIFIED"
                ),
                "settings_epoch": config.settings_epoch,
                "capabilities_sha256": intent["capabilities_sha256"],
                "probe_binding": intent["binding"],
                "capture_binding": {key: request[key] for key in _REQUEST_BINDING},
                "capture_preparation_sha256": prepared.preparation_sha256,
                "capture_evidence_sha256": checked.evidence_sha256,
                "capture_request_sha256": prepared.admission_request.request_sha256,
                "native_receipt_valid": receipt is not None,
                "native_status": None if receipt is None else receipt.status,
                "native_requested_mode": (
                    None
                    if receipt is None or receipt.requested_mode is None
                    else asdict(receipt.requested_mode)
                ),
                "requested_mode": asdict(config.mode),
                "observed_mode": (
                    None
                    if receipt is None or receipt.observed_mode is None
                    else asdict(receipt.observed_mode)
                ),
                "mode_matched": mode_match,
                "controls": rows,
                "reasons": reasons,
                "process_status": checked.status,
                "process_cleanup_confirmed": process_cleanup,
                "native_cleanup_confirmed": native_cleanup,
                "frame_content_verified": False,
                "physical_authority": False,
                "hardware_qualified": False,
                "final_power_state": "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION",
            }
        )
    )


def verify_physical_camera_readback(
    payload: bytes,
    *,
    configuration: StagedPhysicalCameraConfiguration,
    capture_evidence: (
        OwnedNativeCameraRunEvidence | tuple[CameraActivationArtifact, ...]
    ),
    expected_preparation: PreparedOwnedNativeCapture | PreparedOwnedNativeActivation,
    expected_capture_evidence_sha256: str,
    expected_settings_epoch: str,
    expected_readback_sha256: str,
    expected_supervision_sha256: str | None = None,
) -> PhysicalCameraReadback:
    _sha(expected_readback_sha256)
    result = PhysicalCameraReadback(payload)
    _require(
        result.readback_sha256 == expected_readback_sha256,
        "READBACK_TRUSTED_HASH_MISMATCH",
    )
    expected = compare_physical_camera_readback(
        configuration,
        capture_evidence,
        expected_preparation=expected_preparation,
        expected_capture_evidence_sha256=expected_capture_evidence_sha256,
        expected_settings_epoch=expected_settings_epoch,
        expected_supervision_sha256=expected_supervision_sha256,
    )
    _require(result.payload == expected.payload, "READBACK_RETAINED_EVIDENCE_MISMATCH")
    return result
