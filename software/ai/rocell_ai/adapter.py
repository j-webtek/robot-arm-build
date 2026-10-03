"""Read-only compatibility adapter to RoCell's semantic text compilers."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random
import string
from typing import Any

from rocell.typing import PhoneStateError, UnsupportedCharacterError, compile_development_text

from .contract import validate_proposal, validate_result


_DESKTOP_SHIFTED_CHARACTERS = frozenset(
    string.ascii_uppercase + '~!@#$%^&*()_+{}|:"<>?'
)
_PHONE_LAYERED_CHARACTERS = frozenset(
    string.ascii_uppercase + string.digits + string.punctuation
)
_US_SHIFTED_TO_BASE = {
    "~": "GRAVE",
    "!": "1",
    "@": "2",
    "#": "3",
    "$": "4",
    "%": "5",
    "^": "6",
    "&": "7",
    "*": "8",
    "(": "9",
    ")": "0",
    "_": "MINUS",
    "+": "EQUAL",
    "{": "LEFT_BRACKET",
    "}": "RIGHT_BRACKET",
    "|": "BACKSLASH",
    ":": "SEMICOLON",
    '"': "APOSTROPHE",
    "<": "COMMA",
    ">": "PERIOD",
    "?": "SLASH",
}
_US_UNSHIFTED_TO_KEY = {
    "`": "GRAVE",
    "-": "MINUS",
    "=": "EQUAL",
    "[": "LEFT_BRACKET",
    "]": "RIGHT_BRACKET",
    "\\": "BACKSLASH",
    ";": "SEMICOLON",
    "'": "APOSTROPHE",
    ",": "COMMA",
    ".": "PERIOD",
    "/": "SLASH",
    " ": "SPACE",
}
US_PRINTABLE_BASE_KEY_IDS = tuple(sorted(
    set(string.ascii_uppercase)
    | set(string.digits)
    | set(_US_SHIFTED_TO_BASE.values())
    | set(_US_UNSHIFTED_TO_KEY.values())
))

_TARGET_EXTENSION_SEEDS = {
    "SHIFT": {
        "presentation_center_xy_mm": [20.0, 48.0],
        "presentation_width_mm": 37.0,
        "proposed_press_point_xy_mm": [20.0, 48.0],
        "proposed_safe_half_extent_mm": [7.0, 7.0],
        "source_literal": '("SHIFT", ox + 20.0, oy + 48.0, 37.0)',
        "press_point_rule": (
            "EXPLICIT_MAXIMUM_EDGE_CLEARANCE_POINT_WITH_CONSERVATIVE_14_BY_14_MM_PATCH_"
            "NOT_FULL_WIDE_KEY_CENTER_DEFAULT"
        ),
    },
    "LEFT_BRACKET": {
        "presentation_center_xy_mm": [231.5, 90.0],
        "presentation_width_mm": 15.6,
        "proposed_press_point_xy_mm": [231.5, 90.0],
        "proposed_safe_half_extent_mm": [7.0, 7.0],
        "source_literal": '("[", ox + 231.5, oy + 90.0, 15.6)',
        "press_point_rule": "EXPLICIT_MAXIMUM_EDGE_CLEARANCE_POINT",
    },
    "RIGHT_BRACKET": {
        "presentation_center_xy_mm": [250.5, 90.0],
        "presentation_width_mm": 15.6,
        "proposed_press_point_xy_mm": [250.5, 90.0],
        "proposed_safe_half_extent_mm": [7.0, 7.0],
        "source_literal": '("]", ox + 250.5, oy + 90.0, 15.6)',
        "press_point_rule": "EXPLICIT_MAXIMUM_EDGE_CLEARANCE_POINT",
    },
    "BACKSLASH": {
        "presentation_center_xy_mm": [269.5, 90.0],
        "presentation_width_mm": 15.6,
        "proposed_press_point_xy_mm": [269.5, 90.0],
        "proposed_safe_half_extent_mm": [7.0, 7.0],
        "source_literal": '("\\\\", ox + 269.5, oy + 90.0, 15.6)',
        "press_point_rule": "EXPLICIT_MAXIMUM_EDGE_CLEARANCE_POINT",
    },
}


class StickyKeysReplayError(ValueError):
    """A sequence violates the commissioned one-shot modifier contract."""


def compile_virtual_us_sticky_keys(
    text: str, *, commissioned_key_ids: tuple[str, ...]
) -> tuple[str, ...]:
    """Compile printable ASCII only when every emitted key is commissioned."""

    commissioned = frozenset(commissioned_key_ids)
    sequence: list[str] = []
    for index, character in enumerate(text):
        keys: tuple[str, ...]
        if "a" <= character <= "z":
            keys = (character.upper(),)
        elif "A" <= character <= "Z":
            keys = ("SHIFT", character)
        elif character in string.digits:
            keys = (character,)
        elif character in _US_SHIFTED_TO_BASE:
            keys = ("SHIFT", _US_SHIFTED_TO_BASE[character])
        elif character in _US_UNSHIFTED_TO_KEY:
            keys = (_US_UNSHIFTED_TO_KEY[character],)
        else:
            raise StickyKeysReplayError(
                f"unsupported virtual US character {character!r} at index {index}"
            )
        missing = tuple(key_id for key_id in keys if key_id not in commissioned)
        if missing:
            raise StickyKeysReplayError(
                f"uncommissioned key(s) {missing!r} for character {character!r} at index {index}"
            )
        sequence.extend(keys)
    if any(left == right == "SHIFT" for left, right in zip(sequence, sequence[1:])):
        raise StickyKeysReplayError("compiler emitted consecutive Shift presses")
    return tuple(sequence)


def replay_virtual_us_sticky_keys(
    sequence: tuple[str, ...],
    *,
    five_shift_shortcut_disabled: bool,
    turn_off_on_two_keys_disabled: bool,
) -> dict[str, Any]:
    """Replay the Windows one-shot latch semantics without OS or device access."""

    if not five_shift_shortcut_disabled:
        raise StickyKeysReplayError("five-Shift shortcut is not disabled")
    if not turn_off_on_two_keys_disabled:
        raise StickyKeysReplayError("two-key disable behavior is not disabled")
    reverse_unshifted = {key: value for value, key in _US_UNSHIFTED_TO_KEY.items()}
    reverse_shifted = {key: value for value, key in _US_SHIFTED_TO_BASE.items()}
    state = "OFF"
    consecutive_shifts = 0
    output: list[str] = []
    verification: list[dict[str, str]] = []
    for index, key_id in enumerate(sequence):
        if key_id == "SHIFT":
            consecutive_shifts += 1
            if consecutive_shifts >= 2:
                raise StickyKeysReplayError(
                    f"consecutive Shift at action {index} would enter locked state"
                )
            state = "LATCHED"
            verification.append({"key": "SHIFT", "expected_modifier_state": "LATCHED"})
            continue
        consecutive_shifts = 0
        if len(key_id) == 1 and "A" <= key_id <= "Z":
            character = key_id if state == "LATCHED" else key_id.lower()
        elif key_id in string.digits:
            character = reverse_shifted[key_id] if state == "LATCHED" else key_id
        elif state == "LATCHED" and key_id in reverse_shifted:
            character = reverse_shifted[key_id]
        elif state == "OFF" and key_id in reverse_unshifted:
            character = reverse_unshifted[key_id]
        else:
            raise StickyKeysReplayError(
                f"key {key_id!r} is invalid in modifier state {state} at action {index}"
            )
        output.append(character)
        state = "OFF"
        verification.append({"key": key_id, "expected_modifier_state": "OFF"})
    if state != "OFF":
        raise StickyKeysReplayError("sequence ends with a latched modifier")
    return {
        "text": "".join(output),
        "final_modifier_state": state,
        "keystroke_log_expectations": verification,
        "dialog_triggered": False,
        "sticky_keys_disabled": False,
    }


def run_seeded_sticky_keys_replay(
    *, seed: int, string_count: int, maximum_length: int
) -> dict[str, Any]:
    """Replay fixed edge cases and seeded printable-ASCII strings deterministically."""

    if type(seed) is not int or type(string_count) is not int or string_count < 1:
        raise ValueError("seed must be an integer and string_count must be positive")
    if type(maximum_length) is not int or maximum_length < 1:
        raise ValueError("maximum_length must be positive")
    alphabet = "".join(chr(value) for value in range(32, 127))
    fixed_cases = ("AA", "!!", "aA", "A", " A")
    generator = random.Random(seed)
    random_cases = tuple(
        "".join(generator.choice(alphabet) for _ in range(generator.randint(1, maximum_length)))
        for _ in range(string_count)
    )
    cases = fixed_cases + random_cases
    commissioned = tuple((*US_PRINTABLE_BASE_KEY_IDS, "SHIFT"))
    total_characters = 0
    total_actions = 0
    total_shift_presses = 0
    for text in cases:
        sequence = compile_virtual_us_sticky_keys(
            text, commissioned_key_ids=commissioned
        )
        replay = replay_virtual_us_sticky_keys(
            sequence,
            five_shift_shortcut_disabled=True,
            turn_off_on_two_keys_disabled=True,
        )
        if replay["text"] != text:
            raise StickyKeysReplayError("seeded replay changed requested text")
        total_characters += len(text)
        total_actions += len(sequence)
        total_shift_presses += sequence.count("SHIFT")
    case_bytes = json.dumps(cases, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    return {
        "seed": seed,
        "fixed_cases": list(fixed_cases),
        "random_string_count": string_count,
        "total_string_count": len(cases),
        "maximum_length": maximum_length,
        "total_characters": total_characters,
        "total_actions": total_actions,
        "total_shift_presses": total_shift_presses,
        "failures": 0,
        "cases_sha256": hashlib.sha256(case_bytes).hexdigest(),
    }


def planner_capability_contract(
    *,
    keyboard_target_ids: tuple[str, ...] = (),
    sticky_keys_verified: bool = False,
    phone_target_ids: tuple[str, ...] = (),
    adb_layer_verification: bool = False,
) -> dict[str, Any]:
    """Describe the commissioned prerequisites for sequential shifted input.

    This is a capability audit, not a target map or execution permit.  The
    language model never supplies these target identities or capability facts.
    """

    keyboard_targets = frozenset(keyboard_target_ids)
    phone_targets = frozenset(phone_target_ids)
    missing_base_keys = tuple(sorted(set(US_PRINTABLE_BASE_KEY_IDS) - keyboard_targets))
    missing_modifier_keys = () if "SHIFT" in keyboard_targets else ("SHIFT",)
    keyboard_ready = (
        not missing_base_keys
        and not missing_modifier_keys
        and sticky_keys_verified is True
    )
    required_phone_targets = frozenset({"key_shift", "key_symbols", "key_letters"})
    phone_ready = required_phone_targets <= phone_targets and adb_layer_verification is True
    core: dict[str, Any] = {
        "schema": "rocell.ai_planner_capability_contract.v1",
        "keyboard": {
            "strategy": "STICKY_KEYS_SEQUENTIAL_MODIFIER",
            "simultaneous_chord_supported": False,
            "caps_lock_optimization_enabled": False,
            "required_target_ids": ["SHIFT"],
            "required_base_key_ids": list(US_PRINTABLE_BASE_KEY_IDS),
            "required_base_key_count": len(US_PRINTABLE_BASE_KEY_IDS),
            "missing_base_key_ids": list(missing_base_keys),
            "missing_modifier_key_ids": list(missing_modifier_keys),
            "sticky_keys_commissioning_evidence_required": True,
            "required_configuration": {
                "sticky_keys_enabled": True,
                "one_shot_shift_latch": True,
                "five_shift_shortcut_disabled": True,
                "turn_off_when_two_keys_pressed_disabled": True,
            },
            "verification_source": "HOST_KEYSTROKE_AND_MODIFIER_STATE_LOG",
            "ready": keyboard_ready,
            "blocked_reason": None if keyboard_ready else "keyboard_modifier_uncommissioned",
        },
        "phone": {
            "strategy": "VERIFIED_LAYER_STATE_MACHINE",
            "states": ["KEYBOARD_LOWER", "KEYBOARD_UPPER", "SYMBOLS_1"],
            "required_transition_target_ids": sorted(required_phone_targets),
            "adb_verification_before_every_press": True,
            "ready": phone_ready,
            "blocked_reason": None if phone_ready else "phone_layer_uncommissioned",
        },
        "language_model_may_emit_target_ids": False,
        "coordinates_present": False,
        "hardware_commands_generated": 0,
        "physical_authority": False,
    }
    encoded = json.dumps(
        core, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return {**core, "contract_sha256": hashlib.sha256(encoded).hexdigest()}


def build_planner_capability_audit(
    target_catalog_path: Path, source_commit: str
) -> dict[str, Any]:
    """Audit the current nominal catalog against the frozen capability contract."""

    source = json.loads(target_catalog_path.read_text(encoding="utf-8"))

    def target_ids(section: dict[str, Any]) -> tuple[str, ...]:
        values: list[str] = []
        for row in section["rows"]:
            values.extend(row.get("key_ids", row.get("target_ids", ())))
        values.extend(section["explicit_targets"])
        return tuple(values)

    keyboard_ids = target_ids(source["keyboard"])
    phone_ids = target_ids(source["phone"])
    core: dict[str, Any] = {
        "schema": "rocell.ai_planner_capability_audit.v1",
        "source_commit": source_commit,
        "target_catalog_file": target_catalog_path.as_posix(),
        "target_catalog_file_sha256": hashlib.sha256(
            target_catalog_path.read_bytes()
        ).hexdigest(),
        "contract": planner_capability_contract(
            keyboard_target_ids=keyboard_ids,
            sticky_keys_verified=False,
            phone_target_ids=phone_ids,
            adb_layer_verification=False,
        ),
        "keyboard_target_count": len(keyboard_ids),
        "phone_target_count": len(phone_ids),
        "seeded_replay": run_seeded_sticky_keys_replay(
            seed=190055, string_count=5000, maximum_length=64
        ),
        "hardware_writes": 0,
        "physical_movements": 0,
        "physical_authority": False,
    }
    encoded = json.dumps(
        core, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return {**core, "audit_sha256": hashlib.sha256(encoded).hexdigest()}


def build_keyboard_target_extension_proposal(
    target_catalog_path: Path, geometry_source_path: Path, source_commit: str
) -> dict[str, Any]:
    """Propose missing keyboard targets without installing unqualified geometry."""

    catalog = json.loads(target_catalog_path.read_text(encoding="utf-8"))
    geometry_source = geometry_source_path.read_text(encoding="utf-8")
    if "Presentation-only outer modifiers" not in geometry_source:
        raise ValueError("geometry source is not explicitly presentation-only")
    for target_id, seed in _TARGET_EXTENSION_SEEDS.items():
        if seed["source_literal"] not in geometry_source:
            raise ValueError(f"geometry source no longer contains exact {target_id} seed")

    existing_ids = {
        key_id
        for row in catalog["keyboard"]["rows"]
        for key_id in row["key_ids"]
    } | set(catalog["keyboard"]["explicit_targets"])
    required = ("SHIFT", "BACKSLASH", "GRAVE", "LEFT_BRACKET", "RIGHT_BRACKET")
    if existing_ids.intersection(required):
        raise ValueError("proposal target already exists in active keyboard catalog")

    targets: list[dict[str, Any]] = []
    for target_id in required:
        seed = _TARGET_EXTENSION_SEEDS.get(target_id)
        if seed is None:
            targets.append({
                "target_id": target_id,
                "proposal_status": "BLOCKED_GEOMETRY_SOURCE_INSUFFICIENT",
                "press_point_xy_mm": None,
                "safe_half_extent_mm": None,
                "geometry_source": None,
                "geometry_limitation": (
                    "No repository source defines the Grave key. Pitch extrapolation is rejected: "
                    "one 19.05 mm pitch left of key 1 gives x=2.95 mm, which cannot contain the "
                    "ordinary 7 mm half-width inside the 315 mm device boundary."
                ),
                "camera_visibility": "NOT_TESTABLE_WITHOUT_GEOMETRY_AND_COMMISSIONED_CAMERA",
                "arm_runtime_ik": "NOT_TESTABLE_WITHOUT_GEOMETRY_SHARED_WITH_ARM_RUNTIME",
                "parked_arm_self_occlusion": "NOT_TESTABLE_WITHOUT_GEOMETRY_AND_COMMISSIONED_CAMERA",
            })
            continue
        targets.append({
            "target_id": target_id,
            "proposal_status": "PROVISIONAL_SIMULATION_ONLY_PENDING_SHARED_REVIEW",
            "press_point_xy_mm": seed["proposed_press_point_xy_mm"],
            "safe_half_extent_mm": seed["proposed_safe_half_extent_mm"],
            "press_point_rule": seed["press_point_rule"],
            "presentation_key_center_xy_mm": seed["presentation_center_xy_mm"],
            "presentation_key_width_mm": seed["presentation_width_mm"],
            "geometry_source": {
                "path": geometry_source_path.as_posix(),
                "file_sha256": hashlib.sha256(geometry_source_path.read_bytes()).hexdigest(),
                "source_state": "PRESENTATION_ONLY_NOT_CONTROL_OR_COMMISSIONING_AUTHORITY",
            },
            "geometry_limitation": (
                "The source is a visual presentation model, not a product drawing or measurement. "
                "The proposed region may seed synthetic/shared review only."
            ),
            "camera_visibility": "PENDING_COMMISSIONED_PARKED_CAMERA_CHECK",
            "arm_runtime_ik": "PENDING_ARM_LANE_READ_ONLY_IK_CHECK",
            "parked_arm_self_occlusion": "PENDING_COMMISSIONED_PARKED_ARM_PROJECTION_CHECK",
        })

    blockers = [
        "GRAVE_GEOMETRY_SOURCE_MISSING",
        "FIVE_TARGETS_NOT_INSTALLED_IN_SHARED_CATALOG",
        "COMMISSIONED_CAMERA_VISIBILITY_NOT_PROVEN",
        "PARKED_ARM_NON_OCCLUSION_NOT_PROVEN",
        "ARM_RUNTIME_IK_REACHABILITY_NOT_PROVEN",
        "TARGET_CATALOG_HASH_NOT_REFROZEN",
        "V5_5_IDENTITIES_NOT_AMENDED_TO_80_TARGETS",
        "V5_5_POWER_CHECK_NOT_RERUN",
    ]
    core: dict[str, Any] = {
        "schema": "rocell.ai_keyboard_target_extension_proposal.v1",
        "scope": "SYNTHETIC_SHARED_CATALOG_PROPOSAL_NO_COMMISSIONING_OR_PHYSICAL_AUTHORITY",
        "source_commit": source_commit,
        "active_catalog": {
            "path": target_catalog_path.as_posix(),
            "file_sha256": hashlib.sha256(target_catalog_path.read_bytes()).hexdigest(),
            "keyboard_target_count": len(existing_ids),
            "total_target_count": len(existing_ids) + 29,
            "unchanged": True,
        },
        "targets": targets,
        "shared_catalog_install_authorized": False,
        "compiler_expansion_authorized": False,
        "v5_5": {
            "required_total_target_count_after_admission": 80,
            "render_authorized": False,
            "evaluation_remains_unrendered": True,
            "blockers": blockers,
        },
        "ownership": {
            "ai_lane": "PROPOSAL_SOURCE_BINDING_AND_SYNTHETIC_CORPUS_ADMISSION",
            "arm_lane": "READ_ONLY_IK_REACHABILITY_DECISION",
            "shared_commissioning": "CAMERA_VISIBILITY_AND_PARKED_ARM_OCCLUSION",
        },
        "hardware_writes": 0,
        "physical_movements": 0,
        "physical_authority": False,
    }
    encoded = json.dumps(
        core, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return {**core, "proposal_sha256": hashlib.sha256(encoded).hexdigest()}


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
    if proposal["device"] == "keyboard" and any(
        character in _DESKTOP_SHIFTED_CHARACTERS for character in proposal["text"]
    ):
        return blocked("keyboard_modifier_uncommissioned")
    if proposal["device"] == "phone" and any(
        character in _PHONE_LAYERED_CHARACTERS
        and character not in {".", "\n"}
        for character in proposal["text"]
    ):
        return blocked("phone_layer_uncommissioned")
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-catalog", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target-extension-geometry-source", type=Path)
    args = parser.parse_args()
    if args.target_extension_geometry_source is None:
        result = build_planner_capability_audit(args.target_catalog, args.source_commit)
    else:
        result = build_keyboard_target_extension_proposal(
            args.target_catalog, args.target_extension_geometry_source, args.source_commit
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
