from __future__ import annotations

import csv
from pathlib import Path

import pytest

from rocell.application.hardware_intake import (
    HARDWARE_INTAKE_SCHEMA,
    HardwareIntakeError,
    assess_hardware_intake,
)


WORKSPACE = Path(__file__).resolve().parents[3]
TEMPLATE = WORKSPACE / "hardware/static_overhead_camera/hardware_intake_template.csv"


def test_controlled_template_is_complete_but_not_review_ready() -> None:
    report = assess_hardware_intake(WORKSPACE, TEMPLATE)
    assert report.record_count == 55
    assert len(report.incomplete_record_ids) == 55
    assert report.review_ready_record_ids == ()
    assert report.ready_for_human_review is False
    assert report.stage("receipt").ready_for_human_review is False
    assert len(report.stage("receipt").record_ids) == 19
    assert report.to_dict()["schema"] == HARDWARE_INTAKE_SCHEMA
    assert report.to_dict()["authority"]["physical_release_effect"] == "NONE"


def _copy_workspace_fixture(tmp_path: Path) -> tuple[Path, Path, list[dict[str, str]]]:
    workspace = tmp_path / "workspace"
    template = workspace / "hardware/static_overhead_camera/hardware_intake_template.csv"
    template.parent.mkdir(parents=True)
    template.write_bytes(TEMPLATE.read_bytes())
    with template.open("r", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    return workspace, template, rows


def _write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=tuple(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_completed_copy_hashes_every_observation_evidence(tmp_path: Path) -> None:
    workspace, template, rows = _copy_workspace_fixture(tmp_path)
    evidence = workspace / "evidence/receipt.txt"
    evidence.parent.mkdir()
    evidence.write_text("observed physical intake evidence", encoding="utf-8")
    for row in rows:
        row["observed_value"] = "observed"
        row["instrument_or_method"] = "operator measurement"
        row["evidence_path"] = "evidence/receipt.txt"
        row["status"] = "PASS"
    completed = workspace / "completed.csv"
    _write_rows(completed, rows)

    report = assess_hardware_intake(
        workspace, completed, template_path=template
    )
    assert report.ready_for_human_review is True
    assert len(report.review_ready_record_ids) == 55
    assert len(report.evidence_bindings) == 55
    assert report.hold_record_ids == ()
    assert all(stage.ready_for_human_review for stage in report.stage_assessments)


def test_changed_controlled_question_is_rejected(tmp_path: Path) -> None:
    workspace, template, rows = _copy_workspace_fixture(tmp_path)
    rows[0]["candidate_or_requirement"] = "silently relaxed"
    changed = workspace / "changed.csv"
    _write_rows(changed, rows)

    with pytest.raises(HardwareIntakeError, match="controlled question"):
        assess_hardware_intake(workspace, changed, template_path=template)


def test_pass_without_evidence_is_rejected(tmp_path: Path) -> None:
    workspace, template, rows = _copy_workspace_fixture(tmp_path)
    rows[0]["observed_value"] = "observed"
    rows[0]["instrument_or_method"] = "measurement"
    rows[0]["status"] = "PASS"
    changed = workspace / "missing-evidence.csv"
    _write_rows(changed, rows)

    with pytest.raises(HardwareIntakeError, match="requires evidence_path"):
        assess_hardware_intake(workspace, changed, template_path=template)


def test_evidence_escape_is_rejected(tmp_path: Path) -> None:
    workspace, template, rows = _copy_workspace_fixture(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    rows[0]["observed_value"] = "observed"
    rows[0]["instrument_or_method"] = "measurement"
    rows[0]["evidence_path"] = "../outside.txt"
    rows[0]["status"] = "PASS"
    changed = workspace / "escape.csv"
    _write_rows(changed, rows)

    with pytest.raises(HardwareIntakeError, match="outside the workspace"):
        assess_hardware_intake(workspace, changed, template_path=template)


def test_intake_copy_itself_must_remain_inside_workspace(tmp_path: Path) -> None:
    workspace, template, rows = _copy_workspace_fixture(tmp_path)
    outside = tmp_path / "outside.csv"
    _write_rows(outside, rows)

    with pytest.raises(HardwareIntakeError, match="outside the workspace"):
        assess_hardware_intake(workspace, outside, template_path=template)
