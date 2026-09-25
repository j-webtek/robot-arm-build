"""Conservative deterministic baseline for the first offline benchmark.

This module has no arm, camera, network, or execution adapter. RoCell's own
typing compiler remains the authority for supported characters and plan shape.
"""

from __future__ import annotations

import re
from typing import Any

from rocell.typing import UnsupportedCharacterError, compile_development_text

from . import SCHEMA_ID


_DEVICE = r"(?:physical\s+)?(?:keyboard|cell\s+phone|phone)"
_DEVICE_RE = re.compile(rf"\b(?:the\s+)?(?P<device>{_DEVICE})\b", re.I)
_TYPE_RE = re.compile(r"^\s*(?:please\s+)?(?:type|enter)\s+", re.I)
_PREFIX_DEVICE_RE = re.compile(rf"^\s*(?:on|into|in|using)\s+(?:the\s+)?{_DEVICE}\s*[,;:]\s*(?:please\s+)?(?:type|enter)\s+", re.I)
_SUFFIX_DEVICE_RE = re.compile(rf"\s+(?:on|into|in|using)\s+(?:the\s+)?{_DEVICE}\s*[.!?]?\s*$", re.I)
_QUOTED_SUFFIX_RE = re.compile(rf'^\s*(?:please\s+)?(?:type|enter)\s+"(?P<text>[^"]*)"\s+(?:on|into|in|using)\s+(?:the\s+)?{_DEVICE}\s*[.!?]?\s*$', re.I)
_QUOTED_PREFIX_RE = re.compile(rf'^\s*(?:on|into|in|using)\s+(?:the\s+)?{_DEVICE}\s*[,;:]\s*(?:please\s+)?(?:type|enter)\s+"(?P<text>[^"]*)"\s*[.!?]?\s*$', re.I)


def _decision(request_id: str, observation_ref: str, decision: str, **fields: str) -> dict[str, str]:
    return {
        "schema": SCHEMA_ID,
        "request_id": request_id,
        "observation_ref": observation_ref,
        "decision": decision,
        **fields,
    }


def propose(*, request_id: str, request: str, observation: dict[str, Any]) -> dict[str, str]:
    """Return a task proposal, clarification, or unsupported result.

    The input observation is a benchmark fixture, not live camera/arm evidence.
    An actual execution adapter must validate fresh source identity separately.
    """

    if not isinstance(request_id, str) or not request_id.strip():
        raise ValueError("request_id must be nonempty")
    if not isinstance(request, str):
        raise TypeError("request must be a string")
    if not isinstance(observation, dict):
        raise TypeError("observation must be an object")
    observation_ref = observation.get("ref")
    if not isinstance(observation_ref, str) or not observation_ref.strip():
        raise ValueError("observation.ref must be nonempty")
    if observation.get("fresh") is not True:
        return _decision(request_id, observation_ref, "unsupported", reason="stale_observation")

    raw = request.strip()
    outside_quotes = re.sub(r'"[^"]*"', '""', raw)
    if re.search(r"\b(?:call|dial)\b", outside_quotes, re.I):
        return _decision(request_id, observation_ref, "unsupported", reason="operation_not_available")
    devices = {"phone" if "phone" in match.group("device").lower() else "keyboard" for match in _DEVICE_RE.finditer(outside_quotes)}
    if len(devices) != 1:
        return _decision(request_id, observation_ref, "clarify", reason="device_ambiguous")
    device = next(iter(devices))

    quoted = re.findall(r'"([^"]*)"', raw)
    if len(quoted) > 1:
        return _decision(request_id, observation_ref, "clarify", reason="text_ambiguous")
    if quoted:
        match = _QUOTED_SUFFIX_RE.fullmatch(raw) or _QUOTED_PREFIX_RE.fullmatch(raw)
        if match is None:
            return _decision(request_id, observation_ref, "clarify", reason="intent_ambiguous")
        text = match.group("text")
    else:
        prefix = _PREFIX_DEVICE_RE.match(raw)
        if prefix:
            text = raw[prefix.end():]
        else:
            start = _TYPE_RE.match(raw)
            suffix = _SUFFIX_DEVICE_RE.search(raw)
            if not start or not suffix or suffix.start() <= start.end():
                return _decision(request_id, observation_ref, "clarify", reason="intent_ambiguous")
            text = raw[start.end():suffix.start()]
        text = text.strip()
        if not text or text.endswith(("?", "!")):
            return _decision(request_id, observation_ref, "clarify", reason="text_ambiguous")

    if not text:
        return _decision(request_id, observation_ref, "clarify", reason="text_ambiguous")
    if device == "phone" and observation.get("phone_state") != "KEYBOARD_LOWER":
        return _decision(request_id, observation_ref, "unsupported", reason="phone_state_unverified")
    try:
        compile_development_text(device, text)
    except UnsupportedCharacterError:
        return _decision(request_id, observation_ref, "unsupported", reason="unsupported_by_profile")
    return _decision(request_id, observation_ref, "type_text", device=device, text=text)
