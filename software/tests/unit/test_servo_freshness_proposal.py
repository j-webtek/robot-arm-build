import json

import pytest

from rocell.arm.servo_freshness_proposal import JOINTS, SCHEMA, SimulatedServoFreshnessMonitor


def sample(sequence=1):
    tick = 1_000_000+sequence*20_000
    return dict(schema=SCHEMA, boot_id='a'*32, command_sha256='b'*64,
        command_applied_us=1_000_000, report_sequence=sequence, published_us=tick,
        joints={j: dict(read_ok=True, sequence=sequence, acquired_us=tick-1000,
                        position_rad=0.) for j in JOINTS})


def monitor():
    return SimulatedServoFreshnessMonitor(boot_id='a'*32, command_sha256='b'*64)


def send(m, body):
    return m.push(json.dumps(body).encode())


def test_unchanged_positions_need_new_acquisitions_but_never_grant_authority():
    m = monitor()
    for i in range(1, 10):
        result = send(m, sample(i))
    assert result['status'] == 'SIMULATED_REPORTS_CONSISTENT'
    assert not result['device_sample_freshness_verified']
    assert not result['automatic_next_command_allowed']
    assert not result['installed_protocol_supported']


@pytest.mark.parametrize('fault', ['boot', 'command', 'report_replay', 'clock', 'epoch',
    'joint_sequence', 'joint_clock', 'failed_read', 'stale', 'future', 'before_command',
    'nan', 'missing_joint', 'extra', 'bool'])
def test_faults_hold_without_rearm(fault):
    m = monitor()
    send(m, sample())
    value = sample(2)
    row = value['joints']['t']
    if fault == 'boot': value['boot_id'] = 'c'*32
    elif fault == 'command': value['command_sha256'] = 'c'*64
    elif fault == 'report_replay': value['report_sequence'] = 1
    elif fault == 'clock': value['published_us'] = 1
    elif fault == 'epoch': value['command_applied_us'] += 1
    elif fault == 'joint_sequence': row['sequence'] = 1
    elif fault == 'joint_clock': row['acquired_us'] = sample()['joints']['t']['acquired_us']
    elif fault == 'failed_read': row['read_ok'] = False
    elif fault == 'stale': value['published_us'] += 100_001
    elif fault == 'future': row['acquired_us'] = value['published_us']+1
    elif fault == 'before_command': row['acquired_us'] = 1
    elif fault == 'nan': row['position_rad'] = float('nan')
    elif fault == 'missing_joint': del value['joints']['g']
    elif fault == 'extra': value['motion_authorized'] = True
    else: row['sequence'] = True
    with pytest.raises(ValueError): send(m, value)
    assert m.snapshot()['status'] == 'HELD'
    with pytest.raises(ValueError): send(m, sample(3))


def test_original_input_is_not_retained_by_reference_and_budget_is_finite():
    m = monitor()
    first = sample()
    send(m, first)
    first['joints']['t']['sequence'] = 999999
    for i in range(2, 513): send(m, sample(i))
    with pytest.raises(ValueError): send(m, sample(513))


def test_legacy_t1051_is_not_silently_upgraded():
    with pytest.raises(ValueError): send(monitor(), dict(T=1051, t=0))
