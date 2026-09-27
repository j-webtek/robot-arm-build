"""Integrity checks for held-out synthetic precision-adapter evidence."""

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

AI = Path(__file__).resolve().parents[1]
ROOT = AI.parents[1]
sys.path[:0] = [str(AI), str(AI.parent / "src")]

from rocell.models import decode_model_motion_batch_v2_json
from rocell_ai.scene_observation import canonical_hash

BUNDLE_PATH = AI / "eval/precision_adapter_localization_v1_bundle.json"
BATCH_PATH = AI / "eval/precision_adapter_batch_v2_contract_fixture.json"
METADATA_PATH = AI / "eval/precision_adapter_batch_v2_contract_fixture_metadata.json"


def _load(path):
    return json.loads(path.read_text())


def test_bundle_schema_hashes_scope_and_per_target_accounting():
    bundle = _load(BUNDLE_PATH)
    schema = _load(AI / "schemas/localization_evaluation_bundle_v1.schema.json")
    qualification_schema = _load(AI / "schemas/localization_qualification_v0.schema.json")
    qualification_uri = "https://rocell.local/schemas/localization_qualification_v0.schema.json"
    registry = Registry().with_resource(
        qualification_uri, Resource.from_contents(qualification_schema)
    )
    Draft202012Validator(schema, registry=registry).validate(bundle)
    plan = _load(AI / "eval/precision_adapter_localization_v1_plan.json")
    assert bundle["scope"] == "SYNTHETIC_OFFLINE_ONLY"
    assert bundle["qualification_installed"] is False
    assert bundle["physical_deployment_qualified"] is False
    assert bundle["hardware_writes"] == bundle["physical_movements"] == 0
    assert bundle["model_checkpoint_sha256"] == plan["model_checkpoint_sha256"]
    assert bundle["target_catalog_sha256"] == plan["target_catalog_sha256"]
    assert bundle["calibration_dataset_sha256"] != bundle["evaluation_dataset_sha256"]
    assert bundle["bundle_sha256"] == canonical_hash(
        {key: value for key, value in bundle.items() if key != "bundle_sha256"}
    )
    assert set(bundle["per_target"]) == set(bundle["covered_target_ids"])
    radius = bundle["conservative_planar_error_bound_mm"]
    for result in bundle["per_target"].values():
        assert result["sample_count"] == bundle["evaluation_sample_count"]
        assert len(result["error_series_sha256"]) == 64
        assert 0 <= result["failure_count"] <= result["sample_count"]
        assert len(result["failure_case_ids"]) == result["failure_count"]
        assert result["abstention_count"] == result["sample_count"]
        assert result["maximum_error_mm"] <= radius or result["failure_count"] > 0


def test_contract_fixture_is_actual_v2_output_with_zero_authority():
    metadata = _load(METADATA_PATH)
    payload = BATCH_PATH.read_bytes()
    batch = decode_model_motion_batch_v2_json(payload)
    assert metadata["scope"] == "SYNTHETIC_CONTRACT_FIXTURE_ONLY"
    assert metadata["batch_file_sha256"] == hashlib.sha256(payload).hexdigest()
    assert [proposal.target_id for proposal in batch.proposals] == ["H", "H", "1", "PERIOD"]
    document = batch.to_dict()
    assert document["controller_commands"] == []
    assert document["hardware_access"] is document["physical_authority"] is False
    assert metadata["qualification_installed_for_deployment"] is False
    assert metadata["physical_deployment_qualified"] is False
    assert metadata["hardware_writes"] == metadata["physical_movements"] == 0


def test_contract_fixture_generator_replays_exact_retained_bytes():
    result = subprocess.run(
        [sys.executable, str(AI / "eval/generate_precision_adapter_batch_v2_fixture.py")],
        cwd=ROOT, check=True, capture_output=True, text=True, timeout=30,
    )
    assert json.loads(result.stdout)["batch_file_sha256"] == hashlib.sha256(
        BATCH_PATH.read_bytes()).hexdigest()


def test_full_evaluator_fails_closed_when_research_artifacts_are_external():
    path = AI / "eval/evaluate_precision_adapter_localization_v1.py"
    spec = importlib.util.spec_from_file_location("precision_evaluator", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        module.evaluate(AI / "eval/precision_adapter_localization_v1_plan.json")
    except FileNotFoundError as error:
        message = str(error)
    else:
        raise AssertionError("external research dependencies unexpectedly resolved")
    assert "precision evaluation requires external research artifacts" in message
    assert "grouped_linear_refit_v1/model.pt" in message
