"""Static-overhead semantic task to nominal geometry and sampled IK, no devices."""
import hashlib
from dataclasses import replace

from rocell.application.first_motion_contract import canonical
from rocell.application.simulate import run_scenario_ik
from rocell.application.trajectory_simulation import validate_scene_park_xy, screen_scenario_route
from rocell.application.static_simulation_context import (
    revalidate_static_simulation_context, static_simulation_context_hashes)
from rocell.motion import GeometricDryRunEngine, GeometricSimulationSettings
from rocell.models.actions import PressKey, TapPhoneTarget
from rocell.simulation.profile import (
    SimulationHardwareProfile, SimulatedArmIdentity, SimulatedCameraIdentity)
from rocell.simulation.scenario import VirtualToolCase
from rocell.typing.static_development_profiles import compile_static_development_text


def run_static_task_rehearsal(context, *, device, text, park_xy_board_mm=None, dense=False,
                              tool_length_mm=None, keyboard_translation_mm=None):
    """Rehearse at most eight characters with explicit static source identity.

    Contact points here are numerical candidates only, never controller commands.
    Reuse the established geometry engine and IK sampler without converting a
    static context into a legacy one or rewriting frozen build files.
    """
    if type(text) is not str or not 1 <= len(text) <= 8:
        raise ValueError('Static rehearsal requires one to eight characters')
    if type(dense) is not bool:
        raise TypeError('dense must be Boolean')
    if tool_length_mm is not None and (
            type(tool_length_mm) not in (int, float) or tool_length_mm not in (80.,100.,120.)):
        raise ValueError('Tool study permits only 80, 100 or 120 mm nominal cases')
    sources = dict(static_simulation_context_hashes(context))
    plan = compile_static_development_text(device, text)
    profile = SimulationHardwareProfile(
        profile_id='ROCELL-STATIC-TASK-NUMERICAL-001',
        design_revision=context.snapshot.design_revision,
        source_profile_sha256=context.bundle.source_sha256,
        source_freeze_id=context.snapshot.manifest_id,
        source_manifest_sha256=context.snapshot.manifest_sha256,
        source_camera_binding_id='static-overhead-b0477-phase1.v1',
        source_camera_manifest_sha256=sources['camera_architecture_plan'],
        source_manifest_status='STATIC_SOFTWARE_OVERLAY_NOT_PHYSICAL_FREEZE',
        source_physical_release_status='UNRELEASED',
        arm=SimulatedArmIdentity('Waveshare', 'RoArm-M3-Pro'),
        camera=SimulatedCameraIdentity('Arducam', 'B0477', 'B0477', 'USB', 'Sony IMX283'),
        assumptions=('Nominal geometry and unmeasured tool offset only',
                     'Static optical proxy is not installed calibration'))
    p = context.scenario.path_policy
    settings = GeometricSimulationSettings(
        clearance_above_highest_obstacle_mm=p.clearance_above_highest_obstacle_mm,
        segment_clearance_mm=p.segment_clearance_mm,
        hover_height_mm=p.hover_height_mm, approach_height_mm=p.approach_height_mm,
        contact_overtravel_mm=p.contact_overtravel_mm,
        park_xy_board_mm=p.park_xy_board_mm if park_xy_board_mm is None else park_xy_board_mm)
    scene,targets=context.scene,context.targets
    placement=None
    if keyboard_translation_mm is not None:
        if device!='keyboard':
            raise ValueError('Keyboard translation cannot be applied to phone tasks')
        from .keyboard_placement_overlay import translate_keyboard
        scene,targets,placement=translate_keyboard(scene,targets,keyboard_translation_mm)
    validate_scene_park_xy(scene, settings.park_xy_board_mm)
    geometry = GeometricDryRunEngine(settings).run(
            plan, context.snapshot, profile, scene, targets)
    # Change only the numerical tool-offset hypothesis, never the validated
    # context, controlled files or an installed tool calibration.
    scenario = context.scenario
    if tool_length_mm is not None:
        case = VirtualToolCase(f'explicit_nominal_tool_{tool_length_mm:g}mm', -float(tool_length_mm))
        scenario = replace(scenario, hand_tcp_to_tip_z_mm=case.hand_tcp_to_tip_z_mm,
            tool_case_id=case.case_id, tool_cases=(*scenario.tool_cases, case))
    ik = run_scenario_ik(scenario, geometry)
    route = screen_scenario_route(scenario, plan, geometry) if dense else None
    # Preserve repetitions and order: eight identical presses are eight tasks,
    # even when the endpoint-only sampler deduplicates their identical poses.
    requested_targets = [action.key_id if isinstance(action, PressKey) else action.target_id
                         for action in plan.actions if isinstance(action, (PressKey, TapPhoneTarget))]
    batch = (route or {}).get('round') or {}
    failed = next((row for row in batch.get('joint_results', []) if not row['accepted']), None)
    revalidate_static_simulation_context(context)
    report = dict(
        schema='rocell.static_task_rehearsal.v1',
        status=(route['status'] if route is not None else
                'GEOMETRY_FAILED' if not geometry.all_checks_pass else
                'SAMPLED_IK_GAPS' if not ik.all_sampled_converged else
                'SAMPLED_CHECKS_PASS_NOT_EXECUTABLE'),
        architecture='static_overhead_eye_to_hand', device=device,
        keyboard_placement_overlay=placement,
        tool_selection=dict(source='NOMINAL' if tool_length_mm is None else 'EXPLICIT_SIMULATION_OVERLAY',
            hand_tcp_to_tip_z_mm=scenario.hand_tcp_to_tip_z_mm,
            installed_tool_verified=False, frozen_geometry_modified=False),
        park_selection=dict(source='NOMINAL' if park_xy_board_mm is None else 'EXPLICIT_SIMULATION_OVERLAY',
                            xy_board_mm=list(settings.park_xy_board_mm),
                            frozen_geometry_modified=False, installed_position_verified=False),
        plan_hash=plan.plan_hash, profile_id=plan.profile_id,
        source_hashes=sources, bundle_sha256=context.bundle.source_sha256,
        hardware_profile=profile.to_dict(), geometry=geometry.to_dict(), ik=ik.to_dict(),
        dense_route=route,
        task_summary=dict(requested_target_count=len(requested_targets),
            requested_targets=requested_targets,
            evaluated_waypoint_count=batch.get('evaluated_waypoint_count'),
            planned_waypoint_count=batch.get('waypoint_count'),
            first_failure=None if failed is None else dict(
                waypoint_sequence=failed['waypoint_sequence'],
                target=failed['semantic_target'], phase=failed['phase'],
                reason=failed['failure_reason']),
            physical_input_events_observed=0,
            input_event_verification_performed=False),
        hardware_access=False, hardware_commands_generated=0,
        physical_authority=False, installed_calibration_verified=False,
        vision_observation_performed=False,
        limitations=['Synthetic target locations, not measured keys/screens',
                     'Sampled IK, not a continuous or full-arm collision check',
                     'No camera capture, physical contact or input-event verification',
                     'No controller-frame correlation or executable route'])
    return {**report, 'report_sha256': hashlib.sha256(canonical(report)).hexdigest()}
