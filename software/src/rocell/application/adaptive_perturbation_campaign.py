"""Deterministic adversarial perturbations for the adaptive virtual session.

This campaign expands the two golden positive-X examples into signed,
combined-translation, yaw, and over-limit cases.  Inputs are derived by a
versioned SHA-256 generator instead of Python's process-dependent randomness,
so a seed has identical meaning on every supported interpreter.

Exact hidden transforms are passed only to the virtual truth boundary.  The
aggregate report commits to them by hash and records classifications and child
outcomes, but does not serialize the private transform values.  The campaign
is simulation-only and never imports or opens hardware adapters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, Callable, Mapping, cast

from rocell.geometry import Vec3
from rocell.simulation.virtual_profile import (
    VirtualCommissioningProfile,
    VirtualProfileContext,
    load_virtual_commissioning_profile,
)
from rocell.typing import compile_development_text

from .adaptive_virtual_session import (
    MAX_ADAPTIVE_EXECUTION_WAYPOINTS,
    AdaptiveVirtualSessionPolicy,
    AdaptiveVirtualSessionReport,
    run_adaptive_virtual_session,
    synthetic_wide_fov_adaptive_session_policy,
)
from .bootstrap import (
    VirtualWorkcellBootstrap,
    bootstrap_virtual_workcell,
    revalidate_virtual_workcell,
)
from .virtual_arm_camera import make_hidden_virtual_board_truth
from .virtual_session import VirtualSessionScenarioBinding


ADAPTIVE_PERTURBATION_CAMPAIGN_SCHEMA = "rocell.adaptive_perturbation_campaign.v1"
ADAPTIVE_PERTURBATION_GENERATOR = "sha256-angle-radius-v1"
DEFAULT_ADAPTIVE_PERTURBATION_SEED = 20_260_903
MAX_ADAPTIVE_PERTURBATION_CASES = 32
MAX_GENERATED_PERTURBATION_CASES = 16
MAX_PERTURBATION_EXECUTIONS = MAX_ADAPTIVE_PERTURBATION_CASES * 128
MAX_PERTURBATION_CAPTURES = MAX_ADAPTIVE_PERTURBATION_CASES * 3
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_DECISION_STATUSES = frozenset({"NO_CHANGE", "APPLY", "REJECT"})
_MAX_CASE_TEXT = 128
_MAX_ABSOLUTE_TRANSLATION_MM = 1_000.0
_MAX_ABSOLUTE_YAW_RAD = math.pi


class AdaptivePerturbationCampaignError(ValueError):
    """A generated campaign or its child evidence violated its contract."""


def _stable_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _digest(value: str, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise AdaptivePerturbationCampaignError(
            f"{label} must be a lowercase SHA-256"
        )
    return value


def _bounded_text(value: object, label: str, *, maximum: int = _MAX_CASE_TEXT) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value.strip() != value
        or len(value) > maximum
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise AdaptivePerturbationCampaignError(f"{label} is invalid")
    return value


def _authority() -> dict[str, object]:
    return {
        "simulation_only": True,
        "hardware_accessed": False,
        "hardware_commands_generated": 0,
        "execution_authorized": False,
        "live_motion_authorized": False,
        "physical_contact_authorized": False,
        "can_release_physical_gates": False,
        "physical_release_effect": "NONE",
    }


def _zero_authority(value: object) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key in {
                "hardware_accessed",
                "execution_authorized",
                "live_motion_authorized",
                "physical_contact_authorized",
                "can_release_physical_gates",
                "hardware_command_emitted",
            } and child is not False:
                return False
            if key == "hardware_commands_generated" and child != 0:
                return False
            if not _zero_authority(child):
                return False
        return True
    if isinstance(value, (tuple, list)):
        return all(_zero_authority(item) for item in value)
    return True


def _freeze_json(value: object, label: str) -> object:
    if isinstance(value, Mapping):
        frozen: dict[str, object] = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise AdaptivePerturbationCampaignError(
                    f"{label} keys must be strings"
                )
            frozen[key] = _freeze_json(child, f"{label}.{key}")
        return MappingProxyType(frozen)
    if isinstance(value, (tuple, list)):
        return tuple(
            _freeze_json(child, f"{label}[{index}]")
            for index, child in enumerate(value)
        )
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    raise AdaptivePerturbationCampaignError(
        f"{label} must contain finite JSON-compatible values"
    )


def _thaw_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _thaw_json(child) for key, child in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(child) for child in value]
    return value


def _unit_interval(seed: int, ordinal: int, channel: str) -> float:
    digest = hashlib.sha256(
        f"{ADAPTIVE_PERTURBATION_GENERATOR}:{seed}:{ordinal}:{channel}".encode(
            "ascii"
        )
    ).digest()
    integer = int.from_bytes(digest[:8], "big")
    return integer / float((1 << 64) - 1)


def _default_campaign_session_policy() -> AdaptiveVirtualSessionPolicy:
    """Bind stress acceptance to the synthetic renderer's measured envelope.

    The arm-mounted wide-FOV fixture rounds tag corners to image pixels.  At
    the most oblique phone viewpoints, repeated pose solves have shown up to a
    3 px inlier residual and roughly 1.2 mm of post-correction translation
    residual.  These are convergence settings for this synthetic diagnostic,
    not physical calibration tolerances or release criteria.  The hard 15 mm
    translation and 5 degree yaw rejection limits remain unchanged.
    """

    return synthetic_wide_fov_adaptive_session_policy()


@dataclass(frozen=True, slots=True)
class AdaptivePerturbationSpec:
    """One private truth input with a public expected behavior contract."""

    case_id: str
    device: str
    translation_Wv_mm: tuple[float, float, float]
    yaw_board_rad: float
    expected_outcome: str
    classification: str

    def __post_init__(self) -> None:
        _bounded_text(self.case_id, "case_id")
        _bounded_text(self.classification, "classification")
        if self.device not in {"keyboard", "phone"}:
            raise AdaptivePerturbationCampaignError("device is invalid")
        if self.expected_outcome not in {
            "COMPLETE_NO_CHANGE",
            "COMPLETE_CORRECTED",
            "REJECT_BEFORE_CONTACT",
        }:
            raise AdaptivePerturbationCampaignError("expected outcome is invalid")
        if not isinstance(self.translation_Wv_mm, tuple) or len(
            self.translation_Wv_mm
        ) != 3:
            raise AdaptivePerturbationCampaignError(
                "translation_Wv_mm must be an immutable xyz tuple"
            )
        for value in (*self.translation_Wv_mm, self.yaw_board_rad):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
            ):
                raise AdaptivePerturbationCampaignError(
                    "perturbation values must be finite real numbers"
                )
        if any(
            abs(float(value)) > _MAX_ABSOLUTE_TRANSLATION_MM
            for value in self.translation_Wv_mm
        ):
            raise AdaptivePerturbationCampaignError(
                "translation perturbation exceeds the hard diagnostic bound"
            )
        if abs(float(self.yaw_board_rad)) > _MAX_ABSOLUTE_YAW_RAD:
            raise AdaptivePerturbationCampaignError(
                "yaw perturbation exceeds the hard diagnostic bound"
            )

    def _private_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "device": self.device,
            "translation_Wv_mm": [float(value) for value in self.translation_Wv_mm],
            "yaw_board_rad": float(self.yaw_board_rad),
            "expected_outcome": self.expected_outcome,
            "classification": self.classification,
        }

    @property
    def input_hash(self) -> str:
        return _stable_hash(self._private_dict())

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "device": self.device,
            "expected_outcome": self.expected_outcome,
            "classification": self.classification,
            "private_input_sha256": self.input_hash,
            "private_transform_serialized": False,
        }


@dataclass(frozen=True, slots=True)
class AdaptivePerturbationPolicy:
    seed: int = DEFAULT_ADAPTIVE_PERTURBATION_SEED
    generated_case_count: int = 8
    maximum_total_executions: int = MAX_PERTURBATION_EXECUTIONS
    maximum_total_captures: int = MAX_PERTURBATION_CAPTURES
    session_policy: AdaptiveVirtualSessionPolicy = field(
        default_factory=_default_campaign_session_policy
    )

    def __post_init__(self) -> None:
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise AdaptivePerturbationCampaignError("seed must be an integer")
        if not -(1 << 63) <= self.seed < (1 << 63):
            raise AdaptivePerturbationCampaignError("seed must fit signed 64-bit")
        if not isinstance(self.session_policy, AdaptiveVirtualSessionPolicy):
            raise TypeError("session_policy must be AdaptiveVirtualSessionPolicy")
        for name, lower, upper in (
            ("generated_case_count", 0, MAX_GENERATED_PERTURBATION_CASES),
            ("maximum_total_executions", 1, MAX_PERTURBATION_EXECUTIONS),
            ("maximum_total_captures", 1, MAX_PERTURBATION_CAPTURES),
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not lower <= value <= upper
            ):
                raise AdaptivePerturbationCampaignError(
                    f"{name} must be an integer in [{lower}, {upper}]"
                )

    @property
    def cases(self) -> tuple[AdaptivePerturbationSpec, ...]:
        return default_adaptive_perturbation_specs(
            self.seed, generated_case_count=self.generated_case_count
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "rocell.adaptive_perturbation_policy.v1",
            "seed": self.seed,
            "generator": ADAPTIVE_PERTURBATION_GENERATOR,
            "generated_case_count": self.generated_case_count,
            "case_count": len(self.cases),
            "case_input_sha256s": [case.input_hash for case in self.cases],
            "maximum_total_executions": self.maximum_total_executions,
            "maximum_total_captures": self.maximum_total_captures,
            "session_policy": {
                **self.session_policy.to_dict(),
                "policy_sha256": self.session_policy.policy_hash,
                "physical_tolerance_claimed": False,
            },
            "authority": _authority(),
        }

    @property
    def policy_hash(self) -> str:
        return _stable_hash(self.to_dict())


def default_adaptive_perturbation_specs(
    seed: int = DEFAULT_ADAPTIVE_PERTURBATION_SEED,
    *,
    generated_case_count: int = 8,
) -> tuple[AdaptivePerturbationSpec, ...]:
    """Return fixed boundary classes plus deterministic combined cases."""

    if isinstance(seed, bool) or not isinstance(seed, int):
        raise AdaptivePerturbationCampaignError("seed must be an integer")
    if not -(1 << 63) <= seed < (1 << 63):
        raise AdaptivePerturbationCampaignError("seed must fit signed 64-bit")
    if (
        isinstance(generated_case_count, bool)
        or not isinstance(generated_case_count, int)
        or not 0 <= generated_case_count <= MAX_GENERATED_PERTURBATION_CASES
    ):
        raise AdaptivePerturbationCampaignError(
            "generated_case_count is outside its hard bound"
        )
    deg = math.pi / 180.0
    fixed = (
        AdaptivePerturbationSpec(
            "nominal.keyboard", "keyboard", (0.0, 0.0, 0.0), 0.0,
            "COMPLETE_NO_CHANGE", "NOMINAL",
        ),
        AdaptivePerturbationSpec(
            "nominal.phone", "phone", (0.0, 0.0, 0.0), 0.0,
            "COMPLETE_NO_CHANGE", "NOMINAL",
        ),
        AdaptivePerturbationSpec(
            "signed.keyboard.x_positive_in_band", "keyboard", (12.0, 0.0, 0.0), 0.0,
            "COMPLETE_CORRECTED", "SIGNED_TRANSLATION",
        ),
        AdaptivePerturbationSpec(
            "signed.keyboard.x_negative_in_band", "keyboard", (-12.0, 0.0, 0.0), 0.0,
            "COMPLETE_CORRECTED", "SIGNED_TRANSLATION",
        ),
        AdaptivePerturbationSpec(
            "signed.phone.y_positive_in_band", "phone", (0.0, 8.0, 0.0), 0.0,
            "COMPLETE_CORRECTED", "SIGNED_TRANSLATION",
        ),
        AdaptivePerturbationSpec(
            "signed.phone.y_negative_in_band", "phone", (0.0, -8.0, 0.0), 0.0,
            "COMPLETE_CORRECTED", "SIGNED_TRANSLATION",
        ),
        AdaptivePerturbationSpec(
            "yaw.keyboard.positive_in_band", "keyboard", (0.0, 0.0, 0.0), 2.0 * deg,
            "COMPLETE_CORRECTED", "SIGNED_YAW",
        ),
        AdaptivePerturbationSpec(
            "yaw.phone.negative_in_band", "phone", (0.0, 0.0, 0.0), -2.0 * deg,
            "COMPLETE_CORRECTED", "SIGNED_YAW",
        ),
        AdaptivePerturbationSpec(
            "reject.keyboard.x_positive_over_limit", "keyboard", (16.0, 0.0, 0.0), 0.0,
            "REJECT_BEFORE_CONTACT", "OVER_TRANSLATION_LIMIT",
        ),
        AdaptivePerturbationSpec(
            "reject.phone.x_negative_over_limit", "phone", (-16.0, 0.0, 0.0), 0.0,
            "REJECT_BEFORE_CONTACT", "OVER_TRANSLATION_LIMIT",
        ),
        AdaptivePerturbationSpec(
            "reject.keyboard.yaw_positive_over_limit", "keyboard", (0.0, 0.0, 0.0), 6.0 * deg,
            "REJECT_BEFORE_CONTACT", "OVER_YAW_LIMIT",
        ),
        AdaptivePerturbationSpec(
            "reject.phone.yaw_negative_over_limit", "phone", (0.0, 0.0, 0.0), -6.0 * deg,
            "REJECT_BEFORE_CONTACT", "OVER_YAW_LIMIT",
        ),
    )
    generated: list[AdaptivePerturbationSpec] = []
    for ordinal in range(generated_case_count):
        angle = 2.0 * math.pi * _unit_interval(seed, ordinal, "angle")
        radius = 2.0 + 7.0 * _unit_interval(seed, ordinal, "radius")
        yaw = (-1.0 + 2.0 * _unit_interval(seed, ordinal, "yaw")) * 1.5 * deg
        generated.append(
            AdaptivePerturbationSpec(
                case_id=f"seeded.combined.{ordinal:02d}",
                device="keyboard" if ordinal % 2 == 0 else "phone",
                translation_Wv_mm=(
                    radius * math.cos(angle),
                    radius * math.sin(angle),
                    0.0,
                ),
                yaw_board_rad=yaw,
                expected_outcome="COMPLETE_CORRECTED",
                classification="SEEDED_COMBINED_TRANSLATION_YAW",
            )
        )
    cases = (*fixed, *generated)
    if len(cases) > MAX_ADAPTIVE_PERTURBATION_CASES:
        raise AdaptivePerturbationCampaignError("case catalog exceeded hard cap")
    return cases


@dataclass(frozen=True, slots=True)
class AdaptivePerturbationResult:
    spec: AdaptivePerturbationSpec
    child_report_sha256: str
    truth_registration_sha256: str
    decision_statuses: tuple[str, ...]
    execution_count: int
    capture_count: int
    correction_installation_count: int
    contact_count: int
    arm_closed: bool
    authority_verified: bool
    pipeline_completed: bool
    fault_reason: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.spec, AdaptivePerturbationSpec):
            raise TypeError("spec must be AdaptivePerturbationSpec")
        _digest(self.child_report_sha256, "child report hash")
        _digest(self.truth_registration_sha256, "truth registration hash")
        if (
            not isinstance(self.decision_statuses, tuple)
            or len(self.decision_statuses) > 2
            or any(status not in _DECISION_STATUSES for status in self.decision_statuses)
        ):
            raise AdaptivePerturbationCampaignError(
                "decision_statuses must be a bounded immutable status tuple"
            )
        for name, value, maximum in (
            (
                "execution_count",
                self.execution_count,
                MAX_ADAPTIVE_EXECUTION_WAYPOINTS,
            ),
            ("capture_count", self.capture_count, 3),
            ("correction_installation_count", self.correction_installation_count, 1),
            ("contact_count", self.contact_count, 1),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not 0 <= value <= maximum
            ):
                raise AdaptivePerturbationCampaignError(
                    f"{name} must be an integer in [0, {maximum}]"
                )
        for name in ("arm_closed", "authority_verified", "pipeline_completed"):
            if not isinstance(getattr(self, name), bool):
                raise AdaptivePerturbationCampaignError(f"{name} must be boolean")
        if self.correction_installation_count > self.capture_count:
            raise AdaptivePerturbationCampaignError(
                "correction installations cannot exceed camera captures"
            )
        if self.fault_reason is not None:
            _bounded_text(self.fault_reason, "fault_reason", maximum=256)
        if self.pipeline_completed and self.fault_reason is not None:
            raise AdaptivePerturbationCampaignError(
                "a completed case cannot retain a fault reason"
            )

    @property
    def passed(self) -> bool:
        common = self.arm_closed and self.authority_verified
        if self.spec.expected_outcome == "COMPLETE_NO_CHANGE":
            return (
                common
                and self.pipeline_completed
                and self.fault_reason is None
                and self.decision_statuses == ("NO_CHANGE",)
                and self.correction_installation_count == 0
                and self.contact_count == 1
            )
        if self.spec.expected_outcome == "COMPLETE_CORRECTED":
            return (
                common
                and self.pipeline_completed
                and self.fault_reason is None
                and self.decision_statuses == ("APPLY", "NO_CHANGE")
                and self.correction_installation_count == 1
                and self.contact_count == 1
            )
        return (
            common
            and not self.pipeline_completed
            and self.decision_statuses == ("REJECT",)
            and self.correction_installation_count == 0
            and self.contact_count == 0
            and isinstance(self.fault_reason, str)
            and self.fault_reason.startswith("BOARD_POSE_CORRECTION_REJECTED:")
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "case": self.spec.to_dict(),
            "child_report_sha256": self.child_report_sha256,
            "truth_registration_sha256": self.truth_registration_sha256,
            "decision_statuses": list(self.decision_statuses),
            "execution_count": self.execution_count,
            "capture_count": self.capture_count,
            "correction_installation_count": self.correction_installation_count,
            "contact_count": self.contact_count,
            "arm_closed": self.arm_closed,
            "authority_verified": self.authority_verified,
            "pipeline_completed": self.pipeline_completed,
            "fault_reason": self.fault_reason,
            "passed": self.passed,
            "authority": _authority(),
        }


@dataclass(frozen=True, slots=True)
class AdaptivePerturbationCampaignReport:
    source: Mapping[str, object]
    policy: AdaptivePerturbationPolicy
    results: tuple[AdaptivePerturbationResult, ...]
    final_revalidation_passed: bool

    def __post_init__(self) -> None:
        if not isinstance(self.source, Mapping):
            raise AdaptivePerturbationCampaignError("source must be a mapping")
        frozen_source = _freeze_json(self.source, "source")
        if not isinstance(frozen_source, Mapping):  # Defensive for type narrowing.
            raise AdaptivePerturbationCampaignError("source must be a mapping")
        object.__setattr__(self, "source", frozen_source)
        if not isinstance(self.policy, AdaptivePerturbationPolicy):
            raise TypeError("policy must be AdaptivePerturbationPolicy")
        if not isinstance(self.final_revalidation_passed, bool):
            raise AdaptivePerturbationCampaignError(
                "final_revalidation_passed must be boolean"
            )
        if (
            not isinstance(self.results, tuple)
            or any(
                not isinstance(result, AdaptivePerturbationResult)
                for result in self.results
            )
        ):
            raise AdaptivePerturbationCampaignError(
                "results must be an immutable result tuple"
            )
        if tuple(result.spec for result in self.results) != self.policy.cases:
            raise AdaptivePerturbationCampaignError(
                "results do not exactly match the generated case catalog"
            )
        if len(self.results) > MAX_ADAPTIVE_PERTURBATION_CASES:
            raise AdaptivePerturbationCampaignError("result count exceeded hard cap")
        if self.total_executions > self.policy.maximum_total_executions:
            raise AdaptivePerturbationCampaignError("execution count exceeded policy cap")
        if self.total_captures > self.policy.maximum_total_captures:
            raise AdaptivePerturbationCampaignError("capture count exceeded policy cap")
        if not _zero_authority(self.source):
            raise AdaptivePerturbationCampaignError("source carries hardware authority")

    @property
    def total_executions(self) -> int:
        return sum(result.execution_count for result in self.results)

    @property
    def total_captures(self) -> int:
        return sum(result.capture_count for result in self.results)

    @property
    def campaign_passed(self) -> bool:
        return (
            self.final_revalidation_passed
            and bool(self.results)
            and all(result.passed for result in self.results)
        )

    @property
    def status(self) -> str:
        return (
            "ADAPTIVE_PERTURBATION_CAMPAIGN_PASS_WITH_PHYSICAL_HOLDS"
            if self.campaign_passed
            else "ADAPTIVE_PERTURBATION_CAMPAIGN_GAPS_REPORTED"
        )

    def _without_hash(self) -> dict[str, object]:
        return {
            "schema": ADAPTIVE_PERTURBATION_CAMPAIGN_SCHEMA,
            "status": self.status,
            "source": _thaw_json(self.source),
            "policy": {**self.policy.to_dict(), "policy_sha256": self.policy.policy_hash},
            "results": [result.to_dict() for result in self.results],
            "summary": {
                "case_count": len(self.results),
                "passed_count": sum(result.passed for result in self.results),
                "failed_count": sum(not result.passed for result in self.results),
                "expected_rejection_count": sum(
                    result.spec.expected_outcome == "REJECT_BEFORE_CONTACT"
                    for result in self.results
                ),
                "total_executions": self.total_executions,
                "total_captures": self.total_captures,
                "campaign_passed": self.campaign_passed,
                "final_revalidation_passed": self.final_revalidation_passed,
                "physical_ready": False,
            },
            "authority": _authority(),
        }

    @property
    def report_hash(self) -> str:
        return _stable_hash(self._without_hash())

    def to_dict(self) -> dict[str, object]:
        return {**self._without_hash(), "report_sha256": self.report_hash}


def _scenario(profile: VirtualCommissioningProfile) -> VirtualSessionScenarioBinding:
    park = profile.park_point_board
    return VirtualSessionScenarioBinding(
        scenario_id=profile.profile_id,
        scenario_hash=profile.source_sha256,
        park_point_board_mm=(park.x, park.y, park.z),
    )


def _result(
    spec: AdaptivePerturbationSpec,
    report: AdaptiveVirtualSessionReport,
) -> AdaptivePerturbationResult:
    return AdaptivePerturbationResult(
        spec=spec,
        child_report_sha256=report.report_hash,
        truth_registration_sha256=report.truth_registration_sha256,
        decision_statuses=tuple(
            attempt.decision.status.value
            for attempt in report.vision_attempts
            if attempt.decision is not None
        ),
        execution_count=len(report.executions),
        capture_count=len(report.vision_attempts),
        correction_installation_count=len(report.correction_installations),
        contact_count=len(report.contact_attempts),
        arm_closed=report.arm_document.get("lifecycle") == "CLOSED",
        authority_verified=_zero_authority(report.to_dict()),
        pipeline_completed=report.pipeline_completed,
        fault_reason=report.fault_reason,
    )


def _run_adaptive_perturbation_campaign_with_runners(
    workspace: Path,
    *,
    policy: AdaptivePerturbationPolicy,
    runtime_path: Path | None = None,
    bootstrap_runner: Callable[..., VirtualWorkcellBootstrap] | None = None,
    profile_loader: Callable[..., VirtualCommissioningProfile] | None = None,
    session_runner: Callable[..., AdaptiveVirtualSessionReport] | None = None,
    revalidator: Callable[[VirtualWorkcellBootstrap], None] | None = None,
) -> AdaptivePerturbationCampaignReport:
    if not isinstance(policy, AdaptivePerturbationPolicy):
        raise TypeError("policy must be AdaptivePerturbationPolicy")
    bootstrap_fn = bootstrap_runner or bootstrap_virtual_workcell
    profile_fn = profile_loader or load_virtual_commissioning_profile
    session_fn = session_runner or run_adaptive_virtual_session
    revalidate_fn = revalidator or revalidate_virtual_workcell
    bootstrap = bootstrap_fn(Path(workspace).resolve(), runtime_path)
    profile = profile_fn(cast(VirtualProfileContext, bootstrap.context))
    scenario = _scenario(profile)
    results: list[AdaptivePerturbationResult] = []
    total_executions = 0
    total_captures = 0
    for spec in policy.cases:
        plan = compile_development_text(spec.device, "a")
        truth = make_hidden_virtual_board_truth(
            profile.study_input,
            translation_Wv_mm=Vec3(*spec.translation_Wv_mm),
            yaw_board_rad=spec.yaw_board_rad,
        )
        child = session_fn(
            bootstrap,
            plan,
            "a",
            profile.study_input,
            scenario,
            truth=truth,
            policy=policy.session_policy,
        )
        result = _result(spec, child)
        results.append(result)
        total_executions += result.execution_count
        total_captures += result.capture_count
        if total_executions > policy.maximum_total_executions:
            raise AdaptivePerturbationCampaignError(
                "execution count exceeded policy cap"
            )
        if total_captures > policy.maximum_total_captures:
            raise AdaptivePerturbationCampaignError("capture count exceeded policy cap")
    revalidate_fn(bootstrap)
    snapshot = bootstrap.context.snapshot
    return AdaptivePerturbationCampaignReport(
        source={
            "bootstrap_sha256": bootstrap.bootstrap_hash,
            "manifest_id": snapshot.manifest_id,
            "manifest_sha256": snapshot.manifest_sha256,
            "snapshot_sha256": snapshot.snapshot_hash,
            "virtual_profile_id": profile.profile_id,
            "virtual_profile_sha256": profile.source_sha256,
            "virtual_profile_classification": profile.status,
            "physical_ready": False,
            "authority": _authority(),
        },
        policy=policy,
        results=tuple(results),
        final_revalidation_passed=True,
    )


def run_adaptive_perturbation_campaign(
    workspace: Path,
    *,
    policy: AdaptivePerturbationPolicy | None = None,
    runtime_path: Path | None = None,
) -> AdaptivePerturbationCampaignReport:
    selected = policy or AdaptivePerturbationPolicy()
    if not isinstance(selected, AdaptivePerturbationPolicy):
        raise TypeError("policy must be AdaptivePerturbationPolicy")
    return _run_adaptive_perturbation_campaign_with_runners(
        workspace,
        policy=selected,
        runtime_path=runtime_path,
    )


__all__ = [
    "ADAPTIVE_PERTURBATION_CAMPAIGN_SCHEMA",
    "ADAPTIVE_PERTURBATION_GENERATOR",
    "DEFAULT_ADAPTIVE_PERTURBATION_SEED",
    "AdaptivePerturbationCampaignError",
    "AdaptivePerturbationCampaignReport",
    "AdaptivePerturbationPolicy",
    "AdaptivePerturbationResult",
    "AdaptivePerturbationSpec",
    "default_adaptive_perturbation_specs",
    "run_adaptive_perturbation_campaign",
]
