from dataclasses import replace
import json
from pathlib import Path

import jsonschema
import pytest

from rocell.application.installed_controller_qualification_v1 import (
    ReviewDisposition,
)
from rocell.application.r97_independent_review_decision_v1 import (
    EXPECTED_CHECKS,
    R97_APP_SHA256,
    R97_REVIEW_MANIFEST_SHA256,
    R97_REVIEW_PACKET_SHA256,
    R97IndependentReviewDecisionError,
    R97IndependentReviewDecisionV1,
    R97ReviewCheck,
    R97ReviewCheckResultV1,
    assess_r97_independent_review_decision_v1,
)


ROOT = Path(__file__).resolve().parents[2]


def _checks(*, failed: R97ReviewCheck | None = None):
    return tuple(
        R97ReviewCheckResultV1(check=item, passed=item is not failed)
        for item in R97ReviewCheck
    )


def _decision(**changes):
    # Synthetic fixture only. It is not external review evidence.
    values = {
        "decision_id": "synthetic-test-decision",
        "reviewer_id": "synthetic-reviewer",
        "reviewer_affiliation": "test-fixture-only",
        "reviewer_attestation_sha256": "a" * 64,
        "review_started_utc": "2026-09-26T12:00:00Z",
        "review_completed_utc": "2026-09-26T12:30:00Z",
        "reviewed_packet_sha256": R97_REVIEW_PACKET_SHA256,
        "reviewed_manifest_sha256": R97_REVIEW_MANIFEST_SHA256,
        "reviewed_app_sha256": R97_APP_SHA256,
        "reviewer_independence_asserted": True,
        "reviewer_was_implementation_author": False,
        "checks": _checks(),
        "findings": (),
        "disposition": ReviewDisposition.INDEPENDENTLY_APPROVED,
    }
    values.update(changes)
    return R97IndependentReviewDecisionV1(**values)


def _schema(name):
    return json.loads((ROOT / "ai/schemas" / name).read_text(encoding="utf-8"))


def test_approved_decision_is_schema_valid_and_ready_for_epoch_intake():
    decision = _decision()
    report = assess_r97_independent_review_decision_v1(decision)
    assert tuple(item.check.value for item in decision.checks) == EXPECTED_CHECKS
    assert report.status == "INDEPENDENT_REVIEW_ACCEPTED"
    assert report.blockers == ()
    assert report.decision_sha256 == decision.decision_sha256
    for document in (decision.to_dict(), report.to_dict()):
        assert document["installation_authorized"] is False
        assert document["controller_start_authorized"] is False
        assert document["execution_authorized"] is False
        assert document["physical_authority"] is False
    jsonschema.Draft202012Validator(_schema(
        "r97_independent_review_decision_v1.schema.json"
    )).validate(decision.to_dict())
    jsonschema.Draft202012Validator(_schema(
        "r97_independent_review_decision_report_v1.schema.json"
    )).validate(report.to_dict())


@pytest.mark.parametrize(
    "field,value,blocker",
    [
        ("reviewed_packet_sha256", "1" * 64, "PACKET_IDENTITY_MISMATCH"),
        ("reviewed_manifest_sha256", "2" * 64, "MANIFEST_IDENTITY_MISMATCH"),
        ("reviewed_app_sha256", "3" * 64, "APP_IDENTITY_MISMATCH"),
        ("reviewer_independence_asserted", False, "INDEPENDENCE_NOT_ASSERTED"),
        ("reviewer_was_implementation_author", True,
         "IMPLEMENTATION_AUTHOR_CONFLICT"),
        ("findings", ("open finding",), "APPROVAL_HAS_OPEN_FINDINGS"),
        ("disposition", ReviewDisposition.REJECTED, "DECISION_NOT_APPROVED"),
    ],
)
def test_material_review_failures_block(field, value, blocker):
    report = assess_r97_independent_review_decision_v1(
        _decision(**{field: value}))
    assert report.status == "BLOCKED"
    assert blocker in report.blockers


def test_failed_check_blocks():
    report = assess_r97_independent_review_decision_v1(_decision(
        checks=_checks(failed=R97ReviewCheck.SINGLE_GROUP_WRITE)))
    assert report.blockers == ("CHECKLIST_INCOMPLETE",)


@pytest.mark.parametrize(
    "checks",
    [(), _checks()[:-1], _checks()[::-1]],
)
def test_checklist_membership_and_order_are_closed(checks):
    with pytest.raises(R97IndependentReviewDecisionError, match="closed checklist"):
        _decision(checks=checks)


def test_unreviewed_is_not_a_decision():
    with pytest.raises(R97IndependentReviewDecisionError, match="approve or reject"):
        _decision(disposition=ReviewDisposition.UNREVIEWED)


@pytest.mark.parametrize(
    "changes,match",
    [
        ({"review_started_utc": "not-utc"}, "whole-second UTC"),
        ({"review_completed_utc": "2026-09-26T11:59:59Z"}, "predate"),
    ],
)
def test_review_times_are_valid_and_ordered(changes, match):
    with pytest.raises(R97IndependentReviewDecisionError, match=match):
        _decision(**changes)


def test_decision_digest_is_deterministic_and_materially_bound():
    first = _decision()
    assert first.decision_sha256 == _decision().decision_sha256
    assert replace(first, reviewer_attestation_sha256="b" * 64).decision_sha256 != (
        first.decision_sha256)


def test_assessment_requires_typed_decision():
    with pytest.raises(TypeError, match="R97IndependentReviewDecisionV1"):
        assess_r97_independent_review_decision_v1({})
