"""Validate the deterministic 100-second storyboard and first-contact benchmark."""

from __future__ import annotations

import json
import math
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
    assert inserts, "at least one camera insert is required"
    insert_ranges: list[tuple[int, int]] = []
    for insert in inserts:
        parent = shots[insert["scene_id"] - 1]
        assert parent["start"] <= insert["start"] <= insert["end"] <= parent["end"]
        assert insert["rig"] in allowed_rigs
        assert insert["rig"] != parent["rig"]
        duration = insert["end"] - insert["start"] + 1
        assert duration <= 2 * fps, "camera inserts must be two seconds or shorter"
        assert insert["purpose"].strip(), "camera inserts require an editorial purpose"
        insert_ranges.append((insert["start"], insert["end"]))
        rig_frames[parent["rig"]] -= duration
        rig_frames[insert["rig"]] += duration
    for previous, current in zip(sorted(insert_ranges), sorted(insert_ranges)[1:]):
        assert previous[1] < current[0], "camera inserts may not overlap"
    assert sum(rig_frames.values()) == data["frame_end"]
    assert all(frame_count > 0 for frame_count in rig_frames.values())
    assert max(rig_frames.values()) <= 25 * fps, dict(rig_frames)
    assert shots[1]["rig"] == "macro"
    assert shots[4]["rig"] == "overhead"
    assert shots[6]["rig"] == "low_three_quarter"
    assert shots[7]["rig"] == "low_three_quarter"
    benchmark = data["benchmark"]
    assert benchmark["scene_id"] == 8
    assert benchmark["target"] == "keyboard:r"
    expected = ["transit", "align", "settle", "approach", "contact", "retract", "verify"]
    assert [phase["name"] for phase in benchmark["phases"]] == expected
    frames = [phase["frame"] for phase in benchmark["phases"]]
    benchmark_shot = shots[benchmark["scene_id"] - 1]
    assert frames == sorted(frames)
    assert benchmark_shot["start"] <= frames[0] <= frames[-1] <= benchmark_shot["end"]
    contact_frame = next(
        phase["frame"] for phase in benchmark["phases"] if phase["name"] == "contact"
    )
    assert any(
        insert["scene_id"] == 8
        and insert["rig"] == "macro"
        and insert["start"] <= contact_frame <= insert["end"]
        for insert in inserts
    ), "the first contact needs a bounded macro insert"
    assert any(
        insert["scene_id"] == 7 and insert["rig"] == "macro"
        for insert in inserts
    ), "scene 7 needs a bounded toolhead-detail insert"
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
    operator_display = data["operator_display_sequence"]
    assert operator_display["presentation_only"] is True
    placement = operator_display["placement"]
    assert placement["board_overlap"] is False
    assert placement["overhead_camera_visible"] is False
    center_x, center_y = placement["center_board_xy_mm"]
    width, height = placement["screen_size_mm"]
    yaw = math.radians(placement["yaw_degrees"])
    projected_half_width = (width / 2) * abs(math.cos(yaw)) + 9 * abs(math.sin(yaw))
    projected_half_depth = (width / 2) * abs(math.sin(yaw)) + 9 * abs(math.cos(yaw))
    assert center_x + projected_half_width <= 0, (
        "operator display must stay wholly left of the measured board"
    )
    # Keep the display outside the nominal robot's documented planar envelope.
    robot_x, robot_y = 305.0, 457.0
    nearest_x = center_x + projected_half_width
    nearest_y = min(max(robot_y, center_y - projected_half_depth),
                    center_y + projected_half_depth)
    clearance = math.hypot(robot_x - nearest_x, robot_y - nearest_y)
    assert clearance >= placement["minimum_robot_base_clearance_mm"]
    display_states = operator_display["states"]
    assert [state["name"] for state in display_states] == [
        "request console", "empty test pad", "test pad r", "test pad re",
        "test pad rea", "test pad read", "test pad ready",
    ]
    assert display_states[0]["start"] <= shots[1]["start"]
    assert display_states[0]["end"] >= shots[1]["end"]
    assert display_states[1]["start"] <= 960 <= display_states[1]["end"]
    assert display_states[0]["body"].startswith("REQUEST CONSOLE")
    assert display_states[1]["body"] == "LOCAL TEST PAD\n_"
    assert [state["body"].split("\n")[-1] for state in display_states[2:]] == [
        "r", "re", "rea", "read", "ready",
    ]
    for previous, current in zip(display_states, display_states[1:]):
        assert previous["end"] + 1 == current["start"]
    assert display_states[-1]["end"] == data["frame_end"]
    assert [state["start"] for state in display_states[2:]] == [1064, *contacts]
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
        "off-board stateful request-to-test-pad operator display, "
        "seven benchmark phases, four independently permitted rhythm contacts, "
        "one contact-free high-clearance crossing, and eleven independently "
        "permitted phone contacts with disclosed 2x montage timing"
    )


if __name__ == "__main__":
    main()
