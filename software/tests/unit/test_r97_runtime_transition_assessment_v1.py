from __future__ import annotations

import hashlib
import json
from pathlib import Path

import jsonschema
import pytest

from rocell.application.r97_runtime_transition_assessment_v1 import (
    ARM064_RECEIPT_SHA256,
    R97RuntimeTransitionAssessmentError,
    assess_r97_runtime_transition_v1,
)


ROOT = Path(__file__).resolve().parents[2]
RECEIPT = ROOT / "ai/eval/arm064_active_feedback_qualification_20260927.json"


def test_retained_arm065_assessment_is_closed_and_blocked():
    retained = ROOT / "ai/eval/arm065_r97_runtime_transition_assessment.json"
    document = json.loads(retained.read_text(encoding="utf-8"))
    schema = json.loads((ROOT / "ai/schemas/r97_runtime_transition_assessment_v1.schema.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(document)
    rebuilt = assess_r97_runtime_transition_v1(RECEIPT.read_bytes()).to_dict()
    assert document == rebuilt
    assert document["status"] == "BLOCKED"
    assert document["installation_intake_ready"] is False
    assert document["blockers"] == [
        "INSTALLED_RUNTIME_NOT_ATTESTED_AS_R97",
        "ACTIVE_FEEDBACK_SURFACE_REJECTED",
        "R97_INDEPENDENT_REVIEW_DECISION_MISSING",
        "MEASURED_CONFIGURATION_EPOCH_MISSING",
        "R97_CONFIGURATION_EPOCH_NULL",
    ]


def test_assessment_binds_exact_arm064_receipt_and_zero_authority():
    report = assess_r97_runtime_transition_v1(RECEIPT.read_bytes()).to_dict()
    assert report["arm064_receipt_sha256"] == ARM064_RECEIPT_SHA256
    for field in ("installation_authorized", "controller_start_authorized",
                  "transport_authorized", "execution_authorized",
                  "hardware_access", "physical_authority"):
        assert report[field] is False


def test_tampered_arm064_receipt_fails_closed():
    tampered = RECEIPT.read_bytes().replace(
        b"ACTIVE_FEEDBACK_FAILED_TERMINAL", b"ACTIVE_FEEDBACK_FAILED_TAMPERED")
    assert hashlib.sha256(tampered).hexdigest() != ARM064_RECEIPT_SHA256
    with pytest.raises(R97RuntimeTransitionAssessmentError, match="digest differs"):
        assess_r97_runtime_transition_v1(tampered)
