from rocell.application.local_pair_mapping_batch import plan_mapping_batch
from rocell.application.separated_pair_mapping_batch import plan_separated_mapping_batch
from rocell.application.fine_pair_lookup_validation import plan_fine_lookup_validation
from rocell.application.local_interval_campaign import plan_local_interval_campaign
from rocell.application.shoulder_movement_matrix import is_mapping_batch


def test_only_exact_mapping_batch_selects_retained_small_policy():
    goals=plan_mapping_batch()['manifest']['goals']
    assert is_mapping_batch(goals)
    changed=[list(pair) for pair in goals];changed[3][0]+=1
    assert not is_mapping_batch(changed)


def test_only_exact_separated_mapping_batch_selects_retained_small_policy():
    goals=plan_separated_mapping_batch()['manifest']['goals']
    assert is_mapping_batch(goals)
    changed=[list(pair) for pair in goals];changed[4][1]+=1
    assert not is_mapping_batch(changed)


def test_only_exact_fine_lookup_batch_selects_retained_small_policy():
    goals=plan_fine_lookup_validation()['manifest']['goals']
    assert is_mapping_batch(goals)
    changed=[list(pair) for pair in goals];changed[10][0]-=1
    assert not is_mapping_batch(changed)


def test_only_exact_local_interval_campaign_selects_retained_small_policy():
    goals=plan_local_interval_campaign()['manifest']['goals']
    assert is_mapping_batch(goals)
    changed=[list(pair) for pair in goals];changed[1][0]+=1
    assert not is_mapping_batch(changed)
