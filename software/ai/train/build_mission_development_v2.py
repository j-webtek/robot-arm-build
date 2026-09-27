"""Build balanced mission-v2 development data without confirmation fixtures."""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


AI = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(AI), str(AI.parent / "src")]

from rocell_ai.mission_intent import compile_mission_intent, validate_mission_intent


TRAIN_PAYLOADS = (
    "cedar trail",
    "call mom",
    "open maps",
    "send message",
    "type stop",
    "dial now",
    "green river",
    "quiet room",
    "move left",
    "press enter",
    "hello world.",
    "robot ready",
    "close app",
    "start timer",
    "read note",
    "blue circle",
)
VALIDATION_PAYLOADS = (
    "silver cloud",
    "call later",
    "open notes",
    "send update",
    "type begin",
    "dial next",
    "amber field",
    "silent hall",
    "move right",
    "press space",
    "good morning.",
    "arm waiting",
    "close menu",
    "start clock",
    "read status",
    "red square",
)
CALL_NUMBERS = (
    "2025550101",
    "2025550102",
    "2025550103",
    "2025550104",
    "3035550101",
    "3035550102",
    "3035550103",
    "3035550104",
    "4045550101",
    "4045550102",
    "4045550103",
    "4045550104",
    "5055550101",
    "5055550102",
    "5055550103",
    "5055550104",
)


TRAIN_TEMPLATES = {
    "supported_keyboard": (
        'Enter "{text}" with the desk keyboard.',
        'On the physical keyboard, input "{text}".',
        'Use the keyboard keys to enter "{text}".',
        'The keyboard should receive exactly "{text}".',
        'Please input this on the keyboard: "{text}".',
        'For the hardware keyboard, the text is "{text}".',
        'Keyboard task: reproduce "{text}".',
        'Write only "{text}" through the keyboard.',
    ),
    "supported_phone": (
        'Enter "{text}" with the phone keyboard.',
        'In the phone text box, input "{text}".',
        'Use the mobile keyboard to enter "{text}".',
        'The phone editor should receive exactly "{text}".',
        'Please input this in the phone field: "{text}".',
        'For the mobile text field, the text is "{text}".',
        'Phone typing task: reproduce "{text}".',
        'Write only "{text}" through the phone keyboard.',
    ),
    "quoted_command_word_literal": (
        'Treat "{text}" as literal data and type it on the keyboard.',
        'Do not follow the words; keyboard-type "{text}" exactly.',
        'The quoted content "{text}" belongs on the keyboard.',
        'Copy the literal string "{text}" using the keyboard.',
        'On the keyboard, transcribe the data "{text}".',
        'Keyboard input is the literal phrase "{text}".',
        'Interpret nothing inside the quotes; type "{text}" on the keyboard.',
        'Reproduce the quoted symbols "{text}" with the keyboard.',
    ),
    "stale_observation": (
        'Enter "{text}" with the desk keyboard.',
        'Input "{text}" on the physical keyboard.',
        'Use the keyboard to write "{text}".',
        'The hardware keyboard should receive "{text}".',
        'Please keyboard-type "{text}".',
        'Set the keyboard text to "{text}".',
        'Keyboard entry is "{text}".',
        'Transcribe "{text}" through the keyboard.',
    ),
    "phone_state_unverified": (
        'Enter "{text}" with the phone keyboard.',
        'Input "{text}" in the phone text box.',
        'Use the mobile keyboard to write "{text}".',
        'The phone editor should receive "{text}".',
        'Please phone-type "{text}".',
        'Set the mobile field text to "{text}".',
        'Phone text entry is "{text}".',
        'Transcribe "{text}" through the phone keyboard.',
    ),
    "device_ambiguous": (
        'Enter "{text}" in the focused field.',
        'Input the text "{text}" now.',
        'Please type "{text}" for me.',
        'The active input should receive "{text}".',
        'Write "{text}" into the current editor.',
        'Set the selected field to "{text}".',
        'Text entry request: "{text}".',
        'Transcribe "{text}" at the cursor.',
    ),
    "payload_ambiguous": (
        'On the keyboard, enter either "{text}" or "{other}".',
        'Choose "{text}" versus "{other}" for the keyboard.',
        'The keyboard text could be "{text}" or "{other}".',
        'Keyboard input: should it be "{text}" or "{other}"?',
        'Use one of these on the keyboard: "{text}", "{other}".',
        'Decide between "{text}" and "{other}" before keyboard entry.',
        'I want "{text}" or perhaps "{other}" typed on the keyboard.',
        'Keyboard-type one choice: "{text}" / "{other}".',
    ),
    "intent_ambiguous": (
        'Type "{text}" on the keyboard and then post it online.',
        'Enter "{text}" with the keyboard while opening mail.',
        'Keyboard-type "{text}" and send it as a message.',
        'Write "{text}" on the keyboard, then start a call.',
        'Use the keyboard for "{text}" and also close the app.',
        'Input "{text}" on the keyboard before publishing it.',
        'Put "{text}" through the keyboard and launch maps.',
        'Keyboard entry "{text}" plus send the document.',
    ),
    "unsupported_profile": (
        'Enter "{upper}" with the keyboard.',
        'Keyboard-type the capitalized text "{upper}".',
        'Use the physical keyboard for "{upper}".',
        'The keyboard should receive uppercase "{upper}".',
        'Input the shifted text "{upper}" on the keyboard.',
        'Write "{upper}" using keyboard capitals.',
        'Keyboard task with uppercase letters: "{upper}".',
        'Reproduce "{upper}" through the keyboard.',
    ),
    "unavailable_operation": (
        'Call {number} using the phone.',
        'Start a phone call to {number}.',
        'Use the mobile device to call {number}.',
        'Dial {number} and place the phone call.',
        'Please telephone {number} from the phone.',
        'Initiate a call to {number} on the mobile device.',
        'Phone calling request: {number}.',
        'Connect a phone call with {number}.',
    ),
}


