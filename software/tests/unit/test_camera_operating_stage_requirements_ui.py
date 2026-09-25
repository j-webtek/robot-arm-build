"""Actual JS renderer, fictional v3 data, no original store or hardware."""

import pytest

from rocell.application.camera_operating_stage_requirements import (
    project_operating_requirements,
)
from test_camera_operating_pixels_ui import example as pixel_example
from test_camera_workspace_ui import render


def example(*, count=2, failed=False):
    full = pixel_example(count=count)
    report = full["result"]["steps"][0]["report"]
    report["schema"] = "rocell.camera_original_operating_assessment.v3"
    preflight = report["preflight"]
    if failed:
        preflight["checks"][0]["satisfied"] = False
        preflight["failed_checks"] = [preflight["checks"][0]["id"]]
        preflight["status"] = "BLOCKED_METADATA"
    report["stage_requirements"] = project_operating_requirements(
        report["unresolved_checks"], preflight["failed_checks"]
    )
    return full


@pytest.mark.parametrize("count", [0, 1, 2])
@pytest.mark.parametrize("failed", [False, True])
def test_stage_groups_retain_all_holds_without_changing_permissions(count, failed):
    text = " ".join(
        render(full=example(count=count, failed=failed), load=True)["checklists"]
    )
    assert "Checklist unavailable" not in text
    assert "Mode/control stage — original evidence and separate review" in text
    assert "Later camera stages — freshness and installed calibration" in text
    assert "not removed or approved" in text
    assert "OPERATING APPROVAL HELD" in text
    assert (
        "6 remaining requirements" if count == 2 else "7 remaining requirements"
    ) in text
    assert ("metadata checks above also remain unsatisfied" in text) is failed


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "extra",
        "authority",
        "schema",
        "scope",
        "owner",
        "failed",
        "drop",
        "duplicate",
        "row_extra",
        "stage",
        "row_scope",
        "id",
    ],
)
def test_forged_or_incomplete_stage_projection_never_renders_passes(fault):
    full = example()
    report = full["result"]["steps"][0]["report"]
    projection = report["stage_requirements"]
    row = projection["requirements"][0]
    if fault == "missing":
        report.pop("stage_requirements")
    elif fault == "extra":
        projection["surprise"] = True
    elif fault == "authority":
        projection["stage_passed"] = True
    elif fault in ("schema", "scope"):
        projection[fault] = "incorrect"
    elif fault == "owner":
        projection["metadata_check_owner"] = "noncontact_acceptance"
    elif fault == "failed":
        projection["failed_metadata_checks"] = ["unknown"]
    elif fault == "drop":
        projection["requirements"].pop()
    elif fault == "duplicate":
        projection["requirements"][1] = row.copy()
    elif fault == "row_extra":
        row["approved"] = True
    elif fault == "stage":
        row["owner_stages"] = ["reference_frame_calibration"]
    elif fault == "row_scope":
        row["scope"] = "LATER_STAGE"
    else:
        row["id"] = "unknown"
    text = " ".join(render(full=full, load=True)["checklists"])
    assert "Checklist unavailable" in text
    assert "metadata checks satisfied" not in text


def test_v2_history_remains_unmodified_without_retroactive_stage_claims():
    text = " ".join(render(full=pixel_example(), load=True)["checklists"])
    assert "Saved-pixel verification" in text
    assert "Mode/control stage —" not in text
    assert "6 remaining requirements" in text
