"""Offline tests for the passive installed-controller evidence candidate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import jsonschema
import pytest

from rocell.application.installed_controller_passive_evidence_v1 import (
    BLOCKERS,
    InstalledControllerPassiveEvidenceError,
    assemble_installed_controller_passive_evidence_v1,
)


WORKSPACE = Path(__file__).resolve().parents[3]
APP = b"reviewed-r96-app-bytes"
APP_SHA = hashlib.sha256(APP).hexdigest()
BOOT = "4390cfab5cd74a16fd5048406c1b5adf"
CAPABILITIES = {
    "schema": "rocell.registration_ladder.v1",
    "boot_id": BOOT,
    "maximum_legs": 1,
    "automatic_progression": False,
    "gripper_writes": False,
    "motion_authorized": False,
}


def _json_bytes(value):
    return json.dumps(value, sort_keys=True).encode("utf-8")


def _journal():
    rows = [
        {"stage": "RESERVED", "app_sha256": APP_SHA},
        {"stage": "IDENTITY_AND_PREWRITE_VERIFIED", "mac": "00:00:00:00:00:00"},
        {"stage": "WRITE_ATTEMPT_STARTED"},
        {"stage": "FLASH_VERIFIED", "app_sha256": APP_SHA,
         "protected_regions_unchanged": True},
        {"stage": "ONE_STARTUP_ATTEMPT"},
        {"stage": "STARTUP_RESET_SENT", "application_health_verified": False},
    ]
    return ("\n".join(json.dumps(row) for row in rows) + "\n").encode()


def _manifest():
    return _json_bytes({
        "complete": True,
        "kind": "DIAGNOSTIC_ONLY",
        "physical_authority": "NONE",
    })


def _attachment(**changes):
    value = {
        "schema": "rocell.registration_ladder_leg_attempt.v1",
        "boot_id": BOOT,
        "app_sha256": APP_SHA,
        "category": "LEG_VERIFIED",
        "automatic_progression": False,
        "retry_allowed": False,
    }
    value.update(changes)
    return _json_bytes(value)


def _assemble(**changes):
    values = dict(
        capture_id="passive-r96-20260926",
        captured_at_utc="2026-09-26T18:00:00Z",
        usb_port="COM7",
        usb_pnp_instance_id=r"USB\VID_10C4&PID_EA60\TEST",
        installed_app_bytes=APP,
        deployment_journal_bytes=_journal(),
        final_export_manifest_bytes=_manifest(),
        final_feedback_attachment_bytes=_attachment(),
        live_capabilities=CAPABILITIES,
    )
    values.update(changes)
    return assemble_installed_controller_passive_evidence_v1(**values)


def test_matching_passive_sources_form_unreviewed_zero_authority_candidate():
    document = _assemble().to_dict()
    assert document["controller_session_id"] == BOOT
    assert document["retained_originals"]["installed_app_sha256"] == APP_SHA
    assert document["review_disposition"] == "UNREVIEWED"
    assert document["qualification_evidence_ready"] is False
    assert document["blockers"] == list(BLOCKERS)
    assert document["serial_port_opened"] is False
    assert document["controller_restarted"] is False
    assert document["hardware_writes"] == document["movement_commands"] == 0
    assert document["execution_authorized"] is False
    assert document["transport_authorized"] is False
    schema = json.loads((
        WORKSPACE / "software/ai/schemas/installed_controller_passive_evidence_v1.schema.json"
    ).read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(document)


@pytest.mark.parametrize("capability_change", [
    {"motion_authorized": True},
    {"gripper_writes": True},
    {"automatic_progression": True},
    {"maximum_legs": 2},
    {"boot_id": "0" * 32},
])
def test_live_capability_drift_fails_closed(capability_change):
    capabilities = dict(CAPABILITIES)
    capabilities.update(capability_change)
    with pytest.raises(InstalledControllerPassiveEvidenceError):
        _assemble(live_capabilities=capabilities)


def test_app_hash_mismatch_and_install_stage_drift_fail_closed():
    with pytest.raises(InstalledControllerPassiveEvidenceError):
        _assemble(installed_app_bytes=b"different-app")
    rows = _journal().decode().splitlines()
    rows[2], rows[3] = rows[3], rows[2]
    with pytest.raises(InstalledControllerPassiveEvidenceError):
        _assemble(deployment_journal_bytes=("\n".join(rows) + "\n").encode())


def test_final_feedback_must_bind_same_boot_app_and_bounded_result():
    with pytest.raises(InstalledControllerPassiveEvidenceError):
        _assemble(final_feedback_attachment_bytes=_attachment(boot_id="0" * 32))
    with pytest.raises(InstalledControllerPassiveEvidenceError):
        _assemble(final_feedback_attachment_bytes=_attachment(retry_allowed=True))
    with pytest.raises(InstalledControllerPassiveEvidenceError):
        _assemble(final_feedback_attachment_bytes=_attachment(category="UNCERTAIN"))


def test_candidate_cannot_be_mutated_into_approved_authority_under_schema():
    document = _assemble().to_dict()
    schema = json.loads((
        WORKSPACE / "software/ai/schemas/installed_controller_passive_evidence_v1.schema.json"
    ).read_text(encoding="utf-8"))
    document["review_disposition"] = "INDEPENDENTLY_APPROVED"
    document["qualification_evidence_ready"] = True
    document["execution_authorized"] = True
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(document)
