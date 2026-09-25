"""Review baseline observations, never authorize motion or assert tip accuracy."""
from .servo_diagnostic_contract import _identifier, _integer
from .servo_register_reference import PROFILE_ID
from .servo_acquisition_pair import assess_acquisition_pair


def assess_baseline_only(record, *, boot_id, scan_id, maximum_pair_us=1000000,
                         maximum_scan_us=7000000):
    _identifier(boot_id); _identifier(scan_id)
    _integer(maximum_pair_us, 1, 1000000); _integer(maximum_scan_us, 1, 7000000)
    fields = {'schema', 'boot_id', 'scan_id', 'profile_id', 'byte_order',
              'complete', 'reason', 'reads'}
    if (type(record) is not dict or set(record) != fields or
            record['schema'] != 'rocell.baseline_only.v1' or
            record['boot_id'] != boot_id or record['scan_id'] != scan_id or
            record['profile_id'] != PROFILE_ID or record['byte_order'] != 'little' or
            type(record['complete']) is not bool or
            record['reason'] not in ('NOT_STARTED', 'INVALID_SCAN_CONFIGURATION',
                'BASELINE_READ_FAILED', 'BASELINE_TIMING_INVALID', 'BASELINE_CAPTURED')):
        raise ValueError('Invalid baseline-only envelope')
    rows = record['reads']
    if type(rows) is not list or len(rows) > 7:
        raise ValueError('Invalid baseline read count')
    joints = []; issues = []; previous = 0; sequence = -1; first = None
    for index, row in enumerate(rows):
        if type(row) is not list or len(row) != 2:
            raise ValueError('Invalid baseline pair')
        pair = dict(schema='rocell.servo_acquisition_pair.v1', profile_id=PROFILE_ID,
                    byte_order='little')
        for offset, (name, address, width) in enumerate((('target', 42, 2), ('feedback', 56, 15))):
            read = row[offset]
            if type(read) is not list or len(read) != 7:
                raise ValueError('Invalid baseline read')
            seq, start, finish, returned, error, success, raw = read
            _integer(seq); _integer(start); _integer(finish)
            _integer(returned, -2**31, 2**31-1); _integer(error, -1, 255)
            if (seq != index*2+offset or type(success) is not bool or
                    success != (returned == width and error == 0 and finish >= start)):
                raise ValueError('Contradictory baseline read')
            pair[name] = dict(boot_id=boot_id, command_id=scan_id, servo_id=11+index,
                sequence=seq, read_started_us=start, read_finished_us=finish,
                address=address, width=width, status='SUCCEEDED' if success else 'FAILED',
                device_error=error if error >= 0 else None, raw_hex=raw)
        if first is None: first = pair['target']['read_started_us']
        try:
            assessed = assess_acquisition_pair(pair, boot_id=boot_id, command_id=scan_id,
                servo_id=11+index, dispatch_us=0, previous_sequence=sequence,
                previous_finished_us=previous, maximum_pair_us=maximum_pair_us)
        except ValueError:
            issues.append('INVALID_PAIR_EVIDENCE')
            break
        if assessed['status'] != 'REFERENCE_READ_PAIR_COMPLETE':
            issues.append('INCOMPLETE_READ_PAIR')
            break
        sequence = assessed['last_sequence']; previous = assessed['last_finished_us']
        if previous-first > maximum_scan_us:
            issues.append('SCAN_TIME_EXCEEDED'); break
        feedback = assessed['decoded']['feedback']
        joints.append(dict(servo_id=11+index,
            target=assessed['decoded']['target']['decoded_value'],
            position=feedback['position']['decoded_value'],
            moving=feedback['moving']['decoded_value']))
    complete = (len(joints) == 7 and not issues and record['complete'] is True
                and record['reason'] == 'BASELINE_CAPTURED')
    if not complete and not issues: issues.append('SCAN_NOT_COMPLETE')
    return dict(schema='rocell.baseline_only_assessment.v1',
        status='BASELINE_CAPTURED' if complete else 'INCONCLUSIVE', joints=joints,
        issues=issues, simultaneous=False, freshness_at_use_verified=False,
        physical_clearance_verified=False, progression_authority=False,
        endpoint_assessed=False)
