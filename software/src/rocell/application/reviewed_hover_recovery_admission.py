"""Offline exact r91 recovery manifest and boot/release-bound admission body.

Constructing this body does not attest to installation or authorize motion.
"""

import hashlib
import re

from .first_motion_contract import canonical


POSES = ["A_CLEAR", "A_HOVER", "A_DOWN", "A_HOVER", "A_CLEAR"]
_BOOT = re.compile(r"[0-9a-f]{32}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_WIRE = re.compile(
    rb"RCHR1:([0-9a-f]{32}):([0-9a-f]{64}):([0-9a-f]{64}):LIVE_NONCONTACT\Z")


def recovery_manifest() -> dict:
    return dict(schema="rocell.reviewed_hover_recovery_manifest.v1",
                source_pose="A_HOVER", pose_ids=POSES[:], speed=20,
                acceleration=1, maximum_writes=5,
                export_before_next=True, one_use_per_boot=True,
                hardware_access=False, motion_authorized=False)


def validate_recovery_manifest(document: dict) -> str:
    if type(document) is not dict or document != recovery_manifest():
        raise ValueError("Exact fixed recovery manifest required")
    return hashlib.sha256(canonical(document)).hexdigest()


def encode_recovery_admission(manifest: dict, *, boot: str,
                              release_sha256: str,
                              authorize_noncontact_motion: bool) -> bytes:
    if authorize_noncontact_motion is not True:
        raise ValueError("Explicit noncontact admission required")
    if (type(boot) is not str or not _BOOT.fullmatch(boot) or boot == "0" * 32
            or type(release_sha256) is not str
            or not _SHA.fullmatch(release_sha256)
            or release_sha256 == "0" * 64):
        raise ValueError("Nonzero boot and reviewed release required")
    digest = validate_recovery_manifest(manifest)
    return f"RCHR1:{boot}:{digest}:{release_sha256}:LIVE_NONCONTACT".encode("ascii")


def decode_recovery_admission(body: bytes, *, boot: str,
                              release_sha256: str) -> dict:
    if type(body) is not bytes:
        raise ValueError("Exact admission bytes required")
    match = _WIRE.fullmatch(body)
    if not match:
        raise ValueError("Malformed recovery admission")
    expected = encode_recovery_admission(recovery_manifest(), boot=boot,
        release_sha256=release_sha256, authorize_noncontact_motion=True)
    if body != expected:
        raise ValueError("Recovery admission binding differs")
    return dict(schema="rocell.reviewed_hover_recovery_admission.v1",
                boot_id=boot, release_sha256=release_sha256,
                recipe_sha256=match[2].decode("ascii"),
                pose_ids=POSES[:], motion_authorized=False,
                hardware_access=False)
