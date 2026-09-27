import hashlib
import json
import sys
from pathlib import Path


AI = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(AI), str(AI.parent / "src")]

from rocell_ai.mission_student_eval import evaluate


RESULT = AI / "results/mission_student_v1"


def test_frozen_training_and_import_lineage():
    plan_path = AI / "train/mission_student_v1_plan.json"
    plan = json.loads(plan_path.read_text())
    run = json.loads((RESULT / "run_manifest.json").read_text())
    imported = json.loads((RESULT / "epoch-3/import_manifest.json").read_text())
    assert run["plan_sha256"] == hashlib.sha256(plan_path.read_bytes()).hexdigest()
    assert run["heldout_read"] is False
    assert run["model_fits"] == 1
    assert run["selected_epoch"] == 3
    assert run["optimizer_updates"] == 39
    assert run["selected_adapter_sha256"] == "bb0afa4fcb729c7ca475f1e7ee1d61017f675aa2acc941d3e86f917928db04f1"
    assert imported["adapter_sha256"] == run["selected_adapter_sha256"]
    assert imported["base_digest"] == plan["base_ollama_digest"]
    assert imported["digest"] == "4340d7f6191e01a1ea4071a31785e01cbe2744eb01037cb43b6e1056b4b78a78"
    assert run["hardware_writes"] == run["physical_movements"] == 0


def test_heldout_scorecard_recounts_exactly():
    cases = AI / "data/mission_curriculum_v1_heldout.jsonl"
    predictions = RESULT / "heldout_predictions.jsonl"
    scorecard_path = RESULT / "heldout_scorecard.json"
    plan = json.loads((AI / "train/mission_student_v1_plan.json").read_text())
    stored = json.loads(scorecard_path.read_text())
    assert hashlib.sha256(predictions.read_bytes()).hexdigest() == "5609c52e628fa310cfda8ffca14cc1699a4ccf0ebb1122526b400d80488faacc"
    assert hashlib.sha256(scorecard_path.read_bytes()).hexdigest() == "0fd68713c36b6638091c2a313998bda88856def085e9334e00fb4c8f40977b75"
    assert evaluate(cases, predictions, plan) == stored
    assert stored["counts"] == {
        "accepted_correct": 7,
        "actual_accepted": 7,
        "blocked_expected_accepted": 16,
        "changed_literal": 0,
        "exact": 23,
        "expected_accepted": 23,
        "invalid": 6,
        "total": 80,
        "valid": 74,
        "wrong_accepted": 0,
    }
    assert stored["checks"] == {
        "minimum_exact_fraction": False,
        "minimum_expected_accepted_coverage": False,
        "zero_changed_literal": True,
        "zero_invalid": False,
        "zero_wrong_accepted": True,
    }
    assert stored["passed"] is False
    assert stored["hardware_writes"] == stored["physical_movements"] == 0
    assert stored["qualification_installed"] is False
