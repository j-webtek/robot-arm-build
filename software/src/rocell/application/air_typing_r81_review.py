"""Independent raw-record review of elbow approach-direction comparison."""
from __future__ import annotations

import hashlib
from pathlib import Path

from .air_typing_r81_campaign import assess_leg
from .first_motion_contract import canonical
from .physical_onboarding_durability import read_bounded_regular_file
from .product_ghost_export_review import _read
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


EXPORTS=(
    "wizard-20260925T011708071876Z-50e7e7f9c9b44e2e8500c6a7caa12f36",
    "wizard-20260925T011709712383Z-203429d062df4896923fc1c0abac79d2",
    "wizard-20260925T011711368704Z-7d55246ec89942968d80f7e335d0b3cf",
    "wizard-20260925T011712999627Z-654509d20b0f4408bf10e71462191c94",
    "wizard-20260925T011714533376Z-c31157030b184638a0c7b169ca2c9563",
    "wizard-20260925T011716266046Z-70fa6ee473934b1bb87fc59f8ba8e1e5",
    "wizard-20260925T011717911714Z-96fde937f67040deb106bdcdf4f843b2",
    "wizard-20260925T011719439949Z-665b83c9c1304bc29729329396a1dc7a",
)


def summarize(rows):
    if (len(rows)!=8 or any(row.get("status")!="ELBOW_DIRECTION_LEG_ENDPOINT_VERIFIED"
                            or row.get("source_kind")!="controller_feedback"
                            or row.get("physical_accuracy_verified") is not False
                            for row in rows)):
        raise ValueError("Eight controller-verified noncontact rows required")
    first_low,first_high=rows[1],rows[3]
    second_low,second_high=rows[5],rows[7]
    for row in (first_low,first_high,second_low,second_high):
        if row["target_goals"]!=[2047,2075,2039,2600,2233,2040,2047]:
            raise ValueError("Compared A target differs")
    prediction=dict(from_low_elbow_position=first_low["final_positions"][3],
                    from_high_elbow_position=first_high["final_positions"][3])
    held_out=dict(from_low_elbow_position=second_low["final_positions"][3],
                  from_high_elbow_position=second_high["final_positions"][3])
    errors={key:held_out[key]-value for key,value in prediction.items()}
    difference=first_high["final_positions"][3]-first_low["final_positions"][3]
    held_out_difference=second_high["final_positions"][3]-second_low["final_positions"][3]
    return dict(schema="rocell.air_typing_r81_direction_review.v1",
                status="ELBOW_APPROACH_DIRECTION_CONTROLLER_EFFECT_CONFIRMED",
                leg_count=8,goal_elbow_count=2600,
                first_cycle_arrival_prediction=prediction,
                held_out_second_cycle_arrival=held_out,
                held_out_prediction_errors_counts=errors,
                first_cycle_high_minus_low_counts=difference,
                held_out_high_minus_low_counts=held_out_difference,
                same_direction_repeatability_counts={
                    "from_low":abs(errors["from_low_elbow_position"]),
                    "from_high":abs(errors["from_high_elbow_position"])},
                physical_tip_accuracy_verified=False,physical_key_press_verified=False,
                general_compensation_supported=False,
                caveat="Controller counts only at one noncontact pose, load and speed; physical TCP not measured.")


def review(export_root):
    root=Path(export_root).resolve();rows=[];references=[];boot=None
    for leg,export_id in enumerate(EXPORTS,1):
        retained,digest=_read(root,export_id,"attachment-elbow-direction-assessment.json")
        raw_hex=read_bounded_regular_file(
            root/export_id/"attachment-elbow-direction-record.hex.txt",maximum_bytes=2260)
        if len(raw_hex)!=2260 or any(c not in b"0123456789abcdef" for c in raw_hex):
            raise ValueError("Raw elbow-direction record encoding differs")
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
    report=summarize(rows);report["boot"]=boot;report["sources"]=references
    return report


def export_review(export_root):
    root=Path(export_root).resolve();report=review(root)
    exporter=WizardDiagnosticExporter(root);exporter.prepare(create=True)
    saved=exporter.export({"mode":"r81-elbow-direction-results"},[],attachments={
        "r81-elbow-direction-results.json":canonical(report)})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("Direction review export invalid")
    return report,saved["path"]
