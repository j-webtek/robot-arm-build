"""Finite synthetic preload/enable rehearsal, never a hardware runner.

Group enable is an explicit unverified model assumption, NOT an implemented
atomic servo operation. No callbacks, sockets, serial, retries or torque-off.
"""
from copy import deepcopy


FAULTS=('NONE','PRELOAD_ACK_LOST','PRELOAD_READBACK_WRONG','PRELOAD_ENABLED_TORQUE',
        'DRIFT_BEFORE_ENABLE','PARTIAL_SHOULDER_ENABLE','ENABLE_ACK_LOST',
        'NEIGHBOR_DRIFT','EXPORT_FAILED')


def rehearse(positions, goals, torques, *, fault='NONE'):
    for values,high in ((positions,4095),(goals,4095),(torques,1)):
        if type(values) not in (list,tuple) or len(values)!=7 or any(
                type(v) is not int or not 0<=v<=high for v in values):
            raise ValueError('Seven explicit register values required')
    if fault not in FAULTS:raise ValueError('Named simulated fault required')
    if any(t and abs(p-g)>2 for p,g,t in zip(positions,goals,torques)):
        raise ValueError('Already enabled joint not tracking; no rehearsal writes')
    state=dict(positions=list(positions),goals=list(goals),torques=list(torques))
    targets=list(positions); events=[]; actions=[]
    report=dict(schema='rocell.upright_initialization_sim.v1',origin='SIMULATION',
        status='STOPPED',reason=None,initial=deepcopy(state),targets=targets,
        actions=actions,events=events,motion_authorized=False,whole_arm_ready=False,
        hardware_access=False,contact_release_simulated=False,dynamics_simulated=False,
        group_enable_assumption='UNVERIFIED_ABSTRACT_OPERATION',retry_allowed=False,
        shoulder_pair_residual_counts=positions[1]+positions[2]-4094)
    def finish(reason,success=False):
        report.update(status='MODEL_COMPLETED' if success else 'STOPPED',reason=reason,
            final=deepcopy(state))
        return report
    def snapshot(stage):events.append(dict(stage=stage,registers=deepcopy(state)))
    snapshot('BASELINE')
    # Preload every passive target before ANY enable, preserving enabled joints.
    for index in range(7):
        if torques[index]:continue
        payload=bytes([1])+targets[index].to_bytes(2,'little')+bytes([0,0,20,0])
        actions.append(dict(kind='PRELOAD',servo_ids=[11+index],address=41,payload_hex=payload.hex()))
        state['goals'][index]=targets[index]
        if fault=='PRELOAD_ACK_LOST':return finish('UNCERTAIN_PRELOAD_DELIVERY')
        if fault=='PRELOAD_READBACK_WRONG':state['goals'][index]=0
        if fault=='PRELOAD_ENABLED_TORQUE':state['torques'][index]=1
        snapshot('PRELOAD_READBACK')
        if state['goals'][index]!=targets[index] or state['torques']!=list(torques):
            return finish('PRELOAD_READBACK_MISMATCH')
    if fault=='DRIFT_BEFORE_ENABLE':state['positions'][1]+=3
    snapshot('BEFORE_ENABLE')
    if any(abs(a-b)>2 for a,b in zip(state['positions'],targets)):
        return finish('POSE_CHANGED_BEFORE_ENABLE')
    # This hypothesizes a grouped operation; native bus semantics/skew and
    # mechanical loading must be reviewed before selecting an implementation.
    for group in ((12,13),(11,),(15,),(16,),(17,),(14,)):
        passive=[sid for sid in group if state['torques'][sid-11]==0]
        if not passive:continue
        if any(state['goals'][sid-11]!=targets[sid-11] for sid in passive):
            return finish('STALE_ENABLE_TARGET')
        actions.append(dict(kind='ABSTRACT_GROUP_ENABLE',servo_ids=passive))
        for sid in passive:state['torques'][sid-11]=1
        if fault=='PARTIAL_SHOULDER_ENABLE' and group==(12,13):state['torques'][2]=0
        if fault=='ENABLE_ACK_LOST':return finish('UNCERTAIN_ENABLE_DELIVERY')
        if fault=='NEIGHBOR_DRIFT':state['positions'][3]+=3
        snapshot('ENABLE_READBACK')
        if any(state['torques'][sid-11]!=1 for sid in passive):return finish('PARTIAL_ENABLE')
        if any(abs(a-b)>2 for a,b in zip(state['positions'],targets)):
            return finish('UNEXPECTED_JOINT_MOTION')
    snapshot('SETTLED_MODEL')
    if fault=='EXPORT_FAILED':return finish('EXPORT_FAILED')
    return finish('SYNTHETIC_INITIALIZATION_ONLY',success=True)
