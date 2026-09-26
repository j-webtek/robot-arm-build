from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sys

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT / "software/ai"), str(ROOT / "software/tests/unit"),
    str(ROOT / "software/tests/integration"),
]

import test_model_motion_ingress_v2 as arm  # noqa: E402
import test_model_motion_v2_shared_gate as shared  # noqa: E402
import test_synthetic_epoch_model_arm_rehearsal_v1 as downstream  # noqa: E402
from rocell_ai.batch_emitter_v2 import assemble  # noqa: E402
from rocell.application.ai_emitted_epoch_model_arm_rehearsal_v1 import (  # noqa: E402
    AIEmittedEpochModelArmRehearsalError,
    assess_ai_emitted_epoch_model_arm_rehearsal_v1,
)
from rocell.application.model_motion_planner_gate_v2 import (  # noqa: E402
    ArmMotionPolicyV2,
    evaluate_model_motion_planner_gate_v2,
)
from rocell.application.model_motion_registry_v2 import (  # noqa: E402
    ingest_with_trusted_registry_v2,
    revalidate_with_trusted_registry_v2,
)


def _actual_emitter_lineage():
    context, plan, args, registry = shared._actual_bytes_and_registry()
    payload = assemble(plan, **args)
    assert isinstance(payload, bytes)
    batch = arm.decode_model_motion_batch_v2_json(payload)
    ingress = ingest_with_trusted_registry_v2(
        batch, plan, context, registry=registry,
        current_time_epoch_ms=arm.T0 + 3_000,
        current_monotonic_ns=9_000_000_000)
    preplanner = revalidate_with_trusted_registry_v2(
        ingress, registry=registry, current_monotonic_ns=10_000_000_000)
    planner = evaluate_model_motion_planner_gate_v2(
        batch.proposals[0], batch, ingress, preplanner, context,
        policy=ArmMotionPolicyV2(
            "keyboard-contact-conservative-v1", 25.0, arm.SpeedClass.SLOW),
        observed_start_state=shared._fresh_observed_state(context),
        evaluation_monotonic_ns=10_500_000_000)

    values = list(downstream._lineage())
    synthetic_planner = downstream.envelope_fixture._synthetic_ready(planner)
    inner = replace(
        downstream.envelope_fixture._inner(
            batch.batch_sha256,
            synthetic_planner["derived_v1_surrogate_sha256"],
            synthetic_planner["measured_planner_gate_sha256"]),
        configuration_epoch_sha256=values[1].configuration_epoch_sha256,
    )
    envelope = downstream.bind_trajectory_execution_envelope_v2(
        batch, batch.proposals[0], synthetic_planner, inner)
    profile = downstream.WaveshareT102EncodingProfileV1(
        profile_id="waveshare-t102-ai-emitted-preview-v1",
        vendor_source_sha256="1" * 64,
        controller_joint_mapping_sha256="2" * 64,
        expected_trajectory_limits_sha256=(
            downstream.trajectory_limits_sha256(envelope)),
        controller_session_id=inner.controller_session_id,
        configuration_epoch_sha256=values[1].configuration_epoch_sha256,
        fixed_gripper_rad=0.25, speed=20, acceleration=1,
    )
    permit = downstream.issue_zero_write_encoding_permit_v1(
        envelope, profile, issued_monotonic_ns=10,
        expires_monotonic_ns=2_000_000_000)
    receipt = downstream.ZeroWriteWaveshareAdapterV1().preview(
        envelope, permit, profile, now_monotonic_ns=100)
    values[3:] = [batch, envelope, profile, receipt]
    synthetic_report = downstream._assess(values)
    return payload, ingress, preplanner, planner, synthetic_report


def _assess(values):
    names = (
        "batch_payload", "ingress_report", "preplanner_report",
        "planner_report", "synthetic_rehearsal_report",
    )
    return assess_ai_emitted_epoch_model_arm_rehearsal_v1(
        **dict(zip(names, values, strict=True)))


def test_actual_ai_emitter_bytes_reach_arm_blocker_and_bound_preview():
    values = _actual_emitter_lineage()
    report = _assess(values)
    document = report.to_dict()

    assert document["status"] == (
        "AI_BYTES_ADMITTED_PLANNER_BLOCKED_SYNTHETIC_PREVIEW_ONLY")
    assert document["measured_planner_status"] == (
        "BLOCKED_CALIBRATION_MISSING_OR_STALE")
    assert document["actual_ai_emitter_bytes_admitted"] is True
    assert document["synthetic_downstream_preview"] is True
    assert document["command_count"] == 1
    assert document["production_dispatch_allowed"] is False
    assert document["hardware_access"] is document["physical_authority"] is False
    schema = json.loads((
        ROOT / "software/ai/schemas/ai_emitted_epoch_model_arm_rehearsal_v1.schema.json"
    ).read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(document)


def test_noncanonical_or_tampered_emitter_bytes_fail_closed():
    values = list(_actual_emitter_lineage())
    values[0] += b"\n"
    with pytest.raises(AIEmittedEpochModelArmRehearsalError, match="canonical"):
        _assess(values)


def test_crossed_ingress_or_downstream_batch_fails_closed():
    values = list(_actual_emitter_lineage())
    crossed = dict(values[1]); crossed["batch_sha256"] = "f" * 64
    values[1] = crossed
    with pytest.raises(AIEmittedEpochModelArmRehearsalError, match="content hash"):
        _assess(values)


def test_planner_readiness_cannot_replace_required_calibration_blocker():
    values = list(_actual_emitter_lineage())
    planner = dict(values[3]); planner["status"] = (
        "READY_FOR_SINGLE_ACTION_EXECUTION_ADMISSION")
    values[3] = planner
    with pytest.raises(AIEmittedEpochModelArmRehearsalError, match="content hash"):
        _assess(values)
