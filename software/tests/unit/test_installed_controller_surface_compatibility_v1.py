"""Offline tests for installed-controller command-surface compatibility."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import jsonschema
import pytest

from rocell.application.installed_controller_passive_evidence_v1 import (
    assemble_installed_controller_passive_evidence_v1,
)
from rocell.application.installed_controller_surface_compatibility_v1 import (
    InstalledControllerSurfaceEvidenceV1,
    SurfaceReviewDisposition,
    assess_installed_controller_surface_compatibility_v1,
)


WORKSPACE = Path(__file__).resolve().parents[3]
APP = b"reviewed-r96-app-bytes"
APP_SHA = hashlib.sha256(APP).hexdigest()
BOOT = "4390cfab5cd74a16fd5048406c1b5adf"
REVIEW_SHA = hashlib.sha256(b"linked-image-review").hexdigest()


def _json_bytes(value):
    return json.dumps(value, sort_keys=True).encode("utf-8")


def _passive():
    journal = [
        {"stage": "RESERVED", "app_sha256": APP_SHA},
        {"stage": "IDENTITY_AND_PREWRITE_VERIFIED"},
        {"stage": "WRITE_ATTEMPT_STARTED"},
        {"stage": "FLASH_VERIFIED", "app_sha256": APP_SHA,
         "protected_regions_unchanged": True},
        {"stage": "ONE_STARTUP_ATTEMPT"},
        {"stage": "STARTUP_RESET_SENT"},
    ]
    return assemble_installed_controller_passive_evidence_v1(
        capture_id="passive-r96-20260926",
        captured_at_utc="2026-09-26T18:00:00Z",
        usb_port="COM7",
        usb_pnp_instance_id=r"USB\VID_10C4&PID_EA60\TEST",
        installed_app_bytes=APP,
        deployment_journal_bytes=(
            "\n".join(json.dumps(row) for row in journal) + "\n").encode(),
        final_export_manifest_bytes=_json_bytes({
            "complete": True,
            "kind": "DIAGNOSTIC_ONLY",
            "physical_authority": "NONE",
        }),
        final_feedback_attachment_bytes=_json_bytes({
            "schema": "rocell.registration_ladder_leg_attempt.v1",
            "boot_id": BOOT,
            "app_sha256": APP_SHA,
            "category": "LEG_VERIFIED",
            "automatic_progression": False,
            "retry_allowed": False,
        }),
        live_capabilities={
            "schema": "rocell.registration_ladder.v1",
            "boot_id": BOOT,
            "maximum_legs": 1,
            "automatic_progression": False,
            "gripper_writes": False,
            "motion_authorized": False,
        },
    )


def _surface(**changes):
    values = dict(
        surface_id="r96-registration-ladder",
        reviewed_app_sha256=APP_SHA,
        linked_image_review_sha256=REVIEW_SHA,
        generic_command_dispatch_present=False,
        t102_command_supported=False,
        t105_feedback_request_supported=False,
        t1051_feedback_response_supported=False,
        runtime_app_hash_attested=False,
        review_disposition=SurfaceReviewDisposition.UNREVIEWED,
    )
    values.update(changes)
    return InstalledControllerSurfaceEvidenceV1(**values)


def _schema(name: str):
    return json.loads((WORKSPACE / "software/ai/schemas" / name).read_text(
        encoding="utf-8"))


def test_r96_finite_diagnostic_surface_is_explicitly_incompatible():
    surface = _surface()
    report = assess_installed_controller_surface_compatibility_v1(
        _passive(), surface)
    assert report.status == "BLOCKED"
    assert report.blockers == (
        "RUNTIME_APP_HASH_NOT_ATTESTED",
        "GENERIC_COMMAND_DISPATCH_ABSENT",
        "T102_COMMAND_UNAVAILABLE",
        "T105_FEEDBACK_REQUEST_UNAVAILABLE",
        "T1051_FEEDBACK_RESPONSE_UNAVAILABLE",
        "INDEPENDENT_REVIEW_INCOMPLETE",
    )
    assert "APP_HASH_MISMATCH" not in report.blockers
    assert report.to_dict()["hardware_commands_generated"] == 0
    jsonschema.Draft202012Validator(_schema(
        "installed_controller_surface_evidence_v1.schema.json"
    )).validate(surface.to_dict())
    jsonschema.Draft202012Validator(_schema(
        "installed_controller_surface_compatibility_report_v1.schema.json"
    )).validate(report.to_dict())


def test_modeled_complete_surface_only_allows_zero_write_binding():
    surface = _surface(
        generic_command_dispatch_present=True,
        t102_command_supported=True,
        t105_feedback_request_supported=True,
        t1051_feedback_response_supported=True,
        runtime_app_hash_attested=True,
        review_disposition=SurfaceReviewDisposition.INDEPENDENTLY_APPROVED,
    )
    report = assess_installed_controller_surface_compatibility_v1(
        _passive(), surface)
    document = report.to_dict()
    assert report.status == "COMPATIBLE_FOR_ZERO_WRITE_BINDING"
    assert report.blockers == ()
    assert document["profile_binding_compatible"] is True
    assert document["execution_authorized"] is False
    assert document["transport_authorized"] is False
    assert document["hardware_access"] is False
    assert document["physical_authority"] is False


@pytest.mark.parametrize(("change", "blocker"), [
    ({"reviewed_app_sha256": "0" * 64}, "APP_HASH_MISMATCH"),
    ({"runtime_app_hash_attested": False}, "RUNTIME_APP_HASH_NOT_ATTESTED"),
    ({"generic_command_dispatch_present": False},
     "GENERIC_COMMAND_DISPATCH_ABSENT"),
    ({"t102_command_supported": False}, "T102_COMMAND_UNAVAILABLE"),
    ({"t105_feedback_request_supported": False},
     "T105_FEEDBACK_REQUEST_UNAVAILABLE"),
    ({"t1051_feedback_response_supported": False},
     "T1051_FEEDBACK_RESPONSE_UNAVAILABLE"),
    ({"review_disposition": SurfaceReviewDisposition.REJECTED},
     "INDEPENDENT_REVIEW_INCOMPLETE"),
])
def test_each_compatibility_requirement_fails_closed(change, blocker):
    complete = dict(
        generic_command_dispatch_present=True,
        t102_command_supported=True,
        t105_feedback_request_supported=True,
        t1051_feedback_response_supported=True,
        runtime_app_hash_attested=True,
        review_disposition=SurfaceReviewDisposition.INDEPENDENTLY_APPROVED,
    )
    complete.update(change)
    report = assess_installed_controller_surface_compatibility_v1(
        _passive(), _surface(**complete))
    assert report.blockers == (blocker,)


def test_schemas_reject_mutation_into_execution_authority():
    report = assess_installed_controller_surface_compatibility_v1(
        _passive(), _surface()).to_dict()
    report["execution_authorized"] = True
    report["hardware_commands_generated"] = 1
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema(
            "installed_controller_surface_compatibility_report_v1.schema.json"
        )).validate(report)
