"""Derive compact decisions and prove exact MissionIntentV1 reassembly."""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


AI = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(AI), str(AI.parent / "src")]

from rocell_ai.mission_decision import assemble_mission_decision, validate_mission_decision
from rocell_ai.mission_intent import canonical_sha256, validate_mission_intent


SOURCE_MANIFEST_SHA256 = "2eb484610cf51a21ee41a10100631bdefe92fa94d79a797cfa195fbb1577ac34"
SOURCE_SPLIT_SHA256 = {
    "train": "ec8739514dfd0dc2f4556694f547f2aa28b489355a15eb6a3cb8772d4cf7fc9e",
    "validation": "fc4b94d49ca7f0e0354f2aa70e186cca6edb5e8148451176eaf0fda37b30ca7b",
}


def decision_from_mission(mission: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    validate_mission_intent(mission)
    decision = mission["decision"]
    if decision == "execute":
        label = f"execute.{mission['device']}"
        target = {
            "schema": "rocell.mission_decision.v1",
            "decision": "execute",
            "device": mission["device"],
        }
    elif decision == "clarify":
        label = f"clarify.{mission['reason']}"
        target = {
            "schema": "rocell.mission_decision.v1",
            "decision": "clarify",
            "reason": mission["reason"],
        }
    elif mission["required_capability"] == "keyboard.typing.shifted":
        label = "unsupported.shifted_keyboard_text"
        target = {
            "schema": "rocell.mission_decision.v1",
            "decision": "unsupported",
            "kind": "shifted_keyboard_text",
        }
    elif mission["required_capability"] == "phone.dialer.call":
        label = "unsupported.phone_call"
        target = {
            "schema": "rocell.mission_decision.v1",
            "decision": "unsupported",
            "kind": "phone_call",
        }
    else:
        raise ValueError("mission cannot map to a compact decision")
    validate_mission_decision(target)
    return label, target


def source_rows(split: str) -> list[dict[str, Any]]:
    path = AI / f"data/mission_development_v2_{split}.jsonl"
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_SPLIT_SHA256[split]:
        raise ValueError("source development split hash mismatch")
    return [json.loads(line) for line in raw.decode("utf-8").splitlines()]


def build_records() -> tuple[dict[str, list[dict[str, Any]]], Counter[str]]:
    manifest = AI / "data/mission_development_v2.manifest.json"
    if hashlib.sha256(manifest.read_bytes()).hexdigest() != SOURCE_MANIFEST_SHA256:
        raise ValueError("source development manifest hash mismatch")
    records: dict[str, list[dict[str, Any]]] = {"train": [], "validation": []}
    counts: Counter[str] = Counter()
    for split in records:
        for source in source_rows(split):
            label, target = decision_from_mission(source["target"])
            assembly = assemble_mission_decision(
                target,
                request_id=source["id"],
                observation_ref=source["observation"]["ref"],
                request=source["request"],
            )
            if assembly["status"] != "assembled":
                raise AssertionError("source target conservatively downgraded")
            if assembly["mission_intent"] != source["target"]:
                raise AssertionError("compact decision does not reproduce source mission")
            records[split].append(
                {
                    "id": source["id"],
                    "split": split,
                    "family": source["family"],
                    "category": source["category"],
                    "class_label": label,
                    "request": source["request"],
                    "observation": source["observation"],
                    "target": target,
                    "expected_mission_sha256": canonical_sha256(source["target"]),
                    "assembly_status": assembly["status"],
                    "review": {
                        "state": "deterministically_derived_compiler_checked_simulated_review_no_human",
                        "basis": "exact_reassembly_to_frozen_mission_development_v2_target",
                    },
                }
            )
            counts[f"{split}:{label}"] += 1
    return records, counts


def encoded(records: list[dict[str, Any]]) -> bytes:
    return b"".join(
        (json.dumps(record, sort_keys=True, ensure_ascii=True) + "\n").encode("utf-8")
        for record in records
    )


def run() -> None:
    records, counts = build_records()
    paths = {
        split: AI / f"data/mission_decision_curriculum_v1_{split}.jsonl"
        for split in records
    }
    manifest_path = AI / "data/mission_decision_curriculum_v1.manifest.json"
    if manifest_path.exists() or any(path.exists() for path in paths.values()):
        raise FileExistsError("existing compact mission decision curriculum")
    payloads = {split: encoded(items) for split, items in records.items()}
    for split, path in paths.items():
        path.write_bytes(payloads[split])
    class_counts = {
        split: Counter(record["class_label"] for record in items)
        for split, items in records.items()
    }
    class_weights = {
        split: {
            label: len(records[split]) / (len(values) * count)
            for label, count in sorted(values.items())
        }
        for split, values in class_counts.items()
    }
    result = {
        "schema": "rocell.mission_decision_curriculum.v1",
        "target_schema": "rocell.mission_decision.v1",
        "source_manifest_sha256": SOURCE_MANIFEST_SHA256,
        "source_split_sha256": SOURCE_SPLIT_SHA256,
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "splits": {
            split: {
                "count": len(items),
                "sha256": hashlib.sha256(payloads[split]).hexdigest(),
                "families": sorted({item["family"] for item in items}),
            }
            for split, items in records.items()
        },
        "class_counts": {
            split: dict(sorted(values.items())) for split, values in class_counts.items()
        },
        "recommended_inverse_frequency_weights": class_weights,
        "exact_reassembly_count": sum(len(items) for items in records.values()),
        "conservative_downgrade_count": 0,
        "confirmation": {"present": False},
        "human_reviewed": False,
        "hardware_writes": 0,
        "physical_movements": 0,
        "limitations": [
            "Labels are deterministically derived from agent-authored templated development data.",
            "Exact source reassembly does not establish natural-language generalization.",
            "Class frequencies differ because multiple mission categories map to execute classes.",
            "No confirmation data, model result, camera, motion, or physical evidence exists.",
        ],
    }
    manifest_path.write_bytes((json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps({"splits": result["splits"], "class_counts": result["class_counts"]}, indent=2))


if __name__ == "__main__":
    run()
