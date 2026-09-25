from rocell.application.air_typing_r76_endpoint_rule import endpoint_joint_verified as verified


def test_already_near_target_can_remain_still():
    assert verified(initial_goal=2076, initial_position=2082,
                    target_goal=2080, final_position=2082)
    assert verified(initial_goal=2038, initial_position=2033,
                    target_goal=2034, final_position=2033)


def test_no_travel_only_exempt_when_near_on_both_ends():
    assert not verified(initial_goal=2076, initial_position=2088,
                        target_goal=2080, final_position=2088)
    assert not verified(initial_goal=2076, initial_position=2083,
                        target_goal=2080, final_position=2084)
    assert not verified(initial_goal=1994, initial_position=2001,
                        target_goal=1941, final_position=2001)


def test_large_directional_move_and_bounds_still_required():
    assert verified(initial_goal=1994, initial_position=2001,
                    target_goal=1941, final_position=1949)
    assert not verified(initial_goal=1994, initial_position=2001,
                        target_goal=1941, final_position=2004)
    assert not verified(initial_goal=1994, initial_position=2001,
                        target_goal=1941, final_position=1920)
