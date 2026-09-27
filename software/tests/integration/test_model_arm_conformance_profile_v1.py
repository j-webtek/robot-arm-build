"""Shared AI/arm conformance matrix; synthetic and strictly zero hardware."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sys

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "software/ai"), str(ROOT / "software/tests/unit")]

import test_model_motion_ingress_v2 as arm  # noqa: E402
import test_model_motion_v2_shared_gate as shared  # noqa: E402
from rocell_ai.batch_emitter_v2 import TargetObservationV2, assemble  # noqa: E402
from rocell.application.model_motion_registry_v2 import (  # noqa: E402
    ingest_with_trusted_registry_v2,
    revalidate_with_trusted_registry_v2,
)
from rocell.models import (  # noqa: E402
    ActionPlan,
    Device,
    MAX_BATCH_PROPOSALS_V2,
    ModelMotionBatchV2Error,
    TapPhoneTarget,
    VerifyPhoneState,
    decode_model_motion_batch_v2_json,
)
from rocell.models.model_motion_batch_v2 import (  # noqa: E402
    BATCH_SCHEMA,
    COORDINATE_PROFILE_V2,
    PROPOSAL_SCHEMA,
)


PROFILE_PATH = ROOT / "software/config/model_arm_conformance_profile_v1.json"
SCHEMA_PATH = ROOT / "software/ai/schemas/model_arm_conformance_profile_v1.schema.json"


def _profile() -> dict:
    value = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(value)
    return value


def _case(case_id: str) -> dict:
    return next(item for item in _profile()["conformance_cases"]
                if item["case_id"] == case_id)


def test_profile_matches_the_implemented_producer_consumer_boundary():
    profile = _profile()
    boundary = profile["wire_boundary"]
    assert boundary == {
        "batch_schema": BATCH_SCHEMA,
        "proposal_schema": PROPOSAL_SCHEMA,
        "coordinate_profile": COORDINATE_PROFILE_V2,
        "coordinate_units": "mm",
        "maximum_actions": MAX_BATCH_PROPOSALS_V2,
        "supported_device": "keyboard",
        "supported_action": "press_key",
        "supported_interaction": "contact",
    }
    assert {item["case_id"] for item in profile["conformance_cases"]} == {
        "keyboard_hhi_ordered",
        "missing_qualified_uncertainty",
        "phone_plan",
        "low_observation_confidence",
        "uncertainty_crosses_safe_region",
        "model_injects_arm_policy_or_authority",
    }
    assert profile["current_result"]["controller_commands"] == []
    assert profile["current_result"]["hardware_access"] is False
    assert profile["current_result"]["physical_authority"] is False


def test_actual_ai_emitter_bytes_preserve_hhi_and_reach_the_arm_gate():
    context, plan, args, registry = shared._actual_bytes_and_registry()
    payload = assemble(plan, **args)
    batch = decode_model_motion_batch_v2_json(payload)
    ingress = ingest_with_trusted_registry_v2(
        batch, plan, context, registry=registry,
        current_time_epoch_ms=arm.T0 + 3_000,
        current_monotonic_ns=9_000_000_000,
    )
    preplanner = revalidate_with_trusted_registry_v2(
        ingress, registry=registry, current_monotonic_ns=10_000_000_000)

    expected = _case("keyboard_hhi_ordered")
    assert expected["expected_disposition"] == (
        "accepted_for_fresh_sequential_planner_gates")
    assert ingress["ordered_target_ids"] == expected["expected_targets"]
    assert preplanner["status"] == "FRESH_FOR_DETERMINISTIC_PLANNING"
    assert ingress["controller_commands"] == preplanner["controller_commands"] == []
    assert ingress["hardware_access"] is preplanner["hardware_access"] is False
    assert ingress["physical_authority"] is preplanner["physical_authority"] is False


def test_unqualified_ai_research_output_abstains_before_wire_emission():
    _context, plan, args, _registry = shared._actual_bytes_and_registry()
    args["uncertainty"] = None
    assert _case("missing_qualified_uncertainty")["expected_disposition"] == (
        "producer_abstains")
    assert assemble(plan, **args) is None


def test_initial_profile_rejects_phone_sequences():
    _context, _plan, args, _registry = shared._actual_bytes_and_registry()
    phone = ActionPlan.from_text(
        device=Device.PHONE,
        profile_id=args["capability"].profile_id,
        text="tap 1",
        actions=(
            VerifyPhoneState("dialer-ready"),
            TapPhoneTarget("1", "dialer-ready", "digit-entered"),
            VerifyPhoneState("digit-entered"),
        ),
        required_calibrations=("phone_pose", "phone_tcp"),
    )
    assert _case("phone_plan")["expected_disposition"] == (
        "unsupported_by_initial_profile")
    with pytest.raises(ValueError, match="keyboard PressKey plans only"):
        assemble(phone, **args)


def test_low_confidence_bytes_decode_but_arm_consumer_rejects():
    context, plan, args, registry = shared._actual_bytes_and_registry()
    args["observations"]["H"] = replace(
        args["observations"]["H"], observation_confidence=0.1)
    batch = decode_model_motion_batch_v2_json(assemble(plan, **args))
    assert _case("low_observation_confidence")["expected_disposition"] == (
        "consumer_rejects")
    with pytest.raises(ValueError, match="confidence is below policy"):
        ingest_with_trusted_registry_v2(
            batch, plan, context, registry=registry,
            current_time_epoch_ms=arm.T0 + 3_000,
            current_monotonic_ns=9_000_000_000,
        )


def test_uncertainty_disk_crossing_a_key_region_is_rejected():
    context, plan, args, registry = shared._actual_bytes_and_registry()
    target = context.targets.resolve("keyboard", "H")
    left = target.safe_rectangle_board_mm[0]
    args["observations"]["H"] = TargetObservationV2(
        arm.Point3Mm("board", left + 1.1, target.center.y, target.center.z), 0.93)
    batch = decode_model_motion_batch_v2_json(assemble(plan, **args))
    assert _case("uncertainty_crosses_safe_region")["expected_disposition"] == (
        "consumer_rejects")
    with pytest.raises(ValueError, match="uncertainty leaves measured region"):
        ingest_with_trusted_registry_v2(
            batch, plan, context, registry=registry,
            current_time_epoch_ms=arm.T0 + 3_000,
            current_monotonic_ns=9_000_000_000,
        )


@pytest.mark.parametrize("field,value", [
    ("speed", "FAST"),
    ("clearance", 5.0),
    ("joint_angles", [0.0, 0.0, 0.0]),
])
def test_model_cannot_inject_arm_owned_policy(field, value):
    _context, plan, args, _registry = shared._actual_bytes_and_registry()
    document = json.loads(assemble(plan, **args))
    document["proposals"][0][field] = value
    assert _case("model_injects_arm_policy_or_authority")[
        "expected_disposition"] == "decoder_rejects"
    with pytest.raises(ModelMotionBatchV2Error, match="must contain exactly"):
        decode_model_motion_batch_v2_json(json.dumps(
            document, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def test_model_cannot_claim_controller_commands_or_hardware_authority():
    _context, plan, args, _registry = shared._actual_bytes_and_registry()
    for mutation in (
        {"controller_commands": [{"T": 102}]},
        {"hardware_access": True},
        {"physical_authority": True},
    ):
        document = json.loads(assemble(plan, **args))
        document.update(mutation)
        with pytest.raises(ModelMotionBatchV2Error, match="zero authority"):
            decode_model_motion_batch_v2_json(json.dumps(
                document, sort_keys=True, separators=(",", ":")).encode("utf-8"))
