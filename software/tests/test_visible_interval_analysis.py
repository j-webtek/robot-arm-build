import copy

import pytest

from rocell.application.visible_interval_analysis import analyze_visible_interval_cycles


def cycle():
    actuals = ([2410, 1706], [2398, 1718], [2403, 1712], [2415, 1700])
    targets = ([2401, 1713], [2389, 1725], [2401, 1713], [2413, 1701])
    directions = (-1, -1, 1, 1)
    return {"schema": "rocell.visible_interval_campaign_result.v1", "plan_sha256": "a" * 64,
            "rows": [{"leg": leg, "target": target, "actual": actual,
                      "target_residual": [actual[j] - target[j] for j in range(2)],
                      "approach_direction": direction}
                     for leg, (target, actual, direction) in enumerate(
                         zip(targets, actuals, directions))]}


def test_three_exact_cycles_fit_direction_model_without_promotion():
    report = analyze_visible_interval_cycles([cycle(), cycle(), cycle()])
    assert report["direction_models"]["-1"]["median_residual"] == [9, -7]
    assert report["direction_models"]["-1"]["pair_sum_preserving_correction"] == [-8, 8]
    assert report["direction_models"]["1"]["median_residual"] == [2, -1]
    assert report["direction_models"]["1"]["pair_sum_preserving_correction"] == [-2, 2]
    assert report["run_to_run_endpoint_span"] == [0] * 8
    assert report["held_out_proposal"]["candidate_command"] == [2399, 1715]
    assert report["model_fitted"] is True
    assert report["held_out_validated"] is report["compensation_promoted"] is False


@pytest.mark.parametrize("fault", ["count", "schema", "plan", "route", "direction"])
def test_analysis_rejects_noncomparable_cycles(fault):
    cycles = [cycle(), cycle(), cycle()]
    if fault == "count": cycles.pop()
    elif fault == "schema": cycles[1]["schema"] = "wrong"
    elif fault == "plan": cycles[1]["plan_sha256"] = "b" * 64
    elif fault == "route": cycles[1]["rows"][0]["target"][0] += 1
    else: cycles[1]["rows"][0]["approach_direction"] = 1
    with pytest.raises(ValueError):
        analyze_visible_interval_cycles(copy.deepcopy(cycles))
