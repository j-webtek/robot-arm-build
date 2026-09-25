"""Replayable zero-write composition of intent, scene, and target observations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .multimodal_preview import guarded_preview
from .scene_observation import FrameEvidence, SHA256_PATTERN, canonical_hash, parse_utc


SCHEMA = "rocell.ai_shadow_preview.v0"
FIELDS = {
    "schema", "request_id", "request", "frame_id", "captured_at_utc", "evaluated_at_utc",
    "image_sha256", "scene_observation_sha256", "precision_observation_sha256", "result",
    "mode", "hardware_writes", "execution_permit_created", "execution_authorized", "shadow_sha256",
}


def validate(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != FIELDS or value.get("schema") != SCHEMA:
        raise ValueError("shadow preview has invalid schema or fields")
    for key in ("request_id", "request", "frame_id"):
        if not isinstance(value[key], str) or not value[key].strip():
            raise ValueError(f"shadow {key} is required")
    parse_utc(value["captured_at_utc"], "captured_at_utc")
    parse_utc(value["evaluated_at_utc"], "evaluated_at_utc")
    for key in ("image_sha256", "scene_observation_sha256", "precision_observation_sha256", "shadow_sha256"):
        if not isinstance(value[key], str) or SHA256_PATTERN.fullmatch(value[key]) is None:
            raise ValueError(f"invalid shadow {key}")
    if (value["mode"] != "OFFLINE_SHADOW" or type(value["hardware_writes"]) is not int
            or value["hardware_writes"] != 0
            or value["execution_permit_created"] is not False
            or value["execution_authorized"] is not False):
        raise ValueError("shadow preview cannot authorize or record hardware effects")
    if not isinstance(value["result"], dict) or value["result"].get("execution_authorized") is not False:
        raise ValueError("shadow result must remain unauthorized")
    core = {key: item for key, item in value.items() if key != "shadow_sha256"}
    if value["shadow_sha256"] != canonical_hash(core):
        raise ValueError("shadow preview hash mismatch")
    return value


def build(*, request: str, request_id: str, workspace: Path, frame: FrameEvidence,
          scene_observation: dict[str, Any], precision_observation: dict[str, Any],
          evaluated_at_utc: str, phone_state: str = "UNKNOWN") -> dict[str, Any]:
    """Compose existing read-only components and record their exact lineage."""
    result = guarded_preview(
        request,
        {"ref": frame.frame_id, "fresh": True, "phone_state": phone_state},
        request_id=request_id,
        workspace=workspace,
        frame=frame,
        scene_observation=scene_observation,
        precision_observation=precision_observation,
        evaluated_at_utc=evaluated_at_utc,
    )
    core = {
        "schema": SCHEMA,
        "request_id": request_id,
        "request": request,
        "frame_id": frame.frame_id,
        "captured_at_utc": frame.captured_at_utc,
        "evaluated_at_utc": evaluated_at_utc,
        "image_sha256": frame.image_sha256,
        "scene_observation_sha256": scene_observation.get("observation_sha256"),
        "precision_observation_sha256": precision_observation.get("observation_sha256"),
        "result": result,
        "mode": "OFFLINE_SHADOW",
        "hardware_writes": 0,
        "execution_permit_created": False,
        "execution_authorized": False,
    }
    return validate({**core, "shadow_sha256": canonical_hash(core)})
