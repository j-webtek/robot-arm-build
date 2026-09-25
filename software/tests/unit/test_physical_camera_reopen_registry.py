"""Own temporary metadata only; qualification records are explicitly modeled.

These tests do not open M1, enumerate devices, create processes or qualify a
volume. Real filesystem guards are exercised only against these tmp_path data.
"""

from dataclasses import FrozenInstanceError
import hashlib
import json
import os
from pathlib import Path
import subprocess
import threading
import time

import pytest

from rocell.application import physical_camera_reopen_registry as module
from rocell.application.commissioning_camera_persistence import (
    physical_camera_source_binding,
)
from rocell.application.physical_onboarding_durability import (
    DURABILITY_ADAPTER_ID,
    DURABILITY_REPORT_SCHEMA,
    canonical_bytes,
    canonical_sha256,
)
from rocell.application.physical_onboarding_m1 import (
    M1CellDescriptor,
    PhysicalOnboardingM1Runtime,
)
from rocell.application.physical_onboarding_v2 import (
    V2SessionHeader,
    WINDOWS_NTFS_QUALIFIED,
    _canonical_bytes,
)

SOURCE = "a" * 64
CURRENT = "wizard-" + "2" * 32
ORIGIN = "wizard-" + "1" * 32


def metadata_store(workspace: Path, *, origin=ORIGIN, source=SOURCE):
    """Modeled self-consistent historical metadata, never actual qualification."""
    directory = workspace / "software/runs/physical-camera-acquisition" / origin
    directory.mkdir(parents=True)
    lineage = module._hash(module._json({"launch": origin, "source": source}))
    cell_id = "wizard-physical-camera-" + lineage[:16]
    session_id = "physical-camera-" + lineage[16:48]
    domain = physical_camera_source_binding(source)
    core = {
        "schema": DURABILITY_REPORT_SCHEMA,
        "adapter_id": DURABILITY_ADAPTER_ID,
        "checked_at_ns": 1,
        "source_binding_sha256": domain,
        "root_sha256": hashlib.sha256(str(directory).encode("utf-8")).hexdigest(),
        "platform": "Windows",
        "filesystem": "NTFS",
        "volume_identity": "MODELED_NO_VOLUME_QUALIFICATION",
        "qualified_for_effects": True,
        "checks": [
            {
                "check_id": value,
                "passed": True,
                "detail": "Modeled historical metadata only.",
            }
            for value in (
                "LOCKFILEEX_EXCLUSIVE_LEASE",
                "WRITE_THROUGH_FILE_OPEN",
                "FLUSH_FILE_BUFFERS",
                "ATOMIC_REPLACE",
                "DIRECTORY_ENTRY_DURABILITY_TEST",
            )
        ],
    }
    anchor = {**core, "report_sha256": canonical_sha256(core)}
    cell = M1CellDescriptor.build(
        cell_id=cell_id,
        source_binding_sha256=domain,
        durability_qualification_sha256=anchor["report_sha256"],
        created_at_ns=2,
    )
    header = V2SessionHeader.build(
        session_id=session_id,
        cell_id=cell_id,
        created_at_ns=3,
        source_binding_sha256=domain,
        publication_durability=WINDOWS_NTFS_QUALIFIED,
        durability_qualification_sha256=anchor["report_sha256"],
    )
    cell_path = directory / "cells" / ("cell-" + cell.cell_key_sha256) / "cell.json"
    header_path = directory / ("onboarding-" + session_id) / "header.json"
    cell_path.parent.mkdir(parents=True)
    header_path.parent.mkdir()
    cell_path.write_bytes(canonical_bytes(cell.to_dict()))
    header_path.write_bytes(_canonical_bytes(header.to_dict()))
    (directory / "durability-anchor.json").write_bytes(canonical_bytes(anchor))
    return directory, header_path, cell_path


