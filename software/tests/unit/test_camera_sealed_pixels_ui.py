"""Actual JavaScript with fictional original/legacy projections; no device I/O."""

import pytest

from rocell.application.camera_operating_stage_requirements import (
    project_operating_requirements,
)
from test_camera_operating_pixels_ui import example
from test_camera_workspace_ui import render


def sealed_example(*, mixed=False, changed=False):
    full = example(
        "PIXEL_FILE_UNAVAILABLE_OR_CHANGED" if changed else "VERIFIED_AT_READ"
    )
    report = full["result"]["steps"][0]["report"]
    report.update(
        schema="rocell.camera_original_operating_assessment.v4",
        pixel_reference_scope="PER_CAPTURE_ORIGINAL_OR_LEGACY_REFERENCE",
    )
    for index, pixel in enumerate(report["pixel_checks"]):
        if mixed and index == 1:
            continue
        pixel.update(
            schema="rocell.camera_operating_pixel_check.v2",
            result_sha256=None,
            capture_checksum_sha256="d" * 64,
            reference_scope="M1_SEALED_CAPTURE_CHECKSUM",
        )
        report["captures"][index]["capture_checksum_sha256"] = "d" * 64
    if mixed and "PIXEL_FILES_NOT_VERIFIED" not in report["unresolved_checks"]:
        # Use the original obligation order rather than inventing an appended
        # hold that would fail the UI's independent closed projection contract.
        report["unresolved_checks"] = example("REFERENCE_MISMATCH")["result"]["steps"][
            0
        ]["report"]["unresolved_checks"]
    report["stage_requirements"] = project_operating_requirements(
        report["unresolved_checks"], report["preflight"]["failed_checks"]
    )
    return full


@pytest.mark.parametrize(
    "mixed,changed", [(False, False), (True, False), (False, True)]
)
def test_original_origin_is_visible_but_stage_approval_stays_held(mixed, changed):
    page = render(full=sealed_example(mixed=mixed, changed=changed), load=True)
    text = " ".join(page["checklists"])
    assert "Checklist unavailable" not in text
    assert "Original receipt-bound checksum" in text
    assert (
        "OPERATING APPROVAL HELD" in text
        and "Legacy references are not promoted" in text
    )
    if mixed:
        assert "Launch-only reference; not an original checksum record" in text
        assert "7 remaining requirements" in text


@pytest.mark.parametrize(
    "fault",
    ["hash", "binding", "schema", "log", "scope", "authority", "missing", "mixed-hold"],
)
def test_inconsistent_original_projection_never_renders_success(fault):
    full = sealed_example(mixed=fault == "mixed-hold")
    report = full["result"]["steps"][0]["report"]
    pixel = report["pixel_checks"][0]
    if fault == "hash":
        pixel["capture_checksum_sha256"] = "0" * 64
    elif fault == "binding":
        report["captures"][0]["capture_checksum_sha256"] = "f" * 64
    elif fault == "schema":
        report["schema"] = "rocell.camera_original_operating_assessment.v3"
    elif fault == "log":
        pixel["result_sha256"] = "f" * 64
    elif fault == "scope":
        pixel["reference_scope"] = "CANONICAL_STAGE_PASS"
    elif fault == "authority":
        pixel["original_stage_record_retained"] = True
    elif fault == "missing":
        pixel.pop("capture_checksum_sha256")
    else:
        report["unresolved_checks"].remove("PIXEL_FILES_NOT_VERIFIED")
    assert "Checklist unavailable" in " ".join(
        render(full=full, load=True)["checklists"]
    )
