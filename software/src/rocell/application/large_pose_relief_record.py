"""Decode and independently assess the exact native T1 -> P1 relief record."""
from __future__ import annotations

DOMAIN = b"RCRELIEF01"
RECORD_BYTES = 10 + 16 + 4 + 8 + 1 + 7 * (16 + 7 * 20)
SOURCE_GOALS = [2047, 2348, 1766, 2907, 1654, 2040, 2047]
SOURCE_POSITIONS = [2047, 2357, 1759, 2904, 1652, 2041, 2047]
TARGET_GOALS = [2047, 2348, 1766, 2842, 1719, 2040, 2047]
SELECTED = {3, 4}


def reviewed_profile(profile):
    if profile == 'P4':
        from .p4_wrist_review import SOURCE_GOALS as wrist_source, SOURCE_POSITIONS as wrist_positions, TARGET_GOALS as wrist_targets
        return (b'RCP4WRST01', list(wrist_source), list(wrist_positions), list(wrist_targets), {4}, 'P4E')
    if profile == 'P4E':
        from .p4_extension_review import SOURCE_GOALS as elbow_source, SOURCE_POSITIONS as elbow_positions, INTERMEDIATE_GOALS as elbow_targets
        return (b'RCP4ELBW01', list(elbow_source), list(elbow_positions), list(elbow_targets), {3}, 'T4')
    if profile == 'T4':
        from .t4_wrist_review import SOURCE_GOALS as wrist_source, SOURCE_POSITIONS as wrist_positions, TARGET_GOALS as wrist_targets
        return (b'RCT4WRST01', list(wrist_source), list(wrist_positions), list(wrist_targets), {4}, 'T4L')
    if profile == 'T4L':
        from .t4_lift_review import SOURCE_GOALS as lift_source, SOURCE_POSITIONS as lift_positions, INTERMEDIATE_GOALS as lift_targets
        return (b'RCT4LIFT01', list(lift_source), list(lift_positions), list(lift_targets), {1,2}, 'P3')
    if profile == 'P1':
        return (DOMAIN, SOURCE_GOALS, SOURCE_POSITIONS, TARGET_GOALS, SELECTED, 'T1')
    if profile == 'P2L':
        return (b'RCP2LIFT01', [2047,2348,1766,2842,1719,2040,2047],
                [2047,2356,1759,2844,1720,2041,2047],
                [2047,2283,1831,2842,1719,2040,2047], {1,2}, 'P1')
    if profile == 'P2':
        from .p2_wrist_review import SOURCE_GOALS as wrist_source, SOURCE_POSITIONS as wrist_positions, TARGET_GOALS as wrist_targets
        return (b'RCP2WRST01', list(wrist_source), list(wrist_positions), list(wrist_targets), {4}, 'P2L')
    if profile == 'P3E':
        from .p3_extension_review import SOURCE_GOALS as elbow_source, SOURCE_POSITIONS as elbow_positions, INTERMEDIATE_GOALS as elbow_targets
        return (b'RCP3ELBW01', list(elbow_source), list(elbow_positions), list(elbow_targets), {3}, 'P2')
    if profile == 'P3':
        from .p3_wrist_review import SOURCE_GOALS as wrist_source, SOURCE_POSITIONS as wrist_positions, TARGET_GOALS as wrist_targets
        return (b'RCP3WRST01', list(wrist_source), list(wrist_positions), list(wrist_targets), {4}, 'P3E')
    raise ValueError('Unknown reviewed movement profile')


def record_bytes(profile='P1'):
    return RECORD_BYTES + 2*(len(reviewed_profile(profile)[4])-2)


def decode_large_pose_relief_record(raw, *, profile='P1'):
    domain, _, _, goals, selected, _ = reviewed_profile(profile)
    if type(raw) is not bytes or len(raw) != record_bytes(profile) or raw[:10] != domain:
        raise ValueError("Invalid large-pose relief record framing")
    offset = 10
    def take(count):
        nonlocal offset
        value = raw[offset:offset + count];offset += count;return value
    boot = take(16).hex()
    targets = [int.from_bytes(take(2), "big") for _ in range(len(selected))]
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
    if offset != len(raw) or targets != [goals[i] for i in sorted(selected)] or writes != 1 or not sent_us:
        raise ValueError("Invalid large-pose relief record body")
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


def assess_large_pose_relief_record(raw, *, expected_boot, profile='P1'):
    _, source_goals, source_positions, target_goals, selected, source_name = reviewed_profile(profile)
    record = decode_large_pose_relief_record(raw, profile=profile)
    if record["boot"] != expected_boot:
        raise ValueError("Large-pose relief identity mismatch")
    before, prewrite, after = record["start"], record["prewrite"], record["endpoint"]
    _stable(before);_valid(prewrite);_stable(after, record["sent_us"])
    if (prewrite["started_us"] <= before[-1]["finished_us"] or
            record["sent_us"] < prewrite["finished_us"] or
            record["sent_us"]-prewrite["finished_us"] > 100000):
        raise ValueError("Prewrite not bound to send")
    initial = before[-1]["joints"]
    for i, joint in enumerate(initial):
        if joint["goal"] != source_goals[i] or abs(joint["position"]-source_positions[i]) > 3:
            raise ValueError("Start differs from "+source_name)
        immediate = prewrite["joints"][i]
        if immediate["goal"] != joint["goal"] or abs(immediate["position"]-joint["position"]) > 1:
            raise ValueError("Prewrite changed")
    for pose in after:
        for i, (joint, source) in enumerate(zip(pose["joints"], initial)):
            if i in selected:
                command = target_goals[i]-source["goal"];travel = joint["position"]-source["position"]
                if joint["goal"] != target_goals[i] or travel*(1 if command > 0 else -1) < -1 or abs(travel) > 80:
                    raise ValueError("Selected joint exceeded envelope")
            elif joint["goal"] != source["goal"] or abs(joint["position"]-source["position"]) > 2:
                raise ValueError("Passive joint changed")
    final = after[-1]["joints"]
    deltas = [final[i]["position"]-initial[i]["position"] for i in range(7)]
    errors = [final[i]["position"]-target_goals[i] for i in range(7)]
    for i in selected:
        command = target_goals[i]-initial[i]["goal"]
        if deltas[i]*(1 if command > 0 else -1) < 2 or abs(errors[i]) > 12:
            raise ValueError(profile+" endpoint not established")
    return dict(schema="rocell.large_pose_relief_assessment.v1", boot=expected_boot,
                status=profile+"_JOINT_ENDPOINT_MEASURED", source_pose=source_name, target_pose=profile,
                position_delta_counts=deltas, endpoint_error_counts=errors,
                synchronized_servo_ids=[11+i for i in sorted(selected)], physical_clearance_proven=False,
                continuation_authorized=False)
