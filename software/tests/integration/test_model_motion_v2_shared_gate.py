"""Actual AI v2 bytes through the consumer-owned arm registry; zero hardware."""

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
from rocell_ai.batch_emitter_v2 import TargetObservationV2, assemble  # noqa: E402
from rocell.application.model_motion_registry_v2 import (  # noqa: E402
    ingest_with_trusted_registry_v2, revalidate_with_trusted_registry_v2)


def _actual_bytes_and_registry():
    context = arm.load_simulation_context(arm.WORKSPACE, arm.MANIFEST)
    plan = arm.ActionPlan.from_text(device=arm.Device.KEYBOARD,
        profile_id="keyboard-development-v1", text="hhi",
        actions=(arm.PressKey("H"), arm.PressKey("H"), arm.PressKey("I")),
        required_calibrations=("keyboard_pose", "keyboard_tcp"))
    fixture = arm._batch(context)
    args = dict(batch_id="shared-gate-v2", request_id="shared-request-v2",
        capability=fixture.capability, geometry=fixture.geometry,
        evidence=fixture.evidence, uncertainty=fixture.uncertainty,
        observations={proposal.target_id: TargetObservationV2(
            proposal.target, 0.93) for proposal in fixture.proposals})
    return context, plan, args, arm._registry(context)


def test_actual_ai_bytes_pass_registry_ingress_and_preplanner_gate():
    context, plan, args, registry = _actual_bytes_and_registry()
    payload = assemble(plan, **args)
    schema_root = ROOT / "software/ai/schemas"
    batch_schema = json.loads((schema_root / "model_motion_batch_v2.schema.json").read_text())
    proposal_schema = json.loads((schema_root / "model_motion_proposal_v2.schema.json").read_text())
    inline_proposal = {key: value for key, value in proposal_schema.items()
                       if key not in {"$schema", "$id", "$defs"}}
    batch_schema["properties"]["proposals"]["items"] = inline_proposal
    jsonschema.Draft202012Validator(batch_schema).validate(json.loads(payload))
    batch = arm.decode_model_motion_batch_v2_json(payload)
    ingress = ingest_with_trusted_registry_v2(batch, plan, context,
        registry=registry, current_time_epoch_ms=arm.T0 + 3_000,
        current_monotonic_ns=9_000_000_000)
    gate = revalidate_with_trusted_registry_v2(ingress, registry=registry,
        current_monotonic_ns=10_000_000_000)
    assert ingress["ordered_target_ids"] == ["H", "H", "I"]
    assert gate["status"] == "FRESH_FOR_DETERMINISTIC_PLANNING"
    assert ingress["controller_commands"] == gate["controller_commands"] == []
    assert ingress["hardware_access"] is gate["hardware_access"] is False
    assert ingress["physical_authority"] is gate["physical_authority"] is False


@pytest.mark.parametrize("mutation", [
    "capability", "camera", "clock", "lease", "placement", "target_map",
    "qualification", "domain", "uncertainty", "edge"])
def test_actual_ai_bytes_fail_closed_for_each_trust_or_geometry_mutation(mutation):
    context, plan, args, registry = _actual_bytes_and_registry()
    if mutation == "capability":
        args["capability"] = replace(args["capability"], profile_sha256="1" * 64)
    elif mutation == "camera":
        args["evidence"] = replace(args["evidence"], camera_identity_sha256="1" * 64)
    elif mutation == "clock":
        args["evidence"] = replace(args["evidence"], capture_clock_domain_id="other-clock")
    elif mutation == "lease":
        args["evidence"] = replace(args["evidence"], scene_lease_sha256="1" * 64)
    elif mutation == "placement":
        args["geometry"] = replace(args["geometry"],
                                   placement_observation_sha256="1" * 64)
    elif mutation == "target_map":
        args["geometry"] = replace(args["geometry"], target_catalog_sha256="1" * 64)
    elif mutation == "qualification":
        args["uncertainty"] = replace(args["uncertainty"],
                                      qualification_sha256="1" * 64)
    elif mutation == "domain":
        args["uncertainty"] = replace(args["uncertainty"], domain_id="other-domain")
    elif mutation == "uncertainty":
        args["uncertainty"] = replace(args["uncertainty"], error_bound_mm=1.1)
    elif mutation == "edge":
        target = context.targets.resolve("keyboard", "H")
        left = target.safe_rectangle_board_mm[0]
        args["observations"]["H"] = TargetObservationV2(
            arm.Point3Mm("board", left + 1.1, target.center.y, target.center.z), 0.93)
    payload = assemble(plan, **args)
    batch = arm.decode_model_motion_batch_v2_json(payload)
    with pytest.raises(ValueError):
        ingest_with_trusted_registry_v2(batch, plan, context, registry=registry,
            current_time_epoch_ms=arm.T0 + 3_000,
            current_monotonic_ns=9_000_000_000)


def test_actual_ai_bytes_expire_at_exact_deadline_and_never_reach_commands():
    context, plan, args, registry = _actual_bytes_and_registry()
    batch = arm.decode_model_motion_batch_v2_json(assemble(plan, **args))
    with pytest.raises(ValueError, match="future-dated or expired"):
        ingest_with_trusted_registry_v2(batch, plan, context, registry=registry,
            current_time_epoch_ms=args["evidence"].expires_at_epoch_ms,
            current_monotonic_ns=9_000_000_000)
