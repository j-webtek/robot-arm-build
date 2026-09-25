"""Decode and independently assess the exact native P0 -> T1 lift record."""
from __future__ import annotations

DOMAIN = b"RCLIFT0001"
RECORD_BYTES = 10 + 16 + 6 + 8 + 1 + 7 * (16 + 7 * 20)
SOURCE_GOALS = [2047, 2413, 1701, 2907, 1589, 2040, 2047]
SOURCE_POSITIONS = [2047, 2415, 1700, 2904, 1591, 2041, 2047]
TARGET_GOALS = [2047, 2348, 1766, 2907, 1654, 2040, 2047]
SELECTED = {1, 2, 4}


def decode_large_pose_lift_record(raw):
    if type(raw) is not bytes or len(raw) != RECORD_BYTES or raw[:10] != DOMAIN:
        raise ValueError("Invalid large-pose lift record framing")
    offset = 10
    def take(count):
        nonlocal offset
        value = raw[offset:offset + count];offset += count;return value
    boot = take(16).hex()
    targets = [int.from_bytes(take(2), "big") for _ in range(3)]
    sent_us = int.from_bytes(take(8), "big")
    writes = int.from_bytes(take(1), "big")
    poses = []
    for _ in range(7):
        started = int.from_bytes(take(8), "big");finished = int.from_bytes(take(8), "big")
        joints = []
        for servo_id in range(11, 18):
            position = int.from_bytes(take(2), "big");goal = int.from_bytes(take(2), "big")
            torque = int.from_bytes(take(1), "big");feedback = take(15)
            joints.append(dict(servo_id=servo_id, position=position, goal=goal,
                               torque=torque, feedback=feedback))
        poses.append(dict(started_us=started, finished_us=finished, joints=joints))
    if offset != len(raw) or targets != [2348, 1766, 1654] or writes != 1 or not sent_us:
        raise ValueError("Invalid large-pose lift record body")
    return dict(boot=boot, targets=targets, sent_us=sent_us, writes_attempted=writes,
                start=poses[:3], prewrite=poses[3], endpoint=poses[4:])


def _valid(pose):
    if (not pose["started_us"] or pose["finished_us"] < pose["started_us"] or
            pose["finished_us"] - pose["started_us"] > 300000):
        raise ValueError("Invalid sample time")
    for joint in pose["joints"]:
        if (joint["position"] > 4095 or joint["goal"] > 4095 or joint["torque"] != 1 or
                any(joint["feedback"][i] for i in (2, 3, 10)) or
                int.from_bytes(joint["feedback"][:2], "little") != joint["position"]):
            raise ValueError("Invalid or moving servo feedback")


def _stable(poses, after=0):
    if (poses[0]["started_us"] <= after or
            not 200000 <= poses[-1]["finished_us"] - poses[0]["started_us"] <= 1500000):
        raise ValueError("Invalid sample window")
    for n, pose in enumerate(poses):
        _valid(pose)
        if n and pose["started_us"] - poses[n-1]["finished_us"] < 100000:
            raise ValueError("Samples insufficiently spaced")
        for joint, first in zip(pose["joints"], poses[0]["joints"]):
            if joint["goal"] != first["goal"] or abs(joint["position"]-first["position"]) > 1:
                raise ValueError("Unstable sampled pose")


def assess_large_pose_lift_record(raw, *, expected_boot):
    record = decode_large_pose_lift_record(raw)
    if record["boot"] != expected_boot:
        raise ValueError("Large-pose lift identity mismatch")
    before, prewrite, after = record["start"], record["prewrite"], record["endpoint"]
    _stable(before);_valid(prewrite);_stable(after, record["sent_us"])
    if (prewrite["started_us"] <= before[-1]["finished_us"] or
            record["sent_us"] < prewrite["finished_us"] or
            record["sent_us"]-prewrite["finished_us"] > 100000):
        raise ValueError("Prewrite not bound to send")
    initial = before[-1]["joints"]
    for i, joint in enumerate(initial):
        if joint["goal"] != SOURCE_GOALS[i] or abs(joint["position"]-SOURCE_POSITIONS[i]) > 2:
            raise ValueError("Start differs from P0")
        immediate = prewrite["joints"][i]
        if immediate["goal"] != joint["goal"] or abs(immediate["position"]-joint["position"]) > 1:
            raise ValueError("Prewrite changed")
    for pose in after:
        for i, (joint, source) in enumerate(zip(pose["joints"], initial)):
            if i in SELECTED:
                command = TARGET_GOALS[i]-source["goal"];travel = joint["position"]-source["position"]
                if joint["goal"] != TARGET_GOALS[i] or travel*(1 if command > 0 else -1) < -1 or abs(travel) > 80:
                    raise ValueError("Selected joint exceeded envelope")
            elif joint["goal"] != source["goal"] or abs(joint["position"]-source["position"]) > 2:
                raise ValueError("Passive joint changed")
    final = after[-1]["joints"]
    deltas = [final[i]["position"]-initial[i]["position"] for i in range(7)]
    errors = [final[i]["position"]-TARGET_GOALS[i] for i in range(7)]
    for i in SELECTED:
        command = TARGET_GOALS[i]-initial[i]["goal"]
        if deltas[i]*(1 if command > 0 else -1) < 2 or abs(errors[i]) > 12:
            raise ValueError("T1 endpoint not established")
    return dict(schema="rocell.large_pose_lift_assessment.v1", boot=expected_boot,
                status="T1_JOINT_ENDPOINT_MEASURED", source_pose="P0", target_pose="T1",
                position_delta_counts=deltas, endpoint_error_counts=errors,
                synchronized_servo_ids=[12, 13, 15], physical_clearance_proven=False,
                continuation_authorized=False)
