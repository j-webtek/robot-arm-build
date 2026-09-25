"""Independent raw-record review of the two-goal elbow grid."""
from __future__ import annotations

import hashlib
from pathlib import Path

from .air_typing_r81_review import review as review_r81
from .air_typing_r83_campaign import assess_leg
from .first_motion_contract import canonical
from .physical_onboarding_durability import read_bounded_regular_file
from .product_ghost_export_review import _read
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


EXPORTS = (
    "wizard-20260925T015236786095Z-7a44f5c62b7a4bbc950d0a52aa5200df",
    "wizard-20260925T015238543684Z-8096c27bddb1475cacf927c2345fab13",
    "wizard-20260925T015240155329Z-4aa30d41db644111ab11bc5b99827c93",
    "wizard-20260925T015241793606Z-acba28fcbff841008a54a318401ca252",
    "wizard-20260925T015244046050Z-e89090ab725f4c778a21056ae055cb13",
    "wizard-20260925T015245688015Z-4b1ecf9722b0477f81302557a96a642c",
    "wizard-20260925T015247329532Z-1659fd05c7174cd99fa262cbffe9a02f",
    "wizard-20260925T015248962121Z-6eec8967fb85466da6edc541a1d35621",
    "wizard-20260925T015251132507Z-2d5b86461eb6439d949942b396dd6aea",
    "wizard-20260925T015252753896Z-21a9e0c7ebc9414e89e03413a0fe5954",
    "wizard-20260925T015254387304Z-7ebcc361679545ffb868282e0595f5c5",
    "wizard-20260925T015256024195Z-ab2e4e5333044b3882e62551ea4c1e20",
    "wizard-20260925T015258168372Z-35e626eb38d44969a519d244a8b38e71",
    "wizard-20260925T015259808770Z-54ba1482164744e3a216ee77a1fccea8",
    "wizard-20260925T015301557245Z-fb55903231f94832b2aa318a815b0761",
    "wizard-20260925T015303129018Z-328caaed1c9046379902acd77dc6a32a",
)


def summarize(rows, training):
    if (len(rows) != 16 or
            any(row.get("status") != "ELBOW_GRID_LEG_ENDPOINT_VERIFIED"
                or row.get("source_kind") != "controller_feedback"
                or row.get("physical_accuracy_verified") is not False for row in rows)
            or training.get("status") != "ELBOW_APPROACH_DIRECTION_CONTROLLER_EFFECT_CONFIRMED"):
        raise ValueError("Verified r81 training and sixteen r83 records required")
    arrivals = [rows[i] for i in (1, 3, 5, 7, 9, 11, 13, 15)]
    goals = [2590, 2590, 2620, 2620] * 2
    labels = ["from_low", "from_high", "from_high", "from_low"] * 2
    if any(row["target_goals"] != [2047, 2075, 2039, goal, 2233, 2040, 2047]
           for row, goal in zip(arrivals, goals)):
        raise ValueError("Held-out elbow grid target differs")
    first = training["first_cycle_arrival_prediction"]
    offsets = {"from_low": first["from_low_elbow_position"] - 2600,
               "from_high": first["from_high_elbow_position"] - 2600}
    observed = [row["final_positions"][3] for row in arrivals]
    predicted = [goal + offsets[label] for goal, label in zip(goals, labels)]
    errors = [actual - forecast for actual, forecast in zip(observed, predicted)]
    baseline = [actual - goal for actual, goal in zip(observed, goals)]
    repeatability = {
        "2590_from_low": abs(observed[4] - observed[0]),
        "2590_from_high": abs(observed[5] - observed[1]),
        "2620_from_high": abs(observed[6] - observed[2]),
        "2620_from_low": abs(observed[7] - observed[3]),
    }
    return dict(
        schema="rocell.air_typing_r83_two_goal_review.v1",
        status="TWO_GOAL_DIRECTION_PREDICTION_CONTROLLER_VERIFIED",
        training_goal_elbow_count=2600,
        held_out_goal_elbow_counts=goals,
        held_out_approach_labels=labels,
        trained_direction_offsets_counts=offsets,
        held_out_observed_elbow_positions=observed,
        held_out_predicted_elbow_positions=predicted,
        held_out_prediction_errors_counts=errors,
        held_out_prediction_mean_abs_error_counts=sum(map(abs, errors)) / len(errors),
        unadjusted_goal_mean_abs_error_counts=sum(map(abs, baseline)) / len(baseline),
        same_direction_repeatability_counts=repeatability,
        physical_tip_accuracy_verified=False,
        physical_key_press_verified=False,
        general_compensation_supported=False,
        caveat="Controller counts only, at fixed speed/load and a small elbow region; no physical TCP measurement.",
    )


def review(export_root):
    root = Path(export_root).resolve()
    training = review_r81(root)
    rows = []
    sources = []
    boot = None
    for leg, export_id in enumerate(EXPORTS, 1):
        retained, digest = _read(root, export_id, "attachment-elbow-grid-assessment.json")
        raw_hex = read_bounded_regular_file(
            root / export_id / "attachment-elbow-grid-record.hex.txt", maximum_bytes=2260)
        if len(raw_hex) != 2260 or any(c not in b"0123456789abcdef" for c in raw_hex):
            raise ValueError("Raw elbow-grid record encoding differs")
        raw = bytes.fromhex(raw_hex.decode("ascii"))
        boot = retained["boot"] if boot is None else boot
        row = assess_leg(raw, boot=boot, leg=leg, previous=rows[-1] if rows else None)
        row["source_kind"] = "controller_feedback"
        if canonical(row) != canonical(retained):
            raise ValueError("Retained assessment differs from raw record")
        rows.append(row)
        sources.append(dict(leg=leg, export_id=export_id,
                            assessment_sha256=digest,
                            record_sha256=hashlib.sha256(raw).hexdigest()))
    report = summarize(rows, training)
    report["boot"] = boot
    report["training_boot"] = training["boot"]
    report["sources"] = sources
    report["training_sources"] = training["sources"]
    return report


def export_review(export_root):
    root = Path(export_root).resolve()
    report = review(root)
    exporter = WizardDiagnosticExporter(root)
    exporter.prepare(create=True)
    saved = exporter.export({"mode": "r83-two-goal-results"}, [], attachments={
        "r83-two-goal-results.json": canonical(report)})
    if not verify_export(Path(saved["path"]))["valid"]:
        raise ValueError("Two-goal review export invalid")
    return report, saved["path"]
