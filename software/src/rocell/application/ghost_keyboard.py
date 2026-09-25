"""Camera-free named-key route preview using the existing semantic compiler.

This is a nominal geometry overlay, not an executable controller request. Every
stroke ends at an imaginary plane; no real input or physical clearance is inferred.
"""
import hashlib
import json
import math
from rocell.models.profiles import KeyboardProfile
from rocell.typing.keyboard_compiler import KeyboardCompiler
from rocell.kinematics.firmware_reference import inverse, forward, REFERENCE_SHA256
from .first_motion_contract import canonical


def rehearse_ghost_keyboard(workspace, text='aba'):
    if type(text) is not str or not 1 <= len(text) <= 8 or any(c not in 'abc' for c in text):
        raise ValueError('Use one to eight lowercase ghost keys a, b or c')
    path=workspace/'software/config/ghost_keyboard_v1.json'
    raw=path.read_bytes()
    layout=json.loads(raw)
    # The first version is intentionally fixed, not an unchecked configuration
    # loader for live coordinates. Later layout versions need explicit validation.
    expected=dict(schema='rocell.ghost_keyboard_layout.v1',layout_id='ghost-three-key-row-v1',
        units='mm',frame='GHOST_KEYBOARD',controller_reference='R_ctrl',
        transform_basis='NOMINAL_SIMULATION_ONLY',origin_controller_mm=[340,0,220],
        yaw_rad=math.pi/2,controller_pitch_rad=0,key_pitch_mm=19,key_width_mm=15,
        keys={'A':[0,0],'B':[19,0],'C':[38,0]},travel_height_mm=10,
        hover_height_mm=4,virtual_surface_z_mm=0,sample_spacing_mm=2,
        installed_tool_offset_applied=False)
    if canonical(layout)!=canonical(expected):
        raise ValueError('Ghost layout differs from the supported nominal version')
    profile=KeyboardProfile('simulation/ghost-three-key-row-v1',
        {c:(c.upper(),) for c in 'abc'},required_calibrations=())
    plan=KeyboardCompiler().compile(text,profile)
    def pose(x,y,z):
        yaw=layout['yaw_rad']; origin=layout['origin_controller_mm']
        return [origin[0]+x*math.cos(yaw)-y*math.sin(yaw),
                origin[1]+x*math.sin(yaw)+y*math.cos(yaw),origin[2]+z,
                layout['controller_pitch_rad']]
    current=pose(0,0,layout['travel_height_mm']); legs=[]; failure=None
    bounds=((-math.pi,math.pi),(-math.pi/2,math.pi/2),(0,2.95),(-math.pi/2,math.pi/2))
    for action_index,action in enumerate(plan.actions):
        x,y=layout['keys'][action.key_id]
        for phase,z in (('travel',10),('hover',4),('virtual_downstroke',0),('retract',10)):
            target=pose(x,y,z)
            count=max(1,math.ceil(math.dist(current[:3],target[:3])/layout['sample_spacing_mm']))
            samples=[]
            for i in range(count+1):
                p=[a+(b-a)*i/count for a,b in zip(current,target)]
                try:
                    joints=inverse(*p); recovered=forward(*joints)
                    accepted=(all(lo<=v<=hi for v,(lo,hi) in zip(joints,bounds))
                        and math.dist(p[:3],recovered[:3])<1e-6
                        and abs(p[3]-recovered[3])<1e-8)
                    reason=None if accepted else 'JOINT_LIMIT_OR_ROUNDTRIP'
                except ValueError:
                    joints=None; accepted=False; reason='IK_DOMAIN'
                samples.append(dict(pose=p,joints_rad=joints,accepted=accepted))
                if not accepted:
                    failure=dict(action_index=action_index,key=action.key_id,phase=phase,reason=reason)
                    break
            legs.append(dict(sequence=len(legs),action_index=action_index,key=action.key_id,
                phase=phase,start=current,target=target,samples=samples))
            if failure: break
            current=target
        if failure: break
    report=dict(schema='rocell.ghost_keyboard_rehearsal.v1',
        status='SAMPLED_GHOST_ROUTE_PASS' if failure is None else 'GHOST_ROUTE_REJECTED',
        layout=layout,layout_sha256=hashlib.sha256(raw).hexdigest(),plan_hash=plan.plan_hash,
        reference_sha256=REFERENCE_SHA256,requested_keys=[a.key_id for a in plan.actions],
        nominal_start_pose=pose(0,0,10),legs=legs,first_failure=failure,
        hardware_access=False,motion_authorized=False,hardware_commands_generated=0,
        camera_required=False,physical_input_events_observed=0,
        physical_accuracy_verified=False,full_arm_clearance_verified=False,
        timing_simulated=False,endpoint_feedback_simulated=False,
        limitations=['Nominal controller-frame placement; not a measured board transform.',
            'Sampled reference IK only; installed firmware and full-arm collisions unverified.',
            'No controller dispatch, endpoint dynamics, real keypress or installed stylus offset.'])
    return dict(report,report_sha256=hashlib.sha256(canonical(report)).hexdigest())
