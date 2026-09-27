"""ModelMotionBatchV2 production from a qualified precision-adapter result.

The producer has zero execution authority.  It emits canonical proposal bytes
or abstains.  Independent RoCell ingress still resolves registries and decides
whether the proposal may progress toward planning.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Mapping

from rocell.models import (
    ActionPlan,
    MotionCapabilityV2,
    MotionEvidenceV2,
    MotionGeometryV2,
    MotionUncertaintyV2,
    Point3Mm,
    UncertaintyBoundType,
)

from .batch_emitter_v2 import TargetObservationV2, assemble
from .precision_adapter_v2 import PrecisionAdapterResultV2
from .precision_observation import validate as validate_precision
from .scene_observation import SHA256_PATTERN


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


@dataclass(frozen=True, slots=True)
class PlacedTargetRegionMapV2:
    """Independently supplied board-frame target regions for producer checks."""

    target_catalog_sha256: str
    placement_observation_sha256: str
    regions_board_mm: Mapping[str, tuple[float, float, float, float]]

    def __post_init__(self) -> None:
        _digest(self.target_catalog_sha256, "target_catalog_sha256")
        _digest(self.placement_observation_sha256, "placement_observation_sha256")
        regions = {}
        for target_id, rectangle in self.regions_board_mm.items():
            if not isinstance(target_id, str) or not target_id:
                raise ValueError("placed target id must be nonempty")
            if not isinstance(rectangle, tuple) or len(rectangle) != 4:
                raise ValueError("placed target region must be a four-number tuple")
            left, front, right, rear = (
                _number(value, f"placed target region {target_id}") for value in rectangle
            )
            if left >= right or front >= rear:
                raise ValueError("placed target region must have positive area")
            regions[target_id] = (left, front, right, rear)
        if not regions:
            raise ValueError("placed target regions must be nonempty")
        object.__setattr__(self, "regions_board_mm", MappingProxyType(regions))


def produce_model_motion_batch_v2(
    plan: ActionPlan,
    *,
    adapter_result: PrecisionAdapterResultV2,
    batch_id: str,
    request_id: str,
    capability: MotionCapabilityV2,
    geometry: MotionGeometryV2,
    evidence: MotionEvidenceV2,
    placed_targets: PlacedTargetRegionMapV2,
    now_epoch_ms: int,
    maximum_evidence_age_ms: int = 2_000,
    minimum_observation_confidence: float = 0.95,
) -> bytes | None:
    """Return canonical V2 proposal bytes or ``None`` for policy abstention."""
    if not isinstance(adapter_result, PrecisionAdapterResultV2):
        raise TypeError("adapter_result must come from the precision adapter")
    precision = dict(adapter_result.precision_observation)
    validate_precision(precision)
    if precision["abstain"]:
        return None
    qualification = adapter_result.qualification
    if qualification is None or adapter_result.evaluation_bundle_sha256 is None:
        return None
    prediction = precision["prediction"]
    bindings = {
        "precision": (
            precision["observation_sha256"],
            evidence.precision_observation_sha256,
        ),
        "frame": (prediction["frame_id"], evidence.frame_id),
        "image": (prediction["image_sha256"], evidence.image_sha256),
        "model": (prediction["model_sha256"], evidence.model_sha256),
        "target catalog": (
            prediction["target_catalog_sha256"],
            geometry.target_catalog_sha256,
        ),
        "placed target catalog": (
            placed_targets.target_catalog_sha256,
            geometry.target_catalog_sha256,
        ),
        "placement": (
            placed_targets.placement_observation_sha256,
            geometry.placement_observation_sha256,
        ),
    }
    for label, (observed, expected) in bindings.items():
        if observed != expected:
            raise ValueError(f"{label} evidence mismatch")
    if evidence.evaluated_at_epoch_ms != adapter_result.model_output.evaluated_at_epoch_ms:
        raise ValueError("evaluation time evidence mismatch")
    if isinstance(now_epoch_ms, bool) or not isinstance(now_epoch_ms, int):
        raise ValueError("now_epoch_ms must be an integer")
    if isinstance(maximum_evidence_age_ms, bool) or not isinstance(
        maximum_evidence_age_ms, int
    ) or maximum_evidence_age_ms <= 0:
        raise ValueError("maximum_evidence_age_ms must be positive")
    if not evidence.evaluated_at_epoch_ms <= now_epoch_ms < evidence.expires_at_epoch_ms:
        return None
    if now_epoch_ms - evidence.evaluated_at_epoch_ms > maximum_evidence_age_ms:
        return None
    confidence = adapter_result.model_output.observation_confidence
    threshold = _number(minimum_observation_confidence, "minimum_observation_confidence")
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("minimum_observation_confidence must be in [0,1]")
    if confidence is None or confidence < threshold:
        return None

    radius = _number(qualification["error_bound_mm"], "error_bound_mm")
    observations = {}
    for target_id in dict.fromkeys(adapter_result.required_target_ids):
        if target_id not in qualification["target_ids"]:
            return None
        target = prediction["targets"].get(target_id)
        rectangle = placed_targets.regions_board_mm.get(target_id)
        if target is None or rectangle is None:
            return None
        x, y, z = target["center_board_mm"]
        left, front, right, rear = rectangle
        if x - radius < left or x + radius > right or y - radius < front \
                or y + radius > rear:
            return None
        observations[target_id] = TargetObservationV2(
            Point3Mm("board", x, y, z), confidence
        )

    uncertainty = MotionUncertaintyV2(
        bound_type=UncertaintyBoundType.PLANAR_L2_DISK,
        error_bound_mm=radius,
        coverage_probability=qualification["coverage_probability"],
        qualification_sha256=qualification["qualification_sha256"],
        evidence_method_sha256=adapter_result.evaluation_bundle_sha256,
        domain_id=qualification["domain_id"],
        covered_target_ids=tuple(qualification["target_ids"]),
    )
    return assemble(
        plan,
        batch_id=batch_id,
        request_id=request_id,
        capability=capability,
        geometry=geometry,
        evidence=evidence,
        observations=observations,
        uncertainty=uncertainty,
    )


__all__ = ["PlacedTargetRegionMapV2", "produce_model_motion_batch_v2"]
