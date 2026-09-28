"""Validate the deterministic 100-second storyboard and first-contact benchmark."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path


PATH = Path(__file__).with_name("storyboard_v21_shots.json")
HANDOFF_PATH = Path(__file__).with_name("ADVERTISING_STORYBOARD_HANDOFF.md")


def validate_handoff(shots: list[dict[str, object]]) -> None:
    """Keep the collaborator-facing scene table aligned with the canonical JSON."""
    text = HANDOFF_PATH.read_text(encoding="utf-8")
    rows: list[tuple[int, str, str]] = []
    for line in text.splitlines():
        match = re.match(r"^\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|", line)
        if match:
            rows.append((int(match.group(1)), match.group(2), match.group(3).strip(" `")))
    assert len(rows) == 17, "advertising handoff must contain exactly 17 scene rows"
    expected = [
        (shot["id"], shot["seconds"], shot["stage"] or "—") for shot in shots
    ]
    assert rows == expected, "advertising handoff scene IDs, timing, or stages drifted"
    assert "CHECK/ACT/VERIFY" not in text
    assert "Delivered" not in text


def main() -> None:
    data = json.loads(PATH.read_text(encoding="utf-8"))
    fps = data["fps"]
    shots = data["shots"]
    assert fps == 24
    assert data["duration_seconds"] == 100
    assert data["frame_start"] == 1
    assert data["frame_end"] == fps * data["duration_seconds"]
    assert len(shots) == 17
    assert [shot["id"] for shot in shots] == list(range(1, 18))
    assert shots[0]["start"] == 1
    assert shots[-1]["end"] == data["frame_end"]
    for previous, current in zip(shots, shots[1:]):
        assert previous["end"] + 1 == current["start"], (
            f"gap or overlap between scenes {previous['id']} and {current['id']}"
        )
    allowed_rigs = {
        "macro", "dolly", "arm_follow", "hero", "overhead", "low_three_quarter"
    }
    assert {shot["rig"] for shot in shots} == allowed_rigs
    # No reusable camera setup may dominate more than one quarter of the film.
    rig_frames: Counter[str] = Counter()
    for shot in shots:
        rig_frames[shot["rig"]] += shot["end"] - shot["start"] + 1
    inserts = data["camera_inserts"]
    assert len(inserts) == 1
    for insert in inserts:
        parent = shots[insert["scene_id"] - 1]
        assert parent["start"] <= insert["start"] <= insert["end"] <= parent["end"]
        assert insert["rig"] in allowed_rigs
        assert insert["rig"] != parent["rig"]
        duration = insert["end"] - insert["start"] + 1
        rig_frames[parent["rig"]] -= duration
        rig_frames[insert["rig"]] += duration
    assert rig_frames == Counter({
        "macro": 356,
        "hero": 528,
        "dolly": 504,
        "arm_follow": 504,
        "overhead": 168,
        "low_three_quarter": 340,
    })
    assert max(rig_frames.values()) <= 25 * fps, dict(rig_frames)
    assert shots[1]["rig"] == "macro"
    assert shots[4]["rig"] == "overhead"
    assert shots[6]["rig"] == "low_three_quarter"
    assert shots[7]["rig"] == "low_three_quarter"
    assert inserts[0] == {
        "scene_id": 8,
        "start": 1049,
        "end": 1068,
        "rig": "macro",
        "purpose": (
            "brief key-depression insert inside the low-three-quarter "
            "first-contact lesson"
        ),
    }
    benchmark = data["benchmark"]
    assert benchmark["scene_id"] == 8
    assert benchmark["target"] == "keyboard:r"
    expected = ["transit", "align", "settle", "approach", "contact", "retract", "verify"]
    assert [phase["name"] for phase in benchmark["phases"]] == expected
    frames = [phase["frame"] for phase in benchmark["phases"]]
    benchmark_shot = shots[benchmark["scene_id"] - 1]
    assert frames == sorted(frames)
    assert benchmark_shot["start"] <= frames[0] <= frames[-1] <= benchmark_shot["end"]
    rhythm = data["rhythm"]
    assert rhythm["scene_id"] == 9
    assert [target["key"] for target in rhythm["targets"]] == list("eady")
    contacts = [target["contact_frame"] for target in rhythm["targets"]]
    verifies = [target["verify_frame"] for target in rhythm["targets"]]
    rhythm_shot = shots[rhythm["scene_id"] - 1]
    assert contacts == [1178, 1220, 1262, 1304]
    assert all(contact < verify for contact, verify in zip(contacts, verifies))
    assert rhythm_shot["start"] <= contacts[0] < verifies[-1] <= rhythm_shot["end"]
    assert rhythm["permit_scope"] == "one contact"
    assert rhythm["next_target_authority"] == "preview only"
    assert rhythm["visual_shorthand"] == "permit plus verification tick only"
    crossing = data["crossing"]
    assert crossing["scene_id"] == 11
    assert (crossing["start_frame"], crossing["midpoint_frame"], crossing["end_frame"]) == (
        1465, 1528, 1608
    )
    crossing_shot = shots[crossing["scene_id"] - 1]
    assert crossing_shot["start"] == crossing["start_frame"]
    assert crossing_shot["end"] == crossing["end_frame"]
    assert crossing["minimum_authored_wrist_height_mm"] >= 255
    assert crossing["contact_authority"] == "none"
    phone = data["phone_sequence"]
    assert phone["scenes"] == [12, 13, 14]
    assert phone["phrase"] == "on my way"
    assert shots[11]["start"] <= phone["messages_app_contact_frame"] <= shots[11]["end"]
    assert len(phone["contact_frames"]) == len(phone["phrase"])
    assert phone["contact_frames"] == sorted(phone["contact_frames"])
    assert shots[11]["start"] <= phone["contact_frames"][0]
    assert phone["contact_frames"][-1] <= shots[12]["end"]
    assert shots[13]["start"] <= phone["send_contact_frame"] <= shots[13]["end"]
    assert phone["permit_scope"] == "one contact"
    assert phone["screen_check_before_each_contact"] is True
    assert phone["verify_after_each_state_change"] is True
    assert phone["ui_layout"] == {
        "orientation": "portrait",
        "header": "contact identity at top",
        "conversation_history_bubbles": 2,
        "composer": "immediately above software keyboard",
        "send": "right edge of composer",
        "sent_receipt": "outgoing bubble in conversation with sent tick",
    }
    assert phone["time_compression"] == {
        "scene": 13, "start_frame": 1850, "end_frame": 1968,
        "rate": "2x", "disclosed": True
    }
    assert phone["visual_shorthand_after_first_contact"] == (
        "permit plus verification tick only"
    )
    assert phone["runtime_locked_fields"] == [
        "speed", "contact_depth", "retry_policy", "timing"
    ]
    assert data["stage_vocabulary"] == ["UNDERSTAND", "LOCATE", "CHECK", "ACT", "VERIFY"]
    assert shots[1]["stage"] is None
    assert shots[3]["stage"] == "UNDERSTAND"
    assert all(shots[index]["stage"] == "ACT" for index in range(7, 14))
    assert (shots[12]["start"], shots[12]["end"]) == (1777, 1968)
    assert shots[14]["end"] - shots[14]["start"] + 1 == 6 * fps
    assert shots[15]["end"] - shots[15]["start"] + 1 == 3 * fps
    validate_handoff(shots)
    print(
        "PASS storyboard_v21: 17 contiguous scenes, 2400 frames, six rigs, "
        "no rig over 25 percent, synchronized advertising handoff, "
        "seven benchmark phases, four independently permitted rhythm contacts, "
        "one contact-free high-clearance crossing, and eleven independently "
        "permitted phone contacts with disclosed 2x montage timing"
    )


if __name__ == "__main__":
    main()
