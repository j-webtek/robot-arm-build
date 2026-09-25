"""Offline contract for a future bounded, runtime-loaded hover campaign.

This module does not send commands. The installed r84 firmware does not accept
this manifest. Controller-side validation is required before any live use.
"""
from __future__ import annotations

import hashlib
import re

from .first_motion_contract import canonical
from .ghost_key_multitarget_recipe import (
    A_DOWN,A_HOVER,A_RETRACT,B_DOWN,B_HOVER,B_RETRACT,SOURCE_GOALS,
)


POSES = dict(A_CLEAR=A_RETRACT,A_HOVER=A_HOVER,A_DOWN=A_DOWN,
             B_CLEAR=B_RETRACT,B_HOVER=B_HOVER,B_DOWN=B_DOWN)
EDGES = frozenset({
    ("A_CLEAR","A_HOVER"),("A_CLEAR","B_HOVER"),
    ("A_HOVER","A_DOWN"),("A_HOVER","A_CLEAR"),
    ("A_DOWN","A_HOVER"),
    ("B_CLEAR","B_HOVER"),("B_CLEAR","A_HOVER"),
    ("B_HOVER","B_DOWN"),("B_HOVER","B_CLEAR"),
    ("B_DOWN","B_HOVER"),
})
MAX_LEGS = 16
POSE_IDS = {name: index for index, name in enumerate(
    ("A_CLEAR", "A_HOVER", "A_DOWN", "B_CLEAR", "B_HOVER", "B_DOWN"))}
POSE_NAMES = tuple(POSE_IDS)


def validate_manifest(document):
    if type(document) is not dict or set(document) != {
            "schema","source_pose","pose_ids","speed","acceleration",
            "maximum_writes","export_before_next","one_use_per_boot",
            "hardware_access","motion_authorized"}:
        raise ValueError("Exact offline manifest fields required")
    if (document["schema"] != "rocell.reviewed_hover_manifest.v1"
            or document["source_pose"] != "A_CLEAR"
            or type(document["speed"]) is not int or document["speed"] != 20
            or type(document["acceleration"]) is not int or document["acceleration"] != 1
            or type(document["maximum_writes"]) is not int or document["maximum_writes"] != MAX_LEGS
            or document["export_before_next"] is not True
            or document["one_use_per_boot"] is not True
            or document["hardware_access"] is not False
            or document["motion_authorized"] is not False):
        raise ValueError("Manifest policy differs")
    names = document["pose_ids"]
    if type(names) is not list or not 1 <= len(names) <= MAX_LEGS:
        raise ValueError("Finite pose list required")
    prior = "A_CLEAR"
    for leg,name in enumerate(names,1):
        if type(name) is not str or (prior,name) not in EDGES:
            raise ValueError(f"Unreviewed pose edge at leg {leg}")
        previous, target = POSES[prior],POSES[name]
        changed = [i for i in range(7) if previous[i] != target[i]]
        if (not changed or any(not 10 <= abs(target[i]-previous[i]) <= 60 for i in changed)
                or any(not 0 <= value <= 4095 for value in target)):
            raise ValueError(f"Unreviewed goal step at leg {leg}")
        prior = name
    if POSES[document["source_pose"]] != SOURCE_GOALS:
        raise ValueError("Source pose differs")
    return dict(schema="rocell.reviewed_hover_manifest_validation.v1",
        status="OFFLINE_MANIFEST_VALID_NOT_EXECUTABLE",
        source_goals=list(SOURCE_GOALS),
        targets=[list(POSES[name]) for name in names],
        pose_ids=names[:],leg_count=len(names),
        manifest_sha256=hashlib.sha256(canonical(document)).hexdigest(),
        controller_support_verified=False,hardware_access=False,motion_authorized=False)


def ghost_key_manifest():
    names = ["A_HOVER","A_DOWN","A_HOVER","A_CLEAR",
             "B_HOVER","B_DOWN","B_HOVER","B_CLEAR"] * 2
    document = dict(schema="rocell.reviewed_hover_manifest.v1",
        source_pose="A_CLEAR",pose_ids=names,speed=20,acceleration=1,
        maximum_writes=MAX_LEGS,export_before_next=True,one_use_per_boot=True,
        hardware_access=False,motion_authorized=False)
    validate_manifest(document)
    return document


def encode_reviewed_hover_start(document: dict) -> bytes:
    """Exact authenticated-route body; constructing it does not authorize motion."""
    reviewed = validate_manifest(document)
    ids = bytes(POSE_IDS[name] for name in reviewed["pose_ids"])
    return f"RCHM1:{len(ids):02x}:{ids.hex()}:{reviewed['manifest_sha256']}".encode("ascii")


def decode_reviewed_hover_start(body: bytes) -> dict:
    """Reject any wire body that is not the exact canonical reviewed policy."""
    if type(body) is not bytes:
        raise ValueError("Exact reviewed-hover start body required")
    match = re.fullmatch(rb"RCHM1:([0-9a-f]{2}):([0-9a-f]{2,32}):([0-9a-f]{64})", body)
    if not match:
        raise ValueError("Exact reviewed-hover start body required")
    count = int(match[1], 16)
    ids = bytes.fromhex(match[2].decode("ascii"))
    if not 1 <= count <= MAX_LEGS or len(ids) != count or any(value >= 6 for value in ids):
        raise ValueError("Invalid reviewed-hover pose list")
    document = dict(schema="rocell.reviewed_hover_manifest.v1",
        source_pose="A_CLEAR", pose_ids=[POSE_NAMES[value] for value in ids],
        speed=20, acceleration=1, maximum_writes=MAX_LEGS,
        export_before_next=True, one_use_per_boot=True,
        hardware_access=False, motion_authorized=False)
    if encode_reviewed_hover_start(document) != body:
        raise ValueError("Reviewed-hover manifest digest differs")
    return document
