"""Strict model-authored coordinate proposals with no transport authority."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import re
from typing import Any, Mapping

from .frames import Point3Mm
from .units import finite_real


SCHEMA = "rocell.model_motion_proposal.v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FIELDS = {
    "schema",
    "proposal_id",
    "device",
    "target_id",
    "coordinate_frame",
    "target_mm",
    "interaction",
    "approach_clearance_mm",
    "speed_class",
    "confidence",
    "source",
}
_SOURCE_FIELDS = {"model_id", "frame_id", "image_sha256"}
_POINT_FIELDS = {"x", "y", "z"}


class MotionProposalError(ValueError):
    """A model proposal is malformed, ambiguous, or outside its contract."""


class ProposalDevice(str, Enum):
    KEYBOARD = "keyboard"
    PHONE = "phone"


class ProposalFrame(str, Enum):
    KEYBOARD_LOCAL = "keyboard_local"
    PHONE_SCREEN_LOCAL = "phone_screen_local"
    BOARD = "board"


class Interaction(str, Enum):
    HOVER = "HOVER"
    CONTACT = "CONTACT"


class SpeedClass(str, Enum):
    SLOW = "SLOW"
    NOMINAL = "NOMINAL"


def _identifier(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MotionProposalError(f"{name} must be a non-empty string")
    result = value.strip()
    if any(ord(character) < 32 for character in result):
        raise MotionProposalError(f"{name} contains a control character")
    return result


def _strict_mapping(value: object, fields: set[str], name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise MotionProposalError(f"{name} must contain exactly {sorted(fields)}")
    return value


@dataclass(frozen=True, slots=True)
class ProposalSource:
    model_id: str
    frame_id: str
    image_sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_id", _identifier(self.model_id, "model_id"))
        object.__setattr__(self, "frame_id", _identifier(self.frame_id, "frame_id"))
        if not isinstance(self.image_sha256, str) or _SHA256.fullmatch(self.image_sha256) is None:
            raise MotionProposalError("image_sha256 must be a lowercase SHA-256 digest")

    def to_dict(self) -> dict[str, str]:
        return {
            "model_id": self.model_id,
            "frame_id": self.frame_id,
            "image_sha256": self.image_sha256,
        }


@dataclass(frozen=True, slots=True)
class ModelMotionProposal:
    proposal_id: str
    device: ProposalDevice
    target_id: str
    target: Point3Mm
    interaction: Interaction
    approach_clearance_mm: float
    speed_class: SpeedClass
    confidence: float
    source: ProposalSource
    schema: str = SCHEMA

    def __post_init__(self) -> None:
        if self.schema != SCHEMA:
            raise MotionProposalError(f"Unsupported proposal schema {self.schema!r}")
        object.__setattr__(self, "proposal_id", _identifier(self.proposal_id, "proposal_id"))
        object.__setattr__(self, "target_id", _identifier(self.target_id, "target_id"))
        try:
            object.__setattr__(self, "device", ProposalDevice(self.device))
            object.__setattr__(self, "interaction", Interaction(self.interaction))
            object.__setattr__(self, "speed_class", SpeedClass(self.speed_class))
        except ValueError as exc:
            raise MotionProposalError(str(exc)) from exc
        if not isinstance(self.target, Point3Mm):
            raise MotionProposalError("target must be a Point3Mm")
        allowed_frames = {
            ProposalDevice.KEYBOARD: {ProposalFrame.KEYBOARD_LOCAL.value, ProposalFrame.BOARD.value},
            ProposalDevice.PHONE: {ProposalFrame.PHONE_SCREEN_LOCAL.value, ProposalFrame.BOARD.value},
        }
        if self.target.frame not in allowed_frames[self.device]:
            raise MotionProposalError(
                f"Frame {self.target.frame!r} is incompatible with device {self.device.value!r}"
            )
        clearance = finite_real(self.approach_clearance_mm, name="approach_clearance_mm")
        if clearance <= 0.0 or clearance > 250.0:
            raise MotionProposalError("approach_clearance_mm must be in (0, 250]")
        object.__setattr__(self, "approach_clearance_mm", clearance)
        confidence = finite_real(self.confidence, name="confidence")
        if not 0.0 <= confidence <= 1.0:
            raise MotionProposalError("confidence must be in [0, 1]")
        object.__setattr__(self, "confidence", confidence)
        if not isinstance(self.source, ProposalSource):
            raise MotionProposalError("source must be a ProposalSource")

    @classmethod
    def from_mapping(cls, value: object) -> "ModelMotionProposal":
        document = _strict_mapping(value, _FIELDS, "proposal")
        if document.get("schema") != SCHEMA:
            raise MotionProposalError(f"Unsupported proposal schema {document.get('schema')!r}")
        point = _strict_mapping(document.get("target_mm"), _POINT_FIELDS, "target_mm")
        source = _strict_mapping(document.get("source"), _SOURCE_FIELDS, "source")
        frame = _identifier(document.get("coordinate_frame"), "coordinate_frame")
        return cls(
            proposal_id=document.get("proposal_id"),
            device=document.get("device"),
            target_id=document.get("target_id"),
            target=Point3Mm(frame, point.get("x"), point.get("y"), point.get("z")),
            interaction=document.get("interaction"),
            approach_clearance_mm=document.get("approach_clearance_mm"),
            speed_class=document.get("speed_class"),
            confidence=document.get("confidence"),
            source=ProposalSource(
                model_id=source.get("model_id"),
                frame_id=source.get("frame_id"),
                image_sha256=source.get("image_sha256"),
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "proposal_id": self.proposal_id,
            "device": self.device.value,
            "target_id": self.target_id,
            "coordinate_frame": self.target.frame,
            "target_mm": {"x": self.target.x, "y": self.target.y, "z": self.target.z},
            "interaction": self.interaction.value,
            "approach_clearance_mm": self.approach_clearance_mm,
            "speed_class": self.speed_class.value,
            "confidence": self.confidence,
            "source": self.source.to_dict(),
        }

    @property
    def proposal_sha256(self) -> str:
        payload = json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()
