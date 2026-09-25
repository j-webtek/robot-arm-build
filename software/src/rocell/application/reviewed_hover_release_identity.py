"""Offline source-to-image release binding for a future reviewed-hover image.

The release ID is derived from pre-build source/toolchain inputs, not from the
final app image (which cannot embed its own hash). Verification of a record is
not independent approval, proof of an installed image, or motion authority.
"""
from __future__ import annotations

import hashlib
import re

from .first_motion_contract import canonical


_HASH = re.compile(r"[0-9a-f]{64}\Z")
_SOURCE_PREFIX = "firmware/diagnostics/"
_REQUIRED_INPUTS = frozenset({
    "reviewed_hover_manifest.h", "reviewed_hover_owner.h",
    "reviewed_hover_routes.h", "reviewed_hover_composition.h",
    "reviewed_hover_board_adapter.h", "reviewed_hover_live_admission.h",
})
_APP_SLOT = 0x140000
_GENERATED_STAMP = "reviewed_hover_release_stamp.h"


def _hash(value: str) -> bool:
    return type(value) is str and _HASH.fullmatch(value) is not None


def derive_release_identity(*, source_hashes: dict, toolchain_lock_sha256: str,
                            recipe_sha256: str, build_profile: str) -> str:
    """Derive an embed-ready identity from an exact, pre-build source set."""
    required = {_SOURCE_PREFIX + name for name in _REQUIRED_INPUTS}
    if (type(source_hashes) is not dict or
            not required <= set(source_hashes) or
            not all(type(name) is str and (name.startswith(_SOURCE_PREFIX) or
                     name.startswith(".firmware-tools/")) and ".." not in name
                    for name in source_hashes) or
            any(name.endswith("/" + _GENERATED_STAMP) for name in source_hashes) or
            not all(_hash(value) for value in source_hashes.values()) or
            not _hash(toolchain_lock_sha256) or not _hash(recipe_sha256) or
            build_profile != "default-4mb-no-psram"):
        raise ValueError("Exact reviewed-hover release inputs required")
    identity = dict(schema="rocell.reviewed_hover_release_inputs.v1",
                    source_hashes=source_hashes,
                    toolchain_lock_sha256=toolchain_lock_sha256,
                    recipe_sha256=recipe_sha256, build_profile=build_profile)
    return hashlib.sha256(canonical(identity)).hexdigest()


def render_release_stamp(release_sha256: str) -> bytes:
    """Deterministic generated header; excluded from its own source identity."""
    if not _hash(release_sha256) or release_sha256 == "0" * 64:
        raise ValueError("Valid nonzero release identity required")
    values = ",".join("0x" + release_sha256[index:index + 2]
                      for index in range(0, 64, 2))
    return ("// Generated from a reviewed source/toolchain manifest; do not edit.\n"
            "#pragma once\n#include <cstdint>\nnamespace rocell_diag {\n"
            "static constexpr uint8_t reviewed_hover_release_sha256[32]={" + values + "};\n"
            "}\n").encode("ascii")


def verify_release_pair(record: dict, *, compile_report: dict,
                        source_bytes: dict, app_image: bytes) -> dict:
    """Check a pinned review record against independent build outputs.

    The caller must obtain the record from a separately verified, durable
    review export. This function will not create or approve a record.
    """
    fields = {"schema", "release_sha256", "app_sha256", "app_bytes",
              "app_offset", "app_slot_bytes", "recipe_sha256",
              "source_hashes", "toolchain_lock_sha256", "build_profile",
              "target", "compile_review_sha256", "hardware_access",
              "firmware_uploaded", "deployment_authorized"}
    if type(record) is not dict or set(record) != fields:
        raise ValueError("Exact release review fields required")
    if (record["schema"] != "rocell.reviewed_hover_release_review.v1" or
            record["hardware_access"] is not False or
            record["firmware_uploaded"] is not False or
            record["deployment_authorized"] is not False or
            record["app_offset"] != 0x10000 or
            record["app_slot_bytes"] != _APP_SLOT or
            type(record["app_bytes"]) is not int or
            not 0 < record["app_bytes"] <= _APP_SLOT or
            not _hash(record["app_sha256"]) or
            not _hash(record["compile_review_sha256"]) or
            type(record["target"]) is not str or
            not re.fullmatch(r"configured-diagnostic-candidate-r[1-9][0-9]{0,3}",
                             record["target"])):
        raise ValueError("Invalid reviewed-hover release review")
    release = derive_release_identity(
        source_hashes=record["source_hashes"],
        toolchain_lock_sha256=record["toolchain_lock_sha256"],
        recipe_sha256=record["recipe_sha256"],
        build_profile=record["build_profile"])
    if release != record["release_sha256"]:
        raise ValueError("Release identity differs")
    if (type(source_bytes) is not dict or set(source_bytes) != set(record["source_hashes"]) or
            any(type(data) is not bytes or
                hashlib.sha256(data).hexdigest() != record["source_hashes"][name]
                for name, data in source_bytes.items())):
        raise ValueError("Source bytes differ")
    if (type(app_image) is not bytes or len(app_image) != record["app_bytes"] or
            hashlib.sha256(app_image).hexdigest() != record["app_sha256"]):
        raise ValueError("App image differs")
    compiled_sources = compile_report.get("source_hashes", {}) if type(compile_report) is dict else {}
    if (type(compiled_sources) is not dict or
            any(type(name) is not str or type(digest) is not str
                for name, digest in compiled_sources.items())):
        raise ValueError("Invalid compile source manifest")
    stamp_sources = {name.replace("\\", "/"): digest
                     for name, digest in compiled_sources.items()
                     if name.replace("\\", "/").endswith("/" + _GENERATED_STAMP)}
    compiled_sources = {name.replace("\\", "/"): digest
                        for name, digest in compiled_sources.items()
                        if not name.replace("\\", "/").endswith("/" + _GENERATED_STAMP)}
    stamp_sha256 = hashlib.sha256(render_release_stamp(release)).hexdigest()
    if len(stamp_sources) != 1 or next(iter(stamp_sources.values())) != stamp_sha256:
        raise ValueError("Generated release stamp differs")
    if (type(compile_report) is not dict or compile_report.get("status") != "COMPILED" or
            compile_report.get("target") != record["target"] or
            compile_report.get("build_profile") != record["build_profile"] or
            compile_report.get("toolchain_lock_sha256") != record["toolchain_lock_sha256"] or
            compile_report.get("artifact_hashes", {}).get("RoArm-M3_example.ino.bin") !=
            record["app_sha256"] or
            compiled_sources != record["source_hashes"]):
        raise ValueError("Compile evidence differs")
    if hashlib.sha256(canonical(compile_report)).hexdigest() != record["compile_review_sha256"]:
        raise ValueError("Compile review digest differs")
    if bytes.fromhex(release) not in app_image:
        raise ValueError("Release identity absent from app image")
    return dict(schema="rocell.reviewed_hover_release_pair_check.v1",
                release_sha256=release, app_sha256=record["app_sha256"],
                source_count=len(source_bytes), image_verified=True,
                installed_image_verified=False, deployment_authorized=False,
                hardware_access=False)
