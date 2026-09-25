from rocell.application.air_typing_repeat_recipe import (
    DOWN,HOVER,RETRACT,SOURCE_GOALS,SOURCE_POSITIONS,TARGETS,validate_recipe,
)


def test_six_leg_two_cycle_recipe_is_fixed_and_bounded():
    assert validate_recipe() is True
    assert TARGETS==(HOVER,DOWN,RETRACT,HOVER,DOWN,RETRACT)
    assert SOURCE_GOALS==RETRACT
    assert SOURCE_POSITIONS==(2041,2081,2033,2609,2233,2041,2047)
    prior=SOURCE_GOALS
    for target in TARGETS:
        assert max(abs(a-b) for a,b in zip(prior,target))<=80
        prior=target
