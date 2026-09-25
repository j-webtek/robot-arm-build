"""Read-only raw review and cross-pose prediction from r81 to r82."""
from __future__ import annotations

import hashlib
from pathlib import Path

from .air_typing_r81_review import review as review_r81
from .air_typing_r82_campaign import assess_leg
from .first_motion_contract import canonical
from .physical_onboarding_durability import read_bounded_regular_file
from .product_ghost_export_review import _read
from .wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


EXPORTS=(
    "wizard-20260925T013526119380Z-1b4accad51464b118d9bc72b8356eca7",
    "wizard-20260925T013527768381Z-fd78cdaab9f34dbcbf3041fc7f0b3d98",
    "wizard-20260925T013529387022Z-47b06fdb6a5e4ab5b9f2db38bcbc35d0",
    "wizard-20260925T013531040425Z-9f3c8a0227c848e197dfc71fff140f2e",
    "wizard-20260925T013532662008Z-08c08a0332ea42569fb719445d55b278",
    "wizard-20260925T013534193849Z-b0b7748afc7046258b450f47fa9ca482",
    "wizard-20260925T013535937501Z-6e7613a07f344392b39a227e79bfe0cc",
    "wizard-20260925T013537473684Z-d9c823e27197402dbc2b3061a8e679ff",
)


def summarize(rows,training):
    if (len(rows)!=8 or any(row.get("status")!="ELBOW_SHIFT_LEG_ENDPOINT_VERIFIED"
                            or row.get("source_kind")!="controller_feedback"
                            or row.get("physical_accuracy_verified") is not False
                            for row in rows)
            or training.get("status")!="ELBOW_APPROACH_DIRECTION_CONTROLLER_EFFECT_CONFIRMED"):
        raise ValueError("Verified r81 and eight r82 records required")
    arrivals=[rows[i] for i in (1,3,5,7)]
    if any(row["target_goals"]!=[2047,2075,2039,2610,2233,2040,2047]
           for row in arrivals):
        raise ValueError("Held-out target differs")
    train=training["first_cycle_arrival_prediction"]
    offsets=dict(from_low=train["from_low_elbow_position"]-2600,
                 from_high=train["from_high_elbow_position"]-2600)
    labels=("from_low","from_high","from_low","from_high")
    observed=[row["final_positions"][3] for row in arrivals]
    predicted=[2610+offsets[label] for label in labels]
    errors=[actual-forecast for actual,forecast in zip(observed,predicted)]
    baseline_errors=[actual-2610 for actual in observed]
    return dict(schema="rocell.air_typing_r82_cross_pose_review.v1",
                status="NEARBY_POSE_DIRECTION_PREDICTION_CONTROLLER_VERIFIED",
                training_goal_elbow_count=2600,held_out_goal_elbow_count=2610,
                trained_direction_offsets_counts=offsets,
                held_out_approach_labels=list(labels),
                held_out_observed_elbow_positions=observed,
                held_out_predicted_elbow_positions=predicted,
                held_out_prediction_errors_counts=errors,
                held_out_prediction_max_abs_error_counts=max(map(abs,errors)),
                held_out_prediction_mean_abs_error_counts=sum(map(abs,errors))/len(errors),
                unadjusted_goal_mean_abs_error_counts=sum(map(abs,baseline_errors))/len(errors),
                same_direction_repeatability_counts=dict(
                    from_low=abs(observed[2]-observed[0]),
                    from_high=abs(observed[3]-observed[1])),
                physical_tip_accuracy_verified=False,physical_key_press_verified=False,
                general_compensation_supported=False,
                caveat="Only one adjacent elbow goal, same load/speed/pose family; no physical TCP measurement.")


def review(export_root):
    root=Path(export_root).resolve();training=review_r81(root)
    rows=[];references=[];boot=None
    for leg,export_id in enumerate(EXPORTS,1):
        retained,digest=_read(root,export_id,"attachment-elbow-shift-assessment.json")
        raw_hex=read_bounded_regular_file(
            root/export_id/"attachment-elbow-shift-record.hex.txt",maximum_bytes=2260)
        if len(raw_hex)!=2260 or any(c not in b"0123456789abcdef" for c in raw_hex):
            raise ValueError("Raw elbow-shift record encoding differs")
        raw=bytes.fromhex(raw_hex.decode("ascii"))
        boot=retained["boot"] if boot is None else boot
        row=assess_leg(raw,boot=boot,leg=leg,previous=rows[-1] if rows else None)
        row["source_kind"]="controller_feedback"
        if canonical(row)!=canonical(retained):
            raise ValueError("Retained assessment differs from raw record")
        rows.append(row)
        references.append(dict(leg=leg,export_id=export_id,
                               assessment_sha256=digest,
                               record_sha256=hashlib.sha256(raw).hexdigest()))
    report=summarize(rows,training);report["boot"]=boot
    report["training_boot"]=training["boot"]
    report["sources"]=references
    report["training_sources"]=training["sources"]
    return report


def export_review(export_root):
    root=Path(export_root).resolve();report=review(root)
    exporter=WizardDiagnosticExporter(root);exporter.prepare(create=True)
    saved=exporter.export({"mode":"r82-cross-pose-results"},[],attachments={
        "r82-cross-pose-results.json":canonical(report)})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("Cross-pose review export invalid")
    return report,saved["path"]
