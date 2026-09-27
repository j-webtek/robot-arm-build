"""Frozen prompt and input rendering for the mission-intent student."""

from __future__ import annotations

import hashlib
import json
from typing import Any


SYSTEM_PROMPT = """You are an offline semantic mission interpreter for RoCell.
Return exactly one JSON object matching rocell.mission_intent.v1 and no other text.
Copy request_id and observation_ref exactly from the input.
Use execute only for one exact type_text request on keyboard or phone.
Preserve literal text exactly, including command words inside quotes.
Keyboard lowercase typing uses keyboard.typing.lowercase and verify_after_each_action.
Phone lowercase typing uses phone.typing.lowercase and verify_after_each_state_change.
Stale observations or an unverified phone state do not change a clearly stated semantic typing intent; deterministic compilation will block it.
Use unsupported with keyboard.typing.shifted for shifted keyboard text and phone.dialer.call for phone calls.
Use clarify for missing or conflicting device, payload, or intent.
Never emit coordinates, joints, PWM, controller data, permits, transport fields, or success claims."""

PROMPT_SHA256 = hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest()


def render_user(record: dict[str, Any]) -> str:
    return json.dumps(
        {
            "request_id": record["id"],
            "request": record["request"],
            "observation": record["observation"],
        },
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    )
