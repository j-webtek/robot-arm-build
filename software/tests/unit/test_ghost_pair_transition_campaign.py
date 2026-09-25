from rocell.application.ghost_pair_transition_campaign import (
    DIRECT_TRANSITION_LEGS,PRIMARY_ROUTE,plan_ghost_pair_transition_campaign)


def test_transition_campaign_is_exact_bounded_and_non_authorizing():
    plan=plan_ghost_pair_transition_campaign()
    assert plan['manifest']['legs']==12
    assert [row[0] for row in plan['manifest']['goals']]==list(PRIMARY_ROUTE)
    assert all(a+b==4114 for a,b in plan['manifest']['goals'])
    assert plan['direct_transition_legs']==[list(pair) for pair in DIRECT_TRANSITION_LEGS]
    assert plan['manifest']['automatic_retry'] is False
    assert plan['claims']['movement_authorized'] is False
    assert plan['claims']['ghost_pair_cycle_validated'] is False
    assert len(plan['plan_sha256'])==64


def test_small_response_exception_is_scoped_to_verified_manifest():
    policy=plan_ghost_pair_transition_campaign()['small_response_policy']
    assert policy['ordinary_global_relaxation'] is False
    assert policy['exact_manifest_only'] is True
    assert policy['continue_only_after_fresh_endpoint_verification'] is True
    assert policy['maximum_consecutive_direct_transitions']==4
    assert policy['stop_on_out_of_tolerance_or_wrong_direction'] is True
