"""Offline ordering comparison, not collision validation or live admission.

Samples the pinned configured end-edge model at no more than one encoder count
per selected axis. Excludes link volumes, gravity, contact forces and cable paths.
"""
import itertools
import math
from .firmware_reference import forward, REFERENCE_SHA256


def compare_orders(positions):
    if type(positions) not in (list,tuple) or len(positions)!=7 or any(
            type(v) is not int or not 0<=v<=4095 for v in positions):
        raise ValueError('Seven valid servo counts required')
    step=2*math.pi/4096
    start=[(2048-positions[0])*step,(positions[1]-2048)*step,
           (positions[3]-1024)*step,(positions[4]-2048)*step]
    target=[start[0],0,math.pi/2,0]  # Preserve base direction, not a home command.
    origin=forward(*start); names={1:'shoulder',2:'elbow',3:'wrist_pitch'}
    comparisons=[]
    for order in itertools.permutations((1,2,3)):
        pose=start[:];minimum=0.;first=None;samples=0
        for axis in order:
            initial=pose[axis]
            count=max(1,math.ceil(abs(target[axis]-initial)/step))
            for index in range(1,count+1):
                pose[axis]=initial+(target[axis]-initial)*index/count
                dz=forward(*pose)[2]-origin[2]
                minimum=min(minimum,dz);samples+=1
                if first is None:first=dz
        comparisons.append(dict(order=[names[i] for i in order],samples=samples,
            first_sample_delta_z_mm=first,minimum_sampled_delta_z_mm=minimum))
    return dict(schema='rocell.upright_recovery_preview.v1',basis='NOMINAL_REFERENCE_ONLY',
        source_sha256=REFERENCE_SHA256,positions=list(positions),
        start_reference_angles_deg=[math.degrees(v) for v in start],
        target_reference_angles_deg=[math.degrees(v) for v in target],
        start_reference_endpoint=list(origin),target_reference_endpoint=list(forward(*target)),
        shoulder_pair_count_sum=positions[1]+positions[2],reference_pair_count_sum=4094,
        shoulder_pair_residual_counts=positions[1]+positions[2]-4094,
        orders=comparisons,physical_clearance_verified=False,dynamics_simulated=False,
        physical_pose_verified=False,motion_authorized=False,
        limitations=['Configured end edge, not measured lowest gripper point',
            'No board transform, link volumes, cable model or contact forces',
            'Other joints assumed fixed; passive joints may not remain fixed',
            'Shoulder follower alignment is not established by driving-servo FK'])
