"""Failed or uncertain predecessor evidence cannot become a goal ledger."""
import pytest
import copy

from rocell.application import servo_goal_ledger as ledger


@pytest.mark.parametrize('fault', ['uncertain', 'inconclusive', 'not-arrived', 'write-unverified'])
def test_rejects_unverified_predecessor(tmp_path, monkeypatch, fault):
    result = dict(delivery=dict(result='CONTROLLER_REPORTED_ACCEPTANCE'),
        outcome=dict(status='ASSESSED', assessment=dict(
            category='DIAGNOSTIC_ENDPOINT_CRITERIA_MET',
            write=dict(acknowledgment_verified=True))))
    if fault == 'uncertain': result['delivery']['result'] = 'DELIVERY_UNCERTAIN'
    if fault == 'inconclusive': result['outcome'] = dict(status='INCONCLUSIVE', assessment=None)
    if fault == 'not-arrived':
        result['outcome']['assessment']['category'] = 'FRESH_POSITION_NOT_SETTLED_AT_DESIRED_TARGET'
    if fault == 'write-unverified':
        result['outcome']['assessment']['write']['acknowledgment_verified'] = False
    monkeypatch.setattr(ledger, 'replay_started_startup', lambda *args: result)
    with pytest.raises(ValueError, match='Verified accepted startup arrival required'):
        ledger.load_startup_ledger(tmp_path, 'unverified-predecessor')


def check_two_scan_observation(root, export_id, anchor, native_control, policy):
    """Use the native pipeline's exported predecessor, not a fabricated ledger."""
    second = copy.deepcopy(anchor)
    shift = anchor['reads'][-1][1][2] + policy['minimum_separation_us'] - anchor['reads'][0][0][1]
    for row in second['reads']:
        for read in row:
            read[1] += shift
            read[2] += shift
    control = copy.deepcopy(native_control)
    control['command_id'] = anchor['scan_id']
    end = second['reads'][-1][1][2]
    for index, row in enumerate(control['reads']):
        row[2][1] = end + 10 * (index + 1)
        row[2][2] = row[2][1] + 1
    boundary = control['reads'][-1][2][2] + 1

    def review(a=anchor, b=second, c=control, at=boundary):
        return ledger.assess_mixed_goal_observation(root, export_id, a, b, c,
            scan_id=anchor['scan_id'], boundary_us=at)

    result = review()
    assert result['two_scan_stability_verified'] and result['control_state_verified']
    assert not result['progression_authority'] and not result['provenance_verified']
    assert not result['physical_accuracy_verified']
    # The older anchor is deliberately outside the current-scan age window.
    assert boundary-anchor['reads'][0][0][1] > policy['maximum_age_us']
    for fault in ('mode', 'torque', 'servo', 'address', 'sequence', 'short-read',
                  'device-error', 'failed', 'raw', 'overlap', 'missing', 'boot', 'identity', 'bool'):
        bad = copy.deepcopy(control)
        if fault == 'mode': bad['reads'][0][2][6] = '01'
        if fault == 'torque': bad['reads'][1][2][6] = '00'
        if fault == 'servo': bad['reads'][0][0] = 12
        if fault == 'address': bad['reads'][0][1] = 56
        if fault == 'sequence': bad['reads'][0][2][0] = 1
        if fault == 'short-read': bad['reads'][0][2][3] = 0
        if fault == 'device-error': bad['reads'][0][2][4] = 1
        if fault == 'failed': bad['reads'][0][2][5] = False
        if fault == 'raw': bad['reads'][0][2][6] = '0000'
        if fault == 'overlap': bad['reads'][0][2][1] = end
        if fault == 'missing': bad['reads'].pop()
        if fault == 'boot': bad['boot_id'] = '33' * 16
        if fault == 'identity': bad['command_id'] = 'other-observation'
        if fault == 'bool': bad['reads'][0][2][0] = False
        with pytest.raises(ValueError): review(c=bad)
    with pytest.raises(ValueError): review(at=boundary + policy['maximum_age_us'])
    with pytest.raises(ValueError): review(at=boundary-2)
    for offset in (-1, policy['maximum_wait_us']):
        bad = copy.deepcopy(second)
        for row in bad['reads']:
            for read in row:
                read[1] += offset
                read[2] += offset
        with pytest.raises(ValueError): review(b=bad)
    # Each scan can be close to the ledger but too far from the other scan.
    a, b = copy.deepcopy(anchor), copy.deepcopy(second)
    for scan, position in ((a, 2126), (b, 2130)):
        scan['reads'][0][1][6] = position.to_bytes(2, 'little').hex() + scan['reads'][0][1][6][4:]
    with pytest.raises(ValueError, match='scan-to-scan drift'): review(a=a, b=b)
