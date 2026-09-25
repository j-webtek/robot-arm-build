"""Strict zero-hardware receipt contract for the selected Arducam B0477.

The purchased-camera profile records what was ordered.  This module models the
*shape* of the later receipt inspection while hardware is unavailable.  Its
fixtures are explicitly synthetic, every physical measurement remains null,
and every hardware/motion/contact authority remains false.

Identity values are deliberately parsed before they are compared.  That lets a
structurally valid but wrong delivered part retain its own canonical digest and
then fail an explicit comparison check; a mismatch can never be hidden by
hashing an expected template.  Parsing and comparison perform no device I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from .camera_profile import CAMERA_PROFILE_SCHEMA, PurchasedCameraProfile


B0477_CAMERA_RECEIPT_SCHEMA = "rocell.synthetic_b0477_camera_receipt.v1"
B0477_CAMERA_RECEIPT_ASSESSMENT_SCHEMA = (
    "rocell.synthetic_b0477_camera_receipt_assessment.v1"
)
MAX_B0477_CAMERA_RECEIPT_BYTES = 32 * 1024

_TARGET_PROFILE_ID = "arducam-b0477-imx283-16mm-purchased-001"
_FIXTURE_CLASS = "SYNTHETIC_ZERO_HARDWARE"
_EVIDENCE_ORIGIN = "SYNTHETIC_TEST_FIXTURE"
_EVIDENCE_AUTHORITY = "NO_PHYSICAL_EVIDENCE_AUTHORITY"
_CLAIM_SCOPE = (
    "receipt parser/comparator rehearsal only; no camera was received, "
    "inspected, opened, or measured"
)
_UNMEASURED_STATE = "UNMEASURED_NO_HARDWARE"
_LENS_SUPPLY_RELATIONSHIP = "included with B0477"

_ROOT_FIELDS = frozenset(
    {
        "schema",
        "schema_version",
        "receipt_id",
        "fixture_class",
        "target_profile",
        "evidence",
        "identity",
        "unmeasured_physical",
        "authority",
    }
)
_TARGET_FIELDS = frozenset({"schema", "profile_id"})
_EVIDENCE_FIELDS = frozenset({"origin", "authority", "claim_scope"})
_IDENTITY_FIELDS = frozenset({"manufacturer", "model", "sensor", "lens"})
_LENS_FIELDS = frozenset(
    {"mount", "focal_length_mm", "supply_relationship"}
)
_UNMEASURED_FIELDS = frozenset(
    {
        "state",
        "case_width_mm",
        "case_height_mm",
        "case_depth_mm",
        "mass_g",
        "mount_pattern",
        "fastener_thread",
        "fastener_depth_mm",
        "lens_projection_mm",
        "connector_clearance_mm",
        "entrance_pupil_offset_mm",
        "focus_distance_mm",
        "measured_horizontal_fov_deg",
        "measured_vertical_fov_deg",
        "usable_coverage_width_mm",
        "usable_coverage_height_mm",
    }
)
_UNMEASURED_VALUE_FIELDS = _UNMEASURED_FIELDS - {"state"}
_AUTHORITY_FIELDS = frozenset(
    {
        "hardware_accessed",
        "physical_receipt_verified",
        "camera_opened",
        "camera_frames_requested",
        "arm_commands",
        "hardware_presence_authority",
        "live_capture_authority",
        "calibration_authority",
        "robot_motion_authority",
        "contact_authority",
        "physical_release_effect",
    }
)


class CameraReceiptError(ValueError):
    """A synthetic receipt is malformed or overclaims physical evidence."""


class CameraReceiptMismatchError(CameraReceiptError):
    """A valid receipt does not match the selected purchased-camera profile."""


def _canonical_bytes(document: object) -> bytes:
    try:
        return json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CameraReceiptError("camera receipt cannot be canonicalized") from exc


def _sha256(document: object) -> str:
    return hashlib.sha256(_canonical_bytes(document)).hexdigest()


def _reject_constant(value: str) -> None:
    raise CameraReceiptError(
        f"camera receipt contains nonfinite JSON constant {value!r}"
    )


def _object_without_duplicates(
    pairs: Sequence[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CameraReceiptError(
                f"camera receipt contains duplicate key {key!r}"
            )
        result[key] = value
    return result


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CameraReceiptError(f"{label} must be an object")
    return value


def _exact_fields(
    value: Mapping[str, Any], expected: frozenset[str], label: str
) -> None:
    actual = frozenset(value)
    if actual != expected:
        raise CameraReceiptError(
            f"{label} fields differ; missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _exact(value: object, expected: object, label: str) -> None:
    # JSON booleans are Python integers; exact type checks prevent True == 1.
    if type(value) is not type(expected) or value != expected:
        raise CameraReceiptError(
            f"{label} must be {expected!r}, got {value!r}"
        )


def _text(value: object, label: str, *, maximum: int = 160) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value.strip() != value
        or len(value) > maximum
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise CameraReceiptError(
            f"{label} must be non-empty bounded trimmed text"
        )
    return value


def _finite_positive(value: object, label: str, *, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CameraReceiptError(f"{label} must be a finite positive number")
    parsed = float(value)
    if not math.isfinite(parsed) or not 0.0 < parsed <= maximum:
        raise CameraReceiptError(
            f"{label} must be finite and within (0, {maximum}]"
        )
    return parsed


def _digest(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise CameraReceiptError(f"{label} must be a lowercase SHA-256 digest")
    return value


@dataclass(frozen=True, slots=True)
class CameraReceiptLensIdentity:
    """Lens markings transcribed into the synthetic receipt fixture."""

    mount: str
    focal_length_mm: float
    supply_relationship: str

    def __post_init__(self) -> None:
        _text(self.mount, "identity.lens.mount")
        object.__setattr__(
            self,
            "focal_length_mm",
            _finite_positive(
                self.focal_length_mm,
                "identity.lens.focal_length_mm",
                maximum=1_000.0,
            ),
        )
        _text(
            self.supply_relationship,
            "identity.lens.supply_relationship",
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "mount": self.mount,
            "focal_length_mm": self.focal_length_mm,
            "supply_relationship": self.supply_relationship,
        }


@dataclass(frozen=True, slots=True)
class CameraReceiptIdentity:
    """Identity transcribed from a synthetic delivered-part description."""

    manufacturer: str
    model: str
    sensor: str
    lens: CameraReceiptLensIdentity

    def __post_init__(self) -> None:
        _text(self.manufacturer, "identity.manufacturer")
        _text(self.model, "identity.model")
        _text(self.sensor, "identity.sensor")
        if not isinstance(self.lens, CameraReceiptLensIdentity):
            raise CameraReceiptError(
                "identity.lens must be CameraReceiptLensIdentity"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "manufacturer": self.manufacturer,
            "model": self.model,
            "sensor": self.sensor,
            "lens": self.lens.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class B0477CameraReceipt:
    """Immutable interpretation of one strict, explicitly synthetic receipt."""

    source_path: Path | None
    source_file_sha256: str
    canonical_sha256: str
    receipt_id: str
    target_profile_schema: str
    target_profile_id: str
    identity: CameraReceiptIdentity
    unmeasured_physical: Mapping[str, None]

    def __post_init__(self) -> None:
        _digest(self.source_file_sha256, "source_file_sha256")
        _digest(self.canonical_sha256, "canonical_sha256")
        _text(self.receipt_id, "receipt_id", maximum=96)
        _text(self.target_profile_schema, "target_profile.schema")
        _text(self.target_profile_id, "target_profile.profile_id")
        if not isinstance(self.identity, CameraReceiptIdentity):
            raise CameraReceiptError("identity must be CameraReceiptIdentity")
        if frozenset(self.unmeasured_physical) != _UNMEASURED_VALUE_FIELDS:
            raise CameraReceiptError(
                "unmeasured physical field set differs from the receipt schema"
            )
        if any(value is not None for value in self.unmeasured_physical.values()):
            raise CameraReceiptError(
                "unmeasured physical values must all remain null"
            )
        object.__setattr__(
            self,
            "unmeasured_physical",
            MappingProxyType(dict(self.unmeasured_physical)),
        )
        expected_digest = _sha256(self.to_dict())
        if self.canonical_sha256 != expected_digest:
            raise CameraReceiptError(
                "canonical_sha256 does not bind the actual camera receipt object"
            )

    # These constants are validated at the JSON boundary and cannot be supplied
    # as permissive constructor flags.
    @property
    def fixture_class(self) -> str:
        return _FIXTURE_CLASS

    @property
    def hardware_accessed(self) -> bool:
        return False

    @property
    def physical_receipt_verified(self) -> bool:
        return False

    @property
    def live_ready(self) -> bool:
        return False

    def to_dict(self) -> dict[str, object]:
        """Return the exact normalized meaning bound by ``canonical_sha256``."""

        physical: dict[str, object] = {"state": _UNMEASURED_STATE}
        physical.update(self.unmeasured_physical)
        return {
            "schema": B0477_CAMERA_RECEIPT_SCHEMA,
            "schema_version": 1,
            "receipt_id": self.receipt_id,
            "fixture_class": _FIXTURE_CLASS,
            "target_profile": {
                "schema": self.target_profile_schema,
                "profile_id": self.target_profile_id,
            },
            "evidence": {
                "origin": _EVIDENCE_ORIGIN,
                "authority": _EVIDENCE_AUTHORITY,
                "claim_scope": _CLAIM_SCOPE,
            },
            "identity": self.identity.to_dict(),
            "unmeasured_physical": physical,
            "authority": {
                "hardware_accessed": False,
                "physical_receipt_verified": False,
                "camera_opened": False,
                "camera_frames_requested": 0,
                "arm_commands": 0,
                "hardware_presence_authority": False,
                "live_capture_authority": False,
                "calibration_authority": False,
                "robot_motion_authority": False,
                "contact_authority": False,
                "physical_release_effect": "NONE",
            },
        }


@dataclass(frozen=True, slots=True)
class CameraReceiptCheck:
    """One stable, machine-readable receipt comparison result."""

    check_id: str
    passed: bool
    detail: str

    def __post_init__(self) -> None:
        _text(self.check_id, "check.check_id", maximum=96)
        if not isinstance(self.passed, bool):
            raise CameraReceiptError("check.passed must be boolean")
        _text(self.detail, "check.detail", maximum=320)

    def to_dict(self) -> dict[str, object]:
        return {
            "check_id": self.check_id,
            "passed": self.passed,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class B0477CameraReceiptAssessment:
    """Fail-closed comparison of actual receipt values to the purchase profile."""

    receipt_id: str
    receipt_canonical_sha256: str
    profile_id: str
    profile_canonical_sha256: str
    checks: tuple[CameraReceiptCheck, ...]
    matched: bool = field(init=False)
    detail_code: str = field(init=False)
    physical_receipt_verified: bool = field(init=False, default=False)
    hardware_accessed: bool = field(init=False, default=False)
    physical_release_effect: str = field(init=False, default="NONE")

    def __post_init__(self) -> None:
        _text(self.receipt_id, "assessment.receipt_id", maximum=96)
        _digest(
            self.receipt_canonical_sha256,
            "assessment.receipt_canonical_sha256",
        )
        _text(self.profile_id, "assessment.profile_id")
        _digest(
            self.profile_canonical_sha256,
            "assessment.profile_canonical_sha256",
        )
        if not isinstance(self.checks, tuple) or not self.checks:
            raise CameraReceiptError("assessment.checks must be a non-empty tuple")
        if any(not isinstance(check, CameraReceiptCheck) for check in self.checks):
            raise CameraReceiptError(
                "assessment.checks must contain CameraReceiptCheck values"
            )
        check_ids = tuple(check.check_id for check in self.checks)
        if len(set(check_ids)) != len(check_ids):
            raise CameraReceiptError("assessment contains duplicate check IDs")
        matched = all(check.passed for check in self.checks)
        object.__setattr__(self, "matched", matched)
        object.__setattr__(
            self,
            "detail_code",
            (
                "SYNTHETIC_B0477_RECEIPT_MATCH"
                if matched
                else "SYNTHETIC_B0477_RECEIPT_MISMATCH_BLOCKED"
            ),
        )

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(check.check_id for check in self.checks if not check.passed)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": B0477_CAMERA_RECEIPT_ASSESSMENT_SCHEMA,
            "receipt_id": self.receipt_id,
            "receipt_canonical_sha256": self.receipt_canonical_sha256,
            "profile_id": self.profile_id,
            "profile_canonical_sha256": self.profile_canonical_sha256,
            "checks": [check.to_dict() for check in self.checks],
            "matched": self.matched,
            "detail_code": self.detail_code,
            "failed_check_ids": list(self.failed_check_ids),
            "physical_receipt_verified": self.physical_receipt_verified,
            "hardware_accessed": self.hardware_accessed,
            "physical_release_effect": self.physical_release_effect,
        }

    @property
    def canonical_sha256(self) -> str:
        return _sha256(self.to_dict())


def _parse_identity(raw: object) -> CameraReceiptIdentity:
    identity = _mapping(raw, "identity")
    _exact_fields(identity, _IDENTITY_FIELDS, "identity")
    lens = _mapping(identity.get("lens"), "identity.lens")
    _exact_fields(lens, _LENS_FIELDS, "identity.lens")
    return CameraReceiptIdentity(
        manufacturer=_text(identity.get("manufacturer"), "identity.manufacturer"),
        model=_text(identity.get("model"), "identity.model"),
        sensor=_text(identity.get("sensor"), "identity.sensor"),
        lens=CameraReceiptLensIdentity(
            mount=_text(lens.get("mount"), "identity.lens.mount"),
            focal_length_mm=_finite_positive(
                lens.get("focal_length_mm"),
                "identity.lens.focal_length_mm",
                maximum=1_000.0,
            ),
            supply_relationship=_text(
                lens.get("supply_relationship"),
                "identity.lens.supply_relationship",
            ),
        ),
    )


def parse_b0477_camera_receipt_json(
    payload: bytes, *, source_path: Path | None = None
) -> B0477CameraReceipt:
    """Parse one bounded receipt fixture without opening a camera or robot.

    A wrong but well-formed identity remains representable here.  Call
    :func:`compare_b0477_camera_receipt` to reject it against the selected
    purchase profile.
    """

    if not isinstance(payload, bytes):
        raise CameraReceiptError("camera receipt payload must be bytes")
    if not payload:
        raise CameraReceiptError("camera receipt is empty")
    if len(payload) > MAX_B0477_CAMERA_RECEIPT_BYTES:
        raise CameraReceiptError(
            f"camera receipt exceeds {MAX_B0477_CAMERA_RECEIPT_BYTES} bytes"
        )
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CameraReceiptError("camera receipt must be UTF-8") from exc
    try:
        decoded = json.loads(
            text,
            object_pairs_hook=_object_without_duplicates,
            parse_constant=_reject_constant,
        )
    except CameraReceiptError:
        raise
    except (json.JSONDecodeError, ValueError) as exc:
        raise CameraReceiptError(f"invalid camera receipt JSON: {exc}") from exc

    document = _mapping(decoded, "root")
    _exact_fields(document, _ROOT_FIELDS, "root")
    _exact(document.get("schema"), B0477_CAMERA_RECEIPT_SCHEMA, "schema")
    _exact(document.get("schema_version"), 1, "schema_version")
    receipt_id = _text(document.get("receipt_id"), "receipt_id", maximum=96)
    _exact(document.get("fixture_class"), _FIXTURE_CLASS, "fixture_class")

    target = _mapping(document.get("target_profile"), "target_profile")
    _exact_fields(target, _TARGET_FIELDS, "target_profile")
    target_schema = _text(target.get("schema"), "target_profile.schema")
    target_id = _text(target.get("profile_id"), "target_profile.profile_id")

    evidence = _mapping(document.get("evidence"), "evidence")
    _exact_fields(evidence, _EVIDENCE_FIELDS, "evidence")
    _exact(evidence.get("origin"), _EVIDENCE_ORIGIN, "evidence.origin")
    _exact(
        evidence.get("authority"),
        _EVIDENCE_AUTHORITY,
        "evidence.authority",
    )
    _exact(evidence.get("claim_scope"), _CLAIM_SCOPE, "evidence.claim_scope")

    identity = _parse_identity(document.get("identity"))

    physical = _mapping(
        document.get("unmeasured_physical"), "unmeasured_physical"
    )
    _exact_fields(physical, _UNMEASURED_FIELDS, "unmeasured_physical")
    _exact(
        physical.get("state"),
        _UNMEASURED_STATE,
        "unmeasured_physical.state",
    )
    for name in sorted(_UNMEASURED_VALUE_FIELDS):
        if physical.get(name) is not None:
            raise CameraReceiptError(
                f"unmeasured_physical.{name} must remain null in a "
                "zero-hardware receipt"
            )
    unmeasured = {name: None for name in _UNMEASURED_VALUE_FIELDS}

    authority = _mapping(document.get("authority"), "authority")
    _exact_fields(authority, _AUTHORITY_FIELDS, "authority")
    expected_authority: dict[str, object] = {
        "hardware_accessed": False,
        "physical_receipt_verified": False,
        "camera_opened": False,
        "camera_frames_requested": 0,
        "arm_commands": 0,
        "hardware_presence_authority": False,
        "live_capture_authority": False,
        "calibration_authority": False,
        "robot_motion_authority": False,
        "contact_authority": False,
        "physical_release_effect": "NONE",
    }
    for name, expected in expected_authority.items():
        _exact(authority.get(name), expected, f"authority.{name}")

    # Normalize numeric meaning first, then hash the typed receipt's actual
    # values.  This is intentionally not a digest of an expected B0477 template.
    normalized: dict[str, object] = {
        "schema": B0477_CAMERA_RECEIPT_SCHEMA,
        "schema_version": 1,
        "receipt_id": receipt_id,
        "fixture_class": _FIXTURE_CLASS,
        "target_profile": {"schema": target_schema, "profile_id": target_id},
        "evidence": {
            "origin": _EVIDENCE_ORIGIN,
            "authority": _EVIDENCE_AUTHORITY,
            "claim_scope": _CLAIM_SCOPE,
        },
        "identity": identity.to_dict(),
        "unmeasured_physical": {
            "state": _UNMEASURED_STATE,
            **unmeasured,
        },
        "authority": expected_authority,
    }
    return B0477CameraReceipt(
        source_path=source_path.resolve() if source_path is not None else None,
        source_file_sha256=hashlib.sha256(payload).hexdigest(),
        canonical_sha256=_sha256(normalized),
        receipt_id=receipt_id,
        target_profile_schema=target_schema,
        target_profile_id=target_id,
        identity=identity,
        unmeasured_physical=unmeasured,
    )


def synthetic_b0477_camera_receipt_document(
    *,
    manufacturer: str = "Arducam",
    model: str = "B0477",
    sensor: str = "Sony IMX283",
    lens_mount: str = "C-mount",
    lens_focal_length_mm: float = 16.0,
    lens_supply_relationship: str = _LENS_SUPPLY_RELATIONSHIP,
) -> dict[str, object]:
    """Build explicit zero-authority fixture data for deterministic tests.

    Optional identity values exist solely so fault scenarios can construct and
    hash the actual wrong receipt before the comparator rejects it.
    """

    physical: dict[str, object] = {"state": _UNMEASURED_STATE}
    physical.update({name: None for name in _UNMEASURED_VALUE_FIELDS})
    return {
        "schema": B0477_CAMERA_RECEIPT_SCHEMA,
        "schema_version": 1,
        "receipt_id": "synthetic-b0477-receipt-001",
        "fixture_class": _FIXTURE_CLASS,
        "target_profile": {
            "schema": CAMERA_PROFILE_SCHEMA,
            "profile_id": _TARGET_PROFILE_ID,
        },
        "evidence": {
            "origin": _EVIDENCE_ORIGIN,
            "authority": _EVIDENCE_AUTHORITY,
            "claim_scope": _CLAIM_SCOPE,
        },
        "identity": {
            "manufacturer": manufacturer,
            "model": model,
            "sensor": sensor,
            "lens": {
                "mount": lens_mount,
                "focal_length_mm": lens_focal_length_mm,
                "supply_relationship": lens_supply_relationship,
            },
        },
        "unmeasured_physical": physical,
        "authority": {
            "hardware_accessed": False,
            "physical_receipt_verified": False,
            "camera_opened": False,
            "camera_frames_requested": 0,
            "arm_commands": 0,
            "hardware_presence_authority": False,
            "live_capture_authority": False,
            "calibration_authority": False,
            "robot_motion_authority": False,
            "contact_authority": False,
            "physical_release_effect": "NONE",
        },
    }


def make_synthetic_b0477_camera_receipt(
    *,
    manufacturer: str = "Arducam",
    model: str = "B0477",
    sensor: str = "Sony IMX283",
    lens_mount: str = "C-mount",
    lens_focal_length_mm: float = 16.0,
    lens_supply_relationship: str = _LENS_SUPPLY_RELATIONSHIP,
) -> B0477CameraReceipt:
    """Construct a typed fixture through the same strict JSON boundary."""

    document = synthetic_b0477_camera_receipt_document(
        manufacturer=manufacturer,
        model=model,
        sensor=sensor,
        lens_mount=lens_mount,
        lens_focal_length_mm=lens_focal_length_mm,
        lens_supply_relationship=lens_supply_relationship,
    )
    return parse_b0477_camera_receipt_json(_canonical_bytes(document))


def compare_b0477_camera_receipt(
    receipt: B0477CameraReceipt,
    profile: PurchasedCameraProfile,
) -> B0477CameraReceiptAssessment:
    """Compare actual parsed receipt values to the selected purchase profile."""

    if not isinstance(receipt, B0477CameraReceipt):
        raise TypeError("receipt must be B0477CameraReceipt")
    if not isinstance(profile, PurchasedCameraProfile):
        raise TypeError("profile must be PurchasedCameraProfile")

    identity = receipt.identity
    lens = identity.lens
    checks = (
        CameraReceiptCheck(
            "target_profile_schema_matches",
            receipt.target_profile_schema == CAMERA_PROFILE_SCHEMA,
            "receipt target schema matches the purchased-camera schema",
        ),
        CameraReceiptCheck(
            "target_profile_id_matches",
            receipt.target_profile_id == profile.profile_id,
            "receipt target profile ID matches the loaded purchase profile",
        ),
        CameraReceiptCheck(
            "manufacturer_matches",
            identity.manufacturer == profile.manufacturer == "Arducam",
            "receipt manufacturer must be exactly Arducam",
        ),
        CameraReceiptCheck(
            "model_matches",
            identity.model == profile.model == "B0477",
            "receipt catalog model must be exactly B0477",
        ),
        CameraReceiptCheck(
            "sensor_matches",
            identity.sensor == profile.sensor == "Sony IMX283",
            "receipt sensor must be exactly Sony IMX283",
        ),
        CameraReceiptCheck(
            "lens_mount_matches",
            lens.mount == profile.lens_mount == "C-mount",
            "receipt lens mount must be exactly C-mount",
        ),
        CameraReceiptCheck(
            "lens_focal_length_matches",
            lens.focal_length_mm == profile.focal_length_mm == 16.0,
            "receipt lens focal length must be exactly 16 mm",
        ),
        CameraReceiptCheck(
            "lens_supply_relationship_matches",
            lens.supply_relationship == _LENS_SUPPLY_RELATIONSHIP,
            "receipt lens must be the nominal lens included with B0477",
        ),
        CameraReceiptCheck(
            "physical_measurements_remain_unmeasured",
            all(value is None for value in receipt.unmeasured_physical.values()),
            "zero-hardware receipt retains null physical measurements",
        ),
        CameraReceiptCheck(
            "zero_hardware_authority_held",
            not receipt.hardware_accessed
            and not receipt.physical_receipt_verified
            and not receipt.live_ready,
            "receipt fixture grants no physical or live authority",
        ),
    )
    return B0477CameraReceiptAssessment(
        receipt_id=receipt.receipt_id,
        receipt_canonical_sha256=receipt.canonical_sha256,
        profile_id=profile.profile_id,
        profile_canonical_sha256=profile.canonical_sha256,
        checks=checks,
    )


def require_matching_b0477_camera_receipt(
    receipt: B0477CameraReceipt,
    profile: PurchasedCameraProfile,
) -> B0477CameraReceiptAssessment:
    """Return a matching assessment or raise with stable failed check IDs."""

    assessment = compare_b0477_camera_receipt(receipt, profile)
    if not assessment.matched:
        raise CameraReceiptMismatchError(
            "camera receipt does not match selected B0477 configuration; "
            f"failed_checks={list(assessment.failed_check_ids)!r}; "
            f"receipt_sha256={assessment.receipt_canonical_sha256}"
        )
    return assessment


__all__ = [
    "B0477_CAMERA_RECEIPT_ASSESSMENT_SCHEMA",
    "B0477_CAMERA_RECEIPT_SCHEMA",
    "MAX_B0477_CAMERA_RECEIPT_BYTES",
    "B0477CameraReceipt",
    "B0477CameraReceiptAssessment",
    "CameraReceiptCheck",
    "CameraReceiptError",
    "CameraReceiptIdentity",
    "CameraReceiptLensIdentity",
    "CameraReceiptMismatchError",
    "compare_b0477_camera_receipt",
    "make_synthetic_b0477_camera_receipt",
    "parse_b0477_camera_receipt_json",
    "require_matching_b0477_camera_receipt",
    "synthetic_b0477_camera_receipt_document",
]
