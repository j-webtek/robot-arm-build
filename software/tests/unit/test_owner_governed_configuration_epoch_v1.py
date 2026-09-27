from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path

import jsonschema
import pytest

from rocell.application.controller_configuration_epoch_intake_v1 import (
    ConfigurationEpochComponent,
    EXPECTED_COMPONENT_IDS,
)
from rocell.application.installed_controller_qualification_v1 import (
    EvidenceOrigin,
)
from rocell.application.owner_governed_configuration_epoch_v1 import (
    REQUIRED_COMPONENT_BINDINGS,
    ComponentBindingEvidenceV1,
    ComponentInstallationState,
    OwnerAIReviewDisposition,
    OwnerGovernedConfigurationComponentV1,
    OwnerGovernedConfigurationEpochError,
    assess_owner_governed_configuration_epoch_v1,
    build_owner_governed_configuration_epoch_draft_v1,
    parse_owner_governed_configuration_epoch_draft_v1,
)
from rocell.application.r97_owner_ai_review_acceptance_v1 import (
    parse_r97_owner_ai_review_acceptance_v1,
)


ROOT = Path(__file__).resolve().parents[2]


def digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def acceptance():
    return parse_r97_owner_ai_review_acceptance_v1(json.loads(
        (ROOT / "ai/eval/arm067_r97_owner_ai_review_acceptance.json")
        .read_text(encoding="utf-8")))


def component(component_id: str, *, measured: int = 10, expires: int = 100,
              binding_count: int | None = None,
              origin: EvidenceOrigin = EvidenceOrigin.PHYSICAL_RETAINED_ORIGINALS,
              review: OwnerAIReviewDisposition = (
                  OwnerAIReviewDisposition.OWNER_AI_ACCEPTED)):
    binding_ids = REQUIRED_COMPONENT_BINDINGS[component_id]
    if binding_count is not None:
        binding_ids = binding_ids[:binding_count]
    return OwnerGovernedConfigurationComponentV1(
        component=ConfigurationEpochComponent(component_id),
        installation_state=(
            ComponentInstallationState.CONFIRMED_NOT_INSTALLED
            if component_id == "phone_station"
            else ComponentInstallationState.INSTALLED),
        evidence_bundle_sha256=digest(f"bundle:{component_id}"),
        binding_evidence=tuple(ComponentBindingEvidenceV1(
            binding_id=binding_id,
            evidence_sha256=digest(f"binding:{component_id}:{binding_id}"),
        ) for binding_id in binding_ids),
        owner_ai_review_sha256=digest(f"review:{component_id}"),
        measured_monotonic_ns=measured,
        valid_until_monotonic_ns=expires,
        evidence_origin=origin,
        review_disposition=review,
    )


def test_empty_draft_reports_all_eight_missing_without_authority():
    draft = build_owner_governed_configuration_epoch_draft_v1(
        epoch_id="arm-068-test", owner_acceptance=acceptance())
    report = assess_owner_governed_configuration_epoch_v1(
        draft, evaluated_monotonic_ns=20, owner_acceptance=acceptance())
    document = report.to_dict()
    assert document["status"] == "BLOCKED"
    assert document["configuration_epoch_sha256"] is None
    assert document["blockers"] == ["COMPONENT_MISSING"]
    assert document["missing_component_ids"] == list(EXPECTED_COMPONENT_IDS)
    assert all(item["status"] == "MISSING"
               for item in document["component_assessments"])
    for field in (
        "installation_authorized", "controller_start_authorized",
        "transport_authorized", "execution_authorized", "hardware_access",
        "physical_authority",
    ):
        assert document[field] is False


def test_complete_physical_owner_ai_reviewed_epoch_is_build_proposal_ready():
    draft = build_owner_governed_configuration_epoch_draft_v1(
        epoch_id="arm-068-complete", owner_acceptance=acceptance(),
        components=tuple(component(item) for item in EXPECTED_COMPONENT_IDS))
    report = assess_owner_governed_configuration_epoch_v1(
        draft, evaluated_monotonic_ns=20, owner_acceptance=acceptance())
    assert report.blockers == ()
    assert report.to_dict()["status"] == (
        "READY_FOR_EPOCH_BOUND_BUILD_PROPOSAL")
    assert report.to_dict()["configuration_epoch_sha256"] == draft.draft_sha256
    assert report.to_dict()["ready_component_ids"] == list(
        EXPECTED_COMPONENT_IDS)
    assert report.to_dict()["installation_authorized"] is False


