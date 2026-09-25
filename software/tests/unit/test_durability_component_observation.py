"""Fresh component metadata without redundant probes or device effects.

Counting tests assert call structure, not wall-clock speed. Real files and links
are confined to new pytest directories; no failed commissioning store is used.
"""

import errno
import os
from pathlib import Path
import stat
import subprocess
from types import SimpleNamespace

import pytest

from rocell.application import physical_onboarding_durability as durability


@pytest.fixture(autouse=True)
def no_process(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail("metadata observation must not launch a process")

    monkeypatch.setattr(subprocess, "Popen", denied)


def metadata(*, mode=stat.S_IFREG, attributes=0, links=1):
    return SimpleNamespace(st_mode=mode, st_file_attributes=attributes, st_nlink=links)


def test_one_lstat_for_all_predicates_and_no_cache(tmp_path, monkeypatch):
    path = tmp_path / "original.json"
    calls = []
    current = metadata()

    def observed(component):
        calls.append(component)
        return current

    def redundant(*args, **kwargs):
        pytest.fail("component predicates must use one current lstat result")

    with monkeypatch.context() as patch:
        patch.setattr(Path, "lstat", observed)
        patch.setattr(Path, "stat", redundant)
        patch.setattr(Path, "is_symlink", redundant)
        patch.setattr(os.path, "lexists", redundant)
        patch.setattr(durability, "_win32", redundant)
        durability._reject_unsafe_component(path, "original")
        durability._reject_unsafe_component(path, "original")
        current = metadata(attributes=0x400)
        with pytest.raises(
            durability.PhysicalOnboardingDurabilityError, match="reparse"
        ):
            durability._reject_unsafe_component(path, "original")
        assert calls == [path] * 3


@pytest.mark.parametrize(
    "observed,reason",
    [
        (metadata(mode=stat.S_IFLNK), "symlink"),
        (metadata(attributes=0x400), "reparse"),
        (metadata(mode=stat.S_IFDIR, attributes=0x400), "reparse"),
        (metadata(links=2), "hard-linked"),
        (metadata(links=0), "hard-linked"),
    ],
)
def test_unsafe_current_metadata_refused(tmp_path, monkeypatch, observed, reason):
    monkeypatch.setattr(Path, "lstat", lambda _: observed)
    with pytest.raises(durability.PhysicalOnboardingDurabilityError, match=reason):
        durability._reject_unsafe_component(tmp_path / "original", "original")


@pytest.mark.parametrize("code", [errno.EACCES, errno.EIO, errno.ENOTDIR, errno.ELOOP])
def test_nonmissing_errors_are_not_absence(tmp_path, monkeypatch, code):
    failure = OSError(code, "modeled unreadable component")

    def unreadable(_):
        raise failure

    monkeypatch.setattr(Path, "lstat", unreadable)
    with pytest.raises(
        durability.PhysicalOnboardingDurabilityError, match="cannot inspect"
    ) as caught:
        durability._reject_unsafe_component(tmp_path / "original", "original")
    assert caught.value.__cause__ is failure


@pytest.mark.parametrize("attributes", [None, True, -1, 0xFFFFFFFF, "0"])
def test_windows_missing_or_invalid_attributes_cannot_authorize_path(
    tmp_path, monkeypatch, attributes
):
    observed = metadata(attributes=attributes)
    monkeypatch.setattr(Path, "lstat", lambda _: observed)
    # Only the component function sees a modeled OS; pathlib/pytest stay native.
    monkeypatch.setattr(durability, "os", SimpleNamespace(name="nt"))
    with pytest.raises(
        durability.PhysicalOnboardingDurabilityError, match="Windows attributes"
    ):
        durability._reject_unsafe_component(tmp_path, "original")


def test_portable_metadata_without_windows_attributes(tmp_path, monkeypatch):
    observed = SimpleNamespace(st_mode=stat.S_IFREG, st_nlink=1)
    monkeypatch.setattr(Path, "lstat", lambda _: observed)
    monkeypatch.setattr(durability, "os", SimpleNamespace(name="posix"))
    durability._reject_unsafe_component(tmp_path, "original")


def test_real_regular_directory_and_missing_component(tmp_path):
    regular = tmp_path / "original.json"
    regular.write_bytes(b"{}\n")
    for path in (tmp_path, regular, tmp_path / "missing"):
        durability._reject_unsafe_component(path, "original")
    assert durability.read_bounded_regular_file(regular, maximum_bytes=3) == b"{}\n"
    with pytest.raises(durability.PhysicalOnboardingDurabilityError):
        durability.read_bounded_regular_file(regular, maximum_bytes=2)
    with pytest.raises(durability.PhysicalOnboardingDurabilityError):
        durability.read_bounded_regular_file(tmp_path / "missing", maximum_bytes=3)


def test_real_hardlink_is_refused_before_read(tmp_path):
    original = tmp_path / "original.json"
    original.write_bytes(b"{}\n")
    linked = tmp_path / "linked.json"
    os.link(original, linked)
    for path in (original, linked):
        with pytest.raises(
            durability.PhysicalOnboardingDurabilityError, match="hard-linked"
        ):
            durability.read_bounded_regular_file(path, maximum_bytes=3)


@pytest.mark.skipif(os.name != "nt", reason="actual Windows junction metadata")
def test_real_junction_cannot_be_used_as_root_even_for_missing_suffix(tmp_path):
    import _winapi

    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "junction"
    _winapi.CreateJunction(str(target), str(link))
    try:
        for path in (link, link / "missing"):
            with pytest.raises(
                durability.PhysicalOnboardingDurabilityError, match="reparse"
            ):
                durability.safe_root(path)
    finally:
        # Only this fresh exact junction is removed, never its target tree.
        link.rmdir()
    assert target.is_dir()


def test_safe_root_rechecks_every_component_on_every_call(tmp_path, monkeypatch):
    calls = []
    actual = Path.lstat
    selected = Path(os.path.abspath(tmp_path))
    expected = [
        Path(selected.anchor).joinpath(*selected.parts[1:index])
        for index in range(2, len(selected.parts) + 1)
    ]

    def observed(path):
        calls.append(path)
        return actual(path)

    monkeypatch.setattr(Path, "lstat", observed)
    for _ in range(2):
        calls.clear()
        assert durability.safe_root(selected) == selected
        assert calls == expected


@pytest.mark.skipif(os.name != "nt", reason="native opened-handle verification")
def test_opened_handle_rejects_late_hardlink_even_after_path_check(
    tmp_path, monkeypatch
):
    original = tmp_path / "original.json"
    original.write_bytes(b"{}\n")
    linked = tmp_path / "late-link.json"
    actual = durability._windows_read_regular_file
    calls = []

    def changed_after_path_check(path, **kwargs):
        calls.append(path)
        os.link(original, linked)
        return actual(path, **kwargs)

    monkeypatch.setattr(
        durability, "_windows_read_regular_file", changed_after_path_check
    )
    with pytest.raises(
        durability.PhysicalOnboardingDurabilityError, match="hard-linked"
    ):
        durability.read_bounded_regular_file(original, maximum_bytes=3)
    assert calls == [original]
