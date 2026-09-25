"""Immutable B0477 operating intent; never an approved profile or device permit.

The owner supplies independently checked context and original bytes. These pure
codecs compare that context but cannot authenticate storage, currentness or people.
Historical entry identity is deliberately not equated with fresh probe selection.
"""

from dataclasses import asdict, dataclass
import re
from typing import Any

from rocell.providers.windows.camera_worker_client import (
    NativeCameraMode,
    CameraWorkerError,
)
from rocell.providers.windows.owned_worker_process import decode_owned_json
from rocell.providers.windows.usb_identity_protocol import canonical, digest
from rocell.vision.camera_profile import parse_camera_profile_json

from .physical_camera_configuration import (
    StagedPhysicalCameraConfiguration,
    _binding as _validate_probe_binding,
)
from .physical_camera_mode_entry import (
    _binding as _validate_entry_binding,
    camera_mode_operator_valid,
    verify_camera_mode_entry,
)

SCHEMA = "rocell.camera_operating_proposal.v1"
MAX_BYTES = 24 * 1024
REQUIRED_MANUAL_CONTROLS = ("exposure", "white_balance")
REFERENCE_MODE = NativeCameraMode(5472, 3648, 9, 1)
VARIANCE_MODE = NativeCameraMode(5472, 3648, 8, 1)
FALSE_FIELDS = (
    "approved_operating_policy",
    "original_store_authenticated",
    "authenticated_operator_identity",
    "stage_passed",
    "physical_authority",
    "hardware_qualified",
    "camera_capture_authorized",
    "arm_access_authorized",
    "device_io_performed",
    "automatic_fallback",
)
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"modepolicy-[0-9a-f]{32}\Z")
_SUBJECTS = {
    "entry_sha256",
    "purchase_file_sha256",
    "purchase_canonical_sha256",
    "settings_epoch",
    "capabilities_sha256",
}
_FIELDS = {
    "schema",
    "state",
    "proposal_id",
    "operator_id",
    "recorded_at_utc_ns",
    "rationale",
    "variance_rationale",
    "policy_kind",
    "target_mode",
    "reference_mode",
    "required_manual_controls",
    "subjects",
    "entry_binding",
    "probe_binding",
    *FALSE_FIELDS,
}


class CameraOperatingProposalError(ValueError):
    """Closed error: no operator labels or original device paths in diagnostics."""

    def __init__(self) -> None:
        super().__init__("CAMERA_OPERATING_PROPOSAL_INVALID")


def _need(condition: bool) -> None:
    if not condition:
        raise CameraOperatingProposalError()


def _sha(value: Any) -> None:
    _need(
        type(value) is str and _HASH.fullmatch(value) is not None and value != "0" * 64
    )


def _text(value: Any) -> None:
    _need(type(value) is str and 0 < len(value) <= 1024 and value == value.strip())
    _need(not any(ord(c) < 32 or ord(c) == 127 for c in value))
    _need(len(value.encode("utf-8")) <= 1024)


def _kind(mode: NativeCameraMode) -> str:
    if mode.same_format(REFERENCE_MODE):
        return "REFERENCE_9_FPS_PROPOSAL"
    _need(mode.same_format(VARIANCE_MODE))
    return "EXPLICIT_8_FPS_VARIANCE_PROPOSAL"


def _document(payload: bytes) -> dict[str, Any]:
    try:
        value = decode_owned_json(payload, maximum=MAX_BYTES)
        _need(set(value) == _FIELDS and canonical(value) == payload)
        _need(value["schema"] == SCHEMA and value["state"] == "PROPOSED_NOT_REVIEWED")
        _need(all(value[key] is False for key in FALSE_FIELDS))
        _need(
            type(value["proposal_id"]) is str
            and _ID.fullmatch(value["proposal_id"]) is not None
        )
        _need(camera_mode_operator_valid(value["operator_id"]))
        when = value["recorded_at_utc_ns"]
        _need(type(when) is int and 0 < when < 2**63)
        _text(value["rationale"])
        _need(
            type(value["target_mode"]) is dict
            and set(value["target_mode"]) == set(asdict(REFERENCE_MODE))
        )
        kind = _kind(NativeCameraMode(**value["target_mode"]))
        _need(value["policy_kind"] == kind)
        if kind == "EXPLICIT_8_FPS_VARIANCE_PROPOSAL":
            _text(value["variance_rationale"])
        else:
            _need(value["variance_rationale"] is None)
        _need(canonical(value["reference_mode"]) == canonical(asdict(REFERENCE_MODE)))
        _need(value["required_manual_controls"] == list(REQUIRED_MANUAL_CONTROLS))
        _need(type(value["subjects"]) is dict and set(value["subjects"]) == _SUBJECTS)
        for subject in value["subjects"].values():
            _sha(subject)
        # Reuse the existing exact binding codecs rather than maintaining a
        # second list of their IDs/hash rules. Shape checks are not provenance.
        _validate_entry_binding(value["entry_binding"])
        _validate_probe_binding(value["probe_binding"])
        for key in ("source_sha256", "session_id"):
            _need(value["entry_binding"][key] == value["probe_binding"][key])
        return value
    except CameraOperatingProposalError:
        raise
    except (
        ValueError,
        TypeError,
        KeyError,
        RecursionError,
        UnicodeError,
        CameraWorkerError,
    ) as exc:
        raise CameraOperatingProposalError() from exc


