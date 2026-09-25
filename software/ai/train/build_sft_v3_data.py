"""Build balanced intent pairs with template families held out for validation."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import sys


AI_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_DIR))
sys.path.insert(0, str(AI_DIR.parent / "src"))

from rocell_ai import SCHEMA_ID  # noqa: E402
from rocell_ai.adapter import inspect  # noqa: E402
from rocell_ai.contract import validate_proposal  # noqa: E402
from build_sft_data import WORDS, signature  # noqa: E402


SEED = 2112
VERSIONS = ("v0", "v1", "v2", "v3", "v4", "v5", "v6", "v7")
TEMPLATES = {
    "target_device": {
        "device": "keyboard", "reason": "device_ambiguous",
        "train_positive": (
            'The physical keyboard should receive "{text}" as typed input.',
            'Using the keyboard keys, please write "{text}".',
        ),
        "train_negative": 'Put "{text}" into the input that is currently focused.',
        "validation_positive": 'Please have the keyboard enter "{text}" into its text field.',
        "validation_negative": 'Please write "{text}" where the insertion point is.',
    },
    "quoted_device": {
        "device": "phone", "reason": "device_ambiguous",
        "train_positive": (
            'On the phone, enter the literal words "{literal}" in the text box.',
            'Type "{literal}" with the phone ready keyboard.',
        ),
        "train_negative": 'Type the literal words "{literal}" in this box.',
        "validation_positive": 'The phone text box should contain "{literal}"; type it there.',
        "validation_negative": 'Put the quoted phrase "{literal}" into the active box.',
    },
    "text_choice": {
        "device": "keyboard", "reason": "text_ambiguous",
        "train_positive": (
            'For keyboard input, the selected text is "{text}"; enter it.',
            'The choice is "{text}"; write that on the keyboard.',
        ),
        "train_negative": 'On keyboard, the options are "{text}" and "{other}"; choose one.',
        "validation_positive": 'Please type only "{text}" on the keyboard; that is my selection.',
        "validation_negative": 'Write either "{text}" or "{other}" with the keyboard, as you prefer.',
    },
    "device_choice": {
        "device": "keyboard", "reason": "device_ambiguous",
        "train_positive": (
            'For this request, keyboard is the selected device: type "{text}".',
            'Type "{text}" on the keyboard, which I have selected.',
        ),
        "train_negative": 'Use either the keyboard or the phone to type "{text}".',
        "validation_positive": 'I choose the keyboard for "{text}"; type it there.',
        "validation_negative": 'For "{text}", choose between the phone and the keyboard yourself.',
    },
    "referent": {
        "device": "phone", "reason": "text_ambiguous",
        "train_positive": (
            'In the phone editor, enter the exact text "{text}".',
            'Please type "{text}" on the cell phone ready keyboard.',
        ),
        "train_negative": 'In the phone editor, enter the text mentioned earlier in ticket {index}.',
        "validation_positive": 'The selected phone text is "{text}"; type it now.',
        "validation_negative": 'On the phone keyboard, put the prior phrase from item {index}.',
    },
}


def build() -> tuple[list[dict], list[dict], dict]:
    data_dir = AI_DIR / "data"
    prior_manifest_path = data_dir / "synthetic_sft_v1.manifest.json"
    prior_manifest = json.loads(prior_manifest_path.read_text(encoding="utf-8"))
    train: list[dict] = []
    validation: list[dict] = []
    for split in ("train", "validation"):
        raw = (data_dir / f"synthetic_sft_v1_{split}.jsonl").read_bytes()
        if hashlib.sha256(raw).hexdigest() != prior_manifest[f"{split}_sha256"]:
            raise ValueError("v1 data hash mismatch")
        for line in raw.decode("utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                train.append({**row, "id": "v3-" + row["id"],
                              "family": "prior_" + row["family"]})

    def add(destination: list[dict], family: str, request: str, observation: dict, target: dict) -> None:
        case_id = f"v3-synthetic-{len(train) + len(validation):04d}"
        proposal = {"schema": SCHEMA_ID, "request_id": case_id,
                    "observation_ref": observation["ref"], **target}
        validate_proposal(proposal)
        if (inspect(proposal, observation)["status"] == "accepted") != (target["decision"] == "type_text"):
            raise ValueError(f"compiler/label dispute: {case_id}")
        destination.append({"id": case_id, "family": family, "request": request,
                            "observation": observation, "target": target})

    for theme, spec in TEMPLATES.items():
        for i in range(30):
            text = WORDS[i]
            other = WORDS[(i + 7) % len(WORDS)]
            literal = ("keyboard " if i % 2 else "phone ") + text
            values = {"text": text, "other": other, "literal": literal, "index": 7000 + i}
            is_validation = i >= 20
            destination = validation if is_validation else train
            observation = {"ref": f"v3-{theme}-{i}", "fresh": True}
            if spec["device"] == "phone" or theme == "device_choice":
                observation["phone_state"] = "KEYBOARD_LOWER"
            positive = {"decision": "type_text", "device": spec["device"],
                        "text": literal if theme == "quoted_device" else text}
            negative = {"decision": "clarify", "reason": spec["reason"]}
            if is_validation:
                add(destination, f"{theme}_validation_positive",
                    spec["validation_positive"].format(**values),
                    {**observation, "ref": observation["ref"] + "-p"}, positive)
                add(destination, f"{theme}_validation_negative",
                    spec["validation_negative"].format(**values),
                    {**observation, "ref": observation["ref"] + "-n"}, negative)
            else:
                for variant, template in enumerate(spec["train_positive"]):
                    add(destination, f"{theme}_train_positive_{variant}", template.format(**values),
                        {**observation, "ref": observation["ref"] + f"-p{variant}"}, positive)
                add(destination, f"{theme}_train_negative", spec["train_negative"].format(**values),
                    {**observation, "ref": observation["ref"] + "-n"}, negative)

    benchmark_hashes: dict[str, str] = {}
    benchmark_exact: set[str] = set()
    benchmark_signatures: set[str] = set()
    for version in VERSIONS:
        raw = (AI_DIR / "eval" / f"benchmark_{version}.jsonl").read_bytes()
        benchmark_hashes[version] = hashlib.sha256(raw).hexdigest()
        for line in raw.decode("utf-8").splitlines():
            request = json.loads(line)["request"]
            benchmark_exact.add(request.casefold().strip())
            benchmark_signatures.add(signature(request))
    seen: set[str] = set()
    train_signatures = {signature(row["request"]) for row in train}
    for row in train + validation:
        normalized = row["request"].casefold().strip()
        if normalized in seen or normalized in benchmark_exact or signature(row["request"]) in benchmark_signatures:
            raise ValueError(f"benchmark overlap or duplicate synthetic request: {row['id']}")
        seen.add(normalized)
    for row in validation:
        if signature(row["request"]) in train_signatures:
            raise ValueError(f"validation template leaked into training: {row['id']}")
    train_families = {row["family"] for row in train}
    validation_families = {row["family"] for row in validation}
    if train_families & validation_families:
        raise ValueError("validation family leaked into training")

    manifest = {
        "schema": "rocell.ai_synthetic_sft_data.v3", "seed": SEED,
        "source": "agent_authored_balanced_pairs_with_family_heldout_validation",
        "human_reviewed": False,
        "prior_data_manifest_sha256": hashlib.sha256(prior_manifest_path.read_bytes()).hexdigest(),
        "validation_policy": "Five new paraphrase themes; positive and negative validation templates and family IDs are absent from training.",
        "limitations": "Normalized template separation cannot prove semantic independence; all labels are agent-authored and no physical outcomes are included.",
        "benchmark_sha256": benchmark_hashes,
        "counts": {"train": len(train), "validation": len(validation),
                   "families": dict(sorted(Counter(row["family"] for row in train + validation).items()))},
    }
    return train, validation, manifest


def main() -> None:
    train, validation, manifest = build()
    folder = AI_DIR / "data"
    for split, rows in (("train", train), ("validation", validation)):
        raw = ("\n".join(json.dumps(row, sort_keys=True, ensure_ascii=False) for row in rows) + "\n").encode("utf-8")
        (folder / f"synthetic_sft_v3_{split}.jsonl").write_bytes(raw)
        manifest[f"{split}_sha256"] = hashlib.sha256(raw).hexdigest()
    (folder / "synthetic_sft_v3.manifest.json").write_bytes((json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
