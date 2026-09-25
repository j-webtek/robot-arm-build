"""One-use, export-gated multi-joint noncontact hover campaign."""
from __future__ import annotations

import hashlib

from .air_typing_multi_hover_recipe import PHASES, SOURCE_GOALS, SOURCE_POSITIONS, TARGETS
from .air_typing_r76_endpoint_rule import endpoint_joint_verified
from .air_typing_r78_source_rule import source_joint_verified
from .air_typing_r81_campaign import AirTypingElbowDirectionHost
from .large_pose_relief_record import _stable, _valid, decode_large_pose_relief_record


def assess_leg(raw: bytes, *, boot: str, leg: int, previous=None) -> dict:
    if type(leg) is not int or not 1 <= leg <= 5 or type(raw) is not bytes or len(raw) != 1130:
        raise ValueError("Invalid multi-hover record")
    if raw[:10] != b"RCAIRABA01" or raw[26] != leg:
        raise ValueError("Wrong multi-hover domain or ordinal")
    target = TARGETS[leg-1]
    if int.from_bytes(raw[27:29], "big") != target[4]:
        raise ValueError("Wrong multi-hover wrist target")
    framed = b"RCP4WRST01" + raw[10:26] + (1980).to_bytes(2, "big") + raw[29:]
    record = decode_large_pose_relief_record(framed, profile="P4")
    if record["boot"] != boot:
        raise ValueError("Wrong boot")
    before, pre, after = record["start"], record["prewrite"], record["endpoint"]
    _stable(before); _valid(pre); _stable(after, record["sent_us"])
    if not before[-1]["finished_us"] < pre["started_us"] <= pre["finished_us"] <= record["sent_us"]:
        raise ValueError("Prewrite chronology invalid")
    if record["sent_us"] - pre["finished_us"] > 100000:
        raise ValueError("Prewrite expired")
    if leg == 1:
        if previous is not None:
            raise ValueError("Unexpected prior leg")
        positions, goals = SOURCE_POSITIONS, SOURCE_GOALS
    else:
        if previous is None or previous.get("boot") != boot or previous.get("leg") != leg-1:
            raise ValueError("Missing verified previous leg")
        positions, goals = previous["final_positions"], previous["final_goals"]
        if before[0]["started_us"] <= previous["finished_us"]:
            raise ValueError("Replayed source samples")
    initial = before[-1]["joints"]
    for i, joint in enumerate(initial):
        if (not source_joint_verified(previous_position=positions[i], expected_goal=goals[i],
                                      current_position=joint["position"], current_goal=joint["goal"])
                or joint["torque"] != 1 or pre["joints"][i]["torque"] != 1):
            raise ValueError("Source changed")
        if (pre["joints"][i]["goal"] != joint["goal"] or
                abs(pre["joints"][i]["position"] - joint["position"]) > 1):
            raise ValueError("Prewrite changed")
    selected = [i for i in range(7) if target[i] != initial[i]["goal"]]
    expected = [3] if leg == 1 else [0, 1, 2, 3, 4]
    if selected != expected or any(not 10 <= abs(target[i]-initial[i]["goal"]) <= 60
                                   for i in selected):
        raise ValueError("Unreviewed multi-joint step")
    for sample in after:
        for i, joint in enumerate(sample["joints"]):
            if joint["goal"] != target[i] or joint["torque"] != 1:
                raise ValueError("Endpoint control differs")
            travel = joint["position"] - initial[i]["position"]
            if i in selected:
                direction = 1 if target[i] > initial[i]["goal"] else -1
                if travel*direction < -1 or abs(travel) > 72:
                    raise ValueError("Selected direction or travel invalid")
            elif abs(travel) > 2:
                raise ValueError("Passive drift")
    final = after[-1]["joints"]
    for i in selected:
        if not endpoint_joint_verified(initial_goal=initial[i]["goal"],
                initial_position=initial[i]["position"], target_goal=target[i],
                final_position=final[i]["position"]):
            raise ValueError("Selected endpoint not verified")
    return dict(status="MULTI_HOVER_LEG_ENDPOINT_VERIFIED", boot=boot, leg=leg,
                phase=PHASES[leg-1], target_goals=list(target), selected_joints=selected,
                final_positions=[joint["position"] for joint in final],
                final_goals=[joint["goal"] for joint in final],
                target_errors_counts=[final[i]["position"]-target[i] for i in range(7)],
                finished_us=after[-1]["finished_us"], record_sha256=hashlib.sha256(raw).hexdigest(),
                physical_clearance_verified=False, physical_accuracy_verified=False)


class AirTypingMultiHoverHost(AirTypingElbowDirectionHost):
    route = "/rocell/air-multi-hover/"
    selector = b"AIRM5"
    leg_count = 5
    mode_prefix = "r84-multi-hover"
    attachment_prefix = "multi-hover"
    completion_status = "MULTI_HOVER_COMPLETE"
    assess = staticmethod(assess_leg)
