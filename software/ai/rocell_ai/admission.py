"""Conservative request-grounding gate before offline plan inspection."""

from __future__ import annotations

import re
from typing import Any

from .adapter import inspect
from .contract import validate_proposal, validate_result


_QUOTED = re.compile(r'"([^"]*)"')
_DEVICE = re.compile(r"\b(?:keyboard|cell\s+phone|phone)\b", re.I)
_UNAVAILABLE = re.compile(r"\b(?:call|dial|send|open|launch|tap|swipe|delete|submit|press|save|share|search|navigate|click|run|execute|upload|post|publish)\b", re.I)
_SEQUENCE = re.compile(r"\b(?:and|or|then|after|before)\b", re.I)
_TYPING = re.compile(r"\b(?:type|typed|typing|enter|write|put|place|copy|transcribe)\b", re.I)


def admit(request: str, proposal: dict[str, Any], observation: dict[str, Any]) -> dict[str, Any]:
    """Require explicit text and device evidence; never issue hardware commands."""

    if not isinstance(request, str) or not isinstance(observation, dict):
        raise ValueError("request and observation must be supplied")
    validate_proposal(proposal)
    if observation.get("ref") != proposal["observation_ref"]:
        raise ValueError("observation reference mismatch")
    base = {
        "schema": "rocell.ai_plan_result.v0",
        "request_id": proposal["request_id"],
        "observation_ref": proposal["observation_ref"],
    }

    def blocked(reason: str) -> dict[str, Any]:
        result = {**base, "status": "blocked", "reason": reason}
        validate_result(result)
        return result

    if observation.get("fresh") is not True:
        return blocked("stale_observation")
    if proposal["decision"] != "type_text":
        return blocked(proposal["reason"])
    if proposal["device"] == "phone" and observation.get("phone_state") != "KEYBOARD_LOWER":
        return blocked("phone_state_unverified")

    quoted = _QUOTED.findall(request)
    outside = _QUOTED.sub(" ", request)
    # An already open editor describes context; "open the editor" requests a
    # separate operation and remains blocked by the unavailable-action check.
    outside = re.sub(r"\bopen\s+editor\b", "editor", outside, flags=re.I)
    if _UNAVAILABLE.search(outside):
        return blocked("operation_not_available")
    if _SEQUENCE.search(outside):
        return blocked("intent_ambiguous")
    if request.count('"') != 2 or len(quoted) != 1 or quoted[0] != proposal["text"]:
        return blocked("text_ambiguous")
    outside = re.sub(r"\b(?:cell\s+)?phone\s+keyboard\b", "phone", outside, flags=re.I)
    devices = {"phone" if "phone" in match.group().casefold() else "keyboard" for match in _DEVICE.finditer(outside)}
    if devices != {proposal["device"]}:
        return blocked("device_ambiguous")
    if not _TYPING.search(outside):
        return blocked("intent_ambiguous")
    return inspect(proposal, observation)
