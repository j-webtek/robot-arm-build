"""Source-derived release identity cannot be echoed from a start request."""
from copy import deepcopy
import hashlib

import pytest

from rocell.application.first_motion_contract import canonical
from rocell.application.reviewed_hover_release_identity import (
    derive_release_identity, render_release_stamp, verify_release_pair,
)


NAMES = (
    "reviewed_hover_manifest.h", "reviewed_hover_owner.h",
    "reviewed_hover_routes.h", "reviewed_hover_composition.h",
    "reviewed_hover_board_adapter.h", "reviewed_hover_live_admission.h",
)


def fixture(recipe="cd" * 32):
    sources = {"firmware/diagnostics/" + name: name.encode() for name in NAMES}
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in sources.items()}
    lock = "ab" * 32
    release = derive_release_identity(source_hashes=hashes,
        toolchain_lock_sha256=lock, recipe_sha256=recipe,
        build_profile="default-4mb-no-psram")
    app = b"synthetic-app-image" + bytes.fromhex(release)
    record = dict(schema="rocell.reviewed_hover_release_review.v1",
        release_sha256=release, app_sha256=hashlib.sha256(app).hexdigest(),
        app_bytes=len(app), app_offset=0x10000, app_slot_bytes=0x140000,
        recipe_sha256=recipe, source_hashes=hashes,
        toolchain_lock_sha256=lock, build_profile="default-4mb-no-psram",
        target="configured-diagnostic-candidate-r85",
        compile_review_sha256="ef" * 32,
        hardware_access=False, firmware_uploaded=False,
        deployment_authorized=False)
    compiled = dict(status="COMPILED", target=record["target"],
                    build_profile=record["build_profile"],
                    toolchain_lock_sha256=lock,
                    artifact_hashes={"RoArm-M3_example.ino.bin":record["app_sha256"]},
                    source_hashes={**hashes,
                        "firmware/diagnostics/reviewed_hover_release_stamp.h":
                        hashlib.sha256(render_release_stamp(release)).hexdigest()})
    record["compile_review_sha256"] = hashlib.sha256(canonical(compiled)).hexdigest()
    return record, compiled, sources, app


def test_review_pair_has_distinct_source_and_image_identity():
    record, compiled, sources, app = fixture()
    checked = verify_release_pair(record, compile_report=compiled,
                                  source_bytes=sources, app_image=app)
    assert checked["release_sha256"] != checked["app_sha256"]
    assert checked["image_verified"]
    assert not checked["installed_image_verified"]
    assert not checked["deployment_authorized"]


@pytest.mark.parametrize("mutation", [
    lambda r, c, s, a: (r.update(release_sha256="00" * 32), a),
    lambda r, c, s, a: (r.update(app_sha256="00" * 32), a),
    lambda r, c, s, a: (r.update(deployment_authorized=True), a),
    lambda r, c, s, a: (r.update(app_slot_bytes=1), a),
    lambda r, c, s, a: (c.update(status="FAILED"), a),
    lambda r, c, s, a: (c["artifact_hashes"].update({"RoArm-M3_example.ino.bin":"00"*32}), a),
    lambda r, c, s, a: (c["source_hashes"].update({".firmware-tools/extra.cpp":"00"*32}), a),
    lambda r, c, s, a: (c["source_hashes"].update({
        "firmware/diagnostics/reviewed_hover_release_stamp.h":"00"*32}), a),
    lambda r, c, s, a: (s.update({next(iter(s)):b"changed"}), a),
    lambda r, c, s, a: (None, a+b"changed"),
])
def test_pair_rejects_mismatched_or_self_authorized_evidence(mutation):
    record, compiled, sources, app = fixture()
    _, app = mutation(record, compiled, sources, app)
    with pytest.raises(ValueError):
        verify_release_pair(record, compile_report=compiled,
                            source_bytes=sources, app_image=app)


def test_release_input_set_is_exact_and_sensitive_to_source_changes():
    record, _, _, _ = fixture()
    mutated = deepcopy(record["source_hashes"])
    key = next(iter(mutated))
    mutated[key] = "00" * 32
    assert derive_release_identity(source_hashes=mutated,
        toolchain_lock_sha256=record["toolchain_lock_sha256"],
        recipe_sha256=record["recipe_sha256"],
        build_profile=record["build_profile"]) != record["release_sha256"]
    del mutated[key]
    with pytest.raises(ValueError):
        derive_release_identity(source_hashes=mutated,
            toolchain_lock_sha256=record["toolchain_lock_sha256"],
            recipe_sha256=record["recipe_sha256"],
            build_profile=record["build_profile"])
