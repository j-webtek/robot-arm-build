"""Frozen prompt surface for the compact mission-decision classifier."""

from __future__ import annotations

import hashlib
import json
from typing import Any


SYSTEM_PROMPT = """Classify one user request. Return exactly one JSON object matching the supplied schema and no other text.

Allowed outcomes:
- execute on keyboard
- execute on phone
- clarify device_ambiguous
- clarify payload_ambiguous
- clarify intent_ambiguous
- unsupported shifted_keyboard_text
- unsupported phone_call

Choose execute only for one explicit device, one double-quoted lowercase typing payload, and no additional operation. Treat a phone, mobile, or handset keyboard as phone unless the request explicitly contrasts it with a physical keyboard. Uppercase or shifted keyboard text is unsupported. Calling or dialing is unsupported. Do not copy payload text, identifiers, observations, capabilities, policies, coordinates, motion, or hardware fields."""

PROMPT_SHA256 = hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest()


def render_user(row: dict[str, Any]) -> str:
    request = row.get("request")
    if not isinstance(request, str) or not request:
        raise ValueError("mission decision row requires a nonempty request")
    return json.dumps({"request": request}, sort_keys=True, separators=(",", ":"))
