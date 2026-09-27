from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from rocell.application.native_t102_adapter_review_decision_v1 import (
    ADAPTER_SOURCE_SHA256,
    CANDIDATE_COMMIT,
    EXPECTED_CHECKS,
    MANIFEST_SHA256,
    PACKET_SHA256,
)
from rocell.application.native_t102_owner_ai_review_acceptance_v1 import (
    NativeT102OwnerAIReviewAcceptanceError,
    accept_native_t102_internal_ai_review_v1,
)


ROOT = Path(__file__).resolve().parents[2]


def review(**changes):
    value = {
        "schema": "rocell.internal_ai_technical_review.v1",
        "review_id": "arm054-ai-review-65749a9f-20260927",
        "reviewer_id": "openai-codex-primary-agent",
        "review_kind": "INTERNAL_AI_TECHNICAL_REVIEW",
        "evidence_origin": "SYNTHETIC_TEST_ONLY",
        "review_completed_utc": "2026-09-27T11:52:55Z",
        "reviewed_packet_sha256": PACKET_SHA256,
        "reviewed_manifest_sha256": MANIFEST_SHA256,
        "reviewed_candidate_commit": CANDIDATE_COMMIT,
        "reviewed_adapter_source_sha256": ADAPTER_SOURCE_SHA256,
        "technical_disposition": "PASS_OFFLINE_REVIEW_SCOPE",
        "governance_disposition": "BLOCKED_EXTERNAL_INDEPENDENCE_REQUIRED",
        "reviewer_independence_asserted": False,
        "reviewer_participated_in_implementation_chain": True,
        "qualifies_as_external_independent_review": False,
        "ready_for_read_only_endpoint_qualification_intake": False,
        "endpoint_open_authorized": False,
        "controller_start_authorized": False,
        "execution_authorized": False,
        "hardware_access": False,
        "physical_authority": False,
        "checks": [
            {"check_id": check, "passed": True} for check in EXPECTED_CHECKS
        ],
        "test_runs": [
            {
                "scope": "adapter plus ARM-053 composition and production-boundary tests",
                "result": "35 passed",
                "duration_seconds": 1.54,
            },
            {
                "scope": "review packet, decision intake, exchange CLI, adapter, and composition tests",
                "result": "53 passed",
                "duration_seconds": 1.89,
            },
            {
                "scope": "repository hardware-free CI test selection",
                "result": "354 passed",
                "duration_seconds": 42.62,
            },
        ],
        "open_technical_findings": [],
        "limitations": [
            "No real serial endpoint was opened.",
            "No controller was started and no command was sent to hardware.",
            "The review does not authenticate an external reviewer or establish chain of custody.",
            "The review does not qualify the installed controller, firmware, calibration, or physical motion behavior.",
        ],
    }
    value.update(changes)
    return value


def raw(value=None):
    return json.dumps(
        review() if value is None else value,
        indent=2, ensure_ascii=True,
    ).encode("utf-8") + b"\n"


def accept(value=None):
    return accept_native_t102_internal_ai_review_v1(
        raw(value), acceptance_id="arm059-owner-acceptance-1",
        owner_id="project-owner", accepted_utc="2026-09-27T12:10:00Z",
    )


def test_owner_accepts_exact_ai_review_for_read_only_intake_only():
    result = accept()
    document = result.to_dict()
    assert document["status"] == "OWNER_ACCEPTED_AI_REVIEW_WITH_CAVEAT"
    assert document["ready_for_read_only_endpoint_qualification_intake"] is True
    assert document["human_review_claimed"] is False
    assert document["external_independence_claimed"] is False
    assert document["owner_governance_override"] is True
    for name in (
        "endpoint_open_authorized", "controller_start_authorized",
        "transport_write_authorized", "execution_authorized",
        "hardware_access", "physical_authority",
    ):
        assert document[name] is False
    schema = json.loads((ROOT / "ai/schemas" /
                         "native_t102_owner_ai_review_acceptance_v1.schema.json"
                         ).read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(document)


@pytest.mark.parametrize("field,value", [
    ("reviewed_packet_sha256", "1" * 64),
    ("reviewed_manifest_sha256", "2" * 64),
    ("reviewed_candidate_commit", "3" * 40),
    ("reviewed_adapter_source_sha256", "4" * 64),
    ("technical_disposition", "FAIL"),
    ("governance_disposition", "EXTERNAL_INDEPENDENT"),
    ("qualifies_as_external_independent_review", True),
    ("endpoint_open_authorized", True),
    ("execution_authorized", True),
])
def test_crossed_identity_provenance_or_authority_rejects(field, value):
    changed = review()
    changed[field] = value
    with pytest.raises(NativeT102OwnerAIReviewAcceptanceError, match="differs"):
        accept(changed)


def test_failed_or_reordered_checklist_rejects():
    failed = review()
    failed["checks"][3]["passed"] = False
    with pytest.raises(NativeT102OwnerAIReviewAcceptanceError, match="checklist"):
        accept(failed)
    reordered = review()
    reordered["checks"] = list(reversed(reordered["checks"]))
    with pytest.raises(NativeT102OwnerAIReviewAcceptanceError, match="checklist"):
        accept(reordered)


def test_open_findings_reject():
    changed = review(open_technical_findings=["unresolved"])
    with pytest.raises(NativeT102OwnerAIReviewAcceptanceError, match="findings"):
        accept(changed)


def test_duplicate_json_field_rejects():
    duplicate = raw()[:-2] + b',"schema":"crossed"}\n'
    with pytest.raises(NativeT102OwnerAIReviewAcceptanceError, match="duplicate"):
        accept_native_t102_internal_ai_review_v1(
            duplicate, acceptance_id="arm059-owner-acceptance-1",
            owner_id="project-owner", accepted_utc="2026-09-27T12:10:00Z",
        )


def test_file_and_canonical_content_hashes_bind_format_and_meaning():
    first = accept()
    compact = json.dumps(review(), separators=(",", ":")).encode("utf-8")
    second = accept_native_t102_internal_ai_review_v1(
        compact, acceptance_id="arm059-owner-acceptance-1",
        owner_id="project-owner", accepted_utc="2026-09-27T12:10:00Z",
    )
    assert first.source_review_file_sha256 != second.source_review_file_sha256
    assert first.source_review_content_sha256 == second.source_review_content_sha256
    assert first.acceptance_sha256 != second.acceptance_sha256
