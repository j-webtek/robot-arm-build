"""Strict, zero-authority physical-onboarding hazard register.

The register is a pre-hardware review artifact.  Loading it can describe open
hazards and the evidence needed to review them, but it cannot activate a
runtime, issue a permit, touch a device, or close a hazard.  The loader is
deliberately fail-closed: JSON structure, bounds, stage and configuration-epoch
references, file containment, and the absence of physical authority are all
checked before a value is returned.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import math
import os
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from rocell.application.physical_onboarding import PhysicalOnboardingStage


PHYSICAL_ONBOARDING_HAZARD_REGISTER_SCHEMA = (
    "rocell.physical_onboarding_hazard_register.v1"
)
# Plural aliases match the configuration filename and make the public boundary
# unsurprising to callers that treat this as a collection rather than a policy.
PHYSICAL_ONBOARDING_HAZARDS_SCHEMA = PHYSICAL_ONBOARDING_HAZARD_REGISTER_SCHEMA
DEFAULT_PHYSICAL_ONBOARDING_HAZARDS = Path(
    "software/config/physical_onboarding_hazards.json"
)
DEFAULT_PHYSICAL_ONBOARDING_HAZARD_REGISTER = DEFAULT_PHYSICAL_ONBOARDING_HAZARDS
MAX_PHYSICAL_ONBOARDING_HAZARD_BYTES = 256 * 1024
MAX_HAZARDS = 64
MAX_REFERENCES_PER_HAZARD = 32
MAX_CONTROLS_PER_HAZARD = 32
MAX_EVIDENCE_REQUIREMENTS_PER_HAZARD = 32

_HAZARD_ID = re.compile(r"HZ-[0-9]{3}\Z")
_ACTION_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,127}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
# The historical policy rejects C0 and DEL, not all Unicode control categories.
# Compile that exact scan; no register, file observation or decision is cached.
_TEXT_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_EXPECTED_HAZARD_IDS = tuple(f"HZ-{index:03d}" for index in range(1, 17))
_CANONICAL_LEASE_ORDER_CONTROL = (
    "Acquire leases only in canonical order CELL -> SESSION -> CAMERA -> "
    "ARM_CONTROLLER, with one mutable physical session per cell."
)
_EXPECTED_ROOT_FIELDS = frozenset(
    {
        "schema",
        "register_id",
        "revision",
        "status",
        "runtime_activation",
        "authority",
        "hazards",
    }
)
_EXPECTED_AUTHORITY_FIELDS = frozenset(
    {
        "planning_authority",
        "simulation_authority",
        "device_io_authorized",
        "robot_power_authorized",
        "motion_authorized",
        "contact_authorized",
        "build_promotion_authorized",
        "physical_release_effect",
    }
)
_EXPECTED_AUTHORITY = {
    "planning_authority": True,
    "simulation_authority": True,
    "device_io_authorized": False,
    "robot_power_authorized": False,
    "motion_authorized": False,
    "contact_authorized": False,
    "build_promotion_authorized": False,
    "physical_release_effect": "NONE",
}
_EXPECTED_HAZARD_FIELDS = frozenset(
    {
        "id",
        "title",
        "severity",
        "status",
        "evidence_stages",
        "invalidation_epochs",
        "controls",
        "required_evidence",
        "fail_safe",
        "residual_status",
    }
)


def _has_exact_typed_values(
    actual: Mapping[str, Any], expected: Mapping[str, object]
) -> bool:
    """Compare schema values without allowing ``0 == False`` or ``1 == True``."""

    return all(
        key in actual
        and type(actual[key]) is type(expected_value)
        and actual[key] == expected_value
        for key, expected_value in expected.items()
    )


class PhysicalOnboardingHazardError(ValueError):
    """The hazard register is malformed, unsafe, or outside its workspace."""


class HazardSeverity(str, Enum):
    """Severity vocabulary used by the reviewed pre-hardware register."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"


