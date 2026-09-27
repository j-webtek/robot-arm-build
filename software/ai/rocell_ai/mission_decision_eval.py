"""Compiler-backed scoring for compact mission-decision predictions."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from .mission_decision import assemble_mission_decision, decode_mission_decision
from .mission_intent import canonical_sha256, compile_mission_intent


def evaluate(
    cases_path: Path,
    predictions_path: Path,
    plan: dict[str, Any],
    expected_cases_sha256: str,
    split: str,
) -> dict[str, Any]:
    cases_raw = cases_path.read_bytes()
    predictions_raw = predictions_path.read_bytes()
    cases_sha256 = hashlib.sha256(cases_raw).hexdigest()
    if cases_sha256 != expected_cases_sha256:
        raise ValueError("case hash mismatch")
    cases = [json.loads(line) for line in cases_raw.decode("utf-8").splitlines()]
    predictions = [json.loads(line) for line in predictions_raw.decode("utf-8").splitlines()]
    by_id = {item["id"]: item for item in predictions}
    if len(by_id) != len(predictions) or set(by_id) != {case["id"] for case in cases}:
        raise ValueError("predictions must contain every case ID exactly once")
    identities = {(item.get("model"), item.get("model_digest")) for item in predictions}
    if len(identities) != 1:
        raise ValueError("predictions must bind one model tag and digest")
    model, model_digest = identities.pop()
    if not isinstance(model, str) or not isinstance(model_digest, str):
        raise ValueError("prediction model identity is missing")

    counts: Counter[str] = Counter(total=len(cases))
    classes: dict[str, Counter[str]] = {}
    rows = []
    for case in cases:
        label = case["class_label"]
        class_counts = classes.setdefault(label, Counter(total=0))
        class_counts["total"] += 1
        prediction = by_id[case["id"]]
        actual = None
        actual_assembly = None
        actual_compilation = None
        error = None
        expected_assembly = assemble_mission_decision(
            case["target"],
            request_id=case["id"],
            observation_ref=case["observation"]["ref"],
            request=case["request"],
        )
        expected_mission = expected_assembly["mission_intent"]
        if canonical_sha256(expected_mission) != case["expected_mission_sha256"]:
            raise ValueError("expected compact decision no longer reproduces source mission")
        expected_compilation = compile_mission_intent(expected_mission, case["observation"])
        try:
            actual = decode_mission_decision(prediction.get("response"))
            actual_assembly = assemble_mission_decision(
                actual,
                request_id=case["id"],
                observation_ref=case["observation"]["ref"],
                request=case["request"],
            )
            actual_compilation = compile_mission_intent(
                actual_assembly["mission_intent"], case["observation"]
            )
        except (KeyError, TypeError, ValueError) as caught:
            error = type(caught).__name__ + ": " + str(caught)
        exact_decision = actual == case["target"]
        assembly_exact = (
            actual_assembly is not None
            and canonical_sha256(actual_assembly["mission_intent"])
            == case["expected_mission_sha256"]
        )
        actual_accepted = (
            actual_compilation is not None and actual_compilation["status"] == "accepted"
        )
        expected_accepted = expected_compilation["status"] == "accepted"
        wrong_accepted = actual_accepted and not assembly_exact
        accepted_correct = actual_accepted and expected_accepted and assembly_exact
        values = {
            "valid_decision": actual is not None,
            "invalid_decision": actual is None,
            "exact_decision": exact_decision,
            "assembly_exact": assembly_exact,
            "actual_accepted": actual_accepted,
            "expected_accepted": expected_accepted,
            "accepted_correct": accepted_correct,
            "wrong_accepted": wrong_accepted,
        }
        for name, value in values.items():
            counts[name] += int(value)
            class_counts[name] += int(value)
        rows.append(
            {
                "id": case["id"],
                "class_label": label,
                "expected": case["target"],
                "actual": actual,
                "exact_decision": exact_decision,
                "assembly_status": actual_assembly["status"] if actual_assembly else None,
                "assembly_exact": assembly_exact,
                "actual_compilation_status": actual_compilation["status"] if actual_compilation else None,
                "expected_compilation_status": expected_compilation["status"],
                "wrong_accepted": wrong_accepted,
                "error": error,
            }
        )
    values = dict(sorted(counts.items()))
    class_values = {name: dict(sorted(value.items())) for name, value in sorted(classes.items())}
    class_accuracies = {
        name: value.get("exact_decision", 0) / value["total"]
        for name, value in class_values.items()
    }
    metrics = {
        "exact_decision_fraction": values["exact_decision"] / values["total"],
        "assembly_exact_fraction": values["assembly_exact"] / values["total"],
        "macro_class_accuracy": sum(class_accuracies.values()) / len(class_accuracies),
        "minimum_class_accuracy": min(class_accuracies.values()),
        "expected_accepted_coverage": (
            values["accepted_correct"] / values["expected_accepted"]
            if values["expected_accepted"] else 0.0
        ),
    }
    checks = {
        "zero_invalid_decisions": values["invalid_decision"] == 0,
        "zero_wrong_accepted": values["wrong_accepted"] == 0,
        "minimum_assembly_exact_fraction": metrics["assembly_exact_fraction"] >= plan["minimum_assembly_exact_fraction"],
        "minimum_macro_class_accuracy": metrics["macro_class_accuracy"] >= plan["minimum_macro_class_accuracy"],
        "minimum_class_accuracy": metrics["minimum_class_accuracy"] >= plan["minimum_class_accuracy"],
        "minimum_expected_accepted_coverage": metrics["expected_accepted_coverage"] >= plan["minimum_expected_accepted_coverage"],
    }
    return {
        "schema": "rocell.mission_decision_scorecard.v1",
        "split": split,
        "model": model,
        "model_digest": model_digest,
        "cases_sha256": cases_sha256,
        "predictions_sha256": hashlib.sha256(predictions_raw).hexdigest(),
        "counts": values,
        "metrics": metrics,
        "class_accuracies": class_accuracies,
        "classes": class_values,
        "checks": checks,
        "passed": all(checks.values()),
        "cases": rows,
        "hardware_writes": 0,
        "physical_movements": 0,
        "qualification_installed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--split", required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("scorecard output already exists")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    expected = manifest.get("splits", {}).get(args.split, {}).get("sha256")
    if not isinstance(expected, str):
        raise ValueError("manifest does not define requested split")
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    result = evaluate(args.cases, args.predictions, plan, expected, args.split)
    args.output.write_bytes((json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], **result["metrics"]}, sort_keys=True))


if __name__ == "__main__":
    main()
