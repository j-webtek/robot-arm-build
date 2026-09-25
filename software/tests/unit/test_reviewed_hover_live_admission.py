"""Live-intent wire contract is distinct from the offline simulation selector."""
from copy import deepcopy
import hashlib

import pytest

from rocell.application.first_motion_contract import canonical
from rocell.application.reviewed_hover_live_admission import (
    decode_live_admission, encode_live_admission,
    encode_live_admission_from_review,
)
from rocell.application.reviewed_hover_manifest import ghost_key_manifest


BOOT = "ab" * 16
RELEASE = "cd" * 32


def wire(manifest=None):
    return encode_live_admission(manifest or ghost_key_manifest(), boot=BOOT,
                                 release_sha256=RELEASE,
                                 authorize_noncontact_motion=True)


def test_exact_live_intent_has_distinct_domain_and_stays_non_executable():
    body = wire()
    assert body.startswith(b"RCHL2:") and body.endswith(b":LIVE_NONCONTACT")
    parsed = decode_live_admission(body, boot=BOOT, release_sha256=RELEASE)
    assert parsed["pose_ids"] == ghost_key_manifest()["pose_ids"]
    assert parsed["requested_noncontact_motion"]
    assert not parsed["motion_authorized"]
    assert not parsed["hardware_access"]
    assert not parsed["controller_support_verified"]


@pytest.mark.parametrize("change", [
    lambda body: body.replace(b"RCHL2", b"RCHM1"),
    lambda body: body.replace(b"LIVE_NONCONTACT", b"LIVE_CONTACT"),
    lambda body: body.replace(b"ab" * 16, b"00" * 16),
    lambda body: body.replace(b"cd" * 32, b"00" * 32),
    lambda body: body[:-1],
    lambda body: body.upper(),
    lambda body: body.replace(b":10:", b":11:"),
    lambda body: body.replace(b":10:", b":00:"),
    lambda body: body.replace(b"cd" * 32, b"ef" * 32),
])
def test_live_wire_rejects_mismatch_or_mutation(change):
    with pytest.raises(ValueError):
        decode_live_admission(change(wire()), boot=BOOT, release_sha256=RELEASE)


@pytest.mark.parametrize("kwargs", [
    dict(boot="0" * 32), dict(boot="AB" * 16),
    dict(release_sha256="0" * 64), dict(release_sha256="CD" * 32),
    dict(authorize_noncontact_motion=False),
])
def test_encoder_requires_explicit_release_inputs(kwargs):
    inputs = dict(boot=BOOT, release_sha256=RELEASE,
                  authorize_noncontact_motion=True)
    inputs.update(kwargs)
    with pytest.raises(ValueError):
        encode_live_admission(ghost_key_manifest(), **inputs)


def test_unreviewed_recipe_cannot_be_wrapped_as_live():
    manifest = deepcopy(ghost_key_manifest())
    manifest["pose_ids"][0] = "B_DOWN"
    with pytest.raises(ValueError):
        wire(manifest)


def test_review_backed_encoder_rejects_recipe_or_image_mismatch():
    from test_reviewed_hover_release_identity import fixture
    record, compiled, sources, app = fixture()
    # Synthetic release review must bind to the actual recipe, not an arbitrary
    # digest that merely passes source/image pair checks.
    with pytest.raises(ValueError, match="recipe differs"):
        encode_live_admission_from_review(ghost_key_manifest(), boot=BOOT,
            review_record=record, compile_report=compiled, source_bytes=sources,
            app_image=app, authorize_noncontact_motion=True)
    record, compiled, sources, app = fixture(
        hashlib.sha256(canonical(ghost_key_manifest())).hexdigest())
    body = encode_live_admission_from_review(ghost_key_manifest(), boot=BOOT,
        review_record=record, compile_report=compiled, source_bytes=sources,
        app_image=app, authorize_noncontact_motion=True)
    assert decode_live_admission(body, boot=BOOT,
        release_sha256=record["release_sha256"])["pose_ids"]
    with pytest.raises(ValueError, match="App image differs"):
        encode_live_admission_from_review(ghost_key_manifest(), boot=BOOT,
            review_record=record, compile_report=compiled, source_bytes=sources,
            app_image=app+b"x", authorize_noncontact_motion=True)
