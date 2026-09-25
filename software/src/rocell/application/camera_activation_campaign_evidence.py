"""Closed camera-v2 evidence pair, separate from legacy campaign byte limits.

These private bytes are not authority, original-store provenance or a stage
decision. Cross-checking preserves a failed run; it does not require a complete
native result or synthesize missing counters. No file/device/process I/O occurs.
"""

from dataclasses import dataclass
import re
from types import MappingProxyType

from rocell.providers.windows.native_camera_activation_evidence import (
    MAX_EVIDENCE_BYTES,
    SCHEMA as RUN_SCHEMA,
    OwnedNativeCameraActivationRunEvidence,
)
from rocell.providers.windows.native_camera_activation_observations import (
    ActivationOwnerObservation,
)
from rocell.providers.windows.native_camera_activation_registration import (
    PreparedOwnedNativeActivation,
)
from rocell.providers.windows.native_camera_activation_supervisor import (
    ActivationSupervision,
    MAX_SUPERVISION_BYTES,
    SUPERVISION_SCHEMA,
)
from rocell.providers.windows.native_camera_protocol import canonical, digest, _require
from rocell.providers.windows.owned_worker_process import (
    decode_owned_json,
    owned_registration_document,
)

ROLES = ("run", "supervision")
ROLE_SCHEMAS = MappingProxyType({"run": RUN_SCHEMA, "supervision": SUPERVISION_SCHEMA})
ROLE_LIMITS = MappingProxyType(
    {"run": MAX_EVIDENCE_BYTES, "supervision": MAX_SUPERVISION_BYTES}
)
MAX_CAMERA_ACTIVATION_CAMPAIGN_BYTES = MAX_EVIDENCE_BYTES + MAX_SUPERVISION_BYTES
_ERROR = re.compile(r"[A-Za-z0-9_:-]{1,192}\Z")
_COMMON = (
    "preparation_sha256",
    "owner_constructed",
    "started_ns",
    "finished_ns",
    "parent_deadline_ns",
    "primary_error",
    "cleanup",
    "ready_wire",
    "release_wire",
    "release_check_passed",
    "accepted_result_sha256",
    "physical_authority",
    "hardware_qualified",
)
_DETAIL_FIELDS = set(_COMMON) | {
    "schema",
    "actual_registration",
    "before_cleanup",
    "after_cleanup",
    "supervisor_errors",
    "unresolved_owner_retained",
}


@dataclass(frozen=True, slots=True)
class CameraActivationArtifact:
    """Closed role and finite bytes; not accepted by the legacy evidence validator."""

    role: str
    payload: bytes

    def __post_init__(self) -> None:
        _require(type(self.role) is str and self.role in ROLES, "CAMERA_ARTIFACT_ROLE")
        _require(
            type(self.payload) is bytes
            and 0 < len(self.payload) <= ROLE_LIMITS[self.role],
            "CAMERA_ARTIFACT_BYTE_LIMIT",
        )

    @property
    def label(self) -> str:
        return "camera-activation-" + self.role + "-v2"

    @property
    def schema(self) -> str:
        return ROLE_SCHEMAS[self.role]

    @property
    def payload_sha256(self) -> str:
        return digest(self.payload)


@dataclass(frozen=True, slots=True)
class ValidatedCameraActivationEvidence:
    run: OwnedNativeCameraActivationRunEvidence
    supervision_payload: bytes

    @property
    def prepared(self) -> PreparedOwnedNativeActivation:
        return PreparedOwnedNativeActivation(
            canonical(self.run.to_dict()["preparation"])
        )


