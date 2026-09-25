"""Read-only compatibility adapter to RoCell's semantic text compilers."""

from __future__ import annotations

from typing import Any

from rocell.typing import PhoneStateError, UnsupportedCharacterError, compile_development_text

from .contract import validate_proposal, validate_result


def inspect(proposal: dict[str, str], observation: dict[str, Any]) -> dict[str, Any]:
    """Compile a supported proposal without camera, controller, or arm access."""

    validate_proposal(proposal)
    if not isinstance(observation, dict) or observation.get("ref") != proposal["observation_ref"]:
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
    try:
        plan = compile_development_text(proposal["device"], proposal["text"])
    except UnsupportedCharacterError:
        return blocked("unsupported_by_profile")
    except PhoneStateError:
        return blocked("phone_state_unverified")
    result = {
        **base,
        "status": "accepted",
        "profile_id": plan.profile_id,
        "plan_hash": plan.plan_hash,
        "action_plan": plan.to_dict(),
    }
    validate_result(result)
    return result