class HazardStatus(str, Enum):
    """The only states allowed before physical evidence and review exist."""

    OPEN_BLOCKING = "OPEN_BLOCKING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class ConfigurationEpoch(str, Enum):
    """Configuration identities whose change makes hazard evidence stale."""

    SOFTWARE_BUILD = "software_build"
    CAMERA_SUPPORT_OPTICS = "camera_support_optics"
    BOARD_TAGS_BENCH = "board_tags_bench"
    ARM_CONTROLLER_TOOL = "arm_controller_tool"
    POWER_SYSTEM = "power_system"
    KEYBOARD_STATION = "keyboard_station"
    PHONE_STATION = "phone_station"
    EMPTY_CELL_SAFETY = "empty_cell_safety"


def _strict_object(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PhysicalOnboardingHazardError(f"duplicate JSON field {key!r}")
        result[key] = value
    return result


def _reject_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise PhysicalOnboardingHazardError(f"nonfinite JSON value {value!r}")
    # No field in this schema has floating-point semantics.  Rejecting all
    # floats also prevents alternate spellings of the integer revision.
    raise PhysicalOnboardingHazardError("hazard register must not contain floats")


def _reject_constant(value: str) -> None:
    raise PhysicalOnboardingHazardError(f"nonfinite JSON constant {value!r}")


def _parse_integer(value: str) -> int:
    if len(value) > 10:
        raise PhysicalOnboardingHazardError("hazard register integer is out of bounds")
    return int(value)


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise PhysicalOnboardingHazardError(f"{label} must be a JSON object")
    return value


def _array(value: object, label: str, *, maximum: int) -> list[Any]:
    if not isinstance(value, list):
        raise PhysicalOnboardingHazardError(f"{label} must be a JSON array")
    if len(value) > maximum:
        raise PhysicalOnboardingHazardError(f"{label} exceeds the {maximum}-item limit")
    return value


def _exact_fields(
    value: Mapping[str, Any], expected: frozenset[str], label: str
) -> None:
    actual = frozenset(value)
    if actual != expected:
        raise PhysicalOnboardingHazardError(
            f"{label} fields differ: missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )


def _text(value: object, label: str, *, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise PhysicalOnboardingHazardError(f"{label} must be non-empty trimmed text")
    if len(value) > maximum:
        raise PhysicalOnboardingHazardError(f"{label} exceeds {maximum} characters")
    control = (
        _TEXT_CONTROL.search(value) is not None
        if type(value) is str
        # Preserve the existing public helper's str-subclass iterator behavior.
        else any(ord(character) < 32 or ord(character) == 127 for character in value)
    )
    if control:
        raise PhysicalOnboardingHazardError(f"{label} contains a control character")
    return value


def _action_code(value: object, label: str) -> str:
    result = _text(value, label, maximum=128)
    if _ACTION_CODE.fullmatch(result) is None:
        raise PhysicalOnboardingHazardError(
            f"{label} must be an uppercase bounded action code"
        )
    return result


def _unique_text_tuple(
    value: object,
    label: str,
    *,
    maximum_items: int,
) -> tuple[str, ...]:
    items = _array(value, label, maximum=maximum_items)
    if not items:
        raise PhysicalOnboardingHazardError(f"{label} must not be empty")
    result = tuple(_text(item, f"{label}[{index}]") for index, item in enumerate(items))
    if len(result) != len(set(result)):
        raise PhysicalOnboardingHazardError(f"{label} contains duplicates")
    return result


def _stage_tuple(value: object, label: str) -> tuple[PhysicalOnboardingStage, ...]:
    raw_stages = _array(value, label, maximum=MAX_REFERENCES_PER_HAZARD)
    if not raw_stages:
        raise PhysicalOnboardingHazardError(f"{label} must not be empty")
    stages: list[PhysicalOnboardingStage] = []
    for index, raw_stage in enumerate(raw_stages):
        try:
            stage = PhysicalOnboardingStage(raw_stage)
        except (TypeError, ValueError) as exc:
            raise PhysicalOnboardingHazardError(
                f"{label}[{index}] is not a valid onboarding stage"
            ) from exc
        stages.append(stage)
    if len(stages) != len(set(stages)):
        raise PhysicalOnboardingHazardError(f"{label} contains duplicate stages")
    return tuple(stages)


def _epoch_tuple(value: object, label: str) -> tuple[ConfigurationEpoch, ...]:
    raw_epochs = _array(value, label, maximum=MAX_REFERENCES_PER_HAZARD)
    if not raw_epochs:
        raise PhysicalOnboardingHazardError(f"{label} must not be empty")
    epochs: list[ConfigurationEpoch] = []
    for index, raw_epoch in enumerate(raw_epochs):
        try:
            epoch = ConfigurationEpoch(raw_epoch)
        except (TypeError, ValueError) as exc:
            raise PhysicalOnboardingHazardError(
                f"{label}[{index}] is not a valid configuration epoch"
            ) from exc
        epochs.append(epoch)
    if len(epochs) != len(set(epochs)):
        raise PhysicalOnboardingHazardError(
            f"{label} contains duplicate configuration epochs"
        )
    return tuple(epochs)


def _reject_symlink_chain(path: Path, label: str) -> None:
    """Reject a symlink at the selected path or any existing ancestor."""

    cursor = Path(os.path.abspath(path))
    while True:
        try:
            if os.path.lexists(cursor) and cursor.is_symlink():
                raise PhysicalOnboardingHazardError(f"{label} contains a symlink")
        except OSError as exc:
            raise PhysicalOnboardingHazardError(f"{label} is unavailable") from exc
        if cursor.parent == cursor:
            return
        cursor = cursor.parent


def _resolve_register_path(workspace: Path, selected: Path) -> tuple[Path, Path]:
    _reject_symlink_chain(workspace, "workspace")
    try:
        root = workspace.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise PhysicalOnboardingHazardError("workspace is unavailable") from exc
    if not root.is_dir():
        raise PhysicalOnboardingHazardError("workspace must be a directory")

    if not selected.is_absolute() and ".." in selected.parts:
        raise PhysicalOnboardingHazardError(
            "hazard register path must not contain traversal"
        )
    candidate = selected if selected.is_absolute() else root / selected
    _reject_symlink_chain(candidate, "hazard register path")
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise PhysicalOnboardingHazardError(
            "hazard register must be a file beneath the workspace"
        ) from exc
    if not resolved.is_file():
        raise PhysicalOnboardingHazardError("hazard register must be a regular file")
    return root, resolved


@dataclass(frozen=True, slots=True)
class HazardAuthority:
    """Planning-only authority carried by this pre-hardware artifact."""

    planning_authority: bool
    simulation_authority: bool
    device_io_authorized: bool
    robot_power_authorized: bool
    motion_authorized: bool
    contact_authorized: bool
    build_promotion_authorized: bool
    physical_release_effect: str

    def __post_init__(self) -> None:
        if not _has_exact_typed_values(self.to_dict(), _EXPECTED_AUTHORITY):
            raise PhysicalOnboardingHazardError(
                "hazard authority must remain planning-only with zero physical authority"
            )

    @property
    def zero_physical_authority(self) -> bool:
        return True

    def to_dict(self) -> dict[str, object]:
        return {
            "planning_authority": self.planning_authority,
            "simulation_authority": self.simulation_authority,
            "device_io_authorized": self.device_io_authorized,
            "robot_power_authorized": self.robot_power_authorized,
            "motion_authorized": self.motion_authorized,
            "contact_authorized": self.contact_authorized,
            "build_promotion_authorized": self.build_promotion_authorized,
            "physical_release_effect": self.physical_release_effect,
        }


@dataclass(frozen=True, slots=True)
class PhysicalOnboardingHazard:
    """One still-open hazard and its evidence/invalidation boundaries."""

    hazard_id: str
    title: str
    severity: HazardSeverity
    status: HazardStatus
    evidence_stages: tuple[PhysicalOnboardingStage, ...]
    invalidation_epochs: tuple[ConfigurationEpoch, ...]
    controls: tuple[str, ...]
    required_evidence: tuple[str, ...]
    fail_safe: str
    residual_status: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.hazard_id, str)
            or _HAZARD_ID.fullmatch(self.hazard_id) is None
        ):
            raise PhysicalOnboardingHazardError("hazard_id is invalid")
        _text(self.title, "hazard title", maximum=160)
        if not isinstance(self.severity, HazardSeverity):
            raise PhysicalOnboardingHazardError("hazard severity is invalid")
        if not isinstance(self.status, HazardStatus):
            raise PhysicalOnboardingHazardError(
                "pre-hardware hazard status must remain open"
            )
        if (
            not isinstance(self.evidence_stages, tuple)
            or not self.evidence_stages
            or len(self.evidence_stages) > MAX_REFERENCES_PER_HAZARD
            or any(
                not isinstance(stage, PhysicalOnboardingStage)
                for stage in self.evidence_stages
            )
            or len(self.evidence_stages) != len(set(self.evidence_stages))
        ):
            raise PhysicalOnboardingHazardError(
                "hazard evidence stages must not be empty"
            )
        if (
            not isinstance(self.invalidation_epochs, tuple)
            or not self.invalidation_epochs
            or len(self.invalidation_epochs) > MAX_REFERENCES_PER_HAZARD
            or any(
                not isinstance(epoch, ConfigurationEpoch)
                for epoch in self.invalidation_epochs
            )
            or len(self.invalidation_epochs) != len(set(self.invalidation_epochs))
        ):
            raise PhysicalOnboardingHazardError(
                "hazard invalidation epochs must be non-empty valid unique epochs"
            )
        if (
            not isinstance(self.controls, tuple)
            or not self.controls
            or len(self.controls) > MAX_CONTROLS_PER_HAZARD
            or any(not isinstance(control, str) for control in self.controls)
            or len(self.controls) != len(set(self.controls))
        ):
            raise PhysicalOnboardingHazardError("hazard controls must not be empty")
        for index, control in enumerate(self.controls):
            _text(control, f"hazard controls[{index}]")
        if (
            not isinstance(self.required_evidence, tuple)
            or not self.required_evidence
            or len(self.required_evidence) > MAX_EVIDENCE_REQUIREMENTS_PER_HAZARD
            or any(not isinstance(evidence, str) for evidence in self.required_evidence)
            or len(self.required_evidence) != len(set(self.required_evidence))
        ):
            raise PhysicalOnboardingHazardError(
                "hazard required evidence must not be empty"
            )
        for index, evidence in enumerate(self.required_evidence):
            _text(evidence, f"hazard required_evidence[{index}]")
        _action_code(self.fail_safe, "hazard fail_safe")
        _action_code(self.residual_status, "hazard residual_status")

    @property
    def id(self) -> str:
        """Expose the register spelling while keeping a descriptive field name."""

        return self.hazard_id

    @property
    def configuration_epochs(self) -> tuple[ConfigurationEpoch, ...]:
        """Alias that makes the invalidation semantics explicit to callers."""

        return self.invalidation_epochs

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.hazard_id,
            "title": self.title,
            "severity": self.severity.value,
            "status": self.status.value,
            "evidence_stages": [stage.value for stage in self.evidence_stages],
            "invalidation_epochs": [epoch.value for epoch in self.invalidation_epochs],
            "controls": list(self.controls),
            "required_evidence": list(self.required_evidence),
            "fail_safe": self.fail_safe,
            "residual_status": self.residual_status,
        }


