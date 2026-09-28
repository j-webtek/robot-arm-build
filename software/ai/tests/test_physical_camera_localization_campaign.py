from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import pytest
from jsonschema import Draft202012Validator


AI_ROOT = Path(__file__).resolve().parents[1]
RECEIPT_SCHEMA_PATH = AI_ROOT / "schemas" / "physical_camera_localization_preflight_receipt_v1.schema.json"
sys.path.insert(0, str(AI_ROOT))

from eval.preflight_physical_camera_campaign import (  # noqa: E402
    SCHEMA_PATH,
    canonical_hash,
    load_strict_json,
    preflight,
)


CONDITIONS = [
    "nominal", "low_light", "high_light", "glare", "blur",
    "arm_occlusion", "tool_occlusion", "cable_occlusion",
    "placement_translation", "placement_yaw", "device_absent",
]


def _file_record(root: Path, relative: str, payload: bytes) -> dict[str, object]:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return {
        "relative_path": relative,
        "size_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def _campaign(root: Path) -> dict[str, object]:
    common = "a" * 64
    camera = "b" * 64
    mode = "c" * 64
    epoch = "d" * 64
    calibration = []
    evaluation = []
    for index in range(600):
        split = "calibration" if index < 300 else "evaluation"
        local_index = index if index < 300 else index - 300
        image = _file_record(root, f"images/{split}-{local_index:03d}.png", f"image-{index}".encode())
        truth = _file_record(root, f"truth/{split}-{local_index:03d}.json", f'{{"index":{index}}}'.encode())
        record = {
            "capture_id": f"{split}-{local_index:03d}",
            "session_id": f"{split}-session-a",
            "captured_at_utc": f"2026-10-01T12:{index % 60:02d}:00Z",
            "conditions": ["nominal"] if split == "calibration" else [CONDITIONS[local_index % len(CONDITIONS)]],
            "camera_identity_sha256": camera,
            "camera_mode_controls_sha256": mode,
            "configuration_epoch_sha256": epoch,
            "image": image,
            "ground_truth": truth,
        }
        (calibration if split == "calibration" else evaluation).append(record)
    campaign = {
        "schema": "rocell.physical_camera_localization_campaign.v1",
        "campaign_id": "physical-camera-keyboard-v1",
        "source_commit": "1" * 40,
        "domain_id": "final-camera-keyboard-v1",
        "camera_support_optics_intake_sha256": common,
        "configuration_epoch_sha256": epoch,
        "camera_profile_sha256": common,
        "camera_identity_sha256": camera,
        "camera_mode_controls_sha256": mode,
        "camera_intrinsics_sha256": common,
        "camera_to_board_calibration_sha256": common,
        "keyboard_target_map_sha256": common,
        "model_artifact_manifest_sha256": common,
        "ground_truth_method": "INDEPENDENT_SURVEYED_FIDUCIAL_GEOMETRY",
        "requirements": {
            "minimum_calibration_captures": 300,
            "minimum_evaluation_captures": 300,
            "minimum_evaluation_captures_per_condition": 20,
            "required_conditions": CONDITIONS,
            "split_sessions_disjoint": True,
            "declared_coverage_probability": 0.99,
            "confidence_level": 0.95,
            "safe_region_rule": "COMPOSED_ERROR_BOUND_MUST_FIT_PER_TARGET_SAFE_REGION",
        },
        "calibration_captures": calibration,
        "evaluation_captures": evaluation,
        "camera_open_authorized": False,
        "controller_start_authorized": False,
        "execution_authorized": False,
        "hardware_writes": 0,
        "physical_movements": 0,
    }
    campaign["campaign_sha256"] = canonical_hash(campaign)
    return campaign


@pytest.fixture(scope="module")
def retained_campaign(tmp_path_factory):
    root = tmp_path_factory.mktemp("physical-camera-campaign")
    campaign = _campaign(root)
    campaign_path = root / "campaign.json"
    campaign_path.write_text(json.dumps(campaign), encoding="utf-8")
    return root, campaign_path, campaign


def _write_campaign(root: Path, name: str, campaign: dict[str, object]) -> Path:
    campaign["campaign_sha256"] = canonical_hash(
        {key: value for key, value in campaign.items() if key != "campaign_sha256"}
    )
    path = root / name
    path.write_text(json.dumps(campaign), encoding="utf-8")
    return path


def test_schema_is_valid_and_complete():
    Draft202012Validator.check_schema(load_strict_json(SCHEMA_PATH))


def test_complete_campaign_preflight_is_zero_authority(retained_campaign):
    root, campaign_path, _ = retained_campaign
    receipt = preflight(campaign_path, root)
    assert receipt["status"] == "READY_FOR_OFFLINE_EVALUATION"
    assert receipt["calibration_capture_count"] == 300
    assert receipt["evaluation_capture_count"] == 300
    assert min(receipt["evaluation_condition_counts"].values()) >= 20
    assert receipt["verified_retained_file_count"] == 1200
    assert receipt["camera_opened"] is False
    assert receipt["controller_started"] is False
    assert receipt["hardware_writes"] == 0
    assert receipt["physical_movements"] == 0
    core = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    assert receipt["receipt_sha256"] == canonical_hash(core)
    Draft202012Validator(load_strict_json(RECEIPT_SCHEMA_PATH)).validate(receipt)


def test_calibration_and_evaluation_sessions_must_be_disjoint(retained_campaign):
    root, _, original = retained_campaign
    campaign = deepcopy(original)
    campaign["evaluation_captures"][0]["session_id"] = "calibration-session-a"
    path = _write_campaign(root, "overlap.json", campaign)
    with pytest.raises(ValueError, match="sessions must be disjoint"):
        preflight(path, root)


def test_evaluation_condition_coverage_cannot_be_declared_only(retained_campaign):
    root, _, original = retained_campaign
    campaign = deepcopy(original)
    for capture in campaign["evaluation_captures"]:
        capture["conditions"] = ["nominal"]
    path = _write_campaign(root, "missing-conditions.json", campaign)
    with pytest.raises(ValueError, match="insufficient evaluation condition coverage"):
        preflight(path, root)


def test_retained_bytes_must_match_declared_identity(retained_campaign):
    root, campaign_path, original = retained_campaign
    relative = original["evaluation_captures"][0]["image"]["relative_path"]
    image_path = root / relative
    before = image_path.read_bytes()
    try:
        image_path.write_bytes(b"altered")
        with pytest.raises(ValueError, match="retained size mismatch|retained SHA-256 mismatch"):
            preflight(campaign_path, root)
    finally:
        image_path.write_bytes(before)


def test_duplicate_json_fields_are_rejected(tmp_path):
    path = tmp_path / "duplicate.json"
    path.write_text('{"schema":"one","schema":"two"}', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate JSON field"):
        load_strict_json(path)
