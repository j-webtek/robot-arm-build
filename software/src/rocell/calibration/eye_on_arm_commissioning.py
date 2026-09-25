"""Fail-closed commissioning-readiness assessment for eye-on-arm evidence.

This boundary never promotes or installs a calibration artifact.  It only
states whether a complete, externally bound evidence set is eligible for a
separate controlled promotion review.  Its output always has zero physical
release effect.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from types import MappingProxyType
from typing import Any, Mapping

from .artifacts import CalibrationArtifact, CalibrationResolution
from .eye_on_arm_dataset import EyeOnArmDataset
from .eye_on_arm_evidence import (
    PINNED_ROARM_M3_KINEMATIC_SHA256,
    EyeOnArmCaptureEvidence,
    EyeOnArmFkVerification,
)
from .eye_on_arm_solver import (
    EyeOnArmSolveError,
    EyeOnArmSolveResult,
    EyeOnArmSolverUnavailable,
    solve_eye_on_arm,
)


REQUIRED_PREREQUISITES = frozenset(
    {
        "camera_intrinsics",
        "measured_tag_map",
        "robot_reference",
        "carrier_registration",
        "carrier_kinematic_model",
        "camera_physical_identity",
        "camera_settings",
        "timing_qualification",
    }
)

# The current repository can assess numerical and structural readiness, but it
# cannot yet resolve and content-validate all physical artifacts or prove an
# exposure bracket.  Keeping these blockers in executable policy prevents a
# collection of mutually consistent caller-authored hashes from becoming a
# commissioning pass.
OPEN_PHYSICAL_ACCEPTANCE_BLOCKERS = (
    "verified_active_build_context",
    "registry_resolved_typed_artifact_payloads",
    "qualified_pre_exposure_post_feedback_bracket",
    "raw_wire_image_detection_bundle",
    "registry_backed_independent_validation",
)


@dataclass(frozen=True, slots=True)
class EyeOnArmCommissioningPolicy:
    """Physical-evidence review floor; not a motion or contact policy."""

    policy_id: str = "ROCELL-EYE-ON-ARM-COMMISSIONING-REVIEW-001"
    minimum_training_samples: int = 15
    minimum_held_out_samples: int = 6
    maximum_training_rms_translation_mm: float = 1.0
    maximum_training_max_translation_mm: float = 2.0
    maximum_training_rms_rotation_rad: float = 0.01
    maximum_training_max_rotation_rad: float = 0.02
    maximum_held_out_rms_translation_mm: float = 1.5
    maximum_held_out_max_translation_mm: float = 3.0
    maximum_held_out_rms_rotation_rad: float = 0.015
    maximum_held_out_max_rotation_rad: float = 0.03
    maximum_relative_rms_translation_mm: float = 1.0
    maximum_relative_max_translation_mm: float = 2.0
    maximum_relative_rms_rotation_rad: float = 0.01
    maximum_relative_max_rotation_rad: float = 0.02

    def __post_init__(self) -> None:
        if not isinstance(self.policy_id, str) or not self.policy_id:
            raise ValueError("policy_id must be a non-empty string")
        for value, label in (
            (self.minimum_training_samples, "minimum_training_samples"),
            (self.minimum_held_out_samples, "minimum_held_out_samples"),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{label} must be a positive integer")
        numeric = (
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
        for label in numeric:
            value = getattr(self, label)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or float(value) <= 0.0
            ):
                raise ValueError(f"{label} must be finite and positive")

    def to_dict(self) -> dict[str, Any]:
        return {
            key: getattr(self, key)
            for key in (
                "policy_id",
                "minimum_training_samples",
                "minimum_held_out_samples",
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
        }


DEFAULT_COMMISSIONING_POLICY = EyeOnArmCommissioningPolicy()


@dataclass(frozen=True, slots=True)
class EyeOnArmCommissioningContext:
    """Claimed external state used for drift diagnostics only.

    This value is intentionally *not* treated as a verified active context.
    A future boundary must construct its context from content-verified registry
    and build-snapshot inputs rather than accepting this caller-authored map.
    """

    manifest_id: str
    active_build_id: str
    source_hashes: Mapping[str, str]

    def __post_init__(self) -> None:
        if not isinstance(self.manifest_id, str) or not self.manifest_id:
            raise ValueError("manifest_id must be a non-empty string")
        if not isinstance(self.active_build_id, str) or not self.active_build_id:
            raise ValueError("active_build_id must be a non-empty string")
        hashes = dict(self.source_hashes)
        if not hashes or any(
            not isinstance(key, str)
            or not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
            for key, value in hashes.items()
        ):
            raise ValueError("source_hashes must be a non-empty SHA-256 map")
        object.__setattr__(self, "source_hashes", MappingProxyType(dict(sorted(hashes.items()))))

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_id": self.manifest_id,
            "active_build_id": self.active_build_id,
            "source_hashes": dict(self.source_hashes),
        }


@dataclass(frozen=True, slots=True)
class CommissioningCheck:
    check_id: str
    passed: bool
    detail: str

    def __post_init__(self) -> None:
        if not isinstance(self.check_id, str) or not self.check_id:
            raise ValueError("check_id must be a non-empty string")
        if not isinstance(self.passed, bool):
            raise TypeError("Commissioning check passed must be a bool")
        if not isinstance(self.detail, str) or not self.detail:
            raise ValueError("Commissioning check detail must be a non-empty string")

    def to_dict(self) -> dict[str, Any]:
        return {"check_id": self.check_id, "passed": self.passed, "detail": self.detail}


@dataclass(frozen=True, slots=True)
class EyeOnArmCommissioningAssessment:
    status: str
    checks: tuple[CommissioningCheck, ...]
    dataset_hash: str
    evidence_hash: str
    fk_verification_hash: str
    solver_report_hash: str
    policy: EyeOnArmCommissioningPolicy
    physical_release_effect: str = "NONE"

    def __post_init__(self) -> None:
        checks = tuple(self.checks)
        object.__setattr__(self, "checks", checks)
        if not checks:
            raise ValueError("Commissioning assessment must contain checks")
        if len({check.check_id for check in checks}) != len(checks):
            raise ValueError("Commissioning check ids must be unique")
        for digest, label in (
            (self.dataset_hash, "dataset_hash"),
            (self.evidence_hash, "evidence_hash"),
            (self.fk_verification_hash, "fk_verification_hash"),
            (self.solver_report_hash, "solver_report_hash"),
        ):
            if (
                not isinstance(digest, str)
                or len(digest) != 64
                or any(character not in "0123456789abcdef" for character in digest)
            ):
                raise ValueError(f"{label} must be a lowercase SHA-256 digest")
        if not isinstance(self.policy, EyeOnArmCommissioningPolicy):
            raise TypeError("policy must be an EyeOnArmCommissioningPolicy")
        if self.physical_release_effect != "NONE":
            raise ValueError("Commissioning assessment cannot release physical motion")
        # Passing this evidence gate is deliberately unavailable until all
        # OPEN_PHYSICAL_ACCEPTANCE_BLOCKERS have typed, registry-backed inputs.
        if self.status != "EVIDENCE_GATE_BLOCKED" or all(
            check.passed for check in checks
        ):
            raise ValueError(
                "Physical commissioning remains blocked pending typed acceptance evidence"
            )

    @property
    def evidence_gate_passed(self) -> bool:
        return self.status == "EVIDENCE_GATE_PASS_NO_AUTHORITY"

    @property
    def report_hash(self) -> str:
        encoded = json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "rocell.eye_on_arm_commissioning_assessment.v1",
            "status": self.status,
            "physical_release_effect": self.physical_release_effect,
            "dataset_hash": self.dataset_hash,
            "evidence_hash": self.evidence_hash,
            "fk_verification_hash": self.fk_verification_hash,
            "solver_report_hash": self.solver_report_hash,
            "policy": self.policy.to_dict(),
            "checks": [check.to_dict() for check in self.checks],
            "authority": {
                "artifact_created": False,
                "artifact_installed": False,
                "motion_authorized": False,
                "contact_authorized": False,
            },
        }


def _summary_checks(
    prefix: str,
    summary: Any,
    policy: EyeOnArmCommissioningPolicy,
) -> tuple[CommissioningCheck, ...]:
    comparisons = (
        (
            "rms_translation_mm",
            summary.rms_translation_mm,
            getattr(policy, f"maximum_{prefix}_rms_translation_mm"),
        ),
        (
            "max_translation_mm",
            summary.max_translation_mm,
            getattr(policy, f"maximum_{prefix}_max_translation_mm"),
        ),
        (
            "rms_rotation_rad",
            summary.rms_rotation_rad,
            getattr(policy, f"maximum_{prefix}_rms_rotation_rad"),
        ),
        (
            "max_rotation_rad",
            summary.max_rotation_rad,
            getattr(policy, f"maximum_{prefix}_max_rotation_rad"),
        ),
    )
    checks: list[CommissioningCheck] = []
    for name, value, limit in comparisons:
        numeric = isinstance(value, (int, float)) and not isinstance(value, bool)
        finite = numeric and math.isfinite(float(value))
        passed = finite and 0.0 <= float(value) <= limit
        detail = (
            f"{float(value):.12g} <= {limit:.12g}"
            if finite
            else f"INVALID_METRIC:{value!r}"
        )
        checks.append(CommissioningCheck(f"{prefix}_{name}", passed, detail))
    return tuple(checks)


def _expected_prerequisite_hashes(
    dataset: EyeOnArmDataset,
    evidence: EyeOnArmCaptureEvidence,
) -> dict[str, str]:
    """Map every prerequisite id to the exact capture-bound artifact hash."""

    return {
        "camera_intrinsics": dataset.source_hashes["camera_intrinsics"],
        "measured_tag_map": dataset.source_hashes["measured_tag_map"],
        "robot_reference": evidence.robot_reference_sha256,
        "carrier_registration": evidence.carrier_registration_sha256,
        "carrier_kinematic_model": evidence.kinematic_model_sha256,
        "camera_physical_identity": evidence.camera_usb_identity_sha256,
        "camera_settings": evidence.camera_settings_sha256,
        "timing_qualification": evidence.timing_qualification_sha256,
    }


def _solver_residual_coverage(
    dataset: EyeOnArmDataset,
    result: EyeOnArmSolveResult,
) -> bool:
    """Require one correctly split residual for every precommitted sample."""

    held_out = set(dataset.held_out_sample_ids)
    expected = tuple(
        (
            sample.sample_id,
            "HELD_OUT" if sample.sample_id in held_out else "TRAIN",
        )
        for sample in dataset.samples
    )
    actual = tuple((residual.sample_id, residual.split) for residual in result.residuals)
    return actual == expected


def assess_eye_on_arm_commissioning(
    dataset: EyeOnArmDataset,
    evidence: EyeOnArmCaptureEvidence,
    fk_verification: EyeOnArmFkVerification,
    solver_result: EyeOnArmSolveResult,
    prerequisite_resolution: CalibrationResolution,
    independent_validation: CalibrationArtifact | None,
    context: EyeOnArmCommissioningContext,
    *,
    policy: EyeOnArmCommissioningPolicy = DEFAULT_COMMISSIONING_POLICY,
) -> EyeOnArmCommissioningAssessment:
    """Produce a fail-closed physical-commissioning readiness report.

    The generic ``independent_validation`` argument is retained only so older
    callers receive an explicit rejection in the report.  A generic
    :class:`CalibrationArtifact` is not an independently validated physical
    report and can never satisfy this boundary.
    """

    if not isinstance(dataset, EyeOnArmDataset):
        raise TypeError("dataset must be an EyeOnArmDataset")
    if not isinstance(evidence, EyeOnArmCaptureEvidence):
        raise TypeError("evidence must be an EyeOnArmCaptureEvidence")
    if not isinstance(fk_verification, EyeOnArmFkVerification):
        raise TypeError("fk_verification must be an EyeOnArmFkVerification")
    if not isinstance(solver_result, EyeOnArmSolveResult):
        raise TypeError("solver_result must be an EyeOnArmSolveResult")
    if not isinstance(prerequisite_resolution, CalibrationResolution):
        raise TypeError("prerequisite_resolution must be a CalibrationResolution")
    if independent_validation is not None and not isinstance(
        independent_validation, CalibrationArtifact
    ):
        raise TypeError("independent_validation must be a CalibrationArtifact or None")
    if not isinstance(context, EyeOnArmCommissioningContext):
        raise TypeError("context must be an EyeOnArmCommissioningContext")
    if not isinstance(policy, EyeOnArmCommissioningPolicy):
        raise TypeError("policy must be an EyeOnArmCommissioningPolicy")
    held_out = set(dataset.held_out_sample_ids)
    training_count = len(dataset.samples) - len(held_out)
    dataset_sample_ids = tuple(sample.sample_id for sample in dataset.samples)
    fk_sample_ids = tuple(sample.sample_id for sample in fk_verification.samples)
    expected_pair_count = training_count * (training_count - 1) // 2

    try:
        reproduced_solver = solve_eye_on_arm(dataset, policy=solver_result.policy)
        supplied_solver_hash = solver_result.report_hash
        reproduced_solver_hash = reproduced_solver.report_hash
    except (EyeOnArmSolveError, EyeOnArmSolverUnavailable, TypeError, ValueError) as exc:
        solver_reproduced = False
        solver_reproduction_detail = f"RECOMPUTE_FAILED:{type(exc).__name__}"
        # Keep the readiness report serializable without inventing a digest for
        # an invalid supplied report.
        supplied_solver_hash = hashlib.sha256(
            f"INVALID_SOLVER_REPORT:{type(exc).__name__}".encode("utf-8")
        ).hexdigest()
    else:
        solver_reproduced = reproduced_solver_hash == supplied_solver_hash
        solver_reproduction_detail = (
            reproduced_solver_hash
            if solver_reproduced
            else "REPORT_HASH_MISMATCH"
        )

    checks: list[CommissioningCheck] = [
        CommissioningCheck(
            "offline_capture_kind",
            dataset.dataset_kind == "OFFLINE_CAPTURE",
            dataset.dataset_kind,
        ),
        CommissioningCheck(
            "exposure_synchronization_contract",
            dataset.exposure_synchronized,
            f"INTERNAL_DATASET_CONTRACT_ONLY:{dataset.exposure_synchronized}",
        ),
        CommissioningCheck(
            "minimum_training_samples",
            training_count >= policy.minimum_training_samples,
            f"{training_count} >= {policy.minimum_training_samples}",
        ),
        CommissioningCheck(
            "minimum_held_out_samples",
            len(held_out) >= policy.minimum_held_out_samples,
            f"{len(held_out)} >= {policy.minimum_held_out_samples}",
        ),
        CommissioningCheck(
            "capture_dataset_binding",
            evidence.dataset_id == dataset.dataset_id
            and evidence.dataset_sha256 == dataset.content_hash,
            evidence.dataset_sha256,
        ),
        CommissioningCheck(
            "reviewed_kinematic_model_pin",
            evidence.kinematic_model_sha256
            == PINNED_ROARM_M3_KINEMATIC_SHA256
            and dataset.source_hashes["carrier_kinematic_model"]
            == PINNED_ROARM_M3_KINEMATIC_SHA256
            and fk_verification.kinematic_model_sha256
            == PINNED_ROARM_M3_KINEMATIC_SHA256,
            evidence.kinematic_model_sha256,
        ),
        CommissioningCheck(
            "claimed_manifest_build_binding",
            evidence.manifest_id == context.manifest_id
            and evidence.active_build_id == context.active_build_id,
            f"{evidence.manifest_id}/{evidence.active_build_id}",
        ),
        CommissioningCheck(
            "claimed_source_hashes",
            dict(dataset.source_hashes) == dict(context.source_hashes),
            f"dataset={len(dataset.source_hashes)} context={len(context.source_hashes)}",
        ),
        CommissioningCheck(
            "fk_verification_binding",
            fk_verification.dataset_id == dataset.dataset_id
            and fk_verification.evidence_id == evidence.evidence_id
            and fk_verification.dataset_hash == dataset.content_hash
            and fk_verification.evidence_hash == evidence.content_hash,
            fk_verification.status,
        ),
        CommissioningCheck(
            "fk_sample_coverage_exact",
            fk_sample_ids == dataset_sample_ids,
            f"fk={len(fk_sample_ids)} dataset={len(dataset_sample_ids)}",
        ),
        CommissioningCheck(
            "fk_verification_pass",
            fk_verification.all_passed,
            fk_verification.status,
        ),
        CommissioningCheck(
            "solver_dataset_binding",
            solver_result.dataset_id == dataset.dataset_id
            and solver_result.dataset_hash == dataset.content_hash,
            solver_result.dataset_hash,
        ),
        CommissioningCheck(
            "solver_source_hashes_exact",
            dict(solver_result.source_hashes) == dict(dataset.source_hashes),
            f"solver={len(solver_result.source_hashes)} dataset={len(dataset.source_hashes)}",
        ),
        CommissioningCheck(
            "solver_exposure_contract_binding",
            solver_result.exposure_synchronized == dataset.exposure_synchronized,
            str(solver_result.exposure_synchronized),
        ),
        CommissioningCheck(
            "solver_residual_coverage_exact",
            _solver_residual_coverage(dataset, solver_result),
            f"solver={len(solver_result.residuals)} dataset={len(dataset.samples)}",
        ),
        CommissioningCheck(
            "solver_split_summary_counts",
            solver_result.training_summary.count == training_count
            and solver_result.held_out_summary.count == len(held_out),
            (
                f"training={solver_result.training_summary.count}/{training_count};"
                f"held_out={solver_result.held_out_summary.count}/{len(held_out)}"
            ),
        ),
        CommissioningCheck(
            "solver_relative_pair_count",
            solver_result.observability.relative_motion_pairs == expected_pair_count
            and solver_result.relative_motion_summary.count == expected_pair_count,
            (
                f"observed={solver_result.observability.relative_motion_pairs};"
                f"summary={solver_result.relative_motion_summary.count};"
                f"expected={expected_pair_count}"
            ),
        ),
        CommissioningCheck(
            "solver_report_reproduced",
            solver_reproduced,
            solver_reproduction_detail,
        ),
        CommissioningCheck(
            "solver_diagnostic_pass",
            solver_result.diagnostic_pass,
            solver_result.status,
        ),
    ]
    prerequisite_ids = set(prerequisite_resolution.assessments)
    expected_prerequisite_hashes = _expected_prerequisite_hashes(dataset, evidence)
    checks.append(
        CommissioningCheck(
            "calibration_prerequisites_exact",
            prerequisite_ids == REQUIRED_PREREQUISITES
            and prerequisite_resolution.all_valid,
            ",".join(sorted(prerequisite_ids)),
        )
    )
    checks.append(
        CommissioningCheck(
            "calibration_prerequisite_hash_binding",
            prerequisite_ids == REQUIRED_PREREQUISITES
            and all(
                prerequisite_resolution.assessments[artifact_id].artifact_id
                == artifact_id
                and prerequisite_resolution.assessments[artifact_id].artifact_hash
                == expected_hash
                for artifact_id, expected_hash in expected_prerequisite_hashes.items()
            ),
            "EXACT_CAPTURE_BOUND_HASHES_REQUIRED",
        )
    )
    checks.extend(_summary_checks("training", solver_result.training_summary, policy))
    checks.extend(_summary_checks("held_out", solver_result.held_out_summary, policy))
    checks.extend(
        _summary_checks("relative", solver_result.relative_motion_summary, policy)
    )
    blocker_details = {
        "verified_active_build_context": "NO_VERIFIED_CONTEXT_PROVIDER",
        "registry_resolved_typed_artifact_payloads": (
            "HASH_ASSESSMENTS_DO_NOT_PROVE_CARRIER_REFERENCE_CAMERA_OR_TIMING_PAYLOADS"
        ),
        "qualified_pre_exposure_post_feedback_bracket": (
            "STRUCTURAL_BRACKET_EXISTS_BUT_T1051_HAS_NO_DEVICE_TIME_AND_CLOCK_CORRELATION_IS_UNVERIFIED"
        ),
        "raw_wire_image_detection_bundle": (
            "STRUCTURAL_BYTE_BUNDLE_NOT_ACCEPTED_AND_RAW_TAG_CORNERS_INLIERS_COVARIANCE_ARE_MISSING"
        ),
        "registry_backed_independent_validation": (
            "GENERIC_CALIBRATION_ARTIFACT_REJECTED:"
            + (
                independent_validation.content_hash
                if independent_validation is not None
                else "MISSING_TYPED_INDEPENDENT_REPORT"
            )
        ),
    }
    checks.extend(
        CommissioningCheck(blocker, False, blocker_details[blocker])
        for blocker in OPEN_PHYSICAL_ACCEPTANCE_BLOCKERS
    )
    frozen_checks = tuple(checks)
    return EyeOnArmCommissioningAssessment(
        status="EVIDENCE_GATE_BLOCKED",
        checks=frozen_checks,
        dataset_hash=dataset.content_hash,
        evidence_hash=evidence.content_hash,
        fk_verification_hash=fk_verification.report_hash,
        solver_report_hash=supplied_solver_hash,
        policy=policy,
    )