@dataclass(frozen=True, slots=True)
class PhysicalOnboardingHazardRegister:
    """A validated, immutable, planning-only view of the hazard register."""

    source_path: Path
    source_sha256: str
    register_id: str
    revision: int
    status: str
    runtime_activation: bool
    authority: HazardAuthority
    hazards: tuple[PhysicalOnboardingHazard, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.source_path, Path):
            raise PhysicalOnboardingHazardError(
                "hazard register source path is invalid"
            )
        if (
            not isinstance(self.source_sha256, str)
            or _SHA256.fullmatch(self.source_sha256) is None
        ):
            raise PhysicalOnboardingHazardError("hazard register hash is invalid")
        if self.register_id != "ROCELL-PHYSICAL-ONBOARDING-HAZARDS-001":
            raise PhysicalOnboardingHazardError("hazard register ID is invalid")
        if type(self.revision) is not int or self.revision != 2:
            raise PhysicalOnboardingHazardError("hazard register revision must be 2")
        if self.status != "PREHARDWARE_OPEN_ZERO_AUTHORITY":
            raise PhysicalOnboardingHazardError(
                "hazard register status must remain pre-hardware and open"
            )
        if self.runtime_activation is not False:
            raise PhysicalOnboardingHazardError(
                "hazard register cannot activate a physical runtime"
            )
        if not isinstance(self.authority, HazardAuthority):
            raise PhysicalOnboardingHazardError("hazard authority is invalid")
        if not isinstance(self.hazards, tuple):
            raise PhysicalOnboardingHazardError("hazards must be an immutable tuple")
        ids = tuple(hazard.hazard_id for hazard in self.hazards)
        if len(ids) != len(set(ids)):
            raise PhysicalOnboardingHazardError("duplicate hazard ID")
        if ids != _EXPECTED_HAZARD_IDS:
            raise PhysicalOnboardingHazardError(
                "hazard ID order or membership differs from HZ-001..HZ-016"
            )
        if any(not isinstance(hazard.status, HazardStatus) for hazard in self.hazards):
            raise PhysicalOnboardingHazardError(
                "pre-hardware hazards must remain open or review-required"
            )
        if self.hazards[11].controls[0] != _CANONICAL_LEASE_ORDER_CONTROL:
            raise PhysicalOnboardingHazardError(
                "HZ-012 must retain canonical CELL -> SESSION -> CAMERA -> "
                "ARM_CONTROLLER lease order"
            )
        expected_hazard_scope: dict[
            str,
            tuple[
                tuple[PhysicalOnboardingStage, ...],
                tuple[ConfigurationEpoch, ...] | None,
            ],
        ] = {
            "HZ-001": (
                (
                    PhysicalOnboardingStage.POWER_SAFETY,
                    PhysicalOnboardingStage.POWER_ON_OBSERVATION,
                    PhysicalOnboardingStage.REFERENCE_FRAME_CALIBRATION,
                    PhysicalOnboardingStage.NONCONTACT_ACCEPTANCE,
                ),
                None,
            ),
            "HZ-004": (
                (
                    PhysicalOnboardingStage.POWER_SAFETY,
                    PhysicalOnboardingStage.POWER_ON_OBSERVATION,
                    PhysicalOnboardingStage.REFERENCE_FRAME_CALIBRATION,
                    PhysicalOnboardingStage.NONCONTACT_ACCEPTANCE,
                ),
                None,
            ),
            "HZ-015": (
                (
                    PhysicalOnboardingStage.CAMERA_MODE_CONTROLS,
                    PhysicalOnboardingStage.CAMERA_FRAME_FRESHNESS,
                    PhysicalOnboardingStage.OPTICS_INTRINSICS,
                    PhysicalOnboardingStage.STATIC_REGISTRATION,
                ),
                (
                    ConfigurationEpoch.SOFTWARE_BUILD,
                    ConfigurationEpoch.CAMERA_SUPPORT_OPTICS,
                    ConfigurationEpoch.PHONE_STATION,
                ),
            ),
            "HZ-016": (
                (
                    PhysicalOnboardingStage.POWER_SAFETY,
                    PhysicalOnboardingStage.POWER_ON_OBSERVATION,
                    PhysicalOnboardingStage.FEEDBACK_ONLY_CONNECTION,
                    PhysicalOnboardingStage.REFERENCE_FRAME_CALIBRATION,
                    PhysicalOnboardingStage.NONCONTACT_ACCEPTANCE,
                ),
                None,
            ),
        }
        for hazard_id, (stages, epochs) in expected_hazard_scope.items():
            hazard = self.by_id[hazard_id]
            if hazard.evidence_stages != stages or (
                epochs is not None and hazard.invalidation_epochs != epochs
            ):
                raise PhysicalOnboardingHazardError(
                    f"{hazard_id} reviewed stage or epoch scope changed"
                )

    @property
    def by_id(self) -> Mapping[str, PhysicalOnboardingHazard]:
        return MappingProxyType({hazard.hazard_id: hazard for hazard in self.hazards})

    @property
    def zero_physical_authority(self) -> bool:
        return self.authority.zero_physical_authority

    @property
    def blocking_hazards(self) -> tuple[PhysicalOnboardingHazard, ...]:
        return tuple(
            hazard
            for hazard in self.hazards
            if hazard.status is HazardStatus.OPEN_BLOCKING
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": PHYSICAL_ONBOARDING_HAZARD_REGISTER_SCHEMA,
            "register_id": self.register_id,
            "revision": self.revision,
            "status": self.status,
            "runtime_activation": self.runtime_activation,
            "authority": self.authority.to_dict(),
            "hazards": [hazard.to_dict() for hazard in self.hazards],
        }