@dataclass(frozen=True, slots=True)
class CameraOperatingProposal:
    """Structurally valid data only; use the verifier for independent joins."""

    payload: bytes

    def __post_init__(self) -> None:
        _document(self.payload)

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _document(self.payload)


def build_camera_operating_proposal(
    *,
    proposal_id: str,
    operator_id: str,
    recorded_at_utc_ns: int,
    rationale: str,
    variance_rationale: str | None,
    entry_payload: bytes,
    expected_entry_id: str,
    expected_entry_binding: dict[str, str],
    purchase_profile_payload: bytes,
    expected_purchase_profile_sha256: str,
    configuration_payload: bytes,
    expected_settings_epoch: str,
) -> CameraOperatingProposal:
    """Propose the exact staged mode; never choose a mode or change settings.

    Configuration parsing is not native-evidence verification. The subsequent
    preflight re-derives it from the original probe/capture subjects.
    """
    try:
        entry = verify_camera_mode_entry(
            entry_payload,
            expected_entry_id=expected_entry_id,
            expected_binding=expected_entry_binding,
        )
        _sha(expected_purchase_profile_sha256)
        profile = parse_camera_profile_json(purchase_profile_payload)
        _need(profile.source_file_sha256 == expected_purchase_profile_sha256)
        _sha(expected_settings_epoch)
        config = StagedPhysicalCameraConfiguration(configuration_payload)
        _need(config.settings_epoch == expected_settings_epoch)
        probe_binding = config.to_dict()["binding"]
        for key in ("source_sha256", "session_id"):
            _need(probe_binding[key] == expected_entry_binding[key])
        kind = _kind(config.mode)
        # No disk reads or mutation of the strict purchase record. Its parser
        # validates the known B0477 reference; the variant lives only here.
        return CameraOperatingProposal(
            canonical(
                dict(
                    schema=SCHEMA,
                    state="PROPOSED_NOT_REVIEWED",
                    proposal_id=proposal_id,
                    operator_id=operator_id,
                    recorded_at_utc_ns=recorded_at_utc_ns,
                    rationale=rationale,
                    variance_rationale=variance_rationale,
                    policy_kind=kind,
                    target_mode=asdict(config.mode),
                    reference_mode=asdict(REFERENCE_MODE),
                    required_manual_controls=list(REQUIRED_MANUAL_CONTROLS),
                    subjects=dict(
                        entry_sha256=entry.sha256,
                        purchase_file_sha256=profile.source_file_sha256,
                        purchase_canonical_sha256=profile.canonical_sha256,
                        settings_epoch=config.settings_epoch,
                        capabilities_sha256=config.to_dict()["capabilities_sha256"],
                    ),
                    entry_binding=entry.to_dict()["binding"],
                    probe_binding=probe_binding,
                    **{key: False for key in FALSE_FIELDS},
                )
            )
        )
    except CameraOperatingProposalError:
        raise
    except (
        ValueError,
        TypeError,
        KeyError,
        RecursionError,
        UnicodeError,
        CameraWorkerError,
    ) as exc:
        raise CameraOperatingProposalError() from exc


def verify_camera_operating_proposal(
    payload: bytes,
    *,
    expected_proposal_sha256: str,
    entry_payload: bytes,
    expected_entry_id: str,
    expected_entry_binding: dict[str, str],
    purchase_profile_payload: bytes,
    expected_purchase_profile_sha256: str,
    configuration_payload: bytes,
    expected_settings_epoch: str,
) -> CameraOperatingProposal:
    """Rebuild from independently supplied subjects, never from stored bindings."""
    _sha(expected_proposal_sha256)
    result = CameraOperatingProposal(payload)
    _need(result.sha256 == expected_proposal_sha256)
    data = result.to_dict()
    rebuilt = build_camera_operating_proposal(
        **{
            key: data[key]
            for key in (
                "proposal_id",
                "operator_id",
                "recorded_at_utc_ns",
                "rationale",
                "variance_rationale",
            )
        },
        entry_payload=entry_payload,
        expected_entry_id=expected_entry_id,
        expected_entry_binding=expected_entry_binding,
        purchase_profile_payload=purchase_profile_payload,
        expected_purchase_profile_sha256=expected_purchase_profile_sha256,
        configuration_payload=configuration_payload,
        expected_settings_epoch=expected_settings_epoch,
    )
    _need(rebuilt.payload == payload)
    return result
