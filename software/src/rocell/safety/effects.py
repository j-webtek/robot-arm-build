"""Stage-agnostic authority and physical-effect design contract.

This module is deliberately descriptive.  It does not import a camera, serial
transport, arm adapter, permit issuer, or onboarding stage catalog, and loading
the policy cannot activate any runtime path.  ``device_open_allowed`` describes
what an eventual, separately authorized attempt would need to account for; it
does not grant permission to open a device.

The authority footprint intentionally parallels ``RuntimeAuthority`` and the
certainty values intentionally parallel the onboarding ``EffectCertainty``.
They are repeated here instead of importing application-layer runtime code so
this safety contract remains isolated and cannot become an accidental adapter
activation seam.  In particular, this file provides no conversion to a runtime
authority or permit.
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
from typing import Any, Iterable, Mapping


AUTHORITY_EFFECT_POLICY_SCHEMA = "rocell.authority_effect_policy.v1"
AUTHORITY_EFFECT_POLICY_ID = "ROCELL-AUTHORITY-EFFECT-001"
AUTHORITY_EFFECT_POLICY_SCOPE = "STAGE_AGNOSTIC_DESIGN_ONLY"
DEFAULT_AUTHORITY_EFFECT_POLICY = Path(
    "software/config/authority_effect_policy.json"
)

_MAX_POLICY_BYTES = 256 * 1024
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


class AuthorityEffectPolicyError(ValueError):
    """The design policy is malformed, ambiguous, or claims authority."""


class EffectClass(str, Enum):
    """Side-effect risk categories, independent of onboarding stage names."""

    NO_DEVICE_IO = "NO_DEVICE_IO"
    READ_ONLY_OS_INVENTORY = "READ_ONLY_OS_INVENTORY"
    BOUNDED_CAMERA_CAMPAIGN = "BOUNDED_CAMERA_CAMPAIGN"
    MANUAL_ENERGY_CHANGE = "MANUAL_ENERGY_CHANGE"
    MANUAL_POSSIBLE_MOTION = "MANUAL_POSSIBLE_MOTION"
    SERIAL_OPEN_OR_WRITE = "SERIAL_OPEN_OR_WRITE"
    NONCONTACT_ARM_MOTION_EXTERNAL = "NONCONTACT_ARM_MOTION_EXTERNAL"


class EffectCertainty(str, Enum):
    """Whether the outcome of an already attempted physical effect is known."""

    CONFIRMED = "CONFIRMED"
    UNCERTAIN = "UNCERTAIN"


EXPECTED_EFFECT_CLASS_ORDER = tuple(EffectClass)

# These values are the reviewed v1 risk taxonomy.  Keeping the complete table
# in code means a modified JSON file cannot quietly relabel a hazardous action
# as retryable, non-durable, or free of possible external effects.
_EXPECTED_EFFECT_CLASS_PROPERTIES: tuple[
    tuple[EffectClass, bool, bool, bool, bool], ...
] = (
    (EffectClass.NO_DEVICE_IO, False, False, False, False),
    (EffectClass.READ_ONLY_OS_INVENTORY, False, False, False, False),
    (EffectClass.BOUNDED_CAMERA_CAMPAIGN, True, True, True, False),
    (EffectClass.MANUAL_ENERGY_CHANGE, False, True, True, False),
    (EffectClass.MANUAL_POSSIBLE_MOTION, False, True, True, False),
    (EffectClass.SERIAL_OPEN_OR_WRITE, True, True, True, False),
    (EffectClass.NONCONTACT_ARM_MOTION_EXTERNAL, True, True, True, False),
)


def _strict_object(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AuthorityEffectPolicyError(
                f"duplicate authority/effect policy field {key!r}"
            )
        result[key] = value
    return result


def _reject_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise AuthorityEffectPolicyError(
            f"authority/effect policy contains nonfinite value {value!r}"
        )
    raise AuthorityEffectPolicyError(
        "authority/effect policy must not contain floats"
    )


def _reject_constant(value: str) -> None:
    raise AuthorityEffectPolicyError(
        f"authority/effect policy contains nonfinite constant {value!r}"
    )


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if type(value) is not dict:
        raise AuthorityEffectPolicyError(f"{label} must be an object")
    return value


def _exact_fields(
    value: Mapping[str, Any], expected: set[str], label: str
) -> None:
    actual = set(value)
    if actual != expected:
        raise AuthorityEffectPolicyError(
            f"{label} fields differ: missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )


def _boolean(value: object, label: str) -> bool:
    if type(value) is not bool:
        raise AuthorityEffectPolicyError(f"{label} must be boolean")
    return value


def _zero_integer(value: object, label: str) -> int:
    if type(value) is not int:
        raise AuthorityEffectPolicyError(f"{label} must be integer zero")
    if value != 0:
        raise AuthorityEffectPolicyError(
            "authority/effect policy must retain zero authority"
        )
    return value


def _exact_text(value: object, expected: str, label: str) -> str:
    if type(value) is not str or value != expected:
        raise AuthorityEffectPolicyError(f"{label} must equal {expected!r}")
    return value


def _reject_symlink_chain(path: Path, label: str) -> None:
    """Reject a symlink at the source, workspace, or any existing parent."""

    cursor = Path(os.path.abspath(path))
    while True:
        if os.path.lexists(cursor) and cursor.is_symlink():
            raise AuthorityEffectPolicyError(f"{label} contains a symlink")
        if cursor.parent == cursor:
            return
        cursor = cursor.parent


def _workspace_root(workspace: Path) -> Path:
    _reject_symlink_chain(workspace, "workspace")
    try:
        root = workspace.resolve(strict=True)
    except OSError as exc:
        raise AuthorityEffectPolicyError("workspace is unavailable") from exc
    if not root.is_dir():
        raise AuthorityEffectPolicyError("workspace must be a directory")
    return root


def _policy_source(root: Path, requested: Path) -> tuple[Path, str]:
    selected = requested if requested.is_absolute() else root / requested
    _reject_symlink_chain(selected, "authority/effect policy source")
    try:
        resolved = selected.resolve(strict=True)
        relative = resolved.relative_to(root).as_posix()
    except (OSError, ValueError) as exc:
        raise AuthorityEffectPolicyError(
            "authority/effect policy source is unavailable or outside the workspace"
        ) from exc
    if not resolved.is_file():
        raise AuthorityEffectPolicyError(
            "authority/effect policy source must be a regular file"
        )
    return resolved, relative


def _read_policy(path: Path) -> tuple[Mapping[str, Any], bytes]:
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise AuthorityEffectPolicyError(
            "could not read authority/effect policy source"
        ) from exc
    if not payload or len(payload) > _MAX_POLICY_BYTES:
        raise AuthorityEffectPolicyError(
            f"authority/effect policy size must be within 1..{_MAX_POLICY_BYTES} bytes"
        )
    try:
        document = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_strict_object,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise AuthorityEffectPolicyError(
            "authority/effect policy must be strict UTF-8 JSON"
        ) from exc
    return _mapping(document, "authority/effect policy"), payload


@dataclass(frozen=True, slots=True)
class ZeroAuthority:
    """A descriptive footprint that is valid only when every authority is zero.

    The first, second, fourth, fifth, sixth, and final fields mirror the ideas
    carried by ``RuntimeAuthority``.  Device-I/O, robot-power, and promotion
    gates are explicit here because this is a broader design policy, not a
    runtime-port record.
    """

    hardware_accessed: bool
    hardware_commands_generated: int
    device_io_authorized: bool
    robot_power_authorized: bool
    live_motion_authorized: bool
    physical_contact_authorized: bool
    build_promotion_authorized: bool
    physical_release_effect: str

    def __post_init__(self) -> None:
        for field_name in (
            "hardware_accessed",
            "device_io_authorized",
            "robot_power_authorized",
            "live_motion_authorized",
            "physical_contact_authorized",
            "build_promotion_authorized",
        ):
            value = _boolean(getattr(self, field_name), field_name)
            if value:
                raise AuthorityEffectPolicyError(
                    "authority/effect policy must retain zero authority"
                )
        _zero_integer(
            self.hardware_commands_generated, "hardware_commands_generated"
        )
        if self.physical_release_effect != "NONE":
            raise AuthorityEffectPolicyError(
                "authority/effect policy must retain zero authority"
            )

    @property
    def is_zero_authority(self) -> bool:
        """True for every constructible instance; computed for audit clarity."""

        return (
            not self.hardware_accessed
            and self.hardware_commands_generated == 0
            and not self.device_io_authorized
            and not self.robot_power_authorized
            and not self.live_motion_authorized
            and not self.physical_contact_authorized
            and not self.build_promotion_authorized
            and self.physical_release_effect == "NONE"
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "hardware_accessed": self.hardware_accessed,
            "hardware_commands_generated": self.hardware_commands_generated,
            "device_io_authorized": self.device_io_authorized,
            "robot_power_authorized": self.robot_power_authorized,
            "live_motion_authorized": self.live_motion_authorized,
            "physical_contact_authorized": self.physical_contact_authorized,
            "build_promotion_authorized": self.build_promotion_authorized,
            "physical_release_effect": self.physical_release_effect,
        }


@dataclass(frozen=True, slots=True)
class EffectCertaintyContract:
    """Fail-closed handling for confirmed versus uncertain external effects."""

    values: tuple[EffectCertainty, ...]
    uncertain_requires_manual_reconciliation: bool
    automatic_retry_after_uncertain_effect: bool

    def __post_init__(self) -> None:
        if type(self.values) is not tuple or self.values != tuple(EffectCertainty):
            raise AuthorityEffectPolicyError(
                "effect certainty values differ from the locked contract"
            )
        if any(type(value) is not EffectCertainty for value in self.values):
            raise AuthorityEffectPolicyError(
                "effect certainty values contain an unsupported type"
            )
        if _boolean(
            self.uncertain_requires_manual_reconciliation,
            "uncertain_requires_manual_reconciliation",
        ) is not True:
            raise AuthorityEffectPolicyError(
                "an uncertain effect must require manual reconciliation"
            )
        if _boolean(
            self.automatic_retry_after_uncertain_effect,
            "automatic_retry_after_uncertain_effect",
        ) is not False:
            raise AuthorityEffectPolicyError(
                "an uncertain effect must never be retried automatically"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "values": [value.value for value in self.values],
            "uncertain_requires_manual_reconciliation": (
                self.uncertain_requires_manual_reconciliation
            ),
            "automatic_retry_after_uncertain_effect": (
                self.automatic_retry_after_uncertain_effect
            ),
        }


@dataclass(frozen=True, slots=True)
class EffectClassRule:
    """Risk metadata for one class; never an executable capability grant."""

    effect_class: EffectClass
    device_open_allowed: bool
    external_physical_effect_possible: bool
    durable_attempt_required: bool
    automatic_retry_allowed: bool

    def __post_init__(self) -> None:
        if type(self.effect_class) is not EffectClass:
            raise AuthorityEffectPolicyError(
                "effect_class must be an EffectClass value"
            )
        for field_name in (
            "device_open_allowed",
            "external_physical_effect_possible",
            "durable_attempt_required",
            "automatic_retry_allowed",
        ):
            _boolean(getattr(self, field_name), field_name)
        if self.automatic_retry_allowed:
            raise AuthorityEffectPolicyError(
                "automatic retry must be disabled for every effect class"
            )
        if (
            self.external_physical_effect_possible
            != self.durable_attempt_required
        ):
            raise AuthorityEffectPolicyError(
                "possible external effects require a durable attempt"
            )

    @property
    def id(self) -> EffectClass:
        """The JSON-facing class identifier."""

        return self.effect_class

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.effect_class.value,
            "device_open_allowed": self.device_open_allowed,
            "external_physical_effect_possible": (
                self.external_physical_effect_possible
            ),
            "durable_attempt_required": self.durable_attempt_required,
            "automatic_retry_allowed": self.automatic_retry_allowed,
        }


@dataclass(frozen=True, slots=True)
class AuthorityEffectPolicy:
    """Immutable, source-bound, stage-agnostic v1 design policy."""

    schema: str
    policy_id: str
    scope: str
    runtime_activation: bool
    authority: ZeroAuthority
    effect_certainty: EffectCertaintyContract
    effect_classes: tuple[EffectClassRule, ...]
    source_relative_path: str
    source_sha256: str

    def __post_init__(self) -> None:
        _exact_text(self.schema, AUTHORITY_EFFECT_POLICY_SCHEMA, "schema")
        _exact_text(self.policy_id, AUTHORITY_EFFECT_POLICY_ID, "policy_id")
        _exact_text(self.scope, AUTHORITY_EFFECT_POLICY_SCOPE, "scope")
        if _boolean(self.runtime_activation, "runtime_activation"):
            raise AuthorityEffectPolicyError(
                "runtime activation must remain disabled"
            )
        if type(self.authority) is not ZeroAuthority:
            raise AuthorityEffectPolicyError(
                "authority must be an immutable ZeroAuthority record"
            )
        self.authority.__post_init__()
        if not self.authority.is_zero_authority:
            raise AuthorityEffectPolicyError(
                "authority/effect policy must retain zero authority"
            )
        if type(self.effect_certainty) is not EffectCertaintyContract:
            raise AuthorityEffectPolicyError(
                "effect_certainty must be an immutable certainty contract"
            )
        self.effect_certainty.__post_init__()
        if type(self.effect_classes) is not tuple:
            raise AuthorityEffectPolicyError(
                "effect_classes must be an immutable tuple"
            )
        if any(type(rule) is not EffectClassRule for rule in self.effect_classes):
            raise AuthorityEffectPolicyError(
                "effect_classes contains a substituted rule type"
            )
        for rule in self.effect_classes:
            rule.__post_init__()
        actual = tuple(
            (
                rule.effect_class,
                rule.device_open_allowed,
                rule.external_physical_effect_possible,
                rule.durable_attempt_required,
                rule.automatic_retry_allowed,
            )
            for rule in self.effect_classes
        )
        if actual != _EXPECTED_EFFECT_CLASS_PROPERTIES:
            raise AuthorityEffectPolicyError(
                "effect class risk properties differ from the locked v1 contract"
            )
        if (
            type(self.source_relative_path) is not str
            or not self.source_relative_path
            or self.source_relative_path != self.source_relative_path.strip()
            or Path(self.source_relative_path).is_absolute()
            or ".." in Path(self.source_relative_path).parts
            or "\\" in self.source_relative_path
        ):
            raise AuthorityEffectPolicyError(
                "source_relative_path must be a normalized workspace-relative path"
            )
        if (
            type(self.source_sha256) is not str
            or _SHA256_RE.fullmatch(self.source_sha256) is None
        ):
            raise AuthorityEffectPolicyError(
                "source_sha256 must be a lowercase SHA-256 digest"
            )

    def rule_for(self, effect_class: EffectClass | str) -> EffectClassRule:
        """Return one exact rule without introducing a stage-to-class mapping."""

        try:
            selected = (
                effect_class
                if type(effect_class) is EffectClass
                else EffectClass(effect_class)
            )
        except (TypeError, ValueError) as exc:
            raise AuthorityEffectPolicyError(
                f"unsupported effect class {effect_class!r}"
            ) from exc
        return self.effect_classes[EXPECTED_EFFECT_CLASS_ORDER.index(selected)]

    def to_dict(self) -> dict[str, object]:
        """Return a detached JSON representation of the controlled document."""

        return {
            "schema": self.schema,
            "policy_id": self.policy_id,
            "scope": self.scope,
            "runtime_activation": self.runtime_activation,
            "authority": self.authority.to_dict(),
            "effect_certainty": self.effect_certainty.to_dict(),
            "effect_classes": [rule.to_dict() for rule in self.effect_classes],
        }


def _parse_authority(document: Mapping[str, Any]) -> ZeroAuthority:
    fields = {
        "hardware_accessed",
        "hardware_commands_generated",
        "device_io_authorized",
        "robot_power_authorized",
        "live_motion_authorized",
        "physical_contact_authorized",
        "build_promotion_authorized",
        "physical_release_effect",
    }
    _exact_fields(document, fields, "authority")
    return ZeroAuthority(
        hardware_accessed=document["hardware_accessed"],
        hardware_commands_generated=document["hardware_commands_generated"],
        device_io_authorized=document["device_io_authorized"],
        robot_power_authorized=document["robot_power_authorized"],
        live_motion_authorized=document["live_motion_authorized"],
        physical_contact_authorized=document["physical_contact_authorized"],
        build_promotion_authorized=document["build_promotion_authorized"],
        physical_release_effect=document["physical_release_effect"],
    )


def _parse_effect_certainty(
    document: Mapping[str, Any],
) -> EffectCertaintyContract:
    _exact_fields(
        document,
        {
            "values",
            "uncertain_requires_manual_reconciliation",
            "automatic_retry_after_uncertain_effect",
        },
        "effect_certainty",
    )
    values = document["values"]
    if type(values) is not list:
        raise AuthorityEffectPolicyError("effect_certainty.values must be an array")
    try:
        parsed_values = tuple(EffectCertainty(value) for value in values)
    except (TypeError, ValueError) as exc:
        raise AuthorityEffectPolicyError(
            "effect_certainty.values contains an unsupported value"
        ) from exc
    return EffectCertaintyContract(
        values=parsed_values,
        uncertain_requires_manual_reconciliation=document[
            "uncertain_requires_manual_reconciliation"
        ],
        automatic_retry_after_uncertain_effect=document[
            "automatic_retry_after_uncertain_effect"
        ],
    )


def _parse_effect_classes(value: object) -> tuple[EffectClassRule, ...]:
    if type(value) is not list:
        raise AuthorityEffectPolicyError("effect_classes must be an array")
    result: list[EffectClassRule] = []
    for index, raw_rule in enumerate(value):
        document = _mapping(raw_rule, f"effect_classes[{index}]")
        _exact_fields(
            document,
            {
                "id",
                "device_open_allowed",
                "external_physical_effect_possible",
                "durable_attempt_required",
                "automatic_retry_allowed",
            },
            f"effect_classes[{index}]",
        )
        try:
            effect_class = EffectClass(document["id"])
        except (TypeError, ValueError) as exc:
            raise AuthorityEffectPolicyError(
                f"effect_classes[{index}].id is unsupported"
            ) from exc
        result.append(
            EffectClassRule(
                effect_class=effect_class,
                device_open_allowed=document["device_open_allowed"],
                external_physical_effect_possible=document[
                    "external_physical_effect_possible"
                ],
                durable_attempt_required=document["durable_attempt_required"],
                automatic_retry_allowed=document["automatic_retry_allowed"],
            )
        )
    return tuple(result)


def load_authority_effect_policy(
    workspace: Path,
    policy_path: Path = DEFAULT_AUTHORITY_EFFECT_POLICY,
) -> AuthorityEffectPolicy:
    """Load a strict source-bound policy without activating any runtime code.

    Both the workspace and policy source must be real, non-symlinked paths.  An
    absolute custom source is accepted only when it resolves inside ``workspace``.
    JSON floats (including finite floats), non-finite constants, duplicate keys,
    and unknown fields fail before an immutable policy is returned.
    """

    if not isinstance(workspace, Path) or not isinstance(policy_path, Path):
        raise TypeError("workspace and policy_path must be pathlib.Path values")
    root = _workspace_root(workspace)
    source, relative = _policy_source(root, policy_path)
    document, payload = _read_policy(source)
    _exact_fields(
        document,
        {
            "schema",
            "policy_id",
            "scope",
            "runtime_activation",
            "authority",
            "effect_certainty",
            "effect_classes",
        },
        "authority/effect policy",
    )
    return AuthorityEffectPolicy(
        schema=document["schema"],
        policy_id=document["policy_id"],
        scope=document["scope"],
        runtime_activation=document["runtime_activation"],
        authority=_parse_authority(_mapping(document["authority"], "authority")),
        effect_certainty=_parse_effect_certainty(
            _mapping(document["effect_certainty"], "effect_certainty")
        ),
        effect_classes=_parse_effect_classes(document["effect_classes"]),
        source_relative_path=relative,
        source_sha256=hashlib.sha256(payload).hexdigest(),
    )


__all__ = [
    "AUTHORITY_EFFECT_POLICY_ID",
    "AUTHORITY_EFFECT_POLICY_SCHEMA",
    "AUTHORITY_EFFECT_POLICY_SCOPE",
    "DEFAULT_AUTHORITY_EFFECT_POLICY",
    "EXPECTED_EFFECT_CLASS_ORDER",
    "AuthorityEffectPolicy",
    "AuthorityEffectPolicyError",
    "EffectCertainty",
    "EffectCertaintyContract",
    "EffectClass",
    "EffectClassRule",
    "ZeroAuthority",
    "load_authority_effect_policy",
]
