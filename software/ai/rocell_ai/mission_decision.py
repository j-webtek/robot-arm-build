"""Compact model decision and deterministic binding to MissionIntentV1."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from .mission_intent import validate_mission_intent


DECISION_SCHEMA = "rocell.mission_decision.v1"
ASSEMBLY_SCHEMA = "rocell.mission_decision_assembly.v1"
_SHAPES = {
    "execute": {"schema", "decision", "device"},
    "clarify": {"schema", "decision", "reason"},
    "unsupported": {"schema", "decision", "kind"},
}
_CLARIFY = {"device_ambiguous", "payload_ambiguous", "intent_ambiguous"}
_KINDS = {"shifted_keyboard_text", "phone_call"}
_QUOTED = re.compile(r'"([^"\r\n]+)"')
_DEVICE_WORDS = {
    "keyboard": re.compile(r"\b(?:keyboard|keys)\b", re.IGNORECASE),
    "phone": re.compile(r"\b(?:phone|mobile|handset)\b", re.IGNORECASE),
}
_EXTRA_OPERATION = re.compile(
    r"\b(?:email|publish|post|send|forward|open|launch|call|dial|close|start|navigate|navigation)\b",
    re.IGNORECASE,
)


def _pairs_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def decode_mission_decision(payload: str) -> dict[str, Any]:
    if not isinstance(payload, str) or len(payload.encode("utf-8")) > 4096:
        raise ValueError("mission decision must be bounded JSON")
    try:
        value = json.loads(payload, object_pairs_hook=_pairs_without_duplicates)
    except json.JSONDecodeError as error:
        raise ValueError("mission decision is not valid JSON") from error
    validate_mission_decision(value)
    return value


def validate_mission_decision(value: Any) -> None:
    if not isinstance(value, dict) or value.get("schema") != DECISION_SCHEMA:
        raise ValueError("invalid mission decision schema")
    decision = value.get("decision")
    if decision not in _SHAPES or set(value) != _SHAPES[decision]:
        raise ValueError("invalid mission decision fields")
    if decision == "execute" and value["device"] not in {"keyboard", "phone"}:
        raise ValueError("invalid execution device")
    if decision == "clarify" and value["reason"] not in _CLARIFY:
        raise ValueError("invalid clarification reason")
    if decision == "unsupported" and value["kind"] not in _KINDS:
        raise ValueError("invalid unsupported kind")


def _mission_base(request_id: str, observation_ref: str) -> dict[str, str]:
    for name, value in (("request_id", request_id), ("observation_ref", observation_ref)):
        if not isinstance(value, str) or not value or any(ord(char) < 32 for char in value):
            raise ValueError(f"{name} must be a nonempty identifier")
    return {
        "schema": "rocell.mission_intent.v1",
        "request_id": request_id,
        "observation_ref": observation_ref,
    }


def _clarify(base: dict[str, str], reason: str) -> dict[str, Any]:
    return {**base, "decision": "clarify", "reason": reason}


def assemble_mission_decision(
    decision: dict[str, Any],
    *,
    request_id: str,
    observation_ref: str,
    request: str,
) -> dict[str, Any]:
    """Ground a compact decision; unsafe execute claims downgrade to clarify."""

    validate_mission_decision(decision)
    if not isinstance(request, str) or not request:
        raise ValueError("request must be nonempty text")
    base = _mission_base(request_id, observation_ref)
    original_decision_sha256 = hashlib.sha256(
        json.dumps(decision, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    status = "assembled"
    downgrade_reason = None

    if decision["decision"] == "clarify":
        mission = _clarify(base, decision["reason"])
    elif decision["decision"] == "unsupported":
        if decision["kind"] == "shifted_keyboard_text":
            mission = {
                **base,
                "decision": "unsupported",
                "operation": "type_text",
                "device": "keyboard",
                "required_capability": "keyboard.typing.shifted",
                "reason": "unsupported_by_profile",
            }
        else:
            mission = {
                **base,
                "decision": "unsupported",
                "operation": "place_phone_call",
                "device": "phone",
                "required_capability": "phone.dialer.call",
                "reason": "operation_not_available",
            }
    else:
        literals = _QUOTED.findall(request)
        outside = _QUOTED.sub(" ", request)
        mentions = {
            device for device, pattern in _DEVICE_WORDS.items() if pattern.search(outside)
        }
        if len(literals) != 1:
            downgrade_reason = "payload_ambiguous"
        elif mentions != {decision["device"]}:
            downgrade_reason = "device_ambiguous"
        elif _EXTRA_OPERATION.search(outside):
            downgrade_reason = "intent_ambiguous"
        if downgrade_reason is not None:
            status = "downgraded"
            mission = _clarify(base, downgrade_reason)
        else:
            device = decision["device"]
            mission = {
                **base,
                "decision": "execute",
                "operation": "type_text",
                "device": device,
                "arguments": {"text": literals[0]},
                "required_capability": f"{device}.typing.lowercase",
                "observation_policy": (
                    "verify_after_each_action"
                    if device == "keyboard"
                    else "verify_after_each_state_change"
                ),
            }
    validate_mission_intent(mission)
    return {
        "schema": ASSEMBLY_SCHEMA,
        "status": status,
        "decision_sha256": original_decision_sha256,
        "downgrade_reason": downgrade_reason,
        "mission_intent": mission,
        "hardware_writes": 0,
        "physical_movements": 0,
    }
