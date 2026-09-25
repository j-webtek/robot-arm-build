import pytest

from rocell.application.air_typing_cycle_review import summarize_rows


def test_repeated_target_delta_does_not_authorize_compensation():
    rows=[]
    for i in range(7):
        rows.append(dict(phase="other",boot="one" if i<3 else "two",
                         target_goals=[100]*7,final_positions=[100]*7,
                         target_errors_counts=[0]*7,selected_joints=[0],
                         source_kind="controller_feedback",
                         physical_accuracy_verified=False,
                         physical_clearance_verified=False))
    rows[3]["phase"]="A_return_travel"
    rows[6]["phase"]="A_retract"
    rows[6]["final_positions"]=[100,99,102,108,98,100,100]
    rows[6]["target_errors_counts"]=[0,-1,2,8,-2,0,0]
    result=summarize_rows(rows)
    assert result["maximum_repeated_A_arrival_delta_counts"]==8
    assert result["repeated_A_arrival_delta_counts"]==[0,-1,2,8,-2,0,0]
    assert result["repeatability_samples_at_A_target"]==2
    assert result["compensation_supported"] is False


def test_wrong_target_or_physical_claim_rejected():
    rows=[]
    for i in range(7):
        rows.append(dict(phase="A_return_travel" if i==3 else
                         "A_retract" if i==6 else "other",boot="x",
                         target_goals=[100]*7,final_positions=[100]*7,
                         target_errors_counts=[0]*7,selected_joints=[0],
                         source_kind="controller_feedback",
                         physical_accuracy_verified=False,
                         physical_clearance_verified=False))
    rows[6]["target_goals"]=[101]*7
    with pytest.raises(ValueError):summarize_rows(rows)
    rows[6]["target_goals"]=[100]*7
    rows[6]["physical_accuracy_verified"]=True
    with pytest.raises(ValueError):summarize_rows(rows)
