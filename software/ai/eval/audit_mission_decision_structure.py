"""Audit structural separability against a committed model scorecard."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path


AI = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(AI), str(AI.parent / "src")]

from rocell_ai.mission_decision_structure import structural_decision


def run(cases_path: Path, model_scorecard_path: Path, output: Path) -> dict:
    if output.exists():
        raise FileExistsError("audit output already exists")
    cases_raw = cases_path.read_bytes()
    model_raw = model_scorecard_path.read_bytes()
    cases = [json.loads(line) for line in cases_raw.decode("utf-8").splitlines()]
    model = json.loads(model_raw)
    if model["cases_sha256"] != hashlib.sha256(cases_raw).hexdigest():
        raise ValueError("model scorecard and cases differ")
    model_rows = {row["id"]: row for row in model["cases"]}
    if set(model_rows) != {case["id"] for case in cases}:
        raise ValueError("model scorecard case IDs differ")
    class_counts: dict[str, Counter[str]] = {}
    confusion: Counter[str] = Counter()
    exact = 0
    model_exact = 0
    rows = []
    for case in cases:
        predicted = structural_decision(case["request"])
        matched = predicted == case["target"]
        model_matched = bool(model_rows[case["id"]]["exact_decision"])
        exact += int(matched)
        model_exact += int(model_matched)
        stats = class_counts.setdefault(case["class_label"], Counter(total=0, exact=0))
        stats["total"] += 1
        stats["exact"] += int(matched)
        actual = model_rows[case["id"]]["actual"] or {}
        actual_label = ".".join(
            str(value) for value in (
                actual.get("decision", "invalid"),
                actual.get("device") or actual.get("reason") or actual.get("kind") or "invalid",
            )
        )
        confusion[f"{case['class_label']} -> {actual_label}"] += 1
        rows.append({
            "id": case["id"], "class_label": case["class_label"],
            "structural_decision": predicted, "structural_exact": matched,
            "model_exact": model_matched,
        })
    result = {
        "schema": "rocell.mission_decision_structure_audit.v1",
        "cases_sha256": hashlib.sha256(cases_raw).hexdigest(),
        "model_scorecard_sha256": hashlib.sha256(model_raw).hexdigest(),
        "total": len(cases),
        "structural_exact": exact,
        "structural_exact_fraction": exact / len(cases),
        "model_exact": model_exact,
        "model_exact_fraction": model_exact / len(cases),
        "structural_class_accuracy": {
            label: values["exact"] / values["total"]
            for label, values in sorted(class_counts.items())
        },
        "model_confusion": dict(sorted(confusion.items())),
        "interpretation": "Current templated validation is structurally separable and cannot justify another generative fit. Preserve deterministic safety checks and build a frozen residual paraphrase set that is not solved by this baseline before training another model.",
        "rows": rows,
        "hardware_writes": 0,
        "physical_movements": 0,
        "qualification_installed": False,
        "limitations": [
            "Development audit over the existing agent-authored templated validation only.",
            "Perfect structural separation here does not establish natural-language generalization.",
            "This diagnostic is not installed in runtime and has no execution authority.",
        ],
    }
    output.write_bytes((json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--model-scorecard", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.cases, args.model_scorecard, args.output)
    print(json.dumps({key: result[key] for key in ("total", "structural_exact", "structural_exact_fraction", "model_exact", "model_exact_fraction")}, sort_keys=True))


if __name__ == "__main__":
    main()
