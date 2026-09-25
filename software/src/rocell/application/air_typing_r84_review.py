"""Independent raw-record review of the noncontact multi-joint hover cycle."""
from __future__ import annotations

import hashlib
from pathlib import Path

from .air_typing_r84_campaign import assess_leg
from .first_motion_contract import canonical
from .physical_onboarding_durability import read_bounded_regular_file
from .product_ghost_export_review import _read
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


EXPORTS = (
    "wizard-20260925T021059337585Z-380b152c9f424d5783b4b54638a0f186",
    "wizard-20260925T021101368885Z-d687b11b48494db6be073e7a12098f3a",
    "wizard-20260925T021103416857Z-beeb1fd656f44cbc81cb56f89de93212",
    "wizard-20260925T021105656168Z-84c7b583f8914922acc8bc1513615bd0",
    "wizard-20260925T021107732675Z-f78e38c83e084ab9b11a84e8b7068012",
)


def summarize(rows):
    if (len(rows) != 5 or
            any(row.get("status") != "MULTI_HOVER_LEG_ENDPOINT_VERIFIED"
                or row.get("source_kind") != "controller_feedback"
                or row.get("physical_accuracy_verified") is not False for row in rows)
            or rows[1]["target_goals"] != rows[3]["target_goals"]
            or rows[0]["target_goals"] != rows[2]["target_goals"]
            or rows[2]["target_goals"] != rows[4]["target_goals"]):
        raise ValueError("Five verified A/lateral-hover records required")
    lateral_first, lateral_second = rows[1]["final_positions"], rows[3]["final_positions"]
    a_first, a_second = rows[2]["final_positions"], rows[4]["final_positions"]
    lateral_delta = [b-a for a,b in zip(lateral_first,lateral_second)]
    a_delta = [b-a for a,b in zip(a_first,a_second)]
    selected = [0,1,2,3,4]
    if rows[1]["selected_joints"] != selected or rows[2]["selected_joints"] != selected or rows[3]["selected_joints"] != selected or rows[4]["selected_joints"] != selected:
        raise ValueError("Multi-joint selection differs")
    return dict(schema="rocell.air_typing_r84_multi_hover_review.v1",
        status="MULTI_JOINT_HOVER_CONTROLLER_REPEATABILITY_VERIFIED",
        leg_count=5, selected_joints=selected,
        lateral_goal=rows[1]["target_goals"], a_goal=rows[2]["target_goals"],
        lateral_first_positions=lateral_first, lateral_second_positions=lateral_second,
        lateral_repeat_delta_counts=lateral_delta,
        a_first_return_positions=a_first, a_second_return_positions=a_second,
        a_repeat_delta_counts=a_delta,
        maximum_repeat_difference_counts=max(map(abs,lateral_delta+a_delta)),
        all_endpoints_controller_verified=True,
        physical_tip_accuracy_verified=False, physical_key_press_verified=False,
        general_compensation_supported=False,
        caveat="Repeatability is in servo feedback at two noncontact poses; no observed tool tip, board registration, or contact.")


def review(export_root):
    root = Path(export_root).resolve()
    rows, sources, boot = [], [], None
    for leg, export_id in enumerate(EXPORTS,1):
        retained,digest = _read(root,export_id,"attachment-multi-hover-assessment.json")
        raw_hex = read_bounded_regular_file(
            root/export_id/"attachment-multi-hover-record.hex.txt",maximum_bytes=2260)
        if len(raw_hex) != 2260 or any(c not in b"0123456789abcdef" for c in raw_hex):
            raise ValueError("Raw multi-hover record encoding differs")
        raw = bytes.fromhex(raw_hex.decode("ascii"))
        boot = retained["boot"] if boot is None else boot
        row = assess_leg(raw,boot=boot,leg=leg,previous=rows[-1] if rows else None)
        row["source_kind"] = "controller_feedback"
        if canonical(row) != canonical(retained):
            raise ValueError("Retained assessment differs from raw record")
        rows.append(row)
        sources.append(dict(leg=leg,export_id=export_id,assessment_sha256=digest,
                            record_sha256=hashlib.sha256(raw).hexdigest()))
    report = summarize(rows)
    report["boot"] = boot
    report["sources"] = sources
    return report


def export_review(export_root):
    root = Path(export_root).resolve()
    report = review(root)
    exporter = WizardDiagnosticExporter(root)
    exporter.prepare(create=True)
    saved = exporter.export({"mode":"r84-multi-hover-results"},[],attachments={
        "r84-multi-hover-results.json":canonical(report)})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("Multi-hover review export invalid")
    return report,saved["path"]
