"""Build contrast-paired synthetic examples for device and text ambiguity."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import sys


AI_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_DIR))
sys.path.insert(0, str(AI_DIR.parent / "src"))

from rocell_ai import SCHEMA_ID  # noqa: E402
from rocell_ai.adapter import inspect  # noqa: E402
from rocell_ai.contract import validate_proposal  # noqa: E402
from build_sft_data import signature, WORDS  # noqa: E402


SEED = 2111
VERSIONS = ("v0", "v1", "v2", "v3", "v4", "v5", "v6")


def build() -> tuple[list[dict], list[dict], dict]:
    rng = random.Random(SEED)
    data_dir = AI_DIR / "data"
    prior_manifest_path = data_dir / "synthetic_sft_v1.manifest.json"
    prior_manifest = json.loads(prior_manifest_path.read_text(encoding="utf-8"))
    records: list[dict] = []
    for split in ("train", "validation"):
        raw = (data_dir / f"synthetic_sft_v1_{split}.jsonl").read_bytes()
        if hashlib.sha256(raw).hexdigest() != prior_manifest[f"{split}_sha256"]:
            raise ValueError("v1 data hash mismatch")
        for line in raw.decode("utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                records.append({**row, "id": "v2-" + row["id"],
                                "family": "v1_" + row["family"]})

    def add(family: str, request: str, observation: dict, target: dict) -> None:
        case_id = f"v2-synthetic-{len(records):04d}"
        proposal = {"schema": SCHEMA_ID, "request_id": case_id,
                    "observation_ref": observation["ref"], **target}
        validate_proposal(proposal)
        accepted = inspect(proposal, observation)["status"] == "accepted"
        if accepted != (target["decision"] == "type_text"):
            raise ValueError(f"compiler/label dispute: {case_id}")
        records.append({"id": case_id, "family": family, "request": request,
                        "observation": observation, "target": target})

    device_missing = (
        'I need "{text}" typed into the focused input area.',
        'Please place "{text}" in the visible text field.',
        'Enter "{text}" where the cursor currently sits.',
    )
    device_present = (
        'I need "{text}" typed into the focused keyboard input area.',
        'Please place "{text}" in the visible keyboard text field.',
        'Enter "{text}" on the keyboard where the cursor currently sits.',
    )
    word_missing = (
        'Type the literal word "{text}" into this field.',
        'Please write "{text}" in the active input.',
        'Enter the exact text "{text}" here.',
    )
    word_present = (
        'Type the literal word "{text}" into the phone text field.',
        'Please write "{text}" in the active phone input.',
        'Enter the exact text "{text}" on the phone here.',
    )
    choice_missing = (
        'For the keyboard, type "{left}" or "{right}"; either is fine.',
        'Keyboard entry can be "{left}" or "{right}"; pick one.',
        'Write one of "{left}" and "{right}" on the keyboard.',
    )
    choice_present = (
        'For the keyboard, type "{left}" only.',
        'Keyboard entry is "{left}"; that is the selected text.',
        'Write "{left}" on the keyboard as selected.',
    )
    target_missing = (
        'Please type "{text}" on the keyboard or the phone.',
        'Either device may receive "{text}": keyboard or phone.',
        'Write "{text}" using whichever of the keyboard and phone you choose.',
    )
    target_present = (
        'Please type "{text}" on the physical keyboard.',
        'The keyboard should receive "{text}".',
        'Write "{text}" using the keyboard device.',
    )
    referent_missing = (
        'On the phone keyboard, enter the earlier word from request {index}.',
        'Please put that prior phrase on the phone for task {index}.',
        'The phone keyboard should type the previous text from item {index}.',
    )
    referent_present = (
        'On the phone keyboard, enter "{text}" now.',
        'Please put "{text}" on the phone for task {index}.',
        'The phone keyboard should type "{text}" from item {index}.',
    )

    for i in range(25):
        word = WORDS[i]
        other = WORDS[(i + 7) % len(WORDS)]
        variant = i % 3
        add("contrast_device_missing", device_missing[variant].format(text=word),
            {"ref": f"v2-dm-{i}", "fresh": True},
            {"decision": "clarify", "reason": "device_ambiguous"})
        add("contrast_device_present", device_present[variant].format(text=word),
            {"ref": f"v2-dp-{i}", "fresh": True},
            {"decision": "type_text", "device": "keyboard", "text": word})

        literal = ("keyboard " if i % 2 else "phone ") + word
        add("contrast_quoted_device_missing", word_missing[variant].format(text=literal),
            {"ref": f"v2-qm-{i}", "fresh": True},
            {"decision": "clarify", "reason": "device_ambiguous"})
        add("contrast_quoted_device_present", word_present[variant].format(text=literal),
            {"ref": f"v2-qp-{i}", "fresh": True, "phone_state": "KEYBOARD_LOWER"},
            {"decision": "type_text", "device": "phone", "text": literal})

        add("contrast_text_choice_missing", choice_missing[variant].format(left=word, right=other),
            {"ref": f"v2-cm-{i}", "fresh": True},
            {"decision": "clarify", "reason": "text_ambiguous"})
        add("contrast_text_choice_present", choice_present[variant].format(left=word, right=other),
            {"ref": f"v2-cp-{i}", "fresh": True},
            {"decision": "type_text", "device": "keyboard", "text": word})

        add("contrast_target_choice_missing", target_missing[variant].format(text=word),
            {"ref": f"v2-tm-{i}", "fresh": True, "phone_state": "KEYBOARD_LOWER"},
            {"decision": "clarify", "reason": "device_ambiguous"})
        add("contrast_target_choice_present", target_present[variant].format(text=word),
            {"ref": f"v2-tp-{i}", "fresh": True},
            {"decision": "type_text", "device": "keyboard", "text": word})

        add("contrast_referent_missing", referent_missing[variant].format(index=6000 + i),
            {"ref": f"v2-rm-{i}", "fresh": True, "phone_state": "KEYBOARD_LOWER"},
            {"decision": "clarify", "reason": "text_ambiguous"})
        add("contrast_referent_present", referent_present[variant].format(text=word, index=6000 + i),
            {"ref": f"v2-rp-{i}", "fresh": True, "phone_state": "KEYBOARD_LOWER"},
            {"decision": "type_text", "device": "phone", "text": word})

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
    for row in records:
        normalized = row["request"].casefold().strip()
        if normalized in seen or normalized in benchmark_exact or signature(row["request"]) in benchmark_signatures:
            raise ValueError(f"benchmark overlap or duplicate synthetic request: {row['id']}")
        seen.add(normalized)
    rng.shuffle(records)
    validation_ids = {row["id"] for row in records[:80]}
    train = [row for row in records if row["id"] not in validation_ids]
    validation = [row for row in records if row["id"] in validation_ids]
    manifest = {
        "schema": "rocell.ai_synthetic_sft_data.v2", "seed": SEED,
        "source": "agent_authored_contrast_pairs_compiler_checked", "human_reviewed": False,
        "prior_data_manifest_sha256": hashlib.sha256(prior_manifest_path.read_bytes()).hexdigest(),
        "limitations": "Exact and normalized signature overlap checks cannot prove semantic independence; validation shares request families with training.",
        "benchmark_sha256": benchmark_hashes,
        "counts": {"train": len(train), "validation": len(validation),
                   "families": dict(sorted(Counter(row["family"] for row in records).items()))},
    }
    return train, validation, manifest


def main() -> None:
    train, validation, manifest = build()
    folder = AI_DIR / "data"
    for split, rows in (("train", train), ("validation", validation)):
        raw = ("\n".join(json.dumps(row, sort_keys=True, ensure_ascii=False) for row in rows) + "\n").encode("utf-8")
        (folder / f"synthetic_sft_v2_{split}.jsonl").write_bytes(raw)
        manifest[f"{split}_sha256"] = hashlib.sha256(raw).hexdigest()
    (folder / "synthetic_sft_v2.manifest.json").write_bytes((json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
