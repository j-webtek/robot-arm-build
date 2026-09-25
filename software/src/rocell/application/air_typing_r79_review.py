"""Read-only, raw-record review of the r79 repeated A-target arrivals."""
from __future__ import annotations

import hashlib
from pathlib import Path

from .air_typing_r79_campaign import assess_leg
from .first_motion_contract import canonical
from .physical_onboarding_durability import read_bounded_regular_file
from .product_ghost_export_review import _read
from .wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


EXPORTS=(
    "wizard-20260925T005159100448Z-12fe39d6cb8745bcb761578ef8f7e6c9",
    "wizard-20260925T005200560072Z-50f86394b0d644c1a8008f9816808f72",
    "wizard-20260925T005202801676Z-47cff071716441b78315a24b17983c22",
    "wizard-20260925T005204430544Z-b7b0a64dd53d46f1ac5dabf6a0b838e6",
    "wizard-20260925T005205863579Z-d7822fd515084f419fa541dd794efd0e",
    "wizard-20260925T005208116238Z-9058a361c92f4d81ba686b724286c712",
)


def summarize(rows):
    if len(rows)!=6 or any(row.get("status")!="A_REPEAT_LEG_ENDPOINT_VERIFIED"
                           or row.get("source_kind")!="controller_feedback"
                           or row.get("physical_accuracy_verified") is not False
                           for row in rows):
        raise ValueError("Six controller-verified noncontact rows required")
    pairs=[]
    for i in range(3):
        first,second=rows[i],rows[i+3]
        if first["target_goals"]!=second["target_goals"]:
            raise ValueError("Repeated target differs")
        delta=[second["final_positions"][j]-first["final_positions"][j]
               for j in range(7)]
        pairs.append(dict(action=first["phase"].rsplit("_",1)[0],
                          target_goals=first["target_goals"],
                          first_positions=first["final_positions"],
                          second_positions=second["final_positions"],
                          second_minus_first_counts=delta,
                          maximum_abs_delta_counts=max(map(abs,delta)),
                          first_goal_error_counts=first["target_errors_counts"],
                          second_goal_error_counts=second["target_errors_counts"]))
    return dict(schema="rocell.air_typing_r79_repeat_review.v1",
                status="TWO_A_CYCLES_CONTROLLER_VERIFIED",leg_count=6,
                pairs=pairs,maximum_pair_difference_counts=max(
                    row["maximum_abs_delta_counts"] for row in pairs),
                retract_elbow_goal_error_counts=[rows[2]["target_errors_counts"][3],
                                                 rows[5]["target_errors_counts"][3]],
                physical_tip_accuracy_verified=False,physical_key_press_verified=False,
                compensation_supported=False)


def review(export_root):
    root=Path(export_root).resolve();rows=[];references=[];boot=None
    for leg,export_id in enumerate(EXPORTS,1):
        retained,digest=_read(root,export_id,"attachment-air-typing-repeat-assessment.json")
        raw_hex=read_bounded_regular_file(
            root/export_id/"attachment-air-typing-repeat-record.hex.txt",maximum_bytes=2260)
        if len(raw_hex)!=2260 or any(c not in b"0123456789abcdef" for c in raw_hex):
            raise ValueError("Raw repeat record encoding differs")
        raw=bytes.fromhex(raw_hex.decode("ascii"))
        boot=retained["boot"] if boot is None else boot
        row=assess_leg(raw,boot=boot,leg=leg,previous=rows[-1] if rows else None)
        row["source_kind"]="controller_feedback"
        if canonical(row)!=canonical(retained):
            raise ValueError("Retained repeat assessment differs from raw record")
        rows.append(row)
        references.append(dict(leg=leg,export_id=export_id,
                               assessment_sha256=digest,
                               record_sha256=hashlib.sha256(raw).hexdigest()))
    report=summarize(rows);report["boot"]=boot;report["sources"]=references
    return report


def export_review(export_root):
    root=Path(export_root).resolve();report=review(root)
    exporter=WizardDiagnosticExporter(root);exporter.prepare(create=True)
    saved=exporter.export({"mode":"r79-air-typing-repeat-review"},[],attachments={
        "r79-air-typing-repeat-review.json":canonical(report)})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("Repeat review export invalid")
    return report,saved["path"]
