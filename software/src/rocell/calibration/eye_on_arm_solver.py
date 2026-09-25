"""Numerical eye-on-arm candidate solving with zero physical authority.

NumPy is imported only when :func:`solve_eye_on_arm` is called.  Dataset
parsing, calibration status, and the rest of RoCell therefore remain usable
without numerical or computer-vision wheels.  OpenCV is intentionally not a
dependency of this solver: the small AX=XB implementation below is auditable,
uses the repository's frame-labelled transforms at its boundary, and avoids a
second set of transform-direction conventions.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib
import json
import math
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from rocell.geometry.transforms import RigidTransform, Rotation3, Vec3

from .artifacts import ArtifactState, CalibrationArtifact
from .eye_on_arm_dataset import EyeOnArmDataset, EyeOnArmSample


class EyeOnArmSolverUnavailable(RuntimeError):
    """The isolated numerical calibration dependency is unavailable."""


class EyeOnArmSolveError(ValueError):
    """The dataset cannot support an observable eye-on-arm candidate solve."""


def _numpy() -> Any:
    try:
        return importlib.import_module("numpy")
    except Exception as exc:  # NumPy can fail at import time due to binary ABI issues.
        raise EyeOnArmSolverUnavailable(
            "Eye-on-arm solving requires the optional 'calibration' NumPy dependency"
        ) from exc


@dataclass(frozen=True, slots=True)
class EyeOnArmSolverPolicy:
    """Complete, hashed resource/observability/diagnostic solver policy."""

    policy_id: str = "ROCELL-EYE-ON-ARM-DIAGNOSTIC-001"
    minimum_training_samples: int = 5
    minimum_held_out_samples: int = 1
    maximum_samples: int = 128
    maximum_relative_motion_pairs: int = 4096
    near_duplicate_translation_mm: float = 0.1
    near_duplicate_rotation_rad: float = 0.001
    minimum_carrier_rotation_axis_rank: int = 2
    minimum_rotation_span_rad: float = 0.05
    minimum_second_axis_excitation_rad: float = 0.02
    minimum_rotation_nullspace_gap: float = 1e-6
    maximum_translation_condition_number: float = 1e8
    minimum_translation_rank: int = 3
    maximum_rotation_fit_ratio: float = 0.25
    maximum_training_rms_translation_mm: float = 2.0
    maximum_training_max_translation_mm: float = 5.0
    maximum_training_rms_rotation_rad: float = 0.02
    maximum_training_max_rotation_rad: float = 0.05
    maximum_held_out_rms_translation_mm: float = 3.0
    maximum_held_out_max_translation_mm: float = 6.0
    maximum_held_out_rms_rotation_rad: float = 0.03
    maximum_held_out_max_rotation_rad: float = 0.06
    maximum_relative_rms_translation_mm: float = 2.0
    maximum_relative_max_translation_mm: float = 5.0
    maximum_relative_rms_rotation_rad: float = 0.02
    maximum_relative_max_rotation_rad: float = 0.05

    def __post_init__(self) -> None:
        if not self.policy_id or not isinstance(self.policy_id, str):
            raise ValueError("policy_id must be a non-empty string")
        for value, label in (
            (self.minimum_training_samples, "minimum_training_samples"),
            (self.minimum_held_out_samples, "minimum_held_out_samples"),
            (self.maximum_samples, "maximum_samples"),
            (self.maximum_relative_motion_pairs, "maximum_relative_motion_pairs"),
            (self.minimum_carrier_rotation_axis_rank, "minimum_carrier_rotation_axis_rank"),
            (self.minimum_translation_rank, "minimum_translation_rank"),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{label} must be a positive integer")
        if self.minimum_carrier_rotation_axis_rank > 3:
            raise ValueError("minimum_carrier_rotation_axis_rank cannot exceed 3")
        if self.minimum_translation_rank > 3:
            raise ValueError("minimum_translation_rank cannot exceed 3")
        if self.maximum_samples < (
            self.minimum_training_samples + self.minimum_held_out_samples
        ):
            raise ValueError("maximum_samples cannot be below the minimum split size")
        minimum_pairs = (
            self.minimum_training_samples * (self.minimum_training_samples - 1) // 2
        )
        if self.maximum_relative_motion_pairs < minimum_pairs:
            raise ValueError(
                "maximum_relative_motion_pairs cannot be below the minimum training pair count"
            )
        numeric_fields = (
            "near_duplicate_translation_mm",
            "near_duplicate_rotation_rad",
            "minimum_rotation_span_rad",
            "minimum_second_axis_excitation_rad",
            "minimum_rotation_nullspace_gap",
            "maximum_translation_condition_number",
            "maximum_rotation_fit_ratio",
            "maximum_training_rms_translation_mm",
            "maximum_training_max_translation_mm",
            "maximum_training_rms_rotation_rad",
            "maximum_training_max_rotation_rad",
            "maximum_held_out_rms_translation_mm",
            "maximum_held_out_max_translation_mm",
            "maximum_held_out_rms_rotation_rad",
            "maximum_held_out_max_rotation_rad",
            "maximum_relative_rms_translation_mm",
            "maximum_relative_max_translation_mm",
            "maximum_relative_rms_rotation_rad",
            "maximum_relative_max_rotation_rad",
        )
        for label in numeric_fields:
            value = getattr(self, label)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{label} must be a real number")
            if not math.isfinite(float(value)) or float(value) <= 0.0:
                raise ValueError(f"{label} must be finite and positive")
        for rms_name, max_name in (
            ("maximum_training_rms_translation_mm", "maximum_training_max_translation_mm"),
            ("maximum_training_rms_rotation_rad", "maximum_training_max_rotation_rad"),
            ("maximum_held_out_rms_translation_mm", "maximum_held_out_max_translation_mm"),
            ("maximum_held_out_rms_rotation_rad", "maximum_held_out_max_rotation_rad"),
            ("maximum_relative_rms_translation_mm", "maximum_relative_max_translation_mm"),
            ("maximum_relative_rms_rotation_rad", "maximum_relative_max_rotation_rad"),
        ):
            if getattr(self, rms_name) > getattr(self, max_name):
                raise ValueError(f"{rms_name} cannot exceed {max_name}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "minimum_training_samples": self.minimum_training_samples,
            "minimum_held_out_samples": self.minimum_held_out_samples,
            "maximum_samples": self.maximum_samples,
            "maximum_relative_motion_pairs": self.maximum_relative_motion_pairs,
            "near_duplicate_translation_mm": self.near_duplicate_translation_mm,
            "near_duplicate_rotation_rad": self.near_duplicate_rotation_rad,
            "minimum_carrier_rotation_axis_rank": self.minimum_carrier_rotation_axis_rank,
            "minimum_rotation_span_rad": self.minimum_rotation_span_rad,
            "minimum_second_axis_excitation_rad": self.minimum_second_axis_excitation_rad,
            "minimum_rotation_nullspace_gap": self.minimum_rotation_nullspace_gap,
            "maximum_translation_condition_number": self.maximum_translation_condition_number,
            "minimum_translation_rank": self.minimum_translation_rank,
            "maximum_rotation_fit_ratio": self.maximum_rotation_fit_ratio,
            "maximum_training_rms_translation_mm": self.maximum_training_rms_translation_mm,
            "maximum_training_max_translation_mm": self.maximum_training_max_translation_mm,
            "maximum_training_rms_rotation_rad": self.maximum_training_rms_rotation_rad,
            "maximum_training_max_rotation_rad": self.maximum_training_max_rotation_rad,
            "maximum_held_out_rms_translation_mm": self.maximum_held_out_rms_translation_mm,
            "maximum_held_out_max_translation_mm": self.maximum_held_out_max_translation_mm,
            "maximum_held_out_rms_rotation_rad": self.maximum_held_out_rms_rotation_rad,
            "maximum_held_out_max_rotation_rad": self.maximum_held_out_max_rotation_rad,
            "maximum_relative_rms_translation_mm": self.maximum_relative_rms_translation_mm,
            "maximum_relative_max_translation_mm": self.maximum_relative_max_translation_mm,
            "maximum_relative_rms_rotation_rad": self.maximum_relative_rms_rotation_rad,
            "maximum_relative_max_rotation_rad": self.maximum_relative_max_rotation_rad,
        }


DEFAULT_EYE_ON_ARM_SOLVER_POLICY = EyeOnArmSolverPolicy()


@dataclass(frozen=True, slots=True)
class PoseResidual:
    sample_id: str
    split: str
    translation_mm: float
    rotation_rad: float

    def __post_init__(self) -> None:
        if self.split not in {"TRAIN", "HELD_OUT"}:
            raise ValueError("Residual split must be TRAIN or HELD_OUT")
        for value, label in (
            (self.translation_mm, "translation_mm"),
            (self.rotation_rad, "rotation_rad"),
        ):
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{label} must be finite and non-negative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "split": self.split,
            "translation_mm": self.translation_mm,
            "rotation_rad": self.rotation_rad,
        }


@dataclass(frozen=True, slots=True)
class ResidualSummary:
    count: int
    rms_translation_mm: float
    max_translation_mm: float
    rms_rotation_rad: float
    max_rotation_rad: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "rms_translation_mm": self.rms_translation_mm,
            "max_translation_mm": self.max_translation_mm,
            "rms_rotation_rad": self.rms_rotation_rad,
            "max_rotation_rad": self.max_rotation_rad,
        }


@dataclass(frozen=True, slots=True)
class EyeOnArmObservability:
    """Numerical excitation metrics from actual carrier poses, not pose count."""

    relative_motion_pairs: int
    carrier_rotation_axis_rank: int
    carrier_rotation_span_rad: float
    second_axis_excitation_rad: float
    rotation_nullspace_gap: float
    rotation_fit_ratio: float
    translation_rank: int
    translation_condition_number: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "relative_motion_pairs": self.relative_motion_pairs,
            "carrier_rotation_axis_rank": self.carrier_rotation_axis_rank,
            "carrier_rotation_span_rad": self.carrier_rotation_span_rad,
            "second_axis_excitation_rad": self.second_axis_excitation_rad,
            "rotation_nullspace_gap": self.rotation_nullspace_gap,
            "rotation_fit_ratio": self.rotation_fit_ratio,
            "translation_rank": self.translation_rank,
            "translation_condition_number": self.translation_condition_number,
        }


@dataclass(frozen=True, slots=True)
class EyeOnArmSolveResult:
    """Immutable solver report; never a commissioned transform or motion permit."""

    dataset_id: str
    dataset_hash: str
    solver: str
    solver_versions: Mapping[str, str]
    policy: EyeOnArmSolverPolicy
    status: str
    diagnostic_pass: bool
    diagnostic_failures: tuple[str, ...]
    exposure_synchronized: bool
    E_T_C_arm_candidate: RigidTransform
    Wv_T_B_candidate: RigidTransform
    observability: EyeOnArmObservability
    training_summary: ResidualSummary
    held_out_summary: ResidualSummary
    relative_motion_summary: ResidualSummary
    residuals: tuple[PoseResidual, ...]
    source_hashes: Mapping[str, str]
    limitations: tuple[str, ...]
    physical_release_effect: str = "NONE"

    def __post_init__(self) -> None:
        if self.physical_release_effect != "NONE":
            raise ValueError("Numerical calibration reports cannot release physical motion")
        if not isinstance(self.policy, EyeOnArmSolverPolicy):
            raise TypeError("policy must be an EyeOnArmSolverPolicy")
        if not isinstance(self.diagnostic_pass, bool):
            raise TypeError("diagnostic_pass must be a bool")
        if (
            self.E_T_C_arm_candidate.parent_frame != "E"
            or self.E_T_C_arm_candidate.child_frame != "C_arm"
        ):
            raise ValueError("Extrinsic candidate must be E_T_C_arm")
        if (
            self.Wv_T_B_candidate.parent_frame != "Wv"
            or self.Wv_T_B_candidate.child_frame != "B"
        ):
            raise ValueError("Robot/world candidate must be Wv_T_B")
        object.__setattr__(
            self, "solver_versions", MappingProxyType(dict(sorted(self.solver_versions.items())))
        )
        object.__setattr__(
            self, "source_hashes", MappingProxyType(dict(sorted(self.source_hashes.items())))
        )
        object.__setattr__(self, "residuals", tuple(self.residuals))
        object.__setattr__(self, "limitations", tuple(self.limitations))
        object.__setattr__(self, "diagnostic_failures", tuple(self.diagnostic_failures))
        if self.diagnostic_pass == bool(self.diagnostic_failures):
            raise ValueError("diagnostic_pass must be true exactly when failures are empty")
        expected_status = (
            "DIAGNOSTIC_PASS_CANDIDATE_NOMINAL_ONLY_NO_PHYSICAL_AUTHORITY"
            if self.diagnostic_pass
            else "DIAGNOSTIC_FAIL_CANDIDATE_NOMINAL_ONLY_NO_PHYSICAL_AUTHORITY"
        )
        if self.status != expected_status:
            raise ValueError("status and diagnostic result differ")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "rocell.eye_on_arm_solve_report.v1",
            "status": self.status,
            "physical_release_effect": self.physical_release_effect,
            "dataset_id": self.dataset_id,
            "dataset_hash": self.dataset_hash,
            "solver": self.solver,
            "solver_versions": dict(self.solver_versions),
            "solver_policy": self.policy.to_dict(),
            "diagnostic_pass": self.diagnostic_pass,
            "diagnostic_failures": list(self.diagnostic_failures),
            "exposure_synchronized": self.exposure_synchronized,
            "equation": "Wv_T_B = Wv_T_E * E_T_C_arm * C_arm_T_B",
            "E_T_C_arm_candidate": _transform_dict(self.E_T_C_arm_candidate),
            "Wv_T_B_candidate": _transform_dict(self.Wv_T_B_candidate),
            "observability": self.observability.to_dict(),
            "training_residuals": self.training_summary.to_dict(),
            "held_out_residuals": self.held_out_summary.to_dict(),
            "relative_motion_residuals": self.relative_motion_summary.to_dict(),
            "per_pose_residuals": [residual.to_dict() for residual in self.residuals],
            "source_hashes": dict(self.source_hashes),
            "limitations": list(self.limitations),
        }

    @property
    def report_hash(self) -> str:
        """SHA-256 of the canonical semantic report, excluding no hidden state."""

        encoded = json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def to_nominal_artifact(
        self,
        *,
        version: int,
        created_utc: str,
        manifest_id: str,
        active_build_id: str,
    ) -> CalibrationArtifact:
        """Wrap the candidate for storage without allowing self-promotion to VALID.

        A separately designed commissioning/acceptance boundary must validate
        real identity, timing, residual thresholds, independent trials, and
        installation state before any future artifact may become ``VALID``.
        """

        dependencies = {
            "arm_frame_contract": self.source_hashes["arm_frame_contract"],
            "camera_manifest": self.source_hashes["camera_manifest"],
            "carrier_kinematic_model": self.source_hashes["carrier_kinematic_model"],
            "carrier_registration": self.source_hashes["carrier_registration"],
            "eye_on_arm_dataset": self.dataset_hash,
        }
        parents = {
            "camera_intrinsics": self.source_hashes["camera_intrinsics"],
            "measured_tag_map": self.source_hashes["measured_tag_map"],
            "robot_reference": self.source_hashes["robot_reference"],
        }
        return CalibrationArtifact(
            artifact_id="eye_on_arm_extrinsic",
            version=version,
            state=ArtifactState.NOMINAL_ONLY,
            created_utc=created_utc,
            manifest_id=manifest_id,
            active_build_id=active_build_id,
            dependency_hashes=dependencies,
            parent_artifact_hashes=parents,
            payload=self.to_dict(),
        )


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


def _matrix(transform: RigidTransform, np: Any) -> Any:
    matrix = np.eye(4, dtype=float)
    matrix[:3, :3] = np.asarray(transform.rotation.matrix, dtype=float).reshape(3, 3)
    matrix[:3, 3] = np.asarray(
        (
            transform.translation_mm.x,
            transform.translation_mm.y,
            transform.translation_mm.z,
        ),
        dtype=float,
    )
    return matrix


def _rigid(parent: str, child: str, matrix: Any) -> RigidTransform:
    return RigidTransform(
        parent_frame=parent,
        child_frame=child,
        rotation=Rotation3(tuple(float(item) for item in matrix[:3, :3].reshape(-1))),
        translation_mm=Vec3.from_iterable(float(item) for item in matrix[:3, 3]),
    )


def _project_rotation(matrix: Any, np: Any) -> Any:
    left, _, right_t = np.linalg.svd(matrix)
    rotation = left @ right_t
    if float(np.linalg.det(rotation)) < 0.0:
        left[:, -1] *= -1.0
        rotation = left @ right_t
    return rotation


def _rotation_angle(rotation: Any, np: Any) -> float:
    cosine = float((np.trace(rotation) - 1.0) * 0.5)
    return math.acos(max(-1.0, min(1.0, cosine)))


def _rotation_vector(rotation: Any, np: Any) -> Any:
    angle = _rotation_angle(rotation, np)
    if angle <= 1e-12:
        return np.zeros(3, dtype=float)
    if abs(math.pi - angle) <= 1e-6:
        # The symmetric part remains stable when sin(angle) is nearly zero.
        eigenvalues, eigenvectors = np.linalg.eig(rotation)
        index = int(np.argmin(np.abs(eigenvalues - 1.0)))
        axis = np.real(eigenvectors[:, index])
        axis /= np.linalg.norm(axis)
    else:
        axis = np.asarray(
            (
                rotation[2, 1] - rotation[1, 2],
                rotation[0, 2] - rotation[2, 0],
                rotation[1, 0] - rotation[0, 1],
            ),
            dtype=float,
        ) / (2.0 * math.sin(angle))
    return axis * angle


def _difference(left: Any, right: Any, np: Any) -> tuple[float, float]:
    translation = float(np.linalg.norm(left[:3, 3] - right[:3, 3]))
    angle = _rotation_angle(left[:3, :3].T @ right[:3, :3], np)
    return translation, angle


def _summary(residuals: Sequence[PoseResidual]) -> ResidualSummary:
    if not residuals:
        raise EyeOnArmSolveError("Residual summary cannot be empty")
    count = len(residuals)
    return ResidualSummary(
        count=count,
        rms_translation_mm=math.sqrt(
            sum(item.translation_mm**2 for item in residuals) / count
        ),
        max_translation_mm=max(item.translation_mm for item in residuals),
        rms_rotation_rad=math.sqrt(
            sum(item.rotation_rad**2 for item in residuals) / count
        ),
        max_rotation_rad=max(item.rotation_rad for item in residuals),
    )


def _relative_summary(values: Sequence[tuple[float, float]]) -> ResidualSummary:
    residuals = tuple(
        PoseResidual(
            sample_id=f"relative_pair_{index}",
            split="TRAIN",
            translation_mm=translation,
            rotation_rad=rotation,
        )
        for index, (translation, rotation) in enumerate(values)
    )
    return _summary(residuals)


def _diagnostic_failures(
    policy: EyeOnArmSolverPolicy,
    observability: EyeOnArmObservability,
    training: ResidualSummary,
    held_out: ResidualSummary,
    relative: ResidualSummary,
) -> tuple[str, ...]:
    checks = (
        (
            "ROTATION_FIT_RATIO",
            observability.rotation_fit_ratio,
            policy.maximum_rotation_fit_ratio,
        ),
        (
            "TRAINING_RMS_TRANSLATION_MM",
            training.rms_translation_mm,
            policy.maximum_training_rms_translation_mm,
        ),
        (
            "TRAINING_MAX_TRANSLATION_MM",
            training.max_translation_mm,
            policy.maximum_training_max_translation_mm,
        ),
        (
            "TRAINING_RMS_ROTATION_RAD",
            training.rms_rotation_rad,
            policy.maximum_training_rms_rotation_rad,
        ),
        (
            "TRAINING_MAX_ROTATION_RAD",
            training.max_rotation_rad,
            policy.maximum_training_max_rotation_rad,
        ),
        (
            "HELD_OUT_RMS_TRANSLATION_MM",
            held_out.rms_translation_mm,
            policy.maximum_held_out_rms_translation_mm,
        ),
        (
            "HELD_OUT_MAX_TRANSLATION_MM",
            held_out.max_translation_mm,
            policy.maximum_held_out_max_translation_mm,
        ),
        (
            "HELD_OUT_RMS_ROTATION_RAD",
            held_out.rms_rotation_rad,
            policy.maximum_held_out_rms_rotation_rad,
        ),
        (
            "HELD_OUT_MAX_ROTATION_RAD",
            held_out.max_rotation_rad,
            policy.maximum_held_out_max_rotation_rad,
        ),
        (
            "RELATIVE_RMS_TRANSLATION_MM",
            relative.rms_translation_mm,
            policy.maximum_relative_rms_translation_mm,
        ),
        (
            "RELATIVE_MAX_TRANSLATION_MM",
            relative.max_translation_mm,
            policy.maximum_relative_max_translation_mm,
        ),
        (
            "RELATIVE_RMS_ROTATION_RAD",
            relative.rms_rotation_rad,
            policy.maximum_relative_rms_rotation_rad,
        ),
        (
            "RELATIVE_MAX_ROTATION_RAD",
            relative.max_rotation_rad,
            policy.maximum_relative_max_rotation_rad,
        ),
    )
    return tuple(
        f"{name}:{value:.12g}>{limit:.12g}"
        for name, value, limit in checks
        if value > limit
    )


def solve_eye_on_arm(
    dataset: EyeOnArmDataset,
    *,
    policy: EyeOnArmSolverPolicy = DEFAULT_EYE_ON_ARM_SOLVER_POLICY,
) -> EyeOnArmSolveResult:
    """Solve ``A_i X C_i = Z`` and report train/held-out consistency.

    ``A_i`` is ``Wv_T_E``, ``X`` is the desired ``E_T_C_arm``, ``C_i`` is
    ``C_arm_T_B``, and ``Z`` is the constant ``Wv_T_B``.  At least five
    training poses and one explicitly reserved held-out pose are required.
    The algorithm uses all training-pose pairs, so it evaluates carrier
    excitation rather than accepting a large count of downstream-only joint
    changes that leave ``E`` stationary.
    """

    if not isinstance(dataset, EyeOnArmDataset):
        raise TypeError("dataset must be an EyeOnArmDataset")
    if not isinstance(policy, EyeOnArmSolverPolicy):
        raise TypeError("policy must be an EyeOnArmSolverPolicy")
    held_out = dataset.held_out_sample_ids
    held_out_set = set(held_out)
    training = tuple(
        sample for sample in dataset.samples if sample.sample_id not in held_out_set
    )
    held_out_samples = tuple(dataset.sample(sample_id) for sample_id in held_out)
    if len(dataset.samples) > policy.maximum_samples:
        raise EyeOnArmSolveError(
            f"Dataset has {len(dataset.samples)} samples; policy maximum is {policy.maximum_samples}"
        )
    if len(training) < policy.minimum_training_samples:
        raise EyeOnArmSolveError(
            f"Training split has {len(training)} poses; policy minimum is "
            f"{policy.minimum_training_samples}"
        )
    if len(held_out_samples) < policy.minimum_held_out_samples:
        raise EyeOnArmSolveError(
            f"Held-out split has {len(held_out_samples)} poses; policy minimum is "
            f"{policy.minimum_held_out_samples}"
        )
    relative_pair_count = len(training) * (len(training) - 1) // 2
    if relative_pair_count > policy.maximum_relative_motion_pairs:
        raise EyeOnArmSolveError(
            f"Training split requires {relative_pair_count} relative pairs; policy maximum is "
            f"{policy.maximum_relative_motion_pairs}"
        )

    np = _numpy()
    all_carrier = [
        _matrix(sample.carrier_pose.transform, np) for sample in dataset.samples
    ]
    for left_index in range(len(dataset.samples)):
        for right_index in range(left_index + 1, len(dataset.samples)):
            translation, rotation = _difference(
                all_carrier[left_index], all_carrier[right_index], np
            )
            if (
                translation <= policy.near_duplicate_translation_mm
                and rotation <= policy.near_duplicate_rotation_rad
            ):
                left = dataset.samples[left_index]
                right = dataset.samples[right_index]
                cross_split = (left.sample_id in held_out_set) != (
                    right.sample_id in held_out_set
                )
                label = "TRAIN/HELD_OUT leakage" if cross_split else "near-duplicate carrier poses"
                raise EyeOnArmSolveError(
                    f"{label}: {left.sample_id} and {right.sample_id} differ by "
                    f"{translation:.6g} mm / {rotation:.6g} rad"
                )
    carrier = [_matrix(sample.carrier_pose.transform, np) for sample in training]
    target = [_matrix(sample.target_pose.transform, np) for sample in training]

    relative: list[tuple[Any, Any]] = []
    for left_index in range(len(training)):
        for right_index in range(left_index + 1, len(training)):
            # From A_i X C_i = A_j X C_j:
            # (A_j^-1 A_i) X = X (C_j C_i^-1).
            relative_a = np.linalg.inv(carrier[right_index]) @ carrier[left_index]
            relative_b = target[right_index] @ np.linalg.inv(target[left_index])
            relative.append((relative_a, relative_b))

    rotation_vectors = np.vstack(
        [_rotation_vector(item[0][:3, :3], np) for item in relative]
    )
    nonzero_vectors = rotation_vectors[
        np.linalg.norm(rotation_vectors, axis=1) > 1e-10
    ]
    axis_rank = (
        int(np.linalg.matrix_rank(nonzero_vectors, tol=1e-8))
        if len(nonzero_vectors)
        else 0
    )
    rotation_span = (
        max(float(np.linalg.norm(vector)) for vector in rotation_vectors)
        if len(rotation_vectors)
        else 0.0
    )
    excitation_singular_values = (
        np.linalg.svd(rotation_vectors, compute_uv=False)
        if len(rotation_vectors)
        else np.zeros(0, dtype=float)
    )
    second_axis_excitation = (
        float(excitation_singular_values[1] / math.sqrt(len(rotation_vectors)))
        if len(excitation_singular_values) >= 2
        else 0.0
    )
    if (
        axis_rank < policy.minimum_carrier_rotation_axis_rank
        or rotation_span < policy.minimum_rotation_span_rad
        or second_axis_excitation < policy.minimum_second_axis_excitation_rad
    ):
        raise EyeOnArmSolveError(
            "Carrier poses lack diverse upstream rotation or second-axis excitation; "
            "downstream-only, repeated, or nearly single-axis Wv_T_E motion cannot "
            "support hand-eye calibration"
        )

    identity = np.eye(3, dtype=float)
    rotation_system = np.vstack(
        [
            np.kron(identity, relative_a[:3, :3])
            - np.kron(relative_b[:3, :3].T, identity)
            for relative_a, relative_b in relative
        ]
    )
    _, rotation_singular_values, right_t = np.linalg.svd(
        rotation_system, full_matrices=False
    )
    if len(rotation_singular_values) < 2 or rotation_singular_values[0] <= 0.0:
        raise EyeOnArmSolveError("Rotation system has no usable excitation")
    nullspace_gap = float(rotation_singular_values[-2] / rotation_singular_values[0])
    if nullspace_gap < policy.minimum_rotation_nullspace_gap:
        raise EyeOnArmSolveError("Rotation system is numerically unobservable")
    fit_ratio = float(
        rotation_singular_values[-1]
        / max(rotation_singular_values[-2], np.finfo(float).eps)
    )
    raw_rotation = right_t[-1].reshape((3, 3), order="F")
    if float(np.linalg.det(raw_rotation)) < 0.0:
        raw_rotation *= -1.0
    rotation_x = _project_rotation(raw_rotation, np)

    translation_system = np.vstack(
        [relative_a[:3, :3] - identity for relative_a, _ in relative]
    )
    translation_rhs = np.concatenate(
        [
            rotation_x @ relative_b[:3, 3] - relative_a[:3, 3]
            for relative_a, relative_b in relative
        ]
    )
    translation_rank = int(np.linalg.matrix_rank(translation_system, tol=1e-10))
    if translation_rank < policy.minimum_translation_rank:
        raise EyeOnArmSolveError("Carrier motion cannot observe all three extrinsic translations")
    translation_singular_values = np.linalg.svd(
        translation_system, compute_uv=False
    )
    translation_condition = float(
        translation_singular_values[0] / translation_singular_values[-1]
    )
    if (
        not math.isfinite(translation_condition)
        or translation_condition > policy.maximum_translation_condition_number
    ):
        raise EyeOnArmSolveError("Extrinsic translation system is ill-conditioned")
    translation_x, _, _, _ = np.linalg.lstsq(
        translation_system, translation_rhs, rcond=None
    )

    matrix_x = np.eye(4, dtype=float)
    matrix_x[:3, :3] = rotation_x
    matrix_x[:3, 3] = translation_x
    world_candidates = [
        carrier_pose @ matrix_x @ target_pose
        for carrier_pose, target_pose in zip(carrier, target)
    ]
    matrix_world = np.eye(4, dtype=float)
    matrix_world[:3, :3] = _project_rotation(
        sum((candidate[:3, :3] for candidate in world_candidates), np.zeros((3, 3))),
        np,
    )
    matrix_world[:3, 3] = np.mean(
        np.vstack([candidate[:3, 3] for candidate in world_candidates]), axis=0
    )

    residuals: list[PoseResidual] = []
    for sample in dataset.samples:
        candidate = (
            _matrix(sample.carrier_pose.transform, np)
            @ matrix_x
            @ _matrix(sample.target_pose.transform, np)
        )
        translation, rotation = _difference(matrix_world, candidate, np)
        residuals.append(
            PoseResidual(
                sample_id=sample.sample_id,
                split="HELD_OUT" if sample.sample_id in held_out_set else "TRAIN",
                translation_mm=translation,
                rotation_rad=rotation,
            )
        )

    relative_residuals = []
    for relative_a, relative_b in relative:
        relative_residuals.append(
            _difference(relative_a @ matrix_x, matrix_x @ relative_b, np)
        )
    train_residuals = tuple(item for item in residuals if item.split == "TRAIN")
    test_residuals = tuple(item for item in residuals if item.split == "HELD_OUT")
    observability = EyeOnArmObservability(
        relative_motion_pairs=len(relative),
        carrier_rotation_axis_rank=axis_rank,
        carrier_rotation_span_rad=rotation_span,
        second_axis_excitation_rad=second_axis_excitation,
        rotation_nullspace_gap=nullspace_gap,
        rotation_fit_ratio=fit_ratio,
        translation_rank=translation_rank,
        translation_condition_number=translation_condition,
    )
    training_summary = _summary(train_residuals)
    held_out_summary = _summary(test_residuals)
    relative_summary = _relative_summary(relative_residuals)
    diagnostic_failures = _diagnostic_failures(
        policy,
        observability,
        training_summary,
        held_out_summary,
        relative_summary,
    )
    diagnostic_pass = not diagnostic_failures
    limitations = (
        "OFFLINE_NUMERICAL_CANDIDATE_ONLY; physical release effect is NONE.",
        "The solver trusts the supplied Wv_T_E poses; it does not prove joint references, FK, or link2_T_E/carrier registration.",
        "The solver trusts camera intrinsics and C_arm_T_B detections identified only by source hashes.",
        "Residuals are consistency metrics, not commissioned acceptance thresholds or uncertainty bounds.",
        "The five-training/one-held-out minimum is an algorithm test floor; future physical qualification policy requires at least 15 training and 6 held-out poses.",
        "No robust outlier rejection, rolling-shutter correction, collision analysis, live capture, arm I/O, or motion authority is included.",
        "Host receipt timestamps are not accepted as exposure-time synchronization.",
        "exposure_synchronized reports internal dataset-contract consistency only; no external timing qualification is verified.",
    )
    return EyeOnArmSolveResult(
        dataset_id=dataset.dataset_id,
        dataset_hash=dataset.content_hash,
        solver="numpy_kronecker_ax_xb_v1",
        solver_versions={"numpy": str(np.__version__)},
        policy=policy,
        status=(
            "DIAGNOSTIC_PASS_CANDIDATE_NOMINAL_ONLY_NO_PHYSICAL_AUTHORITY"
            if diagnostic_pass
            else "DIAGNOSTIC_FAIL_CANDIDATE_NOMINAL_ONLY_NO_PHYSICAL_AUTHORITY"
        ),
        diagnostic_pass=diagnostic_pass,
        diagnostic_failures=diagnostic_failures,
        exposure_synchronized=dataset.exposure_synchronized,
        E_T_C_arm_candidate=_rigid("E", "C_arm", matrix_x),
        Wv_T_B_candidate=_rigid("Wv", "B", matrix_world),
        observability=observability,
        training_summary=training_summary,
        held_out_summary=held_out_summary,
        relative_motion_summary=relative_summary,
        residuals=tuple(residuals),
        source_hashes=dataset.source_hashes,
        limitations=limitations,
    )
