import importlib.util
import json
from pathlib import Path

import pytest

from rocell.application.r97_independent_review_decision_v1 import (
    parse_r97_independent_review_decision_v1,
)


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build_r97_synthetic_review_rehearsal.py"
SPEC = importlib.util.spec_from_file_location("synthetic_review_builder", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


def test_builder_writes_explicitly_synthetic_non_authorizing_artifacts(tmp_path):
    output = tmp_path / "synthetic-review"
    summary = builder.build(
        output,
        rehearsal_id="arm-036",
        review_started_utc="2026-09-26T13:00:00Z",
        review_completed_utc="2026-09-26T13:01:00Z",
    )
    decision = json.loads((
        output / "r97-synthetic-review-decision.json").read_text(encoding="utf-8"))
    report = json.loads((
        output / "r97-synthetic-review-report.json").read_text(encoding="utf-8"))
    assert decision["evidence_origin"] == "SYNTHETIC_TEST_ONLY"
    assert report["status"] == "SYNTHETIC_REHEARSAL_ACCEPTED"
    assert report["blockers"] == ["SYNTHETIC_EVIDENCE_NOT_INDEPENDENT"]
    assert summary["decision_sha256"] == decision["decision_sha256"]
    assert parse_r97_independent_review_decision_v1(
        decision).decision_sha256 == summary["decision_sha256"]
    assert summary["synthetic_rehearsal_ready"] is True
    for document in (summary, report):
        assert document["ready_for_epoch_intake"] is False
        assert document["installation_authorized"] is False
        assert document["controller_start_authorized"] is False
        assert document["execution_authorized"] is False
        assert document["physical_authority"] is False


def test_builder_refuses_to_overwrite_existing_evidence(tmp_path):
    output = tmp_path / "synthetic-review"
    kwargs = {
        "rehearsal_id": "arm-036",
        "review_started_utc": "2026-09-26T13:00:00Z",
        "review_completed_utc": "2026-09-26T13:01:00Z",
    }
    builder.build(output, **kwargs)
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        builder.build(output, **kwargs)
