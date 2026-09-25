"""One fresh metadata observation per ancestor; no device/process execution.

Real links/junctions and original stores are created only inside fresh temporary
test directories. Modeled metadata covers unavailable link privileges and OS
errors without turning unreadable components into safe paths.
"""

import errno
import json
import os
from pathlib import Path
import stat
import subprocess
from types import SimpleNamespace

import pytest

from rocell.application import physical_onboarding_v2 as v2
from rocell.application.physical_onboarding import PhysicalOnboardingSession


@pytest.fixture(autouse=True)
def no_process(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail("path observation must not launch a process")

    monkeypatch.setattr(subprocess, "Popen", denied)


def ancestors(path):
    absolute = Path(os.path.abspath(path))
    return [absolute, *absolute.parents]


def metadata(*, link=False, reparse=False, regular=False):
    return SimpleNamespace(
        st_mode=stat.S_IFLNK if link else stat.S_IFREG if regular else stat.S_IFDIR,
        st_file_attributes=0x400 if reparse else 0,
    )


def test_one_lstat_per_ancestor_through_root_and_every_call(tmp_path, monkeypatch):
    path = tmp_path / "missing" / "receipt.json"
    expected = ancestors(path)
    calls = []

    def observed(component):
        calls.append(component)
        return metadata(regular=component == path)

    def redundant(*args, **kwargs):
        pytest.fail("must derive both link predicates from the one lstat result")

    with monkeypatch.context() as patch:
        patch.setattr(Path, "lstat", observed)
        patch.setattr(Path, "is_symlink", redundant)
        patch.setattr(os.path, "lexists", redundant)
        patch.setattr(v2, "_is_link_or_reparse", redundant)
        v2._reject_link_chain(path, "original")
        assert calls == expected
        v2._reject_link_chain(path, "original")
        assert calls == expected * 2
    assert expected[-1].parent == expected[-1]


@pytest.mark.parametrize("position", ["leaf", "parent", "root"])
@pytest.mark.parametrize("kind", ["symlink", "reparse", "both"])
def test_each_link_kind_at_any_level_is_rejected(tmp_path, monkeypatch, position, kind):
    path = tmp_path / "parent" / "original.json"
    chain = ancestors(path)
    target = {"leaf": chain[0], "parent": chain[1], "root": chain[-1]}[position]
    calls = []

    def observed(component):
        calls.append(component)
        return metadata(
            link=component == target and kind in {"symlink", "both"},
            reparse=component == target and kind in {"reparse", "both"},
        )

    monkeypatch.setattr(Path, "lstat", observed)
    with pytest.raises(v2.PhysicalOnboardingV2Error, match="link or reparse point"):
        v2._reject_link_chain(path, "original")
    assert calls == chain[: chain.index(target) + 1]


@pytest.mark.parametrize("linked_parent", [False, True])
def test_missing_suffix_never_skips_its_ancestors(tmp_path, monkeypatch, linked_parent):
    path = tmp_path / "not-created" / "original.json"
    chain = ancestors(path)
    calls = []

    def observed(component):
        calls.append(component)
        if component in chain[:2]:
            raise FileNotFoundError(
                errno.ENOENT, "modeled absent component", str(component)
            )
        return metadata(reparse=linked_parent and component == tmp_path)

    monkeypatch.setattr(Path, "lstat", observed)
    if linked_parent:
        with pytest.raises(v2.PhysicalOnboardingV2Error, match="link or reparse point"):
            v2._reject_link_chain(path, "original")
        assert calls == chain[:3]
    else:
        v2._reject_link_chain(path, "original")
        assert calls == chain


@pytest.mark.parametrize("code", [errno.EACCES, errno.EIO, errno.ENOTDIR, errno.ELOOP])
@pytest.mark.parametrize("position", ["leaf", "parent"])
def test_nonmissing_inspection_errors_fail_closed(
    tmp_path, monkeypatch, code, position
):
    path = tmp_path / "unreadable" / "original.json"
    chain = ancestors(path)
    target = chain[0 if position == "leaf" else 1]
    failure = OSError(code, "modeled inspection failure", str(target))
    calls = []

    def observed(component):
        calls.append(component)
        if component == target:
            raise failure
        return metadata()

    monkeypatch.setattr(Path, "lstat", observed)
    with pytest.raises(
        v2.PhysicalOnboardingV2Error, match="could not be inspected"
    ) as raised:
        v2._reject_link_chain(path, "original")
    assert raised.value.__cause__ is failure
    assert calls == chain[: chain.index(target) + 1]


def test_next_call_observes_changed_parent_instead_of_caching(tmp_path, monkeypatch):
    path = tmp_path / "original.json"
    chain = ancestors(path)
    changed = False
    calls = []

    def observed(component):
        calls.append(component)
        return metadata(reparse=changed and component == tmp_path)

    monkeypatch.setattr(Path, "lstat", observed)
    v2._reject_link_chain(path, "original")
    assert calls == chain
    changed = True
    with pytest.raises(v2.PhysicalOnboardingV2Error, match="link or reparse point"):
        v2._reject_link_chain(path, "original")
    assert calls == chain + chain[:2]


def test_nonwindows_metadata_without_file_attributes_is_supported(
    tmp_path, monkeypatch
):
    calls = []

    def observed(component):
        calls.append(component)
        return SimpleNamespace(st_mode=stat.S_IFDIR)

    monkeypatch.setattr(Path, "lstat", observed)
    v2._reject_link_chain(tmp_path, "original")
    assert calls == ancestors(tmp_path)


def test_real_directory_regular_file_and_absent_suffix(tmp_path, monkeypatch):
    regular = tmp_path / "original.json"
    regular.write_bytes(b"{}\n")
    calls = []
    actual = Path.lstat

    def observed(component):
        calls.append(component)
        return actual(component)

    monkeypatch.setattr(Path, "lstat", observed)
    for path in (tmp_path, regular, tmp_path / "absent" / "original.json"):
        calls.clear()
        v2._reject_link_chain(path, "original")
        assert calls == ancestors(path)


def make_symlink(link, target, *, directory=False):
    try:
        link.symlink_to(target, target_is_directory=directory)
    except OSError as exc:
        if (
            exc.errno in {errno.EACCES, errno.EPERM, errno.ENOSYS}
            or getattr(exc, "winerror", None) == 1314
        ):
            pytest.skip("host does not permit creation of isolated test symlinks")
        raise


def test_real_dangling_symlink_is_rejected(tmp_path):
    link = tmp_path / "dangling-original.json"
    make_symlink(link, tmp_path / "never-created.json")
    assert stat.S_ISLNK(link.lstat().st_mode)
    with pytest.raises(v2.PhysicalOnboardingV2Error, match="link or reparse point"):
        v2._reject_link_chain(link, "original")


def test_real_missing_leaf_above_symlink_parent_is_rejected(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "linked-parent"
    make_symlink(link, target, directory=True)
    with pytest.raises(v2.PhysicalOnboardingV2Error, match="link or reparse point"):
        v2._reject_link_chain(link / "missing" / "original.json", "original")


@pytest.mark.skipif(os.name != "nt", reason="Windows junction observation")
def test_real_junction_and_missing_descendant_are_rejected(tmp_path):
    import _winapi

    target = tmp_path / "junction-target"
    target.mkdir()
    link = tmp_path / "junction"
    _winapi.CreateJunction(str(target), str(link))
    try:
        assert link.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT
        for path in (link, link / "missing" / "original.json"):
            with pytest.raises(
                v2.PhysicalOnboardingV2Error, match="link or reparse point"
            ):
                v2._reject_link_chain(path, "original")
    finally:
        # Remove only this exact fresh junction, never its target or recursively.
        link.rmdir()
    assert target.is_dir()


def tree_bytes(directory):
    return {
        str(path.relative_to(directory)): path.read_bytes()
        for path in directory.rglob("*")
        if path.is_file()
    }


@pytest.mark.parametrize("version", [1, 2])
def test_original_readback_bytes_source_and_no_authority_unchanged(tmp_path, version):
    factory = (
        PhysicalOnboardingSession if version == 1 else v2.PhysicalOnboardingV2Session
    )
    session = factory.create(
        tmp_path,
        session_id="unchanged-original",
        cell_id="cell-a",
        source_binding_sha256="a" * 64,
        created_at_ns=1000,
    )
    before = tree_bytes(session.directory)
    opened = v2.open_onboarding_session(session.directory)
    if version == 1:
        assert isinstance(opened, v2.LegacyV1ReadOnlySession)
        snapshot = opened.verify()
        assert opened.export_document()["read_only_reason"] == v2.LEGACY_V1_READ_ONLY
        authority = opened.export_document()["authority"]
        with pytest.raises(v2.LegacyV1ReadOnlyError):
            opened.commit_stage_state()
    else:
        snapshot = opened.snapshot()
        assert snapshot == session.snapshot()
        assert all(stage.state is v2.V2StageState.PENDING for stage in snapshot.stages)
        authority = json.loads(before["header.json"])
    assert snapshot.header.source_binding_sha256 == "a" * 64
    header = json.loads(before["header.json"])
    assert header["physical_release_effect"] == "NONE"
    assert header["motion_authorized"] is False
    assert header["contact_authorized"] is False
    for flag in (
        "device_io_authorized",
        "robot_power_authorized",
        "motion_authorized",
        "contact_authorized",
    ):
        assert authority[flag] is False
    assert tree_bytes(session.directory) == before


def test_independent_bounded_reader_still_rejects_hardlinked_original(tmp_path):
    original = tmp_path / "original.json"
    original.write_bytes(b"{}\n")
    alias = tmp_path / "hardlinked.json"
    os.link(original, alias)
    # This predicate only rejects links/reparse ancestors; handle-based regular
    # file and hardlink verification remains mandatory in the separate reader.
    v2._reject_link_chain(alias, "original")
    with pytest.raises(v2.PhysicalOnboardingV2Error, match="cannot read original"):
        v2._read_canonical_json(alias, "original")
