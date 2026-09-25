import pytest

from rocell.application.local_pair_mapping_batch import (
    INITIAL_GOALS,
    INITIAL_POSITIONS,
    LocalPairMappingBatch,
    plan_mapping_batch,
)


def test_exact_batch_covers_both_directions_and_repeated_anchors() -> None:
    plan = plan_mapping_batch()
    goals = plan["manifest"]["goals"]
    assert len(goals) == 12
    assert all(a + b == 4114 for a, b in goals)
    assert plan["initial_gate"]["goals"] == list(INITIAL_GOALS)
    assert plan["initial_gate"]["positions"] == list(INITIAL_POSITIONS)
    deltas = plan["primary_step_deltas"]
    assert all(4 <= abs(delta) <= 12 for delta in deltas)
    assert any(delta < 0 for delta in deltas) and any(delta > 0 for delta in deltas)
    assert [pair[0] for pair in goals].count(2377) == 3
    assert [pair[0] for pair in goals].count(2389) == 3
    assert plan["limits"]["maximum_initial_excursion_counts"] <= 32
    assert plan["claims"]["general_compensation_validated"] is False


def test_route_is_not_an_arbitrary_target_surface() -> None:
    with pytest.raises(ValueError, match="Exact reviewed"):
        LocalPairMappingBatch((2377, 2389))


def test_plan_identity_is_deterministic() -> None:
    assert plan_mapping_batch()["plan_sha256"] == plan_mapping_batch()["plan_sha256"]
