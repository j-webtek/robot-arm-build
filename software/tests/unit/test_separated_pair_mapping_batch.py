import pytest

from rocell.application.separated_pair_mapping_batch import (
    SeparatedPairMappingBatch,plan_separated_mapping_batch,
)


def test_route_separates_plateau_probes_with_large_transitions():
    plan=plan_separated_mapping_batch();primary=[pair[0] for pair in plan['manifest']['goals']]
    assert primary==[2389,2377,2385,2389,2383,2377,2388,2377,2381,2389,2377,2387]
    assert all(4<=abs(delta)<=12 for delta in plan['primary_step_deltas'])
    assert all(sum(pair)==4114 for pair in plan['manifest']['goals'])
    assert plan['initial_gate']==dict(goals=[2381,1733],positions=[2387,1728],
                                      position_tolerance_counts=1)
    assert plan['design']['plateau_probes_are_adjacent'] is False
    assert plan['limits']['maximum_initial_excursion_counts']<=32


def test_route_is_fixed_and_claims_remain_local():
    with pytest.raises(ValueError):SeparatedPairMappingBatch((2389,2377))
    claims=plan_separated_mapping_batch()['claims']
    assert claims['general_compensation_validated'] is False
    assert claims['cartesian_accuracy_validated'] is False
