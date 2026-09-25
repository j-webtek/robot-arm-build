"""Fresh-read regression for the single-walk qualified storage read path.

Real NTFS qualification/readers are used. Fault injection changes only the
particular observed condition being rejected, never a successful approval.
No camera, arm, USB enumeration or device owner is constructed.
"""

import os
from pathlib import Path

import pytest

from rocell.application import physical_onboarding_durability as durability
from rocell.application.physical_onboarding_storage import (
    PhysicalOnboardingStorageError,
)
from test_physical_onboarding_storage import _adapter


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Actual Windows NTFS reader")


@pytest.fixture
def store(tmp_path):
    root, publication = _adapter(tmp_path)
    ledger = root / "ledger"
    ledger.mkdir()
    (ledger / "record.bin").write_bytes(b"first")
    return root, ledger, publication


def test_each_read_rechecks_qualification_and_walks_selected_root_once(
    store, monkeypatch
):
    root, ledger, publication = store
    actual_root = durability.safe_root
    actual_volume = durability._windows_volume_identity
    roots = []
    volumes = []

    def observe_root(path, **kwargs):
        roots.append(path)
        return actual_root(path, **kwargs)

    def observe_volume(path):
        volumes.append(path)
        return actual_volume(path)

    monkeypatch.setattr(durability, "safe_root", observe_root)
    monkeypatch.setattr(durability, "_windows_volume_identity", observe_volume)
    for _ in range(2):
        assert (
            publication.read_bounded(ledger, "record.bin", maximum_bytes=16) == b"first"
        )
    assert roots == [root, ledger, root, ledger]
    assert volumes == [root, root]


def test_replacement_bytes_are_read_fresh(store):
    _, ledger, publication = store
    assert publication.read_bounded(ledger, "record.bin", maximum_bytes=16) == b"first"
    replacement = ledger / "replacement.bin"
    replacement.write_bytes(b"second")
    os.replace(replacement, ledger / "record.bin")
    assert publication.read_bounded(ledger, "record.bin", maximum_bytes=16) == b"second"


@pytest.mark.parametrize("position", ["root", "relative-directory"])
def test_real_junction_is_rejected_after_a_successful_read(store, position):
    import _winapi

    _, ledger, publication = store
    publication.read_bounded(ledger, "record.bin", maximum_bytes=16)
    if position == "root":
        destination = ledger.with_name("preserved-ledger")
        ledger.rename(destination)
        junction = ledger
        relative = "record.bin"
    else:
        destination = ledger / "preserved-subdirectory"
        destination.mkdir()
        (destination / "record.bin").write_bytes(b"first")
        junction = ledger / "linked-directory"
        relative = "linked-directory/record.bin"
    _winapi.CreateJunction(str(destination), str(junction))
    try:
        with pytest.raises(
            durability.PhysicalOnboardingDurabilityError, match="reparse"
        ):
            publication.read_bounded(ledger, relative, maximum_bytes=16)
    finally:
        # Remove only this exact test-created junction, preserving its target.
        junction.rmdir()
    assert destination.is_dir()


def test_changed_volume_after_success_is_rejected(store, monkeypatch):
    _, ledger, publication = store
    publication.read_bounded(ledger, "record.bin", maximum_bytes=16)
    actual = durability._windows_volume_identity

    def changed_volume(path):
        filesystem, identity = actual(path)
        return filesystem, identity + "-changed"

    monkeypatch.setattr(durability, "_windows_volume_identity", changed_volume)
    with pytest.raises(
        durability.DurabilityQualificationError, match="another deployment volume"
    ):
        publication.read_bounded(ledger, "record.bin", maximum_bytes=16)


@pytest.mark.parametrize("fault", ["missing", "file", "hardlink", "oversized"])
def test_changed_root_or_file_after_success_is_rejected(store, fault):
    _, ledger, publication = store
    publication.read_bounded(ledger, "record.bin", maximum_bytes=16)
    if fault in {"missing", "file"}:
        ledger.rename(ledger.with_name("preserved-ledger"))
        if fault == "file":
            ledger.write_bytes(b"not a directory")
    elif fault == "hardlink":
        os.link(ledger / "record.bin", ledger / "second-link.bin")
    else:
        (ledger / "record.bin").write_bytes(b"x" * 17)
    with pytest.raises(durability.PhysicalOnboardingDurabilityError):
        publication.read_bounded(ledger, "record.bin", maximum_bytes=16)


def test_opened_handle_still_rejects_hardlink_created_after_path_checks(
    store, monkeypatch
):
    _, ledger, publication = store
    actual_open = durability._windows_open_regular_read_handle

    def substitute(path, **kwargs):
        os.link(path, ledger / "substitution-link.bin")
        return actual_open(path, **kwargs)

    monkeypatch.setattr(durability, "_windows_open_regular_read_handle", substitute)
    with pytest.raises(PhysicalOnboardingStorageError, match="could not read"):
        publication.read_bounded(ledger, "record.bin", maximum_bytes=16)


@pytest.mark.parametrize(
    "relative", ["../record.bin", "C:/record.bin", "record.bin:stream", "CON"]
)
def test_unsafe_relative_names_are_rejected(store, relative):
    _, ledger, publication = store
    with pytest.raises(PhysicalOnboardingStorageError):
        publication.read_bounded(ledger, relative, maximum_bytes=16)


def test_outside_root_is_rejected_before_file_read(store, tmp_path, monkeypatch):
    _, _, publication = store
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "record.bin").write_bytes(b"outside")

    def must_not_open(*args, **kwargs):
        pytest.fail("Out-of-scope file must not be opened")

    monkeypatch.setattr(durability, "_windows_open_regular_read_handle", must_not_open)
    with pytest.raises(PhysicalOnboardingStorageError, match="outside"):
        publication.read_bounded(outside, "record.bin", maximum_bytes=16)


def test_new_reparse_attribute_is_rejected_on_the_next_walk(store, monkeypatch):
    _, ledger, publication = store
    publication.read_bounded(ledger, "record.bin", maximum_bytes=16)
    actual_lstat = Path.lstat

    def observed_reparse(path):
        value = actual_lstat(path)
        if path == ledger:

            class ReparseObservation:
                st_mode = value.st_mode
                st_nlink = value.st_nlink
                st_file_attributes = value.st_file_attributes | 0x400

            return ReparseObservation()
        return value

    monkeypatch.setattr(Path, "lstat", observed_reparse)
    with pytest.raises(durability.PhysicalOnboardingDurabilityError, match="reparse"):
        publication.read_bounded(ledger, "record.bin", maximum_bytes=16)
