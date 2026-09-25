"""Bounded offline interpolation screening; no transport or native requests."""
import hashlib
import math

from .first_motion_contract import canonical
from .product_ghost_controller_bridge import bridge_product_ghost
from rocell.motion.characterization_controller import _screen_reference_trace
from rocell.simulation.controller import ControllerPose, simulate_t104_trace


def screen_product_ghost(source, *, spd=0.05):
    """Regenerate the bridge from source and screen each adjacent reference leg.

    The gripper value is a constant simulation placeholder, never a hardware
    target. Roll follows the solved model, but is outside four-joint reference IK.
    Samples have interpolation indices, not measured or predicted elapsed times.
    """
    if type(spd) not in (int, float) or not math.isfinite(spd) or not .01 <= spd <= 1:
        raise ValueError('Simulation speed coefficient must be within [0.01, 1]')
    bridge = bridge_product_ghost(source)
    rows = []
    # The bridge bounds the route to 127 legs. Process one <=1024-sample
    # trace at a time and retain compact diagnostics, not all trace objects.
    for leg in bridge['legs']:
        endpoints = [bridge['samples'][leg[k]] for k in ('start_sequence', 'target_sequence')]
        poses = [ControllerPose(*s['controller_reference_xyz_pitch'],
                                s['solved_arm_joints_rad']['r'], math.pi) for s in endpoints]
        row = dict(sequence=leg['sequence'], target_key=endpoints[1]['key'],
                   target_phase=endpoints[1]['phase'], target_action_index=endpoints[1]['action_index'])
        try:
            trace = simulate_t104_trace(*poses, spd_coefficient=spd,
                                       maximum_samples=1024)
            check = _screen_reference_trace(trace)
            row.update(sample_count=len(trace.samples), reference_ik=check,
                       status=check['status'], zero_motion_delta=trace.zero_motion_delta)
        except (ValueError, OverflowError) as exc:
            row.update(status='TRACE_UNAVAILABLE', reason=str(exc), sample_count=0)
        rows.append(row)
        if row['status'] != 'REFERENCE_IK_PASS':
            break
    passed = len(rows) == len(bridge['legs']) and all(r['status'] == 'REFERENCE_IK_PASS' for r in rows)
    result = dict(schema='rocell.product_ghost_interpolation.v1',
        status='REFERENCE_INTERPOLATION_PASS' if passed else 'REFERENCE_INTERPOLATION_INCOMPLETE',
        source_bridge_sha256=bridge['report_sha256'], reference_sha256=bridge['reference_sha256'],
        spd_coefficient=spd, planned_legs=len(bridge['legs']), evaluated_legs=len(rows),
        total_samples=sum(r['sample_count'] for r in rows), legs=rows,
        hardware_access=False, motion_authorized=False, timing_available=False,
        physical_accuracy_verified=False, installed_firmware_verified=False,
        tool_clearance_verified=False, approach_from_live_pose_included=False,
        gripper_placeholder_rad=math.pi,
        limitations=['Four-joint reference IK only; roll, gripper, tool clearance and installed limits are not qualified.',
                    'Constant gripper is a simulation placeholder, not a native goal.',
                    'Sampled interpolation is not continuous collision proof or physical endpoint evidence.'])
    return dict(result, report_sha256=hashlib.sha256(canonical(result)).hexdigest())
