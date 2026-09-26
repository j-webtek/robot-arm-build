from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sys

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "software/ai"), str(ROOT / "software/tests/unit"),
                str(ROOT / "software/tests/integration")]

import test_model_motion_ingress_v2 as arm  # noqa: E402
import test_model_motion_v2_shared_gate as shared  # noqa: E402
from rocell_ai.batch_emitter_v2 import TargetObservationV2, assemble  # noqa: E402
from rocell_ai.shared_shadow_runner_v2 import (  # noqa: E402
    SharedShadowInputsV2, run_shared_shadow_v2)
from rocell.typing import compile_development_text  # noqa: E402


def _inputs(*, edge=False, expired=False):
    context, _plan, args, registry = shared._actual_bytes_and_registry()
    profile_id = compile_development_text("keyboard", "hhi").profile_id
    capability = replace(args["capability"], profile_id=profile_id)
    registry = replace(registry, capability_profile_id=profile_id)
    observations = dict(args["observations"])
    if edge:
        target = context.targets.resolve("keyboard", "H")
        observations["H"] = TargetObservationV2(
            arm.Point3Mm("board", target.safe_rectangle_board_mm[0] + 1.1,
                         target.center.y, target.center.z), 0.93)
    evidence = args["evidence"]
    now = arm.T0 + 3_000
    if expired:
        now = evidence.expires_at_epoch_ms
    return context, SharedShadowInputsV2(
        batch_id="raw-shadow-v2", capability=capability,
        geometry=args["geometry"], evidence=evidence,
        uncertainty=args["uncertainty"], observations=observations,
        registry=registry,
        policy=arm.ArmMotionPolicyV2(
            "keyboard-contact-conservative-v1", 25.0, arm.SpeedClass.SLOW),
        observed_start_state=shared._fresh_observed_state(context),
        current_time_epoch_ms=now, ingress_monotonic_ns=9_000_000_000,
        preplanner_monotonic_ns=10_000_000_000,
        planner_monotonic_ns=10_500_000_000)


def _run(request, observation, inputs=True, **fixture_changes):
    context, fixture = _inputs(**fixture_changes)
    return run_shared_shadow_v2(
        request_id="raw-request-001", request=request,
        observation=observation, context=context,
        inputs=fixture if inputs else None)


def test_supported_raw_request_reaches_exact_arm_blocker_without_authority():
    report = _run("type hhi on keyboard", {"ref": "scene-1", "fresh": True})
    assert report["status"] == "BLOCKED_CALIBRATION_MISSING_OR_STALE"
    assert report["arm_shadow_trace"]["sequence_snapshot"]["action_count"] == 3
    assert report["arm_shadow_trace"]["actions"][0]["target_id"] == "H"
    assert report["controller_commands"] == report["waveshare_bytes"] == []
    assert report["hardware_access"] is report["physical_authority"] is False


def test_actual_compiler_profile_is_accepted_by_batch_schema_and_runtime():
    context, inputs = _inputs()
    plan = compile_development_text("keyboard", "hhi")
    assert plan.profile_id == "development/keyboard-us-lowercase-semantic-v1"
    payload = assemble(
        plan, batch_id=inputs.batch_id, request_id="raw-request-schema",
        capability=inputs.capability, geometry=inputs.geometry,
        evidence=inputs.evidence, observations=inputs.observations,
        uncertainty=inputs.uncertainty)
    schema_root = ROOT / "software/ai/schemas"
    batch_schema = json.loads(
        (schema_root / "model_motion_batch_v2.schema.json").read_text())
    proposal_schema = json.loads(
        (schema_root / "model_motion_proposal_v2.schema.json").read_text())
    batch_schema["properties"]["proposals"]["items"] = {
        key: value for key, value in proposal_schema.items()
        if key not in {"$schema", "$id", "$defs"}
    }
    jsonschema.Draft202012Validator(batch_schema).validate(json.loads(payload))
    decoded = arm.decode_model_motion_batch_v2_json(payload)
    assert decoded.capability.profile_id == plan.profile_id
    assert decoded.intent_plan_sha256 == plan.plan_hash


@pytest.mark.parametrize(("request_text", "observation", "status", "reason"), [
    ("type it on keyboard", {"ref": "scene-1", "fresh": True},
     "CLARIFICATION_REQUIRED", "text_ambiguous"),
    ("call 5551234 on phone", {"ref": "scene-1", "fresh": True},
     "UNSUPPORTED_REQUEST", "operation_not_available"),
    ("type hhi on keyboard", {"ref": "scene-1", "fresh": False},
     "STALE_OBSERVATION", "stale_observation"),
    ("type hhi on keyboard",
     {"ref": "scene-1", "fresh": True, "obstructed": True},
     "PERCEPTION_ABSTAIN_OBSTRUCTED", "working_area_obstructed"),
])
def test_raw_request_terminal_outcomes_are_preserved(
    request_text, observation, status, reason,
):
    report = _run(request_text, observation)
    assert report["status"] == status
    assert report["reason"] == reason
    assert report["arm_shadow_trace"] is None
    assert report["hardware_commands_generated"] == 0


def test_supported_request_without_qualified_perception_stops_before_emission():
    report = _run("type hhi on keyboard", {"ref": "scene-1", "fresh": True},
                  inputs=False)
    assert report["status"] == "PERCEPTION_EVIDENCE_REQUIRED"
    assert report["intent_plan_sha256"] is not None
    assert report["arm_shadow_trace"] is None


@pytest.mark.parametrize("fixture_changes", [{"edge": True}, {"expired": True}])
def test_unsafe_coordinate_or_expired_evidence_rejects_before_planning(
    fixture_changes,
):
    report = _run("type hhi on keyboard", {"ref": "scene-1", "fresh": True},
                  **fixture_changes)
    assert report["status"] == "REJECTED_BEFORE_PLANNING"
    assert report["arm_shadow_trace"] is None
    assert report["controller_commands"] == report["waveshare_bytes"] == []