def test_missing_binding_stale_synthetic_and_unreviewed_are_distinct():
    components = tuple(
        component(item, binding_count=(0 if item == "software_build" else None),
                  expires=(15 if item == "camera_support_optics" else 100),
                  origin=(EvidenceOrigin.SYNTHETIC_TEST_ONLY
                          if item == "board_tags_bench"
                          else EvidenceOrigin.PHYSICAL_RETAINED_ORIGINALS),
                  review=(OwnerAIReviewDisposition.UNREVIEWED
                          if item == "arm_controller_tool"
                          else OwnerAIReviewDisposition.OWNER_AI_ACCEPTED))
        for item in EXPECTED_COMPONENT_IDS
    )
    draft = build_owner_governed_configuration_epoch_draft_v1(
        epoch_id="arm-068-blocked", owner_acceptance=acceptance(),
        components=components)
    report = assess_owner_governed_configuration_epoch_v1(
        draft, evaluated_monotonic_ns=20, owner_acceptance=acceptance())
    assert report.blockers == (
        "REQUIRED_BINDING_MISSING", "MEASUREMENT_STALE",
        "COMPONENT_NOT_PHYSICAL_ORIGINAL",
        "COMPONENT_OWNER_AI_REVIEW_INCOMPLETE",
    )
    assert report.to_dict()["blocked_component_ids"] == [
        "software_build", "camera_support_optics", "board_tags_bench",
        "arm_controller_tool",
    ]


def test_owner_acceptance_and_release_identity_fail_closed():
    draft = build_owner_governed_configuration_epoch_draft_v1(
        epoch_id="arm-068-identity", owner_acceptance=acceptance(),
        components=tuple(component(item) for item in EXPECTED_COMPONENT_IDS))
    missing = assess_owner_governed_configuration_epoch_v1(
        draft, evaluated_monotonic_ns=20, owner_acceptance=None)
    assert missing.blockers == ("OWNER_ACCEPTANCE_MISSING",)
    changed = replace(
        draft, owner_acceptance_sha256="0" * 64,
        candidate_app_sha256="1" * 64)
    mismatched = assess_owner_governed_configuration_epoch_v1(
        changed, evaluated_monotonic_ns=20, owner_acceptance=acceptance())
    assert mismatched.blockers == (
        "OWNER_ACCEPTANCE_MISMATCH", "CANDIDATE_APP_MISMATCH")
    assert mismatched.to_dict()["configuration_epoch_sha256"] is None


def test_draft_round_trip_schemas_and_tamper_rejection():
    draft = build_owner_governed_configuration_epoch_draft_v1(
        epoch_id="arm-068-roundtrip", owner_acceptance=acceptance(),
        components=(component("software_build"),))
    document = draft.to_dict()
    schema = json.loads((
        ROOT / "ai/schemas/owner_governed_configuration_epoch_draft_v1.schema.json"
    ).read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(document)
    assert parse_owner_governed_configuration_epoch_draft_v1(document) == draft
    changed = dict(document)
    changed["hardware_access"] = True
    with pytest.raises(OwnerGovernedConfigurationEpochError,
                       match="provenance or authority differs"):
        parse_owner_governed_configuration_epoch_draft_v1(changed)
    changed = dict(document)
    changed["draft_sha256"] = "0" * 64
    with pytest.raises(OwnerGovernedConfigurationEpochError,
                       match="hash differs"):
        parse_owner_governed_configuration_epoch_draft_v1(changed)


def test_retained_arm068_artifacts_match_builder_and_assessment_schema():
    draft_document = json.loads((
        ROOT / "ai/eval/arm068_owner_epoch_draft.json"
    ).read_text(encoding="utf-8"))
    assessment_document = json.loads((
        ROOT / "ai/eval/arm068_owner_epoch_missing_evidence_report.json"
    ).read_text(encoding="utf-8"))
    draft = build_owner_governed_configuration_epoch_draft_v1(
        epoch_id="arm-068-owner-governed-measured-epoch",
        owner_acceptance=acceptance())
    report = assess_owner_governed_configuration_epoch_v1(
        draft, evaluated_monotonic_ns=1, owner_acceptance=acceptance())
    assert draft_document == draft.to_dict()
    assert assessment_document == report.to_dict()
    for file_name, document in (
        ("owner_governed_configuration_epoch_draft_v1.schema.json",
         draft_document),
        ("owner_governed_configuration_epoch_assessment_v1.schema.json",
         assessment_document),
    ):
        schema = json.loads((ROOT / "ai/schemas" / file_name).read_text())
        jsonschema.Draft202012Validator(schema).validate(document)
