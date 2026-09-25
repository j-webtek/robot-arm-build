"""Pure, bounded stage-5 metadata checks, not original-store acceptance.

Each readback is re-derived from native evidence, not trusted because its status
looks successful. At most two captures are considered. No files are opened, no
settings are applied, and even consistent metadata leaves physical approval held.
"""

from dataclasses import dataclass
from typing import Any

from rocell.providers.windows.camera_worker_client import NativeCameraMode
from rocell.providers.windows.native_camera_activation_registration import (
    PreparedOwnedNativeActivation,
)
from rocell.providers.windows.native_camera_capture_registration import (
    PreparedOwnedNativeCapture,
)
from rocell.providers.windows.native_camera_registration import PreparedOwnedNativeProbe
from rocell.providers.windows.owned_native_camera_evidence import (
    OwnedNativeCameraRunEvidence,
)
from rocell.providers.windows.owned_worker_process import decode_owned_json
from rocell.providers.windows.usb_identity_protocol import canonical, digest

from .camera_activation_campaign_evidence import CameraActivationArtifact
from .camera_operating_proposal import (
    FALSE_FIELDS,
    REQUIRED_MANUAL_CONTROLS,
    verify_camera_operating_proposal,
)
from .physical_camera_configuration import (
    verify_physical_camera_capabilities,
    verify_physical_camera_configuration,
    verify_physical_camera_readback,
)

SCHEMA = "rocell.camera_operating_evidence_preflight.v1"
MAX_BYTES = 16 * 1024
CHECK_IDS = (
    "REQUIRED_CONTROLS_SELECTED_MANUAL",
    "TWO_CAPTURE_REPORTS_PRESENT",
    "DISTINCT_PROBE_AND_CAPTURE_ATTEMPTS",
    "BOTH_READBACKS_MATCH_AND_CLEANUP_CONFIRMED",
    "REPEATED_OBSERVED_FORMAT_AND_LAYOUT",
    "SAME_CAPTURE_RUNTIME",
)
OWNER_OBLIGATIONS = (
    "ORIGINAL_STORE_AND_CURRENTNESS_NOT_AUTHENTICATED",
    "USB_SPEED_AND_IDENTITY_CONTINUITY_NOT_ASSESSED",
    "ORDERED_CLOSE_REOPEN_NOT_AUTHENTICATED",
    "PIXEL_FILES_NOT_VERIFIED",
    "FRAME_FRESHNESS_NOT_ASSESSED",
    "SEPARATE_OPERATOR_REVIEW_NOT_RECORDED",
    "INSTALLED_OPTICS_AND_CALIBRATION_DEFERRED",
)
_FIELDS = {
    "schema",
    "status",
    "proposal_sha256",
    "capabilities_sha256",
    "settings_epoch",
    "probe",
    "captures",
    "checks",
    "failed_checks",
    "owner_obligations",
    *FALSE_FIELDS,
}
_NATIVE_REFS = {"preparation_sha256", "evidence_sha256", "supervision_sha256"}


class CameraOperatingPreflightError(ValueError):
    def __init__(self) -> None:
        super().__init__("CAMERA_OPERATING_EVIDENCE_PREFLIGHT_INVALID")


def _need(condition: bool) -> None:
    if not condition:
        raise CameraOperatingPreflightError()


def _sha(value: Any) -> None:
    _need(
        type(value) is str
        and len(value) == 64
        and all(c in "0123456789abcdef" for c in value)
        and value != "0" * 64
    )


@dataclass(frozen=True, slots=True)
class CameraNativeEvidenceSubject:
    """An untrusted input bundle, not an original-store authentication token.

    Expected digests must come from the owner's independently verified originals.
    V2 requires both run and supervision hashes; the existing verifier enforces
    exact observation domains and rejects substitution or partial pairs.
    """

    preparation: (
        PreparedOwnedNativeProbe
        | PreparedOwnedNativeCapture
        | PreparedOwnedNativeActivation
    )
    evidence: OwnedNativeCameraRunEvidence | tuple[CameraActivationArtifact, ...]
    expected_evidence_sha256: str
    expected_supervision_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class CameraReadbackSubject:
    native: CameraNativeEvidenceSubject
    readback_payload: bytes
    expected_readback_sha256: str


