"""Offline replay of native hold test records. No device authority or transport.

Only SIMULATION is accepted until a signed policy/terminal-manifest contract is
integrated. Native success labels alone never establish verified initialization.
"""
from pathlib import Path
import json

from .first_motion_contract import canonical
from .hold_initialization_model import HoldInitializationModel, Joint, Snapshot, Limits
from .servo_diagnostic_contract import _identifier, _integer
from .servo_register_reference import PROFILE_ID
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def _snapshot(record, maximum_pair_us=10_000):
    if set(record) != {'schema', 'boot_id', 'command_id', 'snapshot_index',
                       'profile_id', 'byte_order', 'complete', 'reason', 'reads'}:
        raise ValueError('Snapshot fields')
    if (record['profile_id'] != PROFILE_ID or record['byte_order'] != 'little' or
            record['complete'] is not True or record['reason'] != 'HOLD_STATE_CAPTURED' or
            type(record['reads']) is not list or len(record['reads']) != 28):
        raise ValueError('Incomplete snapshot')
    values = [{} for _ in range(7)]
    previous = -1
    oldest = None
    pair_start = None
    for index, row in enumerate(record['reads']):
        if type(row) is not list or len(row) != 4 or type(row[3]) is not list or len(row[3]) != 7:
            raise ValueError('Read row')
        servo, address, width, read = row
        seq, start, end, returned, error, success, raw = read
        for value in (servo, address, width, seq, start, end, returned, error):
            _integer(value)
        local = index if index < 14 else index - 14
        expected_addr = ((42, 56) if index < 14 else (33, 40))[local % 2]
        expected_width = {42: 2, 56: 15, 33: 1, 40: 1}[expected_addr]
        if (servo != 11 + local // 2 or address != expected_addr or width != expected_width or
                seq != local or not previous <= start <= end or returned != width or
                error != 0 or success is not True or type(raw) is not str or
                len(raw) != 2 * width or raw != raw.lower()):
            raise ValueError('Invalid raw acquisition')
        data = bytes.fromhex(raw)
        if len(data) != width:
            raise ValueError('Raw width')
        values[local // 2][address] = data
        if address == 42:
            pair_start = start
        if address == 56 and end - pair_start > maximum_pair_us:
            raise ValueError('Pair duration')
        previous = end
        if oldest is None:
            oldest = start
    joints = tuple(Joint(int.from_bytes(v[56][:2], 'little'),
                         int.from_bytes(v[42], 'little'), v[40][0], v[33][0], v[56][10])
                   for v in values)
    return Snapshot(oldest, previous, joints)


def assess_simulated_hold(records, *, allow_enable=False):
    """Replay the default simulation policy; fail closed on missing/extra evidence.

    INCONCLUSIVE includes invalid or incomplete capture, not a non-arrival claim.
    Signed hardware policies and independently authenticated provenance are absent.
    """
    return _assess_hold(records, allow_enable=allow_enable)


def _assess_hold(records, *, allow_enable, limits=Limits(), maximum_pair_us=10_000,
                 maximum_gap_us=500_000, windows=None, include_endpoint=False,
                 supported_recovery=False, recovery_limit=5):
    result = dict(schema='rocell.hold_replay.v1', origin='SIMULATION',
                  category='INCONCLUSIVE', whole_arm_ready=False,
                  progression_authority=False, provenance_verified=False)
    try:
        if type(records) is not list or not 1 <= len(records) <= 11:
            raise ValueError('Record count')
        boot = _identifier(records[0]['boot_id'])
        command = _identifier(records[0]['command_id'])
        scans, actions, terminal = [], [], None
        for record_index, record in enumerate(records):
            if record['boot_id'] != boot or record['command_id'] != command:
                raise ValueError('Mixed identity')
            if record['schema'] == 'rocell.hold_snapshot.v1':
                _integer(record['snapshot_index'], 0, 7)
                if record['snapshot_index'] != len(scans):
                    raise ValueError('Scan ordering')
                scans.append(_snapshot(record, maximum_pair_us))
            elif record['schema'] == 'rocell.hold_action.v1':
                expected = {'schema', 'boot_id', 'command_id', 'action_index', 'servo_id',
                            'address', 'width', 'payload_hex', 'payload_source', 'started_us',
                            'finished_us', 'library_return', 'device_error', 'ack_policy', 'dispatch_status'}
                if set(record) != expected:
                    raise ValueError('Action fields')
                for name in ('action_index', 'servo_id', 'address', 'width', 'started_us',
                             'finished_us', 'library_return', 'device_error'):
                    _integer(record[name])
                if (record['action_index'] != len(actions) or len(actions) >= 2 or
                        record['ack_policy'] != 'ENABLED' or record['library_return'] != 1 or
                        record['device_error'] != 0 or record['dispatch_status'] != 'SUCCEEDED' or
                        record['payload_source'] != 'PINNED_LIBRARY_ARGUMENT_ENCODING'):
                    raise ValueError('Uncertain dispatch')
                actions.append(record)
            elif record['schema'] == 'rocell.hold_terminal.v1':
                if (set(record) != {'schema', 'boot_id', 'command_id', 'state', 'reason',
                                    'snapshot_count', 'action_count', 'whole_arm_ready'} or
                        terminal is not None or record_index != len(records) - 1 or
                        record['whole_arm_ready'] is not False):
                    raise ValueError('Invalid terminal record')
                terminal = record
            else:
                raise ValueError('Unknown record')
        if terminal is None:
            raise ValueError('Missing terminal record')
        _integer(terminal['snapshot_count'], 0, 8)
        _integer(terminal['action_count'], 0, 2)
        if (terminal['state'] != 'CAPTURED' or terminal['reason'] != 'ELBOW_HOLD_CAPTURED' or
                terminal['snapshot_count'] != len(scans) or terminal['action_count'] != len(actions)):
            raise ValueError('Incomplete or faulted terminal')
        if len(scans) not in (5, 7) or len(actions) != (len(scans) - 3) // 2:
            raise ValueError('Incomplete sequence')
        if supported_recovery:
            expected_order = ['snapshot']*3 + ['action'] + ['snapshot']*2 + ['terminal']
            if [r['schema'] for r in records] != ['rocell.hold_'+s+'.v1' for s in expected_order]:
                raise ValueError('Recovery must contain exactly one ordered hold')
            if windows is None or any(not windows[3][0] <= s.joints[3].goal <= windows[3][1]
                                      for s in scans[:3]):
                raise ValueError('Recovery old goal outside envelope')
            if scans[3].started_us-actions[0]['finished_us'] < limits.settle_us:
                raise ValueError('Recovery post-write dwell')
        if any(b.started_us - a.finished_us > maximum_gap_us for a, b in zip(scans, scans[1:])):
            raise ValueError('Observation gap')
        if windows is not None:
            for scan in scans:
                if any(not low <= joint.position <= high
                       for joint, (low, high) in zip(scan.joints, windows)):
                    raise ValueError('Position outside admitted window')
        model = HoldInitializationModel(allow_enable=allow_enable, limits=limits,
                                        supported_recovery=supported_recovery,recovery_limit=recovery_limit)
        model.baseline(scans[0], scans[1], now_us=scans[1].finished_us)

        def dispatch(scan, action):
            expected = model.propose(scan, now_us=action['started_us'])
            wire = bytes.fromhex(action['payload_hex'])
            if (action['servo_id'], action['address'], wire) != expected or len(wire) != action['width']:
                raise ValueError('Payload mismatch')
            model.acknowledge(success=True, finished_us=action['finished_us'])

        dispatch(scans[2], actions[0])
        model.observe(scans[3], now_us=scans[3].finished_us)
        if len(actions) == 2:
            dispatch(scans[4], actions[1])
            model.observe(scans[5], now_us=scans[5].finished_us)
        model.observe(scans[-1], now_us=scans[-1].finished_us)
        if model.state != 'AWAIT_EXPORT':
            raise ValueError('Unsettled endpoint')
        # Derive review values only after replay validates the entire sequence.
        # Payload bytes are the pinned library's argument encoding, NOT an
        # independently observed wire trace. Positions are servo counts, not a
        # measured stylus-tip position in space.
        elbow = 14 - 11
        before, after, settled = scans[2], scans[3], scans[-1]
        payload = bytes.fromhex(actions[0]['payload_hex'])
        endpoint = dict(
            servo_id=14, unit='servo_count',
            requested_hold_target=before.joints[elbow].position,
            encoded_command_target=int.from_bytes(payload[1:3], 'little'),
            command_evidence='PINNED_LIBRARY_ARGUMENT_ENCODING',
            wire_observation_verified=False,
            previous_goal=before.joints[elbow].goal,
            first_goal_readback=after.joints[elbow].goal,
            settled_goal_readback=settled.joints[elbow].goal,
            start_position=before.joints[elbow].position,
            settled_position=settled.joints[elbow].position,
            settled_error_counts=settled.joints[elbow].position-model.target,
            position_change_counts=settled.joints[elbow].position-before.joints[elbow].position,
            torque_before=before.joints[elbow].torque,
            torque_settled=settled.joints[elbow].torque,
            explicit_enable_used=len(actions)==2,
            command_duration_us=actions[0]['finished_us']-actions[0]['started_us'],
            final_observation_after_command_us=settled.finished_us-actions[0]['finished_us'],
            other_joint_changes=[dict(servo_id=11+i,
                position_change_counts=settled.joints[i].position-scans[0].joints[i].position,
                goal_changed=settled.joints[i].goal!=scans[0].joints[i].goal,
                torque_changed=settled.joints[i].torque!=scans[0].joints[i].torque)
                for i in range(7) if i != elbow],
            physical_tip_accuracy_verified=False)
        result.update(category='SIMULATED_HOLD_VERIFIED', target_count=model.target,
                      action_count=len(actions), snapshot_count=len(scans),
                      boot_id=boot, command_id=command)
        if include_endpoint:
            result['endpoint'] = endpoint
    except (ValueError, KeyError, TypeError, IndexError, AttributeError):
        # Stable public failure result; original records remain in the export.
        result['reason'] = 'INCOMPLETE_INVALID_OR_UNCERTAIN_EVIDENCE'
    return result


def review_simulated_hold_endpoints(records, *, allow_enable=False):
    """Add count-level review without changing the historical replay contract."""
    result = _assess_hold(records, allow_enable=allow_enable, include_endpoint=True)
    result['schema'] = 'rocell.hold_endpoint_review.v1'
    return result


def export_simulated_hold(root, records, *, allow_enable=False):
    """Persist source evidence and derived assessment with the existing exporter."""
    if type(allow_enable) is not bool:
        raise ValueError('Boolean simulation enable policy required')
    encoded = canonical(records)
    if len(encoded) > 45056:
        raise ValueError('Hold evidence exceeds reserved budget')
    result = assess_simulated_hold(records, allow_enable=allow_enable)
    exporter = WizardDiagnosticExporter(Path(root))
    exporter.prepare(create=True)
    exported = exporter.export({'mode': 'simulated-hold-review'}, [], attachments={
        'hold-records.json': encoded,
        'hold-assessment.json': canonical(result),
        'hold-endpoints.json': canonical(review_simulated_hold_endpoints(records, allow_enable=allow_enable)),
        'hold-replay-policy.json': canonical({'origin': 'SIMULATION', 'allow_enable': allow_enable,
                                            'policy': 'hold-model-default-v1'}),
    })
    if not verify_export(Path(exported['path']))['valid']:
        raise ValueError('Hold export verification failed')
    return exported


def replay_simulated_hold_export(path):
    """Verify the manifest then recompute, never trust a stored success result."""
    path = Path(path)
    if not verify_export(path)['valid']:
        raise ValueError('Invalid hold export manifest')
    policy = json.loads((path / 'attachment-hold-replay-policy.json').read_bytes())
    if (set(policy) != {'origin', 'allow_enable', 'policy'} or
            policy['origin'] != 'SIMULATION' or policy['policy'] != 'hold-model-default-v1' or
            type(policy['allow_enable']) is not bool):
        raise ValueError('Unsupported replay policy')
    data = (path / 'attachment-hold-records.json').read_bytes()
    if len(data) > 131072:
        raise ValueError('Evidence budget exceeded')
    result = assess_simulated_hold(json.loads(data), allow_enable=policy['allow_enable'])
    if canonical(result) != canonical(json.loads((path / 'attachment-hold-assessment.json').read_bytes())):
        raise ValueError('Stored assessment does not match replay')
    # Older exports predate the optional endpoint review. New exports retain
    # both the unchanged assessment and this independently recomputed detail.
    endpoints = path / 'attachment-hold-endpoints.json'
    if endpoints.exists():
        detail = review_simulated_hold_endpoints(json.loads(data), allow_enable=policy['allow_enable'])
        if canonical(detail) != canonical(json.loads(endpoints.read_bytes())):
            raise ValueError('Stored endpoint review does not match replay')
    return result
