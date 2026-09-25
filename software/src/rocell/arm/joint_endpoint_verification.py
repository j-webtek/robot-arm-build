"""Axis-independent reported endpoint checking; no command or transport access.

Reorder a selected telemetry axis into the proven wrist monitor's selected-axis
slot. All five remaining axes retain their drift checks. The wrist path itself
is unchanged, including historical schemas and exported decisions.
"""
from .wrist_endpoint_verification import verify_reported_wrist

JOINT_KEYS = ('b', 's', 'e', 't', 'r', 'g')


def verify_reported_joint(rows, *, joint, start, target, capture_issues=(), transport_clean=True, path_target=None):
    if type(joint) is not str or joint not in JOINT_KEYS:
        raise ValueError('Known telemetry joint required')
    index = JOINT_KEYS.index(joint)
    if type(start) not in (tuple,list) or len(start)!=6:
        raise ValueError('Six-joint baseline required')
    order=list(range(6))
    order[3],order[index]=order[index],order[3]
    def reordered():
        for row in rows:
            try:
                begin,end,joints=row
                if type(joints) not in (tuple,list) or len(joints)!=6:
                    raise ValueError('Invalid joint row')
                yield begin,end,[joints[i] for i in order]
            except (ValueError,TypeError,IndexError):
                # Let the shared monitor fail closed; do not discard bad rows.
                yield (0,0,[])
                return
    result=verify_reported_wrist(reordered(),start=[start[i] for i in order],
        target=target,capture_issues=capture_issues,transport_clean=transport_clean,path_target=path_target)
    result.update(schema='rocell.reported_joint_endpoint.v1',joint=joint)
    result['joint_excursion']=result.pop('wrist_excursion')
    if result['status']=='WRIST_EXCURSION':result['status']='JOINT_EXCURSION'
    return result
