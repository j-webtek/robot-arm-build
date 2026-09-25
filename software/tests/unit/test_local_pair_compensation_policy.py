import pytest

from rocell.application.local_pair_compensation_policy import promote, resolve


def comparison():
    return dict(schema="rocell.second_heldout_candidate_control_comparison.v1",
        comparison_eligible=True, local_reverse_compensation_supported=True,
        candidate_improves_all_primary_metrics=True,
        model_sha256="963df1b4975ca385e6b8d9cd9509695fdfa4838f0cab9bcde9444e28c28452e5",
        model_refitted=False, general_compensation_validated=False,
        desired=[2387,1729], candidate_before=[2391,1724], control_before=[2391,1724],
        candidate_actual=[2387,1730], candidate_error=[0,1],
        control_actual=[2391,1724], control_error=[4,-5],
        control_terminal_outcome="NO_CLEAR_RESPONSE")


def policy():
    return promote(comparison(), {"goals":[[2377,1737],[2389,1725],[2378,1736]]},
        comparison_export="wizard-comparison", comparison_sha256="a"*64)


def test_exact_local_action_resolves_without_motion_authority():
    result=resolve(policy(),current_goals=[2389,1725],current_positions=[2391,1724],
                   desired_positions=[2387,1729])
    assert result["command_goals"]==[2378,1736]
    assert result["expected_encoder_positions"]==[2387,1730]
    assert result["compensation_applied"] and not result["movement_authorized"]


@pytest.mark.parametrize("field",["goal","position","desired"])
def test_scope_rejects_stale_or_unvalidated_requests(field):
    args=dict(current_goals=[2389,1725],current_positions=[2391,1724],
              desired_positions=[2387,1729])
    if field=="goal":args["current_goals"]=[2388,1726]
    if field=="position":args["current_positions"]=[2389,1724]
    if field=="desired":args["desired_positions"]=[2386,1728]
    with pytest.raises(ValueError):resolve(policy(),**args)


def test_promotion_rejects_weaker_comparison():
    value=comparison();value["candidate_improves_all_primary_metrics"]=False
    with pytest.raises(ValueError):promote(value,{"goals":[[2377,1737],[2389,1725],[2378,1736]]},
        comparison_export="wizard-comparison",comparison_sha256="a"*64)