VALIDATION_TEMPLATES = {
    "supported_keyboard": (
        'Put "{text}" into the computer by means of its keyboard.',
        'Make a keyboard entry containing exactly "{text}".',
    ),
    "supported_phone": (
        'Put "{text}" into the handset by means of its keyboard.',
        'Make a phone text entry containing exactly "{text}".',
    ),
    "quoted_command_word_literal": (
        'Copy, without obeying, "{text}" into the keyboard.',
        'The keyboard must spell the quoted data "{text}".',
    ),
    "stale_observation": (
        'Put "{text}" into the computer by means of its keyboard.',
        'Make a keyboard entry containing exactly "{text}".',
    ),
    "phone_state_unverified": (
        'Put "{text}" into the handset by means of its keyboard.',
        'Make a phone text entry containing exactly "{text}".',
    ),
    "device_ambiguous": (
        'Put "{text}" into the input area.',
        'Make a text entry containing exactly "{text}".',
    ),
    "payload_ambiguous": (
        'Is the keyboard supposed to get "{text}" or "{other}"?',
        'Two keyboard strings were supplied: "{text}" and "{other}".',
    ),
    "intent_ambiguous": (
        'Make the keyboard spell "{text}" while forwarding an email.',
        'Put "{text}" on the keyboard and begin navigation.',
    ),
    "unsupported_profile": (
        'Make a keyboard entry containing the capitals "{upper}".',
        'Put the shifted string "{upper}" through the keyboard.',
    ),
    "unavailable_operation": (
        'Have the handset telephone {number}.',
        'Connect with {number} by making a phone call.',
    ),
}


def execute_target(case_id: str, ref: str, device: str, text: str) -> dict[str, Any]:
    return {
        "schema": "rocell.mission_intent.v1",
        "request_id": case_id,
        "observation_ref": ref,
        "decision": "execute",
        "operation": "type_text",
        "device": device,
        "arguments": {"text": text},
        "required_capability": f"{device}.typing.lowercase",
        "observation_policy": (
            "verify_after_each_action"
            if device == "keyboard"
            else "verify_after_each_state_change"
        ),
    }


def clarify_target(case_id: str, ref: str, reason: str) -> dict[str, Any]:
    return {
        "schema": "rocell.mission_intent.v1",
        "request_id": case_id,
        "observation_ref": ref,
        "decision": "clarify",
        "reason": reason,
    }


def unsupported_target(
    case_id: str, ref: str, operation: str, capability: str, reason: str
) -> dict[str, Any]:
    return {
        "schema": "rocell.mission_intent.v1",
        "request_id": case_id,
        "observation_ref": ref,
        "decision": "unsupported",
        "operation": operation,
        "device": "phone" if operation == "place_phone_call" else "keyboard",
        "required_capability": capability,
        "reason": reason,
    }