def validate_camera_activation_evidence(
    artifacts: tuple[CameraActivationArtifact, ...],
) -> ValidatedCameraActivationEvidence:
    """Verify the complete ordered pair, including failures and unknown facts.

    The before-cleanup observation remains an independent diagnostic snapshot;
    do not replace missing post-cleanup observations with its older values.
    """
    _require(
        type(artifacts) is tuple
        and len(artifacts) == 2
        and all(type(item) is CameraActivationArtifact for item in artifacts),
        "EXACT_CAMERA_ARTIFACT_PAIR",
    )
    for artifact in artifacts:
        artifact.__post_init__()
    _require(
        tuple(item.role for item in artifacts) == ROLES, "ORDERED_CAMERA_ARTIFACT_PAIR"
    )
    _require(
        sum(len(item.payload) for item in artifacts)
        <= MAX_CAMERA_ACTIVATION_CAMPAIGN_BYTES,
        "CAMERA_ARTIFACT_TOTAL_LIMIT",
    )
    run = OwnedNativeCameraActivationRunEvidence(artifacts[0].payload)
    data = run.to_dict()
    prepared = PreparedOwnedNativeActivation(canonical(data["preparation"]))
    detail = decode_owned_json(artifacts[1].payload, maximum=MAX_SUPERVISION_BYTES)
    _require(
        canonical(detail) == artifacts[1].payload
        and set(detail) == _DETAIL_FIELDS
        and detail["schema"] == SUPERVISION_SCHEMA,
        "CAMERA_SUPERVISION_CLOSED_SCHEMA",
    )
    # Canonical comparisons distinguish literal Booleans from 0/1 as well as
    # binding every shared value. A matching hash alone is not enough.
    _require(
        all(canonical(detail[key]) == canonical(data[key]) for key in _COMMON)
        and canonical(detail["after_cleanup"]) == canonical(data["owner_observation"])
        and canonical(detail["actual_registration"])
        == canonical(owned_registration_document(prepared.registration)),
        "CAMERA_SUPERVISION_RUN_BINDING",
    )
    errors = detail["supervisor_errors"]
    _require(
        type(errors) is list
        and len(errors) <= 16
        and all(type(code) is str and bool(_ERROR.fullmatch(code)) for code in errors)
        and (not errors or detail["primary_error"] is not None),
        "CAMERA_SUPERVISOR_ERROR_FIELDS",
    )
    retained = detail["unresolved_owner_retained"]
    _require(
        type(retained) is bool and (not retained or data["owner_constructed"]),
        "CAMERA_SUPERVISOR_OWNER_RETENTION",
    )
    if retained:
        _require(
            run.assessment().status != "SUCCEEDED_NATIVE_DIAGNOSTIC",
            "CAMERA_RETAINED_OWNER_NOT_SUCCESS",
        )
    before = detail["before_cleanup"]
    if before is None:
        _require(
            not data["owner_constructed"]
            or any(code.startswith("BEFORE_CLEANUP:") for code in errors),
            "CAMERA_BEFORE_OBSERVATION_AVAILABILITY",
        )
    else:
        _require(data["owner_constructed"], "CAMERA_BEFORE_OBSERVATION_WITHOUT_OWNER")
        observed = ActivationOwnerObservation(canonical(before)).to_dict()
        budget = prepared.registration.budget
        _require(
            observed["stdout_limit"] == budget.stdout_bytes
            and observed["stderr_limit"] == budget.stderr_bytes,
            "CAMERA_BEFORE_OBSERVATION_BUDGET",
        )
    if detail["after_cleanup"] is None and data["owner_constructed"]:
        _require(
            any(code.startswith("AFTER_CLEANUP:") for code in errors),
            "CAMERA_AFTER_OBSERVATION_AVAILABILITY",
        )
    return ValidatedCameraActivationEvidence(run, artifacts[1].payload)


def camera_activation_evidence(
    prepared: PreparedOwnedNativeActivation,
    supervision: ActivationSupervision,
) -> tuple[CameraActivationArtifact, ...]:
    """Build only from the typed supervisor, not a caller-authored status flag."""
    _require(
        type(supervision) is ActivationSupervision, "EXACT_CAMERA_SUPERVISION_REQUIRED"
    )
    run = supervision.run_evidence(prepared)
    pair = (
        CameraActivationArtifact("run", run.payload),
        CameraActivationArtifact("supervision", canonical(supervision.diagnostics())),
    )
    validate_camera_activation_evidence(pair)
    return pair
