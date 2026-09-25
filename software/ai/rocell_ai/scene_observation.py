"""Strict, image-bound scene observations for multimodal vision runtimes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import re
from typing import Any, Protocol


SCHEMA = "rocell.ai_scene_observation.v0"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
DEVICE_PRESENCE = {"absent", "keyboard", "phone", "both", "uncertain"}
KEYBOARD_LAYOUTS = {"us_qwerty", "unknown", "not_visible"}
PHONE_STATES = {"not_visible", "unknown", "home", "dialer", "keyboard_lower", "call_confirmation"}
LIGHTING = {"acceptable", "dark", "overexposed", "uneven", "unknown"}
IMAGE_LEVELS = {"none", "low", "high", "unknown"}
OCCLUDERS = {"none", "arm", "tool", "cable", "hand", "multiple", "unknown"}
ABSTAIN_REASONS = {
    "device_absent", "device_uncertain", "layout_uncertain", "state_uncertain",
    "lighting_adverse", "blur_adverse", "glare_adverse", "occluded",
    "critical_targets_hidden", "model_refusal", "invalid_output", "runtime_error",
}


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def parse_utc(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{label} must be an RFC 3339 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{label} must be an RFC 3339 UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError(f"{label} must use UTC")
    return parsed


def _bounded_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be finite")
    result = float(value)
    if not 0.0 <= result <= 1.0:
        raise ValueError(f"{label} must be between 0 and 1")
    return result


@dataclass(frozen=True)
class FrameEvidence:
    frame_id: str
    captured_at_utc: str
    image_bytes: bytes

    def __post_init__(self) -> None:
        if not isinstance(self.frame_id, str) or not self.frame_id.strip():
            raise ValueError("frame_id is required")
        parse_utc(self.captured_at_utc, "captured_at_utc")
        if not isinstance(self.image_bytes, bytes) or not self.image_bytes:
            raise ValueError("image_bytes must be nonempty bytes")

    @property
    def image_sha256(self) -> str:
        return hashlib.sha256(self.image_bytes).hexdigest()


class VisionObserver(Protocol):
    def observe(self, frame: FrameEvidence) -> dict[str, Any]: ...


def model_output_schema() -> dict[str, Any]:
    """JSON schema for the fields the multimodal model must classify."""
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "device_presence", "keyboard_layout", "phone_state", "lighting", "blur",
            "glare", "occlusion_source", "occlusion_fraction", "critical_targets_visible",
            "confidence",
        ],
        "properties": {
            "device_presence": {"type": "string", "enum": sorted(DEVICE_PRESENCE)},
            "keyboard_layout": {"type": "string", "enum": sorted(KEYBOARD_LAYOUTS)},
            "phone_state": {"type": "string", "enum": sorted(PHONE_STATES)},
            "lighting": {"type": "string", "enum": sorted(LIGHTING)},
            "blur": {"type": "string", "enum": sorted(IMAGE_LEVELS)},
            "glare": {"type": "string", "enum": sorted(IMAGE_LEVELS)},
            "occlusion_source": {"type": "string", "enum": sorted(OCCLUDERS)},
            "occlusion_fraction": {"type": "number", "minimum": 0, "maximum": 1},
            "critical_targets_visible": {"type": "boolean"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
    }


MODEL_FIELDS = set(model_output_schema()["required"])
OBSERVATION_FIELDS = MODEL_FIELDS | {
    "schema", "frame_id", "captured_at_utc", "image_sha256", "runtime",
    "model", "model_identity", "abstain", "abstain_reasons", "observation_sha256",
}


def validate_model_output(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != MODEL_FIELDS:
        raise ValueError("scene model output has invalid fields")
    enum_fields = {
        "device_presence": DEVICE_PRESENCE,
        "keyboard_layout": KEYBOARD_LAYOUTS,
        "phone_state": PHONE_STATES,
        "lighting": LIGHTING,
        "blur": IMAGE_LEVELS,
        "glare": IMAGE_LEVELS,
        "occlusion_source": OCCLUDERS,
    }
    for key, allowed in enum_fields.items():
        if not isinstance(value[key], str) or value[key] not in allowed:
            raise ValueError(f"invalid {key}")
    value["occlusion_fraction"] = _bounded_number(value["occlusion_fraction"], "occlusion_fraction")
    value["confidence"] = _bounded_number(value["confidence"], "confidence")
    for key in ("critical_targets_visible",):
        if not isinstance(value[key], bool):
            raise ValueError(f"{key} must be boolean")
    return value


def _derived_abstain_reasons(value: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if value["device_presence"] == "absent":
        reasons.append("device_absent")
    elif value["device_presence"] == "uncertain":
        reasons.append("device_uncertain")
    if value["device_presence"] in {"keyboard", "both"} and value["keyboard_layout"] != "us_qwerty":
        reasons.append("layout_uncertain")
    if value["device_presence"] in {"phone", "both"} and value["phone_state"] == "unknown":
        reasons.append("state_uncertain")
    if value["lighting"] != "acceptable":
        reasons.append("lighting_adverse")
    if value["blur"] not in {"none", "low"}:
        reasons.append("blur_adverse")
    if value["glare"] not in {"none", "low"}:
        reasons.append("glare_adverse")
    if value["occlusion_fraction"] > 0.20:
        reasons.append("occluded")
    if not value["critical_targets_visible"]:
        reasons.append("critical_targets_hidden")
    return reasons


def build_observation(*, frame: FrameEvidence, runtime: str, model: str,
                      model_identity: str, model_output: dict[str, Any],
                      forced_abstain_reasons: tuple[str, ...] = ()) -> dict[str, Any]:
    validated = validate_model_output(dict(model_output))
    for label, item in (("runtime", runtime), ("model", model), ("model_identity", model_identity)):
        if not isinstance(item, str) or not item.strip() or len(item) > 256:
            raise ValueError(f"{label} must be nonempty and bounded")
    if any(reason not in ABSTAIN_REASONS for reason in forced_abstain_reasons):
        raise ValueError("invalid forced abstain reason")
    reasons = list(dict.fromkeys([*_derived_abstain_reasons(validated), *forced_abstain_reasons]))
    core = {
        "schema": SCHEMA,
        "frame_id": frame.frame_id,
        "captured_at_utc": frame.captured_at_utc,
        "image_sha256": frame.image_sha256,
        "runtime": runtime,
        "model": model,
        "model_identity": model_identity,
        **validated,
        "abstain": bool(reasons),
        "abstain_reasons": reasons,
    }
    return {**core, "observation_sha256": canonical_hash(core)}


def validate_observation(value: Any, *, frame: FrameEvidence | None = None) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != OBSERVATION_FIELDS or value.get("schema") != SCHEMA:
        raise ValueError("scene observation has invalid schema or fields")
    validate_model_output({key: value[key] for key in MODEL_FIELDS})
    reasons = value["abstain_reasons"]
    if (not isinstance(reasons, list) or len(reasons) > len(ABSTAIN_REASONS)
            or len(set(reasons)) != len(reasons)
            or any(not isinstance(reason, str) or reason not in ABSTAIN_REASONS for reason in reasons)):
        raise ValueError("invalid scene abstain_reasons")
    derived = _derived_abstain_reasons(value)
    externally_forced = {"model_refusal", "invalid_output", "runtime_error"}
    if any(reason not in reasons for reason in derived) or any(
        reason not in derived and reason not in externally_forced for reason in reasons
    ):
        raise ValueError("scene abstain_reasons do not match classifications")
    if not isinstance(value["abstain"], bool) or value["abstain"] != bool(value["abstain_reasons"]):
        raise ValueError("scene abstain must match abstain_reasons")
    if not isinstance(value["frame_id"], str) or not value["frame_id"].strip():
        raise ValueError("scene frame_id is required")
    parse_utc(value["captured_at_utc"], "captured_at_utc")
    if not isinstance(value["image_sha256"], str) or SHA256_PATTERN.fullmatch(value["image_sha256"]) is None:
        raise ValueError("invalid scene image_sha256")
    for key in ("runtime", "model", "model_identity"):
        if not isinstance(value[key], str) or not value[key].strip() or len(value[key]) > 256:
            raise ValueError(f"invalid scene {key}")
    core = {key: item for key, item in value.items() if key != "observation_sha256"}
    if not isinstance(value["observation_sha256"], str) or value["observation_sha256"] != canonical_hash(core):
        raise ValueError("scene observation hash mismatch")
    if frame is not None and (
        value["frame_id"] != frame.frame_id
        or value["captured_at_utc"] != frame.captured_at_utc
        or value["image_sha256"] != frame.image_sha256
    ):
        raise ValueError("scene observation does not bind the supplied frame")
    return value


class FixtureVisionObserver:
    """Deterministic observer for tests; it performs no image inference."""

    def __init__(self, model_output: dict[str, Any]) -> None:
        self._model_output = validate_model_output(dict(model_output))

    def observe(self, frame: FrameEvidence) -> dict[str, Any]:
        return build_observation(
            frame=frame,
            runtime="fixture",
            model="deterministic-scene-fixture-v0",
            model_identity=canonical_hash(self._model_output),
            model_output=self._model_output,
        )
