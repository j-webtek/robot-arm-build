"""Offline five-leg consistency checks; no live controller dependency."""
from copy import deepcopy

import pytest

from rocell.application.ghost_b_cycle_analysis import analyze
from rocell.application.ghost_typing_resume_preview import SOURCE_GOALS, TARGETS


def records():
    previous = list(SOURCE_GOALS)
    result = []
    for leg, target in enumerate(TARGETS, 1):
        selected = [i for i in range(7) if previous[i] != target[i]]
        result.append(dict(schema="rocell.ghost_b_leg_attempt.v1",
                           category="LEG_VERIFIED", leg=leg,
                           boot_id="a" * 32, app_sha256="b" * 64,
                           retry_allowed=False, automatic_progression=False,
                           physical_key_contact=False, one_write_max=True,
                           write_attempted=True,
                           selected_joints=selected, target_goals=list(target),
                           before=dict(positions=list(previous), goals=list(previous)),
                           after=dict(positions=list(target), goals=list(target))))
        previous = list(target)
    return result


def test_five_leg_analysis_is_consistent_and_non_authorizing():
    result = analyze(records())
    assert result["status"] == "CONTROLLER_SEQUENCE_CONSISTENT_NOT_PHYSICAL_KEY_VALIDATION"
    assert len(result["legs"]) == 5
    assert result["maximum_selected_goal_residual_counts"] == 0
    assert result["final_goals"] == list(TARGETS[-1])
    assert not result["motion_authorized"]
    assert not result["keyboard_registered"]


def test_rejects_broken_endpoint_chain_or_contact_claim():
    rows = records()
    rows[2]["before"]["positions"][0] += 1
    with pytest.raises(ValueError, match="leg 3"):
        analyze(rows)
    rows = deepcopy(records())
    rows[4]["physical_key_contact"] = True
    with pytest.raises(ValueError, match="leg 5"):
        analyze(rows)
