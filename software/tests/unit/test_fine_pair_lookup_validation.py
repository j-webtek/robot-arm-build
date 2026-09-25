from rocell.application.fine_pair_lookup_validation import (
    PRIMARY_TARGETS,plan_fine_lookup_validation)


def test_plan_repeats_candidates_from_lower_conditioning_plateau():
    plan=plan_fine_lookup_validation();goals=plan['manifest']['goals']
    assert [row[0] for row in goals]==list(PRIMARY_TARGETS)
    assert all(sum(row)==4114 for row in goals)
    assert plan['manifest']['roles'][1]=='candidate_2387'
    assert plan['manifest']['roles'][4]=='heldout_2387'
    assert plan['manifest']['roles'][7]=='candidate_2389'
    assert plan['manifest']['roles'][10]=='heldout_2389'
    assert max(abs(goals[i][0]-goals[i-1][0]) for i in range(1,12))==12


def test_plan_cannot_claim_validation_or_motion():
    plan=plan_fine_lookup_validation()
    assert plan['claims']['fine_endpoint_lookup_validated'] is False
    assert plan['claims']['movement_authorized'] is False
    assert plan['limits']['automatic_retry'] is False
    assert plan['limits']['automatic_return'] is False
    assert plan_fine_lookup_validation()['plan_sha256']==plan['plan_sha256']
