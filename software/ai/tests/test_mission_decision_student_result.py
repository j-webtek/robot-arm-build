import hashlib
import json
import sys
from pathlib import Path


AI = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(AI), str(AI.parent / "src")]
RESULT = AI / "results/mission_decision_student_v1"

from rocell_ai.mission_decision_eval import evaluate


def test_compact_validation_recounts_and_failed_selection_is_preserved():
    plan = json.loads((AI / "train/mission_decision_student_v1_plan.json").read_text())
    manifest = json.loads((AI / "data/mission_decision_curriculum_v1.manifest.json").read_text())
    cases = AI / "data/mission_decision_curriculum_v1_validation.jsonl"
    expected = manifest["splits"]["validation"]["sha256"]
    expected_hashes = {
        "run_manifest.json": "16400daa0d31beafff253d6413fe8e6451b7628db5a481262b662e42d94c53c9",
        "epoch-1/import_manifest.json": "447166036d69719e3356c9f895ebc4a887f6124a807b3686031c00afcafc21cb",
        "epoch-2/import_manifest.json": "23870cabb6d9ce56c5f330ed7c6e2662dc2402493b484d04837c6b1c191b0d2f",
        "validation_epoch_1_predictions.jsonl": "cd44a9c8d30b52a08b2b1586e050e2b806a534154a5959b48c4c18a2121b8ca4",
        "validation_epoch_1_scorecard.json": "1aa4bd1d7e250710d602167e7095772a67016c3240f216f21936075fbca76469",
        "validation_epoch_2_predictions.jsonl": "5a1aafbb15ea35ab0fde36c1c135e99ef87288e23f47dc253377306798823b5a",
        "validation_epoch_2_scorecard.json": "dba226ee11e03661f2f1ddae05aeb8967d441ff9c0cd45f8f93996d52d8a2ae4",
        "selection.json": "c24945d00b78eb0c44fb4dc75de7c6f20188db7ddc49ba05cd9ed05abcb55c72",
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
        assert stored["passed"] is False
        assert stored["counts"]["invalid_decision"] == 0
        assert stored["counts"]["wrong_accepted"] == 0
    epoch_two = json.loads((RESULT / "validation_epoch_2_scorecard.json").read_text())
    assert epoch_two["counts"]["assembly_exact"] == 185
    assert epoch_two["counts"]["accepted_correct"] == 62
    assert epoch_two["class_accuracies"]["clarify.device_ambiguous"] == 0
    assert epoch_two["class_accuracies"]["unsupported.phone_call"] == 0
    selection = json.loads((RESULT / "selection.json").read_text())
    assert selection["selected_epoch"] == 2
    assert selection["selected_passed_development_gates"] is False
    assert selection["confirmation_read"] is False
    assert selection["hardware_writes"] == selection["physical_movements"] == 0
    assert selection["qualification_installed"] is False
    assert not list(RESULT.glob("*confirmation*"))
