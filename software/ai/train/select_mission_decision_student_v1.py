"""Apply the frozen safety-first compact decision checkpoint rule."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def selection_key(candidate: dict) -> tuple:
    counts = candidate["scorecard"]["counts"]
    metrics = candidate["scorecard"]["metrics"]
    return (
        counts["wrong_accepted"], counts["invalid_decision"],
        -counts["assembly_exact"], -metrics["macro_class_accuracy"],
        -metrics["minimum_class_accuracy"], -counts["accepted_correct"],
        -metrics["expected_accepted_coverage"], candidate["validation_loss"],
        candidate["epoch"],
    )


def run(results: Path, plan_path: Path, output: Path) -> dict:
    if output.exists():
        raise FileExistsError("selection output already exists")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    training = json.loads((results / "run_manifest.json").read_text(encoding="utf-8"))
    if training["plan_sha256"] != hashlib.sha256(plan_path.read_bytes()).hexdigest():
        raise ValueError("training plan hash mismatch")
    candidates = []
    for entry in training["history"]:
        epoch = entry["epoch"]
        imported = json.loads((results / f"epoch-{epoch}/import_manifest.json").read_text())
        scorecard_path = results / f"validation_epoch_{epoch}_scorecard.json"
        scorecard = json.loads(scorecard_path.read_text())
        if imported["adapter_sha256"] != entry["adapter_sha256"]:
            raise ValueError("adapter import mismatch")
        if imported["digest"] != scorecard["model_digest"]:
            raise ValueError("validation model digest mismatch")
        if scorecard["split"] != "validation":
            raise ValueError("selection scorecard is not validation")
        candidates.append({
            **entry, "model": scorecard["model"], "model_digest": scorecard["model_digest"],
            "scorecard_sha256": hashlib.sha256(scorecard_path.read_bytes()).hexdigest(),
            "scorecard": scorecard,
        })
    selected = min(candidates, key=selection_key)
    result = {
        "schema": "rocell.mission_decision_selection.v1",
        "plan_sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
        "selection_rule": plan["checkpoint_selection"],
        "candidate_keys": {str(item["epoch"]): list(selection_key(item)) for item in candidates},
        "selected_epoch": selected["epoch"],
        "selected_adapter_sha256": selected["adapter_sha256"],
        "selected_model": selected["model"],
        "selected_model_digest": selected["model_digest"],
        "selected_validation_scorecard_sha256": selected["scorecard_sha256"],
        "selected_passed_development_gates": selected["scorecard"]["passed"],
        "confirmation_read": False, "hardware_writes": 0, "physical_movements": 0,
        "qualification_installed": False,
    }
    output.write_bytes((json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.results, args.plan, args.output), sort_keys=True))


if __name__ == "__main__":
    main()
