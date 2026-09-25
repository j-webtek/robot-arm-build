"""Independent count-space replay of native leg fixtures; never grants authority.

An independently supplied plan fixes identity, target, tolerance and policy hash.
This is SIMULATION until authenticated runtime/transport integration is reviewed.
Controller terminal labels are checked against reconstructed raw observations.
"""
import hashlib
from pathlib import Path

from .first_motion_contract import canonical
from .hold_bound_replay import _policy
from .hold_record_replay import _snapshot
from .servo_diagnostic_contract import _identifier, _integer
from .product_ghost_export_review import _read
from .wizard_diagnostic_export import WizardDiagnosticExporter


def assess_simulated_held_leg(records, *, plan, policy):
    result = dict(schema='rocell.held_leg_assessment.v1', origin='SIMULATION',
                  category='INCONCLUSIVE', progression_authority=False,
                  provenance_verified=False, wire_observation_verified=False,
                  physical_tip_accuracy_verified=False)
    try:
        _policy(policy)
        if (type(plan) is not dict or set(plan) != {'schema', 'boot_id', 'command_id',
                'target_count', 'tolerance_counts', 'policy_sha256'} or
                plan['schema'] != 'rocell.held_leg_plan.v1' or
                plan['policy_sha256'] != hashlib.sha256(canonical(policy)).hexdigest()):
            raise ValueError('Invalid independent plan')
        boot, command = _identifier(plan['boot_id']), _identifier(plan['command_id'])
        target, tolerance = plan['target_count'], plan['tolerance_counts']
        _integer(target, 0, 4095); _integer(tolerance, 0, 2)
        if not policy['joints'][3][0] <= target <= policy['joints'][3][1]:
            raise ValueError('Target outside envelope')
        if type(records) is not list or not 7 <= len(records) <= 34:
            raise ValueError('Incomplete or oversized leg')
        scans, action, terminal = [], None, None
        for index, record in enumerate(records):
            if record['boot_id'] != boot or record['command_id'] != command:
                raise ValueError('Mixed identity')
            schema = record['schema']
            if schema == 'rocell.held_leg_snapshot.v1':
                _integer(record['snapshot_index'], 0, 31)
                if record['snapshot_index'] != len(scans) or (len(scans)>=3 and action is None):
                    raise ValueError('Scan order')
                scans.append(_snapshot(record, policy['pair_us']))
            elif schema == 'rocell.hold_action.v1':
                fields = {'schema', 'boot_id', 'command_id', 'action_index', 'servo_id',
                    'address', 'width', 'payload_hex', 'payload_source', 'started_us',
                    'finished_us', 'library_return', 'device_error', 'ack_policy', 'dispatch_status'}
                if set(record) != fields or action is not None or len(scans)!=3:
                    raise ValueError('Action order or fields')
                for field in ('action_index','servo_id','address','width','started_us',
                              'finished_us','library_return','device_error'):
                    _integer(record[field])
                payload = bytes([policy['acceleration']])+target.to_bytes(2,'little')+b'\0\0'+policy['speed'].to_bytes(2,'little')
                if (record['action_index']!=0 or record['servo_id']!=14 or record['address']!=41 or
                        record['width']!=7 or record['payload_hex']!=payload.hex() or
                        record['payload_source']!='PINNED_LIBRARY_ARGUMENT_ENCODING' or
                        record['ack_policy']!='ENABLED' or record['library_return']!=1 or
                        record['device_error']!=0 or record['dispatch_status']!='SUCCEEDED'):
                    raise ValueError('Wrong or uncertain command')
                action=record
            elif schema == 'rocell.held_leg_terminal.v1':
                if (set(record)!={'schema','boot_id','command_id','state','reason',
                                  'snapshot_count','action_count','whole_arm_ready'} or
                        index!=len(records)-1 or record['whole_arm_ready'] is not False):
                    raise ValueError('Invalid terminal')
                terminal=record
            else:
                raise ValueError('Unknown record')
        if action is None or terminal is None or len(scans)<5:
            raise ValueError('Missing evidence')
        _integer(terminal['snapshot_count'], 0,32); _integer(terminal['action_count'],0,1)
        if terminal['snapshot_count']!=len(scans) or terminal['action_count']!=1:
            raise ValueError('Terminal count mismatch')
        initial = scans[0].joints
        anchor=initial[3].position
        if not 2*tolerance < abs(target-anchor) <= 16:
            raise ValueError('Invalid displacement')
        for i, scan in enumerate(scans):
            if (scan.finished_us-scan.started_us>policy['scan_us'] or
                    scan.finished_us-scan.started_us>policy['age_us']):
                raise ValueError('Scan too old or slow')
            if i and not 0 < scan.started_us-scans[i-1].finished_us <= policy['maximum_gap_us']:
                raise ValueError('Observation gap or stale scan')
            for j, joint in enumerate(scan.joints):
                low, high = policy['joints'][j]
                if (not low<=joint.position<=high or not 0<=joint.goal<=4095 or
                        joint.torque not in (0,1) or joint.moving not in (0,1) or joint.mode!=0):
                    raise ValueError('Invalid pose/control')
                if j!=3:
                    if (joint.moving or abs(joint.position-initial[j].position)>policy['drift'] or
                            joint.goal!=initial[j].goal or joint.torque!=initial[j].torque):
                        raise ValueError('Neighbor changed')
                elif joint.torque!=1:
                    raise ValueError('Elbow not enabled')
                elif i<3:
                    if (joint.moving or abs(joint.position-joint.goal)>tolerance or
                            abs(joint.position-anchor)>policy['drift'] or joint.goal!=initial[j].goal):
                        raise ValueError('Invalid held baseline')
                elif (joint.goal!=target or not min(anchor,target)-tolerance<=joint.position<=max(anchor,target)+tolerance):
                    raise ValueError('Goal mismatch or unexpected motion')
        if scans[1].started_us-scans[0].finished_us<policy['baseline_gap_us']:
            raise ValueError('Baseline spacing')
        start, end = action['started_us'], action['finished_us']
        if (start<scans[2].finished_us or start-scans[2].started_us>policy['age_us'] or
                start-scans[0].started_us>policy['deadline_us'] or
                not start<=end<=start+policy['age_us'] or scans[3].started_us<=end):
            raise ValueError('Invalid command timing')
        previous=False; arrived=False
        for i, scan in enumerate(scans[3:],3):
            if scan.started_us-scans[i-1].finished_us<policy['settle_us']:
                raise ValueError('Unseparated endpoint samples')
            elapsed=scan.finished_us-end
            # Allow one bounded final acquisition past the deadline, never a
            # missing interval or a claim of on-time arrival from late evidence.
            if scan.started_us-end>policy['deadline_us']+policy['maximum_gap_us']:
                raise ValueError('Late endpoint acquisition')
            in_band=abs(scan.joints[3].position-target)<=tolerance and scan.joints[3].moving==0
            arrived=in_band and previous and elapsed<=policy['deadline_us']
            if (arrived or elapsed>=policy['deadline_us']) and i!=len(scans)-1:
                raise ValueError('Evidence continues after terminal boundary')
            previous=in_band
        if arrived:
            state, reason, category='ARRIVED','LEG_ARRIVED','VERIFIED_ARRIVAL'
        elif elapsed>=policy['deadline_us'] and not in_band:
            state, reason, category='NOT_ARRIVED','LEG_NOT_ARRIVED','VERIFIED_NON_ARRIVAL'
        else:
            raise ValueError('Incomplete endpoint interval')
        if terminal['state']!=state or terminal['reason']!=reason:
            raise ValueError('Contradictory terminal')
        result.update(category=category, boot_id=boot, command_id=command,
            requested_target=target, encoded_target=target, first_goal_readback=scans[3].joints[3].goal,
            settled_goal_readback=scans[-1].joints[3].goal, start_position=anchor,
            final_position=scans[-1].joints[3].position,
            signed_error_counts=scans[-1].joints[3].position-target,
            position_change_counts=scans[-1].joints[3].position-anchor,
            observed_after_command_us=elapsed, snapshot_count=len(scans))
    except (ValueError,TypeError,KeyError,IndexError,AttributeError,OverflowError):
        result['reason']='INCOMPLETE_INVALID_OR_UNCERTAIN_LEG_EVIDENCE'
    return result


