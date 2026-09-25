"""Offline construction/validation of a distinct, boot-bound live selector.

This module has no transport or hardware access. Producing a selector does not
enable the controller route, which remains fail-closed pending release review.
"""
from __future__ import annotations

import re

from .reviewed_hover_manifest import (
    POSE_IDS, POSE_NAMES, decode_reviewed_hover_start,
    validate_manifest,
)
from .reviewed_hover_release_identity import verify_release_pair


_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_BOOT = re.compile(r"[0-9a-f]{32}\Z")
_WIRE = re.compile(
    rb"RCHL2:([0-9a-f]{32}):([0-9a-f]{2}):([0-9a-f]{2,32}):"
    rb"([0-9a-f]{64}):([0-9a-f]{64}):LIVE_NONCONTACT\Z"
)


def encode_live_admission(manifest: dict, *, boot: str, release_sha256: str,
                          authorize_noncontact_motion: bool) -> bytes:
    """Prepare exact signed-request body after an explicit release decision.

    The returned bytes are not a motion command. A future live route must
    independently verify every field and its request authentication.
    """
    if authorize_noncontact_motion is not True:
        raise ValueError("Explicit noncontact motion authorization required")
    if (type(boot) is not str or not _BOOT.fullmatch(boot) or
            boot == "0" * 32):
        raise ValueError("Fresh nonzero boot ID required")
    if (type(release_sha256) is not str or
            not _SHA256.fullmatch(release_sha256) or
            release_sha256 == "0" * 64):
        raise ValueError("Reviewed nonzero release digest required")
    reviewed = validate_manifest(manifest)
    recipe_hash = reviewed["manifest_sha256"]
    ids = bytes(POSE_IDS[name] for name in reviewed["pose_ids"])
    return (f"RCHL2:{boot}:{len(ids):02x}:{ids.hex()}:"
            f"{recipe_hash}:{release_sha256}:LIVE_NONCONTACT").encode("ascii")


def encode_live_admission_from_review(manifest: dict, *, boot: str,
                                      review_record: dict, compile_report: dict,
                                      source_bytes: dict, app_image: bytes,
                                      authorize_noncontact_motion: bool) -> bytes:
    """Use a separately verified review record and matching build outputs.

    This cannot attest that the image is installed. No network access occurs.
    The caller must verify the review export before passing its record here.
    """
    checked = verify_release_pair(review_record, compile_report=compile_report,
                                  source_bytes=source_bytes, app_image=app_image)
    reviewed = validate_manifest(manifest)
    if reviewed["manifest_sha256"] != review_record["recipe_sha256"]:
        raise ValueError("Reviewed release recipe differs")
    return encode_live_admission(manifest, boot=boot,
        release_sha256=checked["release_sha256"],
        authorize_noncontact_motion=authorize_noncontact_motion)


def decode_live_admission(body: bytes, *, boot: str,
                          release_sha256: str) -> dict:
    """Strictly validate an admission body without accepting an offline start."""
    if type(body) is not bytes:
        raise ValueError("Exact live admission bytes required")
    match = _WIRE.fullmatch(body)
    if not match:
        raise ValueError("Exact live admission body required")
    bound_boot, count_hex, ids_hex, recipe_hash, bound_release = (
        part.decode("ascii") for part in match.groups())
    if (bound_boot != boot or bound_release != release_sha256 or
            not _BOOT.fullmatch(boot) or boot == "0" * 32 or
            not _SHA256.fullmatch(release_sha256) or
            release_sha256 == "0" * 64):
        raise ValueError("Live admission binding differs")
    count = int(count_hex, 16)
    ids = bytes.fromhex(ids_hex)
    if not 1 <= count <= 16 or len(ids) != count or any(item >= 6 for item in ids):
        raise ValueError("Invalid live pose list")
    offline_wire = f"RCHM1:{count_hex}:{ids_hex}:{recipe_hash}".encode("ascii")
    manifest = decode_reviewed_hover_start(offline_wire)
    if encode_live_admission(manifest, boot=boot,
                             release_sha256=release_sha256,
                             authorize_noncontact_motion=True) != body:
        raise ValueError("Noncanonical live admission")
    return dict(schema="rocell.reviewed_hover_live_admission.v2",
                boot_id=boot, release_sha256=release_sha256,
                recipe_sha256=recipe_hash, pose_ids=[POSE_NAMES[item] for item in ids],
                requested_noncontact_motion=True, motion_authorized=False,
                contact_authorized=False,
                hardware_access=False, controller_support_verified=False)
