"""Compare verified leg-three feedback with the later post-reset pose; offline only."""
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


LEG3="wizard-20260924T231012251808Z-1613945c126b4a16bd1950ddf6b51bcc"
POSE="wizard-20260924T232712748224Z-e462f96c2c1b4561895acf10ba434231"


def analyze(root):
    root=Path(root).resolve();exports=root/"runs/wizard-exports"
    leg,leg_digest=_read(exports,LEG3,"attachment-air-typing-final-assessment.json")
    pose,pose_digest=_read(exports,POSE,"attachment-pose-assessment.json")
    if (leg["status"]!="FINALE_LEG_ENDPOINT_VERIFIED" or leg["leg"]!=3
            or leg["source_kind"]!="controller_feedback"
            or pose["category"]!="STABLE_SAMPLED_POSE" or pose["origin"]!="DEVICE_CAPTURE"
            or pose["progression_authority"] is not False or len(pose["joints"])!=7):
        raise ValueError("Source evidence differs")
    rows=[]
    for index,joint in enumerate(pose["joints"]):
        if (joint["servo_id"]!=11+index or joint["last_goal"]!=leg["final_goals"][index]
                or joint["torque"]!=1 or joint["controls_unchanged"] is not True
                or joint["position_span"]!=0):
            raise ValueError("Post-reset pose not same-goal stable feedback")
        delta=joint["last_position"]-leg["final_positions"][index]
        rows.append(dict(servo_id=joint["servo_id"],goal=joint["last_goal"],
                         leg_three_position=leg["final_positions"][index],
                         post_reset_position=joint["last_position"],
                         post_reset_minus_leg_three=delta,
                         distance_to_goal=abs(joint["last_position"]-joint["last_goal"])))
    report=dict(schema="rocell.r77_source_gap.v1",leg_three_export=LEG3,
                leg_three_digest=leg_digest,post_reset_pose_export=POSE,
                post_reset_pose_digest=pose_digest,joints=rows,
                would_pass_one_count_source_gate=all(abs(row["post_reset_minus_leg_three"])<=1 for row in rows),
                would_pass_three_count_and_twelve_to_goal_gate=all(
                    abs(row["post_reset_minus_leg_three"])<=3 and row["distance_to_goal"]<=12
                    for row in rows),
                exact_failed_source_samples_retained=False,
                same_boot=False,physical_tip_accuracy_verified=False,
                movement_command_sent=False,progression_authority=False)
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({"mode":"r77-postfault-source-gap"},[],attachments={
        "r77-source-gap.json":canonical(report)})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("Gap export invalid")
    return saved["path"],report


if __name__=="__main__":
    path,result=analyze(Path(__file__).resolve().parents[1])
    print(path)
    print({"one_count_pass":result["would_pass_one_count_source_gate"],
           "three_count_pass":result["would_pass_three_count_and_twelve_to_goal_gate"],
           "deltas":[row["post_reset_minus_leg_three"] for row in result["joints"]]})
