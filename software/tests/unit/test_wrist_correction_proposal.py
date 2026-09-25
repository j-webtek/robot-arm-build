import pytest

from rocell.application.first_motion_contract import canonical
from rocell.application.wrist_correction_proposal import propose_wrist_correction
from rocell.safety.absolute_wrist_review_authority import AbsoluteWristIntent
from test_absolute_wrist_result_review import fixture


def pair(index, direction=-1, fault='miss'):
    request, trial = fixture(direction=direction, fault=fault)
    body = request.to_dict()
    body['attempt_id'] = 'operation-' + format(index, '032x')
    request = AbsoluteWristIntent(canonical(body))
    trial['request_sha256'] = request.request_sha256
    for phase in ('baseline', 'post'):
        trial[phase]['request_sha256'] = request.request_sha256
    return request, canonical(trial)


def propose(*rows):
    return propose_wrist_correction(list(rows), expected_basis='SYNTHETIC_WIRE_REHEARSAL')


def test_separates_nominal_from_raw_motor_target_without_double_quantization():
    p = propose(pair(1), pair(2))
    assert p['status'] == 'OFFLINE_EXPERIMENT_CANDIDATE'
    assert p['nominal_target_deg'] == 0
    assert p['experimental_motor_target_deg'] == pytest.approx(-p['observed_bias_deg'])
    from rocell.application.wrist_accuracy_analysis import reference_wrist_goal
    import math
    goal = reference_wrist_goal(math.radians(p['experimental_motor_target_deg']))
    assert p['reference_goal_register'] == goal['goal_register']
    assert math.radians(p['experimental_motor_target_deg']) != goal['representable_rad']
    assert abs(p['predicted_nominal_error_deg']) < .05
    assert not p['motion_authorized'] and not p['calibration_validated']
    assert not p['automatic_retry'] and p['maximum_commands'] == 1


def test_opposite_direction_changes_correction_sign():
    p = propose(pair(1, 1), pair(2, 1))
    assert p['experimental_motor_target_deg'] > 0


def test_duplicate_attempt_not_independent_evidence():
    with pytest.raises(ValueError, match='Duplicate'):
        propose(pair(1), pair(1))


def test_historical_cache_is_byte_keyed_bounded_and_not_mutable(monkeypatch):
    from rocell.application import wrist_correction_proposal as module
    module._historical_trace_bytes.cache_clear()
    original=module.summarize_absolute_wrist_trace
    calls=[]
    def counted(*args,**kwargs):
        calls.append(True)
        return original(*args,**kwargs)
    monkeypatch.setattr(module,'summarize_absolute_wrist_trace',counted)
    try:
        rows=[pair(701),pair(702)]
        first=propose(*rows)
        first['evidence'][0]['final_error_deg']=12345
        second=propose(*rows)
        assert len(calls)==2 and second['evidence'][0]['final_error_deg']!=12345
        propose(rows[0],pair(703))
        assert len(calls)==3
        for _ in range(2):
            with pytest.raises(ValueError):
                propose((rows[0][0],b'{}'),rows[1])
        assert len(calls)==5  # malformed input is neither reused nor cached
        for _ in range(2):
            with pytest.raises(ValueError):
                module.propose_wrist_correction(rows,expected_basis='WRONG_BASIS')
        assert len(calls)==7
        assert module._historical_trace_bytes.cache_info().maxsize==16
    finally:
        module._historical_trace_bytes.cache_clear()


@pytest.mark.parametrize('fault', ['corrupt','no_response','other_joint','departure'])
def test_bad_original_cannot_be_used_for_correction(fault):
    p = propose(pair(1), pair(2, fault=fault))
    assert p['status'] == 'HELD'
    assert p['experimental_motor_target_deg'] is None


def test_approach_mismatch_is_not_averaged():
    assert 'TARGET_OR_APPROACH_MISMATCH' in propose(pair(1),pair(2,1))['reasons']


def test_good_endpoint_does_not_invent_needed_correction():
    p = propose(pair(1,fault=None),pair(2,fault=None))
    assert 'ALREADY_WITHIN_NOMINAL_TOLERANCE' in p['reasons']


def test_basis_cannot_be_promoted_to_physical():
    with pytest.raises(ValueError):
        propose_wrist_correction([pair(1),pair(2)], expected_basis='RETAINED_PHYSICAL_CAPTURE')


def test_changed_original_hash_rejected():
    import json
    request, raw = pair(2)
    trial = json.loads(raw)
    trial['post']['raw']['sha256'] = 'a'*64
    with pytest.raises(ValueError):
        propose(pair(1), (request,canonical(trial)))
