"""Ordered, provenance-bound model proposals with no execution authority."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Mapping, Sequence

from .motion_proposal import ModelMotionProposal, MotionProposalError


SCHEMA = "rocell.model_motion_batch.v1"
MAX_BATCH_PROPOSALS = 64
MAX_BATCH_BYTES = 1_048_576
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FIELDS = {
    "schema",
    "batch_id",
    "request_id",
    "intent_plan_sha256",
    "scene_observation_sha256",
    "precision_observation_sha256",
    "fusion_decision_sha256",
    "proposals",
    "batch_sha256",
}


class ModelMotionBatchError(ValueError):
    """A model proposal batch is malformed or has inconsistent provenance."""


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ModelMotionBatchError(f"{label} must be nonempty text")
    result = value.strip()
    if any(ord(character) < 32 for character in result):
        raise ModelMotionBatchError(f"{label} contains a control character")
    return result


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ModelMotionBatchError(f"{label} must be a lowercase SHA-256 digest")
    return value


@dataclass(frozen=True, slots=True)
class ModelMotionBatch:
    batch_id: str
    request_id: str
    intent_plan_sha256: str
    scene_observation_sha256: str
    precision_observation_sha256: str
    fusion_decision_sha256: str
    proposals: tuple[ModelMotionProposal, ...]
    schema: str = SCHEMA

    def __post_init__(self) -> None:
        if self.schema != SCHEMA:
            raise ModelMotionBatchError(f"unsupported batch schema {self.schema!r}")
        object.__setattr__(self, "batch_id", _identifier(self.batch_id, "batch_id"))
        object.__setattr__(self, "request_id", _identifier(self.request_id, "request_id"))
        for field in (
            "intent_plan_sha256",
            "scene_observation_sha256",
            "precision_observation_sha256",
            "fusion_decision_sha256",
        ):
            object.__setattr__(self, field, _digest(getattr(self, field), field))
        proposals = tuple(self.proposals)
        if not 1 <= len(proposals) <= MAX_BATCH_PROPOSALS:
            raise ModelMotionBatchError(
                f"proposals must contain 1 to {MAX_BATCH_PROPOSALS} items"
            )
        if any(not isinstance(item, ModelMotionProposal) for item in proposals):
            raise ModelMotionBatchError("proposals must contain ModelMotionProposal values")
        proposal_ids = [item.proposal_id for item in proposals]
        if len(proposal_ids) != len(set(proposal_ids)):
            raise ModelMotionBatchError("proposal ids must be unique within a batch")
        first = proposals[0]
        for proposal in proposals[1:]:
            if proposal.device is not first.device:
                raise ModelMotionBatchError("one batch cannot mix target devices")
            if proposal.source != first.source:
                raise ModelMotionBatchError(
                    "all proposals must bind the same model, frame, and image"
                )
        object.__setattr__(self, "proposals", proposals)

    @classmethod
    def from_mapping(cls, value: object) -> "ModelMotionBatch":
        if not isinstance(value, Mapping) or set(value) != _FIELDS:
            raise ModelMotionBatchError(
                f"batch must contain exactly {sorted(_FIELDS)}"
            )
        raw_proposals = value["proposals"]
        if not isinstance(raw_proposals, Sequence) or isinstance(
            raw_proposals, (str, bytes)
        ):
            raise ModelMotionBatchError("proposals must be an array")
        try:
            proposals = tuple(
                ModelMotionProposal.from_mapping(item) for item in raw_proposals
            )
        except (MotionProposalError, TypeError, ValueError) as exc:
            raise ModelMotionBatchError(f"batch proposal is invalid: {exc}") from exc
        batch = cls(
            schema=value["schema"],
            batch_id=value["batch_id"],
            request_id=value["request_id"],
            intent_plan_sha256=value["intent_plan_sha256"],
            scene_observation_sha256=value["scene_observation_sha256"],
            precision_observation_sha256=value["precision_observation_sha256"],
            fusion_decision_sha256=value["fusion_decision_sha256"],
            proposals=proposals,
        )
        claimed = _digest(value["batch_sha256"], "batch_sha256")
        if claimed != batch.batch_sha256:
            raise ModelMotionBatchError("batch_sha256 does not match batch content")
        return batch

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "batch_id": self.batch_id,
            "request_id": self.request_id,
            "intent_plan_sha256": self.intent_plan_sha256,
            "scene_observation_sha256": self.scene_observation_sha256,
            "precision_observation_sha256": self.precision_observation_sha256,
            "fusion_decision_sha256": self.fusion_decision_sha256,
            "proposals": [item.to_dict() for item in self.proposals],
        }

    @property
    def batch_sha256(self) -> str:
        return hashlib.sha256(_canonical(self.unsigned_dict())).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {**self.unsigned_dict(), "batch_sha256": self.batch_sha256}


def decode_model_motion_batch_json(payload: bytes) -> ModelMotionBatch:
    """Strictly decode one bounded, duplicate-free AI handoff payload."""

    if not isinstance(payload, bytes):
        raise TypeError("payload must be bytes")
    if not payload or len(payload) > MAX_BATCH_BYTES:
        raise ModelMotionBatchError("batch payload is empty or exceeds its byte limit")

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ModelMotionBatchError(f"duplicate JSON field {key!r}")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise ModelMotionBatchError(f"non-finite JSON constant {value!r}")

    try:
        document = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ModelMotionBatchError("batch payload is not strict UTF-8 JSON") from exc
    return ModelMotionBatch.from_mapping(document)


__all__ = [
    "MAX_BATCH_PROPOSALS",
    "MAX_BATCH_BYTES",
    "SCHEMA",
    "ModelMotionBatch",
    "ModelMotionBatchError",
    "decode_model_motion_batch_json",
]
