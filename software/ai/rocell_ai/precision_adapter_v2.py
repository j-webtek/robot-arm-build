"""Fail-closed adapter from pose-model output to precision observation v2.

This module accepts the three normalized values emitted by KeyboardPoseNet and
compatible pose models.  It creates named board-frame target hypotheses, but
it cannot create or install a localization qualification.  The only supported
qualification scope is the existing synthetic-offline v0 record.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, Sequence

from rocell.targets.nominal import load_nominal_target_catalog

from .precision_observation import build as build_precision
from .precision_observation import validate_qualification
from .scene_observation import SHA256_PATTERN, canonical_hash
from .visual_observation import MODEL_SCHEMA, validate as validate_prediction
from vision.synthetic_keyboard import PHOTO_STUDY_CENTER_MM, transform_target


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 128:
        raise ValueError(f"{label} must be nonempty and bounded")
    return value


def _epoch_ms(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer epoch-ms")
    return value


def _confidence(value: object | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("observation_confidence must be numeric")
    result = float(value)
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise ValueError("observation_confidence must be finite in [0,1]")
    return result


def decode_normalized_pose(values: Sequence[float]) -> tuple[float, float, float]:
    """Decode the exact three-value output convention used by KeyboardPoseNet."""
    if isinstance(values, (str, bytes)) or len(values) != 3:
        raise ValueError("pose output must contain exactly three numbers")
    decoded = []
    for index, value in enumerate(values):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"pose output {index} must be numeric")
        item = float(value)
        if not math.isfinite(item):
            raise ValueError(f"pose output {index} must be finite")
        decoded.append(item)
    return (
        PHOTO_STUDY_CENTER_MM[0] + decoded[0] * 30.0,
        PHOTO_STUDY_CENTER_MM[1] + decoded[1] * 24.0,
        math.pi + decoded[2] * 0.2,
    )


@dataclass(frozen=True, slots=True)
class PoseModelOutputV2:
    model_id: str
    model_sha256: str
    frame_id: str
    image_sha256: str
    normalized_pose: tuple[float, float, float]
    evaluated_at_epoch_ms: int
    observation_confidence: float | None = None

    def __post_init__(self) -> None:
        _identifier(self.model_id, "model_id")
        _digest(self.model_sha256, "model_sha256")
        _identifier(self.frame_id, "frame_id")
        _digest(self.image_sha256, "image_sha256")
        values = tuple(self.normalized_pose)
        decode_normalized_pose(values)
        object.__setattr__(self, "normalized_pose", values)
        _epoch_ms(self.evaluated_at_epoch_ms, "evaluated_at_epoch_ms")
        object.__setattr__(
            self, "observation_confidence", _confidence(self.observation_confidence)
        )


@dataclass(frozen=True, slots=True)
class InstalledSyntheticQualificationV0:
    qualification: Mapping[str, object]
    evaluation_bundle_sha256: str

    def __post_init__(self) -> None:
        record = dict(self.qualification)
        validate_qualification(record)
        _digest(self.evaluation_bundle_sha256, "evaluation_bundle_sha256")
        object.__setattr__(self, "qualification", MappingProxyType(record))


@dataclass(frozen=True, slots=True)
class PrecisionAdapterResultV2:
    precision_observation: Mapping[str, object]
    qualification: Mapping[str, object] | None
    evaluation_bundle_sha256: str | None
    model_output: PoseModelOutputV2
    domain_id: str
    required_target_ids: tuple[str, ...]
    diagnostics: tuple[str, ...]

    @property
    def accepted(self) -> bool:
        return not bool(self.precision_observation["abstain"])


def _prediction(workspace: Path, output: PoseModelOutputV2) -> dict[str, object]:
    catalog = load_nominal_target_catalog(workspace)
    center_x, center_y, yaw = decode_normalized_pose(output.normalized_pose)
    targets = {}
    for target_id, region in sorted(catalog.keyboard_targets.items()):
        x, y = transform_target(region.center.x, region.center.y, (center_x, center_y), yaw)
        targets[target_id] = {"center_board_mm": [x, y, region.center.z]}
    core = {
        "schema": MODEL_SCHEMA,
        "frame_id": output.frame_id,
        "device": "keyboard",
        "coordinate_frame": "board",
        "coordinate_unit": "mm",
        "source": "SYNTHETIC_IMAGE_MODEL_PREDICTION",
        "target_catalog_sha256": catalog.content_sha256,
        "image_sha256": output.image_sha256,
        "model_sha256": output.model_sha256,
        "targets": targets,
    }
    prediction = {**core, "observation_sha256": canonical_hash(core)}
    validate_prediction(
        prediction, device="keyboard", catalog_sha256=catalog.content_sha256
    )
    return prediction


def adapt_pose_model_output(
    workspace: Path,
    output: PoseModelOutputV2,
    *,
    domain_id: str,
    required_target_ids: Sequence[str],
    trusted_qualifications: Mapping[str, InstalledSyntheticQualificationV0] | None = None,
    expected_domain_id: str | None = None,
    minimum_observation_confidence: float = 0.95,
    now_epoch_ms: int,
    maximum_evidence_age_ms: int = 2_000,
) -> PrecisionAdapterResultV2:
    """Build precision v2 and attach a qualification only when applicable."""
    if not isinstance(workspace, Path):
        raise TypeError("workspace must be a Path")
    _identifier(domain_id, "domain_id")
    _epoch_ms(now_epoch_ms, "now_epoch_ms")
    if isinstance(maximum_evidence_age_ms, bool) or not isinstance(
        maximum_evidence_age_ms, int
    ) or maximum_evidence_age_ms <= 0:
        raise ValueError("maximum_evidence_age_ms must be a positive integer")
    threshold = _confidence(minimum_observation_confidence)
    if threshold is None:
        raise ValueError("minimum_observation_confidence is required")
    targets = tuple(required_target_ids)
    if not targets or any(not isinstance(item, str) or not item for item in targets):
        raise ValueError("required_target_ids must be nonempty target identifiers")

    prediction = _prediction(workspace, output)
    missing = [item for item in targets if item not in prediction["targets"]]
    if missing:
        raise ValueError(f"unknown required target {missing[0]!r}")

    diagnostics: list[str] = []
    applicable = []
    registry = trusted_qualifications or {}
    for digest, installation in registry.items():
        _digest(digest, "qualification registry key")
        if not isinstance(installation, InstalledSyntheticQualificationV0):
            raise ValueError("qualification registry values must be installed records")
        record = dict(installation.qualification)
        if record["qualification_sha256"] != digest:
            raise ValueError("qualification registry key mismatch")
        if (
            record["model_sha256"] == output.model_sha256
            and record["target_catalog_sha256"] == prediction["target_catalog_sha256"]
            and record["domain_id"] == domain_id
            and set(targets).issubset(record["target_ids"])
        ):
            applicable.append(installation)
    if len(applicable) > 1:
        raise ValueError("multiple localization qualifications are applicable")
    installation = applicable[0] if applicable else None
    if installation is None:
        diagnostics.append("localization_qualification_not_installed")
    if expected_domain_id != domain_id:
        diagnostics.append("localization_domain_unverified")
        installation = None
    confidence = output.observation_confidence
    if confidence is None:
        diagnostics.append("observation_confidence_missing")
        installation = None
    elif confidence < threshold:
        diagnostics.append("observation_confidence_below_threshold")
        installation = None
    age = now_epoch_ms - output.evaluated_at_epoch_ms
    if age < 0 or age > maximum_evidence_age_ms:
        diagnostics.append("precision_evidence_stale")
        installation = None

    qualification_sha256 = (
        None
        if installation is None
        else str(installation.qualification["qualification_sha256"])
    )
    precision = build_precision(
        prediction,
        domain_id=domain_id,
        qualification_sha256=qualification_sha256,
    )
    return PrecisionAdapterResultV2(
        precision_observation=MappingProxyType(precision),
        qualification=None if installation is None else installation.qualification,
        evaluation_bundle_sha256=(
            None if installation is None else installation.evaluation_bundle_sha256
        ),
        model_output=output,
        domain_id=domain_id,
        required_target_ids=targets,
        diagnostics=tuple(diagnostics),
    )


__all__ = [
    "InstalledSyntheticQualificationV0",
    "PoseModelOutputV2",
    "PrecisionAdapterResultV2",
    "adapt_pose_model_output",
    "decode_normalized_pose",
]
