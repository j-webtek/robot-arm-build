from rocell.application.air_typing_approach_recipe import (
    A,HIGH,MID,SOURCE_GOALS,SOURCE_POSITIONS,TARGETS,validate_recipe,
)


def test_fixed_approach_comparison_is_bounded_and_ends_at_A():
    assert validate_recipe() is True
    assert TARGETS==(MID,A,HIGH,A,MID,A,HIGH,A)
    assert SOURCE_GOALS==A
    assert SOURCE_POSITIONS==(2041,2082,2033,2609,2233,2041,2047)
    prior=SOURCE_GOALS
    for target in TARGETS:
        assert max(abs(a-b) for a,b in zip(prior,target))<=80
        prior=target
