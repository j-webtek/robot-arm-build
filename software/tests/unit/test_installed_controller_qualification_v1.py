"""Offline qualification-gate tests; all physical-shaped evidence is modeled."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import jsonschema
import pytest

from rocell.application.installed_controller_qualification_v1 import (
    EXPECTED_ARM_JOINT_ORDER,
    EXPECTED_T102_FIELDS,
    EXPECTED_T1051_FIELDS,
    EvidenceOrigin,
    InstalledControllerQualificationEvidenceV1,
    ReviewDisposition,
    assess_installed_controller_qualification_v1,
)

import test_zero_write_waveshare_adapter_v1 as preview


WORKSPACE = Path(__file__).resolve().parents[3]
SCHEMAS = WORKSPACE / "software" / "ai" / "schemas"


def _profile():
    envelope = preview._envelope()
    return preview._profile(envelope)


def _evidence(profile, **changes):
    values = dict(
        qualification_id="installed-controller-qualification-1",
        controller_binding_sha256="3" * 64,
        installed_firmware_evidence_sha256="4" * 64,
        qualified_protocol_source_sha256=profile.vendor_source_sha256,
        controller_joint_mapping_evidence_sha256="5" * 64,
        controller_joint_mapping_sha256=profile.controller_joint_mapping_sha256,
        feedback_protocol_evidence_sha256="6" * 64,
        startup_behavior_evidence_sha256="7" * 64,
        configuration_epoch_sha256=profile.configuration_epoch_sha256,
        controller_session_id=profile.controller_session_id,
        captured_monotonic_ns=100,
        valid_until_monotonic_ns=1_000,
        t102_command_fields=EXPECTED_T102_FIELDS,
        t1051_feedback_fields=EXPECTED_T1051_FIELDS,
        arm_joint_order=EXPECTED_ARM_JOINT_ORDER,
        fixed_gripper_field="hand",
        evidence_origin=EvidenceOrigin.PHYSICAL_RETAINED_ORIGINALS,
        review_disposition=ReviewDisposition.INDEPENDENTLY_APPROVED,
    )
    values.update(changes)
    return InstalledControllerQualificationEvidenceV1(**values)


def _validate(name, document):
    schema = json.loads((SCHEMAS / name).read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(document)


def test_missing_evidence_is_explicitly_blocked_without_authority():
    report = assess_installed_controller_qualification_v1(
        _profile(), None, evaluated_monotonic_ns=200).to_dict()
    assert report["status"] == "BLOCKED"
    assert report["blockers"] == ["MISSING_REVIEWED_EVIDENCE"]
    assert report["profile_binding_ready"] is False
    assert report["execution_authorized"] is False
    assert report["transport_authorized"] is False
    assert report["hardware_access"] is report["physical_authority"] is False
    _validate("installed_controller_qualification_report_v1.schema.json", report)


def test_exact_reviewed_evidence_can_only_bind_zero_write_profile():
    profile = _profile()
    evidence = _evidence(profile)
    report = assess_installed_controller_qualification_v1(
        profile, evidence, evaluated_monotonic_ns=200).to_dict()
    assert report["status"] == "READY_FOR_ZERO_WRITE_PROFILE_BINDING"
    assert report["blockers"] == []
    assert report["profile_binding_ready"] is True
    assert report["execution_authorized"] is False
    assert report["transport_authorized"] is False
    assert report["hardware_commands_generated"] == 0
    _validate(
        "installed_controller_qualification_evidence_v1.schema.json",
        evidence.to_dict())
    _validate("installed_controller_qualification_report_v1.schema.json", report)


@pytest.mark.parametrize(("change", "blocker"), [
    ({"evidence_origin": EvidenceOrigin.SYNTHETIC_TEST_ONLY},
     "EVIDENCE_NOT_PHYSICAL_ORIGINAL"),
    ({"review_disposition": ReviewDisposition.UNREVIEWED},
     "INDEPENDENT_REVIEW_INCOMPLETE"),
    ({"valid_until_monotonic_ns": 150}, "EVIDENCE_STALE"),
    ({"controller_session_id": "other-session"},
     "CONTROLLER_SESSION_MISMATCH"),
    ({"configuration_epoch_sha256": "8" * 64},
     "CONFIGURATION_EPOCH_MISMATCH"),
    ({"controller_joint_mapping_sha256": "9" * 64},
     "JOINT_MAPPING_HASH_MISMATCH"),
    ({"qualified_protocol_source_sha256": "a" * 64},
     "PROTOCOL_SOURCE_HASH_MISMATCH"),
    ({"t102_command_fields": ("shoulder", "base", "elbow", "wrist", "roll", "hand")},
     "T102_COMMAND_FIELDS_MISMATCH"),
    ({"t1051_feedback_fields": ("s", "b", "e", "t", "r", "g")},
     "T1051_FEEDBACK_FIELDS_MISMATCH"),
    ({"arm_joint_order": tuple(reversed(EXPECTED_ARM_JOINT_ORDER))},
     "ARM_JOINT_ORDER_MISMATCH"),
    ({"fixed_gripper_field": "gripper"}, "FIXED_GRIPPER_FIELD_MISMATCH"),
])
def test_each_qualification_mismatch_blocks_profile_binding(change, blocker):
    profile = _profile()
    evidence = _evidence(profile, **change)
    report = assess_installed_controller_qualification_v1(
        profile, evidence, evaluated_monotonic_ns=200).to_dict()
    assert blocker in report["blockers"]
    assert report["status"] == "BLOCKED"
    assert report["profile_binding_ready"] is False
    assert report["execution_authorized"] is False


def test_evaluation_before_capture_and_altered_profile_both_fail_closed():
    profile = _profile()
    evidence = _evidence(profile)
    early = assess_installed_controller_qualification_v1(
        profile, evidence, evaluated_monotonic_ns=99)
    assert early.blockers == ("EVALUATION_PREDATES_CAPTURE",)
    altered = replace(profile, controller_session_id="changed-session")
    report = assess_installed_controller_qualification_v1(
        altered, evidence, evaluated_monotonic_ns=200)
    assert "CONTROLLER_SESSION_MISMATCH" in report.blockers
    assert report.encoding_profile_sha256 != profile.profile_sha256


def test_schema_rejects_claimed_execution_authority():
    profile = _profile()
    report = assess_installed_controller_qualification_v1(
        profile, _evidence(profile), evaluated_monotonic_ns=200).to_dict()
    report["execution_authorized"] = True
    with pytest.raises(jsonschema.ValidationError):
        _validate("installed_controller_qualification_report_v1.schema.json", report)
