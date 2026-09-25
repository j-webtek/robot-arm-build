"""Read-only, raw-record review of the seven-leg r77/r78 noncontact cycle."""
from __future__ import annotations

import hashlib
from pathlib import Path

from .air_typing_r77_campaign import assess_leg as assess_r77
from .air_typing_r78_campaign import assess_leg as assess_r78
from .first_motion_contract import canonical
from .physical_onboarding_durability import read_bounded_regular_file
from .product_ghost_export_review import _read
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


R77_EXPORTS=(
    "wizard-20260924T231007953994Z-f7add203b3ab484fb3d4a278efab903e",
    "wizard-20260924T231010203228Z-1541dd002726476b9f78f56c6c0b52d1",
    "wizard-20260924T231012251808Z-1613945c126b4a16bd1950ddf6b51bcc",
)
R78_EXPORTS=(
    "wizard-20260924T234854794776Z-12d69d99f9e9461286f1467b8922b6be",
    "wizard-20260924T234856604621Z-6b2c8c4752e245c6b8403aa1e29e947b",
    "wizard-20260924T234858074423Z-e609cecbe5104fe2bcecaa83720e4713",
    "wizard-20260924T234900259937Z-5d6c8c652fe24e2abb137b9046dc7811",
)


def summarize_rows(rows):
    if len(rows)!=7 or any(type(row) is not dict for row in rows):
        raise ValueError("Exactly seven verified rows required")
    first,last=rows[3],rows[6]
    if (first["target_goals"]!=last["target_goals"] or
            first["phase"]!="A_return_travel" or last["phase"]!="A_retract"):
        raise ValueError("A repeated target required")
    for row in rows:
        if (row.get("source_kind")!="controller_feedback" or
                row.get("physical_accuracy_verified") is not False or
                row.get("physical_clearance_verified") is not False or
                len(row["final_positions"])!=7 or len(row["target_errors_counts"])!=7):
            raise ValueError("Only controller feedback and no physical claim")
    repeated_delta=[last["final_positions"][i]-first["final_positions"][i]
                    for i in range(7)]
    per_leg=[dict(phase=row["phase"],boot=row["boot"],
                  target_goals=row["target_goals"],final_positions=row["final_positions"],
                  goal_error_counts=row["target_errors_counts"],
                  maximum_selected_abs_goal_error_counts=max(
                      abs(row["target_errors_counts"][i]) for i in row["selected_joints"]))
             for row in rows]
    return dict(schema="rocell.air_typing_cycle_review.v1",status="SEVEN_LEGS_REVIEWED",
                leg_count=7,boot_count=len({row["boot"] for row in rows}),
                legs=per_leg,repeated_A_target_counts=first["target_goals"],
                repeated_A_arrival_delta_counts=repeated_delta,
                maximum_repeated_A_arrival_delta_counts=max(map(abs,repeated_delta)),
                repeatability_samples_at_A_target=2,
                physical_tip_accuracy_verified=False,physical_key_press_verified=False,
                compensation_supported=False)


def review_retained_cycle(export_root):
    root=Path(export_root).resolve()
    rows=[];references=[]
    for revision,ids,assessment_name,record_name,assess in (
        (77,R77_EXPORTS,"air-typing-final-assessment.json",
         "air-typing-final-record.hex.txt",assess_r77),
        (78,R78_EXPORTS,"air-typing-last-assessment.json",
         "air-typing-last-record.hex.txt",assess_r78),
    ):
        previous=None;boot=None
        for leg,export_id in enumerate(ids,1):
            retained,digest=_read(root,export_id,f"attachment-{assessment_name}")
            folder=root/export_id
            raw_hex=read_bounded_regular_file(folder/f"attachment-{record_name}",
                                               maximum_bytes=2260)
            if len(raw_hex)!=2260 or any(c not in b"0123456789abcdef" for c in raw_hex):
                raise ValueError("Raw record encoding differs")
            raw=bytes.fromhex(raw_hex.decode("ascii"))
            boot=retained["boot"] if boot is None else boot
            row=assess(raw,boot=boot,leg=leg,previous=previous)
            row["source_kind"]="controller_feedback"
            if canonical(row)!=canonical(retained):
                raise ValueError("Retained assessment differs from raw record")
            rows.append(row);previous=row
            references.append(dict(revision=revision,leg=leg,export_id=export_id,
                                   assessment_sha256=digest,
                                   raw_sha256=hashlib.sha256(raw).hexdigest()))
    report=summarize_rows(rows)
    report["source_exports"]=references
    return report


def export_retained_cycle(export_root):
    root=Path(export_root).resolve()
    report=review_retained_cycle(root)
    exporter=WizardDiagnosticExporter(root);exporter.prepare(create=True)
    saved=exporter.export({"mode":"air-typing-cycle-review"},[],attachments={
        "air-typing-cycle-review.json":canonical(report)})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("Cycle review export invalid")
    return report,saved["path"]
