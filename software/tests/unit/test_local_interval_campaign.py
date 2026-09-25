from rocell.application.local_interval_campaign import plan_local_interval_campaign


def test_campaign_is_three_startups_five_endpoints_and_bounded():
    plan=plan_local_interval_campaign()
    assert plan['sessions']==3
    assert plan['endpoint_commands']==[2377,2383,2385,2388,2389]
    assert plan['training_commands']==[2377,2385,2389]
    assert plan['heldout_commands']==[2383,2388]
    assert len(plan['manifest']['goals'])==11
    assert all(sum(pair)==4114 for pair in plan['manifest']['goals'])
    assert plan['limits']['automatic_retry'] is False
    assert plan['claims']['local_interval_interpolation_validated'] is False