def _native_refs(subject: CameraNativeEvidenceSubject) -> dict[str, Any]:
    _need(type(subject) is CameraNativeEvidenceSubject)
    _need(
        type(subject.preparation)
        in (
            PreparedOwnedNativeProbe,
            PreparedOwnedNativeCapture,
            PreparedOwnedNativeActivation,
        )
    )
    _sha(subject.expected_evidence_sha256)
    if subject.expected_supervision_sha256 is not None:
        _sha(subject.expected_supervision_sha256)
    return dict(
        preparation_sha256=subject.preparation.preparation_sha256,
        evidence_sha256=subject.expected_evidence_sha256,
        supervision_sha256=subject.expected_supervision_sha256,
    )


def _status(failed: list[str]) -> str:
    return (
        "BLOCKED_METADATA" if failed else "CONSISTENT_METADATA_PENDING_ORIGINAL_REVIEW"
    )


def _document(payload: bytes) -> dict[str, Any]:
    try:
        value = decode_owned_json(payload, maximum=MAX_BYTES)
        _need(set(value) == _FIELDS and canonical(value) == payload)
        _need(
            value["schema"] == SCHEMA and all(value[k] is False for k in FALSE_FIELDS)
        )
        for key in ("proposal_sha256", "capabilities_sha256", "settings_epoch"):
            _sha(value[key])
        _need(type(value["captures"]) is list and len(value["captures"]) <= 2)
        for refs, fields in [(value["probe"], _NATIVE_REFS)] + [
            (capture, _NATIVE_REFS | {"readback_sha256"})
            for capture in value["captures"]
        ]:
            _need(type(refs) is dict and set(refs) == fields)
            for key, item in refs.items():
                if key != "supervision_sha256" or item is not None:
                    _sha(item)
        checks = value["checks"]
        _need(type(checks) is list and len(checks) == len(CHECK_IDS))
        for check, check_id in zip(checks, CHECK_IDS):
            _need(type(check) is dict and set(check) == {"id", "satisfied"})
            _need(check["id"] == check_id and type(check["satisfied"]) is bool)
        failed = [check["id"] for check in checks if not check["satisfied"]]
        _need(value["failed_checks"] == failed and value["status"] == _status(failed))
        _need(value["owner_obligations"] == list(OWNER_OBLIGATIONS))
        return value
    except CameraOperatingPreflightError:
        raise
    except (ValueError, TypeError, KeyError, RecursionError, UnicodeError) as exc:
        raise CameraOperatingPreflightError() from exc


@dataclass(frozen=True, slots=True)
class CameraOperatingEvidencePreflight:
    """Parsed comparison data. Verification must re-derive every check."""

    payload: bytes

    def __post_init__(self) -> None:
        _document(self.payload)

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _document(self.payload)


