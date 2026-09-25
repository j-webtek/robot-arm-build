"""Review direct mode/torque reads without changing servo configuration."""
from .servo_diagnostic_contract import _identifier, _integer
from .servo_register_reference import PROFILE_ID


def assess_control_state(control, *, boot_id, command_id, reviewed_mode,
                         after_us, boundary_us, maximum_age_us):
    """Require complete ordered register evidence within a caller's time boundary.

    This checks reported bytes, not independent hardware provenance. Torque must
    already be enabled; this module cannot enable it or issue a servo command.
    """
    _identifier(boot_id)
    _identifier(command_id)
    _integer(reviewed_mode, 0, 255)
    _integer(after_us)
    _integer(boundary_us)
    _integer(maximum_age_us, 1)
    fields = {'schema', 'boot_id', 'command_id', 'profile_id', 'reason', 'reads'}
    if (type(control) is not dict or set(control) != fields or
            control['schema'] != 'rocell.control_state_reads.v1' or
            control['boot_id'] != boot_id or control['command_id'] != command_id or
            control['profile_id'] != PROFILE_ID or control['reason'] != 'CONTROL_READ_CAPTURED' or
            type(control['reads']) is not list or len(control['reads']) != 14):
        raise ValueError('Invalid control envelope')
    previous = after_us
    oldest = None
    for index, row in enumerate(control['reads']):
        if type(row) is not list or len(row) != 3 or type(row[2]) is not list or len(row[2]) != 7:
            raise ValueError('Invalid control row')
        servo, address, read = row
        seq, start, finish, returned, error, success, raw = read
        for value in (servo, address, seq, start, finish, returned, error):
            _integer(value)
        if oldest is None:
            oldest = start
        expected_byte = 1 if index % 2 else reviewed_mode
        if (servo != 11 + index // 2 or address != (40 if index % 2 else 33) or
                seq != index or returned != 1 or error != 0 or success is not True or
                raw != f'{expected_byte:02x}' or not previous <= start <= finish or
                (index == 0 and start <= after_us) or
                finish - start > 1000000 or finish - oldest > 7000000):
            raise ValueError('Control acquisition or state mismatch')
        previous = finish
    if not previous <= boundary_us or boundary_us - oldest > maximum_age_us:
        raise ValueError('Control evidence stale or beyond boundary')
    return dict(schema='rocell.control_state_assessment.v1',
        status='CONTROL_STATE_MATCHES', first_started_us=oldest,
        last_finished_us=previous, oldest_age_us=boundary_us-oldest,
        progression_authority=False, provenance_verified=False)
