"""Read-only orphan/cwd inventory checks, not M1 durability qualification."""

from types import SimpleNamespace

import pytest

from rocell.application import commissioning_rehearsal_reopen as reopen
from rocell.application.physical_onboarding_durability import (
    PhysicalOnboardingDurabilityError,
)


def receipt(attempt="attempt-one"):
    return SimpleNamespace(
        document=lambda: {
            "schema": "rocell.rehearsal_owned_feedback_receipt.v1",
            "attempt_result": {"attempt_id": attempt},
        }
    )


def test_no_owned_directory_or_receipt_requires_no_mutation(tmp_path):
    reopen._verify_owned_feedback_directory(tmp_path, [])
    assert list(tmp_path.iterdir()) == []


def test_prepermit_orphan_directory_is_read_only_hold_not_new_campaign(tmp_path):
    orphan = tmp_path / "owned-arm-feedback"
    orphan.mkdir()
    before = orphan.stat()
    with pytest.raises(reopen.RehearsalReopenError) as error:
        reopen._verify_owned_feedback_directory(tmp_path, [])
    assert error.value.code == "ORPHAN_OWNED_ARM_DIRECTORY"
    assert orphan.stat().st_ino == before.st_ino
    assert list(orphan.iterdir()) == []


def test_owned_receipt_requires_original_directory(tmp_path):
    with pytest.raises(reopen.RehearsalReopenError) as error:
        reopen._verify_owned_feedback_directory(tmp_path, [receipt()])
    assert error.value.code == "OWNED_ARM_DIRECTORY_MISSING"


@pytest.mark.parametrize(
    "names", [[], ["other-attempt"], ["owned-arm-attempt-one", "extra"]]
)
def test_only_exact_retained_attempt_directory_is_allowed(tmp_path, names):
    root = tmp_path / "owned-arm-feedback"
    root.mkdir()
    for name in names:
        (root / name).mkdir()
    with pytest.raises(reopen.RehearsalReopenError) as error:
        reopen._verify_owned_feedback_directory(tmp_path, [receipt()])
    assert error.value.code == "OWNED_ARM_DIRECTORY_MISMATCH"
    assert sorted(path.name for path in root.iterdir()) == sorted(names)


def test_successful_empty_attempt_directory_is_observed_without_write(tmp_path):
    root = tmp_path / "owned-arm-feedback"
    child = root / "owned-arm-attempt-one"
    child.mkdir(parents=True)
    before = (root.stat().st_mtime_ns, child.stat().st_mtime_ns)
    reopen._verify_owned_feedback_directory(tmp_path, [receipt()])
    assert (root.stat().st_mtime_ns, child.stat().st_mtime_ns) == before


def test_unexpected_attempt_contents_are_held_not_cleaned(tmp_path):
    child = tmp_path / "owned-arm-feedback" / "owned-arm-attempt-one"
    child.mkdir(parents=True)
    (child / "unexpected").mkdir()
    with pytest.raises(reopen.RehearsalReopenError) as error:
        reopen._verify_owned_feedback_directory(tmp_path, [receipt()])
    assert error.value.code == "OWNED_ARM_DIRECTORY_NOT_EMPTY"
    assert (child / "unexpected").is_dir()


def test_linked_owned_directory_is_rejected(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "owned-arm-feedback"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("Symlink creation requires Windows developer mode")
    with pytest.raises(PhysicalOnboardingDurabilityError, match="symlink"):
        reopen._verify_owned_feedback_directory(tmp_path, [receipt()])
    assert link.is_symlink() and target.is_dir()