def _parse_hazard(raw: object, index: int) -> PhysicalOnboardingHazard:
    label = f"hazards[{index}]"
    value = _mapping(raw, label)
    _exact_fields(value, _EXPECTED_HAZARD_FIELDS, label)

    hazard_id = _text(value["id"], f"{label}.id", maximum=6)
    if _HAZARD_ID.fullmatch(hazard_id) is None:
        raise PhysicalOnboardingHazardError(f"{label}.id is not a valid hazard ID")
    try:
        severity = HazardSeverity(value["severity"])
    except (TypeError, ValueError) as exc:
        raise PhysicalOnboardingHazardError(
            f"{label}.severity is not a valid severity"
        ) from exc
    try:
        status = HazardStatus(value["status"])
    except (TypeError, ValueError) as exc:
        raise PhysicalOnboardingHazardError(
            f"{label}.status must be OPEN_BLOCKING or REVIEW_REQUIRED; "
            "CLOSED is forbidden before hardware review"
        ) from exc

    return PhysicalOnboardingHazard(
        hazard_id=hazard_id,
        title=_text(value["title"], f"{label}.title", maximum=160),
        severity=severity,
        status=status,
        evidence_stages=_stage_tuple(
            value["evidence_stages"], f"{label}.evidence_stages"
        ),
        invalidation_epochs=_epoch_tuple(
            value["invalidation_epochs"], f"{label}.invalidation_epochs"
        ),
        controls=_unique_text_tuple(
            value["controls"],
            f"{label}.controls",
            maximum_items=MAX_CONTROLS_PER_HAZARD,
        ),
        required_evidence=_unique_text_tuple(
            value["required_evidence"],
            f"{label}.required_evidence",
            maximum_items=MAX_EVIDENCE_REQUIREMENTS_PER_HAZARD,
        ),
        fail_safe=_action_code(value["fail_safe"], f"{label}.fail_safe"),
        residual_status=_action_code(
            value["residual_status"], f"{label}.residual_status"
        ),
    )


