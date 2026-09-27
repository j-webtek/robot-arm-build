import hashlib
import json
from pathlib import Path

from eval.audit_mission_decision_structure import run


AI = Path(__file__).resolve().parents[1]


def test_structure_audit_artifact_is_immutable_and_fully_reproducible(tmp_path: Path):
    stored_path = AI / "eval/mission_decision_structure_v1_scorecard.json"
    assert hashlib.sha256(stored_path.read_bytes()).hexdigest() == "fb63f092e6eafbf76123020f688f002c240f33267339ef175b8b5a94e9b29d0b"
    stored = json.loads(stored_path.read_text())
    reproduced_path = tmp_path / "scorecard.json"
    reproduced = run(
        AI / "data/mission_decision_curriculum_v1_validation.jsonl",
        AI / "results/mission_decision_student_v1/validation_epoch_2_scorecard.json",
        reproduced_path,
    )
    assert reproduced == stored
    assert stored["structural_exact"] == stored["total"] == 320
    assert stored["model_exact"] == 185
    assert set(stored["structural_class_accuracy"].values()) == {1.0}
    assert stored["hardware_writes"] == stored["physical_movements"] == 0
    assert stored["qualification_installed"] is False
