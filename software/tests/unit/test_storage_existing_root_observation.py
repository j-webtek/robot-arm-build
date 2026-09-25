"""Fresh existing-root checks on isolated NTFS files, never device operations.

An existing root needs all lexical and physical predicates, but not a second
walk nested inside candidate construction. Each later call and file containment
check must still re-observe the filesystem; this is not a path approval cache.
"""

import errno
import os
from pathlib import Path
import subprocess

import pytest

from rocell.application import physical_onboarding_durability as durability
from rocell.application import physical_onboarding_storage as storage
from test_durability_pair_observation import qualified_pair


pytestmark = pytest.mark.skipif(os.name != "nt", reason="actual qualified NTFS")


@pytest.fixture(autouse=True)
def no_process(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail("existing-root checks must not launch a process")

    monkeypatch.setattr(subprocess, "Popen", denied)


@pytest.fixture
def publication(qualified_pair, tmp_path):
    root, anchor, startup = qualified_pair
    adapter = storage.QualifiedWindowsOnboardingPublication(
        root, "a" * 64, anchor, startup, mutation_guard=lambda: None
    )
    subject = root / tmp_path.name
    subject.mkdir()
    return adapter, subject


@pytest.mark.parametrize("depth", [0, 3])
def test_one_complete_ancestor_walk_per_existing_root_call(
    publication, monkeypatch, depth
):
    adapter, subject = publication
    target = adapter.deployment_root if not depth else subject / "one" / "two"
    if depth:
        target.mkdir(parents=True)
    expected = [
        Path(target.anchor).joinpath(*target.parts[1:index])
        for index in range(2, len(target.parts) + 1)
    ]
    observed = []
    actual = Path.lstat

    def counted(path):
        observed.append(path)
        return actual(path)

    monkeypatch.setattr(Path, "lstat", counted)
    for _ in range(2):
        observed.clear()
        assert adapter._existing_root(target, label="test root") == target
        assert observed == expected


@pytest.mark.parametrize(
    "defect",
    [
        "not-path",
        "relative",
        "outside",
        "prefix-sibling",
        "parent",
        "reserved",
        "stream",
        "trailing-space",
        "trailing-dot",
        "control",
    ],
)
def test_lexically_invalid_roots_reject_without_filesystem_observation(
    publication, monkeypatch, defect
):
    adapter, subject = publication
    root = adapter.deployment_root
    targets = {
        "not-path": str(subject),
        "relative": Path("relative"),
        "outside": root.parent,
        "prefix-sibling": root.with_name(root.name + "-sibling"),
        "parent": subject / ".." / "elsewhere",
        "reserved": subject / "CON.json",
        "stream": subject / "data:stream",
        "trailing-space": subject / "bad ",
        "trailing-dot": subject / "bad.",
        "control": subject / "bad\x01",
    }

    def unexpected(*args, **kwargs):
        pytest.fail("invalid lexical path must not reach filesystem validation")

    monkeypatch.setattr(storage, "safe_root", unexpected)
    monkeypatch.setattr(storage, "contained_path", unexpected)
    with pytest.raises((TypeError, storage.PhysicalOnboardingStorageError)):
        adapter._existing_root(targets[defect], label="test root")


@pytest.mark.parametrize("kind", ["missing", "file", "hardlink"])
def test_existing_root_requires_actual_safe_directory(publication, kind):
    adapter, subject = publication
    target = subject / "candidate"
    if kind != "missing":
        target.write_bytes(b"not a directory")
    if kind == "hardlink":
        os.link(target, subject / "other-link")
    with pytest.raises(durability.PhysicalOnboardingDurabilityError):
        adapter._existing_root(target, label="test root")


@pytest.mark.parametrize("position", ["ancestor", "leaf"])
@pytest.mark.parametrize("code", [errno.EACCES, errno.EIO, errno.ENOTDIR])
def test_component_io_failures_reject(publication, monkeypatch, position, code):
    adapter, subject = publication
    target = subject / "leaf"
    target.mkdir()
    failing = subject if position == "ancestor" else target
    actual = Path.lstat

    def unreadable(path):
        if path == failing:
            raise OSError(code, "modeled component IO failure")
        return actual(path)

    monkeypatch.setattr(Path, "lstat", unreadable)
    with pytest.raises(durability.PhysicalOnboardingDurabilityError, match="inspect"):
        adapter._existing_root(target, label="test root")


@pytest.mark.parametrize("suffix", [False, True])
@pytest.mark.parametrize("outside", [False, True])
def test_real_junction_is_rejected_even_with_missing_suffix(
    publication, tmp_path, suffix, outside
):
    import _winapi

    adapter, subject = publication
    destination = tmp_path / "outside" if outside else subject / "inside"
    destination.mkdir()
    junction = subject / "junction"
    _winapi.CreateJunction(str(destination), str(junction))
    try:
        candidate = junction / "missing" if suffix else junction
        with pytest.raises(durability.PhysicalOnboardingDurabilityError):
            adapter._existing_root(candidate, label="test root")
    finally:
        # Only this exact new junction is removed; its target is preserved.
        junction.rmdir()
    assert destination.is_dir()


def test_next_call_does_not_reuse_previous_root_approval(publication):
    import _winapi

    adapter, subject = publication
    target = subject / "current"
    target.mkdir()
    replacement = subject / "replacement"
    replacement.mkdir()
    assert adapter._existing_root(target, label="test root") == target
    # Preserve the original directory and introduce a new isolated fault.
    target.rename(subject / "preserved")
    _winapi.CreateJunction(str(replacement), str(target))
    try:
        with pytest.raises(
            durability.PhysicalOnboardingDurabilityError, match="reparse"
        ):
            adapter._existing_root(target, label="test root")
    finally:
        target.rmdir()
    assert (subject / "preserved").is_dir() and replacement.is_dir()


def test_file_containment_is_independent_after_qualification(publication, monkeypatch):
    adapter, subject = publication
    leaf = subject / "original.json"
    leaf.write_bytes(b"{}\n")
    actual_qualification = (
        storage.QualifiedWindowsOnboardingPublication._require_qualified_reports
    )
    checks = []

    def qualification_then_fault(self):
        actual_qualification(self)
        # A new fault after qualification's deployment-root observation must
        # still be caught by contained_path, before any native file open. The
        # read path now selects its ledger root lexically; it no longer calls
        # _existing_root immediately before contained_path's identical walk.
        # Inject at the remaining semantic boundary, not the removed helper.
        actual_component = durability._reject_unsafe_component

        def changed(path, path_label):
            checks.append(path)
            if path == subject:
                raise durability.PhysicalOnboardingDurabilityError("late root fault")
            return actual_component(path, path_label)

        monkeypatch.setattr(durability, "_reject_unsafe_component", changed)

    def no_open(*args, **kwargs):
        pytest.fail("late root fault must reject before file open")

    monkeypatch.setattr(
        storage.QualifiedWindowsOnboardingPublication,
        "_require_qualified_reports",
        qualification_then_fault,
    )
    monkeypatch.setattr(durability, "_windows_open_regular_read_handle", no_open)
    with pytest.raises(durability.PhysicalOnboardingDurabilityError, match="late root"):
        adapter.read_bounded(subject, "original.json", maximum_bytes=3)
    assert subject in checks


def test_candidate_for_new_publication_still_checks_existing_ancestors(
    publication, monkeypatch
):
    adapter, subject = publication
    actual = durability._reject_unsafe_component
    calls = []

    def fresh(path, label):
        calls.append(path)
        return actual(path, label)

    monkeypatch.setattr(durability, "_reject_unsafe_component", fresh)
    target = subject / "not-created"
    assert adapter._candidate(target, label="new candidate") == target
    assert adapter.deployment_root in calls and subject in calls and target in calls
