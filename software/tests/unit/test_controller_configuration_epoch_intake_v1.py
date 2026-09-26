from dataclasses import replace
import json
from pathlib import Path

import jsonschema
import pytest

from rocell.application.controller_configuration_epoch_intake_v1 import (
    EXPECTED_COMPONENT_IDS,
    R97_APP_SHA256,
    R97_JOINT_MAPPING_SOURCE_SHA256,
    R97_PROTOCOL_SOURCE_SHA256,
    R97_REVIEW_PACKET_SHA256,
    ConfigurationEpochComponent,
    ControllerConfigurationEpochIntakeError,
    ControllerConfigurationEpochIntakeV1,
    MeasuredConfigurationComponentV1,
    assess_controller_configuration_epoch_intake_v1,
)
from rocell.application.installed_controller_qualification_v1 import (
    EvidenceOrigin,
    ReviewDisposition,
)


ROOT = Path(__file__).resolve().parents[2]


def _components(
    *,
    origin=EvidenceOrigin.PHYSICAL_RETAINED_ORIGINALS,
    disposition=ReviewDisposition.INDEPENDENTLY_APPROVED,
    measured=100,
    valid_until=300,
):
    return tuple(
        MeasuredConfigurationComponentV1(
            component=ConfigurationEpochComponent(component),
            evidence_sha256=f"{index + 1:x}" * 64,
            independent_review_sha256=f"{index + 8:x}" * 64,
            measured_monotonic_ns=measured + index,
            valid_until_monotonic_ns=valid_until + index,
            evidence_origin=origin,
            review_disposition=disposition,
        )
        for index, component in enumerate(EXPECTED_COMPONENT_IDS)
    )


def _intake(**changes):
    values = {
        "epoch_id": "cell-a.epoch-1",
        "predecessor_configuration_epoch_sha256": None,
        "r97_review_packet_sha256": R97_REVIEW_PACKET_SHA256,
        "firmware_independent_review_sha256": "d" * 64,
        "firmware_review_disposition": ReviewDisposition.INDEPENDENTLY_APPROVED,
        "candidate_app_sha256": R97_APP_SHA256,
        "protocol_source_sha256": R97_PROTOCOL_SOURCE_SHA256,
        "joint_mapping_source_sha256": R97_JOINT_MAPPING_SOURCE_SHA256,
        "components": _components(),
    }
    values.update(changes)
    return ControllerConfigurationEpochIntakeV1(**values)


def _schema(name):
    return json.loads((ROOT / "ai/schemas" / name).read_text(encoding="utf-8"))


def test_complete_intake_is_ready_only_for_epoch_bound_build_proposal():
    intake = _intake()
    report = assess_controller_configuration_epoch_intake_v1(
        intake, evaluated_monotonic_ns=200)
    assert report.status == "READY_FOR_EPOCH_BOUND_BUILD_PROPOSAL"
    assert report.blockers == ()
    assert report.configuration_epoch_sha256 == intake.configuration_epoch_sha256
    document = report.to_dict()
    assert document["epoch_bound_build_proposal_ready"] is True
    assert document["installation_authorized"] is False
    assert document["controller_start_authorized"] is False
    assert document["execution_authorized"] is False
    assert document["physical_authority"] is False
    jsonschema.Draft202012Validator(_schema(
        "controller_configuration_epoch_intake_v1.schema.json"
    )).validate(intake.to_dict())
    jsonschema.Draft202012Validator(_schema(
        "controller_configuration_epoch_intake_report_v1.schema.json"
    )).validate(document)


def test_epoch_digest_is_deterministic_and_changes_with_evidence():
    first = _intake()
    assert first.configuration_epoch_sha256 == _intake().configuration_epoch_sha256
    components = list(first.components)
    components[0] = replace(components[0], evidence_sha256="e" * 64)
    assert replace(first, components=tuple(components)).configuration_epoch_sha256 != (
        first.configuration_epoch_sha256)
    assert replace(
        first, predecessor_configuration_epoch_sha256="f" * 64
    ).configuration_epoch_sha256 != first.configuration_epoch_sha256


@pytest.mark.parametrize(
    "field, value, blocker",
    [
        ("firmware_review_disposition", ReviewDisposition.UNREVIEWED,
         "FIRMWARE_INDEPENDENT_REVIEW_INCOMPLETE"),
        ("r97_review_packet_sha256", "1" * 64, "REVIEW_PACKET_MISMATCH"),
        ("candidate_app_sha256", "2" * 64, "CANDIDATE_APP_MISMATCH"),
        ("protocol_source_sha256", "3" * 64, "PROTOCOL_SOURCE_MISMATCH"),
        ("joint_mapping_source_sha256", "4" * 64,
         "JOINT_MAPPING_SOURCE_MISMATCH"),
    ],
)
def test_release_identity_or_review_drift_blocks(field, value, blocker):
    report = assess_controller_configuration_epoch_intake_v1(
        _intake(**{field: value}), evaluated_monotonic_ns=200)
    assert report.status == "BLOCKED"
    assert blocker in report.blockers


def test_synthetic_or_unreviewed_component_blocks():
    synthetic = assess_controller_configuration_epoch_intake_v1(
        _intake(components=_components(origin=EvidenceOrigin.SYNTHETIC_TEST_ONLY)),
        evaluated_monotonic_ns=200,
    )
    unreviewed = assess_controller_configuration_epoch_intake_v1(
        _intake(components=_components(disposition=ReviewDisposition.UNREVIEWED)),
        evaluated_monotonic_ns=200,
    )
    assert synthetic.blockers == ("COMPONENT_NOT_PHYSICAL_ORIGINAL",)
    assert unreviewed.blockers == (
        "COMPONENT_INDEPENDENT_REVIEW_INCOMPLETE",)


def test_future_or_stale_measurements_block():
    future = assess_controller_configuration_epoch_intake_v1(
        _intake(components=_components(measured=300, valid_until=500)),
        evaluated_monotonic_ns=200,
    )
    stale = assess_controller_configuration_epoch_intake_v1(
        _intake(components=_components(measured=100, valid_until=150)),
        evaluated_monotonic_ns=200,
    )
    assert future.blockers == ("EVALUATION_PREDATES_MEASUREMENT",)
    assert stale.blockers == ("MEASUREMENT_STALE",)


@pytest.mark.parametrize("components", [(), _components()[::-1], _components()[:-1]])
def test_component_membership_and_order_are_closed(components):
    with pytest.raises(ControllerConfigurationEpochIntakeError, match="eight closed"):
        _intake(components=components)


def test_component_requires_expiry_after_measurement():
    with pytest.raises(ControllerConfigurationEpochIntakeError, match="expiry"):
        replace(_components()[0], valid_until_monotonic_ns=100)


def test_schema_rejects_claimed_physical_authority():
    document = _intake().to_dict()
    document["installation_authorized"] = True
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema(
            "controller_configuration_epoch_intake_v1.schema.json"
        )).validate(document)
