import hashlib
import json
import sys
from pathlib import Path


AI = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(AI), str(AI.parent / "src")]
RESULT = AI / "results/mission_student_v2"

from rocell_ai.mission_student_v2_eval import evaluate


def test_v2_validation_results_recount_and_selection_is_safe_first():
    plan = json.loads((AI / "train/mission_student_v2_plan.json").read_text())
    manifest = json.loads((AI / "data/mission_development_v2.manifest.json").read_text())
    cases = AI / "data/mission_development_v2_validation.jsonl"
    expected = manifest["splits"]["validation"]["sha256"]
    expected_hashes = {
        "validation_epoch_1_predictions.jsonl": "4e2f742b2f1dcb263228d4d7316dba6c28bba4ac8843b838638c4b34e9de2559",
        "validation_epoch_2_predictions.jsonl": "4e66b3fafddd5f8bf5615c7bf5e0bf8ebabcc7ae6360009ce6d1d5bca8b259dc",
        "validation_epoch_1_scorecard.json": "7b30f2f5323c936052ed671202bc4dd642451473f64ec1e4fcf10af37e1dc635",
        "validation_epoch_2_scorecard.json": "a369d2fe826570b113c450fbec5ec95135883af555a5f044244e33786d76a813",
        "selection.json": "2d949ee0296b41f75a0d93a5f81dcc534effa85c45f324c3eef5dd0a62b249ca",
    }
    for name, digest in expected_hashes.items():
        assert hashlib.sha256((RESULT / name).read_bytes()).hexdigest() == digest
    for epoch in (1, 2):
        stored = json.loads((RESULT / f"validation_epoch_{epoch}_scorecard.json").read_text())
        assert evaluate(
            cases,
            RESULT / f"validation_epoch_{epoch}_predictions.jsonl",
            plan,
            expected,
            "validation",
        ) == stored
        assert not stored["passed"]
        assert stored["counts"]["invalid"] == 0
    selection = json.loads((RESULT / "selection.json").read_text())
    assert selection["selected_epoch"] == 1
    assert selection["candidate_keys"]["1"][0] == 10
    assert selection["candidate_keys"]["2"][0] == 22
    assert selection["selected_passed_development_gates"] is False
    assert selection["confirmation_read"] is False
    assert selection["hardware_writes"] == selection["physical_movements"] == 0
    assert selection["qualification_installed"] is False
    assert not list(RESULT.glob("*confirmation*"))
