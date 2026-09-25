"""Replay a fixed air-typing campaign from immutable per-leg exports."""
from pathlib import Path

from .air_typing_campaign import TARGETS, assess_leg
from .first_motion_contract import canonical
from .product_ghost_export_review import _read
from .wizard_diagnostic_export import verify_export


def score_exported_campaign(export_root, export_ids, *, boot, source_kind="controller_feedback"):
    if (len(export_ids) != len(TARGETS) or len(set(export_ids)) != len(TARGETS)
            or any(type(item) is not str or "/" in item or "\\" in item or item.startswith(".")
                   for item in export_ids)):
        raise ValueError("Seventeen distinct export identifiers required")
    root = Path(export_root).resolve()
    rows = []
    for leg, source in enumerate(export_ids, 1):
        directory = (root / source).resolve()
        if directory.parent != root or not verify_export(directory)["valid"]:
            raise ValueError("Leg export invalid")
        saved, _ = _read(root, source, "attachment-air-typing-assessment.json")
        raw = bytes.fromhex((directory / "attachment-air-typing-record.hex.txt").read_text("ascii"))
        row = assess_leg(raw, boot=boot, leg=leg, previous=rows[-1] if rows else None)
        row["source_kind"] = source_kind
        if canonical(row) != canonical(saved):
            raise ValueError("Saved assessment differs from raw replay")
        rows.append(row)
    return dict(schema="rocell.air_typing_score.v1", result="CONTROLLER_ENDPOINTS_VERIFIED",
                source_kind=source_kind, boot=boot, verified_legs=len(rows),
                source_exports=list(export_ids),
                maximum_joint_error_counts=max(abs(error) for row in rows
                                               for error in row["target_errors_counts"]),
                final_positions=rows[-1]["final_positions"],
                final_goals=rows[-1]["final_goals"],
                virtual_key_sequence="ABA", physical_accuracy_verified=False,
                limitation="Joint feedback does not verify tool-tip location, clearance, or actual key presses")
