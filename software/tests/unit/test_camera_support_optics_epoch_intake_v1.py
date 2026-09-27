from __future__ import annotations

from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path

import jsonschema
import pytest

from rocell.application.camera_support_optics_epoch_intake_v1 import (
    REQUIRED_BINDINGS,
    BindingReviewDisposition,
    CameraSupportBindingV1,
    CameraSupportOpticsEpochError,
    assess_camera_support_optics_epoch_intake_v1,
    build_camera_support_optics_epoch_intake_v1,
    camera_support_optics_epoch_component_v1,
)
from rocell.application.installed_controller_qualification_v1 import EvidenceOrigin


ROOT = Path(__file__).resolve().parents[3]
SOFTWARE = ROOT / "software"


def digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def binding(binding_id: str, **changes) -> CameraSupportBindingV1:
    values = dict(
        binding_id=binding_id,
        evidence_sha256=digest(f"evidence:{binding_id}"),
        owner_ai_review_sha256=digest(f"review:{binding_id}"),
        measured_monotonic_ns=10,
        valid_until_monotonic_ns=100,
        evidence_origin=EvidenceOrigin.PHYSICAL_RETAINED_ORIGINALS,
        review_disposition=BindingReviewDisposition.OWNER_AI_ACCEPTED,
    )
    values.update(changes)
    return CameraSupportBindingV1(**values)


def test_repository_baseline_is_deterministic_and_all_four_bindings_missing():
    first = build_camera_support_optics_epoch_intake_v1(ROOT)
    second = build_camera_support_optics_epoch_intake_v1(ROOT)
    assert first == second
    report = assess_camera_support_optics_epoch_intake_v1(
        first, evaluated_monotonic_ns=20)
    assert report.to_dict()["status"] == "BLOCKED"
    assert report.to_dict()["missing_binding_ids"] == list(REQUIRED_BINDINGS)
    assert report.to_dict()["blocked_binding_ids"] == []
    assert report.to_dict()["component_admission_ready"] is False
    assert report.to_dict()["epoch_advanced"] is False
    facts = dict(first.baseline_facts)
    assert facts["camera_profile_record_state"] == "PURCHASED_PENDING_RECEIPT"
    assert facts["received_unit_confirmed"] is None
    assert facts["persistent_usb_identity_sha256"] is None
    assert facts["commissioned_mode"] is None
    assert facts["camera_controls_snapshot_sha256"] is None
    assert facts["unresolved_hardware_intake_rows"] == 55


def test_synthetic_stale_and_unreviewed_bindings_remain_distinct_blockers():
    bindings = (
        binding("camera_receipt", evidence_origin=EvidenceOrigin.SYNTHETIC_TEST_ONLY),
        binding("camera_identity", valid_until_monotonic_ns=15),
        binding("camera_mode_controls",
                review_disposition=BindingReviewDisposition.UNREVIEWED),
        binding("support_witnesses", measured_monotonic_ns=30,
                valid_until_monotonic_ns=100),
    )
    intake = build_camera_support_optics_epoch_intake_v1(ROOT, bindings=bindings)
    report = assess_camera_support_optics_epoch_intake_v1(
        intake, evaluated_monotonic_ns=20).to_dict()
    assert report["missing_binding_ids"] == []
    assert report["blocked_binding_ids"] == list(REQUIRED_BINDINGS)
    assert report["binding_assessments"][0]["blockers"] == [
        "NOT_PHYSICAL_RETAINED_ORIGINAL"]
    assert report["binding_assessments"][1]["blockers"] == ["EVIDENCE_STALE"]
    assert report["binding_assessments"][2]["blockers"] == [
        "OWNER_AI_REVIEW_INCOMPLETE"]
    assert report["binding_assessments"][3]["blockers"] == [
        "EVALUATION_PREDATES_MEASUREMENT"]


def test_complete_fixture_can_build_component_but_grants_no_authority():
    intake = build_camera_support_optics_epoch_intake_v1(
        ROOT, bindings=tuple(binding(item) for item in REQUIRED_BINDINGS))
    report = assess_camera_support_optics_epoch_intake_v1(
        intake, evaluated_monotonic_ns=20)
    component = camera_support_optics_epoch_component_v1(intake, report)
    assert report.ready is True
    assert component.component.value == "camera_support_optics"
    assert [item.binding_id for item in component.binding_evidence] == list(
        REQUIRED_BINDINGS)
    assert report.to_dict()["hardware_access"] is False
    assert report.to_dict()["physical_authority"] is False
    crossed = replace(report, intake_sha256="0" * 64)
    with pytest.raises(CameraSupportOpticsEpochError,
                       match="crosses intake lineage"):
        camera_support_optics_epoch_component_v1(intake, crossed)


def test_retained_artifacts_match_builder_and_schemas(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "arm070_builder", SOFTWARE / "scripts/build_arm070_camera_support_readiness.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    summary = module.build(repository_root=ROOT, output_directory=tmp_path)
    assert summary["status"] == "BLOCKED"
    assert summary["missing_binding_ids"] == list(REQUIRED_BINDINGS)
    pairs = (
        ("arm070_camera_support_optics_intake.json",
         "camera_support_optics_epoch_intake_v1.schema.json"),
        ("arm070_camera_support_optics_readiness.json",
         "camera_support_optics_epoch_assessment_v1.schema.json"),
    )
    for artifact, schema_name in pairs:
        generated = json.loads((tmp_path / artifact).read_text())
        retained = json.loads((SOFTWARE / "ai/eval" / artifact).read_text())
        assert generated == retained
        schema = json.loads((SOFTWARE / "ai/schemas" / schema_name).read_text())
        jsonschema.Draft202012Validator(schema).validate(retained)
