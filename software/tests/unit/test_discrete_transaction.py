import math
import pytest
from rocell.arm.discrete_transaction import DiscreteTransaction, simulate_transactions
from test_arrival_wizard_service import make_service, _run, _ticket


def transaction():
    return DiscreteTransaction(baseline=[0,0,1,0,0,3],baseline_finished_ns=1_000_000_000,
        target=math.radians(1),completion_budget_ns=3_000_000_000)


def test_all_scenarios_and_no_replay():
    report=simulate_transactions()
    assert report['status']=='SUCCEEDED'
    assert len(report['scenarios'])==7 and report['motion_commands']==0
    assert all(s['transaction']['command_attempts']==1 for s in report['scenarios'])


def test_attempt_consumed_before_ack_and_snapshots_are_copies():
    tx=transaction(); command=tx.begin_dispatch(1_010_000_000)
    command['rad']=99
    assert tx.snapshot()['command']['rad']==math.radians(1)
    tx.fault(1_020_000_000)
    with pytest.raises(ValueError):tx.begin_dispatch(1_030_000_000)
    assert tx.snapshot()['command_attempts']==1


def test_stale_baseline_and_time_regression():
    tx=transaction()
    with pytest.raises(ValueError):tx.begin_dispatch(2_000_000_001)
    assert tx.snapshot()['command_attempts']==0
    with pytest.raises(ValueError):transaction().begin_dispatch(1)


def test_deadline_not_restarted_by_ack():
    tx=transaction();tx.begin_dispatch(1_010_000_000)
    tx.acknowledge(1_900_000_000)
    assert tx.next_deadline_ns()==2_900_000_000
    tx.tick(2_900_000_001)
    assert tx.snapshot()['state']=='FEEDBACK_GAP_EXCEEDED'


def test_wizard_inert_preview_and_export(make_service):
    service,runner,_=make_service(mode='physical')
    _ticket(service,'simulate_discrete_transaction',{})
    assert not runner.calls
    outcome=_run(service,'simulate_discrete_transaction')
    assert outcome['status']=='SUCCEEDED',outcome
    assert _run(service,'export_logs')['status']=='SUCCEEDED'
    assert not runner.calls
