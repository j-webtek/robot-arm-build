from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import jsonschema
import pytest

from rocell.application.phase_local_contact_envelope_gate import (
    PhaseLocalContactAllowance,
    PhaseLocalContactEnvelopeGateError,
    bind_phase_local_contact_envelope_gate,
)
from rocell.application.context import load_simulation_context
from rocell.application.trajectory_execution_envelope_v2 import (
    bind_trajectory_execution_envelope_v2,
)
from rocell.application.conservative_segment_sweep_qualification import (
    qualify_conservative_segment_sweeps,
)
from rocell.application.bounded_segment_collision_qualification import (
    build_bounded_joint_sample_plan,
)
from rocell.simulation.collision import (
    CollisionExclusionEvidenceState,
    CollisionExclusionScope,
    CollisionGeometryContract,
    CollisionPairExclusion,
)

import test_fk_collision_pose_adapter as collision
import test_trajectory_execution_envelope_v2 as envelope_v2


WORKSPACE = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def context():
    return load_simulation_context(
        WORKSPACE, WORKSPACE / "software/config/system_manifest.json"
    )


def _accepted_profile(context):
    source = collision.profile(context)
    exclusions = tuple(
        CollisionPairExclusion(
            item.first_body_id,
            item.second_body_id,
            CollisionExclusionScope.ENGINEERING_GLOBAL,
            CollisionExclusionEvidenceState.ACCEPTED_ENGINEERING,
            "reviewed installed adjacent-body engineering exclusion",
            "accepted engineering review fixture",
        )
        for item in source.contract.pair_exclusions
    )
    contract = CollisionGeometryContract(
        source.contract.contract_id,
        source.contract.root_frame,
        source.contract.requirements,
        source.contract.bodies,
        exclusions,
    )
    return replace(source, contract=contract)


def _contact_route(context, measured, installed, target_id):
    route = collision.trajectory(context, measured, installed, base_offset=0.001)
    unsigned = dict(route)
    unsigned.pop("trajectory_screening_sha256")
    unsigned["waypoints"] = [
        {
            **unsigned["waypoints"][0],
            "phase": "CONTACT",
            "semantic_target": target_id,
        }
    ]
    return {
        **unsigned,
        "trajectory_screening_sha256": collision.digest(unsigned),
    }


def _qualified_inputs(context):
    batch, planner = envelope_v2._planner_inputs()
    planner = envelope_v2._synthetic_ready(planner)
    proposal = batch.proposals[0]
    measured = collision.snapshot(context)
    installed = _accepted_profile(context)
    route = _contact_route(context, measured, installed, proposal.target_id)
    plan = build_bounded_joint_sample_plan(route)
    sweep = qualify_conservative_segment_sweeps(
        context,
        measured,
        installed,
        route,
        collision.bindings(),
        collision.segment_cables(plan),
        collision.sweep_envelopes(plan),
    )
    inner = replace(
        envelope_v2._inner(
            batch.batch_sha256,
            planner["derived_v1_surrogate_sha256"],
            planner["measured_planner_gate_sha256"],
        ),
        trajectory_screening_sha256=route["trajectory_screening_sha256"],
    )
    envelope = bind_trajectory_execution_envelope_v2(
        batch, proposal, planner, inner
    )
    allowance = PhaseLocalContactAllowance(
        "keyboard-single-contact-v1",
        proposal.target_id,
        "attachment:contact_tool",
        "workcell:keyboard",
        "a" * 64,
        "accepted keyboard contact engineering review fixture",
    )
    return proposal, installed, route, sweep, envelope, allowance


def test_contact_gate_binds_exact_policy_sweep_and_envelope(context) -> None:
    proposal, installed, route, sweep, envelope, allowance = _qualified_inputs(
        context
    )
    assert sweep["all_pair_exclusions_physically_accepted"] is True
    assert sweep["continuous_collision_proven_for_bound_geometry"] is True

    report = bind_phase_local_contact_envelope_gate(
        proposal,
        installed,
        route,
        sweep,
        envelope,
        contact_allowance=allowance,
    )

    assert report["status"] == "COLLISION_POLICY_BOUND_NO_WRITE_ENVELOPE"
    assert report["phase_local_contact_allowance"]["phase"] == "CONTACT"
    assert report["phase_local_contact_allowance"]["global_exclusion"] is False
    assert report["controller_commands"] == report["wire_commands"] == []
    assert report["physical_authority"] is report["contact_authority"] is False
    schema = json.loads(
        (
            WORKSPACE
            / "software/ai/schemas/phase_local_contact_envelope_gate_v1.schema.json"
        ).read_text(encoding="utf-8")
    )
    jsonschema.Draft202012Validator(schema).validate(report)


def test_contact_gate_rejects_diagnostic_global_exclusions(context) -> None:
    proposal, _, route, sweep, envelope, allowance = _qualified_inputs(context)
    diagnostic = collision.profile(context)
    with pytest.raises(
        PhaseLocalContactEnvelopeGateError, match="accepted engineering"
    ):
        bind_phase_local_contact_envelope_gate(
            proposal,
            diagnostic,
            route,
            {**sweep, "installed_collision_profile_sha256": diagnostic.content_sha256},
            envelope,
            contact_allowance=allowance,
        )


def test_contact_gate_rejects_missing_or_crossed_contact_policy(context) -> None:
    proposal, installed, route, sweep, envelope, allowance = _qualified_inputs(
        context
    )
    with pytest.raises(
        PhaseLocalContactEnvelopeGateError, match="requires a phase-local"
    ):
        bind_phase_local_contact_envelope_gate(
            proposal, installed, route, sweep, envelope
        )
    crossed = replace(allowance, target_id="keyboard:other")
    with pytest.raises(
        PhaseLocalContactEnvelopeGateError, match="target differs"
    ):
        bind_phase_local_contact_envelope_gate(
            proposal,
            installed,
            route,
            sweep,
            envelope,
            contact_allowance=crossed,
        )


def test_contact_gate_rejects_tampered_sweep_lineage(context) -> None:
    proposal, installed, route, sweep, envelope, allowance = _qualified_inputs(
        context
    )
    tampered = dict(sweep)
    tampered["trajectory_screening_sha256"] = "f" * 64
    with pytest.raises(PhaseLocalContactEnvelopeGateError, match="content hash"):
        bind_phase_local_contact_envelope_gate(
            proposal,
            installed,
            route,
            tampered,
            envelope,
            contact_allowance=allowance,
        )
