"""Offline stability assessment of acquisition-only native records.

Stable means stable over the sampled interval, not safe clearance, torque-held
support, current position, or permission to move. No hardware or policy writes.
"""
from .hold_record_replay import _snapshot
from .first_motion_contract import canonical


def assess_pose_observation(records, *, expected_boot, expected_id):
    result=dict(schema='rocell.pose_observation_review.v1',category='INCONCLUSIVE',
        progression_authority=False,physical_tip_accuracy_verified=False)
    try:
        if type(records) is not list or len(records)!=4:
            raise ValueError('Three snapshots and terminal required')
        terminal=records[-1]
        if canonical(terminal) != canonical(dict(schema='rocell.pose_observation_terminal.v1',
                boot_id=expected_boot,command_id=expected_id,snapshot_count=3,
                action_count=0,state='CAPTURED',reason='OBSERVATIONS_CAPTURED')):
            raise ValueError('Complete acquisition-only terminal required')
        scans=[]
        for i,record in enumerate(records[:-1]):
            if (record['schema']!='rocell.pose_observation_snapshot.v1' or
                    record['boot_id']!=expected_boot or record['command_id']!=expected_id or
                    type(record['snapshot_index']) is not int or record['snapshot_index']!=i):
                raise ValueError('Snapshot identity mismatch')
            scan=_snapshot(record)
            if scan.finished_us-scan.started_us>100000:
                raise ValueError('Scan duration exceeded')
            if scans and scan.started_us-scans[-1].finished_us<100000:
                raise ValueError('Snapshot spacing invalid')
            if any(j.position>4095 or j.goal>4095 or j.torque not in (0,1) or
                   j.moving not in (0,1) for j in scan.joints):
                raise ValueError('Register range invalid')
            scans.append(scan)
        if scans[-1].finished_us-scans[0].started_us>1000000:
            raise ValueError('Sequence duration exceeded')
        joints=[];stable=True
        for i in range(7):
            rows=[s.joints[i] for s in scans]
            span=max(j.position for j in rows)-min(j.position for j in rows)
            unchanged=all((j.goal,j.mode,j.torque)==(rows[0].goal,rows[0].mode,rows[0].torque) for j in rows)
            stable &= span<=2 and unchanged and all(j.moving==0 and j.mode==0 for j in rows)
            joints.append(dict(servo_id=11+i,position_span=span,last_position=rows[-1].position,
                last_goal=rows[-1].goal,torque=rows[-1].torque,controls_unchanged=unchanged))
        result.update(category='STABLE_SAMPLED_POSE' if stable else 'POSE_NOT_STABLE',joints=joints)
    except (ValueError,KeyError,TypeError,IndexError):
        result['reason']='INCOMPLETE_OR_INVALID_OBSERVATIONS'
    return result