def assess_camera_operating_evidence(
    *,
    proposal_payload: bytes,
    expected_proposal_sha256: str,
    entry_payload: bytes,
    expected_entry_id: str,
    expected_entry_binding: dict[str, str],
    purchase_profile_payload: bytes,
    expected_purchase_profile_sha256: str,
    capabilities_payload: bytes,
    expected_capabilities_sha256: str,
    configuration_payload: bytes,
    expected_settings_epoch: str,
    probe: CameraNativeEvidenceSubject,
    captures: tuple[CameraReadbackSubject, ...],
) -> CameraOperatingEvidencePreflight:
    """Re-derive originals supplied by the owner and report missing metadata.

    Invalid/misbound evidence raises a closed error. Valid but unsuccessful or
    incomplete observations produce failed checks. A caller cannot supply an
    `approved` boolean, substitute guidance text, or upgrade a failed capture.
    """
    try:
        _need(type(captures) is tuple and len(captures) <= 2)
        proposal = verify_camera_operating_proposal(
            proposal_payload,
            expected_proposal_sha256=expected_proposal_sha256,
            entry_payload=entry_payload,
            expected_entry_id=expected_entry_id,
            expected_entry_binding=expected_entry_binding,
            purchase_profile_payload=purchase_profile_payload,
            expected_purchase_profile_sha256=expected_purchase_profile_sha256,
            configuration_payload=configuration_payload,
            expected_settings_epoch=expected_settings_epoch,
        )
        probe_refs = _native_refs(probe)
        if not isinstance(
            probe.preparation, (PreparedOwnedNativeProbe, PreparedOwnedNativeActivation)
        ):
            raise CameraOperatingPreflightError()
        caps = verify_physical_camera_capabilities(
            capabilities_payload,
            evidence=probe.evidence,
            expected_preparation=probe.preparation,
            expected_evidence_sha256=probe.expected_evidence_sha256,
            expected_supervision_sha256=probe.expected_supervision_sha256,
            expected_source_sha256=expected_entry_binding["source_sha256"],
            expected_capabilities_sha256=expected_capabilities_sha256,
        )
        config = verify_physical_camera_configuration(
            configuration_payload,
            expected_capabilities=caps,
            expected_settings_epoch=expected_settings_epoch,
        )
        readbacks, capture_refs = [], []
        for capture in captures:
            _need(type(capture) is CameraReadbackSubject)
            refs = _native_refs(capture.native)
            if not isinstance(
                capture.native.preparation,
                (PreparedOwnedNativeCapture, PreparedOwnedNativeActivation),
            ):
                raise CameraOperatingPreflightError()
            checked = verify_physical_camera_readback(
                capture.readback_payload,
                configuration=config,
                capture_evidence=capture.native.evidence,
                expected_preparation=capture.native.preparation,
                expected_capture_evidence_sha256=capture.native.expected_evidence_sha256,
                expected_supervision_sha256=capture.native.expected_supervision_sha256,
                expected_settings_epoch=expected_settings_epoch,
                expected_readback_sha256=capture.expected_readback_sha256,
            )
            readbacks.append(checked.to_dict())
            capture_refs.append({**refs, "readback_sha256": checked.readback_sha256})

        manual_ids = {
            item.control_id for item in config.controls if item.mode == "manual"
        }
        two = len(readbacks) == 2
        bindings = [caps.to_dict()["binding"]] + [
            r["capture_binding"] for r in readbacks
        ]
        all_refs = [probe_refs, *capture_refs]
        # Different IDs are necessary, not proof of temporal order or reopening.
        distinct = (
            two
            and all(
                len({b[key] for b in bindings}) == 3
                for key in ("attempt_id", "permit_sha256")
            )
            and all(
                len({r[key] for r in all_refs}) == 3
                for key in ("preparation_sha256", "evidence_sha256")
            )
        )
        closed = two and all(
            r["status"] == "REQUESTED_SETTINGS_OBSERVED_UNQUALIFIED"
            and r["native_receipt_valid"] is True
            and r["native_status"] == "OK"
            and r["mode_matched"] is True
            and r["process_cleanup_confirmed"] is True
            and r["native_cleanup_confirmed"] is True
            and not r["reasons"]
            for r in readbacks
        )
        modes = [
            (
                None
                if r["observed_mode"] is None
                else NativeCameraMode(**r["observed_mode"])
            )
            for r in readbacks
        ]
        layout = False
        if two and modes[0] is not None and modes[1] is not None:
            layout = (
                modes[0].same_format(modes[1])
                and modes[0].stride_bytes is not None
                and modes[0].stride_bytes == modes[1].stride_bytes
            )
        runtime = two and all(
            readbacks[0]["capture_binding"][key] == readbacks[1]["capture_binding"][key]
            for key in ("helper_sha256", "runtime_registration_sha256")
        )
        results = (
            set(REQUIRED_MANUAL_CONTROLS) <= manual_ids,
            two,
            distinct,
            closed,
            layout,
            runtime,
        )
        checks = [dict(id=key, satisfied=ok) for key, ok in zip(CHECK_IDS, results)]
        failed = [key for key, ok in zip(CHECK_IDS, results) if not ok]
        return CameraOperatingEvidencePreflight(
            canonical(
                dict(
                    schema=SCHEMA,
                    status=_status(failed),
                    proposal_sha256=proposal.sha256,
                    capabilities_sha256=caps.capabilities_sha256,
                    settings_epoch=config.settings_epoch,
                    probe=probe_refs,
                    captures=capture_refs,
                    checks=checks,
                    failed_checks=failed,
                    owner_obligations=list(OWNER_OBLIGATIONS),
                    **{key: False for key in FALSE_FIELDS},
                )
            )
        )
    except CameraOperatingPreflightError:
        raise
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        RecursionError,
        UnicodeError,
    ) as exc:
        raise CameraOperatingPreflightError() from exc


def verify_camera_operating_evidence_preflight(
    payload: bytes, *, expected_preflight_sha256: str, **original_inputs: Any
) -> CameraOperatingEvidencePreflight:
    """Recompute with the same explicitly named inputs as the assessor.

    Hash equality alone is insufficient. No retained checks, bindings or flags
    are used as the inputs to reconstruction. Unknown input names are rejected.
    """
    _sha(expected_preflight_sha256)
    result = CameraOperatingEvidencePreflight(payload)
    _need(result.sha256 == expected_preflight_sha256)
    try:
        rebuilt = assess_camera_operating_evidence(**original_inputs)
    except TypeError as exc:
        raise CameraOperatingPreflightError() from exc
    _need(rebuilt.payload == payload)
    return result