def load_physical_onboarding_hazards(
    workspace: Path,
    register_path: Path | None = None,
) -> PhysicalOnboardingHazardRegister:
    """Load a bounded hazard register without granting or exercising authority."""

    selected = (
        DEFAULT_PHYSICAL_ONBOARDING_HAZARDS
        if register_path is None
        else Path(register_path)
    )
    _root, resolved = _resolve_register_path(Path(workspace), selected)
    try:
        payload = resolved.read_bytes()
    except OSError as exc:
        raise PhysicalOnboardingHazardError("could not read hazard register") from exc
    if not payload or len(payload) > MAX_PHYSICAL_ONBOARDING_HAZARD_BYTES:
        raise PhysicalOnboardingHazardError(
            "hazard register size must be within the configured byte limit"
        )
    try:
        decoded = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_strict_object,
            parse_float=_reject_float,
            parse_int=_parse_integer,
            parse_constant=_reject_constant,
        )
    except PhysicalOnboardingHazardError:
        raise
    except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise PhysicalOnboardingHazardError(
            "hazard register must be strict UTF-8 JSON"
        ) from exc

    document = _mapping(decoded, "hazard register")
    _exact_fields(document, _EXPECTED_ROOT_FIELDS, "hazard register")
    if document["schema"] != PHYSICAL_ONBOARDING_HAZARD_REGISTER_SCHEMA:
        raise PhysicalOnboardingHazardError("unsupported hazard register schema")
    if document["register_id"] != "ROCELL-PHYSICAL-ONBOARDING-HAZARDS-001":
        raise PhysicalOnboardingHazardError("unexpected hazard register ID")
    if type(document["revision"]) is not int or document["revision"] != 2:
        raise PhysicalOnboardingHazardError("hazard register revision must be 2")
    if document["status"] != "PREHARDWARE_OPEN_ZERO_AUTHORITY":
        raise PhysicalOnboardingHazardError(
            "hazard register status must remain pre-hardware and open"
        )
    if document["runtime_activation"] is not False:
        raise PhysicalOnboardingHazardError(
            "hazard register runtime_activation must remain false"
        )

    raw_authority = _mapping(document["authority"], "authority")
    _exact_fields(raw_authority, _EXPECTED_AUTHORITY_FIELDS, "authority")
    if not _has_exact_typed_values(raw_authority, _EXPECTED_AUTHORITY):
        raise PhysicalOnboardingHazardError(
            "hazard register exceeds zero physical authority"
        )
    authority = HazardAuthority(**dict(raw_authority))

    raw_hazards = _array(document["hazards"], "hazards", maximum=MAX_HAZARDS)
    if not raw_hazards:
        raise PhysicalOnboardingHazardError("hazards must not be empty")
    hazards = tuple(
        _parse_hazard(raw_hazard, index) for index, raw_hazard in enumerate(raw_hazards)
    )
    ids = tuple(hazard.hazard_id for hazard in hazards)
    if len(ids) != len(set(ids)):
        raise PhysicalOnboardingHazardError("duplicate hazard ID")
    if ids != _EXPECTED_HAZARD_IDS:
        raise PhysicalOnboardingHazardError(
            "hazard ID order or membership differs from HZ-001..HZ-016"
        )

    return PhysicalOnboardingHazardRegister(
        source_path=resolved,
        source_sha256=hashlib.sha256(payload).hexdigest(),
        register_id=document["register_id"],
        revision=document["revision"],
        status=document["status"],
        runtime_activation=False,
        authority=authority,
        hazards=hazards,
    )


