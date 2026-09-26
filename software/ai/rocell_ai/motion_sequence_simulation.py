"""Bounded coordinate-sequence rehearsal; never controller commands."""
from __future__ import annotations

from dataclasses import replace
import math
from pathlib import Path

from rocell.application.static_simulation_context import load_static_simulation_context, revalidate_static_simulation_context
from rocell.application.robot_layout_overlay import promoted_rank1_robot_layout
from rocell.application.simulate import run_scenario_ik
from rocell.application.trajectory_simulation import screen_scenario_route, validate_scene_park_xy
from rocell.models import ActionPlan, Device, PressKey, Point3Mm
from rocell.motion import GeometricDryRunEngine, GeometricSimulationSettings
from rocell.targets import TargetRegion
from rocell.typing.static_development_profiles import static_development_keyboard_profile

from .motion_assurance import build
from .model_motion_simulation import _simulation_profile
from .scene_observation import canonical_hash


def run(values: list[dict], *, workspace: Path) -> dict:
    if not isinstance(values, list) or not 1 <= len(values) <= 8:
        raise ValueError('Sequence requires one to eight proposals')
    bundles = [build(value, workspace=workspace) for value in values]
    candidates = [bundle['candidate'] for bundle in bundles]
    if any(c['device'] != 'keyboard' or c['interaction'] != 'CONTACT' or c['speed_class'] != 'SLOW' for c in candidates):
        raise ValueError('Sequence supports keyboard CONTACT with SLOW only')
    clearances = [value['approach_clearance_mm'] for value in values]
    if len(set(clearances)) != 1 or clearances[0] not in (12.0, 25.0, 40.0):
        raise ValueError('Sequence requires one common study clearance: 12, 25, or 40 mm')
    context = load_static_simulation_context(workspace)
    scenario, layout = promoted_rank1_robot_layout(context, workspace / 'software/config/virtual_commissioning_profile.json')
    targets = dict(context.targets.keyboard_targets)
    seen = {}
    for candidate in candidates:
        key = candidate['target_id']
        point = candidate['proposed_surface_target_board_mm']
        xyz = (point['x'], point['y'], point['z'])
        if key in seen and seen[key] != xyz:
            raise ValueError('Repeated target coordinates must agree within this sequence')
        seen[key] = xyz
        original = targets[key]
        targets[key] = TargetRegion('keyboard', key, Point3Mm('board', *xyz), original.half_extent_x_mm, original.half_extent_y_mm)
    overlay = {'base_catalog_sha256': context.targets.content_sha256,
               'candidate_sha256_in_order': [c['candidate_sha256'] for c in candidates],
               'centers_board_mm': seen, 'simulation_only': True}
    catalog = replace(context.targets, keyboard_targets=targets, content_sha256=canonical_hash(overlay))
    profile = static_development_keyboard_profile()
    plan = ActionPlan.from_text(device=Device.KEYBOARD, profile_id=profile.profile_id,
        text=canonical_hash(values), actions=tuple(PressKey(c['target_id']) for c in candidates),
        required_calibrations=profile.required_calibrations)
    path = scenario.path_policy
    settings = GeometricSimulationSettings(
        clearance_above_highest_obstacle_mm=path.clearance_above_highest_obstacle_mm,
        segment_clearance_mm=path.segment_clearance_mm, hover_height_mm=clearances[0],
        approach_height_mm=path.approach_height_mm, contact_overtravel_mm=path.contact_overtravel_mm,
        park_xy_board_mm=(290.0, 10.0))
    validate_scene_park_xy(context.scene, settings.park_xy_board_mm)
    geometry = GeometricDryRunEngine(settings).run(plan, context.snapshot, _simulation_profile(context), context.scene, catalog)
    ik = run_scenario_ik(scenario, geometry)
    route = screen_scenario_route(scenario, plan, geometry)
    # This schedule is arithmetic on the geometric path, with explicit synthetic
    # delays. It is not a controller timing or servo-dynamics prediction.
    time_s = 0.0
    previous = None
    events = []
    for step in geometry.steps:
        point = step.tip_point_board
        if point is not None:
            xyz = (point.x, point.y, point.z)
            if previous is not None:
                time_s += math.dist(previous, xyz) / 10.0
            previous = xyz
        if step.phase.value == 'CONTACT':
            events.append({'action_index': step.action_index, 'target': step.semantic_target,
                           'planned_contact_time_s': time_s})
            time_s += 0.1
        if step.phase.value in ('VERIFY', 'VISION_CORRECT'):
            time_s += 0.2
    revalidate_static_simulation_context(context)
    core = {
        'schema': 'rocell.ai_model_motion_sequence_simulation.v0',
        'proposals': values, 'assurance_bundle_sha256_in_order': [b['bundle_sha256'] for b in bundles],
        'target_overlay': overlay, 'target_overlay_sha256': catalog.content_sha256,
        'static_context_sha256': context.bundle.source_sha256, 'layout_overlay': layout,
        'park_xy_board_mm': [290.0, 10.0], 'hover_clearance_mm': clearances[0],
        'requested_targets': [c['target_id'] for c in candidates], 'plan_hash': plan.plan_hash,
        'geometry': geometry.to_dict(), 'sampled_ik_all_converged': ik.all_sampled_converged,
        'dense_route': route,
        'cadence_hypothesis': {'cartesian_speed_mm_s': 10.0, 'contact_dwell_s': 0.1,
            'vision_or_verify_delay_s': 0.2, 'planned_duration_s': time_s, 'contact_events': events,
            'dynamics_verified': False, 'input_events_observed': 0},
        'physical_execution_authorized': False, 'hardware_commands': [], 'hardware_writes': 0,
        'limitations': ['Synthetic proposals and unmeasured base/tool/park geometry',
            'Common clearance is applied to hover and retract; local approach and overtravel use static policy',
            'SLOW maps only to an illustrative constant 10 mm/s schedule; acceleration and servo dynamics are unmodeled',
            'Vision and verification steps are placeholders; no camera or input event was observed',
            'A planned contact event does not mean the dense route reached it; inspect route status',
            'Sampled tip route checks do not prove continuous full-arm collision clearance'],
    }
    return {**core, 'sequence_sha256': canonical_hash(core)}
