"""Deterministic structural baseline for compact mission decisions.

This is a development diagnostic. It has no runtime or execution authority.
"""

from __future__ import annotations

import re

from .mission_decision import validate_mission_decision


_QUOTED = re.compile(r'"([^"\r\n]+)"')
_PHONE = re.compile(r"\b(?:phone|mobile|handset)\b", re.IGNORECASE)
_KEYBOARD = re.compile(r"\b(?:keyboard|keys)\b", re.IGNORECASE)
_PHONE_CALL = re.compile(r"\b(?:call|dial|telephone)\b", re.IGNORECASE)
_EXPLICIT_KEYBOARD_CONFLICT = re.compile(
    r"\b(?:physical|desk|hardware|computer)\s+keyboard\b|\bor\s+(?:the\s+)?keyboard\b",
    re.IGNORECASE,
)
_EXTRA_OPERATION = re.compile(
    r"\b(?:email|publish|post|send|forward|open|launch|call|dial|close|start|navigate|navigation)\w*\b",
    re.IGNORECASE,
)


def structural_decision(request: str) -> dict[str, str]:
    """Classify explicit structure; callers must treat uncovered language as development-only."""

    if not isinstance(request, str) or not request:
        raise ValueError("request must be nonempty text")
    literals = _QUOTED.findall(request)
    outside = _QUOTED.sub(" ", request)
    phone = bool(_PHONE.search(outside))
    keyboard = bool(_KEYBOARD.search(outside))
    if phone and _PHONE_CALL.search(outside) and not literals:
        decision = {
            "schema": "rocell.mission_decision.v1",
            "decision": "unsupported",
            "kind": "phone_call",
        }
    elif len(literals) != 1:
        decision = {
            "schema": "rocell.mission_decision.v1",
            "decision": "clarify",
            "reason": "payload_ambiguous",
        }
    else:
        if phone and keyboard and not _EXPLICIT_KEYBOARD_CONFLICT.search(outside):
            devices = {"phone"}
        else:
            devices = {name for name, present in (("phone", phone), ("keyboard", keyboard)) if present}
        if len(devices) != 1:
            decision = {
                "schema": "rocell.mission_decision.v1",
                "decision": "clarify",
                "reason": "device_ambiguous",
            }
        elif _EXTRA_OPERATION.search(outside):
            decision = {
                "schema": "rocell.mission_decision.v1",
                "decision": "clarify",
                "reason": "intent_ambiguous",
            }
        elif next(iter(devices)) == "keyboard" and any(char.isupper() for char in literals[0]):
            decision = {
                "schema": "rocell.mission_decision.v1",
                "decision": "unsupported",
                "kind": "shifted_keyboard_text",
            }
        else:
            decision = {
                "schema": "rocell.mission_decision.v1",
                "decision": "execute",
                "device": next(iter(devices)),
            }
    validate_mission_decision(decision)
    return decision
