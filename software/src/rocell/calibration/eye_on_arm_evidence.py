"""Raw-feedback and pinned-FK evidence for offline eye-on-arm datasets.

This module closes the gap between a stored joint vector and the stored
``Wv_T_E`` carrier pose.  It remains entirely offline: callers provide a
content-pinned URDF, an immutable raw T=1051 evidence package, and a measured
``link2_T_E`` registration.  No transport, camera, or motion API is imported.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence

from rocell.arm.feedback import FeedbackError, parse_feedback_1051
from rocell.geometry.transforms import RigidTransform, Rotation3, Vec3
from rocell.geometry.urdf import JointPosition, JointStateError, UrdfError, UrdfModel

from .eye_on_arm_dataset import EyeOnArmDataset, JOINT_ORDER


SCHEMA = "rocell.eye_on_arm_capture_evidence.v1"
MAX_EVIDENCE_BYTES = 4 * 1024 * 1024
MAX_KINEMATIC_MODEL_BYTES = 2 * 1024 * 1024
MAX_EVIDENCE_RECORDS = 128
# This is the exact repository model reviewed for the current offline FK
# projection.  A dataset and evidence package are not allowed to nominate a
# different model merely by agreeing on a different digest: that would make
# the supposed model pin circular.
PINNED_ROARM_M3_KINEMATIC_SHA256 = (
    "a565718e7d74b07702802cf41eb9549a6e38e50b5e80aa9b887ab1ae3d0d8190"
)
FEEDBACK_FIELDS = ("b", "s", "e", "t", "r", "g")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.-]+$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class EyeOnArmEvidenceError(ValueError):
    """Capture evidence or pinned kinematic verification is invalid."""


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise EyeOnArmEvidenceError(f"{label} must match {_IDENTIFIER.pattern}")
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EyeOnArmEvidenceError(f"{label} must be a non-empty string")
    return value.strip()


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise EyeOnArmEvidenceError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _integer(value: object, label: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise EyeOnArmEvidenceError(f"{label} must be an integer >= {minimum}")
    return value


def _finite(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EyeOnArmEvidenceError(f"{label} must be a real number")
    result = float(value)
    if not math.isfinite(result):
        raise EyeOnArmEvidenceError(f"{label} must be finite")
    return result


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise EyeOnArmEvidenceError(f"{label} must be an object with string keys")
    return value


def _exact(value: Mapping[str, Any], fields: set[str], label: str) -> None:
    actual = set(value)
    if actual != fields:
        raise EyeOnArmEvidenceError(
            f"{label} fields differ; missing={sorted(fields - actual)}, "
            f"extra={sorted(actual - fields)}"
        )


def _sequence(value: object, length: int, label: str) -> tuple[Any, ...]:
    if not isinstance(value, (list, tuple)) or len(value) != length:
        raise EyeOnArmEvidenceError(f"{label} must contain exactly {length} values")
    return tuple(value)


def _freeze_json(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise EyeOnArmEvidenceError("Raw feedback contains a nonfinite number")
        return value
    if isinstance(value, Mapping):
        return MappingProxyType(
            {
                _string(key, "raw feedback key"): _freeze_json(item)
                for key, item in value.items()
            }
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    raise EyeOnArmEvidenceError(
        f"Raw feedback contains unsupported {type(value).__name__}"
    )


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def _canonical_hash(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        _thaw_json(value), sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _transform(value: object, label: str) -> RigidTransform:
    document = _mapping(value, label)
    _exact(
        document,
        {"to_frame", "from_frame", "rotation_row_major", "translation_mm"},
        label,
    )
    try:
        return RigidTransform(
            parent_frame=_string(document["to_frame"], f"{label}.to_frame"),
            child_frame=_string(document["from_frame"], f"{label}.from_frame"),
            rotation=Rotation3(
                tuple(
                    _finite(item, f"{label}.rotation")
                    for item in _sequence(
                        document["rotation_row_major"], 9, f"{label}.rotation"
                    )
                )
            ),
            translation_mm=Vec3.from_iterable(
                _finite(item, f"{label}.translation")
                for item in _sequence(
                    document["translation_mm"], 3, f"{label}.translation"
                )
            ),
        )
    except (TypeError, ValueError) as exc:
        if isinstance(exc, EyeOnArmEvidenceError):
            raise
        raise EyeOnArmEvidenceError(f"{label} is not a rigid transform: {exc}") from exc


def _transform_dict(value: RigidTransform) -> dict[str, Any]:
    return {
        "to_frame": value.parent_frame,
        "from_frame": value.child_frame,
        "rotation_row_major": list(value.rotation.matrix),
        "translation_mm": [
            value.translation_mm.x,
            value.translation_mm.y,
            value.translation_mm.z,
        ],
    }


@dataclass(frozen=True, slots=True)
class JointReferenceRule:
    """Installed-reference projection ``q_model = sign*q_feedback + offset``."""

    urdf_joint: str
    feedback_field: str
    sign: int
    offset_rad: float

    def __post_init__(self) -> None:
        _identifier(self.urdf_joint, "urdf_joint")
        _identifier(self.feedback_field, "feedback_field")
        if self.sign not in {-1, 1} or isinstance(self.sign, bool):
            raise EyeOnArmEvidenceError("Joint reference sign must be -1 or 1")
        object.__setattr__(self, "offset_rad", _finite(self.offset_rad, "offset_rad"))

    def project(self, feedback_rad: object) -> float:
        return self.sign * _finite(feedback_rad, self.feedback_field) + self.offset_rad

    def to_dict(self) -> dict[str, Any]:
        return {
            "urdf_joint": self.urdf_joint,
            "feedback_field": self.feedback_field,
            "sign": self.sign,
            "offset_rad": self.offset_rad,
        }


@dataclass(frozen=True, slots=True)
class RawJointFeedbackEvidence:
    """One content-hashed decoded T=1051 object tied to a dataset sample.

    Exact newline-terminated wire bytes live in ``EyeOnArmCaptureBundle``;
    this value alone must not be described as original transport evidence.
    """

    sample_id: str
    joint_sequence: int
    timestamp_ns: int
    clock_id: str
    fields_sha256: str
    fields: Mapping[str, Any]

    def __post_init__(self) -> None:
        _identifier(self.sample_id, "sample_id")
        _integer(self.joint_sequence, "joint_sequence")
        _integer(self.timestamp_ns, "timestamp_ns")
        _identifier(self.clock_id, "clock_id")
        _digest(self.fields_sha256, "fields_sha256")
        if not isinstance(self.fields, Mapping):
            raise EyeOnArmEvidenceError("fields must be a raw feedback object")
        frozen = _freeze_json(self.fields)
        object.__setattr__(self, "fields", frozen)
        if _canonical_hash(frozen) != self.fields_sha256:
            raise EyeOnArmEvidenceError(
                f"Raw feedback hash mismatch for sample {self.sample_id}"
            )
        try:
            parsed = parse_feedback_1051(_thaw_json(frozen))
        except FeedbackError as exc:
            raise EyeOnArmEvidenceError(
                f"Invalid T=1051 evidence for sample {self.sample_id}: {exc}"
            ) from exc
        joint_values = (
            parsed.base_rad,
            parsed.shoulder_rad,
            parsed.elbow_rad,
            parsed.wrist_pitch_rad,
            parsed.wrist_roll_rad,
            parsed.gripper_rad,
        )
        if any(value is None for value in joint_values):
            raise EyeOnArmEvidenceError(
                f"Raw feedback for sample {self.sample_id} lacks a complete six-joint state"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "joint_sequence": self.joint_sequence,
            "timestamp_ns": self.timestamp_ns,
            "clock_id": self.clock_id,
            "fields_sha256": self.fields_sha256,
            "fields": _thaw_json(self.fields),
        }


@dataclass(frozen=True, slots=True)
class EyeOnArmCaptureEvidence:
    """Immutable raw capture, reference, carrier, and build evidence package."""

    evidence_id: str
    dataset_id: str
    dataset_sha256: str
    manifest_id: str
    active_build_id: str
    camera_usb_identity_sha256: str
    camera_settings_sha256: str
    timing_qualification_sha256: str
    kinematic_model_sha256: str
    carrier_registration_sha256: str
    robot_reference_sha256: str
    link2_T_E: RigidTransform
    joint_reference: tuple[JointReferenceRule, ...]
    raw_joint_feedback: tuple[RawJointFeedbackEvidence, ...]
    schema: str = SCHEMA
    physical_release_effect: str = "NONE"

    def __post_init__(self) -> None:
        if self.schema != SCHEMA:
            raise EyeOnArmEvidenceError(f"Unsupported capture evidence schema {self.schema!r}")
        _identifier(self.evidence_id, "evidence_id")
        _identifier(self.dataset_id, "dataset_id")
        _digest(self.dataset_sha256, "dataset_sha256")
        _string(self.manifest_id, "manifest_id")
        _string(self.active_build_id, "active_build_id")
        for field_name in (
            "camera_usb_identity_sha256",
            "camera_settings_sha256",
            "timing_qualification_sha256",
            "kinematic_model_sha256",
            "carrier_registration_sha256",
            "robot_reference_sha256",
        ):
            _digest(getattr(self, field_name), field_name)
        if self.physical_release_effect != "NONE":
            raise EyeOnArmEvidenceError("Capture evidence cannot release physical motion")
        if (
            self.link2_T_E.parent_frame != "link2"
            or self.link2_T_E.child_frame != "E"
        ):
            raise EyeOnArmEvidenceError("Carrier registration must be link2_T_E")
        rules = tuple(self.joint_reference)
        if tuple(rule.urdf_joint for rule in rules) != JOINT_ORDER:
            raise EyeOnArmEvidenceError("Joint reference must use exact URDF joint order")
        if tuple(rule.feedback_field for rule in rules) != FEEDBACK_FIELDS:
            raise EyeOnArmEvidenceError("Joint reference must map exact T=1051 b/s/e/t/r/g fields")
        object.__setattr__(self, "joint_reference", rules)
        raw = tuple(self.raw_joint_feedback)
        if len(raw) > MAX_EVIDENCE_RECORDS:
            raise EyeOnArmEvidenceError(
                f"Capture evidence exceeds {MAX_EVIDENCE_RECORDS} raw feedback records"
            )
        if len({record.sample_id for record in raw}) != len(raw):
            raise EyeOnArmEvidenceError("Raw feedback sample ids must be unique")
        object.__setattr__(self, "raw_joint_feedback", raw)

    @property
    def content_hash(self) -> str:
        encoded = json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "evidence_id": self.evidence_id,
            "dataset_id": self.dataset_id,
            "dataset_sha256": self.dataset_sha256,
            "manifest_id": self.manifest_id,
            "active_build_id": self.active_build_id,
            "physical_release_effect": self.physical_release_effect,
            "capture_identity": {
                "camera_usb_identity_sha256": self.camera_usb_identity_sha256,
                "camera_settings_sha256": self.camera_settings_sha256,
                "timing_qualification_sha256": self.timing_qualification_sha256,
            },
            "kinematics": {
                "model_sha256": self.kinematic_model_sha256,
                "root_frame": "world",
                "carrier_link": "link2",
                "carrier_frame": "E",
                "carrier_registration_sha256": self.carrier_registration_sha256,
                "robot_reference_sha256": self.robot_reference_sha256,
                "link2_T_E": _transform_dict(self.link2_T_E),
                "joint_reference": [rule.to_dict() for rule in self.joint_reference],
            },
            "raw_joint_feedback": [record.to_dict() for record in self.raw_joint_feedback],
        }


@dataclass(frozen=True, slots=True)
class EyeOnArmFkVerificationPolicy:
    maximum_joint_projection_error_rad: float = 1e-9
    maximum_carrier_translation_error_mm: float = 1e-6
    maximum_carrier_rotation_error_rad: float = 1e-8
    maximum_records: int = 128
    policy_id: str = "ROCELL-EYE-ON-ARM-FK-VERIFY-001"

    def __post_init__(self) -> None:
        _identifier(self.policy_id, "policy_id")
        for field_name in (
            "maximum_joint_projection_error_rad",
            "maximum_carrier_translation_error_mm",
            "maximum_carrier_rotation_error_rad",
        ):
            value = _finite(getattr(self, field_name), field_name)
            if value <= 0.0:
                raise EyeOnArmEvidenceError(f"{field_name} must be positive")
        _integer(self.maximum_records, "maximum_records", minimum=1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "maximum_joint_projection_error_rad": self.maximum_joint_projection_error_rad,
            "maximum_carrier_translation_error_mm": self.maximum_carrier_translation_error_mm,
            "maximum_carrier_rotation_error_rad": self.maximum_carrier_rotation_error_rad,
            "maximum_records": self.maximum_records,
        }


DEFAULT_FK_VERIFICATION_POLICY = EyeOnArmFkVerificationPolicy()


@dataclass(frozen=True, slots=True)
class FkSampleVerification:
    sample_id: str
    passed: bool
    maximum_joint_projection_error_rad: float
    carrier_translation_error_mm: float
    carrier_rotation_error_rad: float
    recomputed_Wv_T_E: RigidTransform
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        _identifier(self.sample_id, "sample_id")
        if not isinstance(self.passed, bool):
            raise EyeOnArmEvidenceError("FK sample passed must be a bool")
        for field_name in (
            "maximum_joint_projection_error_rad",
            "carrier_translation_error_mm",
            "carrier_rotation_error_rad",
        ):
            value = _finite(getattr(self, field_name), field_name)
            if value < 0.0:
                raise EyeOnArmEvidenceError(f"{field_name} must be non-negative")
        if (
            self.recomputed_Wv_T_E.parent_frame != "Wv"
            or self.recomputed_Wv_T_E.child_frame != "E"
        ):
            raise EyeOnArmEvidenceError("Recomputed carrier pose must be Wv_T_E")
        reasons = tuple(_identifier(reason, "FK reason") for reason in self.reasons)
        if len(set(reasons)) != len(reasons):
            raise EyeOnArmEvidenceError("FK sample reasons must be unique")
        object.__setattr__(self, "reasons", reasons)
        if self.passed == bool(reasons):
            raise EyeOnArmEvidenceError(
                "FK sample passes exactly when its reason list is empty"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "passed": self.passed,
            "maximum_joint_projection_error_rad": self.maximum_joint_projection_error_rad,
            "carrier_translation_error_mm": self.carrier_translation_error_mm,
            "carrier_rotation_error_rad": self.carrier_rotation_error_rad,
            "recomputed_Wv_T_E": _transform_dict(self.recomputed_Wv_T_E),
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True, slots=True)
class EyeOnArmFkVerification:
    dataset_id: str
    dataset_hash: str
    evidence_id: str
    evidence_hash: str
    kinematic_model_sha256: str
    policy: EyeOnArmFkVerificationPolicy
    samples: tuple[FkSampleVerification, ...]
    status: str
    physical_release_effect: str = "NONE"

    def __post_init__(self) -> None:
        _identifier(self.dataset_id, "dataset_id")
        _digest(self.dataset_hash, "dataset_hash")
        _identifier(self.evidence_id, "evidence_id")
        _digest(self.evidence_hash, "evidence_hash")
        _digest(self.kinematic_model_sha256, "kinematic_model_sha256")
        if self.kinematic_model_sha256 != PINNED_ROARM_M3_KINEMATIC_SHA256:
            raise EyeOnArmEvidenceError(
                "FK verification must use the reviewed RoArm-M3 kinematic model"
            )
        if not isinstance(self.policy, EyeOnArmFkVerificationPolicy):
            raise TypeError("policy must be an EyeOnArmFkVerificationPolicy")
        if self.physical_release_effect != "NONE":
            raise EyeOnArmEvidenceError("FK verification cannot release physical motion")
        samples = tuple(self.samples)
        if len({sample.sample_id for sample in samples}) != len(samples):
            raise EyeOnArmEvidenceError("FK verification sample ids must be unique")
        for sample in samples:
            expected_reasons: list[str] = []
            if (
                sample.maximum_joint_projection_error_rad
                > self.policy.maximum_joint_projection_error_rad
            ):
                expected_reasons.append("JOINT_PROJECTION_MISMATCH")
            if (
                sample.carrier_translation_error_mm
                > self.policy.maximum_carrier_translation_error_mm
            ):
                expected_reasons.append("CARRIER_TRANSLATION_MISMATCH")
            if (
                sample.carrier_rotation_error_rad
                > self.policy.maximum_carrier_rotation_error_rad
            ):
                expected_reasons.append("CARRIER_ROTATION_MISMATCH")
            if sample.reasons != tuple(expected_reasons):
                raise EyeOnArmEvidenceError(
                    f"FK sample {sample.sample_id} reasons differ from serialized policy"
                )
        object.__setattr__(self, "samples", samples)
        expected = "PASS" if samples and all(sample.passed for sample in samples) else "FAIL"
        if self.status != expected:
            raise EyeOnArmEvidenceError("FK verification status differs from sample results")

    @property
    def all_passed(self) -> bool:
        return self.status == "PASS"

    @property
    def report_hash(self) -> str:
        encoded = json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "rocell.eye_on_arm_fk_verification.v1",
            "status": self.status,
            "physical_release_effect": self.physical_release_effect,
            "dataset_id": self.dataset_id,
            "dataset_hash": self.dataset_hash,
            "evidence_id": self.evidence_id,
            "evidence_hash": self.evidence_hash,
            "kinematic_model_sha256": self.kinematic_model_sha256,
            "policy": self.policy.to_dict(),
            "samples": [sample.to_dict() for sample in self.samples],
        }


def _rotation_error(left: Rotation3, right: Rotation3) -> float:
    # Avoid acos amplification when both stored and recomputed matrices are
    # bit-identical (or differ only at machine roundoff).
    if left.almost_equal(right, absolute_tolerance=1e-15):
        return 0.0
    delta = left.inverse().compose(right).matrix
    cosine = (delta[0] + delta[4] + delta[8] - 1.0) * 0.5
    return math.acos(max(-1.0, min(1.0, cosine)))


def verify_eye_on_arm_fk(
    dataset: EyeOnArmDataset,
    evidence: EyeOnArmCaptureEvidence,
    kinematic_model_path: str | Path,
    *,
    policy: EyeOnArmFkVerificationPolicy = DEFAULT_FK_VERIFICATION_POLICY,
) -> EyeOnArmFkVerification:
    """Recompute every ``Wv_T_E`` from raw T=1051 fields and pinned URDF FK."""

    if not isinstance(dataset, EyeOnArmDataset):
        raise TypeError("dataset must be an EyeOnArmDataset")
    if not isinstance(evidence, EyeOnArmCaptureEvidence):
        raise TypeError("evidence must be an EyeOnArmCaptureEvidence")
    if not isinstance(policy, EyeOnArmFkVerificationPolicy):
        raise TypeError("policy must be an EyeOnArmFkVerificationPolicy")
    if evidence.dataset_id != dataset.dataset_id or evidence.dataset_sha256 != dataset.content_hash:
        raise EyeOnArmEvidenceError("Capture evidence is bound to a different dataset")
    if len(dataset.samples) > policy.maximum_records:
        raise EyeOnArmEvidenceError("Dataset exceeds FK verification record limit")
    if len(evidence.raw_joint_feedback) != len(dataset.samples):
        raise EyeOnArmEvidenceError(
            "Raw feedback record count differs from dataset sample count"
        )
    if len(evidence.raw_joint_feedback) > policy.maximum_records:
        raise EyeOnArmEvidenceError("Raw feedback exceeds FK verification record limit")
    for source_id, evidence_hash in (
        ("carrier_kinematic_model", evidence.kinematic_model_sha256),
        ("carrier_registration", evidence.carrier_registration_sha256),
        ("robot_reference", evidence.robot_reference_sha256),
    ):
        if dataset.source_hashes[source_id] != evidence_hash:
            raise EyeOnArmEvidenceError(f"Evidence hash differs from dataset {source_id}")
    raw_by_id = {record.sample_id: record for record in evidence.raw_joint_feedback}
    if set(raw_by_id) != {sample.sample_id for sample in dataset.samples}:
        raise EyeOnArmEvidenceError("Raw feedback records do not exactly cover dataset samples")

    model_path = Path(kinematic_model_path)
    try:
        size = model_path.stat().st_size
        if size > MAX_KINEMATIC_MODEL_BYTES:
            raise EyeOnArmEvidenceError("Kinematic model exceeds size limit")
        with model_path.open("rb") as stream:
            raw_model = stream.read(MAX_KINEMATIC_MODEL_BYTES + 1)
    except OSError as exc:
        raise EyeOnArmEvidenceError(f"Could not read kinematic model: {exc}") from exc
    if len(raw_model) > MAX_KINEMATIC_MODEL_BYTES:
        raise EyeOnArmEvidenceError("Kinematic model exceeds size limit")
    model_hash = hashlib.sha256(raw_model).hexdigest()
    if model_hash != evidence.kinematic_model_sha256:
        raise EyeOnArmEvidenceError("Pinned kinematic model hash mismatch")
    if model_hash != PINNED_ROARM_M3_KINEMATIC_SHA256:
        raise EyeOnArmEvidenceError(
            "Kinematic model is not the reviewed RoArm-M3 projection"
        )
    try:
        model = UrdfModel.from_xml(
            raw_model.decode("utf-8"), source_name=str(model_path)
        )
    except (OSError, UnicodeError, UrdfError) as exc:
        raise EyeOnArmEvidenceError(f"Could not load pinned kinematic model: {exc}") from exc
    if model.root_link != "world" or "link2" not in model.link_names:
        raise EyeOnArmEvidenceError("Kinematic model must preserve world root and link2 carrier")
    if set(model.movable_joint_names) != set(JOINT_ORDER):
        raise EyeOnArmEvidenceError("Kinematic model movable joints differ from dataset contract")

    rule_by_joint = {rule.urdf_joint: rule for rule in evidence.joint_reference}
    results: list[FkSampleVerification] = []
    for sample in dataset.samples:
        raw_record = raw_by_id[sample.sample_id]
        if (
            raw_record.joint_sequence != sample.joint_state.sequence
            or raw_record.timestamp_ns != sample.joint_state.timestamp_ns
            or raw_record.clock_id != sample.joint_state.clock_id
        ):
            raise EyeOnArmEvidenceError(
                f"Raw feedback synchronization differs for sample {sample.sample_id}"
            )
        raw_fields = _thaw_json(raw_record.fields)
        projected = {
            joint: rule_by_joint[joint].project(raw_fields[rule_by_joint[joint].feedback_field])
            for joint in JOINT_ORDER
        }
        stored = sample.joint_state.positions_by_name
        joint_error = max(abs(projected[joint] - stored[joint]) for joint in JOINT_ORDER)
        try:
            root_transforms = model.forward_kinematics(
                {
                    joint: JointPosition.radians(projected[joint])
                    for joint in JOINT_ORDER
                }
            )
        except (JointStateError, UrdfError, ValueError) as exc:
            raise EyeOnArmEvidenceError(
                f"Pinned FK failed for sample {sample.sample_id}: {exc}"
            ) from exc
        root_T_link2 = root_transforms["link2"]
        Wv_T_link2 = RigidTransform(
            "Wv", "link2", root_T_link2.rotation, root_T_link2.translation_mm
        )
        recomputed = Wv_T_link2.compose(evidence.link2_T_E)
        stored_carrier = sample.carrier_pose.transform
        translation_error = (recomputed.translation_mm - stored_carrier.translation_mm).norm
        rotation_error = _rotation_error(recomputed.rotation, stored_carrier.rotation)
        reasons: list[str] = []
        if joint_error > policy.maximum_joint_projection_error_rad:
            reasons.append("JOINT_PROJECTION_MISMATCH")
        if translation_error > policy.maximum_carrier_translation_error_mm:
            reasons.append("CARRIER_TRANSLATION_MISMATCH")
        if rotation_error > policy.maximum_carrier_rotation_error_rad:
            reasons.append("CARRIER_ROTATION_MISMATCH")
        results.append(
            FkSampleVerification(
                sample_id=sample.sample_id,
                passed=not reasons,
                maximum_joint_projection_error_rad=joint_error,
                carrier_translation_error_mm=translation_error,
                carrier_rotation_error_rad=rotation_error,
                recomputed_Wv_T_E=recomputed,
                reasons=tuple(reasons),
            )
        )
    samples = tuple(results)
    return EyeOnArmFkVerification(
        dataset_id=dataset.dataset_id,
        dataset_hash=dataset.content_hash,
        evidence_id=evidence.evidence_id,
        evidence_hash=evidence.content_hash,
        kinematic_model_sha256=model_hash,
        policy=policy,
        samples=samples,
        status="PASS" if all(sample.passed for sample in samples) else "FAIL",
    )


def _rule(value: object, index: int) -> JointReferenceRule:
    document = _mapping(value, f"joint_reference[{index}]")
    _exact(document, {"urdf_joint", "feedback_field", "sign", "offset_rad"}, "joint_reference")
    return JointReferenceRule(
        urdf_joint=_identifier(document["urdf_joint"], "urdf_joint"),
        feedback_field=_identifier(document["feedback_field"], "feedback_field"),
        sign=_integer(document["sign"], "sign", minimum=-1),
        offset_rad=_finite(document["offset_rad"], "offset_rad"),
    )


def _raw_feedback(value: object, index: int) -> RawJointFeedbackEvidence:
    document = _mapping(value, f"raw_joint_feedback[{index}]")
    _exact(
        document,
        {"sample_id", "joint_sequence", "timestamp_ns", "clock_id", "fields_sha256", "fields"},
        "raw_joint_feedback",
    )
    return RawJointFeedbackEvidence(
        sample_id=_identifier(document["sample_id"], "sample_id"),
        joint_sequence=_integer(document["joint_sequence"], "joint_sequence"),
        timestamp_ns=_integer(document["timestamp_ns"], "timestamp_ns"),
        clock_id=_identifier(document["clock_id"], "clock_id"),
        fields_sha256=_digest(document["fields_sha256"], "fields_sha256"),
        fields=_mapping(document["fields"], "fields"),
    )


def eye_on_arm_capture_evidence_from_dict(
    value: Mapping[str, Any],
) -> EyeOnArmCaptureEvidence:
    root = _mapping(value, "capture evidence")
    _exact(
        root,
        {
            "schema",
            "evidence_id",
            "dataset_id",
            "dataset_sha256",
            "manifest_id",
            "active_build_id",
            "physical_release_effect",
            "capture_identity",
            "kinematics",
            "raw_joint_feedback",
        },
        "capture evidence",
    )
    identity = _mapping(root["capture_identity"], "capture_identity")
    _exact(
        identity,
        {
            "camera_usb_identity_sha256",
            "camera_settings_sha256",
            "timing_qualification_sha256",
        },
        "capture_identity",
    )
    kinematics = _mapping(root["kinematics"], "kinematics")
    _exact(
        kinematics,
        {
            "model_sha256",
            "root_frame",
            "carrier_link",
            "carrier_frame",
            "carrier_registration_sha256",
            "robot_reference_sha256",
            "link2_T_E",
            "joint_reference",
        },
        "kinematics",
    )
    if (
        kinematics["root_frame"] != "world"
        or kinematics["carrier_link"] != "link2"
        or kinematics["carrier_frame"] != "E"
    ):
        raise EyeOnArmEvidenceError("Kinematic frames must remain world/link2/E")
    rules = kinematics["joint_reference"]
    raw_records = root["raw_joint_feedback"]
    if not isinstance(rules, (list, tuple)) or not isinstance(raw_records, (list, tuple)):
        raise EyeOnArmEvidenceError("joint_reference and raw_joint_feedback must be arrays")
    return EyeOnArmCaptureEvidence(
        schema=_string(root["schema"], "schema"),
        evidence_id=_identifier(root["evidence_id"], "evidence_id"),
        dataset_id=_identifier(root["dataset_id"], "dataset_id"),
        dataset_sha256=_digest(root["dataset_sha256"], "dataset_sha256"),
        manifest_id=_string(root["manifest_id"], "manifest_id"),
        active_build_id=_string(root["active_build_id"], "active_build_id"),
        physical_release_effect=_string(root["physical_release_effect"], "physical_release_effect"),
        camera_usb_identity_sha256=_digest(
            identity["camera_usb_identity_sha256"], "camera_usb_identity_sha256"
        ),
        camera_settings_sha256=_digest(
            identity["camera_settings_sha256"], "camera_settings_sha256"
        ),
        timing_qualification_sha256=_digest(
            identity["timing_qualification_sha256"], "timing_qualification_sha256"
        ),
        kinematic_model_sha256=_digest(kinematics["model_sha256"], "model_sha256"),
        carrier_registration_sha256=_digest(
            kinematics["carrier_registration_sha256"], "carrier_registration_sha256"
        ),
        robot_reference_sha256=_digest(
            kinematics["robot_reference_sha256"], "robot_reference_sha256"
        ),
        link2_T_E=_transform(kinematics["link2_T_E"], "link2_T_E"),
        joint_reference=tuple(_rule(item, index) for index, item in enumerate(rules)),
        raw_joint_feedback=tuple(
            _raw_feedback(item, index) for index, item in enumerate(raw_records)
        ),
    )


def _duplicates(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise EyeOnArmEvidenceError(f"Duplicate JSON field {key!r}")
        result[key] = value
    return result


def load_eye_on_arm_capture_evidence(
    path: str | Path,
    *,
    expected_file_sha256: str | None = None,
) -> EyeOnArmCaptureEvidence:
    source = Path(path)
    try:
        if source.stat().st_size > MAX_EVIDENCE_BYTES:
            raise EyeOnArmEvidenceError("Capture evidence exceeds file size limit")
        with source.open("rb") as stream:
            raw = stream.read(MAX_EVIDENCE_BYTES + 1)
    except OSError as exc:
        raise EyeOnArmEvidenceError(f"Could not read capture evidence: {exc}") from exc
    if len(raw) > MAX_EVIDENCE_BYTES:
        raise EyeOnArmEvidenceError("Capture evidence exceeds file size limit")
    file_hash = hashlib.sha256(raw).hexdigest()
    if expected_file_sha256 is not None and file_hash != _digest(
        expected_file_sha256, "expected_file_sha256"
    ):
        raise EyeOnArmEvidenceError("Capture evidence file hash mismatch")
    try:
        document = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_duplicates,
            parse_constant=lambda value: (_ for _ in ()).throw(
                EyeOnArmEvidenceError(f"Nonfinite JSON constant {value!r}")
            ),
        )
    except (UnicodeError, json.JSONDecodeError, EyeOnArmEvidenceError) as exc:
        raise EyeOnArmEvidenceError(f"Invalid capture evidence: {exc}") from exc
    if not isinstance(document, dict):
        raise EyeOnArmEvidenceError("Capture evidence root must be an object")
    return eye_on_arm_capture_evidence_from_dict(document)
