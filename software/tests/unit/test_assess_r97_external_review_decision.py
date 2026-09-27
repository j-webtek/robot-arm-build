from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import jsonschema
import pytest

from rocell.application.installed_controller_qualification_v1 import ReviewDisposition
from rocell.application.r97_independent_review_decision_v1 import (
    R97IndependentReviewDecisionError,
    R97IndependentReviewDecisionV1,
    R97ReviewCheck,
    R97ReviewCheckResultV1,
    R97ReviewEvidenceOrigin,
)


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import assess_r97_external_review_decision as intake  # noqa: E402


def decision(*, disposition=ReviewDisposition.INDEPENDENTLY_APPROVED,
             findings=()):
    return R97IndependentReviewDecisionV1(
        decision_id="external-review-001",
        reviewer_id="reviewer-001",
        reviewer_affiliation="independent-lab",
        reviewer_attestation_sha256="a" * 64,
        review_started_utc="2026-09-27T14:00:00Z",
        review_completed_utc="2026-09-27T14:05:00Z",
        reviewed_packet_sha256="987cbe86d98440734d8336c704f1ecd89692675a9cb1620cb674e4132957b416",
        reviewed_manifest_sha256="e7c67071d0485b016cf44e0158fddb92edc0373e1e73532a3b1847f976d5117e",
        reviewed_app_sha256="7d2e47d40141e95b611fcf37ca38d495fcf3da4dc3051f128bbae95e10840d1d",
        evidence_origin=R97ReviewEvidenceOrigin.EXTERNAL_INDEPENDENT,
        reviewer_independence_asserted=True,
        reviewer_was_implementation_author=False,
        checks=tuple(R97ReviewCheckResultV1(item, True)
                     for item in R97ReviewCheck),
        findings=tuple(findings),
        disposition=disposition,
    )


def write(path, value):
    raw = (json.dumps(value.to_dict(), indent=2) + "\n").encode()
    path.write_bytes(raw)
    return raw


def test_accepts_exact_external_decision_but_grants_no_physical_authority(tmp_path):
    source = tmp_path / "decision.json"
    raw = write(source, decision())
    output = tmp_path / "assessment"
    summary = intake.assess(
        source, output, received_utc="2026-09-27T14:06:00Z")
    retained = json.loads((output / "intake-summary.json").read_text())
    schema = json.loads((ROOT / "ai/schemas/r97_external_review_decision_intake_v1.schema.json").read_text())
    jsonschema.Draft202012Validator(schema).validate(retained)
    assert summary["status"] == "INDEPENDENT_REVIEW_ACCEPTED"
    assert summary["input_document_sha256"] == hashlib.sha256(raw).hexdigest()
    assert summary["ready_for_configuration_epoch_intake"] is True
    for field in ("installation_authorized", "controller_start_authorized",
                  "transport_authorized", "execution_authorized",
                  "hardware_access", "physical_authority"):
        assert summary[field] is False
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        intake.assess(source, output, received_utc="2026-09-27T14:06:00Z")


def test_rejected_decision_is_retained_as_blocked(tmp_path):
    source = tmp_path / "decision.json"
    write(source, decision(
        disposition=ReviewDisposition.REJECTED,
        findings=("independent reviewer rejected candidate",)))
    summary = intake.assess(
        source, tmp_path / "assessment",
        received_utc="2026-09-27T14:06:00Z")
    assert summary["status"] == "BLOCKED"
    assert summary["ready_for_configuration_epoch_intake"] is False


def test_rejects_duplicate_fields_oversize_bad_time_and_symlink(tmp_path):
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"schema":"a","schema":"b"}', encoding="utf-8")
    with pytest.raises(R97IndependentReviewDecisionError, match="duplicate"):
        intake.assess(duplicate, tmp_path / "duplicate-out",
                      received_utc="2026-09-27T14:06:00Z")
    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b"x" * (intake.MAX_DECISION_BYTES + 1))
    with pytest.raises(R97IndependentReviewDecisionError, match="size"):
        intake.assess(oversized, tmp_path / "oversized-out",
                      received_utc="2026-09-27T14:06:00Z")
    source = tmp_path / "decision.json"
    write(source, decision())
    with pytest.raises(R97IndependentReviewDecisionError, match="whole-second"):
        intake.assess(source, tmp_path / "bad-time", received_utc="now")
    linked = tmp_path / "linked.json"
    try:
        linked.symlink_to(source)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    with pytest.raises(R97IndependentReviewDecisionError, match="non-symlink"):
        intake.assess(linked, tmp_path / "linked-out",
                      received_utc="2026-09-27T14:06:00Z")
