from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from rocell.application.r97_independent_review_decision_v1 import (
    build_synthetic_r97_review_rehearsal_v1,
)
from rocell.application.r97_owner_ai_review_acceptance_v1 import (
    R97OwnerAIReviewAcceptanceError,
    accept_r97_internal_ai_review_v1,
    parse_r97_owner_ai_review_acceptance_v1,
)


ROOT = Path(__file__).resolve().parents[2]


def decision():
    return build_synthetic_r97_review_rehearsal_v1(
        rehearsal_id="arm-067-owner-ai-review",
        review_started_utc="2026-09-27T14:10:00Z",
        review_completed_utc="2026-09-27T14:11:00Z")[0]


def acceptance():
    return accept_r97_internal_ai_review_v1(
        decision(), acceptance_id="arm-067-owner-ai-acceptance",
        owner_id="project-owner", accepted_utc="2026-09-27T14:12:00Z")


def test_owner_override_removes_human_dependency_without_claiming_independence():
    document = acceptance().to_dict()
    assert document["human_review_required"] is False
    assert document["human_review_claimed"] is False
    assert document["external_independence_claimed"] is False
    assert document["owner_governance_override"] is True
    assert document["ready_for_owner_governed_configuration_epoch_intake"] is True
    for field in ("installation_authorized", "controller_start_authorized",
                  "transport_authorized", "execution_authorized",
                  "hardware_access", "physical_authority"):
        assert document[field] is False
    schema = json.loads((ROOT / "ai/schemas/r97_owner_ai_review_acceptance_v1.schema.json").read_text())
    jsonschema.Draft202012Validator(schema).validate(document)
    assert parse_r97_owner_ai_review_acceptance_v1(document) == acceptance()


def test_retained_acceptance_is_exact_and_hash_bound():
    retained = json.loads((ROOT / "ai/eval/arm067_r97_owner_ai_review_acceptance.json").read_text())
    assert retained == acceptance().to_dict()


def test_acceptance_rejects_promoted_authority_and_hash_tampering():
    promoted = acceptance().to_dict()
    promoted["installation_authorized"] = True
    with pytest.raises(R97OwnerAIReviewAcceptanceError, match="authority differs"):
        parse_r97_owner_ai_review_acceptance_v1(promoted)
    changed = acceptance().to_dict()
    changed["acceptance_sha256"] = "0" * 64
    with pytest.raises(R97OwnerAIReviewAcceptanceError, match="hash differs"):
        parse_r97_owner_ai_review_acceptance_v1(changed)