def export_simulated_held_leg(root, records, *, plan, policy):
    """Retain raw evidence and independent expectations; recompute after export."""
    root=Path(root).resolve()
    raw=canonical(records)
    if len(raw)>131072:
        raise ValueError('Leg evidence exceeds export budget')
    assessment=assess_simulated_held_leg(records, plan=plan, policy=policy)
    exporter=WizardDiagnosticExporter(root)
    exporter.prepare(create=True)
    saved=exporter.export({'mode':'simulated-held-leg'}, [], attachments={
        'held-leg-records.json':raw, 'held-leg-plan.json':canonical(plan),
        'held-leg-policy.json':canonical(policy), 'held-leg-assessment.json':canonical(assessment)})
    replay=replay_simulated_held_leg(root, Path(saved['path']).name)
    return dict(export_path=saved['path'], assessment=replay, replay_verified=True,
                progression_authority=False)


def replay_simulated_held_leg(root, export_id):
    root=Path(root).resolve()
    def read(name):
        value,_=_read(root, export_id, 'attachment-held-leg-'+name+'.json')
        return value
    result=assess_simulated_held_leg(read('records'), plan=read('plan'), policy=read('policy'))
    if canonical(result)!=canonical(read('assessment')):
        raise ValueError('Held leg assessment replay mismatch')
    return result