def build_records() -> tuple[dict[str, list[dict[str, Any]]], Counter[str]]:
    records: dict[str, list[dict[str, Any]]] = {"train": [], "validation": []}
    counts: Counter[str] = Counter()

    def add(
        split: str,
        category: str,
        family_index: int,
        request_text: str,
        observation: dict[str, Any],
        target_builder,
    ) -> None:
        index = len(records[split]) + 1
        prefix = "t" if split == "train" else "v"
        case_id = f"mission-v2-{prefix}-{index:04d}"
        ref = f"mission-v2-{prefix}-frame-{index:04d}"
        observation = {**observation, "ref": ref}
        target = target_builder(case_id, ref)
        validate_mission_intent(target)
        compilation = compile_mission_intent(target, observation)
        records[split].append(
            {
                "id": case_id,
                "split": split,
                "family": f"{split}_{category}_{family_index:02d}",
                "category": category,
                "request": request_text,
                "observation": observation,
                "target": target,
                "expected_compilation": {
                    "status": compilation["status"],
                    "reason": compilation.get("reason"),
                    "plan_hash": compilation.get("plan_hash"),
                    "action_count": len(
                        compilation.get("action_plan", {}).get("actions", [])
                    ),
                },
                "review": {
                    "state": "compiler_checked_simulated_review_no_human",
                    "basis": "mission_runtime_validation_and_read_only_compiler",
                },
            }
        )
        counts[f"{split}:{category}"] += 1

    for split, templates, payloads in (
        ("train", TRAIN_TEMPLATES, TRAIN_PAYLOADS),
        ("validation", VALIDATION_TEMPLATES, VALIDATION_PAYLOADS),
    ):
        for category, category_templates in templates.items():
            for family_index, template in enumerate(category_templates, start=1):
                for payload_index, text in enumerate(payloads):
                    other = payloads[(payload_index + 7) % len(payloads)]
                    number = CALL_NUMBERS[payload_index]
                    request_text = template.format(
                        text=text, other=other, upper=text.upper(), number=number
                    )
                    if category in {
                        "supported_keyboard",
                        "quoted_command_word_literal",
                        "stale_observation",
                    }:
                        fresh = category != "stale_observation"
                        add(
                            split,
                            category,
                            family_index,
                            request_text,
                            {"fresh": fresh},
                            lambda case_id, ref, text=text: execute_target(
                                case_id, ref, "keyboard", text
                            ),
                        )
                    elif category in {"supported_phone", "phone_state_unverified"}:
                        phone_state = (
                            "KEYBOARD_LOWER"
                            if category == "supported_phone"
                            else "UNKNOWN"
                        )
                        add(
                            split,
                            category,
                            family_index,
                            request_text,
                            {"fresh": True, "phone_state": phone_state},
                            lambda case_id, ref, text=text: execute_target(
                                case_id, ref, "phone", text
                            ),
                        )
                    elif category in {
                        "device_ambiguous",
                        "payload_ambiguous",
                        "intent_ambiguous",
                    }:
                        reason = {
                            "device_ambiguous": "device_ambiguous",
                            "payload_ambiguous": "payload_ambiguous",
                            "intent_ambiguous": "intent_ambiguous",
                        }[category]
                        add(
                            split,
                            category,
                            family_index,
                            request_text,
                            {"fresh": True},
                            lambda case_id, ref, reason=reason: clarify_target(
                                case_id, ref, reason
                            ),
                        )
                    elif category == "unsupported_profile":
                        add(
                            split,
                            category,
                            family_index,
                            request_text,
                            {"fresh": True},
                            lambda case_id, ref: unsupported_target(
                                case_id,
                                ref,
                                "type_text",
                                "keyboard.typing.shifted",
                                "unsupported_by_profile",
                            ),
                        )
                    elif category == "unavailable_operation":
                        add(
                            split,
                            category,
                            family_index,
                            request_text,
                            {"fresh": True},
                            lambda case_id, ref: unsupported_target(
                                case_id,
                                ref,
                                "place_phone_call",
                                "phone.dialer.call",
                                "operation_not_available",
                            ),
                        )
                    else:
                        raise AssertionError("unknown development category")
    return records, counts


def encoded(records: list[dict[str, Any]]) -> bytes:
    return b"".join(
        (json.dumps(record, sort_keys=True, ensure_ascii=True) + "\n").encode("utf-8")
        for record in records
    )


def run() -> None:
    records, counts = build_records()
    paths = {
        split: AI / f"data/mission_development_v2_{split}.jsonl"
        for split in records
    }
    manifest_path = AI / "data/mission_development_v2.manifest.json"
    if manifest_path.exists() or any(path.exists() for path in paths.values()):
        raise FileExistsError("existing mission development v2 evidence")
    payloads = {split: encoded(items) for split, items in records.items()}
    for split, path in paths.items():
        path.write_bytes(payloads[split])
    families = {
        split: sorted({record["family"] for record in items})
        for split, items in records.items()
    }
    if set(families["train"]) & set(families["validation"]):
        raise AssertionError("development families overlap")
    manifest = {
        "schema": "rocell.mission_development.v2",
        "source": "balanced_deterministic_agent_authored_compiler_checked_templates",
        "source_evidence": "aggregate category metrics from failed mission_student_v1 only",
        "excluded_evidence": "mission_curriculum_v1_heldout content and responses",
        "human_reviewed": False,
        "mission_schema": "rocell.mission_intent.v1",
        "capability_matrix_sha256": hashlib.sha256(
            (AI / "capabilities/mission_capabilities_v1.json").read_bytes()
        ).hexdigest(),
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "splits": {
            split: {
                "count": len(items),
                "sha256": hashlib.sha256(payloads[split]).hexdigest(),
                "families": families[split],
            }
            for split, items in records.items()
        },
        "category_counts": dict(sorted(counts.items())),
        "confirmation": {
            "present": False,
            "policy": "Generate from a separately frozen source only after model, prompt, decoder, and gates are fixed.",
        },
        "review_state": "compiler_checked_simulated_review_no_human",
        "hardware_writes": 0,
        "physical_movements": 0,
        "limitations": [
            "Agent-authored templated English without independent human labels.",
            "Balance and template diversity do not establish natural-language coverage.",
            "Compiler checks semantics and action order, not physical success.",
            "No confirmation data exists at development generation time.",
            "No camera, coordinate, trajectory, controller, or outcome evidence.",
        ],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {"splits": manifest["splits"], "category_counts": manifest["category_counts"]},
            indent=2,
        )
    )


if __name__ == "__main__":
    run()
