"""Independent offline verifier for the proposed RCHOVERR01 controller record.

This is not a live transport or authority to move the arm. It deliberately
checks the raw seven-joint evidence rather than trusting a controller status.
"""
from __future__ import annotations

import hashlib

from .large_pose_relief_record import _stable, _valid
from .reviewed_hover_manifest import POSES, validate_manifest


DOMAIN = b"RCHOVERR01"
RECORD_BYTES = 1163
POSE_NAMES = ("A_CLEAR", "A_HOVER", "A_DOWN", "B_CLEAR", "B_HOVER", "B_DOWN")
INITIAL_POSITIONS = (2040, 2082, 2033, 2609, 2233, 2041, 2047)


def _hex_bytes(value: str, count: int, label: str) -> bytes:
    if type(value) is not str or len(value) != count * 2:
        raise ValueError(f"Invalid {label}")
    try:
        raw = bytes.fromhex(value)
    except ValueError as error:
        raise ValueError(f"Invalid {label}") from error
    if len(raw) != count or raw.hex() != value.lower() or not any(raw):
        raise ValueError(f"Invalid {label}")
    return raw


def decode_reviewed_hover_record(raw: bytes) -> dict:
    if type(raw) is not bytes or len(raw) != RECORD_BYTES or raw[:10] != DOMAIN:
        raise ValueError("Invalid reviewed-hover framing")
    offset = 10

    def take(count: int) -> bytes:
        nonlocal offset
        chunk = raw[offset:offset + count]
        offset += count
        return chunk

    boot = take(16).hex()
    manifest_sha256 = take(32).hex()
    leg = take(1)[0]
    pose_id = take(1)[0]
    wrist_goal = int.from_bytes(take(2), "big")
    sent_us = int.from_bytes(take(8), "big")
    writes = take(1)[0]
    samples = []
    for _ in range(7):
        started_us = int.from_bytes(take(8), "big")
        finished_us = int.from_bytes(take(8), "big")
        joints = []
        for servo_id in range(11, 18):
            position = int.from_bytes(take(2), "big")
            goal = int.from_bytes(take(2), "big")
            torque = take(1)[0]
            feedback = take(15)
            joints.append(dict(servo_id=servo_id, position=position, goal=goal,
                               torque=torque, feedback=feedback))
        samples.append(dict(started_us=started_us, finished_us=finished_us,
                            joints=joints))
    if offset != RECORD_BYTES or not sent_us or writes != 1:
        raise ValueError("Invalid reviewed-hover body")
    return dict(boot=boot, manifest_sha256=manifest_sha256, leg=leg,
                pose_id=pose_id, wrist_goal=wrist_goal, sent_us=sent_us,
                writes_attempted=writes, before=samples[:3], prewrite=samples[3],
                after=samples[4:])


def _assess_bound_leg(raw: bytes, *, pose_ids: list[str], manifest_sha256: str,
                      source_goals: tuple[int, ...] | list[int],
                      source_positions: tuple[int, ...] | list[int],
                      source_tolerance: int, boot: str, leg: int,
                      previous: dict | None) -> dict:
    expected_boot = _hex_bytes(boot, 16, "boot identity").hex()
    expected_digest = _hex_bytes(manifest_sha256, 32,
                                 "manifest digest").hex()
    if type(leg) is not int or not 1 <= leg <= len(pose_ids):
        raise ValueError("Invalid leg ordinal")
    record = decode_reviewed_hover_record(raw)
    pose_name = pose_ids[leg - 1]
    if (record["boot"] != expected_boot or record["manifest_sha256"] != expected_digest
            or record["leg"] != leg or record["pose_id"] != POSE_NAMES.index(pose_name)):
        raise ValueError("Record binding differs")
    target = list(POSES[pose_name])
    if record["wrist_goal"] != target[4]:
        raise ValueError("Wrong selected wrist goal")
    before, pre, after = record["before"], record["prewrite"], record["after"]
    _stable(before)
    _valid(pre)
    _stable(after, record["sent_us"])
    if not (before[-1]["finished_us"] < pre["started_us"] <=
            pre["finished_us"] <= record["sent_us"] < after[0]["started_us"]):
        raise ValueError("Invalid command chronology")
    if record["sent_us"] - pre["finished_us"] > 100000:
        raise ValueError("Expired prewrite")
    if leg == 1:
        if previous is not None:
            raise ValueError("Unexpected prior record")
    else:
        if (type(previous) is not dict or previous.get("status") !=
                "REVIEWED_HOVER_LEG_VERIFIED" or previous.get("boot") != expected_boot
                or previous.get("manifest_sha256") != expected_digest
                or previous.get("leg") != leg - 1
                or before[0]["started_us"] <= previous.get("finished_us", 0)):
            raise ValueError("Missing fresh, verified prior leg")
        source_positions = previous["final_positions"]
        source_goals = previous["final_goals"]
        source_tolerance = 1
    initial = before[-1]["joints"]
    for index, joint in enumerate(initial):
        if (joint["goal"] != source_goals[index] or
                abs(joint["position"] - source_positions[index]) > source_tolerance):
            raise ValueError("Source pose differs")
        immediate = pre["joints"][index]
        if (immediate["goal"] != joint["goal"] or
                abs(immediate["position"] - joint["position"]) > 1 or
                immediate["torque"] != joint["torque"]):
            raise ValueError("Prewrite pose changed")
    selected = [index for index in range(7) if target[index] != initial[index]["goal"]]
    if (not selected or any(not 10 <= abs(target[index] - initial[index]["goal"]) <= 60
                            for index in selected)):
        raise ValueError("Unreviewed selected-joint step")
    for sample in after:
        for index, joint in enumerate(sample["joints"]):
            if joint["goal"] != target[index]:
                raise ValueError("Endpoint goal differs")
            travel = joint["position"] - initial[index]["position"]
            if index in selected:
                direction = 1 if target[index] > initial[index]["goal"] else -1
                if travel * direction < -1 or abs(travel) > 92:
                    raise ValueError("Selected joint exceeded travel envelope")
            elif abs(travel) > 2:
                raise ValueError("Passive joint drift")
    final = after[-1]["joints"]
    for index in selected:
        direction = 1 if target[index] > initial[index]["goal"] else -1
        travel = final[index]["position"] - initial[index]["position"]
        if travel * direction < 2 or abs(final[index]["position"] - target[index]) > 12:
            raise ValueError("Selected endpoint not established")
    return dict(status="REVIEWED_HOVER_LEG_VERIFIED", boot=expected_boot,
                manifest_sha256=expected_digest, leg=leg, pose_id=pose_name,
                target_goals=target, selected_joints=selected,
                final_positions=[joint["position"] for joint in final],
                final_goals=[joint["goal"] for joint in final],
                target_errors_counts=[final[index]["position"] - target[index]
                                      for index in range(7)],
                finished_us=after[-1]["finished_us"],
                record_sha256=hashlib.sha256(raw).hexdigest(),
                physical_clearance_verified=False, physical_accuracy_verified=False)


def assess_reviewed_hover_leg(raw: bytes, *, manifest: dict, boot: str,
                              leg: int, previous: dict | None = None) -> dict:
    reviewed = validate_manifest(manifest)
    return _assess_bound_leg(raw, pose_ids=reviewed["pose_ids"],
        manifest_sha256=reviewed["manifest_sha256"],
        source_goals=POSES["A_CLEAR"], source_positions=INITIAL_POSITIONS,
        source_tolerance=3, boot=boot, leg=leg, previous=previous)
