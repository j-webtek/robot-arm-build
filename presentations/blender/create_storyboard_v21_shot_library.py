"""Create the editorial shot-library manifest for storyboard v2.1.

The canonical storyboard remains the authority for action, timing, and stage
semantics. This script adds editorial coverage choices without changing that
system behavior. Run it from the repository root with normal Python.
"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "presentations" / "blender" / "storyboard_v21_shots.json"
OUTPUT = ROOT / "presentations" / "blender" / "storyboard_v21_shot_library.json"

RIGS = {
    "macro": {
        "framing": "extreme_close_up",
        "lens_mm": 72,
        "camera_motion": "micro_push_or_locked",
        "editorial_strength": "detail and contact mechanics",
    },
    "dolly": {
        "framing": "medium_wide",
        "lens_mm": 58,
        "camera_motion": "controlled_dolly",
        "editorial_strength": "system relationship and overlays",
    },
    "arm_follow": {
        "framing": "medium_action",
        "lens_mm": 52,
        "camera_motion": "subject_follow",
        "editorial_strength": "continuous physical action",
    },
    "hero": {
        "framing": "wide_establishing",
        "lens_mm": 44,
        "camera_motion": "slow_hero_push",
        "editorial_strength": "whole-workcell geography",
    },
    "overhead": {
        "framing": "top_down_wide",
        "lens_mm": 48,
        "camera_motion": "measured_overhead_push",
        "editorial_strength": "device localization and spatial truth",
    },
    "low_three_quarter": {
        "framing": "low_three_quarter_medium",
        "lens_mm": 58,
        "camera_motion": "gentle_push_and_focus_pull",
        "editorial_strength": "arm silhouette and toolhead readability",
    },
    "contact_three_quarter": {
        "framing": "contact_three_quarter_close",
        "lens_mm": 62,
        "camera_motion": "deliberate_contact_push",
        "editorial_strength": "joint chain and contact depth",
    },
}

ALTERNATES = {
    1: ("low_three_quarter", "spatial_context"),
    2: ("hero", "request_in_workcell_context"),
    3: ("dolly", "closer_workcell_reveal"),
    4: ("hero", "proposal_in_system_context"),
    5: ("hero", "external_localization_context"),
    6: ("hero", "fail_closed_wide"),
    7: ("macro", "permit_and_toolhead_detail"),
    8: ("macro", "contact_mechanics"),
    9: ("contact_three_quarter", "rhythm_contact_coverage"),
    10: ("dolly", "receipt_with_keyboard_context"),
    11: ("hero", "crossing_geography"),
    12: ("hero", "phone_setup_geography"),
    13: ("hero", "phone_sequence_context"),
    14: ("arm_follow", "send_action_context"),
    15: ("arm_follow", "phone_receipt_detail"),
    16: ("hero", "evidence_in_workcell_context"),
    17: ("dolly", "closer_brand_resolve_with_workcell_context"),
}

SUBJECTS = {
    1: "stylus hovering over keyboard r",
    2: "operator display request console",
    3: "complete measured workcell",
    4: "amber model proposal and locked runtime fields",
    5: "camera localization of keyboard and phone",
    6: "stale evidence rejection with stationary arm",
    7: "fresh evidence and one-contact permit",
    8: "seven-phase keyboard r contact",
    9: "e a d y keyboard rhythm",
    10: "ready receipt on operator display",
    11: "high-clearance keyboard-to-phone crossing",
    12: "phone screen-state check and Messages entry",
    13: "on my way phone tap sequence",
    14: "separately permitted Send tap",
    15: "local and phone receipts",
    16: "compact evidence trail",
    17: "Tactevra brand resolve",
}

CONTINUITY = {
    1: "hold unresolved uncertainty; no contact",
    2: "display remains physically separate from both controlled devices",
    3: "preserve board, device, arm, and operator-display placement",
    4: "amber means proposal, never authority",
    5: "overhead is the camera view, not an omniscient editor view",
    6: "arm must remain visibly stationary throughout rejection",
    7: "permit is short-lived and limited to the next contact",
    8: "same articulated arm, bare stylus, keyboard, and r key across cut",
    9: "simplified graphics after the first fully taught contact",
    10: "operator display reads lowercase ready",
    11: "no contact authority during high-clearance crossing",
    12: "show expected-screen check before first phone tap",
    13: "show 2x disclosure during compressed middle taps",
    14: "Send receives its own final permit and result reads Sent",
    15: "receipts belong to separate local and phone workflows",
    16: "show evidence summary, not an unreadable log wall",
    17: "logo, one tagline, and simulation qualifier only",
}


def seconds(frame_count: int, fps: int) -> float:
    return round(frame_count / fps, 3)


def asset_record(shot: dict, rig: str, variant: str, purpose: str) -> dict:
    fps = 24
    frame_count = shot["end"] - shot["start"] + 1
    asset_id = f"s{shot['id']:02d}_{shot['slug']}__{variant}"
    rig_meta = RIGS[rig]
    return {
        "asset_id": asset_id,
        "scene_id": shot["id"],
        "scene_slug": shot["slug"],
        "variant": variant,
        "editorial_role": "default_cut" if variant == "primary" else "alternate_coverage",
        "purpose": purpose,
        "stage": shot["stage"],
        "subject": SUBJECTS[shot["id"]],
        "rig": rig,
        "framing": rig_meta["framing"],
        "lens_mm": rig_meta["lens_mm"],
        "camera_motion": rig_meta["camera_motion"],
        "editorial_strength": rig_meta["editorial_strength"],
        "frame_start": shot["start"],
        "frame_end": shot["end"],
        "frame_count": frame_count,
        "duration_seconds": seconds(frame_count, fps),
        "recommended_edit_seconds": [
            round(min(1.25, frame_count / fps), 2),
            round(frame_count / fps, 2),
        ],
        "continuity_requirement": CONTINUITY[shot["id"]],
        "system_truth": "presentation simulation; action timing and state come from canonical storyboard v2.1",
        "audio_strategy": "narration_and_score_from_master; clip is rendered silent",
        "review_status": "generated_for_editorial_review",
        "clip_path": f"clips/{asset_id}.mp4",
        "poster_path": f"posters/{asset_id}.jpg",
    }


def main() -> None:
    canonical = json.loads(SOURCE.read_text(encoding="utf-8"))
    assets = []
    for shot in canonical["shots"]:
        assets.append(asset_record(shot, shot["rig"], "primary", "canonical storyboard coverage"))
        alternate_rig, purpose = ALTERNATES[shot["id"]]
        assets.append(asset_record(shot, alternate_rig, "alternate", purpose))

    inserts = [
        {
            "id": "s07_toolhead-permit__insert",
            "scene_id": 7,
            "scene_slug": "fresh-evidence-one-permit",
            "rig": "macro",
            "start": 794,
            "end": 840,
            "subject": "toolhead construction while first permit travels",
            "purpose": "mechanical_detail_insert",
            "continuity": CONTINUITY[7],
        },
        {
            "id": "s08_r-key-depression__insert",
            "scene_id": 8,
            "scene_slug": "r-contact-benchmark",
            "rig": "macro",
            "start": 1049,
            "end": 1068,
            "subject": "stylus and r key at contact depth",
            "purpose": "contact_detail_insert",
            "continuity": CONTINUITY[8],
        },
    ]
    for insert in inserts:
        rig_meta = RIGS[insert["rig"]]
        frame_count = insert["end"] - insert["start"] + 1
        assets.append({
            "asset_id": insert["id"],
            "scene_id": insert["scene_id"],
            "scene_slug": insert["scene_slug"],
            "variant": "insert",
            "editorial_role": "detail_insert",
            "purpose": insert["purpose"],
            "stage": canonical["shots"][insert["scene_id"] - 1]["stage"],
            "subject": insert["subject"],
            "rig": insert["rig"],
            "framing": rig_meta["framing"],
            "lens_mm": rig_meta["lens_mm"],
            "camera_motion": rig_meta["camera_motion"],
            "editorial_strength": rig_meta["editorial_strength"],
            "frame_start": insert["start"],
            "frame_end": insert["end"],
            "frame_count": frame_count,
            "duration_seconds": seconds(frame_count, canonical["fps"]),
            "recommended_edit_seconds": [0.5, seconds(frame_count, canonical["fps"])],
            "continuity_requirement": insert["continuity"],
            "system_truth": "presentation simulation; action timing and state come from canonical storyboard v2.1",
            "audio_strategy": "event sound may be synchronized in final edit; clip is rendered silent",
            "review_status": "generated_for_editorial_review",
            "clip_path": f"clips/{insert['id']}.mp4",
            "poster_path": f"posters/{insert['id']}.jpg",
        })

    library = {
        "schema": "tactevra.storyboard-shot-library.v1",
        "title": "Tactevra overview storyboard v2.1 editorial shot library",
        "source_manifest": SOURCE.relative_to(ROOT).as_posix(),
        "fps": canonical["fps"],
        "source_duration_seconds": canonical["duration_seconds"],
        "render_profiles": {
            "draft": {"resolution": [640, 360], "samples": 12, "codec": "h264", "quality": "medium"},
            "review": {"resolution": [960, 540], "samples": 32, "codec": "h264", "quality": "high"},
            "master": {"resolution": [1920, 1080], "samples": 64, "codec": "h264", "quality": "perc_lossless"},
        },
        "selection_guidance": {
            "primary": "preserves the current planned edit",
            "alternate": "offers a different scale or spatial reading without changing action",
            "insert": "short detail coverage intended to be cut inside its parent scene",
            "continuity_rule": "never join shots that imply a different robot, tool, device placement, state, or permit scope",
        },
        "asset_count": len(assets),
        "assets": assets,
    }
    OUTPUT.write_text(json.dumps(library, indent=2) + "\n", encoding="utf-8")
    print(f"WROTE {OUTPUT} ({len(assets)} assets)")


if __name__ == "__main__":
    main()
