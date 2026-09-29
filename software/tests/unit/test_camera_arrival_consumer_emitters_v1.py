from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from rocell.application.camera_arrival_consumer_emitters_v1 import (
    CameraArrivalConsumerEmitterV1Error,
    emit_camera_campaign_consumer_receipt_v1,
    emit_camera_localization_consumer_receipt_v1,
    emit_camera_support_consumer_receipt_v1,
)
from rocell.application.camera_arrival_consumer_handoff_v1 import (
    build_camera_arrival_consumer_handoff_v1,
)
from rocell.application.camera_arrival_consumer_validation_v1 import (
    assess_camera_arrival_consumer_validation_v1,
    parse_camera_arrival_consumer_validation_receipt_v1,
)
from rocell.application.camera_arrival_kit_v1 import build_camera_arrival_kit_v1


ROOT = Path(__file__).resolve().parents[3]
H = "a" * 64
WHEN = "2026-09-29T15:00:00Z"


def _hash(core: dict) -> str:
    raw = json.dumps(core, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _populate(root: Path) -> None:
    for slot in build_camera_arrival_kit_v1()["slots"]:
        relative = f"sources/{slot['artifact_id']}.bin"
        source = root / relative
        source.parent.mkdir(parents=True, exist_ok=True)
        payload = slot["artifact_id"].encode()
        source.write_bytes(payload)
        uncertainty = None if not slot["uncertainty_required"] else {
            "value": 0.1, "unit": slot["required_units"][0],
            "method": "fixture bound", "evidence_sha256": H,
        }
        sidecar = root / slot["destination_relative_to_external_evidence_root"]
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        sidecar.write_text(json.dumps({
            "schema": "rocell.camera_arrival_original.v1",
            "artifact_id": slot["artifact_id"],
            "artifact_class": slot["artifact_class"],
            "captured_at_utc": "2026-09-29T12:00:00Z",
            "source_relative_path": relative, "source_size_bytes": len(payload),
            "source_sha256": hashlib.sha256(payload).hexdigest(),
            "units": slot["required_units"], "uncertainty": uncertainty,
            "configuration_epoch_id": "camera-epoch-001",
            "review": {
                "reviewer_id": "owner-ai-review",
                "reviewed_at_utc": "2026-09-29T13:00:00Z",
                "disposition": "ACCEPTED", "review_sha256": H,
            },
        }), encoding="utf-8")


def _support(*, blocked: str | None = None) -> dict:
    bindings = []
    for artifact_id in (
        "camera_receipt", "camera_identity", "camera_mode_controls", "support_witnesses"
    ):
        blockers = ["EVIDENCE_STALE"] if artifact_id == blocked else []
        bindings.append({
            "binding_id": artifact_id,
            "status": "BLOCKED" if blockers else "READY",
            "blockers": blockers,
        })
    core = {
        "schema": "rocell.camera_support_optics_epoch_assessment.v1",
        "status": "BLOCKED" if blocked else "READY_FOR_COMPONENT_ADMISSION",
        "binding_assessments": bindings,
        "component_admission_ready": blocked is None,
        "epoch_advanced": False, "hardware_access": False,
        "camera_open_authorized": False, "installation_authorized": False,
        "controller_start_authorized": False, "transport_authorized": False,
        "execution_authorized": False, "physical_authority": False,
    }
    return {**core, "assessment_sha256": _hash(core)}


def _campaign() -> dict:
    core = {
        "schema": "rocell.physical_camera_localization_campaign_preflight.v1",
        "status": "READY_FOR_OFFLINE_EVALUATION", "camera_opened": False,
        "model_loaded": False, "controller_started": False,
        "hardware_writes": 0, "physical_movements": 0,
        "qualification_installed": False,
    }
    return {**core, "receipt_sha256": _hash(core)}


def _evaluation(*, passed: bool = True) -> dict:
    criteria = {
        "held_out_coverage_met": passed,
        "unsafe_false_accepts_zero": True,
    }
    core = {
        "schema": "rocell.physical_camera_localization_evaluation_result.v1",
        "status": "QUALIFICATION_RECOMMENDED" if passed else "QUALIFICATION_BLOCKED",
        "criteria": criteria, "qualification_installed": False,
        "physical_deployment_qualified": False,
        "model_motion_batch_emitted": False, "controller_started": False,
        "hardware_writes": 0, "physical_movements": 0,
    }
    return {**core, "result_sha256": _hash(core)}


def test_existing_explicit_consumers_emit_eight_exact_pass_receipts(tmp_path: Path):
    _populate(tmp_path)
    handoff = build_camera_arrival_consumer_handoff_v1(ROOT, tmp_path)
    receipts = []
    support = _support()
    for artifact_id in (
        "camera_receipt", "camera_identity", "camera_mode_controls", "support_witnesses"
    ):
        receipts.append(emit_camera_support_consumer_receipt_v1(
            handoff, artifact_id, support, validated_at_utc=WHEN
        ))
    campaign = _campaign()
    for artifact_id in ("camera_intrinsics", "localization_campaign"):
        receipts.append(emit_camera_campaign_consumer_receipt_v1(
            handoff, artifact_id, campaign, validated_at_utc=WHEN
        ))
    evaluation = _evaluation()
    for artifact_id in ("camera_to_board_transform", "localization_evaluation"):
        receipts.append(emit_camera_localization_consumer_receipt_v1(
            handoff, artifact_id, evaluation, validated_at_utc=WHEN
        ))
    assert all(dict(parse_camera_arrival_consumer_validation_receipt_v1(row)) == row for row in receipts)
    assessment = assess_camera_arrival_consumer_validation_v1(handoff, receipts)
    assert assessment["pass_count"] == 8
    assert assessment["pending_count"] == 7
    assert assessment["complete_for_offline_review"] is False
    assert assessment["physical_authority"] is False


def test_native_blocker_is_retained_with_native_output_hash(tmp_path: Path):
    _populate(tmp_path)
    handoff = build_camera_arrival_consumer_handoff_v1(ROOT, tmp_path)
    receipt = emit_camera_localization_consumer_receipt_v1(
        handoff, "localization_evaluation", _evaluation(passed=False),
        validated_at_utc=WHEN,
    )
    assert receipt["validation_status"] == "BLOCKED"
    assert receipt["blockers"] == ["CRITERION_HELD_OUT_COVERAGE_MET"]
    assert len(receipt["output_sha256"]) == 64


def test_support_emitter_preserves_route_local_blocker(tmp_path: Path):
    _populate(tmp_path)
    handoff = build_camera_arrival_consumer_handoff_v1(ROOT, tmp_path)
    receipt = emit_camera_support_consumer_receipt_v1(
        handoff, "camera_identity", _support(blocked="camera_identity"),
        validated_at_utc=WHEN,
    )
    assert receipt["validation_status"] == "BLOCKED"
    assert receipt["blockers"] == ["EVIDENCE_STALE"]


@pytest.mark.parametrize("failure", ("wrong_route", "tampered", "blocked_handoff"))
def test_emitters_fail_closed(tmp_path: Path, failure: str):
    if failure != "blocked_handoff":
        _populate(tmp_path)
    handoff = build_camera_arrival_consumer_handoff_v1(ROOT, tmp_path)
    output = _campaign()
    if failure == "wrong_route":
        with pytest.raises(CameraArrivalConsumerEmitterV1Error):
            emit_camera_campaign_consumer_receipt_v1(
                handoff, "camera_receipt", output, validated_at_utc=WHEN
            )
    elif failure == "tampered":
        output["camera_opened"] = True
        with pytest.raises(CameraArrivalConsumerEmitterV1Error):
            emit_camera_campaign_consumer_receipt_v1(
                handoff, "camera_intrinsics", output, validated_at_utc=WHEN
            )
    else:
        with pytest.raises(CameraArrivalConsumerEmitterV1Error):
            emit_camera_campaign_consumer_receipt_v1(
                handoff, "camera_intrinsics", output, validated_at_utc=WHEN
            )