def load_physical_onboarding_hazard_register(
    workspace: Path,
    register_path: Path | None = None,
) -> PhysicalOnboardingHazardRegister:
    """Singular-name compatibility wrapper for the register-oriented API."""

    return load_physical_onboarding_hazards(workspace, register_path)


# Concise aliases are useful in type annotations while the longer public names
# preserve context at import sites.
OnboardingHazard = PhysicalOnboardingHazard
OnboardingHazardRegister = PhysicalOnboardingHazardRegister
OnboardingHazardError = PhysicalOnboardingHazardError


__all__ = [
    "DEFAULT_PHYSICAL_ONBOARDING_HAZARDS",
    "DEFAULT_PHYSICAL_ONBOARDING_HAZARD_REGISTER",
    "MAX_CONTROLS_PER_HAZARD",
    "MAX_EVIDENCE_REQUIREMENTS_PER_HAZARD",
    "MAX_HAZARDS",
    "MAX_PHYSICAL_ONBOARDING_HAZARD_BYTES",
    "MAX_REFERENCES_PER_HAZARD",
    "PHYSICAL_ONBOARDING_HAZARDS_SCHEMA",
    "PHYSICAL_ONBOARDING_HAZARD_REGISTER_SCHEMA",
    "ConfigurationEpoch",
    "HazardAuthority",
    "HazardSeverity",
    "HazardStatus",
    "OnboardingHazard",
    "OnboardingHazardError",
    "OnboardingHazardRegister",
    "PhysicalOnboardingHazard",
    "PhysicalOnboardingHazardError",
    "PhysicalOnboardingHazardRegister",
    "load_physical_onboarding_hazard_register",
    "load_physical_onboarding_hazards",
]
