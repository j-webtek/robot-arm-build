"""Proposed r76 endpoint rule; does not change the deployed r75 verifier.

The commanded displacement and measured displacement are different quantities.
A small command need not cause two counts of travel when the servo was already
at its new target. This exception is deliberately tight and joint-local.
"""


def endpoint_joint_verified(*, initial_goal: int, initial_position: int,
                            target_goal: int, final_position: int) -> bool:
    command = target_goal - initial_goal
    travel = final_position - initial_position
    if not command or abs(command) > 80 or abs(travel) > 92:
        return False
    direction = 1 if command > 0 else -1
    if travel * direction < -1 or abs(final_position - target_goal) > 12:
        return False
    if abs(command) < 4 or travel * direction >= 2:
        return True
    return (abs(initial_position - target_goal) <= 3
            and abs(final_position - target_goal) <= 3)
