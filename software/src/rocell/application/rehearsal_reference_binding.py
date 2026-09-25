"""Immutable provenance for nominal reference-frame diagnostics, never authority.

The service derives these inputs from independently verified M1 review trios.
Camera results and the serial campaign are dependencies, not measured points or
calibrated joint angles. The small source snapshot supplies the actual nominal
geometry; bytes prevent a caller from mutating nested inputs after binding.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any

from rocell.application.physical_connection_contracts import canonical_sha256

SCHEMA = "rocell.rehearsal_reference_binding.v1"
MAX_SOURCE_CONTEXT_BYTES = 16 * 1024
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\Z")
_ACTOR = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")
_PREDECESSORS = (
    "optics_intrinsics",
    "static_registration",
    "feedback_only_connection",
)


def _digest(value: object) -> None:
    if type(value) is not str or not _HASH.fullmatch(value) or value == "0" * 64:
        raise ValueError("An exact nonzero source/evidence digest is required")


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


@dataclass(frozen=True, slots=True)
class ReviewedReferencePredecessor:
    stage: str
    receipt_sha256: str
    assessment_sha256: str
    review_sha256: str
    evaluation_sha256: str

    def __post_init__(self) -> None:
        if type(self.stage) is not str or self.stage not in _PREDECESSORS:
            raise ValueError(
                "Only reviewed optics, registration and feedback are inputs"
            )
        for name in (
            "receipt_sha256",
            "assessment_sha256",
            "review_sha256",
            "evaluation_sha256",
        ):
            _digest(getattr(self, name))

    def to_dict(self) -> dict[str, str]:
        return {
            "stage": self.stage,
            "receipt_sha256": self.receipt_sha256,
            "assessment_sha256": self.assessment_sha256,
            "review_sha256": self.review_sha256,
            "evaluation_sha256": self.evaluation_sha256,
        }


@dataclass(frozen=True, slots=True)
class RehearsalReferenceBinding:
    workspace_source_sha256: str
    catalog_sha256: str
    cell_id: str
    session_id: str
    operator_id: str
    predecessors: tuple[ReviewedReferencePredecessor, ...]
    camera_capture_receipt_sha256: str
    feedback_binding_sha256: str
    campaign_context_binding_sha256: str
    retained_campaign_sha256: str
    feedback_inner_evidence_sha256: str
    feedback_request_sha256: str
    controller_binding_sha256: str
    final_power_observation_sha256: str
    source_context_json: bytes

    def __post_init__(self) -> None:
        for name in (
            "workspace_source_sha256",
            "catalog_sha256",
            "camera_capture_receipt_sha256",
            "feedback_binding_sha256",
            "campaign_context_binding_sha256",
            "retained_campaign_sha256",
            "feedback_inner_evidence_sha256",
            "feedback_request_sha256",
            "controller_binding_sha256",
            "final_power_observation_sha256",
        ):
            _digest(getattr(self, name))
        for name in ("cell_id", "session_id", "operator_id"):
            value = getattr(self, name)
            pattern = _ACTOR if name == "operator_id" else _ID
            if type(value) is not str or not pattern.fullmatch(value):
                raise ValueError(
                    "An exact bounded session/operator identifier is required"
                )
        if (
            type(self.predecessors) is not tuple
            or len(self.predecessors) != len(_PREDECESSORS)
            or any(
                type(item) is not ReviewedReferencePredecessor
                for item in self.predecessors
            )
            or tuple(item.stage for item in self.predecessors) != _PREDECESSORS
        ):
            raise ValueError(
                "Exactly the ordered stage-7, stage-8 and stage-12 reviews are required"
            )
        if type(self.source_context_json) is not bytes or not (
            0 < len(self.source_context_json) <= MAX_SOURCE_CONTEXT_BYTES
        ):
            raise ValueError(
                "The immutable source snapshot must fit its explicit byte limit"
            )
        try:
            context = json.loads(self.source_context_json)
            if (
                type(context) is not dict
                or set(context)
                != {
                    "schema",
                    "static_phase1_graph_sha256",
                    "static_phase1_context_hashes",
                    "nominal_geometry",
                }
                or context["schema"] != "rocell.rehearsal_reference_sources.v1"
                or type(context["nominal_geometry"]) is not dict
                or type(context["static_phase1_context_hashes"]) is not dict
                or not context["static_phase1_context_hashes"]
                or _canonical(context) != self.source_context_json
            ):
                raise ValueError(
                    "Source snapshot is not exact canonical reference input"
                )
            _digest(context["static_phase1_graph_sha256"])
            for key, value in context["static_phase1_context_hashes"].items():
                if type(key) is not str or not key or len(key) > 128:
                    raise ValueError("Source context names must be bounded strings")
                _digest(value)
        except (UnicodeError, TypeError, RecursionError) as error:
            raise ValueError("Source snapshot is not bounded JSON") from error

    @property
    def source_context(self) -> dict[str, Any]:
        """Return a detached view; callers cannot change the frozen input bytes."""
        return json.loads(self.source_context_json)

    def to_dict(self) -> dict[str, Any]:
        result = {
            name: getattr(self, name)
            for name in (
                "workspace_source_sha256",
                "catalog_sha256",
                "cell_id",
                "session_id",
                "operator_id",
                "camera_capture_receipt_sha256",
                "feedback_binding_sha256",
                "campaign_context_binding_sha256",
                "retained_campaign_sha256",
                "feedback_inner_evidence_sha256",
                "feedback_request_sha256",
                "controller_binding_sha256",
                "final_power_observation_sha256",
            )
        }
        result.update(
            schema=SCHEMA,
            stage="reference_frame_calibration",
            predecessors=[item.to_dict() for item in self.predecessors],
            source_context=self.source_context,
            origin="SYNTHETIC_REHEARSAL",
            camera_input_role="DEPENDENCY_ONLY_NOT_NUMERIC_INPUT",
            feedback_input_role="DEPENDENCY_ONLY_NOT_CALIBRATED_JOINTS",
            physical_authority=False,
        )
        return result

    @property
    def binding_sha256(self) -> str:
        return canonical_sha256(self.to_dict())
