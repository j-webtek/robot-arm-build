"""Candidate r78 joint-local source window; full freshness/stability is separate."""


def source_joint_verified(*, previous_position: int, expected_goal: int,
                          current_position: int, current_goal: int) -> bool:
    return (current_goal == expected_goal
            and abs(current_position - previous_position) <= 3
            and abs(current_position - expected_goal) <= 12)
