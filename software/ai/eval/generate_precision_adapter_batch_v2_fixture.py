"""Generate a synthetic contract-only ModelMotionBatchV2 from actual inference.

The broad acceptance regions in this fixture exist only to exercise the shared
serialization boundary.  They are not measured key safe regions and this file
cannot qualify motion or deployment.
"""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys

AI = Path(__file__).resolve().parents[1]
ROOT = AI.parents[1]
sys.path[:0] = [str(AI), str(AI.parent / "src"), str(AI.parent / "tests/unit")]

import test_model_motion_ingress_v2 as arm
from rocell.models import ActionPlan, Device, PressKey
from rocell_ai.precision_adapter_v2 import (
    InstalledSyntheticQualificationV0,
    PoseModelOutputV2,
    adapt_pose_model_output,
)
from rocell_ai.precision_batch_producer_v2 import (
    PlacedTargetRegionMapV2,
    produce_model_motion_batch_v2,
)
from rocell_ai.scene_observation import canonical_hash
from vision.synthetic_keyboard import catalog_for_workspace


def build() -> tuple[bytes, dict[str, object]]:
    plan = json.loads((AI / "eval/precision_adapter_localization_v1_plan.json").read_text())
    bundle_path = AI / "eval/precision_adapter_localization_v1_bundle.json"
    bundle = json.loads(bundle_path.read_text())
    qualification = bundle["qualification_candidate"]
    if qualification is None:
        raise ValueError("held-out evaluation produced no qualification candidate")
    catalog = catalog_for_workspace(ROOT)
    source = plan["contract_fixture"]
    raw = tuple(source["source_model_output"])
    image_sha256 = source["source_case"]["input_pixels_sha256"]
    now = plan["replay_epoch_ms"]
    output = PoseModelOutputV2(
        model_id=plan["model_id"],
        model_sha256=plan["model_checkpoint_sha256"],
        frame_id="precision-adapter-contract-fixture-v1",
        image_sha256=image_sha256,
        normalized_pose=tuple(float(value) for value in raw),
        evaluated_at_epoch_ms=now,
        observation_confidence=plan["fixture_observation_confidence"],
    )
    installation = InstalledSyntheticQualificationV0(
        qualification, bundle["bundle_sha256"]
    )
    target_order = ("H", "H", "1", "PERIOD")
    adapted = adapt_pose_model_output(
        ROOT,
        output,
        domain_id=plan["domain_id"],
        required_target_ids=target_order,
        trusted_qualifications={qualification["qualification_sha256"]: installation},
        expected_domain_id=plan["domain_id"],
        now_epoch_ms=now,
    )
    context = arm.load_simulation_context(arm.WORKSPACE, arm.MANIFEST)
    fixture = arm._batch(context)
    prediction = adapted.precision_observation["prediction"]
    radius = qualification["error_bound_mm"]
    envelope = radius + 1.0
    regions = {}
    for target_id in dict.fromkeys(target_order):
        x, y, _ = prediction["targets"][target_id]["center_board_mm"]
        regions[target_id] = (x - envelope, y - envelope, x + envelope, y + envelope)
    placement_sha256 = canonical_hash(
        {"scope": "SYNTHETIC_CONTRACT_FIXTURE_ONLY", "regions": regions}
    )
    placed = PlacedTargetRegionMapV2(catalog.content_sha256, placement_sha256, regions)
    geometry = replace(
        fixture.geometry,
        placement_observation_sha256=placement_sha256,
        target_catalog_sha256=catalog.content_sha256,
    )
    evidence = replace(
        fixture.evidence,
        frame_id=output.frame_id,
        image_sha256=image_sha256,
        model_id=output.model_id,
        model_sha256=output.model_sha256,
        precision_observation_sha256=adapted.precision_observation["observation_sha256"],
        captured_at_epoch_ms=now - 100,
        evaluated_at_epoch_ms=now,
        expires_at_epoch_ms=now + 1_000,
    )
    action_plan = ActionPlan.from_text(
        device=Device.KEYBOARD,
        profile_id="keyboard-development-v1",
        text="hh1.",
        actions=tuple(PressKey(target) for target in target_order),
        required_calibrations=("keyboard_pose", "keyboard_tcp"),
    )
    payload = produce_model_motion_batch_v2(
        action_plan,
        adapter_result=adapted,
        batch_id="precision-adapter-contract-fixture-v2",
        request_id="precision-adapter-contract-request-v2",
        capability=fixture.capability,
        geometry=geometry,
        evidence=evidence,
        placed_targets=placed,
        now_epoch_ms=now,
    )
    if payload is None:
        raise ValueError("contract fixture unexpectedly abstained")
    retained_payload = payload + b"\n"
    metadata = {
        "schema": "rocell.ai_precision_adapter_contract_fixture.v1",
        "scope": "SYNTHETIC_CONTRACT_FIXTURE_ONLY",
        "source_model_output": [float(value) for value in raw],
        "source_case": source["source_case"],
        "precision_observation_sha256": adapted.precision_observation["observation_sha256"],
        "evaluation_bundle_sha256": bundle["bundle_sha256"],
        "batch_file_sha256": hashlib.sha256(retained_payload).hexdigest(),
        "requested_target_order": list(target_order),
        "qualification_installed_for_deployment": False,
        "physical_deployment_qualified": False,
        "hardware_writes": 0,
        "physical_movements": 0,
        "limitations": [
            "The source pose is actual frozen-model inference on a synthetic renderer case.",
            "Mainline retains the exact model-output record and image hash; the research checkpoint remains external by digest.",
            "The pose model has no calibrated confidence head; 0.99 is an explicit contract-fixture input.",
            "Acceptance regions are broad synthetic envelopes, not measured key safe regions.",
            "The held-out bound crosses ordinary key safe regions and therefore cannot authorize them.",
            "The qualification candidate is installed only in memory for this contract fixture.",
            "The batch has zero controller commands, hardware access, and physical authority."
        ]
    }
    return retained_payload, metadata


def main() -> None:
    payload, metadata = build()
    output_path = AI / "eval/precision_adapter_batch_v2_contract_fixture.json"
    metadata_path = AI / "eval/precision_adapter_batch_v2_contract_fixture_metadata.json"
    if output_path.exists() or metadata_path.exists():
        if not output_path.is_file() or not metadata_path.is_file():
            raise FileExistsError("partial precision adapter contract fixture")
        if output_path.read_bytes() != payload:
            raise ValueError("retained precision adapter batch differs")
        retained_metadata = json.loads(metadata_path.read_text())
        if retained_metadata != metadata:
            raise ValueError("retained precision adapter metadata differs")
    else:
        output_path.write_bytes(payload)
        metadata_path.write_text(
            json.dumps(metadata, indent=2, allow_nan=False) + "\n")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
