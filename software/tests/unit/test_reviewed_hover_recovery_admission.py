import pytest

from rocell.application.reviewed_hover_recovery_admission import (
    decode_recovery_admission, encode_recovery_admission, recovery_manifest,
    validate_recovery_manifest,
)


BOOT = "ab" * 16
RELEASE = "cd" * 32


def test_exact_fixed_recovery_admission():
    manifest = recovery_manifest()
    digest = validate_recovery_manifest(manifest)
    wire = encode_recovery_admission(manifest, boot=BOOT,
        release_sha256=RELEASE, authorize_noncontact_motion=True)
    assert len(wire) == 184
    assert digest.encode() in wire
    parsed = decode_recovery_admission(wire, boot=BOOT, release_sha256=RELEASE)
    assert parsed["pose_ids"] == manifest["pose_ids"]
    assert not parsed["motion_authorized"]


@pytest.mark.parametrize("field", ["source_pose", "pose_ids", "speed",
                                   "maximum_writes", "hardware_access"])
def test_changed_manifest_rejected(field):
    manifest = recovery_manifest()
    manifest[field] = None
    with pytest.raises(ValueError):
        validate_recovery_manifest(manifest)


def test_replay_and_release_mismatch_rejected():
    wire = encode_recovery_admission(recovery_manifest(), boot=BOOT,
        release_sha256=RELEASE, authorize_noncontact_motion=True)
    for changed in (wire.replace(b"RCHR1", b"RCHL2"), wire.upper(), wire + b"x"):
        with pytest.raises(ValueError):
            decode_recovery_admission(changed, boot=BOOT, release_sha256=RELEASE)
    with pytest.raises(ValueError):
        decode_recovery_admission(wire, boot="ac" * 16, release_sha256=RELEASE)
    with pytest.raises(ValueError):
        decode_recovery_admission(wire, boot=BOOT, release_sha256="ce" * 32)
    with pytest.raises(ValueError):
        encode_recovery_admission(recovery_manifest(), boot=BOOT,
            release_sha256=RELEASE, authorize_noncontact_motion=False)
