import importlib.util
import json
from pathlib import Path

import pytest

from rocell.application.r97_independent_review_decision_v1 import (
    build_synthetic_r97_review_rehearsal_v1,
)


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build_synthetic_configuration_epoch_rehearsal.py"
SPEC = importlib.util.spec_from_file_location("synthetic_epoch_builder", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


def _review_path(tmp_path):
    decision, _ = build_synthetic_r97_review_rehearsal_v1(
        rehearsal_id="arm-036",
        review_started_utc="2026-09-26T13:00:00Z",
        review_completed_utc="2026-09-26T13:01:00Z",
    )
    path = tmp_path / "synthetic-review-decision.json"
    path.write_text(
        json.dumps(decision.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path, decision


def test_builder_ingests_review_and_writes_blocked_epoch(tmp_path):
    review_path, decision = _review_path(tmp_path)
    output = tmp_path / "synthetic-epoch"
    summary = builder.build(
        review_path,
        output,
        rehearsal_id="arm-037",
        measured_monotonic_ns=100,
        valid_until_monotonic_ns=300,
        evaluated_monotonic_ns=200,
    )
    intake = json.loads((
        output / "synthetic-configuration-epoch-intake.json"
    ).read_text(encoding="utf-8"))
    report = json.loads((
        output / "synthetic-configuration-epoch-report.json"
    ).read_text(encoding="utf-8"))
    assert summary["status"] == "SYNTHETIC_EPOCH_REHEARSAL_ACCEPTED"
    assert summary["review_decision_sha256"] == decision.decision_sha256
    assert summary["configuration_epoch_sha256"] == (
        intake["configuration_epoch_sha256"])
    assert report["status"] == "BLOCKED"
    assert report["blockers"] == [
        "FIRMWARE_REVIEW_DECISION_BLOCKED",
        "COMPONENT_NOT_PHYSICAL_ORIGINAL",
    ]
    assert all(
        component["evidence_origin"] == "SYNTHETIC_TEST_ONLY"
        for component in intake["components"]
    )
    for document in (summary, report):
        assert document["epoch_bound_build_proposal_ready"] is False
        assert document["installation_authorized"] is False
        assert document["controller_start_authorized"] is False
        assert document["execution_authorized"] is False
        assert document["physical_authority"] is False


def test_builder_refuses_overwrite_or_tampered_review(tmp_path):
    review_path, _ = _review_path(tmp_path)
    output = tmp_path / "synthetic-epoch"
    kwargs = {
        "rehearsal_id": "arm-037",
        "measured_monotonic_ns": 100,
        "valid_until_monotonic_ns": 300,
        "evaluated_monotonic_ns": 200,
    }
    builder.build(review_path, output, **kwargs)
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        builder.build(review_path, output, **kwargs)
    tampered = json.loads(review_path.read_text(encoding="utf-8"))
    tampered["reviewer_id"] = "tampered"
    tampered_path = tmp_path / "tampered-review.json"
    tampered_path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(ValueError, match="hash"):
        builder.build(tampered_path, tmp_path / "other-output", **kwargs)
