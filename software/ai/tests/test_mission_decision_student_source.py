from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

from rocell_ai.mission_decision import assemble_mission_decision
from rocell_ai.mission_decision_eval import evaluate
from rocell_ai.mission_decision_model import PROMPT_SHA256, render_user
from rocell_ai.mission_decision_ollama import build_payload
from rocell_ai.mission_intent import canonical_sha256
from train.select_mission_decision_student_v1 import selection_key
from train.train_mission_decision_student_v1 import sampling_weights


AI = Path(__file__).resolve().parents[1]
ROOT = AI.parents[1]
PLAN_PATH = AI / "train/mission_decision_student_v1_plan.json"


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_plan_freezes_sources_prompt_data_and_no_confirmation() -> None:
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    assert plan["prompt_sha256"] == PROMPT_SHA256
    assert plan["confirmation_policy"]["present_at_freeze"] is False
    assert plan["qualification_installed"] is False
    for name, digest in plan["file_sha256"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest


def test_prompt_surface_contains_only_request_and_compact_schema() -> None:
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    row = {"request": 'Type "one" on keyboard', "id": "secret", "observation": {"ref": "secret"}}
    rendered = json.loads(render_user(row))
    assert rendered == {"request": row["request"]}
    schema = json.loads((AI / plan["decision_schema_path"]).read_text(encoding="utf-8"))
    payload = build_payload("local", row, schema, plan)
    assert payload["format"] == schema
    assert payload["options"] == {"temperature": 0, "seed": 2910, "num_predict": 96, "num_ctx": 2048}


def test_inverse_frequency_weights_equalize_expected_class_mass() -> None:
    manifest = json.loads((AI / "data/mission_decision_curriculum_v1.manifest.json").read_text())
    rows = _rows(AI / "data/mission_decision_curriculum_v1_train.jsonl")
    weights = sampling_weights(rows, manifest["recommended_inverse_frequency_weights"]["train"])
    mass = defaultdict(float)
    for row, weight in zip(rows, weights):
        mass[row["class_label"]] += weight
    assert len(mass) == 7
    assert max(mass.values()) - min(mass.values()) < 1e-9


def test_perfect_predictions_pass_compiler_backed_gates(tmp_path: Path) -> None:
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    cases_path = AI / "data/mission_decision_curriculum_v1_validation.jsonl"
    cases = _rows(cases_path)
    predictions = tmp_path / "predictions.jsonl"
    digest = "a" * 64
    predictions.write_bytes(b"".join(
        (json.dumps({"id": case["id"], "response": json.dumps(case["target"]), "model": "perfect", "model_digest": digest}, sort_keys=True) + "\n").encode()
        for case in cases
    ))
    result = evaluate(cases_path, predictions, plan, hashlib.sha256(cases_path.read_bytes()).hexdigest(), "validation")
    assert result["passed"] is True
    assert result["counts"]["wrong_accepted"] == 0
    assert result["metrics"]["assembly_exact_fraction"] == 1.0
    assert result["metrics"]["minimum_class_accuracy"] == 1.0


def test_evaluator_rejects_semantically_wrong_accepted_prediction(tmp_path: Path) -> None:
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    source = next(
        row for row in _rows(AI / "data/mission_decision_curriculum_v1_validation.jsonl")
        if row["class_label"] == "execute.keyboard"
    )
    expected = {"schema": "rocell.mission_decision.v1", "decision": "clarify", "reason": "device_ambiguous"}
    expected_mission = assemble_mission_decision(
        expected, request_id=source["id"], observation_ref=source["observation"]["ref"], request=source["request"]
    )["mission_intent"]
    case = {**source, "class_label": "clarify.device_ambiguous", "target": expected, "expected_mission_sha256": canonical_sha256(expected_mission)}
    cases_path = tmp_path / "cases.jsonl"
    cases_path.write_bytes((json.dumps(case, sort_keys=True) + "\n").encode())
    predictions = tmp_path / "predictions.jsonl"
    predictions.write_bytes((json.dumps({"id": case["id"], "response": json.dumps(source["target"]), "model": "unsafe", "model_digest": "b" * 64}, sort_keys=True) + "\n").encode())
    result = evaluate(cases_path, predictions, plan, hashlib.sha256(cases_path.read_bytes()).hexdigest(), "synthetic")
    assert result["counts"]["wrong_accepted"] == 1
    assert result["passed"] is False


def test_selector_prioritizes_safety_before_accuracy_and_loss() -> None:
    def candidate(wrong: int, invalid: int, exact: int, loss: float) -> dict:
        return {
            "epoch": 1, "validation_loss": loss,
            "scorecard": {
                "counts": {"wrong_accepted": wrong, "invalid_decision": invalid, "assembly_exact": exact, "accepted_correct": exact},
                "metrics": {"macro_class_accuracy": exact / 100, "minimum_class_accuracy": exact / 100, "expected_accepted_coverage": exact / 100},
            },
        }
    safe = candidate(0, 0, 80, 2.0)
    accurate_but_unsafe = candidate(1, 0, 100, 0.1)
    assert selection_key(safe) < selection_key(accurate_but_unsafe)
