"""Small file-only snapshot faults; no device, process or long acceptance run."""

import importlib.util
import os
from pathlib import Path
import subprocess

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/camera_acceptance_snapshot.py"
spec = importlib.util.spec_from_file_location("camera_snapshot_test_subject", SCRIPT)
snapshot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(snapshot)


@pytest.fixture(autouse=True)
def no_process(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail("Snapshot tests must not start a process or hardware worker")

    monkeypatch.setattr(subprocess, "Popen", denied)


@pytest.fixture
def inputs(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    for tree in snapshot.INPUT_TREES:
        (root / tree).mkdir(parents=True, exist_ok=True)
    for relative in snapshot.INPUT_FILES:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(("MODELED input: " + relative).encode())
    (root / "software/src/example.py").write_bytes(b"MODELED source bytes")
    return root, tmp_path / "isolated"


@pytest.mark.parametrize("excluded_name", ["runs", "tmp", "node_modules"])
def test_snapshot_keeps_exact_bytes_and_ignores_runs_and_bytecode(
    inputs, excluded_name
):
    source, target = inputs
    excluded = source / "software/tests" / excluded_name
    excluded.mkdir()
    (excluded / "old-evidence.json").write_bytes(b"NEVER COPIED")
    (source / "software/src/cache.pyc").write_bytes(b"NEVER COPIED")
    manifest = snapshot.create_snapshot(source, target)
    assert manifest == snapshot.verify_snapshot(target)
    assert not (target / "software/tests" / excluded_name).exists()
    assert not (target / "software/src/cache.pyc").exists()
    assert manifest["physical_authority"] is False
    assert manifest["file_count"] == len(manifest["files"])
    assert manifest["total_bytes"] == sum(
        row["bytes"] for row in manifest["files"].values()
    )
    # Subsequent shared-checkout work must not change the frozen copy.
    (source / "rocell.ps1").write_bytes(b"MODELED later independent edit")
    assert snapshot.verify_snapshot(target) == manifest


@pytest.mark.parametrize("fault", ["changed", "added", "missing"])
def test_changed_snapshot_inputs_reject(inputs, fault):
    source, target = inputs
    snapshot.create_snapshot(source, target)
    leaf = target / "software/src/example.py"
    if fault == "changed":
        leaf.write_bytes(b"MODELED changed source")
    elif fault == "added":
        leaf.with_name("new.py").write_bytes(b"MODELED extra input")
    else:
        leaf.unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        snapshot.verify_snapshot(target)


def test_existing_destination_is_preserved(inputs):
    source, target = inputs
    target.mkdir()
    sentinel = target / "keep.txt"
    sentinel.write_bytes(b"keep")
    with pytest.raises(ValueError, match="must be absent"):
        snapshot.create_snapshot(source, target)
    assert sentinel.read_bytes() == b"keep"


def test_input_change_during_copy_never_publishes_accepted_manifest(
    inputs, monkeypatch
):
    source, target = inputs
    copied = snapshot._copy_input
    changed = []

    def concurrent_edit(input_path, output_path, expected_bytes):
        copied(input_path, output_path, expected_bytes)
        if not changed:
            changed.append(True)
            (source / "rocell.ps1").write_bytes(b"MODELED concurrent edit")

    monkeypatch.setattr(snapshot, "_copy_input", concurrent_edit)
    with pytest.raises(ValueError, match="changed during snapshot|during copy"):
        snapshot.create_snapshot(source, target)
    assert target.is_dir() and not (target / snapshot.MANIFEST).exists()


@pytest.mark.parametrize("observed_size", [2, 6])
def test_copy_rejects_size_change_without_unbounded_output(tmp_path, observed_size):
    source = tmp_path / "input"
    target = tmp_path / "output"
    source.write_bytes(b"data")
    with pytest.raises(ValueError, match="during copy"):
        snapshot._copy_input(source, target, observed_size)
    assert target.stat().st_size <= observed_size
    assert source.read_bytes() == b"data"


def test_destination_cannot_reenter_input_tree(inputs):
    source, _ = inputs
    with pytest.raises(ValueError, match="overlaps"):
        snapshot.create_snapshot(source, source / "software/src/recursive-copy")


@pytest.mark.parametrize("fault", ["policy", "digest", "authority"])
def test_manifest_changes_cannot_silently_relabel_inputs(inputs, fault):
    import json

    source, target = inputs
    manifest = snapshot.create_snapshot(source, target)
    if fault == "policy":
        manifest["input_trees"] = []
    elif fault == "digest":
        manifest["input_sha256"] = "0" * 64
    else:
        manifest["physical_authority"] = True
    (target / snapshot.MANIFEST).write_bytes(snapshot._canonical(manifest))
    with pytest.raises(ValueError):
        snapshot.verify_snapshot(target)


@pytest.mark.skipif(os.name != "nt", reason="Actual isolated NTFS junction")
def test_junction_is_not_followed_or_copied(inputs, tmp_path):
    import _winapi

    source, target = inputs
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "preserved.txt"
    sentinel.write_bytes(b"keep")
    junction = source / "software/src/junction"
    _winapi.CreateJunction(str(outside), str(junction))
    try:
        with pytest.raises(ValueError, match="reparse"):
            snapshot.create_snapshot(source, target)
        assert not target.exists()
    finally:
        junction.rmdir()  # Only this new link; preserve the target and its contents.
    assert sentinel.read_bytes() == b"keep"


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "skipped",
        "failure",
        "error",
        "empty",
        "duplicate",
        "wrong-case",
        "missing-name",
        "declaration",
        "malformed",
    ],
)
def test_acceptance_requires_the_executed_camera_case_not_just_zero_exit(
    tmp_path, fault
):
    import xml.etree.ElementTree as ET

    root = ET.Element("testsuites")
    suite = ET.SubElement(root, "testsuite")
    case = ET.SubElement(
        suite,
        "testcase",
        classname="tests.unit.test_arrival_camera_full_history_ntfs",
        name=snapshot.FULL_TEST,
    )
    if fault in {"skipped", "failure", "error"}:
        ET.SubElement(case, fault)
    elif fault == "empty":
        suite.remove(case)
    elif fault == "duplicate":
        suite.append(case)
    elif fault == "wrong-case":
        case.set("name", "different_camera_test")
    elif fault == "missing-name":
        case.attrib.pop("classname")
    raw = ET.tostring(root)
    if fault == "declaration":
        raw = b'<!DOCTYPE testsuites [<!ENTITY example "MODELED">]>' + raw
    elif fault == "malformed":
        raw = b"<unfinished"
    junit = tmp_path / "junit.xml"
    junit.write_bytes(raw)
    if fault is None:
        result = snapshot.verify_test_outcome(junit, lane="full")
        assert result["passed"] == 1 and result["skipped"] == 0
    else:
        with pytest.raises((ValueError, ET.ParseError)):
            snapshot.verify_test_outcome(junit, lane="full")
