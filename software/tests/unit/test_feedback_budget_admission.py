from test_wifi_cartesian import setup


def test_short_remaining_window_stays_endpoint_failure_without_new_io(tmp_path):
    _,run,sent,reads,now,_=setup(tmp_path,'deadline_timeout',feedback_budget_ns=800_000_000)
    result=run()
    assert result['status']=='COMPLETION_DEADLINE_EXCEEDED'
    assert result['error'] is None
    assert not result['transaction']['result']['endpoint_verified']
    assert len(sent)==1 and reads
    scheduling=result['feedback_scheduling']
    assert len(scheduling)==1
    assert 0<scheduling[0]['remaining_ns']<800_000_000
    assert now[0]>=13
    assert all(row[1]<13_000_000_000 for row in result['transaction']['rows'])


def test_real_feedback_fault_is_not_suppressed(tmp_path):
    _,run,sent,reads,_,_=setup(tmp_path,'reset',feedback_budget_ns=800_000_000)
    result=run()
    assert result['error']=='TRANSACTION_INTERRUPTED_OR_UNCERTAIN'
    assert result['status']=='COMMAND_OUTCOME_UNCERTAIN'
    assert len(sent)==1 and len(reads)==1
    assert not result['feedback_scheduling']


def test_clean_arrival_does_not_wait_for_deadline(tmp_path):
    _,run,_,_,now,_=setup(tmp_path,'desired_candidate',compensated_endpoint=True,
        wrist_candidate=True,feedback_budget_ns=800_000_000)
    result=run()
    assert result['status']=='COMPENSATED_REPORTED_ENDPOINT_VERIFIED'
    assert now[0]<13 and not result['feedback_scheduling']


def test_cancellation_during_terminal_wait(tmp_path):
    _,run,sent,_,now,_=setup(tmp_path,'unchanged',feedback_budget_ns=800_000_000)
    result=run(lambda:now[0]>=12.8)
    assert result['status']=='CANCELLED_OUTCOME_UNCERTAIN'
    assert len(sent)==1 and now[0]<13