@pytest.fixture(autouse=True)
def no_runtime(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Registry must not open/initialize M1 or execute a process")

    monkeypatch.setattr(PhysicalOnboardingM1Runtime, "open", forbidden)
    monkeypatch.setattr(PhysicalOnboardingM1Runtime, "initialize", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)


@pytest.fixture
def registry(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "source_fingerprint", lambda _: SOURCE)
    return module.PhysicalCameraReopenRegistry(
        tmp_path, current_launch_id=CURRENT, source_sha256=SOURCE
    )


def discover(registry):
    return registry.discover(
        cancellation=threading.Event(), deadline_ns=time.monotonic_ns() + 30_000_000_000
    )


def select(registry, *, cancel=None, choice=None, digest=None):
    return registry.selected(
        choice or registry.choices()[0]["value"],
        digest or registry.view()["discovery_sha256"],
        cancellation=cancel or threading.Event(),
        deadline_ns=time.monotonic_ns() + 120_000_000_000,
    )


def test_constructor_and_cached_views_are_inert(tmp_path, monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail("Cached registry operation performed IO")

    for name in ("stat", "iterdir", "open", "resolve"):
        monkeypatch.setattr(Path, name, denied)
    monkeypatch.setattr(module, "source_fingerprint", denied)
    owner = module.PhysicalCameraReopenRegistry(
        tmp_path, current_launch_id=CURRENT, source_sha256=SOURCE
    )
    assert owner.view()["status"] == "NOT_DISCOVERED"
    assert owner.choices() == []
    with pytest.raises(module.PhysicalCameraReopenError):
        owner.preview("reopen-" + "3" * 32)
    owner.invalidate()
    assert owner.view()["status"] == "INVALIDATED"


def test_missing_root_is_not_created(registry):
    snapshot = discover(registry)
    assert snapshot["status"] == "DISCOVERED"
    assert snapshot["issues"][0]["code"] == "NO_STORE_ROOT"
    assert not registry.root.exists()


def test_actual_typed_metadata_choices_and_guarded_revalidation(registry, tmp_path):
    directory, _, _ = metadata_store(tmp_path)
    snapshot = discover(registry)
    assert snapshot["issues"] == []
    row = snapshot["stores"][0]
    assert row["source_matches"] is row["selectable"] is True
    assert row["source_binding_sha256"] == physical_camera_source_binding(SOURCE)
    assert row["origin_launch_id"] == ORIGIN
    assert "directory" not in registry.preview(row["choice_id"])
    with select(registry) as selected:
        assert selected.directory == directory
        assert selected.descriptor_sha256 == row["descriptor_sha256"]
        assert selected.workspace_source_sha256 == SOURCE
        assert selected.origin_launch_id == ORIGIN
        assert selected.header_sha256 == row["header_sha256"]
        doc = selected.to_dict()
        doc["cell_id"] = "changed"
        assert selected.cell_id != "changed"
        with pytest.raises(FrozenInstanceError):
            selected.payload = b"{}"
        # A normal M1 lease/journal side file does not change immutable metadata.
        (directory / "modeled-lease-state.json").write_bytes(b"{}")
    assert registry.view()["discovery_sha256"] == snapshot["discovery_sha256"]


def test_views_and_preview_are_detached(registry, tmp_path):
    metadata_store(tmp_path)
    snapshot = discover(registry)
    token = snapshot["stores"][0]["choice_id"]
    snapshot["stores"][0]["selectable"] = False
    preview = registry.preview(token)
    preview["header_sha256"] = "f" * 64
    assert registry.preview(token)["header_sha256"] != "f" * 64
    assert registry.view()["stores"][0]["selectable"] is True


def test_other_source_is_visible_but_not_selectable(registry, tmp_path):
    metadata_store(tmp_path, source="b" * 64)
    row = discover(registry)["stores"][0]
    assert row["status"] == "SOURCE_DRIFT_HELD"
    assert row["choice_id"] is None and row["selectable"] is False
    assert registry.choices() == []


@pytest.mark.parametrize(
    "part", ["header", "cell", "anchor", "ambiguity", "lineage", "unknown"]
)
def test_malformed_or_ambiguous_metadata_is_not_selectable(registry, tmp_path, part):
    directory, header, cell = metadata_store(tmp_path)
    if part == "ambiguity":
        (directory / "cells/second").mkdir()
    elif part == "lineage":
        new = directory.with_name("wizard-" + "4" * 32)
        directory.rename(new)
        anchor_path = new / "durability-anchor.json"
        anchor = json.loads(anchor_path.read_bytes())
        anchor["root_sha256"] = module._hash(str(new).encode())
        core = {key: value for key, value in anchor.items() if key != "report_sha256"}
        anchor["report_sha256"] = canonical_sha256(core)
        # Leave joined header/cell hashes unchanged: exact anchor relation fails.
        anchor_path.write_bytes(canonical_bytes(anchor))
    elif part == "unknown":
        (registry.root / "private-label-not-echoed").write_bytes(b"x")
    else:
        path = {
            "header": header,
            "cell": cell,
            "anchor": directory / "durability-anchor.json",
        }[part]
        path.write_bytes(b"{}\n")
    view = discover(registry)
    assert view["issues"]
    if part != "unknown":
        assert registry.choices() == []
    assert "private-label-not-echoed" not in json.dumps(view)


def test_discovery_never_recurses_into_evidence(registry, tmp_path):
    _, header, _ = metadata_store(tmp_path)
    nested = header.parent / "evidence/unread/deeper"
    nested.mkdir(parents=True)
    (nested / "not-metadata").write_bytes(b"corrupt and intentionally uninspected")
    assert len(discover(registry)["stores"]) == 1


def test_hardlinked_metadata_is_held(registry, tmp_path):
    _, header, _ = metadata_store(tmp_path)
    os.link(header, tmp_path / "own-metadata-hardlink")
    assert discover(registry)["issues"][0]["code"] == "UNSAFE_PATH"
    assert registry.choices() == []


def test_reparse_observation_is_held_without_creating_reparse_point(
    registry, tmp_path, monkeypatch
):
    metadata_store(tmp_path)
    original = module._stamp

    def denied(path, *, directory):
        if path.name == "header.json":
            raise module.PhysicalCameraReopenError("UNSAFE_PATH")
        return original(path, directory=directory)

    monkeypatch.setattr(module, "_stamp", denied)
    assert discover(registry)["issues"][0]["code"] == "UNSAFE_PATH"


@pytest.mark.parametrize("failure", ["count", "bytes", "entries"])
def test_bounded_discovery(registry, tmp_path, failure):
    directory, header, _ = metadata_store(tmp_path)
    if failure == "count":
        for number in range(32):
            (registry.root / ("entry-" + str(number))).mkdir()
        with pytest.raises(module.PhysicalCameraReopenError, match="32-entry"):
            discover(registry)
        assert registry.view()["status"] == "HELD"
    else:
        if failure == "bytes":
            header.write_bytes(b"x" * (module.MAX_METADATA_BYTES + 1))
        else:
            for number in range(128):
                (directory / ("entry-" + str(number))).mkdir()
        assert discover(registry)["issues"][0]["code"] == "METADATA_LIMIT"
    assert registry.choices() == []


@pytest.mark.parametrize("moment", ["before", "after"])
def test_selection_metadata_change_revokes_choice(registry, tmp_path, moment):
    _, header, _ = metadata_store(tmp_path)
    discover(registry)
    token = registry.choices()[0]["value"]

    def change():
        value = header.stat()
        os.utime(header, ns=(value.st_atime_ns, value.st_mtime_ns + 1_000_000))

    if moment == "before":
        change()
    with pytest.raises(module.PhysicalCameraReopenError) as error:
        with select(registry):
            assert moment == "after"
            change()
    assert error.value.code == "METADATA_CHANGED"
    assert registry.choices() == []
    with pytest.raises(module.PhysicalCameraReopenError):
        registry.preview(token)


def test_new_discovery_invalidates_old_opaque_ticket(registry, tmp_path):
    metadata_store(tmp_path)
    old = discover(registry)
    token = registry.choices()[0]["value"]
    discover(registry)
    assert registry.choices()[0]["value"] != token
    with pytest.raises(module.PhysicalCameraReopenError):
        with select(registry, choice=token, digest=old["discovery_sha256"]):
            pytest.fail("stale ticket entered")


@pytest.mark.parametrize("where", ["discovery", "selected-before", "selected-after"])
def test_cancel_holds_original_state(registry, tmp_path, where):
    metadata_store(tmp_path)
    stop = threading.Event()
    if where == "discovery":
        stop.set()
        with pytest.raises(module.PhysicalCameraReopenError) as error:
            registry.discover(
                cancellation=stop, deadline_ns=time.monotonic_ns() + 1_000_000_000
            )
    else:
        discover(registry)
        if where == "selected-before":
            stop.set()
        with pytest.raises(module.PhysicalCameraReopenError) as error:
            with select(registry, cancel=stop):
                stop.set()
    assert error.value.code == "CANCELLED"
    assert registry.choices() == []


def test_source_rechecked_after_selected_body(registry, tmp_path, monkeypatch):
    metadata_store(tmp_path)
    discover(registry)
    with pytest.raises(module.PhysicalCameraReopenError) as error:
        with select(registry):
            monkeypatch.setattr(module, "source_fingerprint", lambda _: "f" * 64)
    assert error.value.code == "SOURCE_CHANGED"
    assert registry.choices() == []


@pytest.mark.parametrize("deadline", [True, -1, 2**63, None])
def test_original_bounded_deadline_required(registry, deadline):
    with pytest.raises(module.PhysicalCameraReopenError) as error:
        registry.discover(cancellation=threading.Event(), deadline_ns=deadline)
    assert error.value.code == "INVALID_REQUEST"


def test_selected_deadline_cannot_renew_after_body(registry, tmp_path, monkeypatch):
    metadata_store(tmp_path)
    discover(registry)
    now = time.monotonic_ns()
    with pytest.raises(module.PhysicalCameraReopenError) as error:
        with registry.selected(
            registry.choices()[0]["value"],
            registry.view()["discovery_sha256"],
            cancellation=threading.Event(),
            deadline_ns=now + 1_000_000_000,
        ):
            monkeypatch.setattr(
                module.time, "monotonic_ns", lambda: now + 1_000_000_001
            )
    assert error.value.code == "DEADLINE_EXPIRED"


def test_selected_scope_blocks_parallel_discovery(registry, tmp_path):
    metadata_store(tmp_path)
    discover(registry)
    with select(registry):
        with pytest.raises(module.PhysicalCameraReopenError) as error:
            discover(registry)
        assert error.value.code == "REGISTRY_BUSY"


@pytest.mark.parametrize(
    "change",
    [
        "unknown",
        "domain",
        "identity",
        "bytes",
        "sha",
        "origin",
        "directory",
        "matches",
        "header",
        "authority",
    ],
)
def test_descriptor_is_closed_and_cross_bound(registry, tmp_path, change):
    metadata_store(tmp_path)
    discover(registry)
    with select(registry) as descriptor:
        value = descriptor.to_dict()
    if change == "unknown":
        value["accepted"] = True
    elif change == "domain":
        value["source_binding_sha256"] = "f" * 64
    elif change == "identity":
        value["directory_identities"][0]["file_id"] = 12
    elif change == "bytes":
        value["metadata_files"][0]["bytes"] += 1
    elif change == "sha":
        value["metadata_files"][0]["sha256"] = "f" * 64
    elif change == "origin":
        value["origin_launch_id"] = CURRENT
    elif change == "directory":
        value["directory"] = str(tmp_path / "some-other-directory")
    elif change == "matches":
        value["source_matches"] = False
    elif change == "header":
        value["metadata"]["header"]["mode"] = "REHEARSAL"
    else:
        value["physical_authority"] = 0
    with pytest.raises(module.PhysicalCameraReopenError):
        module.PhysicalCameraStoreDescriptor(module._json(value))


@pytest.mark.parametrize(
    "payload", [b"{}", b"null", b"{}\n", b"{" * 16000, bytearray(b"{}")]
)
def test_descriptor_malformed_bytes_have_fixed_error(payload):
    with pytest.raises(module.PhysicalCameraReopenError):
        module.PhysicalCameraStoreDescriptor(payload)


@pytest.mark.parametrize(
    "error",
    [RuntimeError("original storage failure"), KeyboardInterrupt(), SystemExit(3)],
)
def test_consumer_failure_preserved_and_selection_revoked(registry, tmp_path, error):
    metadata_store(tmp_path)
    discover(registry)
    with pytest.raises(type(error)) as caught:
        with select(registry):
            raise error
    assert caught.value is error
    assert registry.view()["status"] == "INVALIDATED"
    assert registry.choices() == []


def test_identity_replacement_with_identical_bytes_is_stale(registry, tmp_path):
    _, header, _ = metadata_store(tmp_path)
    discover(registry)
    replacement = header.with_name("replacement.json")
    replacement.write_bytes(header.read_bytes())
    os.replace(replacement, header)
    with pytest.raises(module.PhysicalCameraReopenError) as caught:
        with select(registry):
            pytest.fail("replaced identity admitted")
    assert caught.value.code == "METADATA_CHANGED"


def test_midread_cancellation_does_not_publish_partial_choices(
    registry, tmp_path, monkeypatch
):
    metadata_store(tmp_path)
    stop = threading.Event()
    original = module.read_bounded_regular_file

    def cancel_after_read(*args, **kwargs):
        result = original(*args, **kwargs)
        stop.set()
        return result

    monkeypatch.setattr(module, "read_bounded_regular_file", cancel_after_read)
    with pytest.raises(module.PhysicalCameraReopenError) as caught:
        registry.discover(
            cancellation=stop, deadline_ns=time.monotonic_ns() + 30_000_000_000
        )
    assert caught.value.code == "CANCELLED"
    assert registry.view()["stores"] == []


def test_same_source_wrong_lineage_held(registry, tmp_path):
    directory, header_path, cell_path = metadata_store(tmp_path)
    old_header = json.loads(header_path.read_bytes())
    old_cell = json.loads(cell_path.read_bytes())
    wrong_cell = M1CellDescriptor.build(
        cell_id="wizard-physical-camera-" + "f" * 16,
        source_binding_sha256=old_cell["source_binding_sha256"],
        durability_qualification_sha256=old_cell["durability_qualification_sha256"],
        created_at_ns=old_cell["created_at_ns"],
    )
    wrong_header = V2SessionHeader.build(
        session_id=old_header["session_id"],
        cell_id=wrong_cell.cell_id,
        created_at_ns=old_header["created_at_ns"],
        source_binding_sha256=old_header["source_binding_sha256"],
        publication_durability=WINDOWS_NTFS_QUALIFIED,
        durability_qualification_sha256=old_header["durability_qualification_sha256"],
    )
    cell_path.write_bytes(canonical_bytes(wrong_cell.to_dict()))
    cell_path.parent.rename(
        directory / "cells" / ("cell-" + wrong_cell.cell_key_sha256)
    )
    header_path.write_bytes(_canonical_bytes(wrong_header.to_dict()))
    assert discover(registry)["issues"][0]["code"] == "LINEAGE_MISMATCH"


@pytest.mark.skipif(
    os.name != "nt", reason="actual Windows directory sharing semantics"
)
def test_selected_guard_denies_own_leaf_and_ancestor_rename(registry, tmp_path):
    directory, _, _ = metadata_store(tmp_path)
    discover(registry)
    with select(registry):
        for original in (directory, registry.root):
            with pytest.raises(OSError):
                original.rename(original.with_name(original.name + "-renamed"))


def test_registry_bindings_are_read_only(registry):
    for name in ("workspace", "root", "source_sha256", "current_launch_id"):
        with pytest.raises(AttributeError):
            setattr(registry, name, "changed")


def revalidate(registry, descriptor, *, digest=None, cancellation=None):
    return registry.revalidate_original(
        descriptor,
        digest or descriptor.descriptor_sha256,
        cancellation=cancellation or threading.Event(),
        deadline_ns=time.monotonic_ns() + 120_000_000_000,
    )


def test_explicit_original_revalidation_never_revives_failed_choice(registry, tmp_path):
    metadata_store(tmp_path)
    discover(registry)
    token = registry.choices()[0]["value"]
    original = registry.descriptor(token)
    original_digest = registry.preview(token)["descriptor_sha256"]
    failure = RuntimeError("modeled M1 readback failure")
    with pytest.raises(RuntimeError) as caught:
        with select(registry):
            raise failure
    assert caught.value is failure
    with pytest.raises(module.PhysicalCameraReopenError):
        registry.descriptor(token)
    before = registry.view()
    with revalidate(registry, original, digest=original_digest) as observed:
        assert observed.payload == original.payload
        assert observed is not original
    assert registry.view() == before
    assert registry.choices() == []
    with pytest.raises(module.PhysicalCameraReopenError):
        registry.preview(token)


def test_precancelled_open_retains_original_for_later_explicit_inspection(
    registry, tmp_path
):
    metadata_store(tmp_path)
    discover(registry)
    original = registry.descriptor(registry.choices()[0]["value"])
    stop = threading.Event()
    stop.set()
    with pytest.raises(module.PhysicalCameraReopenError) as caught:
        with select(registry, cancel=stop):
            pytest.fail("cancelled selection entered")
    assert caught.value.code == "CANCELLED"
    with revalidate(registry, original) as observed:
        assert observed.descriptor_sha256 == original.descriptor_sha256
    assert registry.choices() == []


def test_descriptor_getter_is_pure(registry, tmp_path, monkeypatch):
    metadata_store(tmp_path)
    discover(registry)
    token = registry.choices()[0]["value"]

    def denied(*args, **kwargs):
        pytest.fail("descriptor getter must not touch filesystem/source")

    for name in ("stat", "iterdir", "open", "resolve"):
        monkeypatch.setattr(Path, name, denied)
    monkeypatch.setattr(module, "source_fingerprint", denied)
    assert (
        registry.descriptor(token).descriptor_sha256
        == registry.preview(token)["descriptor_sha256"]
    )


@pytest.mark.parametrize(
    "kind", ["hash", "launch", "workspace", "source", "dict", "subclass"]
)
def test_explicit_revalidation_requires_original_exact_context(
    registry, tmp_path, monkeypatch, kind
):
    metadata_store(tmp_path)
    discover(registry)
    original = registry.descriptor(registry.choices()[0]["value"])
    digest = original.descriptor_sha256
    receiver = registry
    if kind == "hash":
        digest = "f" * 64
    elif kind == "launch":
        receiver = module.PhysicalCameraReopenRegistry(
            tmp_path, current_launch_id="wizard-" + "9" * 32, source_sha256=SOURCE
        )
    elif kind == "workspace":
        receiver = module.PhysicalCameraReopenRegistry(
            tmp_path / "other", current_launch_id=CURRENT, source_sha256=SOURCE
        )
    elif kind == "source":
        receiver = module.PhysicalCameraReopenRegistry(
            tmp_path, current_launch_id=CURRENT, source_sha256="b" * 64
        )
    elif kind == "dict":
        original = original.to_dict()
    else:

        class Substitute(module.PhysicalCameraStoreDescriptor):
            pass

        original = Substitute(original.payload)
    calls = []
    monkeypatch.setattr(module, "_directory_guard", lambda *a, **k: calls.append(a))
    with pytest.raises(module.PhysicalCameraReopenError):
        with revalidate(receiver, original, digest=digest):
            pytest.fail("non-original descriptor entered")
    assert calls == []
    assert receiver.choices() == []


@pytest.mark.parametrize("moment", ["before", "after"])
def test_explicit_revalidation_does_not_accept_changed_original(
    registry, tmp_path, moment
):
    _, header, _ = metadata_store(tmp_path)
    discover(registry)
    original = registry.descriptor(registry.choices()[0]["value"])
    registry.invalidate()

    def change():
        value = header.stat()
        os.utime(header, ns=(value.st_atime_ns, value.st_mtime_ns + 1_000_000))

    if moment == "before":
        change()
    with pytest.raises(module.PhysicalCameraReopenError) as caught:
        with revalidate(registry, original):
            assert moment == "after"
            change()
    assert caught.value.code == "METADATA_CHANGED"
    assert registry.choices() == []


def test_explicit_revalidation_source_and_cancel_checks_after_body(
    registry, tmp_path, monkeypatch
):
    metadata_store(tmp_path)
    discover(registry)
    original = registry.descriptor(registry.choices()[0]["value"])
    registry.invalidate()
    stop = threading.Event()
    with pytest.raises(module.PhysicalCameraReopenError) as caught:
        with revalidate(registry, original, cancellation=stop):
            stop.set()
    assert caught.value.code == "CANCELLED"
    with pytest.raises(module.PhysicalCameraReopenError) as caught:
        with revalidate(registry, original):
            monkeypatch.setattr(module, "source_fingerprint", lambda _: "b" * 64)
    assert caught.value.code == "SOURCE_CHANGED"
    assert registry.choices() == []
