from rocell.application.air_typing_r79_review import summarize


def test_two_cycle_differences_keep_goal_error_separate():
    rows=[]
    for leg in range(6):
        rows.append(dict(status="A_REPEAT_LEG_ENDPOINT_VERIFIED",
                         source_kind="controller_feedback",physical_accuracy_verified=False,
                         phase=("A_hover","A_virtual_downstroke","A_retract")[leg%3]+f"_{leg//3+1}",
                         target_goals=[100+leg%3]*7,
                         final_positions=[100+leg%3]*7,
                         target_errors_counts=[0]*7))
    rows[3]["final_positions"][1]+=1
    rows[2]["target_errors_counts"][3]=9
    rows[5]["target_errors_counts"][3]=9
    result=summarize(rows)
    assert result["maximum_pair_difference_counts"]==1
    assert result["retract_elbow_goal_error_counts"]==[9,9]
    assert result["compensation_supported"] is False
