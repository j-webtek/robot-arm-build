"""Operational handoff gate tests; retained evidence only, zero hardware."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path

import jsonschema
import pytest

from rocell.application.model_arm_operational_readiness_v1 import (
    SOURCE_PATHS,
    ModelArmOperationalReadinessError,
    assess_model_arm_operational_readiness_v1,
    build_model_arm_operational_readiness_v1,
)


ROOT = Path(__file__).resolve().parents[3]
SOFTWARE = ROOT / "software"
RETAINED = SOFTWARE / "ai/eval/arm072_model_arm_operational_readiness.json"
SCHEMA = SOFTWARE / "ai/schemas/model_arm_operational_readiness_v1.schema.json"


def _loads(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def _inputs() -> tuple[dict, dict, dict, dict, dict, list[dict[str, str]]]:
    values = [_loads(path) for path in SOURCE_PATHS]
    sources = [{
        "path": path,
        "sha256": hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
    } for path in SOURCE_PATHS]
    return values[0], values[1], values[2], values[3], values[4], sources


def test_current_retained_evidence_produces_one_precise_blocker_map():
    report = build_model_arm_operational_readiness_v1(ROOT)
    assert report["status"] == "BLOCKED"
    assert report["ready_stage_ids"] == ["wire_contract"]
    assert report["blocked_stage_ids"] == [
        "qualified_perception",
        "camera_support_optics",
        "measured_configuration_epoch",
        "measured_planner_calibration",
        "installed_controller_runtime",
    ]
    camera = report["stage_assessments"][2]
    assert camera["blockers"] == [
        "RETAINED_ORIGINAL_MISSING:camera_receipt",
        "RETAINED_ORIGINAL_MISSING:camera_identity",
        "RETAINED_ORIGINAL_MISSING:camera_mode_controls",
        "RETAINED_ORIGINAL_MISSING:support_witnesses",
    ]
    assert report["single_action_review_ready"] is False
    assert report["production_dispatch_allowed"] is False
    assert report["controller_commands"] == []
    assert report["hardware_commands_generated"] == 0
    assert report["hardware_access"] is False
    assert report["movement_authorized"] is False
    assert report["physical_authority"] is False
    controller = report["stage_assessments"][5]
    assert "R97_INDEPENDENT_REVIEW_DECISION_MISSING" not in controller["blockers"]
    assert controller["blockers"] == [
        "INSTALLED_RUNTIME_NOT_ATTESTED_AS_R97",
        "ACTIVE_FEEDBACK_SURFACE_REJECTED",
        "MEASURED_CONFIGURATION_EPOCH_MISSING",
        "R97_CONFIGURATION_EPOCH_NULL",
    ]


def test_retained_report_rebuilds_exactly_and_validates_against_schema(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "readiness_builder",
        SOFTWARE / "scripts/build_model_arm_operational_readiness_v1.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    generated_path = tmp_path / "readiness.json"
    generated = module.build(repository_root=ROOT, output=generated_path)
    assert generated == json.loads(RETAINED.read_text(encoding="utf-8"))
    assert generated == json.loads(generated_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(
        json.loads(SCHEMA.read_text(encoding="utf-8"))).validate(generated)


def test_tampered_hashed_assessment_is_rejected():
    conformance, owner_acceptance, epoch, camera, controller, sources = _inputs()
    epoch["missing_component_ids"] = []
    with pytest.raises(ModelArmOperationalReadinessError,
                       match="configuration epoch content hash is invalid"):
        assess_model_arm_operational_readiness_v1(
            conformance=conformance,
            owner_review_acceptance=owner_acceptance,
            configuration_epoch=epoch,
            camera_support=camera,
            controller_runtime=controller,
            source_artifacts=sources,
        )


def test_crossed_camera_original_lineage_is_rejected_even_with_valid_hash():
    conformance, owner_acceptance, epoch, camera, controller, sources = _inputs()
    camera = deepcopy(camera)
    camera["missing_binding_ids"] = camera["missing_binding_ids"][:-1]
    unsigned = {key: value for key, value in camera.items()
                if key != "assessment_sha256"}
    camera["assessment_sha256"] = hashlib.sha256(json.dumps(
        unsigned, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False).encode()).hexdigest()
    with pytest.raises(ModelArmOperationalReadinessError,
                       match="missing-binding lineage differs"):
        assess_model_arm_operational_readiness_v1(
            conformance=conformance,
            owner_review_acceptance=owner_acceptance,
            configuration_epoch=epoch,
            camera_support=camera,
            controller_runtime=controller,
            source_artifacts=sources,
        )


def test_source_set_cannot_be_reordered_or_substituted():
    conformance, owner_acceptance, epoch, camera, controller, sources = _inputs()
    sources[0]["path"] = "software/config/substitute.json"
    with pytest.raises(ModelArmOperationalReadinessError,
                       match="source artifact set differs"):
        assess_model_arm_operational_readiness_v1(
            conformance=conformance,
            owner_review_acceptance=owner_acceptance,
            configuration_epoch=epoch,
            camera_support=camera,
            controller_runtime=controller,
            source_artifacts=sources,
        )
