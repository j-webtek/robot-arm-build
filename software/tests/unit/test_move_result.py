"""Exercise public results against the real transaction engine, without hardware."""
from copy import deepcopy
import json
import pytest
from rocell.application.move_result import summarize_move
from rocell.application.move_request import describe_request
from rocell.arm.discrete_transaction import simulate_transactions
from test_wifi_discrete_runner import setup
from test_wizard_activity_ui import render, view, operation


def summary(outcome):
    return summarize_move(dict(outcome=outcome), request_id='op-0',
                          action_id='run_wifi_roll_trial')


@pytest.mark.parametrize('scenario', simulate_transactions()['scenarios'])
def test_simulated_outcomes_keep_uncertainty(scenario):
    tx = scenario['transaction']
    result = summary(dict(status=tx['state'], transaction=tx))
    expected = 'ARRIVED_REPORTED' if scenario['scenario'] == 'normal' else 'EXECUTION_UNCERTAIN'
    assert result['status'] == expected
    assert result['endpoint_verified'] == (expected == 'ARRIVED_REPORTED')
    assert not result['physical_accuracy_verified']
    assert not result['automatic_retry_allowed']


@pytest.mark.parametrize('mode', ['normal', 'lost_ack', 'reset', 'late'])
def test_injected_transport_result_and_duplicate_do_not_resend(tmp_path, mode):
    _, run, sent, _, _, _ = setup(tmp_path, mode)
    outcome = run()
    before = deepcopy(outcome)
    result = summary(outcome)
    assert outcome == before
    assert result['status'] == ('ARRIVED_REPORTED' if mode == 'normal' else 'EXECUTION_UNCERTAIN')
    assert summary(run())['status'] == 'EXECUTION_UNCERTAIN'
    assert len(sent) == 1


def test_cancel_before_send_and_failed_baseline(tmp_path):
    _, run, sent, _, _, _ = setup(tmp_path)
    assert summary(run(lambda: True))['status'] == 'NOT_SENT'
    assert not sent
    result = summarize_move(dict(status='FAILED', baseline={'status': 'FAILED'}),
                            request_id='op-0', action_id='run_wifi_roll_trial')
    assert result['status'] == 'NOT_SENT' and result['last_reported_deg'] is None
    assert summary({})['status'] == 'EXECUTION_UNCERTAIN'


def test_compensation_keeps_desired_and_command_distinct():
    tx = deepcopy(simulate_transactions()['scenarios'][0]['transaction'])
    tx['desired_endpoint_rad'] = tx['command']['rad'] + 0.001
    result = summary(dict(status=tx['state'], transaction=tx))
    assert result['desired_deg'] != result['commanded_deg']
    assert result['reported_minus_desired_deg'] < 0


def test_real_ui_displays_result_and_raw_evidence():
    tx = simulate_transactions()['scenarios'][0]['transaction']
    result = summary(dict(status=tx['state'], transaction=tx))
    op = operation(action_id='run_wifi_roll_trial', result=dict(
        move_result=result, steps=[dict(report={'outcome': {'transaction': tx}})]))
    page = render(view([op]), steps=[dict(load='op-0')], results={'op-0': op})
    text = json.dumps(page)
    for label in ('ARRIVED_REPORTED', '1.00000', 'desired endpoint',
                  'Inspect full movement evidence', 'not independently measured'):
        assert label in text


def test_request_is_persisted_before_send_and_immutable(tmp_path):
    reservation, run, sent, _, _, _ = setup(tmp_path)
    request = reservation.request()
    record = json.loads((tmp_path / ('a'*32 + '-wifi-reserved.json')).read_text())
    assert record['move_request'] == request and not sent
    request['command']['rad'] = 100
    assert reservation.request() == record['move_request']
    result = summary(run())
    assert result['native_request_id'] == 'a'*32
    assert result['configuration_id'] == record['move_request']['configuration_id']


def test_configuration_hash_tracks_policy_not_target_or_attempt():
    tx = simulate_transactions()['scenarios'][0]['transaction']
    def describe(transaction, attempt='first'):
        return describe_request(attempt_id=attempt, transaction=transaction,
                                address='example', mac='example')
    first = describe(tx)
    other = deepcopy(tx)
    other['command']['rad'] += .001
    assert describe(other, 'second')['configuration_id'] == first['configuration_id']
    other['command']['spd'] += 1
    assert describe(other)['configuration_id'] != first['configuration_id']
    assert first['configuration']['firmware_version'] is None
    assert not first['motion_authorized'] and not first['replay_allowed']
