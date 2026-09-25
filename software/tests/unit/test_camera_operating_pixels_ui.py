"""Actual JavaScript, fictional v2 reports, GET-only navigation/result reads."""

from copy import deepcopy
import pytest

from test_camera_workspace_ui import EXAMPLES, render
from rocell.application.camera_operating_pixels import SCHEMA, REFERENCE_SCOPE


def example(status="VERIFIED_AT_READ", count=2):
    full = EXAMPLES["example_operation"](complete=True)
    report = full["result"]["steps"][0]["report"]
    report.update(
        schema="rocell.camera_original_operating_assessment.v2",
        captures=[],
        pixel_checks=[],
        pixel_reference_scope=REFERENCE_SCOPE,
    )
    for i in range(count):
        key, attempt = f"operation-{str(i + 1) * 32}", f"attempt-example-{i}"
        report["captures"].append(
            dict(request_key=key, attempt_id=attempt, permit_sha256="a" * 64)
        )
        has_ref = status in {"VERIFIED_AT_READ", "PIXEL_FILE_UNAVAILABLE_OR_CHANGED"}
        report["pixel_checks"].append(
            dict(
                schema=SCHEMA,
                request_key=key,
                attempt_id=attempt,
                status=status,
                reference_scope=REFERENCE_SCOPE,
                result_sha256="a" * 64 if has_ref else None,
                native_frame_sha256="b" * 64 if has_ref else None,
                verified_bytes=16 if status == "VERIFIED_AT_READ" else 0,
                content_verified_at_read=status == "VERIFIED_AT_READ",
                frame_freshness_assessed=False,
                original_stage_record_retained=False,
                physical_authority=False,
            )
        )
    if status == "VERIFIED_AT_READ" and count == 2:
        report["unresolved_checks"].remove("PIXEL_FILES_NOT_VERIFIED")
    return full


@pytest.mark.parametrize(
    "status",
    [
        "VERIFIED_AT_READ",
        "LOGGED_REFERENCE_UNAVAILABLE",
        "REFERENCE_MISMATCH",
        "PIXEL_FILE_UNAVAILABLE_OR_CHANGED",
    ],
)
def test_pixel_outcomes_are_visible_and_never_approve_hardware(status):
    page = render(full=example(status), load=True)
    text = " ".join(page["checklists"])
    assert "Saved-pixel verification" in text
    assert "OPERATING APPROVAL HELD" in text and "image freshness" in text
    assert "Checklist unavailable" not in text
    assert (
        "6 remaining requirements"
        if status == "VERIFIED_AT_READ"
        else "7 remaining requirements"
    ) in text


@pytest.mark.parametrize("count", [0, 1])
def test_partial_pixel_selection_keeps_missing_requirement(count):
    text = " ".join(render(full=example(count=count), load=True)["checklists"])
    assert "7 remaining requirements" in text
    assert "Saved pixel files have not been verified" in text


@pytest.mark.parametrize(
    "fault",
    [
        "authority",
        "missing",
        "duplicate",
        "status",
        "bytes",
        "hash",
        "hold",
        "scope",
        "extra",
    ],
)
def test_inconsistent_pixel_reports_do_not_render_success(fault):
    full = example()
    report = full["result"]["steps"][0]["report"]
    p = report["pixel_checks"][0]
    if fault == "authority":
        p["physical_authority"] = True
    elif fault == "missing":
        p.pop("frame_freshness_assessed")
    elif fault == "duplicate":
        report["pixel_checks"][1] = deepcopy(p)
    elif fault == "status":
        p["status"] = "APPROVED"
    elif fault == "bytes":
        p["verified_bytes"] = 2**60
    elif fault == "hash":
        p["native_frame_sha256"] = "0" * 64
    elif fault == "hold":
        report["unresolved_checks"].remove("FRAME_FRESHNESS_NOT_ASSESSED")
    elif fault == "scope":
        report["pixel_reference_scope"] = "CANONICAL_APPROVAL"
    else:
        p["surprise"] = True
    assert "Checklist unavailable" in " ".join(
        render(full=full, load=True)["checklists"]
    )
